import json
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from app.core.config import ensure_storage_dirs, settings
from app.services.human_anchor_service import (
    analyze_body_anchors,
    public_anchor_metadata,
    resolve_ppe_placements,
)
from app.services.ppe_blend_service import prepare_blend_inputs


_DEFAULT_PLACEMENT_PROFILE = {
    "position_x_ratio": 0.5,
    "position_y_ratio": 0.0,
    "ppe_width_ratio": 0.30,
    "opacity": 0.92,
}
_CATEGORY_PLACEMENT_PROFILES = (
    (
        "helmet",
        ("安全帽", "头盔", "helmet", "hard hat"),
        {"position_x_ratio": 0.5, "position_y_ratio": 0.08, "ppe_width_ratio": 0.24, "opacity": 1.0},
    ),
    (
        "reflective_vest",
        ("反光马甲", "反光背心", "安全马甲", "马甲", "背心", "reflective vest", "safety vest", "hi-vis", "high visibility"),
        {"position_x_ratio": 0.5, "position_y_ratio": 0.36, "ppe_width_ratio": 0.42, "opacity": 0.88},
    ),
    ("goggles", ("护目镜", "goggle", "eyewear", "safety glasses"), {"position_x_ratio": 0.5, "position_y_ratio": 0.31, "ppe_width_ratio": 0.30}),
    ("gloves", ("手套", "glove"), {"position_x_ratio": 0.5, "position_y_ratio": 0.57, "ppe_width_ratio": 0.36}),
    ("boots", ("安全鞋", "劳保鞋", "工作鞋", "靴子", "shoe", "boot", "footwear"), {"position_x_ratio": 0.5, "position_y_ratio": 0.80, "ppe_width_ratio": 0.28}),
)

_PROFILE_TO_CATEGORY = {
    "helmet": "helmet",
    "reflective_vest": "vest",
    "goggles": "goggles",
    "gloves": "gloves",
    "boots": "boots",
}


def resolve_human_wearing_placement(
    product_name: str,
    product_category: str,
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve PPE-aware defaults while preserving explicit task overrides."""
    source = f"{product_name} {product_category}".lower()
    profile_name = "default"
    resolved: dict[str, float] = dict(_DEFAULT_PLACEMENT_PROFILE)
    requested_category = str(parameters.get("ppe_category", "")).strip().lower()
    category_profile = {
        "helmet": "helmet",
        "vest": "reflective_vest",
        "goggles": "goggles",
        "gloves": "gloves",
        "boots": "boots",
    }.get(requested_category)
    for candidate_name, keywords, profile in _CATEGORY_PLACEMENT_PROFILES:
        if candidate_name == category_profile or (category_profile is None and any(keyword in source for keyword in keywords)):
            profile_name = candidate_name
            resolved.update(profile)
            break

    # A full figure occupies roughly half the width of a square canvas. Scale the
    # vest to the figure rather than reusing the half-body canvas ratio.
    if profile_name == "reflective_vest" and str(parameters.get("framing", "")).lower() == "full_body":
        resolved.update({"position_y_ratio": 0.27, "ppe_width_ratio": 0.22})

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
        "placement_profile": profile_name,
        "ppe_category": _PROFILE_TO_CATEGORY.get(profile_name, "unknown"),
        "manual_override_fields": manual_overrides,
    }


def _parse_size(size: str) -> tuple[int, int]:
    try:
        width_text, height_text = size.lower().split("x", maxsplit=1)
        return max(256, min(2048, int(width_text))), max(256, min(2048, int(height_text)))
    except (AttributeError, ValueError):
        return 512, 512


def _average_corner_color(image: Image.Image) -> tuple[int, int, int, int]:
    rgb = image.convert("RGB")
    points = ((0, 0), (rgb.width - 1, 0), (0, rgb.height - 1), (rgb.width - 1, rgb.height - 1))
    samples = [rgb.getpixel(point) for point in points]
    return tuple(sum(sample[channel] for sample in samples) // len(samples) for channel in range(3)) + (255,)


def _fit_human_frame(image: Image.Image, size: tuple[int, int], framing: str) -> Image.Image:
    """Preserve the full figure, or top-anchor a portrait for a real half-body crop."""
    target_width, target_height = size
    source = image.convert("RGBA")
    if framing == "full_body":
        scale = min(target_width / source.width, target_height / source.height)
        resized = source.resize(
            (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
            Image.Resampling.LANCZOS,
        )
        canvas = Image.new("RGBA", size, _average_corner_color(source))
        canvas.alpha_composite(
            resized,
            ((target_width - resized.width) // 2, (target_height - resized.height) // 2),
        )
        return canvas

    scale = max(target_width / source.width, target_height / source.height)
    resized = source.resize(
        (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - target_width) // 2)
    # Portrait model assets are usually already composed from head to feet. A
    # top-anchored crop keeps the head and torso; center crop used to cut them off.
    top = 0 if resized.height > target_height else max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def _trim_transparent_product(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    bounds = rgba.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("ppe_reference does not contain visible pixels.")
    left, top, right, bottom = bounds
    padding = max(2, round(max(right - left, bottom - top) * 0.01))
    return rgba.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(rgba.width, right + padding),
            min(rgba.height, bottom + padding),
        )
    )


def _split_paired_product(image: Image.Image) -> list[Image.Image]:
    """Split a side-by-side glove/shoe pair into one source per body side."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A").point(lambda value: 255 if value >= 24 else 0)
    width, height = rgba.size
    if width < 24 or height < 24:
        return [rgba]
    column_profile = alpha.resize((width, 1), Image.Resampling.BOX)
    search_left = max(1, round(width * 0.28))
    search_right = min(width - 1, round(width * 0.72))
    split_x = min(
        range(search_left, search_right),
        key=lambda x: column_profile.getpixel((x, 0)),
    )
    if column_profile.getpixel((split_x, 0)) > 40:
        return [rgba]

    parts: list[Image.Image] = []
    total_visible = max(1, sum(alpha.histogram()[128:]))
    for left, right in ((0, split_x), (split_x, width)):
        part_alpha = alpha.crop((left, 0, right, height))
        bounds = part_alpha.getbbox()
        visible = sum(part_alpha.histogram()[128:])
        if bounds is None or visible < total_visible * 0.18:
            return [rgba]
        parts.append(rgba.crop((left + bounds[0], bounds[1], left + bounds[2], bounds[3])))
    return parts


