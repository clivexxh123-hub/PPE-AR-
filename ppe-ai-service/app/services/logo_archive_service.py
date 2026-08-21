"""Content-addressed local archive for Logo inputs and normalized PNG outputs."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.core.config import settings


@dataclass(frozen=True)
class LogoArchiveAsset:
    asset_id: str
    sha256: str
    asset_types: tuple[str, ...]
    archive_path: str
    metadata_path: str
    file_format: str | None
    width: int | None
    height: int | None
    byte_size: int

    def metadata(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "sha256": self.sha256,
            "asset_types": list(self.asset_types),
            "archive_path": self.archive_path,
            "archive_metadata_path": self.metadata_path,
            "file_format": self.file_format,
            "width": self.width,
            "height": self.height,
            "byte_size": self.byte_size,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_details(path: Path) -> tuple[str | None, int | None, int | None]:
    try:
        with Image.open(path) as image:
            return image.format, image.width, image.height
    except OSError:
        return None, None, None


def archive_logo_asset(path: Path, asset_type: str) -> LogoArchiveAsset:
    """Archive a Logo by its content hash and record the supplied semantic type."""
    if not path.exists() or not path.is_file():
        raise ValueError(f"Logo asset does not exist: {path}")
    normalized_type = asset_type.strip()
    if not normalized_type:
        raise ValueError("Logo asset type cannot be blank.")

    digest = _sha256(path)
    archive_dir = settings.storage_dir / "logo_archive" / digest[:2] / digest
    archive_path = archive_dir / "asset.bin"
    metadata_path = archive_dir / "metadata.json"
    archive_dir.mkdir(parents=True, exist_ok=True)
    if not archive_path.exists():
        shutil.copyfile(path, archive_path)

    existing: dict[str, object] = {}
    if metadata_path.exists():
        try:
            existing = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    prior_types = existing.get("asset_types", [])
    asset_types = tuple(sorted({*(prior_types if isinstance(prior_types, list) else []), normalized_type}))
    file_format, width, height = _image_details(path)
    payload = {
        "asset_id": f"logo-sha256:{digest}",
        "sha256": digest,
        "asset_types": list(asset_types),
        "archive_path": str(archive_path),
        "file_format": file_format,
        "width": width,
        "height": height,
        "byte_size": path.stat().st_size,
    }
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return LogoArchiveAsset(
        asset_id=str(payload["asset_id"]),
        sha256=digest,
        asset_types=asset_types,
        archive_path=str(archive_path),
        metadata_path=str(metadata_path),
        file_format=file_format,
        width=width,
        height=height,
        byte_size=path.stat().st_size,
    )
