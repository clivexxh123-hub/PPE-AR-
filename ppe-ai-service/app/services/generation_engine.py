from pathlib import Path

from app.core.config import settings
from app.services.comfyui_engine import generate_comfyui_image
from app.services.mock_engine import generate_mock_image


async def generate_ai_image(
    task_id: str,
    prompt: str,
    size: str,
    output_format: str = "png",
    product_image_path: Path | None = None,
    mask_image_path: Path | None = None,
    generation_mode: str | None = None,
    denoise: float | None = None,
) -> tuple[Path, Path, str]:
    """根据配置选择 AI 生成引擎。默认 mock，配置为 comfyui 时调用 ComfyUI。"""
    engine = settings.ai_engine.lower()
    if engine == "comfyui":
        image_path, metadata_path = await generate_comfyui_image(
            task_id,
            prompt,
            size,
            output_format,
            product_image_path=product_image_path,
            mask_image_path=mask_image_path,
            generation_mode=generation_mode,
            denoise=denoise,
        )
        return image_path, metadata_path, "comfyui"
    image_path, metadata_path = generate_mock_image(task_id, prompt, size, output_format)
    return image_path, metadata_path, "mock"
