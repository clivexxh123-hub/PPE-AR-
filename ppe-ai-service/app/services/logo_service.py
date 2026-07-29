from pathlib import Path

from PIL import Image

from app.core.config import ensure_storage_dirs, settings


def normalize_logo(task_id: str, logo_path: Path | None, output_format: str = "png") -> tuple[Path, Path]:
    ensure_storage_dirs()
    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    ext = output_format.lower().lstrip(".") or "png"
    image_path = output_dir / f"logo_normalized.{ext}"
    metadata_path = output_dir / "metadata.json"

    if logo_path and logo_path.exists():
        image = Image.open(logo_path).convert("RGBA")
    else:
        image = Image.new("RGBA", (512, 512), (255, 255, 255, 0))

    image.thumbnail((512, 512))
    canvas = Image.new("RGBA", (512, 512), (255, 255, 255, 0))
    canvas.alpha_composite(image, ((512 - image.width) // 2, (512 - image.height) // 2))
    canvas.save(image_path)
    metadata_path.write_text(
        '{\n  "engine": "logo-placeholder",\n  "note": "当前还没有接入真实 Logo 抠图模型。"\n}\n',
        encoding="utf-8",
    )
    return image_path, metadata_path

