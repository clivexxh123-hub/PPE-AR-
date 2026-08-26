import json
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from app.core.config import ensure_storage_dirs, settings
from app.services.human_anchor_service import resolve_anchor


_DEFAULT_PLACEMENT_PROFILE = {
    "position_x_ratio": 0.5,
    "position_y_ratio": 0.0,
    "ppe_width_ratio": 0.30,
    "human_top_padding_ratio": 0.0,
    "opacity": 1.0,
}
_CATEGORY_PLACEMENT_PROFILES = (
    # Helmet source images commonly have a much tighter alpha foreground than
    # their source canvas.  Reserve headroom in a full-body reference and put
    # the smaller, visible helmet over the crown rather than at image origin.
    ("helmet", ("安全帽", "头盔", "helmet", "hard hat"), {"position_x_ratio": 0.5, "position_y_ratio": 0.10, "ppe_width_ratio": 0.22, "human_top_padding_ratio": 0.12}),
    ("vest", ("马甲", "背心", "vest", "waistcoat"), {"position_x_ratio": 0.5, "position_y_ratio": 0.28, "ppe_width_ratio": 0.50}),
    ("goggles", ("护目镜", "goggle", "eyewear", "safety glasses"), {"position_x_ratio": 0.5, "position_y_ratio": 0.31, "ppe_width_ratio": 0.30}),
    ("gloves", ("手套", "glove"), {"position_x_ratio": 0.5, "position_y_ratio": 0.57, "ppe_width_ratio": 0.36}),
    ("boots", ("靴子", "安全鞋", "boot", "safety shoe"), {"position_x_ratio": 0.5, "position_y_ratio": 0.80, "ppe_width_ratio": 0.40}),
)
_BODY_ANCHORED_CATEGORIES = frozenset({"helmet", "vest"})
_PPE_CATEGORY_ALIASES = {
    "helmet": "helmet",
    "头盔": "helmet",
    "安全帽": "helmet",
    "vest": "vest",
    "马甲": "vest",
    "背心": "vest",
    "gloves": "gloves",
    "glove": "gloves",
    "手套": "gloves",
    "boots": "boots",
    "boot": "boots",
    "靴子": "boots",
    "安全鞋": "boots",
}


def resolve_ppe_category(
    product_name: str,
    product_category: str,
    requested_category: str | None = None,
) -> str:
    """Resolve the local PPE category without coupling it to fixture paths or a database."""
    if requested_category is not None and requested_category.strip():
        normalized = requested_category.strip().lower()
        resolved = _PPE_CATEGORY_ALIASES.get(normalized)
        if resolved is None:
            supported = ", ".join(("helmet", "vest", "gloves", "boots"))
            raise ValueError(f"ppe_category 仅支持：{supported}。")
        return resolved

    source = f"{product_name} {product_category}".lower()
    for candidate_name, keywords, _ in _CATEGORY_PLACEMENT_PROFILES:
        if any(keyword in source for keyword in keywords):
            return candidate_name
    return "unknown"


