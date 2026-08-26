"""Contact-region masks and edge treatment for human_wearing refinement.

Global img2img rewrites the whole frame at one denoise level.  Measured on the
real A/B: at 0.30-0.50 the alpha-composite seam survives untouched (a hard edge
is a high-confidence structure the sampler preserves) while the wearer's face,
the product interior and the background all drift.  The fidelity is spent
everywhere except the one place that needs rebuilding.

This module produces the two inputs that let a masked img2img spend a *high*
denoise budget only on the PPE/body contact band:

  * ``build_contact_mask``  - where the sampler is allowed to repaint
  * ``apply_edge_treatment`` - feathered seam + directional contact shadow

Helmet and vest get different bands: a helmet's believability lives at the
brim/forehead/hair/ear boundary, a vest's at the shoulders, sides and armpits.
Pillow only - the service venv has no numpy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# Band geometry, in units of the rendered PPE size or the measured head.
_RING_OUTER = 0.050        # ring reaches this far outside the PPE silhouette
_RING_INNER = 0.035        # ...and this far inside it
_PRODUCT_CORE_ERODE = 0.060      # helmet interior that must never be repainted
_HELMET_BAND_HALF_WIDTH = 0.90   # x half-extent, in head widths (covers ears)
_HELMET_BAND_TOP = 0.25          # above the brim, in helmet heights
_HELMET_BAND_BOTTOM = 0.50       # below the hairline, in head heights
_FACE_PROTECT_TOP = 0.30         # hairline -> brow, in head heights
_FACE_PROTECT_BOTTOM = 0.80      # hairline -> below chin
_FACE_PROTECT_WIDTH = 1.06
_VEST_SHOULDER_TOP = 0.06        # in vest heights
_VEST_SHOULDER_BOTTOM = 0.15
_VEST_SHOULDER_WIDTH = 1.16      # in vest widths, to reach the deltoids
_VEST_SIDE_WIDTH = 0.12
_VEST_SIDE_OUTSET = 0.08
_VEST_CORE_WIDTH = 0.58          # protected centre: strips, pockets, zip
_VEST_CORE_TOP = 0.18
_VEST_CORE_BOTTOM = 0.94
_FEATHER_RATIO = 0.020
_SHADOW_BLUR_RATIO = 0.040
_SHADOW_OFFSET_RATIO = 0.025
_SHADOW_STRENGTH = 0.28
_SEAM_SOFTEN_RATIO = 0.010

_SUPPORTED = frozenset({"helmet", "vest"})


@dataclass(frozen=True)
class BlendResult:
    composite: Image.Image
    mask: Image.Image
    debug: Image.Image
    metadata: dict[str, Any]


def _blur_dilate(mask: Image.Image, radius: float) -> Image.Image:
    """Approximate a morphological dilation; Pillow's rank filters are slow."""
    if radius <= 0:
        return mask
    return mask.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: 255 if v > 26 else 0)


def _blur_erode(mask: Image.Image, radius: float) -> Image.Image:
    if radius <= 0:
        return mask
    return mask.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: 255 if v > 229 else 0)


def _rect(size: tuple[int, int], box: tuple[float, float, float, float]) -> Image.Image:
    layer = Image.new("L", size, 0)
    left, top, right, bottom = (int(round(v)) for v in box)
    if right > left and bottom > top:
        ImageDraw.Draw(layer).rectangle((left, top, right, bottom), fill=255)
    return layer


def _ellipse(size: tuple[int, int], box: tuple[float, float, float, float]) -> Image.Image:
    layer = Image.new("L", size, 0)
    left, top, right, bottom = (int(round(v)) for v in box)
    if right > left and bottom > top:
        ImageDraw.Draw(layer).ellipse((left, top, right, bottom), fill=255)
    return layer


def _ppe_layer(size: tuple[int, int], ppe: Image.Image, paste: tuple[int, int]) -> Image.Image:
    layer = Image.new("L", size, 0)
    layer.paste(ppe.getchannel("A"), paste)
    return layer


