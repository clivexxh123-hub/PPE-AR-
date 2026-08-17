"""Deterministic PPE foreground composition for scene_generation."""

from __future__ import annotations

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


def render_scene_marketing_image(
    task_id: str,
    background_path: Path,
    ppe_path: Path,
    size: str = "512x512",
    product_width_ratio: float = 0.55,
    position_x_ratio: float = 0.5,
    position_y_ratio: float = 0.58,
) -> tuple[Path, Path]:
    """Composite a transparent PPE product over a generated marketing background."""
    ensure_storage_dirs()
    if not background_path.exists() or not ppe_path.exists():
        raise ValueError("scene_generation background or PPE foreground file does not exist.")
    if not 0 < product_width_ratio <= 1:
        raise ValueError("scene_generation product_width_ratio must be between 0 and 1.")
    if not 0 <= position_x_ratio <= 1 or not 0 <= position_y_ratio <= 1:
        raise ValueError("scene_generation position ratios must be between 0 and 1.")

    try:
        with Image.open(background_path) as source:
            background = _cover_resize(source.convert("RGBA"), _parse_size(size))
        with Image.open(ppe_path) as source:
            product = source.convert("RGBA")
    except OSError as exc:
        raise ValueError(f"scene_generation image could not be read: {exc}") from exc

    bounds = product.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("scene_generation PPE foreground is fully transparent.")
    product = product.crop(bounds)
    target_width = max(1, min(background.width, round(background.width * product_width_ratio)))
    target_height = max(1, round(product.height * target_width / product.width))
    product = product.resize((target_width, target_height), Image.Resampling.LANCZOS)
    x = round((background.width - product.width) * position_x_ratio)
    y = round((background.height - product.height) * position_y_ratio)
    background.alpha_composite(product, (x, y))

    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / "result.png"
    metadata_path = output_dir / "metadata.json"
    background.convert("RGB").save(image_path, format="PNG")
    metadata_path.write_text(
        json.dumps(
            {
                "engine": "pillow-scene-foreground-composite",
                "scene_generation_strategy": "generated_background_composite",
                "background_generated": True,
                "product_composited": True,
                "background_path": str(background_path),
                "ppe_foreground_path": str(ppe_path),
                "output_path": str(image_path),
                "width": background.width,
                "height": background.height,
                "product_width_ratio": product_width_ratio,
                "position_x_ratio": position_x_ratio,
                "position_y_ratio": position_y_ratio,
                "product_width": product.width,
                "product_height": product.height,
                "product_x": x,
                "product_y": y,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return image_path, metadata_path
