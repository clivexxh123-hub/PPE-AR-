"""Check deterministic automatic Logo placement and manual overrides."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.services.logo_service import render_printed_design


def _render(root: Path, name: str, base_path: Path, logo_path: Path, **kwargs: object) -> dict:
    image_path, metadata_path = render_printed_design(name, base_path, logo_path, **kwargs)
    with Image.open(image_path) as image:
        assert image.format == "PNG"
        assert image.size == (200, 120)
        assert image.mode == "RGBA"
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ppe-logo-auto-placement-") as temp_dir:
        root = Path(temp_dir)
        inputs = root / "inputs"
        inputs.mkdir(parents=True)
        base_path = inputs / "helmet-base.png"
        logo_path = inputs / "transparent-logo.png"

        base = Image.new("RGBA", (200, 120), (255, 255, 255, 255))
        ImageDraw.Draw(base).rounded_rectangle((40, 20, 160, 100), radius=20, fill=(247, 194, 40, 255))
        base.save(base_path)
        logo = Image.new("RGBA", (80, 40), (0, 0, 0, 0))
        ImageDraw.Draw(logo).rounded_rectangle((2, 2, 77, 37), radius=6, fill=(30, 80, 200, 180))
        logo.save(logo_path)

        original_output_dir = settings.output_dir
        settings.output_dir = root / "outputs"
        try:
            automatic = _render(root, "auto", base_path, logo_path)
            assert automatic["placement_mode"] == "auto"
            assert 0 < automatic["final_x_ratio"] < 1
            assert 0 < automatic["final_y_ratio"] < 1
            assert 0.10 <= automatic["final_width_ratio"] <= 0.35
            assert automatic["logo_transparent_padding_trimmed"] is True
            assert automatic["logo_visible_bounds"] == [2, 2, 78, 38]
            visible_aspect = automatic["logo_visible_width"] / automatic["logo_visible_height"]
            rendered_aspect = automatic["logo_width"] / automatic["logo_height"]
            assert abs(rendered_aspect - visible_aspect) < 0.08
            assert 0 <= automatic["position_x"] <= 200 - automatic["logo_width"]
            assert 0 <= automatic["position_y"] <= 120 - automatic["logo_height"]

            manual_position = _render(
                root,
                "manual-position",
                base_path,
                logo_path,
                position_x_ratio=0.10,
                position_y_ratio=0.80,
            )
            assert manual_position["placement_mode"] == "manual"
            assert abs(manual_position["final_x_ratio"] - 0.10) < 0.02
            assert abs(manual_position["final_y_ratio"] - 0.80) < 0.02
            assert manual_position["final_width_ratio"] == automatic["final_width_ratio"]

            manual_width = _render(root, "manual-width", base_path, logo_path, logo_width_ratio=0.30)
            assert manual_width["placement_mode"] == "manual"
            assert abs(manual_width["final_width_ratio"] - 0.30) < 0.01

            manual_all = _render(
                root,
                "manual-all",
                base_path,
                logo_path,
                position="top-right",
                position_x_ratio=0.75,
                position_y_ratio=0.15,
                logo_width_ratio=0.20,
            )
            assert manual_all["placement_mode"] == "manual"
            assert abs(manual_all["final_x_ratio"] - 0.75) < 0.02
            assert abs(manual_all["final_y_ratio"] - 0.15) < 0.02
            assert abs(manual_all["final_width_ratio"] - 0.20) < 0.01

            bounded = _render(root, "bounded", base_path, logo_path, position="bottom-right", logo_width_ratio=0.90)
            assert bounded["position_x"] + bounded["logo_width"] < 200
            assert bounded["position_y"] + bounded["logo_height"] < 120
        finally:
            settings.output_dir = original_output_dir

    print("LOGO_AUTO_PLACEMENT_SMOKE_OK")


if __name__ == "__main__":
    main()
