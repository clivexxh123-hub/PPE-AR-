import asyncio
import json
import random
from pathlib import Path
from typing import Any

import httpx

from app.core.config import ensure_storage_dirs, settings


class ComfyUIError(RuntimeError):
    """ComfyUI 调用失败时抛出的业务异常。"""


def _parse_size(size: str) -> tuple[int, int]:
    try:
        width_text, height_text = size.lower().split("x", maxsplit=1)
        width = max(256, min(2048, int(width_text)))
        height = max(256, min(2048, int(height_text)))
        return width, height
    except (ValueError, AttributeError):
        return 1024, 1024


def _resolve_workflow_path(workflow_path: Path) -> Path:
    if workflow_path.is_absolute():
        return workflow_path
    return settings.base_dir / workflow_path


def _load_workflow(workflow_path: Path) -> dict[str, Any]:
    resolved_path = _resolve_workflow_path(workflow_path)
    if not resolved_path.exists():
        raise ComfyUIError(f"ComfyUI 工作流文件不存在：{resolved_path}")
    return json.loads(resolved_path.read_text(encoding="utf-8-sig"))


def _node(workflow: dict[str, Any], node_id: str | None) -> dict[str, Any] | None:
    if not node_id:
        return None
    value = workflow.get(str(node_id))
    return value if isinstance(value, dict) else None


def _patch_workflow(
    workflow: dict[str, Any],
    task_id: str,
    prompt: str,
    size: str,
    generation_mode: str,
    comfyui_image_name: str | None = None,
    negative_prompt: str | None = None,
) -> dict[str, Any]:
    width, height = _parse_size(size)
    positive_patched = False
    negative_patched = False
    latent_patched = False
    save_patched = False
    image_patched = comfyui_image_name is None
    denoise_patched = False
    negative_prompt_text = negative_prompt or settings.comfyui_default_negative_prompt

    positive_node = _node(workflow, settings.comfyui_positive_node_id)
    if positive_node is not None:
        positive_node.setdefault("inputs", {})["text"] = prompt
        positive_patched = True

    negative_node = _node(workflow, settings.comfyui_negative_node_id)
    if negative_node is not None:
        negative_node.setdefault("inputs", {})["text"] = negative_prompt_text
        negative_patched = True

    latent_node = _node(workflow, settings.comfyui_latent_node_id)
    if latent_node is not None:
        inputs = latent_node.setdefault("inputs", {})
        inputs["width"] = width
        inputs["height"] = height
        latent_patched = True

    image_node = _node(workflow, settings.comfyui_image_node_id)
    if image_node is not None and comfyui_image_name is not None:
        image_node.setdefault("inputs", {})["image"] = comfyui_image_name
        image_patched = True

    save_node = _node(workflow, settings.comfyui_save_node_id)
    if save_node is not None:
        save_node.setdefault("inputs", {})["filename_prefix"] = f"ppe_ai_{task_id}"
        save_patched = True

    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type", ""))
        inputs = node.setdefault("inputs", {})

        if not positive_patched and class_type == "CLIPTextEncode" and "text" in inputs:
            inputs["text"] = prompt
            positive_patched = True
            continue

        if positive_patched and not negative_patched and class_type == "CLIPTextEncode" and "text" in inputs:
            inputs["text"] = negative_prompt_text
            negative_patched = True
            continue

        if not latent_patched and generation_mode == "text_to_image" and class_type in {"EmptyLatentImage", "EmptySD3LatentImage"}:
            if "width" in inputs:
                inputs["width"] = width
            if "height" in inputs:
                inputs["height"] = height
            latent_patched = True

        if not image_patched and generation_mode == "image_to_image" and class_type == "LoadImage" and "image" in inputs:
            inputs["image"] = comfyui_image_name
            image_patched = True

        if not denoise_patched and generation_mode == "image_to_image" and class_type == "KSampler" and "denoise" in inputs:
            inputs["denoise"] = settings.comfyui_denoise
            denoise_patched = True

        if not save_patched and class_type == "SaveImage":
            inputs["filename_prefix"] = f"ppe_ai_{task_id}"
            save_patched = True

        if "seed" in inputs and isinstance(inputs["seed"], int):
            inputs["seed"] = random.randint(1, 2**31 - 1)

    if not positive_patched:
        raise ComfyUIError("没有找到可写入 Prompt 的节点。请设置 COMFYUI_POSITIVE_NODE_ID 或检查工作流 JSON。")
    if generation_mode == "image_to_image" and not image_patched:
        raise ComfyUIError("没有找到可写入输入图片的 LoadImage 节点。请设置 COMFYUI_IMAGE_NODE_ID 或检查工作流 JSON。")
    return workflow


