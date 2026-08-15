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


def main() -> None:
    temporary_output = tempfile.TemporaryDirectory(prefix="ppe-print-render-smoke-")
    root = Path(temporary_output.name)
    original_output_dir = settings.output_dir
    try:
        base_path = root / "inputs" / "base.png"
        logo_path = root / "inputs" / "logo.png"
        base_path.parent.mkdir(parents=True, exist_ok=True)

        base = Image.new("RGBA", (160, 100), (240, 240, 240, 255))
        ImageDraw.Draw(base).rectangle((10, 10, 150, 90), outline=(40, 80, 120, 255), width=3)
        base.save(base_path, format="PNG")

        logo = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
        ImageDraw.Draw(logo).rectangle((0, 0, 39, 19), fill=(220, 30, 30, 255))
        logo.save(logo_path, format="PNG")

        settings.output_dir = root / "outputs"
        image_path, metadata_path = render_printed_design(
            "print-render-smoke",
            base_path,
            logo_path,
            position_x_ratio=0.5,
            position_y_ratio=0.5,
            logo_width_ratio=0.25,
            opacity=0.75,
        )

        with Image.open(image_path) as result:
            assert result.format == "PNG"
            assert result.mode == "RGBA"
            assert result.size == (160, 100)
            assert result.getpixel((80, 50)) != (240, 240, 240, 255)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["engine"] == "pillow-alpha-composite"
        assert metadata["has_alpha"] is True
        print(f"PRINT_RENDER_SMOKE_OK image={image_path}")
    finally:
        settings.output_dir = original_output_dir
        temporary_output.cleanup()


if __name__ == "__main__":
    main()
