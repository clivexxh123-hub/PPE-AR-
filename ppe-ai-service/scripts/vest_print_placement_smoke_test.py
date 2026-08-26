"""Deterministic smoke coverage for five semantic vest print regions.

The generated fixtures are synthetic placement evidence, not commercial visual
acceptance assets.  Set PPE_VISUAL_OUTPUT_DIR to retain the rendered PNG files.
"""

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

from app.api.routes import _helmet_view_placement_defaults  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.services.logo_service import render_printed_design  # noqa: E402


REGIONS = {
    "front_left_chest": "vest_front_left_chest",
    "front_right_chest": "vest_front_right_chest",
    "back_upper": "vest_back_upper",
    "back_middle": "vest_back_middle",
    "back_lower": "vest_back_lower",
}


def _render(task_id: str, base_path: Path, logo_path: Path, **kwargs: object) -> tuple[Path, dict]:
    image_path, metadata_path = render_printed_design(task_id, base_path, logo_path, **kwargs)
    return image_path, json.loads(metadata_path.read_text(encoding="utf-8"))


def _assert_region(metadata: dict, expected_profile: str) -> None:
    region = metadata["printable_region_bounds"]
    product = metadata["product_bounds"]
    artwork_center_x = metadata["position_x"] + metadata["logo_width"] / 2
    artwork_center_y = metadata["position_y"] + metadata["logo_height"] / 2
    assert metadata["placement_mode"] == "vest-region-profile"
    assert metadata["placement_profile"] == expected_profile
    assert abs(artwork_center_x - (region["left"] + region["right"]) / 2) <= 0.5
    assert abs(artwork_center_y - (region["top"] + region["bottom"]) / 2) <= 0.5
    assert region["left"] <= metadata["position_x"]
    assert metadata["position_x"] + metadata["logo_width"] <= region["right"]
    assert region["top"] <= metadata["position_y"]
    assert metadata["position_y"] + metadata["logo_height"] <= region["bottom"]
    assert product["left"] <= region["left"] < region["right"] <= product["right"]
    assert product["top"] <= region["top"] < region["bottom"] <= product["bottom"]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ppe-vest-print-placement-") as temp_dir:
        root = Path(temp_dir)
        base_path = root / "synthetic-vest.png"
        logo_path = root / "synthetic-print.png"
        base = Image.new("RGBA", (360, 420), (255, 255, 255, 255))
        draw = ImageDraw.Draw(base)
        draw.polygon(
            ((95, 35), (150, 20), (180, 80), (210, 20), (265, 35), (310, 390), (50, 390)),
            fill=(232, 245, 45, 255),
            outline=(55, 65, 70, 255),
        )
        draw.rectangle((65, 105, 295, 135), fill=(190, 205, 210, 255))
        draw.rectangle((60, 305, 300, 340), fill=(190, 205, 210, 255))
        base.save(base_path)
        logo = Image.new("RGBA", (120, 34), (0, 0, 0, 0))
        ImageDraw.Draw(logo).rounded_rectangle((1, 1, 118, 32), radius=4, fill=(15, 35, 75, 255))
        logo.save(logo_path)

        original_output_dir = settings.output_dir
        original_storage_dir = settings.storage_dir
        settings.output_dir = root / "outputs"
        settings.storage_dir = root / "storage"
        rendered: dict[str, dict] = {}
        try:
            for region, expected_profile in REGIONS.items():
                image_path, metadata = _render(region, base_path, logo_path, position=region)
                _assert_region(metadata, expected_profile)
                rendered[region] = metadata
                assert _helmet_view_placement_defaults({"print_region": region}) == {"position": region}
                visual_output = os.environ.get("PPE_VISUAL_OUTPUT_DIR")
                if visual_output:
                    target_dir = Path(visual_output)
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(image_path, target_dir / f"vest_{region}.png")

            assert (
                rendered["front_left_chest"]["position_x"]
                > rendered["front_right_chest"]["position_x"]
            )
            assert rendered["back_upper"]["position_y"] < rendered["back_middle"]["position_y"]
            assert rendered["back_middle"]["position_y"] < rendered["back_lower"]["position_y"]

            _, manual = _render(
                "vest-manual-overrides",
                base_path,
                logo_path,
                position="back_middle",
                position_x_ratio=0.15,
                position_y_ratio=0.72,
                logo_width_ratio=0.18,
                opacity=0.60,
            )
            assert manual["placement_mode"] == "manual"
            assert manual["placement_profile"] == "vest_back_middle"
            assert abs(manual["final_x_ratio"] - 0.15) < 0.02
            assert abs(manual["final_y_ratio"] - 0.72) < 0.02
            assert abs(manual["final_width_ratio"] - 0.18) < 0.01
            assert manual["opacity"] == 0.60
        finally:
            settings.output_dir = original_output_dir
            settings.storage_dir = original_storage_dir

    print("VEST_PRINT_PLACEMENT_SMOKE_OK")


if __name__ == "__main__":
    main()
