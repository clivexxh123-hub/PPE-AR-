import time
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.schemas.business_protocol import BusinessTaskResponse, GenerationTaskInput, TaskResult, WorkerCallbackEvent
from app.schemas.tasks import GenerateRequest, ImageSource, LogoPlaceRequest, TaskResponse, TaskStatus
from app.services.asset_result import build_business_task_result
from app.services.callback_service import send_worker_callback
from app.services.error_codes import map_exception_to_error
from app.services.generation_engine import generate_ai_image
from app.services.human_wearing_service import render_human_wearing_design
from app.services.image_asset_service import (
    ImageAssetValidationError,
    validate_alpha_channel,
    validate_generate_request_images,
    validate_image_source,
)
from app.services.input_adapter import resolve_image_source, save_upload
from app.services.logo_service import normalize_logo, render_printed_design
from app.services.prompt_templates import (
    PromptBuildResult,
    build_managed_prompt,
    build_scene_background_prompt,
)
from app.services.scene_composite_service import render_scene_marketing_image
from app.services.storage_service import StorageUploadResult, upload_result
from app.services.task_store import create_task, load_task, load_task_payload, save_task, to_response
from app.services.url_security import redact_headers, redact_sensitive_data, redact_url

router = APIRouter()


@router.post(
    "/files",
    response_model=dict[str, str],
    summary="上传图片文件",
    description="上传产品图或 Logo 图，返回 file_id；后续生成接口可以通过 file_id 引用该文件。",
    tags=["文件管理"],
)
async def upload_file(file: UploadFile = File(..., description="产品图或 Logo 图文件")) -> dict[str, str]:
    file_id = await save_upload(file)
    return {"file_id": file_id}


@router.post(
    "/ai/generate",
    response_model=TaskResponse,
    summary="生成 AI 营销图片",
    description="根据产品信息、场景、风格和 Prompt 模板创建图片生成任务。默认使用 mock 引擎；设置 AI_ENGINE=comfyui 后会调用 ComfyUI / Flux 工作流。",
    tags=["AI 图片生成"],
)
async def generate_image(payload: GenerateRequest, background_tasks: BackgroundTasks) -> TaskResponse:
    record = create_task("ai.generate", payload.model_dump(mode="json"))
    if payload.sync:
        await _run_generate_task(record.task_id, payload)
    else:
        background_tasks.add_task(_run_generate_task, record.task_id, payload)
    return to_response(load_task(record.task_id) or record)


@router.post(
    "/ai/tasks",
    response_model=BusinessTaskResponse,
    summary="提交业务 AI 任务",
    description="接收 image_generation、logo_remove_bg 或 print_render 任务，并复用统一状态、结果、上传与回调结构。",
    tags=["AI 图片生成"],
)
async def create_business_ai_task(payload: GenerationTaskInput, background_tasks: BackgroundTasks) -> BusinessTaskResponse:
    if settings.ai_task_require_formal_contract:
        try:
            payload.validate_formal_contract()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    request_payload = redact_sensitive_data(payload.model_dump(mode="json"))
    _redact_input_asset_urls(request_payload)
    record = create_task(f"ai.business_{payload.type}", request_payload, task_id=payload.jobId)
    save_task(record, extra=_business_extra(payload))
    if bool(payload.parameters.get("sync", False)):
        await _run_business_task(payload)
    else:
        background_tasks.add_task(_run_business_task, payload)
    return _business_response(load_task(payload.jobId) or record)


@router.post(
    "/logo/remove-bg",
    response_model=TaskResponse,
    summary="Logo 透明底处理",
    description="将常见简单背景的 Logo 处理为透明 PNG。复杂背景仍需要后续增强。",
    tags=["Logo 处理"],
)
async def remove_logo_background(payload: LogoPlaceRequest, background_tasks: BackgroundTasks) -> TaskResponse:
    record = create_task("logo.remove_bg", payload.model_dump(mode="json"))
    if payload.sync:
        await _run_logo_task(record.task_id, payload, operation="remove_bg")
    else:
        background_tasks.add_task(_run_logo_task, record.task_id, payload, "remove_bg")
    return to_response(load_task(record.task_id) or record)


