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
from app.services.image_asset_service import validate_generate_request_images
from app.services.input_adapter import resolve_image_source, save_upload
from app.services.logo_service import normalize_logo
from app.services.prompt_templates import build_prompt
from app.services.storage_service import StorageUploadResult, upload_result
from app.services.task_store import create_task, load_task, load_task_payload, save_task, to_response

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
    summary="提交业务 AI 生成任务",
    description="接收业务端 GenerationTaskInput 风格任务。当前阶段 inputAssets 只记录不解析，callback 支持 HTTP(S) 发送和 internal:// 记录。",
    tags=["AI 图片生成"],
)
async def create_business_ai_task(payload: GenerationTaskInput, background_tasks: BackgroundTasks) -> BusinessTaskResponse:
    record = create_task("ai.business_generate", payload.model_dump(mode="json"), task_id=payload.jobId)
    save_task(record, extra=_business_extra(payload))
    if bool(payload.parameters.get("sync", False)):
        await _run_business_generate_task(payload)
    else:
        background_tasks.add_task(_run_business_generate_task, payload)
    return _business_response(load_task(payload.jobId) or record)


@router.post(
    "/logo/remove-bg",
    response_model=TaskResponse,
    summary="Logo 透明底处理",
    description="将 Logo 规范化为透明 PNG 画布。当前为占位实现，后续会接入真实抠图模型。",
    tags=["Logo 处理"],
)
async def remove_logo_background(payload: LogoPlaceRequest, background_tasks: BackgroundTasks) -> TaskResponse:
    record = create_task("logo.remove_bg", payload.model_dump(mode="json"))
    if payload.sync:
        await _run_logo_task(record.task_id, payload)
    else:
        background_tasks.add_task(_run_logo_task, record.task_id, payload)
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
        await _run_logo_task(record.task_id, payload)
    else:
        background_tasks.add_task(_run_logo_task, record.task_id, payload)
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
        assets.setdefault(asset.role, []).append(asset.model_dump(mode="json"))
    return assets


def _asset_warnings(task: GenerationTaskInput) -> list[dict[str, str]]:
    roles = {asset.role for asset in task.inputAssets}
    product_image_url = _image_url_from_parameter(task.parameters, "product_image")
    logo_image_url = _image_url_from_parameter(task.parameters, "logo_image")
    warnings: list[dict[str, str]] = []
    if "product_reference" in roles and not product_image_url:
        warnings.append(
            {
                "code": "MISSING_PRODUCT_IMAGE_URL",
                "message": "inputAssets 包含 product_reference，但 parameters.product_image.url 缺失；当前按文生图继续。",
            }
        )
    if "logo" in roles and not logo_image_url:
        warnings.append(
            {
                "code": "MISSING_LOGO_IMAGE_URL",
                "message": "inputAssets 包含 logo，但 parameters.logo_image.url 缺失；当前按文生图继续。",
            }
        )
    return warnings


def _validated_product_image_path(input_asset_validation: dict[str, Any] | None) -> Path | None:
    if not isinstance(input_asset_validation, dict):
        return None
    product_image = input_asset_validation.get("product_image")
    if not isinstance(product_image, dict):
        return None
    if product_image.get("validation_status") != "passed":
        return None
    local_path = product_image.get("local_path")
    if not local_path:
        return None
    return Path(str(local_path))

