"""Regression coverage for the first helmet contact-only refinement pass."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402
from app.services.comfyui_engine import (  # noqa: E402
    _load_workflow,
    _lock_human_wearing_unmasked_regions,
    _patch_workflow,
)
from app.services.human_anchor_service import resolve_ppe_placements  # noqa: E402
from app.services.ppe_blend_service import build_contact_mask  # noqa: E402


def _anchors(view: str) -> dict:
    return {
        "view": view,
        "framing": "half_body",
        "face_box": {"x0": 200, "y0": 140, "x1": 300, "y1": 340},
        "face_width": 100.0,
        "head_width": 132.0,
        "head_height": 154.0,
        "head_top_y": 120,
        "hairline_y": 140,
        "eye_line_y": 197,
    }


def _seed_values(workflow: dict) -> list[int]:
    return [
        node["inputs"]["seed"]
        for node in workflow.values()
        if isinstance(node, dict) and isinstance(node.get("inputs"), dict) and "seed" in node["inputs"]
    ]


def main() -> None:
    front = resolve_ppe_placements(_anchors("front"), "helmet", 0.9)[0]
    slight = resolve_ppe_placements(_anchors("slight_side"), "helmet", 0.78)[0]
    assert front["helmet_geometry_profile"] == "helmet_front_contact_v1"
    assert slight["helmet_geometry_profile"] == "helmet_slight_side_contact_v1"
    assert front["width"] > slight["width"], (front, slight)
    assert front["brim_y"] < front["eye_line_y"]
    assert front["center_y"] + front["height"] / 2 == front["brim_y"]
    assert slight["rotation"] < 0

    alpha = Image.new("L", (512, 768), 0)
    ImageDraw.Draw(alpha).rounded_rectangle((185, 42, 335, 177), radius=24, fill=255)
    placement = {
        "rendered_x": 185,
        "rendered_y": 42,
        "rendered_width": 150,
        "rendered_height": 135,
    }
    mask, metadata = build_contact_mask(alpha, "helmet", [placement], _anchors("front"))
    assert metadata["helmet_mask_mode"] == "brim_hairline_contact_band"
    assert 0 < metadata["mask_coverage_ratio"] < 0.02, metadata
    assert metadata["mask_bbox"] is not None
    # Dome and eyes are locked; the lower brim remains refinable.
    assert mask.getpixel((260, 82)) < 8
    assert mask.getpixel((260, 197)) < 8
    assert mask.getpixel((260, 169)) > 80

    workflow = _patch_workflow(
        _load_workflow(settings.comfyui_human_wearing_workflow_path),
        "helmet-seed-smoke",
        "positive",
        "512x768",
        "image_to_image",
        "input.png",
        "mask.png",
        denoise=0.24,
        seed=20260830,
    )
    assert _seed_values(workflow) == [20260830]

    with tempfile.TemporaryDirectory(prefix="helmet-contact-lock-") as raw:
        root = Path(raw)
        original, generated, mask_path = root / "input.png", root / "result.png", root / "mask.png"
        Image.new("RGB", (8, 8), (10, 20, 30)).save(original)
        Image.new("RGB", (8, 8), (230, 40, 50)).save(generated)
        lock_mask = Image.new("L", (8, 8), 0)
        lock_mask.paste(255, (3, 3, 5, 5))
        lock_mask.save(mask_path)
        lock_metadata = _lock_human_wearing_unmasked_regions(generated, original, mask_path)
        with Image.open(generated) as image:
            assert image.convert("RGB").getpixel((0, 0)) == (10, 20, 30)
            assert image.convert("RGB").getpixel((3, 3)) == (230, 40, 50)
        assert lock_metadata["unmasked_mismatch_pixels"] == 0

    print("HELMET_CONTACT_REFINEMENT_SMOKE_OK")


if __name__ == "__main__":
    main()