def resolve_human_wearing_placement(
    product_name: str,
    product_category: str,
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve small category defaults while preserving explicit task overrides."""
    source = f"{product_name} {product_category}".lower()
    ppe_category = resolve_ppe_category(
        product_name,
        product_category,
        str(parameters["ppe_category"]) if parameters.get("ppe_category") is not None else None,
    )
    profile_name = ppe_category if ppe_category != "unknown" else "default"
    resolved: dict[str, float] = dict(_DEFAULT_PLACEMENT_PROFILE)
    for candidate_name, keywords, profile in _CATEGORY_PLACEMENT_PROFILES:
        if candidate_name == ppe_category or (ppe_category == "unknown" and any(keyword in source for keyword in keywords)):
            profile_name = candidate_name
            resolved.update(profile)
            break

    manual_overrides: list[str] = []
    for field in ("position_x_ratio", "position_y_ratio", "opacity"):
        if parameters.get(field) is not None:
            resolved[field] = float(parameters[field])
            manual_overrides.append(field)
    if parameters.get("ppe_width_ratio") is not None:
        resolved["ppe_width_ratio"] = float(parameters["ppe_width_ratio"])
        manual_overrides.append("ppe_width_ratio")
    elif parameters.get("logo_width_ratio") is not None:
        resolved["ppe_width_ratio"] = float(parameters["logo_width_ratio"])
        manual_overrides.append("logo_width_ratio")

    return {
        **resolved,
        "ppe_category": ppe_category,
        "placement_profile": profile_name,
        "manual_override_fields": manual_overrides,
    }


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


def _contain_resize_with_top_padding(
    image: Image.Image,
    size: tuple[int, int],
    top_padding_ratio: float,
) -> Image.Image:
    """Preserve the wearer's full figure and reserve deterministic headroom.

    ``_cover_resize`` centre-crops, which silently removes the head of any
    portrait reference taller than the target canvas.  Every body-anchored
    category has to keep the head, so those categories always come through
    here even when no extra headroom is requested.
    """
    target_width, target_height = size
    available_height = max(1, round(target_height * (1 - top_padding_ratio)))
    scale = min(target_width / image.width, available_height / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    background = image.getpixel((0, 0))
    canvas = Image.new("RGBA", size, background)
    x = (target_width - resized.width) // 2
    y = target_height - resized.height
    canvas.alpha_composite(resized, (x, y))
    return canvas


def render_human_wearing_design(
    task_id: str,
    human_path: Path,
    ppe_path: Path,
    size: str = "512x512",
    position_x_ratio: float = 0.5,
    position_y_ratio: float = 0.0,
    ppe_width_ratio: float = 0.30,
    human_top_padding_ratio: float = 0.0,
    opacity: float = 1.0,
    ppe_category: str | None = None,
) -> tuple[Path, Path]:
    """Create a normalized human/PPE composite for the existing img2img flow."""
    ensure_storage_dirs()
    if not human_path.exists() or not ppe_path.exists():
        raise ValueError("human_reference or ppe_reference file does not exist.")
    if not 0 <= position_x_ratio <= 1 or not 0 <= position_y_ratio <= 1:
        raise ValueError("human_wearing position ratios must be between 0 and 1.")
    if not 0 <= human_top_padding_ratio < 0.5:
        raise ValueError("human_wearing top padding ratio must be between 0 and 0.5.")
    if not 0 < ppe_width_ratio <= 1 or not 0 <= opacity <= 1:
        raise ValueError("human_wearing PPE ratio or opacity is invalid.")

    normalized_category = (ppe_category or "").strip().lower()
    body_anchored_category = normalized_category in _BODY_ANCHORED_CATEGORIES
    try:
        with Image.open(human_path) as source:
            source_human = source.convert("RGBA")
            human = (
                _contain_resize_with_top_padding(source_human, _parse_size(size), human_top_padding_ratio)
                if human_top_padding_ratio > 0 or body_anchored_category
                else _cover_resize(source_human, _parse_size(size))
            )
        with Image.open(ppe_path) as source:
            ppe = source.convert("RGBA")
    except OSError as exc:
        raise ValueError(f"human_wearing image could not be read: {exc}") from exc

    # PPE source exports commonly retain generous transparent canvas margins.
    # Width ratios describe the wearable product, not that unused canvas, so
    # normalize to the visible alpha foreground before applying the existing
    # category placement defaults.  This matches scene_generation behavior.
    foreground_bounds = ppe.getchannel("A").getbbox()
    if foreground_bounds is None:
        raise ValueError("human_wearing PPE foreground is fully transparent.")
    ppe = ppe.crop(foreground_bounds)

    # Prefer a measured body anchor.  A canvas ratio cannot know where the
    # wearer's head is, so the same profile puts a helmet over the face on one
    # reference and floating above the hair on the next.
    anchor = (
        resolve_anchor(human, normalized_category, ppe.height / ppe.width)
        if body_anchored_category
        else None
    )
    if anchor is not None:
        target_width = max(1, min(human.width, anchor["target_width"]))
        target_height = max(1, round(ppe.height * target_width / ppe.width))
        placement_strategy = "body_anchor"
        x = anchor["paste_x"]
        y = anchor["paste_y"]
    else:
        target_width = max(1, min(human.width, round(human.width * ppe_width_ratio)))
        target_height = max(1, round(ppe.height * target_width / ppe.width))
        placement_strategy = "canvas_ratio"
        x = y = None

    ppe = ppe.resize((target_width, target_height), Image.Resampling.LANCZOS)
    if opacity < 1:
        ppe.putalpha(ppe.getchannel("A").point(lambda value: round(value * opacity)))

    if x is None or y is None:
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
                "ppe_foreground_bounds": {
                    "left": foreground_bounds[0],
                    "top": foreground_bounds[1],
                    "right": foreground_bounds[2],
                    "bottom": foreground_bounds[3],
                },
                "output_path": str(image_path),
                "width": human.width,
                "height": human.height,
                "position_x_ratio": position_x_ratio,
                "position_y_ratio": position_y_ratio,
                "ppe_width_ratio": ppe_width_ratio,
                "human_top_padding_ratio": human_top_padding_ratio,
                "opacity": opacity,
                "ppe_category": normalized_category or None,
                "placement_strategy": placement_strategy,
                "paste_x": x,
                "paste_y": y,
                "ppe_rendered_width": ppe.width,
                "ppe_rendered_height": ppe.height,
                "body_anchor": anchor,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return image_path, metadata_path
