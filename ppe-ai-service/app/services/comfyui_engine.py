import asyncio
import json
import random
import tempfile
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageChops, UnidentifiedImageError

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


def prepare_img2img_input(
    image_path: Path,
    size: str,
    destination: Path,
) -> dict[str, int | str]:
    """Fit an img2img input into the requested canvas without stretching it."""
    if not image_path.exists() or not image_path.is_file():
        raise ComfyUIError(f"Input image does not exist: {image_path}")

    target_width, target_height = _parse_size(size)
    try:
        with Image.open(image_path) as source:
            source.load()
            original_width, original_height = source.size
            source_rgba = source.convert("RGBA")
    except (OSError, UnidentifiedImageError) as exc:
        raise ComfyUIError(f"Unable to read input image: {image_path}") from exc

    scale = min(target_width / original_width, target_height / original_height)
    content_width = max(1, round(original_width * scale))
    content_height = max(1, round(original_height * scale))
    resized = source_rgba.resize(
        (content_width, content_height),
        Image.Resampling.LANCZOS,
    )

    canvas = Image.new("RGBA", (target_width, target_height), (255, 255, 255, 255))
    offset_x = (target_width - content_width) // 2
    offset_y = (target_height - content_height) // 2
    canvas.alpha_composite(resized, dest=(offset_x, offset_y))

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(destination, format="PNG")
    return {
        "method": "contain_center_pad",
        "original_width": original_width,
        "original_height": original_height,
        "processed_width": target_width,
        "processed_height": target_height,
        "content_width": content_width,
        "content_height": content_height,
    }


def prepare_mask_input(
    mask_path: Path,
    size: str,
    destination: Path,
) -> dict[str, int | str]:
    """Apply the same contain transform as the guide image to a repaint mask."""
    if not mask_path.exists() or not mask_path.is_file():
        raise ComfyUIError(f"Repaint mask does not exist: {mask_path}")
    target_width, target_height = _parse_size(size)
    try:
        with Image.open(mask_path) as source:
            source.load()
            original_width, original_height = source.size
            source_mask = source.convert("L")
    except (OSError, UnidentifiedImageError) as exc:
        raise ComfyUIError(f"Unable to read repaint mask: {mask_path}") from exc

    scale = min(target_width / original_width, target_height / original_height)
    content_width = max(1, round(original_width * scale))
    content_height = max(1, round(original_height * scale))
    resized = source_mask.resize((content_width, content_height), Image.Resampling.LANCZOS)
    canvas = Image.new("L", (target_width, target_height), 0)
    offset_x = (target_width - content_width) // 2
    offset_y = (target_height - content_height) // 2
    canvas.paste(resized, (offset_x, offset_y))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, format="PNG")
    return {
        "method": "contain_center_pad_mask",
        "original_width": original_width,
        "original_height": original_height,
        "processed_width": target_width,
        "processed_height": target_height,
        "content_width": content_width,
        "content_height": content_height,
    }


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
    comfyui_mask_name: str | None = None,
    negative_prompt: str | None = None,
    denoise: float | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    width, height = _parse_size(size)
    positive_patched = False
    negative_patched = False
    latent_patched = False
    save_patched = False
    image_patched = comfyui_image_name is None
    mask_patched = comfyui_mask_name is None
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

    mask_node = _node(workflow, settings.comfyui_mask_node_id)
    if mask_node is not None and comfyui_mask_name is not None:
        mask_node.setdefault("inputs", {})["image"] = comfyui_mask_name
        mask_patched = True

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

        elif not mask_patched and generation_mode == "image_to_image" and class_type == "LoadImage" and "image" in inputs:
            inputs["image"] = comfyui_mask_name
            mask_patched = True

        if not denoise_patched and generation_mode == "image_to_image" and class_type == "KSampler" and "denoise" in inputs:
            inputs["denoise"] = settings.comfyui_denoise if denoise is None else denoise
            denoise_patched = True

        if not save_patched and class_type == "SaveImage":
            inputs["filename_prefix"] = f"ppe_ai_{task_id}"
            save_patched = True

        if "seed" in inputs and isinstance(inputs["seed"], int):
            inputs["seed"] = random.randint(1, 2**31 - 1) if seed is None else int(seed)

    if not positive_patched:
        raise ComfyUIError("没有找到可写入 Prompt 的节点。请设置 COMFYUI_POSITIVE_NODE_ID 或检查工作流 JSON。")
    if generation_mode == "image_to_image" and not image_patched:
        raise ComfyUIError("没有找到可写入输入图片的 LoadImage 节点。请设置 COMFYUI_IMAGE_NODE_ID 或检查工作流 JSON。")
    if comfyui_mask_name is not None and not mask_patched:
        raise ComfyUIError("没有找到可写入局部重绘蒙版的 LoadImage 节点。请设置 COMFYUI_MASK_NODE_ID 或检查工作流 JSON。")
    return workflow


