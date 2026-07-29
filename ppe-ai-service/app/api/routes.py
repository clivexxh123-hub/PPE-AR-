from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.schemas.tasks import GenerateRequest, LogoPlaceRequest, TaskResponse, TaskStatus
from app.services.generation_engine import generate_ai_image
from app.services.input_adapter import resolve_image_source, save_upload
from app.services.logo_service import normalize_logo
from app.services.prompt_templates import build_prompt
from app.services.task_store import create_task, load_task, save_task, to_response

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