def _visible_average_color(image: Image.Image) -> tuple[int, int, int]:
    rgba = image.convert("RGBA")
    totals = [0, 0, 0]
    total_weight = 0
    for red, green, blue, alpha in rgba.getdata():
        if alpha < 32:
            continue
        totals[0] += red * alpha
        totals[1] += green * alpha
        totals[2] += blue * alpha
        total_weight += alpha
    if not total_weight:
        return 160, 120, 32
    return tuple(round(value / total_weight) for value in totals)


def _warp_vest_rows(image: Image.Image, width: int, height: int, view: str) -> Image.Image:
    """Create a torso-like trapezoid without adding heavyweight CV dependencies."""
    base = image.resize((width, height), Image.Resampling.LANCZOS)
    warped = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    side_view = view == "slight_side"
    for row_index in range(height):
        progress = row_index / max(1, height - 1)
        if side_view:
            left_inset = round(width * (0.15 * (1 - progress)))
            right_inset = round(width * (0.04 * (1 - progress)))
        else:
            inset = round(width * (0.09 * (1 - progress)))
            left_inset = inset
            right_inset = inset
        row_width = max(1, width - left_inset - right_inset)
        row = base.crop((0, row_index, width, row_index + 1)).resize(
            (row_width, 1), Image.Resampling.BILINEAR
        )
        warped.alpha_composite(row, (left_inset, row_index))
    return warped


def _high_visibility_torso_mask(human: Image.Image, y_start: int, y_end: int) -> tuple[Image.Image, int]:
    """Find an existing bright safety vest so it is replaced instead of doubled."""
    hue, saturation, value = human.convert("RGB").convert("HSV").split()
    high_visibility_hue = hue.point(lambda pixel: 255 if 24 <= pixel <= 95 else 0)
    saturated = saturation.point(lambda pixel: 255 if pixel >= 85 else 0)
    bright = value.point(lambda pixel: 255 if pixel >= 145 else 0)
    detected = ImageChops.multiply(ImageChops.multiply(high_visibility_hue, saturated), bright)
    roi = Image.new("L", human.size, 0)
    margin_x = round(human.width * 0.12)
    ImageDraw.Draw(roi).rectangle(
        (margin_x, max(0, y_start), human.width - margin_x, min(human.height, y_end)),
        fill=255,
    )
    detected = ImageChops.multiply(detected, roi)
    pixel_count = sum(detected.histogram()[128:])
    if pixel_count:
        detected = detected.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(5))
    return detected, pixel_count


