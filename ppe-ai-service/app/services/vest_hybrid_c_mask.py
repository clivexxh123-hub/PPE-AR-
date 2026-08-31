"""Hybrid C graded-mask builder for the Vest wearing PoC.

Pillow only, and deliberately free of any ``app.*`` import so the module can be
copied into another worktree unchanged.  Nothing in the formal 1d51e36 pipeline
imports this file.

Formal ``ppe_blend_service.build_contact_mask`` emits a binary contact band and
hard-locks a single rectangle over the whole mid/lower chest.  Here the mask is
graded instead: every pixel carries a 0-255 weight that both
``SetLatentNoiseMask`` and the final ``Image.composite`` read as a per-pixel
generation budget.

    0    person, background and product identity features -- byte identical
    40   halo around identity features, avoids hard cut edges
    140  vest fabric field -- folds, curvature, scene light; colour drift damped
    255  body contact zones -- shoulder cap, neckline, armholes, seams, hem
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter

GRADE_IDENTITY_HALO = 40
GRADE_FIELD = 140
GRADE_CONTACT = 255


@dataclass(frozen=True)
class HybridCMask:
    mask: Image.Image
    overlay: Image.Image
    regions: dict[str, Image.Image]
    metadata: dict[str, Any]


def _morph(mask: Image.Image, radius: float, filter_class: type) -> Image.Image:
    """True morphology in bounded steps; PIL rank filters get slow past ~13px."""
    remaining = int(round(radius))
    result = mask
    while remaining > 0:
        step = min(remaining, 6)
        result = result.filter(filter_class(2 * step + 1))
        remaining -= step
    return result


def dilate(mask: Image.Image, radius: float) -> Image.Image:
    return _morph(mask, radius, ImageFilter.MaxFilter)


def erode(mask: Image.Image, radius: float) -> Image.Image:
    return _morph(mask, radius, ImageFilter.MinFilter)


def binary(mask: Image.Image, threshold: int = 128) -> Image.Image:
    return mask.convert("L").point(lambda value: 255 if value >= threshold else 0)


def _rect(size: tuple[int, int], box: Sequence[float]) -> Image.Image:
    layer = Image.new("L", size, 0)
    x0, y0, x1, y1 = (int(round(value)) for value in box)
    x0, x1 = max(0, min(size[0], x0)), max(0, min(size[0], x1))
    y0, y1 = max(0, min(size[1], y0)), max(0, min(size[1], y1))
    if x1 > x0 and y1 > y0:
        ImageDraw.Draw(layer).rectangle((x0, y0, x1 - 1, y1 - 1), fill=255)
    return layer


def _ellipse(size: tuple[int, int], box: Sequence[float]) -> Image.Image:
    layer = Image.new("L", size, 0)
    x0, y0, x1, y1 = (int(round(value)) for value in box)
    if x1 > x0 and y1 > y0:
        ImageDraw.Draw(layer).ellipse((x0, y0, x1, y1), fill=255)
    return layer


def _flat(size: tuple[int, int], value: int) -> Image.Image:
    return Image.new("L", size, value)


def _scaled(layer: Image.Image, grade: int) -> Image.Image:
    return ImageChops.multiply(layer, _flat(layer.size, grade))


def _coverage(mask: Image.Image, threshold: int) -> float:
    total = mask.width * mask.height
    return round(sum(mask.histogram()[threshold:]) / float(total), 4)


def skin_mask(image: Image.Image) -> Image.Image:
    """Same predicate as human_anchor_service so PoC and formal agree on skin."""
    rgb = image.convert("RGB")
    values = []
    for red, green, blue in rgb.getdata():
        chroma = max(red, green, blue) - min(red, green, blue)
        values.append(
            255
            if (
                red >= 82
                and green >= 38
                and blue >= 18
                and red > green
                and red > blue
                and red - green >= 7
                and chroma >= 18
            )
            else 0
        )
    mask = Image.new("L", rgb.size, 0)
    mask.putdata(values)
    return mask


def product_identity_mask(product_layer: Image.Image, vest: Image.Image) -> Image.Image:
    """Reflective bands, zipper/piping/print frame, and pocket-seam contours."""
    rgb = product_layer.convert("RGB")
    _, saturation, value = rgb.convert("HSV").split()
    silver = ImageChops.multiply(
        saturation.point(lambda pixel: 255 if pixel <= 60 else 0),
        value.point(lambda pixel: 255 if pixel >= 120 else 0),
    )
    dark = value.point(lambda pixel: 255 if pixel <= 70 else 0)
    edges = binary(rgb.convert("L").filter(ImageFilter.FIND_EDGES), 40)
    identity = ImageChops.lighter(ImageChops.lighter(silver, dark), edges)
    return dilate(ImageChops.multiply(identity, vest), 1)


def _row_span_fill(mask: Image.Image, top: int, bottom: int) -> Image.Image:
    """Fill each row between its outermost lit pixels.

    This can only close interior notches; it never widens the silhouette, which
    is what makes it safe to run against a torn studio segmentation.
    """
    width, height = mask.size
    filled = mask.copy()
    pixels = mask.load()
    draw = ImageDraw.Draw(filled)
    for y in range(max(0, top), min(height, bottom)):
        left = next((x for x in range(width) if pixels[x, y]), None)
        if left is None:
            continue
        right = next((x for x in range(width - 1, -1, -1) if pixels[x, y]), left)
        if right > left:
            draw.line((left, y, right, y), fill=255)
    return filled


def repair_subject_mask(
    subject_mask: Image.Image,
    shape_prior: Image.Image,
    anchors: Mapping[str, Any],
    *,
    close_radius: int = 9,
) -> tuple[Image.Image, dict[str, Any]]:
    """Close the studio-background tear that leaks scene pixels onto a shoulder.

    ``human_scene_service._studio_subject_mask`` compares each row against an
    interpolated background colour; where the shirt matches that colour the row
    drops out, and ``_keep_primary_subject`` then erodes the remnants away.
    """
    original = binary(subject_mask, 96)
    closed = erode(dilate(original, close_radius), close_radius)
    face_width = float(anchors["face_width"])
    top = int(round(float(anchors["shoulder_y"]) - face_width * 0.20))
    filled = _row_span_fill(closed, top, subject_mask.height)
    filled = ImageChops.multiply(filled, binary(shape_prior, 128))
    repaired = ImageChops.lighter(original, filled)
    recovered = sum(ImageChops.subtract(repaired, original).histogram()[128:])
    return repaired.filter(ImageFilter.GaussianBlur(1.0)), {
        "method": "morphological_close_plus_row_span_fill_within_shape_prior",
        "close_radius_px": close_radius,
        "row_fill_top_y": top,
        "original_subject_pixels": sum(original.histogram()[128:]),
        "recovered_pixels": recovered,
    }


def build_hybrid_c_mask(
    *,
    product_layer: Image.Image,
    base_human: Image.Image,
    subject_mask: Image.Image,
    anchors: Mapping[str, Any],
    placement: Mapping[str, Any],
) -> HybridCMask:
    size = product_layer.size
    width, height = size
    vest = binary(product_layer.getchannel("A"), 24)

    vest_x0 = float(placement["rendered_x"])
    vest_y0 = float(placement["rendered_y"])
    vest_width = float(placement["rendered_width"])
    vest_x1 = vest_x0 + vest_width
    vest_y1 = min(float(height), vest_y0 + float(placement["rendered_height"]))
    # Half-body framing crops the vest, so every ratio below is taken against
    # the *visible* height.  Using the nominal height puts the neckline and hem
    # bands far outside the canvas.
    vest_visible_height = max(1.0, vest_y1 - vest_y0)
    vest_center_x = (vest_x0 + vest_x1) / 2.0

    face = anchors["face_box"]
    face_width = float(anchors["face_width"])
    face_center_x = (face["x0"] + face["x1"]) / 2.0
    head_width = float(anchors["head_width"])
    head_height = float(anchors["head_height"])
    shoulder_y = float(anchors["shoulder_y"])
    shoulder_left = float(anchors["shoulder_left"])
    shoulder_right = float(anchors["shoulder_right"])
    shoulder_width = max(1.0, shoulder_right - shoulder_left)

    ring_px = max(3.0, min(vest_width, vest_visible_height) * 0.045)

    roi = _rect(
        size,
        (
            vest_x0 - vest_width * 0.14,
            shoulder_y - face_width * 0.55,
            vest_x1 + vest_width * 0.14,
            height,
        ),
    )

    subject = binary(subject_mask, 128)
    background = ImageChops.invert(dilate(subject, 1))
    face_guard = _ellipse(
        size,
        (
            face_center_x - head_width * 0.58,
            float(anchors["head_top_y"]) - head_height * 0.20,
            face_center_x + head_width * 0.58,
            float(face["y1"]) + head_height * 0.06,
        ),
    )
    # The skin predicate accepts saturated reds, so a red garment would be
    # protected as skin.  Subtracting the product interior keeps the throat and
    # the open V-neck protected while never freezing the product itself.
    skin = ImageChops.subtract(dilate(skin_mask(base_human), 3), erode(vest, 2))
    hard_protect = ImageChops.lighter(ImageChops.lighter(background, face_guard), skin)
    allow = ImageChops.invert(hard_protect.filter(ImageFilter.GaussianBlur(1.5)))

    ring = ImageChops.subtract(dilate(vest, ring_px), erode(vest, ring_px))
    # The product's black piping traces the entire silhouette, so the boundary
    # has to come back out of the identity set or Hybrid C re-locks the very
    # edges it exists to soften.
    identity_core = ImageChops.subtract(product_identity_mask(product_layer, vest), ring)
    identity_halo = ImageChops.subtract(dilate(identity_core, 3), identity_core)

    field = ImageChops.subtract(
        ImageChops.subtract(erode(vest, 2), identity_core), identity_halo
    )

    shoulder_cap = ImageChops.multiply(
        _rect(
            size,
            (
                shoulder_left - shoulder_width * 0.10,
                shoulder_y - face_width * 0.35,
                shoulder_right + shoulder_width * 0.10,
                shoulder_y + face_width * 0.30,
            ),
        ),
        subject,
    )
    underarm = Image.new("L", size, 0)
    for center_x in (shoulder_left, shoulder_right):
        underarm = ImageChops.lighter(
            underarm,
            _ellipse(
                size,
                (
                    center_x - face_width * 0.40,
                    shoulder_y + face_width * 0.40,
                    center_x + face_width * 0.40,
                    shoulder_y + face_width * 1.50,
                ),
            ),
        )
    underarm = ImageChops.multiply(underarm, subject)
    neckline = _ellipse(
        size,
        (
            vest_center_x - vest_width * 0.20,
            vest_y0 - vest_visible_height * 0.05,
            vest_center_x + vest_width * 0.20,
            vest_y0 + vest_visible_height * 0.18,
        ),
    )
    side_seams = ImageChops.lighter(
        _rect(size, (vest_x0 - vest_width * 0.07, vest_y0, vest_x0 + vest_width * 0.10, vest_y1)),
        _rect(size, (vest_x1 - vest_width * 0.10, vest_y0, vest_x1 + vest_width * 0.07, vest_y1)),
    )
    hem = _rect(
        size,
        (
            vest_x0 - vest_width * 0.05,
            vest_y1 - vest_visible_height * 0.10,
            vest_x1 + vest_width * 0.05,
            vest_y1,
        ),
    )
    hem_in_frame = vest_y1 < height - 1

    contact = ring
    for layer in (shoulder_cap, underarm, neckline, side_seams):
        contact = ImageChops.lighter(contact, layer)
    if hem_in_frame:
        contact = ImageChops.lighter(contact, hem)
    contact = ImageChops.multiply(contact, dilate(subject, 2))
    contact = ImageChops.multiply(contact, roi)

    graded = _scaled(identity_halo, GRADE_IDENTITY_HALO)
    graded = ImageChops.lighter(graded, _scaled(field, GRADE_FIELD))
    graded = ImageChops.lighter(graded, _scaled(contact, GRADE_CONTACT))
    graded = ImageChops.multiply(graded, roi)
    graded = ImageChops.multiply(graded, allow)
    graded = ImageChops.subtract(graded, _scaled(identity_core, 255))
    mask = ImageChops.multiply(
        graded.filter(ImageFilter.GaussianBlur(2.0)), dilate(roi, 3)
    )

    heat = Image.merge(
        "RGB",
        (
            mask,
            ImageChops.multiply(mask, _flat(size, 60)),
            ImageChops.invert(mask).point(lambda value: value // 3),
        ),
    )
    overlay = Image.blend(base_human.convert("RGB"), heat, 0.55)

    regions = {
        "vest_all": vest,
        "identity_core": erode(identity_core, 3),
        "vest_field": ImageChops.subtract(field, contact),
        "contact_all": contact,
        "shoulder_cap": ImageChops.multiply(shoulder_cap, roi),
        "face_guard": face_guard,
        "skin": skin,
        "background": background,
    }
    histogram = mask.histogram()
    vest_pixels = max(1, sum(vest.histogram()[128:]))
    metadata = {
        "strategy": "hybrid_c_graded_identity_aware_mask",
        # If this climbs past ~0.45 the identity thresholds are too greedy and
        # Hybrid C degenerates back into A.
        "identity_core_share_of_vest": round(
            sum(identity_core.histogram()[128:]) / vest_pixels, 3
        ),
        "grades": {
            "identity_core": 0,
            "identity_halo": GRADE_IDENTITY_HALO,
            "field": GRADE_FIELD,
            "contact": GRADE_CONTACT,
        },
        "ring_px": round(ring_px, 2),
        "vest_visible_height_px": round(vest_visible_height, 1),
        "hem_band_in_frame": hem_in_frame,
        "coverage_any": _coverage(mask, 1),
        "coverage_strong": _coverage(mask, 128),
        "mean_grade_over_vest": round(
            sum(
                value * count
                for value, count in enumerate(
                    ImageChops.multiply(mask, vest).histogram()
                )
            )
            / max(1, sum(vest.histogram()[128:])),
            2,
        ),
        "pixels_hard_locked": histogram[0],
        "mask_bbox": list(mask.getbbox()) if mask.getbbox() else None,
        "region_pixels": {
            name: sum(layer.histogram()[128:]) for name, layer in regions.items()
        },
    }
    return HybridCMask(mask=mask, overlay=overlay, regions=regions, metadata=metadata)
