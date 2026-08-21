import json
from pathlib import Path

from PIL import Image

from app.core.config import ensure_storage_dirs, settings


def _parse_size(size: str) -> tuple[int, int]:
    try:
        width_text, height_text = size.lower().split("x", maxsplit=1)
        return max(256, min(2048, int(width_text))), max(256, min(2048, int(height_text)))
    except (AttributeError, ValueError):
        return 512, 512


def _cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_width, target_height = size
    scale = max(target_width / image.width, target_height / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - target_width) // 2)
    top = max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def render_human_wearing_design(
    task_id: str,
    human_path: Path,
    ppe_path: Path,
    size: str = "512x512",
    position_x_ratio: float = 0.5,
    position_y_ratio: float = 0.0,
    ppe_width_ratio: float = 0.30,
    opacity: float = 1.0,
) -> tuple[Path, Path]:
    """Create a normalized human/PPE composite for the existing img2img flow."""
    ensure_storage_dirs()
    if not human_path.exists() or not ppe_path.exists():
        raise ValueError("human_reference or ppe_reference file does not exist.")
    if not 0 <= position_x_ratio <= 1 or not 0 <= position_y_ratio <= 1:
        raise ValueError("human_wearing position ratios must be between 0 and 1.")
    if not 0 < ppe_width_ratio <= 1 or not 0 <= opacity <= 1:
        raise ValueError("human_wearing PPE ratio or opacity is invalid.")

    try:
        with Image.open(human_path) as source:
            human = _cover_resize(source.convert("RGBA"), _parse_size(size))
        with Image.open(ppe_path) as source:
            ppe = source.convert("RGBA")
    except OSError as exc:
        raise ValueError(f"human_wearing image could not be read: {exc}") from exc

    target_width = max(1, min(human.width, round(human.width * ppe_width_ratio)))
    target_height = max(1, round(ppe.height * target_width / ppe.width))
    ppe = ppe.resize((target_width, target_height), Image.Resampling.LANCZOS)
    if opacity < 1:
        ppe.putalpha(ppe.getchannel("A").point(lambda value: round(value * opacity)))

    x = round((human.width - ppe.width) * position_x_ratio)
    y = round((human.height - ppe.height) * position_y_ratio)
    human.alpha_composite(ppe, (x, y))

    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / "human_wearing_input.png"
    metadata_path = output_dir / "human_wearing_metadata.json"
    human.save(image_path, format="PNG")
    metadata_path.write_text(
        json.dumps(
            {
                "engine": "pillow-alpha-composite",
                "generation_mode": "human_wearing",
                "human_reference_path": str(human_path),
                "ppe_reference_path": str(ppe_path),
                "output_path": str(image_path),
                "width": human.width,
                "height": human.height,
                "position_x_ratio": position_x_ratio,
                "position_y_ratio": position_y_ratio,
                "ppe_width_ratio": ppe_width_ratio,
                "opacity": opacity,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return image_path, metadata_path