def _build_repaint_mask(
    human: Image.Image,
    product_alpha: Image.Image,
    x: int,
    y: int,
    placement_profile: str,
) -> tuple[Image.Image, int]:
    mask = Image.new("L", human.size, 0)
    mask.paste(product_alpha, (x, y), product_alpha)
    detected_pixel_count = 0
    if placement_profile == "reflective_vest":
        # Include neckline, arm-hole seams, and any existing high-visibility vest.
        polygon = Image.new("L", human.size, 0)
        width, height = product_alpha.size
        inset = round(width * 0.08)
        points = (
            (x + inset, max(0, y - round(height * 0.04))),
            (x + width - inset, max(0, y - round(height * 0.04))),
            (min(human.width, x + width + round(width * 0.04)), min(human.height, y + height)),
            (max(0, x - round(width * 0.04)), min(human.height, y + height)),
        )
        ImageDraw.Draw(polygon).polygon(points, fill=255)
        existing_vest, detected_pixel_count = _high_visibility_torso_mask(
            human,
            max(0, y - round(height * 0.08)),
            min(human.height, y + round(height * 1.12)),
        )
        mask = ImageChops.lighter(mask, polygon)
        mask = ImageChops.lighter(mask, existing_vest)

    # Expand past the artificial product boundary and feather the transition.
    radius = max(9, round(min(human.size) * 0.035))
    if radius % 2 == 0:
        radius += 1
    mask = mask.filter(ImageFilter.MaxFilter(radius))
    mask = mask.filter(ImageFilter.GaussianBlur(max(3, round(min(human.size) * 0.012))))
    if placement_profile == "reflective_vest":
        # The vest may touch the neck, but the face must remain identity-stable.
        face_guard = Image.new("L", human.size, 0)
        fade_start = max(0, y - 3)
        fade_end = min(human.height, y + max(8, round(human.height * 0.025)))
        guard_draw = ImageDraw.Draw(face_guard)
        if fade_end > fade_start:
            for row in range(fade_start, fade_end):
                value = round(255 * (row - fade_start) / max(1, fade_end - fade_start))
                guard_draw.line((0, row, human.width, row), fill=value)
        if fade_end < human.height:
            guard_draw.rectangle((0, fade_end, human.width, human.height), fill=255)
        mask = ImageChops.multiply(mask, face_guard)
    return mask, detected_pixel_count


def _alpha_composite_clipped(canvas: Image.Image, layer: Image.Image, x: int, y: int) -> None:
    left = max(0, -x)
    top = max(0, -y)
    right = min(layer.width, canvas.width - x)
    bottom = min(layer.height, canvas.height - y)
    if right <= left or bottom <= top:
        return
    canvas.alpha_composite(layer.crop((left, top, right, bottom)), (max(0, x), max(0, y)))


