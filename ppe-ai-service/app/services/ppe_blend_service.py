"""Build category-aware PPE/body contact masks and edge treatment."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageChops, ImageFilter


@dataclass(frozen=True)
class BlendResult:
    composite: Image.Image
    mask: Image.Image
    debug: Image.Image
    foreground_occlusion_mask: Image.Image
    metadata: dict[str, Any]


def _blur_dilate(mask: Image.Image, radius: float) -> Image.Image:
    if radius <= 0:
        return mask
    return mask.filter(ImageFilter.GaussianBlur(radius)).point(lambda value: 255 if value > 24 else 0)


def _blur_erode(mask: Image.Image, radius: float) -> Image.Image:
    if radius <= 0:
        return mask
    return mask.filter(ImageFilter.GaussianBlur(radius)).point(lambda value: 255 if value > 231 else 0)


def _rect(size: tuple[int, int], box: tuple[float, float, float, float]) -> Image.Image:
    layer = Image.new("L", size, 0)
    left, top, right, bottom = (round(value) for value in box)
    if right > left and bottom > top:
        layer.paste(255, (max(0, left), max(0, top), min(size[0], right), min(size[1], bottom)))
    return layer


def _face_guard(size: tuple[int, int], anchors: dict[str, Any]) -> Image.Image:
    face = anchors["face_box"]
    face_width = float(anchors["face_width"])
    head_height = float(anchors["head_height"])
    center_x = (face["x0"] + face["x1"]) / 2.0
    guard = Image.new("L", size, 0)
    left = round(center_x - face_width * 0.72)
    right = round(center_x + face_width * 0.72)
    top = round(float(anchors["hairline_y"]) - head_height * 0.18)
    bottom = round(face["y1"] + head_height * 0.22)
    from PIL import ImageDraw

    ImageDraw.Draw(guard).ellipse((left, top, right, bottom), fill=255)
    return guard.filter(ImageFilter.GaussianBlur(max(1, round(face_width * 0.035))))


def _helmet_eye_guard(size: tuple[int, int], anchors: dict[str, Any]) -> Image.Image:
    """Protect the eyes and lower face while leaving a narrow hairline band."""
    face = anchors["face_box"]
    face_width = float(anchors["face_width"])
    center_x = (face["x0"] + face["x1"]) / 2.0
    eye_line_y = float(anchors.get("eye_line_y", face["y0"] + face_width * 0.57))
    guard = Image.new("L", size, 0)
    left = round(center_x - face_width * 0.72)
    right = round(center_x + face_width * 0.72)
    top = round(eye_line_y - face_width * 0.10)
    bottom = round(face["y1"] + face_width * 0.20)
    from PIL import ImageDraw

    ImageDraw.Draw(guard).ellipse((left, top, right, bottom), fill=255)
    return guard.filter(ImageFilter.GaussianBlur(max(1, round(face_width * 0.025))))


def _helmet_contact_band(
    band: Image.Image, visible: Image.Image, scale: float, size: tuple[int, int], placement: dict[str, Any]
) -> Image.Image:
    left, top = float(placement["rendered_x"]), float(placement["rendered_y"])
    width, height = float(placement["rendered_width"]), float(placement["rendered_height"])
    right, bottom = left + width, top + height
    brim_band = _rect(size, (left - width * 0.025, bottom - height * 0.16, right + width * 0.025, bottom + height * 0.04))
    visible_brim = ImageChops.multiply(visible, brim_band)
    brim_edge = ImageChops.subtract(_blur_dilate(visible_brim, scale * 0.026), _blur_erode(visible_brim, scale * 0.018))
    return ImageChops.lighter(brim_band, brim_edge)


def _vest_contact_band(
    band: Image.Image, _visible: Image.Image, _scale: float, size: tuple[int, int], placement: dict[str, Any]
) -> Image.Image:
    left, top = float(placement["rendered_x"]), float(placement["rendered_y"])
    width, height = float(placement["rendered_width"]), float(placement["rendered_height"])
    right, bottom = left + width, top + height
    band = ImageChops.lighter(band, _rect(size, (left - width * 0.07, top - height * 0.05, right + width * 0.07, top + height * 0.18)))
    band = ImageChops.lighter(band, _rect(size, (left - width * 0.07, top, left + width * 0.14, bottom)))
    band = ImageChops.lighter(band, _rect(size, (right - width * 0.14, top, right + width * 0.07, bottom)))
    return ImageChops.subtract(band, _rect(size, (left + width * 0.23, top + height * 0.20, right - width * 0.23, top + height * 0.94)))


def _gloves_contact_band(
    band: Image.Image, visible: Image.Image, scale: float, size: tuple[int, int], placement: dict[str, Any]
) -> Image.Image:
    left, top = float(placement["rendered_x"]), float(placement["rendered_y"])
    width, height = float(placement["rendered_width"]), float(placement["rendered_height"])
    right, bottom = left + width, top + height
    band = ImageChops.lighter(band, _rect(size, (left - width * 0.08, bottom - height * 0.28, right + width * 0.08, bottom + height * 0.08)))
    return ImageChops.lighter(band, visible.filter(ImageFilter.GaussianBlur(max(1.0, scale * 0.012))))


def _boots_contact_band(
    band: Image.Image, visible: Image.Image, scale: float, size: tuple[int, int], placement: dict[str, Any]
) -> Image.Image:
    left, top = float(placement["rendered_x"]), float(placement["rendered_y"])
    width, height = float(placement["rendered_width"]), float(placement["rendered_height"])
    right, bottom = left + width, top + height
    band = ImageChops.lighter(band, _rect(size, (left - width * 0.08, top - height * 0.07, right + width * 0.08, top + height * 0.28)))
    band = ImageChops.lighter(band, _rect(size, (left - width * 0.06, bottom - height * 0.15, right + width * 0.06, bottom + height * 0.06)))
    return ImageChops.subtract(band, _blur_erode(visible, scale * 0.10))


_CATEGORY_MASK_BUILDERS = {
    "helmet": _helmet_contact_band,
    "vest": _vest_contact_band,
    "gloves": _gloves_contact_band,
    "boots": _boots_contact_band,
}


def build_contact_mask(
    product_alpha: Image.Image,
    ppe_category: str,
    placements: list[dict[str, Any]],
    anchors: dict[str, Any],
) -> tuple[Image.Image, dict[str, Any]]:
    """Repaint only product/body contact bands; keep product core and face locked."""
    size = product_alpha.size
    category = ppe_category.strip().lower()
    visible = product_alpha.point(lambda value: 255 if value >= 24 else 0)
    scale = max(8.0, min(
        [min(float(item["rendered_width"]), float(item["rendered_height"])) for item in placements]
        or [min(size)]
    ))
    ring = ImageChops.subtract(
        _blur_dilate(visible, scale * 0.055),
        _blur_erode(visible, scale * 0.035),
    )
    band = ring

    builder = _CATEGORY_MASK_BUILDERS.get(category)
    if builder is not None:
        for placement in placements:
            band = builder(band, visible, scale, size, placement)

    if category == "helmet":
        band = ImageChops.subtract(band, _helmet_eye_guard(size, anchors))
    elif category != "goggles":
        band = ImageChops.subtract(band, _face_guard(size, anchors))
    feather = max(1.0, scale * 0.022)
    mask = band.filter(ImageFilter.GaussianBlur(feather))
    coverage = sum(mask.histogram()[128:]) / float(size[0] * size[1])
    mask_bbox = mask.getbbox()
    return mask, {
        "ppe_category": category,
        "strategy": "category_contact_band_mask",
        "mask_coverage_ratio": round(coverage, 4),
        "mask_bbox": list(mask_bbox) if mask_bbox is not None else None,
        "ring_outer_px": round(scale * 0.055, 2),
        "ring_inner_px": round(scale * 0.035, 2),
        "feather_px": round(feather, 2),
        "face_protected": True,
        "product_core_protected": category != "gloves",
        "helmet_mask_mode": "brim_hairline_contact_band" if category == "helmet" else None,
    }


def build_foreground_occlusion_mask(
    product_alpha: Image.Image,
    ppe_category: str,
    placements: list[dict[str, Any]],
    anchors: dict[str, Any],
) -> tuple[Image.Image, dict[str, Any]]:
    """Return the explicit foreground layer used above a PPE pre-composite.

    A catalog Vest already encodes its armholes and V-neck in its alpha silhouette.
    Restoring guessed arm-side bands or a synthetic collar *inside* that silhouette
    makes the garment look cut through and can duplicate the subject before diffusion.
    Keep the source product alpha authoritative until a real human-parsing signal is
    available; the contact/diffusion mask remains unchanged.
    """
    size = product_alpha.size
    empty = Image.new("L", size, 0)
    category = ppe_category.strip().lower()
    if category != "vest":
        return empty, {
            "enabled": False,
            "strategy": "none",
            "reason": "category_not_vest",
            "diffusion_mask_changed": False,
        }
    return empty, {
        "enabled": False,
        "strategy": "vest_product_alpha_authoritative_v1",
        "protected_regions": [],
        "reason": "source_vest_alpha_preserves_real_v_neck_and_armholes",
        "mask_coverage_ratio": 0.0,
        "diffusion_mask_changed": False,
    }


def apply_edge_treatment(
    human: Image.Image,
    product_canvas: Image.Image,
    strength: float = 1.0,
) -> tuple[Image.Image, dict[str, Any]]:
    """Add a subtle contact shadow and soften the alpha cutout seam."""
    base = human.convert("RGB")
    product = product_canvas.convert("RGBA")
    product_alpha = product.getchannel("A")
    bounds = product_alpha.getbbox()
    if bounds is None:
        raise ValueError("PPE 合成层没有可见像素。")
    scale = float(max(8, min(bounds[2] - bounds[0], bounds[3] - bounds[1])))

    shadow_offset = max(1, round(scale * 0.018))
    shifted = Image.new("L", base.size, 0)
    shifted.paste(product_alpha, (0, shadow_offset))
    shadow = shifted.filter(ImageFilter.GaussianBlur(max(1.0, scale * 0.035)))
    shadow = ImageChops.subtract(shadow, _blur_dilate(product_alpha, 1.0))
    shadow_strength = max(0.0, min(0.36, 0.24 * strength))
    darkened = Image.eval(base, lambda value: round(value * (1 - shadow_strength)))
    treated = Image.composite(darkened, base, shadow)

    soften = max(1.0, scale * 0.009)
    seam = ImageChops.subtract(_blur_dilate(product_alpha, soften), _blur_erode(product_alpha, soften))
    seam = seam.filter(ImageFilter.GaussianBlur(soften * 0.75))
    treated = Image.composite(treated.filter(ImageFilter.GaussianBlur(soften * 0.45)), treated, seam)
    treated = Image.alpha_composite(treated.convert("RGBA"), product).convert("RGB")
    return treated, {
        "contact_shadow_strength": round(shadow_strength, 3),
        "shadow_blur_px": round(scale * 0.035, 2),
        "seam_soften_px": round(soften, 2),
    }


def prepare_blend_inputs(
    human: Image.Image,
    product_canvas: Image.Image,
    ppe_category: str,
    placements: list[dict[str, Any]],
    anchors: dict[str, Any],
) -> BlendResult:
    treated, edge_metadata = apply_edge_treatment(human, product_canvas)
    mask, mask_metadata = build_contact_mask(
        product_canvas.getchannel("A"), ppe_category, placements, anchors
    )
    foreground_occlusion, occlusion_metadata = build_foreground_occlusion_mask(
        product_canvas.getchannel("A"), ppe_category, placements, anchors
    )
    composite = Image.composite(human.convert("RGB"), treated, foreground_occlusion)
    overlay = Image.new("RGB", composite.size, (255, 48, 48))
    debug = Image.composite(Image.blend(composite, overlay, 0.42), composite, mask)
    foreground_overlay = Image.new("RGB", composite.size, (48, 156, 255))
    debug = Image.composite(Image.blend(debug, foreground_overlay, 0.38), debug, foreground_occlusion)
    return BlendResult(
        composite=composite,
        mask=mask,
        debug=debug,
        foreground_occlusion_mask=foreground_occlusion,
        metadata={**mask_metadata, **edge_metadata, "foreground_occlusion": occlusion_metadata},
    )