def _workflow_seed(workflow: dict[str, Any]) -> int | None:
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        value = node.get("inputs", {}).get("seed")
        if isinstance(value, int):
            return value
    return None


def _lock_human_wearing_unmasked_regions(
    generated_path: Path,
    input_path: Path,
    mask_path: Path,
) -> dict[str, Any]:
    """Make the contact-only mask a real output invariant, not just metadata."""
    with Image.open(generated_path) as source:
        generated = source.convert("RGB")
    with Image.open(input_path) as source:
        original = source.convert("RGB")
    with Image.open(mask_path) as source:
        mask = source.convert("L")
    if original.size != generated.size or mask.size != generated.size:
        raise ComfyUIError("human_wearing input, mask, and output dimensions must match for core lock.")
    # White mask pixels are the only pixels ComfyUI is permitted to alter.
    # This preserves the P10 shell, printed design, face, shirt and background
    # outside the explicit contact band even if a workflow node is miswired.
    locked = Image.composite(generated, original, mask)
    locked.save(generated_path, format="PNG")
    # A hard-zero mask pixel is contractually immutable after the post-composite.
    # Record the measured result so downstream metadata cannot claim protection
    # without evidence from the actual final output.
    unchanged_mask = mask.point(lambda value: 255 if value == 0 else 0)
    unmasked_delta = ImageChops.multiply(
        ImageChops.difference(locked, original).convert("L"),
        unchanged_mask,
    )
    unmasked_mismatch_pixels = sum(unmasked_delta.histogram()[1:])
    coverage = sum(mask.histogram()[128:]) / float(mask.width * mask.height)
    return {
        "applied": True,
        "method": "post_composite_unmasked_input_lock",
        "mask_coverage_ratio": round(coverage, 4),
        "unmasked_mismatch_pixels": unmasked_mismatch_pixels,
        "protected_regions": ["helmet_core", "eyes_face", "shirt", "body_outline", "background"],
    }


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


