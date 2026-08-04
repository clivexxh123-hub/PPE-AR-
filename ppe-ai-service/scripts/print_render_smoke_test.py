from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from app.core.config import settings
from app.services.logo_service import render_printed_design


OUTPUT_ROOT = Path(r"D:\Don't Click it\JOB\XVison\PPE_AI\output")
TEST_ROOT = OUTPUT_ROOT / "print_render_smoke"


def main() -> None:
    root = TEST_ROOT
    root.mkdir(parents=True, exist_ok=True)
    base_path = root / "inputs" / "base.png"
    logo_path = root / "inputs" / "logo.png"
    base_path.parent.mkdir(parents=True, exist_ok=True)
    logo_path.parent.mkdir(parents=True, exist_ok=True)

    base = Image.new("RGBA", (160, 100), (240, 240, 240, 255))
    ImageDraw.Draw(base).rectangle((10, 10, 150, 90), outline=(40, 80, 120, 255), width=3)
    base.save(base_path, format="PNG")

    logo = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    ImageDraw.Draw(logo).rectangle((0, 0, 39, 19), fill=(220, 30, 30, 255))
    logo.save(logo_path, format="PNG")

    original_output_dir = settings.output_dir
    settings.output_dir = root / "outputs"
    try:
        image_path, metadata_path = render_printed_design(
            "print-render-smoke",
            base_path,
            logo_path,
            position_x_ratio=0.5,
            position_y_ratio=0.5,
            logo_width_ratio=0.25,
            opacity=0.75,
        )
    finally:
        settings.output_dir = original_output_dir

    with Image.open(image_path) as result:
        assert result.format == "PNG"
        assert result.mode == "RGBA"
        assert result.size == (160, 100)
        assert result.getpixel((80, 50)) != (240, 240, 240, 255)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["engine"] == "pillow-alpha-composite"
    assert metadata["has_alpha"] is True
    print(f"PRINT_RENDER_SMOKE_OK image={image_path}")


if __name__ == "__main__":
    main()
