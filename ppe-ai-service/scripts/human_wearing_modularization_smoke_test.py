"""Deterministic behaviour checks for the human-wearing module boundaries."""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.human_anchor_service import resolve_ppe_placements  # noqa: E402
from app.services.human_wearing_categories import render_category_layer  # noqa: E402
from app.services.human_wearing_service import render_human_wearing_design  # noqa: E402
from app.services.ppe_blend_service import build_contact_mask  # noqa: E402
from app.services.human_wearing_preservation import lock_unmasked_regions  # noqa: E402


def _anchors() -> dict:
    return {
        "view": "front", "framing": "full_body", "face_box": {"x0": 180, "y0": 80, "x1": 280, "y1": 200},
        "face_width": 100.0, "head_width": 138.0, "head_height": 154.0, "head_top_y": 45,
        "hairline_y": 80, "eye_line_y": 137, "shoulder_y": 232, "shoulder_left": 132,
        "shoulder_right": 334, "shoulder_width": 202, "hands_visible": True, "feet_visible": True,
        "hands": [{"x0": 82, "y0": 310, "x1": 124, "y1": 402}, {"x0": 350, "y0": 310, "x1": 394, "y1": 402}],
        "feet": [{"x0": 162, "y0": 650, "x1": 232, "y1": 740}, {"x0": 272, "y0": 650, "x1": 344, "y1": 740}],
    }


def _sha(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def main() -> None:
    anchors = _anchors()
    helmet = resolve_ppe_placements(anchors, "helmet", 0.74)[0]
    assert (helmet["role"], helmet["width"], helmet["height"], helmet["center_x"], helmet["rotation"]) == (
        "head", 149, 110, 230.0, 0.0
    )
    assert helmet["helmet_geometry_profile"] == "helmet_front_contact_v1"
    vest = resolve_ppe_placements(anchors, "vest", 1.32)[0]
    assert (vest["role"], vest["width"], vest["height"], vest["center_x"], vest["rotation"]) == (
        "torso", 210, 277, 233.0, 0.0
    )
    gloves = resolve_ppe_placements(anchors, "gloves", 1.55)
    assert [(item["role"], item["width"], item["height"], item["rotation"], item["mirror"]) for item in gloves] == [
        ("left_hand", 70, 109, -8.0, False), ("right_hand", 70, 109, 8.0, True)
    ]

    source = Image.new("RGBA", (53, 71), (0, 0, 0, 0))
    ImageDraw.Draw(source).rectangle((4, 3, 48, 67), fill=(230, 96, 20, 220))
    assert _sha(render_category_layer("vest", source, 117, 155, "slight_side")) == "7ce63c7cba9830bd2bafa45731d78c81e0a048a2cd62bf782d006d38999cdfef"
    assert _sha(render_category_layer("helmet", source, 117, 155, "front")) == "cf74f3048c11bf57b3b21a26df308eedeb310199c1c055250c47bfc07f78f0d8"

    product_alpha = Image.new("L", (512, 768), 0)
    ImageDraw.Draw(product_alpha).rounded_rectangle((186, 45, 326, 145), radius=12, fill=255)
    placement = {"rendered_x": 186, "rendered_y": 45, "rendered_width": 140, "rendered_height": 100}
    mask, metadata = build_contact_mask(product_alpha, "helmet", [placement], anchors)
    assert metadata["helmet_mask_mode"] == "brim_hairline_contact_band"
    assert mask.getpixel((256, 75)) < 8
    assert metadata["mask_coverage_ratio"] > 0
    for category in ("vest", "gloves"):
        category_mask, category_metadata = build_contact_mask(product_alpha, category, [placement], anchors)
        assert category_mask.size == product_alpha.size
        assert category_metadata["ppe_category"] == category
        assert category_metadata["mask_coverage_ratio"] > 0
    assert render_human_wearing_design.__name__ == "render_human_wearing_design"

    with tempfile.TemporaryDirectory(prefix="human-wearing-modular-") as raw:
        root = Path(raw)
        original = Image.new("RGB", (12, 12), (20, 40, 60))
        generated = original.copy()
        generated.putpixel((6, 6), (220, 100, 20))
        original_path, generated_path, mask_path = root / "original.png", root / "generated.png", root / "mask.png"
        original.save(original_path)
        generated.save(generated_path)
        mask = Image.new("L", (12, 12), 0)
        mask.putpixel((6, 6), 255)
        mask.save(mask_path)
        result = lock_unmasked_regions(generated_path, original_path, mask_path)
        raw_output_path = Path(result["raw_output_path"])
        assert raw_output_path.exists()
        with Image.open(raw_output_path) as raw_output:
            assert raw_output.convert("RGB").getpixel((6, 6)) == (220, 100, 20)
        with Image.open(generated_path) as final:
            assert final.convert("RGB").getpixel((6, 6)) == (220, 100, 20)
            assert final.convert("RGB").getpixel((0, 0)) == (20, 40, 60)
        assert result["unmasked_mismatch_pixels"] == 0
        assert result["final_output_path"] == str(generated_path)

    print("HUMAN_WEARING_MODULARIZATION_SMOKE_OK")


if __name__ == "__main__":
    main()