def render_human_wearing_design(
    task_id: str,
    human_path: Path,
    ppe_path: Path,
    size: str = "512x512",
    position_x_ratio: float = 0.5,
    position_y_ratio: float = 0.0,
    ppe_width_ratio: float = 0.30,
    opacity: float = 0.92,
    *,
    placement_profile: str = "default",
    ppe_category: str | None = None,
    view: str = "front",
    framing: str = "half_body",
    body_anchors: Mapping[str, Any] | None = None,
    auto_align: bool = True,
) -> tuple[Path, Path, Path]:
    """Build a body-anchored composite and a contact-only inpaint mask."""
    ensure_storage_dirs()
    if not human_path.exists() or not ppe_path.exists():
        raise ValueError("human_reference or ppe_reference file does not exist.")
    if view not in {"front", "slight_side"}:
        raise ValueError("human_wearing view 仅支持 front 或 slight_side。")
    if framing not in {"half_body", "full_body"}:
        raise ValueError("human_wearing framing 仅支持 half_body 或 full_body。")
    if not 0 <= position_x_ratio <= 1 or not 0 <= position_y_ratio <= 1:
        raise ValueError("human_wearing position ratios must be between 0 and 1.")
    if not 0 < ppe_width_ratio <= 1 or not 0 <= opacity <= 1:
        raise ValueError("human_wearing PPE ratio or opacity is invalid.")

    normalized_category = (ppe_category or _PROFILE_TO_CATEGORY.get(placement_profile, "unknown")).strip().lower()
    if normalized_category not in {"helmet", "vest", "goggles", "gloves", "boots"}:
        raise ValueError("无法识别 PPE 类别；穿戴生成仅支持安全帽、背心、护目镜、手套和鞋子。")

    try:
        with Image.open(human_path) as source:
            human = _fit_human_frame(source, _parse_size(size), framing)
        with Image.open(ppe_path) as source:
            ppe = _trim_transparent_product(source)
    except OSError as exc:
        raise ValueError(f"human_wearing image could not be read: {exc}") from exc

    anchors = dict(body_anchors) if body_anchors is not None else analyze_body_anchors(
        human, view=view, framing=framing
    )
    if normalized_category == "gloves" and not anchors["hands_visible"]:
        raise ValueError("当前模特没有完整露出双手，不能可靠生成手套。请更换露出双手的半身或全身模特。")
    if normalized_category == "boots" and framing != "full_body":
        raise ValueError("鞋子只能使用全身模特生成，请切换到同角度、同性别的全身模特。")
    if normalized_category == "boots" and not anchors["feet_visible"]:
        raise ValueError("当前全身模特的双脚不完整，不能可靠生成鞋子。请更换双脚完整可见的模特。")
    placement_strategy = "body_anchor"
    if auto_align:
        requested_placements = resolve_ppe_placements(
            anchors,
            normalized_category,
            ppe.height / max(1, ppe.width),
        )
    else:
        placement_strategy = "manual_canvas_ratio"
        target_width = max(1, min(human.width, round(human.width * ppe_width_ratio)))
        target_height = max(1, round(ppe.height * target_width / max(1, ppe.width)))
        requested_placements = [{
            "role": "manual",
            "center_x": (human.width - target_width) * position_x_ratio + target_width / 2,
            "center_y": human.height * position_y_ratio + target_height / 2,
            "width": target_width,
            "height": target_height,
            "rotation": 0.0,
            "mirror": False,
        }]

    product_canvas = Image.new("RGBA", human.size, (0, 0, 0, 0))
    rendered_placements: list[dict[str, Any]] = []
    paired_sources = (
        _split_paired_product(ppe)
        if normalized_category in {"gloves", "boots"} and len(requested_placements) == 2
        else [ppe]
    )
    for placement_index, requested in enumerate(requested_placements):
        source_component = paired_sources[min(placement_index, len(paired_sources) - 1)]
        target_width = max(1, round(float(requested["width"])))
        target_height = max(1, round(float(requested["height"])))
        if normalized_category == "vest":
            layer = _warp_vest_rows(source_component, target_width, target_height, view)
        else:
            layer = source_component.resize((target_width, target_height), Image.Resampling.LANCZOS)
        if requested.get("mirror") and len(paired_sources) == 1:
            layer = ImageOps.mirror(layer)
        if opacity < 1:
            layer.putalpha(layer.getchannel("A").point(lambda value: round(value * opacity)))
        rotation = float(requested.get("rotation", 0.0))
        if rotation:
            layer = layer.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=True)
        x = round(float(requested["center_x"]) - layer.width / 2)
        y = round(float(requested["center_y"]) - layer.height / 2)
        _alpha_composite_clipped(product_canvas, layer, x, y)
        rendered_placements.append({
            **requested,
            "rendered_x": x,
            "rendered_y": y,
            "rendered_width": layer.width,
            "rendered_height": layer.height,
            "source_component_index": placement_index if len(paired_sources) > 1 else 0,
            "source_component_count": len(paired_sources),
        })

    blend = prepare_blend_inputs(
        human,
        product_canvas,
        normalized_category,
        rendered_placements,
        anchors,
    )
    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    base_path = output_dir / "human_wearing_base.png"
    product_layer_path = output_dir / "human_wearing_product_layer.png"
    image_path = output_dir / "human_wearing_input.png"
    mask_path = output_dir / "human_wearing_mask.png"
    debug_path = output_dir / "human_wearing_mask_debug.png"
    metadata_path = output_dir / "human_wearing_metadata.json"
    human.convert("RGB").save(base_path, format="PNG")
    product_canvas.save(product_layer_path, format="PNG")
    blend.composite.save(image_path, format="PNG")
    blend.mask.save(mask_path, format="PNG")
    blend.debug.save(debug_path, format="PNG")

    first = rendered_placements[0]
    persisted_anchors = public_anchor_metadata(anchors)
    metadata_path.write_text(
        json.dumps(
            {
                "engine": "pillow-body-anchor-contact-blend",
                "generation_mode": "human_wearing",
                "strategy": "body_anchor_contact_band_masked_img2img",
                "human_reference_path": str(human_path),
                "ppe_reference_path": str(ppe_path),
                "base_path": str(base_path),
                "product_layer_path": str(product_layer_path),
                "output_path": str(image_path),
                "mask_path": str(mask_path),
                "mask_debug_path": str(debug_path),
                "width": human.width,
                "height": human.height,
                "view": view,
                "framing": framing,
                "placement_profile": placement_profile,
                "ppe_category": normalized_category,
                "placement_strategy": placement_strategy,
                "position_x_ratio": position_x_ratio,
                "position_y_ratio": position_y_ratio,
                "ppe_width_ratio": ppe_width_ratio,
                "opacity": opacity,
                "product_pixel_x": first["rendered_x"],
                "product_pixel_y": first["rendered_y"],
                "product_pixel_width": first["rendered_width"],
                "product_pixel_height": first["rendered_height"],
                "auto_alignment_used": placement_strategy == "body_anchor",
                "body_anchors": persisted_anchors,
                "placements": rendered_placements,
                "hands_visible": persisted_anchors["hands_visible"],
                "feet_visible": persisted_anchors["feet_visible"],
                "blend": blend.metadata,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return image_path, metadata_path, mask_path
