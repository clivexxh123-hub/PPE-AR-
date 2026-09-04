"""Deterministic VEST-GEO-01 coverage for the torso four-point pre-composite."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.human_wearing_categories import (  # noqa: E402
    render_category_layer,
    resolve_ppe_placements,
    warp_vest_rows,
)


def _anchors() -> dict:
    subject_mask = Image.new("L", (512, 768), 0)
    ImageDraw.Draw(subject_mask).polygon(((150, 230), (362, 230), (330, 610), (182, 610)), fill=255)
    return {
        "view": "front", "framing": "half_body",
        "face_box": {"x0": 206, "y0": 82, "x1": 306, "y1": 202},
        "face_width": 100.0, "head_width": 132.0, "head_height": 154.0,
        "head_top_y": 52, "hairline_y": 82, "eye_line_y": 139,
        "shoulder_y": 236, "shoulder_left": 154, "shoulder_right": 358,
        "shoulder_width": 204, "subject_box": {"x0": 150, "y0": 52, "x1": 362, "y1": 610},
        "hands": [], "feet": [], "hands_visible": False, "feet_visible": False,
        "subject_mask": subject_mask,
    }


def main() -> None:
    anchors = _anchors()
    placement = resolve_ppe_placements(anchors, "vest", 1.25)[0]
    assert placement["width"] == 212
    assert placement["height"] == 265
    quad = placement["torso_quad"]
    assert quad[0] == [154.0, 236.0]
    assert quad[1] == [358.0, 236.0]
    assert quad[2][1] == quad[3][1] == 469.0
    assert quad[3][0] < quad[2][0]

    source = Image.new("RGBA", (120, 180), (0, 0, 0, 0))
    draw = ImageDraw.Draw(source)
    draw.polygon(((20, 5), (45, 5), (60, 42), (75, 5), (100, 5), (116, 175), (4, 175)), fill=(245, 126, 18, 255))
    draw.rectangle((4, 105, 116, 126), fill=(220, 220, 215, 255))
    baseline = warp_vest_rows(source, placement["width"], placement["height"], "front")
    candidate = render_category_layer("vest", source, placement["width"], placement["height"], "front", placement)
    assert candidate.size == baseline.size
    assert candidate.getchannel("A").getbbox() is not None
    assert candidate.tobytes() != baseline.tobytes(), "Candidate must exercise the torso-quad path."
    assert render_category_layer("helmet", source, 99, 111, "front", None).size == (99, 111)
    print("VEST_TORSO_GEOMETRY_SMOKE_OK")


if __name__ == "__main__":
    main()
