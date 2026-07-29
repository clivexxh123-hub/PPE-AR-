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


def _load_workflow() -> dict[str, Any]:
    workflow_path = settings.comfyui_workflow_path
    if not workflow_path.is_absolute():
        workflow_path = settings.base_dir / workflow_path
    if not workflow_path.exists():
        raise ComfyUIError(f"ComfyUI 工作流文件不存在：{workflow_path}")
    return json.loads(workflow_path.read_text(encoding="utf-8-sig"))


def _node(workflow: dict[str, Any], node_id: str | None) -> dict[str, Any] | None:
    if not node_id:
        return None
    value = workflow.get(str(node_id))
    return value if isinstance(value, dict) else None


def _patch_workflow(workflow: dict[str, Any], task_id: str, prompt: str, size: str) -> dict[str, Any]:
    width, height = _parse_size(size)
    positive_patched = False
    negative_patched = False
    latent_patched = False
    save_patched = False

    positive_node = _node(workflow, settings.comfyui_positive_node_id)
    if positive_node is not None:
        positive_node.setdefault("inputs", {})["text"] = prompt
        positive_patched = True

    negative_node = _node(workflow, settings.comfyui_negative_node_id)
    if negative_node is not None:
        negative_node.setdefault("inputs", {})["text"] = settings.comfyui_default_negative_prompt
        negative_patched = True

    latent_node = _node(workflow, settings.comfyui_latent_node_id)
    if latent_node is not None:
        inputs = latent_node.setdefault("inputs", {})
        inputs["width"] = width
        inputs["height"] = height
        latent_patched = True

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
            inputs["text"] = settings.comfyui_default_negative_prompt
            negative_patched = True
            continue

        if not latent_patched and class_type in {"EmptyLatentImage", "EmptySD3LatentImage"}:
            if "width" in inputs:
                inputs["width"] = width
            if "height" in inputs:
                inputs["height"] = height
            latent_patched = True

        if not save_patched and class_type == "SaveImage":
            inputs["filename_prefix"] = f"ppe_ai_{task_id}"
            save_patched = True

        if "seed" in inputs and isinstance(inputs["seed"], int):
            inputs["seed"] = random.randint(1, 2**31 - 1)

    if not positive_patched:
        raise ComfyUIError("没有找到可写入 Prompt 的节点。请设置 COMFYUI_POSITIVE_NODE_ID 或检查工作流 JSON。")
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


async def generate_comfyui_image(task_id: str, prompt: str, size: str, output_format: str = "png") -> tuple[Path, Path]:
    ensure_storage_dirs()
    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    workflow = _patch_workflow(_load_workflow(), task_id, prompt, size)
    timeout = httpx.Timeout(settings.comfyui_timeout_seconds)
    async with httpx.AsyncClient(base_url=settings.comfyui_base_url, timeout=timeout) as client:
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
        "comfyui_base_url": settings.comfyui_base_url,
        "workflow_path": str(settings.comfyui_workflow_path),
        "prompt_id": prompt_id,
        "prompt": prompt,
        "size": size,
        "source_image": image_info,
        "history_status": history_item.get("status", {}),
        "output_path": str(image_path),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return image_path, metadata_path