def _extract_first_image(history_item: dict[str, Any]) -> dict[str, str] | None:
    outputs = history_item.get("outputs", {})
    for node_output in outputs.values():
        for image in node_output.get("images", []):
            filename = image.get("filename")
            if filename:
                return {
                    "filename": filename,
                    "subfolder": image.get("subfolder", ""),
                    "type": image.get("type", "output"),
                }
    return None


async def _upload_input_image(client: httpx.AsyncClient, image_path: Path, task_id: str) -> str:
    if not image_path.exists() or not image_path.is_file():
        raise ComfyUIError(f"img2img 输入图片不存在：{image_path}")
    suffix = image_path.suffix.lower() or ".png"
    upload_name = f"ppe_ai_{task_id}_input{suffix}"
    with image_path.open("rb") as file_obj:
        files = {"image": (upload_name, file_obj, "application/octet-stream")}
        data = {"type": "input", "overwrite": "true"}
        response = await client.post("/upload/image", files=files, data=data)
    response.raise_for_status()
    payload = response.json()
    name = payload.get("name") or upload_name
    subfolder = payload.get("subfolder")
    if subfolder:
        return f"{subfolder}/{name}"
    return name


async def _wait_for_image(client: httpx.AsyncClient, prompt_id: str) -> tuple[dict[str, Any], dict[str, str]]:
    for _ in range(settings.comfyui_poll_attempts):
        response = await client.get(f"/history/{prompt_id}")
        response.raise_for_status()
        history = response.json()
        history_item = history.get(prompt_id)
        if history_item:
            status = history_item.get("status", {})
            if status.get("status_str") == "error":
                raise ComfyUIError(f"ComfyUI 工作流执行失败：{status}")
            image = _extract_first_image(history_item)
            if image:
                return history_item, image
        await asyncio.sleep(settings.comfyui_poll_interval_seconds)
    raise ComfyUIError("等待 ComfyUI 生成结果超时。")


async def generate_comfyui_image(
    task_id: str,
    prompt: str,
    size: str,
    output_format: str = "png",
    product_image_path: Path | None = None,
    generation_mode: str | None = None,
) -> tuple[Path, Path]:
    ensure_storage_dirs()
    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    requested_generation_mode = generation_mode or ("image_to_image" if product_image_path is not None else "text_to_image")
    workflow_generation_mode = "image_to_image" if product_image_path is not None else "text_to_image"
    workflow_path = (
        settings.comfyui_image_to_image_workflow_path
        if workflow_generation_mode == "image_to_image"
        else settings.comfyui_text_to_image_workflow_path
    )
    negative_prompt = (
        "deformed PPE, extra PPE, floating product, wrong body position, distorted face, extra limbs, "
        "duplicate helmet, text, watermark, collage, low quality, unnatural pose"
        if requested_generation_mode == "human_wearing"
        else settings.comfyui_default_negative_prompt
    )
    timeout = httpx.Timeout(settings.comfyui_timeout_seconds)
    comfyui_image_name: str | None = None
    async with httpx.AsyncClient(base_url=settings.comfyui_base_url, timeout=timeout) as client:
        if product_image_path is not None:
            comfyui_image_name = await _upload_input_image(client, product_image_path, task_id)
        workflow = _patch_workflow(
            _load_workflow(workflow_path),
            task_id,
            prompt,
            size,
            workflow_generation_mode,
            comfyui_image_name,
            negative_prompt=negative_prompt,
        )
        queue_response = await client.post("/prompt", json={"prompt": workflow, "client_id": task_id})
        queue_response.raise_for_status()
        prompt_id = queue_response.json().get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"ComfyUI 未返回 prompt_id：{queue_response.text}")

        history_item, image_info = await _wait_for_image(client, prompt_id)
        image_response = await client.get("/view", params=image_info)
        image_response.raise_for_status()

    source_name = image_info["filename"]
    ext = Path(source_name).suffix.lower().lstrip(".") or output_format.lower().lstrip(".") or "png"
    image_path = output_dir / f"result.{ext}"
    metadata_path = output_dir / "metadata.json"
    image_path.write_bytes(image_response.content)

    metadata = {
        "task_id": task_id,
        "engine": "comfyui",
        "generation_mode": requested_generation_mode,
        "human_wearing_used": requested_generation_mode == "human_wearing",
        "product_image_used": product_image_path is not None,
        "product_image_local_path": str(product_image_path) if product_image_path is not None else None,
        "comfyui_input_image": comfyui_image_name,
        "comfyui_base_url": settings.comfyui_base_url,
        "workflow_path": str(workflow_path),
        "denoise": settings.comfyui_denoise if workflow_generation_mode == "image_to_image" else None,
        "prompt_id": prompt_id,
        "prompt": prompt,
        "size": size,
        "source_image": image_info,
        "history_status": history_item.get("status", {}),
        "output_path": str(image_path),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return image_path, metadata_path