@router.post(
    "/logo/place",
    response_model=TaskResponse,
    summary="Logo 智能贴图",
    description="根据位置和缩放规则将 Logo 贴到营销图上。当前为占位实现，后续会加入真实贴图逻辑。",
    tags=["Logo 处理"],
)
async def place_logo(payload: LogoPlaceRequest, background_tasks: BackgroundTasks) -> TaskResponse:
    record = create_task("logo.place", payload.model_dump(mode="json"))
    if payload.sync:
        await _run_logo_task(record.task_id, payload, operation="place")
    else:
        background_tasks.add_task(_run_logo_task, record.task_id, payload, "place")
    return to_response(load_task(record.task_id) or record)


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="查询任务状态",
    description="根据 task_id 查询 AI 生成或 Logo 处理任务的状态、结果地址和元数据地址。",
    tags=["任务管理"],
)
def get_task(task_id: str) -> TaskResponse:
    record = load_task(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return to_response(record)


@router.get(
    "/ai/tasks/{job_id}",
    response_model=BusinessTaskResponse,
    summary="查询业务 AI 任务",
    description="根据 jobId 查询 /ai/tasks 提交的统一业务任务状态、结果和错误信息。",
    tags=["AI 图片生成"],
)
def get_business_ai_task(job_id: str) -> BusinessTaskResponse:
    record = load_task(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return _business_response(record)


@router.get(
    "/outputs/{task_id}/{filename}",
    summary="获取结果文件",
    description="根据 task_id 和文件名读取生成结果，例如 result.png 或 metadata.json。",
    tags=["结果文件"],
)
def get_output_file(task_id: str, filename: str) -> FileResponse:
    path = settings.output_dir / task_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在。")
    return FileResponse(path)


def _image_source_from_parameter(value: Any) -> ImageSource | None:
    if not isinstance(value, dict):
        return None
    payload = {key: value.get(key) for key in ("file_id", "url", "local_path") if value.get(key)}
    if not payload:
        return None
    return ImageSource.model_validate(payload)


def _image_url_from_parameter(parameters: dict[str, Any], key: str) -> str | None:
    value = parameters.get(key)
    if not isinstance(value, dict):
        return None
    url = value.get("url")
    if url is None:
        return None
    url_text = str(url).strip()
    return url_text or None


def _assets_by_role(task: GenerationTaskInput) -> dict[str, list[dict[str, Any]]]:
    assets: dict[str, list[dict[str, Any]]] = {}
    for asset in task.inputAssets:
        item = asset.model_dump(mode="json")
        if item.get("url"):
            item["url"] = redact_url(str(item["url"]))
        assets.setdefault(asset.role, []).append(item)
    return assets


def _redact_input_asset_urls(payload: dict[str, Any]) -> None:
    assets = payload.get("inputAssets")
    if not isinstance(assets, list):
        return
    for asset in assets:
        if isinstance(asset, dict) and asset.get("url"):
            asset["url"] = redact_url(str(asset["url"]))


def _parameters_with_input_assets(task: GenerationTaskInput) -> dict[str, Any]:
    """Adapt frozen inputAssets URLs to the existing image-source parameter shape."""
    parameters = dict(task.parameters)
    for asset in task.inputAssets:
        if asset.url is None:
            continue
        source = {"url": str(asset.url)}
        if asset.role == "product_reference" and not parameters.get("product_image"):
            parameters["product_image"] = source
        elif asset.role == "logo" and not parameters.get("logo_image"):
            parameters["logo_image"] = source
    return parameters


def _asset_warnings(task: GenerationTaskInput) -> list[dict[str, str]]:
    roles = {asset.role for asset in task.inputAssets}
    parameters = _parameters_with_input_assets(task)
    product_image_url = _image_url_from_parameter(parameters, "product_image")
    logo_image_url = _image_url_from_parameter(parameters, "logo_image")
    warnings: list[dict[str, str]] = []
    if "product_reference" in roles and not product_image_url:
        warnings.append(
            {
                "code": "MISSING_PRODUCT_IMAGE_URL",
                "message": "inputAssets 包含 product_reference，但未提供可用产品图片 URL；当前按文生图继续。",
            }
        )
    if "logo" in roles and not logo_image_url:
        warnings.append(
            {
                "code": "MISSING_LOGO_IMAGE_URL",
                "message": "inputAssets 包含 logo，但未提供可用 Logo 图片 URL；当前按文生图继续。",
            }
        )
    return warnings


def _validated_product_image_path(input_asset_validation: dict[str, Any] | None) -> Path | None:
    return _validated_image_path(input_asset_validation, "product_image")


def _validated_image_path(input_asset_validation: dict[str, Any] | None, key: str) -> Path | None:
    if not isinstance(input_asset_validation, dict):
        return None
    image = input_asset_validation.get(key)
    if not isinstance(image, dict):
        return None
    if image.get("validation_status") != "passed":
        return None
    local_path = image.get("local_path")
    if not local_path:
        return None
    return Path(str(local_path))


def _validated_logo_image_path(input_asset_validation: dict[str, Any] | None) -> Path | None:
    return _validated_image_path(input_asset_validation, "logo_image")


def _placement_summary(metadata_path: Path) -> dict[str, Any]:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        key: metadata[key]
        for key in ("placement_mode", "final_x_ratio", "final_y_ratio", "final_width_ratio")
        if key in metadata
    }


def _prepare_generation_input(
    task: GenerationTaskInput,
    input_asset_validation: dict[str, Any] | None,
) -> tuple[Path | None, dict[str, Any]]:
    product_image_path = _validated_product_image_path(input_asset_validation)
    logo_image_path = _validated_logo_image_path(input_asset_validation)
    if product_image_path is None or logo_image_path is None:
        missing = []
        if product_image_path is None:
            missing.append("product_image")
        if logo_image_path is None:
            missing.append("logo_image")
        return product_image_path, {
            "printed_design_used": False,
            "reason": f"missing_validated_{'_and_'.join(missing)}",
        }

    position = str(task.parameters["position"]) if task.parameters.get("position") is not None else None
    position_x_ratio = (
        float(task.parameters["position_x_ratio"])
        if task.parameters.get("position_x_ratio") is not None
        else None
    )
    position_y_ratio = (
        float(task.parameters["position_y_ratio"])
        if task.parameters.get("position_y_ratio") is not None
        else None
    )
    logo_width_ratio = (
        float(task.parameters["logo_width_ratio"])
        if task.parameters.get("logo_width_ratio") is not None
        else (float(task.parameters["scale"]) if task.parameters.get("scale") is not None else None)
    )
    opacity = float(task.parameters.get("opacity", 1.0))
    printed_design_path, printed_metadata_path = render_printed_design(
        f"{task.jobId}-printed-design",
        product_image_path,
        logo_image_path,
        position=position,
        position_x_ratio=position_x_ratio,
        position_y_ratio=position_y_ratio,
        logo_width_ratio=logo_width_ratio,
        opacity=opacity,
    )
    placement = _placement_summary(printed_metadata_path)
    return printed_design_path, {
        "printed_design_used": True,
        "path": str(printed_design_path),
        "metadata_path": str(printed_metadata_path),
        "product_image_path": str(product_image_path),
        "logo_image_path": str(logo_image_path),
        **placement,
        "opacity": opacity,
    }


async def _prepare_human_wearing_input(
    task: GenerationTaskInput,
    generate_payload: GenerateRequest,
    input_asset_validation: dict[str, Any] | None,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    validation = dict(input_asset_validation or {})
    human_source = _image_source_from_parameter(task.parameters.get("human_reference"))
    ppe_source = _image_source_from_parameter(
        task.parameters.get("ppe_reference") or task.parameters.get("product_image")
    )
    if human_source is None:
        raise ValueError("human_wearing 需要 parameters.human_reference。")
    if ppe_source is None:
        raise ValueError("human_wearing 需要 parameters.ppe_reference 或透明 product_image。")

    try:
        validation["human_reference"] = await validate_image_source(human_source, "human_reference")
        validation["ppe_reference"] = await validate_image_source(ppe_source, "ppe_reference")
        ppe_path = _validated_image_path(validation, "ppe_reference")
        if ppe_path is None:
            raise ValueError("ppe_reference 校验失败。")
        validation["ppe_reference"].update(validate_alpha_channel(ppe_path, "ppe_reference"))
    except ImageAssetValidationError as exc:
        combined = dict(validation)
        ppe_validation = combined.get("ppe_reference")
        if isinstance(ppe_validation, dict):
            ppe_validation.update(exc.validation_result)
        else:
            combined.update(exc.validation_result)
        raise ImageAssetValidationError(str(exc), combined) from exc

    human_path = _validated_image_path(validation, "human_reference")
    ppe_path = _validated_image_path(validation, "ppe_reference")
    if human_path is None or ppe_path is None:
        raise ValueError("human_reference 或 ppe_reference 校验失败。")

    position_x_ratio = float(task.parameters.get("position_x_ratio", 0.5))
    position_y_ratio = float(task.parameters.get("position_y_ratio", 0.0))
    ppe_width_ratio = float(
        task.parameters.get("ppe_width_ratio", task.parameters.get("logo_width_ratio", 0.30))
    )
    opacity = float(task.parameters.get("opacity", 1.0))
    image_path, metadata_path = render_human_wearing_design(
        f"{task.jobId}-human-wearing",
        human_path,
        ppe_path,
        size=generate_payload.size,
        position_x_ratio=position_x_ratio,
        position_y_ratio=position_y_ratio,
        ppe_width_ratio=ppe_width_ratio,
        opacity=opacity,
    )
    return image_path, {
        "printed_design_used": True,
        "human_wearing_used": True,
        "generation_mode": "human_wearing",
        "path": str(image_path),
        "metadata_path": str(metadata_path),
        "human_reference_path": str(human_path),
        "ppe_reference_path": str(ppe_path),
        "position_x_ratio": position_x_ratio,
        "position_y_ratio": position_y_ratio,
        "ppe_width_ratio": ppe_width_ratio,
        "opacity": opacity,
    }, validation


def _prepare_scene_generation_foreground(
    input_asset_validation: dict[str, Any] | None,
) -> tuple[Path, dict[str, Any]]:
    """Require a transparent PPE foreground for deterministic scene compositing."""
    validation = dict(input_asset_validation or {})
    product_path = _validated_product_image_path(validation)
    if product_path is None:
        raise ValueError("scene_generation 需要已校验通过的 parameters.product_image。")
    try:
        product_validation = validation.get("product_image")
        if not isinstance(product_validation, dict):
            product_validation = {}
            validation["product_image"] = product_validation
        product_validation.update(validate_alpha_channel(product_path, "product_image"))
    except ImageAssetValidationError as exc:
        combined = dict(validation)
        product_validation = combined.get("product_image")
        if isinstance(product_validation, dict):
            product_validation.update(exc.validation_result)
        else:
            combined["product_image"] = exc.validation_result
        raise ImageAssetValidationError(str(exc), combined) from exc
    return product_path, validation


def _parameters_to_generate_request(parameters: dict[str, Any]) -> GenerateRequest:
    prompt_overrides = parameters.get("prompt_overrides")
    if not isinstance(prompt_overrides, dict):
        prompt_overrides = {}
    return GenerateRequest(
        product_image=_image_source_from_parameter(parameters.get("product_image")),
        logo_image=_image_source_from_parameter(parameters.get("logo_image")),
        product_name=str(parameters.get("product_name", "")).strip(),
        product_category=str(parameters.get("product_category", "")).strip(),
        template_id=(
            str(parameters["template_id"]).strip()
            if parameters.get("template_id") is not None
            else None
        ),
        scene=str(parameters.get("scene", "")).strip(),
        style=str(parameters.get("style", "")).strip(),
        size=str(parameters.get("size", "512x512")).strip(),
        prompt_overrides=prompt_overrides,
        output_format=str(parameters.get("output_format", "png")).strip(),
        sync=bool(parameters.get("sync", False)),
    )


def _parameters_to_logo_request(parameters: dict[str, Any]) -> LogoPlaceRequest:
    base_value = parameters.get("base_image") or parameters.get("product_image")
    return LogoPlaceRequest(
        base_image=_image_source_from_parameter(base_value),
        logo_image=_image_source_from_parameter(parameters.get("logo_image")),
        position=str(parameters["position"]) if parameters.get("position") is not None else None,
        scale=float(parameters["scale"]) if parameters.get("scale") is not None else None,
        position_x_ratio=(
            float(parameters["position_x_ratio"])
            if parameters.get("position_x_ratio") is not None
            else None
        ),
        position_y_ratio=(
            float(parameters["position_y_ratio"])
            if parameters.get("position_y_ratio") is not None
            else None
        ),
        logo_width_ratio=(
            float(parameters["logo_width_ratio"])
            if parameters.get("logo_width_ratio") is not None
            else None
        ),
        opacity=float(parameters.get("opacity", 1.0)),
        output_format=str(parameters.get("output_format", "png")),
        sync=bool(parameters.get("sync", False)),
    )


def _business_extra(
    task: GenerationTaskInput,
    result: TaskResult | None = None,
    storage_result: StorageUploadResult | None = None,
    local_result_url: str | None = None,
    local_output_path: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    retryable: bool | None = None,
    callback_result: dict[str, Any] | None = None,
    input_asset_validation: dict[str, Any] | None = None,
    printed_design: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parameters = _parameters_with_input_assets(task)
    product_image_url = _image_url_from_parameter(parameters, "product_image")
    logo_image_url = _image_url_from_parameter(parameters, "logo_image")
    generation_mode = str(task.parameters.get("generation_mode", "")).strip() or None
    human_wearing_used = bool(printed_design and printed_design.get("human_wearing_used"))
    scene_generation_used = generation_mode == "scene_generation"
    scene_generation_strategy = (
        str(printed_design.get("scene_generation_strategy"))
        if printed_design and printed_design.get("scene_generation_strategy")
        else None
    )
    background_generated = bool(printed_design and printed_design.get("background_generated"))
    product_composited = bool(printed_design and printed_design.get("product_composited"))
    product_reference_used = _validated_product_image_path(input_asset_validation) is not None
    denoise = (
        settings.comfyui_scene_generation_denoise
        if scene_generation_used and scene_generation_strategy != "generated_background_composite"
        else None
    )
    payload: dict[str, Any] = {
        "business_protocol": {
            "jobId": task.jobId,
            "tenantId": task.tenantId,
            "traceId": task.traceId,
            "attempt": task.attempt,
            "modelProfileId": task.modelProfileId,
            "workflowVersion": task.workflowVersion,
            "operation": task.type,
            "inputAssets": [asset.model_dump(mode="json", exclude={"url"}) | ({"url": redact_url(str(asset.url))} if asset.url else {}) for asset in task.inputAssets],
            "inputAssetsByRole": _assets_by_role(task),
            "raw_callback": redact_url(task.callback),
            "callback_source": "GenerationTaskInput.callback",
            "generation_mode": generation_mode,
            "human_wearing_used": human_wearing_used,
            "scene_generation_used": scene_generation_used,
            "scene_generation_strategy": scene_generation_strategy,
            "background_generated": background_generated,
            "product_composited": product_composited,
            "scene": str(task.parameters.get("scene", "")).strip() or None,
            "style": str(task.parameters.get("style", "")).strip() or None,
            "product_reference_used": product_reference_used,
            "denoise": denoise,
            "parameters": redact_sensitive_data(task.parameters),
            "image_urls": {
                "product_image": redact_url(product_image_url),
                "logo_image": redact_url(logo_image_url),
            },
            "output": {
                "assetKey": task.output.assetKey,
                "method": task.output.method,
                "requiredHeaders": redact_headers(task.output.requiredHeaders),
                "expiresAt": task.output.expiresAt,
                "uploadUrl_present": True,
            }
            if task.output
            else None,
            "input_asset_validation": input_asset_validation or {},
            "printed_design_used": bool(printed_design and printed_design.get("printed_design_used")),
            "printed_design": printed_design,
            "asset_warnings": _asset_warnings(task),
            "storage_backend": storage_result.storage_backend if storage_result else settings.storage_backend,
            "oss_uploaded": storage_result.uploaded if storage_result else False,
            "oss_pending": storage_result.pending if storage_result else True,
            "local_result_url": local_result_url,
            "local_output_path": local_output_path,
        }
    }
    if input_asset_validation is not None:
        payload["input_asset_validation"] = input_asset_validation
    payload["printed_design_used"] = bool(printed_design and printed_design.get("printed_design_used"))
    payload["generation_mode"] = generation_mode
    payload["human_wearing_used"] = human_wearing_used
    payload["scene_generation_used"] = scene_generation_used
    payload["scene_generation_strategy"] = scene_generation_strategy
    payload["background_generated"] = background_generated
    payload["product_composited"] = product_composited
    payload["product_reference_used"] = product_reference_used
    payload["denoise"] = denoise
    if printed_design is not None:
        payload["printed_design"] = printed_design
    if result is not None:
        payload["business_result"] = result.model_dump(mode="json")
        payload["business_protocol"]["assetKey"] = result.assetKey
    if storage_result is not None:
        payload["business_storage"] = storage_result.model_dump(mode="json")
        payload["business_protocol"]["local_result_url"] = storage_result.local_url
        payload["business_protocol"]["local_output_path"] = storage_result.local_path
    if error_code or error_message:
        payload["business_error"] = {
            "errorCode": error_code,
            "errorMessage": error_message,
            "retryable": retryable,
        }
    if callback_result is not None:
        safe_callback_result = redact_sensitive_data(callback_result)
        if isinstance(safe_callback_result, dict) and safe_callback_result.get("callback"):
            safe_callback_result["callback"] = redact_url(str(safe_callback_result["callback"]))
        payload["business_last_callback"] = safe_callback_result
        if safe_callback_result.get("callback_skipped"):
            payload["business_protocol"]["callback_skipped"] = True
            payload["business_protocol"]["callback_skip_reason"] = safe_callback_result.get("reason")
        if safe_callback_result.get("callback"):
            payload["business_protocol"]["callback_url"] = safe_callback_result.get("callback")
        if safe_callback_result.get("sent") is False and not safe_callback_result.get("callback_skipped"):
            payload["business_callback_error"] = safe_callback_result
    return payload


def _append_output_metadata(metadata_path, extra: dict[str, Any]) -> None:
    if metadata_path is None or not metadata_path.exists():
        return
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(extra)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def _business_response(record) -> BusinessTaskResponse:
    raw = load_task_payload(record.task_id) or {}
    protocol = raw.get("business_protocol") or {}
    error = raw.get("business_error") or {}
    result_payload = raw.get("business_result")
    result = TaskResult.model_validate(result_payload) if isinstance(result_payload, dict) else None
    formal_response = settings.ai_task_require_formal_contract and protocol.get("output") is not None
    return BusinessTaskResponse(
        jobId=str(protocol.get("jobId") or record.task_id),
        task_id=record.task_id,
        status=record.status,
        message=record.message,
        result_url=None if formal_response else record.result_url,
        metadata_url=None if formal_response else record.metadata_url,
        errorCode=error.get("errorCode"),
        errorMessage=error.get("errorMessage"),
        retryable=error.get("retryable"),
        result=result,
    )


async def _report_business_event(
    task: GenerationTaskInput,
    status: TaskStatus,
    started_at: float,
    progress: int | None = None,
    result: TaskResult | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    retryable: bool | None = None,
) -> dict[str, Any]:
    event = WorkerCallbackEvent(
        jobId=task.jobId,
        attempt=task.attempt,
        status=status,
        progress=progress,
        elapsedMs=int((time.monotonic() - started_at) * 1000),
        errorCode=error_code,
        errorMessage=error_message,
        retryable=retryable,
        modelProfileId=task.modelProfileId,
        workflowVersion=task.workflowVersion,
        result=result,
    )
    return await send_worker_callback(task.callback, event, hmac_secret=settings.callback_hmac_secret)


async def _run_business_task(task: GenerationTaskInput) -> None:
    if task.type == "image_generation":
        await _run_business_generate_task(task)
        return
    await _run_business_logo_task(task)


async def _run_business_logo_task(task: GenerationTaskInput) -> None:
    started_at = time.monotonic()
    input_asset_validation: dict[str, Any] | None = None
    printed_design: dict[str, Any] | None = None
    record = load_task(task.jobId)
    if record is None:
        return
    try:
        record.status = TaskStatus.running
        record.message = f"正在处理业务 {task.type} 任务。"
        callback_result = await _report_business_event(task, TaskStatus.running, started_at, progress=10)
        save_task(record, extra=_business_extra(task, callback_result=callback_result))

        logo_payload = _parameters_to_logo_request(_parameters_with_input_assets(task))
        if logo_payload.logo_image is None:
            raise ValueError("parameters.logo_image 是必填图片输入。")
        input_asset_validation = {
            "logo_image": await validate_image_source(logo_payload.logo_image, "logo"),
        }
        logo_path = _validated_logo_image_path(input_asset_validation)
        if logo_path is None:
            raise ValueError("logo_image 校验失败。")

        if task.type == "logo_remove_bg":
            image_path, metadata_path = normalize_logo(task.jobId, logo_path, logo_payload.output_format)
            completion_message = "业务 Logo 背景抠除已完成。"
        elif task.type == "print_render":
            if logo_payload.base_image is None:
                raise ValueError("print_render 需要 parameters.base_image 或 parameters.product_image。")
            input_asset_validation["base_image"] = await validate_image_source(logo_payload.base_image, "base_image")
            base_path = _validated_image_path(input_asset_validation, "base_image")
            if base_path is None:
                raise ValueError("base_image 校验失败。")
            image_path, metadata_path = render_printed_design(
                task.jobId,
                base_path,
                logo_path,
                position=logo_payload.position,
                position_x_ratio=logo_payload.position_x_ratio,
                position_y_ratio=logo_payload.position_y_ratio,
                logo_width_ratio=(
                    logo_payload.logo_width_ratio
                    if logo_payload.logo_width_ratio is not None
                    else logo_payload.scale
                ),
                opacity=logo_payload.opacity,
            )
            printed_design = {
                "printed_design_used": True,
                "path": str(image_path),
                "metadata_path": str(metadata_path),
                "product_image_path": str(base_path),
                "logo_image_path": str(logo_path),
                "opacity": logo_payload.opacity,
                **_placement_summary(metadata_path),
            }
            completion_message = "业务印刷设计图已生成。"
        else:
            raise ValueError(f"不支持的业务任务类型：{task.type}")

        result = build_business_task_result(
            task.tenantId,
            task.jobId,
            task.attempt,
            image_path,
            asset_key=task.output.assetKey if task.output else None,
        )
        result_url = f"/outputs/{task.jobId}/{image_path.name}"
        storage_result = await upload_result(image_path, result.assetKey, local_url=result_url, output=task.output)
        record.status = TaskStatus.succeeded
        record.message = completion_message
        record.output_path = str(image_path)
        record.metadata_path = str(metadata_path)
        record.result_url = result_url
        record.metadata_url = f"/outputs/{task.jobId}/{metadata_path.name}"
        callback_result = await _report_business_event(task, TaskStatus.succeeded, started_at, progress=100, result=result)
        extra = _business_extra(
            task,
            result=result,
            storage_result=storage_result,
            callback_result=callback_result,
            input_asset_validation=input_asset_validation,
            printed_design=printed_design,
        )
        _append_output_metadata(metadata_path, extra)
        save_task(record, extra=extra)
    except Exception as exc:
        if input_asset_validation is None:
            input_asset_validation = getattr(exc, "validation_result", None)
        error_code, error_message, retryable = map_exception_to_error(exc)
        record.status = TaskStatus.failed
        record.message = f"业务 {task.type} 任务失败。"
        record.error = error_message
        callback_result = await _report_business_event(
            task,
            TaskStatus.failed,
            started_at,
            error_code=error_code,
            error_message=error_message,
            retryable=retryable,
        )
        save_task(
            record,
            extra=_business_extra(
                task,
                error_code=error_code,
                error_message=error_message,
                retryable=retryable,
                callback_result=callback_result,
                input_asset_validation=input_asset_validation,
                printed_design=printed_design,
            ),
        )


async def _run_business_generate_task(task: GenerationTaskInput) -> None:
    started_at = time.monotonic()
    input_asset_validation: dict[str, Any] | None = None
    printed_design: dict[str, Any] = {
        "printed_design_used": False,
        "reason": "not_processed",
    }
    record = load_task(task.jobId)
    if record is None:
        return
    try:
        generation_mode = str(task.parameters.get("generation_mode", "")).strip().lower()
        record.status = TaskStatus.running
        record.message = f"正在使用 {settings.ai_engine} 引擎处理业务 AI 任务。"
        callback_result = await _report_business_event(task, TaskStatus.running, started_at, progress=10)
        save_task(record, extra=_business_extra(task, callback_result=callback_result))

        generate_payload = _parameters_to_generate_request(_parameters_with_input_assets(task))
        input_asset_validation = await validate_generate_request_images(generate_payload)
        save_task(record, extra=_business_extra(task, callback_result=callback_result, input_asset_validation=input_asset_validation))
        if generation_mode == "human_wearing":
            generation_input_path, printed_design, input_asset_validation = await _prepare_human_wearing_input(
                task, generate_payload, input_asset_validation
            )
        elif generation_mode == "scene_generation":
            generation_input_path, input_asset_validation = _prepare_scene_generation_foreground(input_asset_validation)
            printed_design = {
                "printed_design_used": False,
                "scene_generation_strategy": "generated_background_composite",
                "background_generated": False,
                "product_composited": False,
                "ppe_foreground_path": str(generation_input_path),
            }
        else:
            generation_input_path, printed_design = _prepare_generation_input(task, input_asset_validation)
        save_task(
            record,
            extra=_business_extra(
                task,
                callback_result=callback_result,
                input_asset_validation=input_asset_validation,
                printed_design=printed_design,
            ),
        )
        prompt_result = build_managed_prompt(
            product_name=generate_payload.product_name,
            product_category=generate_payload.product_category,
            scene=generate_payload.scene,
            style=generate_payload.style,
            overrides=generate_payload.prompt_overrides,
            template_id=generate_payload.template_id,
            generation_mode=generation_mode,
        )
        prompt = prompt_result.prompt
        generation_kwargs = (
            {"generation_mode": generation_mode}
            if generation_mode in {"human_wearing", "scene_generation"}
            else {}
        )
        if generation_mode == "scene_generation":
            background_prompt = build_scene_background_prompt(
                scene=generate_payload.scene,
                style=generate_payload.style,
                overrides=generate_payload.prompt_overrides,
            )
            prompt_result = PromptBuildResult(
                template_id=prompt_result.template_id,
                selection_rule=prompt_result.selection_rule,
                prompt=background_prompt,
            )
            background_path, background_metadata_path, background_engine = await generate_ai_image(
                f"{task.jobId}-scene-background",
                background_prompt,
                generate_payload.size,
                generate_payload.output_format,
                generation_mode="scene_generation",
            )
            image_path, metadata_path = render_scene_marketing_image(
                task.jobId,
                background_path,
                generation_input_path,
                size=generate_payload.size,
                product_width_ratio=float(task.parameters.get("scene_product_width_ratio", 0.55)),
                position_x_ratio=float(task.parameters.get("position_x_ratio", 0.5)),
                position_y_ratio=float(task.parameters.get("position_y_ratio", 0.58)),
            )
            engine = f"{background_engine}+pillow"
            printed_design.update(
                {
                    "background_generated": True,
                    "product_composited": True,
                    "background_path": str(background_path),
                    "background_metadata_path": str(background_metadata_path),
                    "path": str(image_path),
                    "metadata_path": str(metadata_path),
                }
            )
        else:
            image_path, metadata_path, engine = await generate_ai_image(
                task.jobId,
                prompt,
                generate_payload.size,
                generate_payload.output_format,
                product_image_path=generation_input_path,
                **generation_kwargs,
            )
        result = build_business_task_result(task.tenantId, task.jobId, task.attempt, image_path, asset_key=task.output.assetKey if task.output else None)
        result_url = f"/outputs/{task.jobId}/{image_path.name}"
        storage_result = await upload_result(image_path, result.assetKey, local_url=result_url, output=task.output)
        record.status = TaskStatus.succeeded
        record.message = f"业务 AI 图片已生成，当前使用 {engine} 引擎。"
        record.output_path = str(image_path)
        record.metadata_path = str(metadata_path)
        record.result_url = result_url
        record.metadata_url = f"/outputs/{task.jobId}/{metadata_path.name}"
        callback_result = await _report_business_event(task, TaskStatus.succeeded, started_at, progress=100, result=result)
        extra = _business_extra(
            task,
            result=result,
            storage_result=storage_result,
            callback_result=callback_result,
            input_asset_validation=input_asset_validation,
            printed_design=printed_design,
        )
        prompt_metadata = prompt_result.metadata()
        extra.update(prompt_metadata)
        extra["business_protocol"].update(prompt_metadata)
        _append_output_metadata(metadata_path, extra)
        save_task(record, extra=extra)
    except Exception as exc:
        if input_asset_validation is None:
            input_asset_validation = getattr(exc, "validation_result", None)
        error_code, error_message, retryable = map_exception_to_error(exc)
        record.status = TaskStatus.failed
        record.message = "业务 AI 图片生成失败。"
        record.error = error_message
        callback_result = await _report_business_event(
            task,
            TaskStatus.failed,
            started_at,
            error_code=error_code,
            error_message=error_message,
            retryable=retryable,
        )
        save_task(
            record,
            extra=_business_extra(
                task,
                error_code=error_code,
                error_message=error_message,
                retryable=retryable,
                callback_result=callback_result,
                input_asset_validation=input_asset_validation,
                printed_design=printed_design,
            ),
        )


async def _run_generate_task(task_id: str, payload: GenerateRequest) -> None:
    record = load_task(task_id)
    if record is None:
        return
    try:
        record.status = TaskStatus.running
        record.message = f"正在使用 {settings.ai_engine} 引擎生成图片。"
        save_task(record)
        await resolve_image_source(payload.product_image)
        await resolve_image_source(payload.logo_image)
        prompt_result = build_managed_prompt(
            product_name=payload.product_name,
            product_category=payload.product_category,
            scene=payload.scene,
            style=payload.style,
            overrides=payload.prompt_overrides,
            template_id=payload.template_id,
        )
        image_path, metadata_path, engine = await generate_ai_image(
            task_id,
            prompt_result.prompt,
            payload.size,
            payload.output_format,
        )
        record.status = TaskStatus.succeeded
        record.message = f"图片已生成，当前使用 {engine} 引擎。"
        record.output_path = str(image_path)
        record.metadata_path = str(metadata_path)
        record.result_url = f"/outputs/{task_id}/{image_path.name}"
        record.metadata_url = f"/outputs/{task_id}/{metadata_path.name}"
        prompt_metadata = prompt_result.metadata()
        _append_output_metadata(metadata_path, prompt_metadata)
        save_task(record, extra=prompt_metadata)
    except Exception as exc:
        record.status = TaskStatus.failed
        record.message = "AI 图片生成失败。"
        record.error = str(exc)
        save_task(record)


async def _run_logo_task(task_id: str, payload: LogoPlaceRequest, operation: str = "place") -> None:
    record = load_task(task_id)
    if record is None:
        return
    try:
        record.status = TaskStatus.running
        record.message = "正在处理 Logo 图片。"
        save_task(record)
        logo_path = await resolve_image_source(payload.logo_image)
        if operation == "place":
            base_path = await resolve_image_source(payload.base_image)
            if base_path is None:
                image_path, metadata_path = normalize_logo(task_id, logo_path, payload.output_format)
            else:
                image_path, metadata_path = render_printed_design(
                    task_id,
                    base_path,
                    logo_path,
                    position=payload.position,
                    position_x_ratio=payload.position_x_ratio,
                    position_y_ratio=payload.position_y_ratio,
                    logo_width_ratio=(
                        payload.logo_width_ratio
                        if payload.logo_width_ratio is not None
                        else payload.scale
                    ),
                    opacity=payload.opacity,
                )
        else:
            image_path, metadata_path = normalize_logo(task_id, logo_path, payload.output_format)
        record.status = TaskStatus.succeeded
        record.message = "Logo 图片处理已完成。"
        record.output_path = str(image_path)
        record.metadata_path = str(metadata_path)
        record.result_url = f"/outputs/{task_id}/{image_path.name}"
        record.metadata_url = f"/outputs/{task_id}/{metadata_path.name}"
        save_task(record)
    except Exception as exc:
        record.status = TaskStatus.failed
        record.message = "Logo 处理失败。"
        record.error = str(exc)
        save_task(record)