async def _upload_input_image(
    client: httpx.AsyncClient,
    image_path: Path,
    task_id: str,
    role: str = "input",
) -> str:
    if not image_path.exists() or not image_path.is_file():
        raise ComfyUIError(f"img2img 输入图片不存在：{image_path}")
    suffix = image_path.suffix.lower() or ".png"
    upload_name = f"ppe_ai_{task_id}_{role}{suffix}"
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
    mask_image_path: Path | None = None,
    generation_mode: str | None = None,
    denoise: float | None = None,
    seed: int | None = None,
) -> tuple[Path, Path]:
    ensure_storage_dirs()
    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    requested_generation_mode = generation_mode or ("image_to_image" if product_image_path is not None else "text_to_image")
    workflow_generation_mode = "image_to_image" if product_image_path is not None else "text_to_image"
    generation_denoise = resolve_generation_denoise(
        requested_generation_mode,
        workflow_generation_mode,
        denoise,
    )
    workflow_path = (
        settings.comfyui_human_wearing_workflow_path
        if requested_generation_mode == "human_wearing" and mask_image_path is not None
        else settings.comfyui_image_to_image_workflow_path
        if workflow_generation_mode == "image_to_image"
        else settings.comfyui_text_to_image_workflow_path
    )
    negative_prompt = (
        "flat sticker, pasted-on product, floating PPE, rigid cardboard clothing, duplicate vest, duplicate helmet, "
        "duplicate gloves, duplicate shoes, old PPE visible, green underlayer, fluorescent lime old vest, "
        "second vest inside neckline, wrong body position, broken neckline, sealed armholes, deformed PPE, extra PPE, "
        "distorted product structure, distorted face, changed identity, extra limbs, extra fingers, extra hands, "
        "extra feet, text, watermark, collage, low quality, unnatural pose"
        if requested_generation_mode == "human_wearing"
        else "deformed product, distorted product, extra products, duplicate products, multiple panels, collage, "
        "text, typography, labels, watermark, logo, people, low quality, messy background"
        if requested_generation_mode == "scene_generation"
        else settings.comfyui_default_negative_prompt
    )
    timeout = httpx.Timeout(settings.comfyui_timeout_seconds)
    comfyui_image_name: str | None = None
    comfyui_mask_name: str | None = None
    input_preprocessing: dict[str, int | str] | None = None
    mask_preprocessing: dict[str, int | str] | None = None
    masked_refinement: dict[str, Any] | None = None
    effective_seed: int | None = None
    with tempfile.TemporaryDirectory(prefix=f"ppe-img2img-{task_id}-") as temp_dir:
        prepared_image_path: Path | None = None
        prepared_mask_path: Path | None = None
        if product_image_path is not None:
            prepared_image_path = Path(temp_dir) / "img2img_input.png"
            input_preprocessing = prepare_img2img_input(product_image_path, size, prepared_image_path)
        if mask_image_path is not None:
            if product_image_path is None:
                raise ComfyUIError("局部重绘蒙版必须与 img2img 输入图片一起使用。")
            prepared_mask_path = Path(temp_dir) / "img2img_mask.png"
            mask_preprocessing = prepare_mask_input(mask_image_path, size, prepared_mask_path)

        async with httpx.AsyncClient(base_url=settings.comfyui_base_url, timeout=timeout) as client:
            if prepared_image_path is not None:
                comfyui_image_name = await _upload_input_image(client, prepared_image_path, task_id, "input")
            if prepared_mask_path is not None:
                comfyui_mask_name = await _upload_input_image(client, prepared_mask_path, task_id, "mask")
            workflow = _patch_workflow(
                _load_workflow(workflow_path),
                task_id,
                prompt,
                size,
                workflow_generation_mode,
                comfyui_image_name,
                comfyui_mask_name,
                negative_prompt=negative_prompt,
                denoise=generation_denoise,
                seed=seed,
            )
            effective_seed = _workflow_seed(workflow)
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
    if (
        requested_generation_mode == "human_wearing"
        and product_image_path is not None
        and mask_image_path is not None
    ):
        masked_refinement = _lock_human_wearing_unmasked_regions(
            image_path,
            product_image_path,
            mask_image_path,
        )

    metadata = {
        "task_id": task_id,
        "engine": "comfyui",
        "generation_mode": requested_generation_mode,
        "human_wearing_used": requested_generation_mode == "human_wearing",
        "scene_generation_used": requested_generation_mode == "scene_generation",
        "product_image_used": product_image_path is not None,
        "product_image_local_path": str(product_image_path) if product_image_path is not None else None,
        "mask_image_used": mask_image_path is not None,
        "mask_image_local_path": str(mask_image_path) if mask_image_path is not None else None,
        "input_preprocessing": input_preprocessing,
        "mask_preprocessing": mask_preprocessing,
        "comfyui_input_image": comfyui_image_name,
        "comfyui_mask_image": comfyui_mask_name,
        "comfyui_base_url": settings.comfyui_base_url,
        "workflow_path": str(workflow_path),
        "denoise": generation_denoise if workflow_generation_mode == "image_to_image" else None,
        "seed": effective_seed,
        "masked_refinement": masked_refinement,
        "prompt_id": prompt_id,
        "prompt": prompt,
        "size": size,
        "source_image": image_info,
        "history_status": history_item.get("status", {}),
        "output_path": str(image_path),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return image_path, metadata_path


def resolve_generation_denoise(
    requested_generation_mode: str,
    workflow_generation_mode: str,
    requested_denoise: float | None = None,
) -> float | None:
    """Return the effective img2img denoise without inventing a value for text-to-image."""
    if workflow_generation_mode != "image_to_image":
        return None
    if requested_denoise is not None:
        value = float(requested_denoise)
        if not 0 <= value <= 1:
            raise ValueError("denoise 必须在 0 到 1 之间。")
        return value
    if requested_generation_mode == "human_wearing":
        return settings.comfyui_human_wearing_blend_denoise
    if requested_generation_mode == "scene_generation":
        return settings.comfyui_scene_generation_denoise
    return settings.comfyui_denoise
