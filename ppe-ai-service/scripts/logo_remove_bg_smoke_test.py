"""Minimal local verification for simple Logo background removal."""

import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.main import app
from app.services.logo_service import normalize_logo


def _expect_value_error(callback) -> None:
    try:
        callback()
    except ValueError:
        return
    raise AssertionError("Expected ValueError")


def _run(output_root: Path) -> None:
    original_output_dir = settings.output_dir
    original_task_dir = settings.task_dir
    settings.output_dir = output_root
    settings.task_dir = output_root / "tasks"
    try:
        inputs = output_root / "inputs"
        inputs.mkdir(parents=True, exist_ok=True)
        logo_path = inputs / "white_background_logo.jpg"
        transparent_logo_path = inputs / "transparent_logo.png"
        magenta_logo_path = inputs / "magenta_foreground_logo.png"
        invalid_path = inputs / "not_an_image.txt"

        logo = Image.new("RGB", (180, 120), "white")
        ImageDraw.Draw(logo).rounded_rectangle((35, 30, 145, 90), radius=12, fill="#0B67C2")
        logo.save(logo_path, format="JPEG")
        transparent_logo = Image.new("RGBA", (80, 40), (0, 0, 0, 0))
        ImageDraw.Draw(transparent_logo).ellipse((12, 6, 68, 34), fill="#EF4444")
        transparent_logo.save(transparent_logo_path, format="PNG")
        magenta_logo = Image.new("RGB", (80, 40), "white")
        ImageDraw.Draw(magenta_logo).rectangle((12, 6, 68, 34), fill=(255, 0, 255))
        magenta_logo.save(magenta_logo_path, format="PNG")
        invalid_path.write_text("not an image", encoding="utf-8")

        image_path, metadata_path = normalize_logo("simple-background", logo_path)
        with Image.open(image_path) as result:
            assert result.mode == "RGBA"
            assert result.getpixel((0, 0))[3] == 0
            assert result.getpixel((256, 256))[3] == 255

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["engine"] == "pillow-simple-background-removal"
        assert metadata["has_alpha"] is True
        assert metadata["background_method"] == "border_flood_fill"

        png_path, png_metadata_path = normalize_logo("transparent-input", transparent_logo_path)
        with Image.open(png_path) as result:
            assert result.mode == "RGBA"
            assert result.getpixel((0, 0))[3] == 0
            assert result.getpixel((256, 256))[3] == 255
        png_metadata = json.loads(png_metadata_path.read_text(encoding="utf-8"))
        assert png_metadata["background_method"] == "preserved_existing_alpha"

        magenta_path, _ = normalize_logo("magenta-foreground", magenta_logo_path)
        with Image.open(magenta_path) as result:
            assert result.getpixel((0, 0))[3] == 0
            assert result.getpixel((256, 256))[3] == 255

        _expect_value_error(lambda: normalize_logo("invalid-input", invalid_path))
        _expect_value_error(lambda: normalize_logo("missing-input", inputs / "missing.png"))

        with TestClient(app) as client:
            response = client.post(
                "/logo/remove-bg",
                json={"logo_image": {"local_path": str(logo_path)}, "sync": True},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["status"] == "succeeded"
            assert client.get(payload["result_url"]).status_code == 200
            route_metadata = client.get(payload["metadata_url"]).json()
            assert route_metadata["engine"] == "pillow-simple-background-removal"
        print("LOGO_REMOVE_BG_SMOKE_OK")
    finally:
        settings.output_dir = original_output_dir
        settings.task_dir = original_task_dir


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="ppe-logo-remove-bg-") as temp_dir:
        _run(Path(temp_dir))
