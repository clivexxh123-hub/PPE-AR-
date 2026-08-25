"""Verify all four helmet print profiles use product-relative printable regions."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.api.routes import _helmet_view_placement_defaults
from app.services.logo_service import render_printed_design
from app.services.logo_template_store import resolve_logo_placement, save_logo_template


def _render(task_id: str, base_path: Path, logo_path: Path, **kwargs: object) -> dict:
    image_path, metadata_path = render_printed_design(task_id, base_path, logo_path, **kwargs)
    visual_output = os.environ.get("PPE_VISUAL_OUTPUT_DIR")
    if visual_output:
        target_dir = Path(visual_output)
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(image_path, target_dir / f"helmet_{task_id}.png")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _assert_print_center(metadata: dict, expected_profile: str) -> None:
    bounds = metadata["printable_region_bounds"]
    product_bounds = metadata["product_bounds"]
    center_x = metadata["position_x"] + metadata["logo_width"] / 2
    printable_center_x = (bounds["left"] + bounds["right"]) / 2
    assert metadata["placement_mode"] == "helmet-view-profile"
    assert metadata["placement_profile"] == expected_profile
    assert abs(center_x - printable_center_x) <= 0.5
    assert bounds["top"] < metadata["position_y"]
    assert metadata["position_y"] + metadata["logo_height"] < bounds["bottom"]
    assert bounds["left"] < metadata["position_x"]
    assert metadata["position_x"] + metadata["logo_width"] < bounds["right"]
    assert product_bounds["left"] <= bounds["left"] < bounds["right"] <= product_bounds["right"]
    assert product_bounds["top"] <= bounds["top"] < bounds["bottom"] <= product_bounds["bottom"]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ppe-helmet-print-centering-") as temp_dir:
        root = Path(temp_dir)
        inputs = root / "inputs"
        inputs.mkdir(parents=True)
        base_path = inputs / "off-center-helmet.png"
        logo_path = inputs / "transparent-text.png"

        # Synthetic fixture: the helmet is intentionally offset from the canvas
        # center, so a canvas ratio of 0.5 would fail this check.
        base = Image.new("RGBA", (320, 190), (255, 255, 255, 255))
        ImageDraw.Draw(base).rounded_rectangle((78, 26, 260, 146), radius=30, fill=(247, 194, 40, 255))
        base.save(base_path)
        logo = Image.new("RGBA", (96, 30), (0, 0, 0, 0))
        ImageDraw.Draw(logo).rounded_rectangle((1, 1, 94, 28), radius=4, fill=(20, 40, 80, 255))
        logo.save(logo_path)

        original_output_dir = settings.output_dir
        original_storage_dir = settings.storage_dir
        settings.output_dir = root / "outputs"
        settings.storage_dir = root / "storage"
        try:
            front = _render("front", base_path, logo_path, position="front")
            _assert_print_center(front, "helmet_front_print_center")

            back = _render("back", base_path, logo_path, position="back")
            _assert_print_center(back, "helmet_back_print_center")
            left = _render("left", base_path, logo_path, position="left")
            _assert_print_center(left, "helmet_left_print_center")
            right = _render("right", base_path, logo_path, position="right")
            _assert_print_center(right, "helmet_right_print_center")
            assert _helmet_view_placement_defaults({"product_view": "正面"}) == {"position": "front"}
            assert _helmet_view_placement_defaults({"view_type": "back"}) == {"position": "back"}
            assert _helmet_view_placement_defaults({"view": "left"}) == {"position": "left"}
            assert _helmet_view_placement_defaults({"product_view": "右侧"}) == {"position": "right"}

            manual = _render(
                "manual-overrides-profile",
                base_path,
                logo_path,
                position="front",
                position_x_ratio=0.10,
                position_y_ratio=0.75,
                logo_width_ratio=0.20,
                opacity=0.55,
            )
            assert manual["placement_mode"] == "manual"
            assert manual["placement_profile"] == "helmet_front_print_center"
            assert abs(manual["final_x_ratio"] - 0.10) < 0.02
            assert abs(manual["final_y_ratio"] - 0.75) < 0.02
            assert abs(manual["final_width_ratio"] - 0.20) < 0.01
            assert manual["opacity"] == 0.55

            side = _render("side-regression", base_path, logo_path, position="top-right")
            assert side["placement_mode"] == "manual"
            assert side["placement_profile"] is None
            assert side["position_x"] + side["logo_width"] < 320
            assert side["position_y"] < 20

            save_logo_template("helmet-corner", {"position": "top-left"})
            template_over_view = resolve_logo_placement(
                "helmet-corner",
                default_placement={"position": "front"},
            )
            assert template_over_view.render_kwargs()["position"] == "top-left"
            manual_over_template = resolve_logo_placement(
                "helmet-corner",
                {"position": "back"},
                {"position": "front"},
            )
            assert manual_over_template.render_kwargs()["position"] == "back"
        finally:
            settings.output_dir = original_output_dir
            settings.storage_dir = original_storage_dir

    print("HELMET_PRINT_CENTERING_SMOKE_OK")


if __name__ == "__main__":
    main()
