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

    for placement in placements:
        left = float(placement["rendered_x"])
        top = float(placement["rendered_y"])
        width = float(placement["rendered_width"])
        height = float(placement["rendered_height"])
        right = left + width
        bottom = top + height
        if category == "helmet":
            band = ImageChops.lighter(
                band,
                _rect(size, (left - width * 0.08, bottom - height * 0.23, right + width * 0.08, bottom + height * 0.11)),
            )
            band = ImageChops.subtract(band, _blur_erode(visible, scale * 0.07))
        elif category == "vest":
            band = ImageChops.lighter(
                band,
                _rect(size, (left - width * 0.07, top - height * 0.05, right + width * 0.07, top + height * 0.18)),
            )
            band = ImageChops.lighter(band, _rect(size, (left - width * 0.07, top, left + width * 0.14, bottom)))
            band = ImageChops.lighter(band, _rect(size, (right - width * 0.14, top, right + width * 0.07, bottom)))
            core = _rect(size, (left + width * 0.23, top + height * 0.20, right - width * 0.23, top + height * 0.94))
            band = ImageChops.subtract(band, core)
        elif category == "gloves":
            band = ImageChops.lighter(
                band,
                _rect(size, (left - width * 0.08, bottom - height * 0.28, right + width * 0.08, bottom + height * 0.08)),
            )
            band = ImageChops.subtract(band, _blur_erode(visible, scale * 0.10))
        elif category == "boots":
            band = ImageChops.lighter(
                band,
                _rect(size, (left - width * 0.08, top - height * 0.07, right + width * 0.08, top + height * 0.28)),
            )
            band = ImageChops.lighter(
                band,
                _rect(size, (left - width * 0.06, bottom - height * 0.15, right + width * 0.06, bottom + height * 0.06)),
            )
            band = ImageChops.subtract(band, _blur_erode(visible, scale * 0.10))

    if category != "goggles":
        band = ImageChops.subtract(band, _face_guard(size, anchors))
    feather = max(1.0, scale * 0.022)
    mask = band.filter(ImageFilter.GaussianBlur(feather))
    coverage = sum(mask.histogram()[128:]) / float(size[0] * size[1])
    return mask, {
        "ppe_category": category,
        "strategy": "category_contact_band_mask",
        "mask_coverage_ratio": round(coverage, 4),
        "ring_outer_px": round(scale * 0.055, 2),
        "ring_inner_px": round(scale * 0.035, 2),
        "feather_px": round(feather, 2),
        "face_protected": True,
        "product_core_protected": True,
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
    overlay = Image.new("RGB", treated.size, (255, 48, 48))
    debug = Image.composite(Image.blend(treated, overlay, 0.42), treated, mask)
    return BlendResult(
        composite=treated,
        mask=mask,
        debug=debug,
        metadata={**mask_metadata, **edge_metadata},
    )
