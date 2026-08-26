"""Detect wearer landmarks so PPE is anchored to the body, not to the canvas.

The previous human_wearing placement interpolated a fixed ratio against the free
space of the output canvas.  That ratio knows nothing about where the wearer's
head actually is, so the same profile put a helmet over the face on one
reference and floating above the hair on the next.  This module measures one
robust landmark - the wearer's face box - and derives helmet / vest anchors from
it using standard head-unit anthropometry.

Pillow only: the AI service must keep running in the existing virtualenv.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from PIL import Image, ImageChops

# Face-width relative anthropometry (front view, adult).  Everything is
# expressed in units of the detected skin face width so a half-body and a
# full-body reference resolve to different pixel geometry automatically.
_HEAD_WIDTH_PER_FACE_WIDTH = 1.32      # hair + ears are wider than bare skin
_HEAD_HEIGHT_PER_FACE_WIDTH = 1.54     # crown to chin
_HAIRLINE_TO_CROWN_PER_HEAD_H = 0.30
_SHOULDER_WIDTH_PER_FACE_WIDTH = 2.45
_SHOULDER_DROP_PER_FACE_WIDTH = 1.75   # hairline -> shoulder line

_HELMET_WIDTH_PER_HEAD_WIDTH = 1.16    # shell sits outside the skull
_HELMET_BROW_PER_FACE_WIDTH = 0.45     # hairline -> front brim resting line
_VEST_WIDTH_PER_SHOULDER_WIDTH = 1.00
_VEST_TOP_DROP_PER_FACE_WIDTH = 0.00   # collar rests on the shoulder line

_MIN_FACE_WIDTH_RATIO = 0.035          # reject noise blobs
_MAX_FACE_WIDTH_RATIO = 0.55


@dataclass(frozen=True)
class FaceBox:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2.0


def _profile(mask: Image.Image, axis: str) -> list[float]:
    width, height = mask.size
    if axis == "row":
        strip = mask.resize((1, height), Image.Resampling.BOX)
        return [strip.getpixel((0, y)) / 255.0 for y in range(height)]
    strip = mask.resize((width, 1), Image.Resampling.BOX)
    return [strip.getpixel((x, 0)) / 255.0 for x in range(width)]


def _skin_mask(rgb: Image.Image) -> Image.Image:
    luma, blue_diff, red_diff = rgb.convert("YCbCr").split()
    mask = ImageChops.multiply(
        ImageChops.multiply(
            luma.point(lambda v: 255 if 60 <= v <= 250 else 0),
            blue_diff.point(lambda v: 255 if 77 <= v <= 130 else 0),
        ),
        red_diff.point(lambda v: 255 if 133 <= v <= 176 else 0),
    )
    return mask.point(lambda v: 255 if v > 127 else 0)


def _runs(profile: list[float], threshold: float) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(profile):
        if value >= threshold and start is None:
            start = index
        elif value < threshold and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(profile)))
    return runs


def _merge_runs(runs: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    """Spectacle frames, hair shadow and beards punch small holes in a skin run."""
    if not runs:
        return runs
    merged = [list(runs[0])]
    for start, end in runs[1:]:
        if start - merged[-1][1] <= max_gap:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def detect_face_box(human: Image.Image, search_top_ratio: float = 0.62) -> FaceBox | None:
    """Locate the wearer's face box, or return None when it is not confident."""
    rgb = human.convert("RGB")
    width, height = rgb.size
    search_height = max(1, int(height * search_top_ratio))
    mask = _skin_mask(rgb.crop((0, 0, width, search_height)))

    rows = _profile(mask, "row")
    row_peak = max(rows, default=0.0)
    if row_peak <= 0.01:
        return None
    row_runs = _merge_runs(
        _runs(rows, max(0.02, row_peak * 0.30)), max(4, int(search_height * 0.06))
    )
    if not row_runs:
        return None
    # The face carries far more skin mass than a bare hand or forearm.
    top, bottom = max(row_runs, key=lambda run: sum(rows[run[0]:run[1]]))

    cols = _profile(mask.crop((0, top, width, bottom)), "col")
    col_peak = max(cols, default=0.0)
    if col_peak <= 0.01:
        return None
    col_runs = _merge_runs(
        _runs(cols, max(0.02, col_peak * 0.30)), max(3, int(width * 0.02))
    )
    if not col_runs:
        return None
    left, right = max(col_runs, key=lambda run: sum(cols[run[0]:run[1]]))

    face_width = right - left
    if not (_MIN_FACE_WIDTH_RATIO * width <= face_width <= _MAX_FACE_WIDTH_RATIO * width):
        return None
    return FaceBox(left, top, right, bottom)


def resolve_anchor(
    human: Image.Image,
    ppe_category: str,
    ppe_aspect: float,
) -> dict[str, Any] | None:
    """Return pixel placement for a PPE foreground, or None to keep the ratio fallback.

    ``ppe_aspect`` is the alpha-cropped foreground height / width.
    """
    if ppe_category not in {"helmet", "vest"}:
        return None
    face = detect_face_box(human)
    if face is None:
        return None

    face_width = float(face.width)
    hairline_y = float(face.y0)
    head_width = face_width * _HEAD_WIDTH_PER_FACE_WIDTH
    head_height = face_width * _HEAD_HEIGHT_PER_FACE_WIDTH
    crown_y = hairline_y - _HAIRLINE_TO_CROWN_PER_HEAD_H * head_height
    shoulder_y = hairline_y + _SHOULDER_DROP_PER_FACE_WIDTH * face_width
    shoulder_width = face_width * _SHOULDER_WIDTH_PER_FACE_WIDTH

    if ppe_category == "helmet":
        target_width = head_width * _HELMET_WIDTH_PER_HEAD_WIDTH
        target_height = target_width * ppe_aspect
        # Rest the front brim on the brow line so the shell always overlaps the
        # skull: no floating gap, no second hat above the hair.
        bottom = hairline_y + _HELMET_BROW_PER_FACE_WIDTH * face_width
        top = bottom - target_height
        anchor = "head_crown"
    else:
        target_width = shoulder_width * _VEST_WIDTH_PER_SHOULDER_WIDTH
        target_height = target_width * ppe_aspect
        top = shoulder_y + _VEST_TOP_DROP_PER_FACE_WIDTH * face_width
        anchor = "shoulder_torso"

    return {
        "anchor": anchor,
        "ppe_category": ppe_category,
        "target_width": int(round(target_width)),
        "target_height": int(round(target_height)),
        "paste_x": int(round(face.center_x - target_width / 2.0)),
        "paste_y": int(round(top)),
        "face_box": asdict(face),
        "face_width": round(face_width, 2),
        "head_width": round(head_width, 2),
        "head_height": round(head_height, 2),
        "hairline_y": round(hairline_y, 2),
        "crown_y": round(crown_y, 2),
        "shoulder_y": round(shoulder_y, 2),
        "shoulder_width": round(shoulder_width, 2),
    }
