from pathlib import Path

import json
from PIL import Image

from app.core.config import ensure_storage_dirs, settings

def render_printed_design(
    task_id: str,
    base_path: Path | None,
    logo_path: Path | None,
    position_x_ratio: float = 0.5,
    position_y_ratio: float = 0.5,
    logo_width_ratio: float = 0.25,
    opacity: float = 1.0,
) -> tuple[Path, Path]:
    """Compose an RGBA logo onto a product image using relative coordinates."""
    ensure_storage_dirs()
    if base_path is None or not base_path.exists():
        raise ValueError(f"Base image does not exist: {base_path}")
    if logo_path is None or not logo_path.exists():
        raise ValueError(f"Logo image does not exist: {logo_path}")
    for name, value in (
        ("position_x_ratio", position_x_ratio),
        ("position_y_ratio", position_y_ratio),
        ("logo_width_ratio", logo_width_ratio),
        ("opacity", opacity),
    ):
        if not 0 <= float(value) <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
    if float(logo_width_ratio) <= 0:
        raise ValueError("logo_width_ratio must be greater than 0")

    try:
        with Image.open(base_path) as source:
            base = source.convert("RGBA")
        with Image.open(logo_path) as source:
            logo = source.convert("RGBA")
    except OSError as exc:
        raise ValueError(f"Unable to read image input: {exc}") from exc

    target_width = max(1, min(base.width, round(base.width * float(logo_width_ratio))))
    target_height = max(1, round(logo.height * target_width / logo.width))
    logo = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)
    if float(opacity) < 1:
        alpha = logo.getchannel("A").point(lambda value: round(value * float(opacity)))
        logo.putalpha(alpha)

    x = round((base.width - logo.width) * float(position_x_ratio))
    y = round((base.height - logo.height) * float(position_y_ratio))
    base.alpha_composite(logo, (x, y))

    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / "printed_design.png"
    metadata_path = output_dir / "metadata.json"
    base.save(image_path, format="PNG")
    metadata = {
        "engine": "pillow-alpha-composite",
        "validation_status": "passed",
        "base_image": str(base_path),
        "logo_image": str(logo_path),
        "output_path": str(image_path),
        "width": base.width,
        "height": base.height,
        "has_alpha": True,
        "position_x_ratio": float(position_x_ratio),
        "position_y_ratio": float(position_y_ratio),
        "logo_width_ratio": float(logo_width_ratio),
        "opacity": float(opacity),
        "position_x": x,
        "position_y": y,
        "logo_width": logo.width,
        "logo_height": logo.height,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return image_path, metadata_path

def normalize_logo(task_id: str, logo_path: Path | None, output_format: str = "png") -> tuple[Path, Path]:
    ensure_storage_dirs()
    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    ext = output_format.lower().lstrip(".") or "png"
    image_path = output_dir / f"logo_normalized.{ext}"
    metadata_path = output_dir / "metadata.json"

    if logo_path and logo_path.exists():
        image = Image.open(logo_path).convert("RGBA")
    else:
        image = Image.new("RGBA", (512, 512), (255, 255, 255, 0))

    image.thumbnail((512, 512))
    canvas = Image.new("RGBA", (512, 512), (255, 255, 255, 0))
    canvas.alpha_composite(image, ((512 - image.width) // 2, (512 - image.height) // 2))
    canvas.save(image_path)
    metadata_path.write_text(
        '{\n  "engine": "logo-placeholder",\n  "note": "当前还没有接入真实 Logo 抠图模型。"\n}\n',
        encoding="utf-8",
    )
    return image_path, metadata_path

