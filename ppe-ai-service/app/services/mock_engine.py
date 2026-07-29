import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.config import ensure_storage_dirs, settings


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _parse_size(size: str) -> tuple[int, int]:
    try:
        width_text, height_text = size.lower().split("x", maxsplit=1)
        width = max(256, min(2048, int(width_text)))
        height = max(256, min(2048, int(height_text)))
        return width, height
    except (ValueError, AttributeError):
        return 1024, 1024


def generate_mock_image(task_id: str, prompt: str, size: str, output_format: str = "png") -> tuple[Path, Path]:
    ensure_storage_dirs()
    width, height = _parse_size(size)
    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    ext = output_format.lower().lstrip(".") or "png"
    image_path = output_dir / f"result.{ext}"
    metadata_path = output_dir / "metadata.json"

    image = Image.new("RGB", (width, height), color=(238, 242, 246))
    draw = ImageDraw.Draw(image)
    title_font = _font(max(24, width // 28))
    body_font = _font(max(14, width // 54))

    draw.rectangle((0, 0, width, int(height * 0.16)), fill=(21, 35, 49))
    draw.text((width * 0.06, height * 0.055), "PPE AI 模拟生成结果", fill=(255, 255, 255), font=title_font)
    draw.rounded_rectangle(
        (width * 0.08, height * 0.25, width * 0.92, height * 0.72),
        radius=24,
        fill=(255, 255, 255),
        outline=(196, 204, 214),
        width=3,
    )
    draw.text((width * 0.12, height * 0.33), "当前是模拟图片占位", fill=(21, 35, 49), font=title_font)
    draw.text((width * 0.12, height * 0.43), "后续会把 mock_engine 替换为 ComfyUI / Flux。", fill=(86, 99, 112), font=body_font)
    draw.text((width * 0.12, height * 0.52), prompt[:180], fill=(60, 70, 82), font=body_font)
    draw.text((width * 0.08, height * 0.82), f"task_id: {task_id}", fill=(60, 70, 82), font=body_font)

    image.save(image_path)
    metadata = {
        "task_id": task_id,
        "engine": "mock",
        "prompt": prompt,
        "size": f"{width}x{height}",
        "output_path": str(image_path),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return image_path, metadata_path