def build_contact_mask(
    size: tuple[int, int],
    ppe: Image.Image,
    paste: tuple[int, int],
    ppe_category: str,
    anchor: Mapping[str, Any],
) -> tuple[Image.Image, dict[str, Any]]:
    """Return the soft mask marking the PPE/body contact band."""
    category = (ppe_category or "").strip().lower()
    if category not in _SUPPORTED:
        raise ValueError(f"ppe_blend 仅支持：{', '.join(sorted(_SUPPORTED))}。")

    ppe_width, ppe_height = ppe.size
    scale = float(min(ppe_width, ppe_height))
    solid = _ppe_layer(size, ppe, paste)
    ring = ImageChops.subtract(
        _blur_dilate(solid, _RING_OUTER * scale),
        _blur_erode(solid, _RING_INNER * scale),
    )

    face = anchor["face_box"]
    face_cx = (face["x0"] + face["x1"]) / 2.0
    face_width = float(anchor["face_width"])
    head_width = float(anchor["head_width"])
    head_height = float(anchor["head_height"])
    hairline = float(anchor["hairline_y"])
    left, top = paste

    band = ring
    if category == "helmet":
        # Only the brim line and what it touches - never the dome.  Repainting
        # the shell is what produces a second hat and a wrong product colour.
        brim = top + ppe_height
        band = ImageChops.lighter(band, _rect(size, (
            face_cx - _HELMET_BAND_HALF_WIDTH * head_width,
            brim - _HELMET_BAND_TOP * ppe_height,
            face_cx + _HELMET_BAND_HALF_WIDTH * head_width,
            max(brim, hairline + _HELMET_BAND_BOTTOM * head_height),
        )))
        band = ImageChops.subtract(band, _blur_erode(solid, _PRODUCT_CORE_ERODE * scale))
    else:
        band = ImageChops.lighter(band, _rect(size, (
            face_cx - _VEST_SHOULDER_WIDTH * ppe_width / 2.0,
            top - _VEST_SHOULDER_TOP * ppe_height,
            face_cx + _VEST_SHOULDER_WIDTH * ppe_width / 2.0,
            top + _VEST_SHOULDER_BOTTOM * ppe_height,
        )))
        for outer_x in (left, left + ppe_width):
            band = ImageChops.lighter(band, _rect(size, (
                outer_x - (_VEST_SIDE_WIDTH if outer_x == left + ppe_width else _VEST_SIDE_OUTSET) * ppe_width,
                top,
                outer_x + (_VEST_SIDE_OUTSET if outer_x == left + ppe_width else _VEST_SIDE_WIDTH) * ppe_width,
                top + ppe_height,
            )))
        band = ImageChops.subtract(band, _rect(size, (
            left + (1 - _VEST_CORE_WIDTH) / 2.0 * ppe_width,
            top + _VEST_CORE_TOP * ppe_height,
            left + (1 + _VEST_CORE_WIDTH) / 2.0 * ppe_width,
            top + _VEST_CORE_BOTTOM * ppe_height,
        )))

    # The wearer's face is never a blending problem; repainting it changes the
    # model's identity, which a client notices immediately.
    band = ImageChops.subtract(band, _ellipse(size, (
        face_cx - _FACE_PROTECT_WIDTH * face_width / 2.0,
        hairline + _FACE_PROTECT_TOP * head_height,
        face_cx + _FACE_PROTECT_WIDTH * face_width / 2.0,
        hairline + _FACE_PROTECT_BOTTOM * head_height,
    )))

    feather = max(1.0, _FEATHER_RATIO * scale)
    mask = band.filter(ImageFilter.GaussianBlur(feather))
    coverage = sum(mask.histogram()[128:]) / float(size[0] * size[1])
    return mask, {
        "ppe_category": category,
        "ring_outer_px": round(_RING_OUTER * scale, 2),
        "ring_inner_px": round(_RING_INNER * scale, 2),
        "feather_px": round(feather, 2),
        "mask_coverage_ratio": round(coverage, 4),
        "face_protected": True,
        "core_protected": category == "vest",
    }


def apply_edge_treatment(
    composite: Image.Image,
    ppe: Image.Image,
    paste: tuple[int, int],
    strength: float = 1.0,
) -> tuple[Image.Image, dict[str, Any]]:
    """Soften the razor alpha seam and drop a contact shadow under the product."""
    base = composite.convert("RGB")
    size = base.size
    ppe_width, ppe_height = ppe.size
    scale = float(min(ppe_width, ppe_height))
    solid = _ppe_layer(size, ppe, paste)

    shadow_source = Image.new("L", size, 0)
    shadow_source.paste(
        ppe.getchannel("A"),
        (paste[0], paste[1] + int(round(_SHADOW_OFFSET_RATIO * ppe_height))),
    )
    shadow = shadow_source.filter(ImageFilter.GaussianBlur(max(1.0, _SHADOW_BLUR_RATIO * scale)))
    # Only outside the product: a shadow on the product itself reads as dirt.
    shadow = ImageChops.subtract(shadow, _blur_dilate(solid, 1.0))
    darkened = Image.eval(base, lambda v: int(v * (1 - _SHADOW_STRENGTH * strength)))
    base = Image.composite(darkened, base, shadow)

    soften = max(1.0, _SEAM_SOFTEN_RATIO * scale)
    seam = ImageChops.subtract(_blur_dilate(solid, soften), _blur_erode(solid, soften))
    seam = seam.filter(ImageFilter.GaussianBlur(soften * 0.7))
    base = Image.composite(base.filter(ImageFilter.GaussianBlur(soften * 0.55)), base, seam)
    return base, {
        "contact_shadow_strength": round(_SHADOW_STRENGTH * strength, 3),
        "shadow_blur_px": round(_SHADOW_BLUR_RATIO * scale, 2),
        "seam_soften_px": round(soften, 2),
    }


def prepare_blend_inputs(
    composite_path,
    ppe_resized: Image.Image,
    paste: tuple[int, int],
    ppe_category: str,
    anchor: Mapping[str, Any],
    edge_strength: float = 1.0,
) -> BlendResult:
    """Build the treated composite, the contact mask and a reviewable overlay."""
    with Image.open(composite_path) as opened:
        composite = opened.convert("RGB")
    mask, mask_meta = build_contact_mask(composite.size, ppe_resized, paste, ppe_category, anchor)
    treated, edge_meta = apply_edge_treatment(composite, ppe_resized, paste, edge_strength)

    overlay = Image.new("RGB", composite.size, (255, 40, 40))
    debug = Image.composite(
        Image.blend(treated, overlay, 0.45), treated, mask.point(lambda v: min(255, v * 2))
    )
    return BlendResult(treated, mask, debug, {**mask_meta, **edge_meta})