def _parameters_to_generate_request(parameters: dict[str, Any]) -> GenerateRequest:
    prompt_overrides = parameters.get("prompt_overrides")
    if not isinstance(prompt_overrides, dict):
        prompt_overrides = {}
    return GenerateRequest(
        product_image=_image_source_from_parameter(parameters.get("product_image")),
        logo_image=_image_source_from_parameter(parameters.get("logo_image")),
        product_name=str(parameters.get("product_name", "")).strip(),
        product_category=str(parameters.get("product_category", "")).strip(),
        scene=str(parameters.get("scene", "")).strip(),
        style=str(parameters.get("style", "")).strip(),
        size=str(parameters.get("size", "512x512")).strip(),
        prompt_overrides=prompt_overrides,
        output_format=str(parameters.get("output_format", "png")).strip(),
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
) -> dict[str, Any]:
    product_image_url = _image_url_from_parameter(task.parameters, "product_image")
    logo_image_url = _image_url_from_parameter(task.parameters, "logo_image")
    payload: dict[str, Any] = {
        "business_protocol": {
            "jobId": task.jobId,
            "tenantId": task.tenantId,
            "traceId": task.traceId,
            "attempt": task.attempt,
            "modelProfileId": task.modelProfileId,
            "workflowVersion": task.workflowVersion,
            "inputAssets": [asset.model_dump(mode="json") for asset in task.inputAssets],
            "inputAssetsByRole": _assets_by_role(task),
            "raw_callback": task.callback,
            "callback_source": "GenerationTaskInput.callback",
            "parameters": task.parameters,
            "image_urls": {
                "product_image": product_image_url,
                "logo_image": logo_image_url,
            },
            "output": {
                "assetKey": task.output.assetKey,
                "method": task.output.method,
                "requiredHeaders": task.output.requiredHeaders,
                "expiresAt": task.output.expiresAt,
                "uploadUrl_present": True,
            }
            if task.output
            else None,
            "input_asset_validation": input_asset_validation or {},
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
        payload["business_last_callback"] = callback_result
        if callback_result.get("callback_skipped"):
            payload["business_protocol"]["callback_skipped"] = True
            payload["business_protocol"]["callback_skip_reason"] = callback_result.get("reason")
        if callback_result.get("callback"):
            payload["business_protocol"]["callback_url"] = callback_result.get("callback")
        if callback_result.get("sent") is False and not callback_result.get("callback_skipped"):
            payload["business_callback_error"] = callback_result
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
    return BusinessTaskResponse(
        jobId=str(protocol.get("jobId") or record.task_id),
        task_id=record.task_id,
        status=record.status,
        message=record.message,
        result_url=record.result_url,
        metadata_url=record.metadata_url,
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
    return await send_worker_callback(task.callback, event)


async def _run_business_generate_task(task: GenerationTaskInput) -> None:
    started_at = time.monotonic()
    input_asset_validation: dict[str, Any] | None = None
    record = load_task(task.jobId)
    if record is None:
        return
    try:
        record.status = TaskStatus.running
        record.message = f"正在使用 {settings.ai_engine} 引擎处理业务 AI 任务。"
        callback_result = await _report_business_event(task, TaskStatus.running, started_at, progress=10)
        save_task(record, extra=_business_extra(task, callback_result=callback_result))

        generate_payload = _parameters_to_generate_request(task.parameters)
        input_asset_validation = await validate_generate_request_images(generate_payload)
        save_task(record, extra=_business_extra(task, callback_result=callback_result, input_asset_validation=input_asset_validation))
        prompt = build_prompt(
            product_name=generate_payload.product_name,
            product_category=generate_payload.product_category,
            scene=generate_payload.scene,
            style=generate_payload.style,
            overrides=generate_payload.prompt_overrides,
        )
        image_path, metadata_path, engine = await generate_ai_image(
            task.jobId,
            prompt,
            generate_payload.size,
            generate_payload.output_format,
            product_image_path=_validated_product_image_path(input_asset_validation),
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
        )
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
        prompt = build_prompt(
            product_name=payload.product_name,
            product_category=payload.product_category,
            scene=payload.scene,
            style=payload.style,
            overrides=payload.prompt_overrides,
        )
        image_path, metadata_path, engine = await generate_ai_image(task_id, prompt, payload.size, payload.output_format)
        record.status = TaskStatus.succeeded
        record.message = f"图片已生成，当前使用 {engine} 引擎。"
        record.output_path = str(image_path)
        record.metadata_path = str(metadata_path)
        record.result_url = f"/outputs/{task_id}/{image_path.name}"
        record.metadata_url = f"/outputs/{task_id}/{metadata_path.name}"
        save_task(record)
    except Exception as exc:
        record.status = TaskStatus.failed
        record.message = "AI 图片生成失败。"
        record.error = str(exc)
        save_task(record)


async def _run_logo_task(task_id: str, payload: LogoPlaceRequest) -> None:
    record = load_task(task_id)
    if record is None:
        return
    try:
        record.status = TaskStatus.running
        record.message = "正在处理 Logo 占位流程。"
        save_task(record)
        logo_path = await resolve_image_source(payload.logo_image)
        image_path, metadata_path = normalize_logo(task_id, logo_path, payload.output_format)
        record.status = TaskStatus.succeeded
        record.message = "Logo 占位处理已完成。后续会接入真实抠图和贴图逻辑。"
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





