import shutil
import uuid
from pathlib import Path

import httpx
from fastapi import UploadFile

from app.core.config import ensure_storage_dirs, settings
from app.schemas.tasks import ImageSource


async def save_upload(file: UploadFile) -> str:
    ensure_storage_dirs()
    suffix = Path(file.filename or "").suffix.lower() or ".bin"
    file_id = f"{uuid.uuid4().hex}{suffix}"
    target = settings.input_dir / file_id
    with target.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            output.write(chunk)
    return file_id


async def resolve_image_source(source: ImageSource | None) -> Path | None:
    if source is None:
        return None
    ensure_storage_dirs()
    if source.file_id:
        return settings.input_dir / source.file_id
    if source.local_path:
        return Path(source.local_path)
    if source.url:
        response = await httpx.AsyncClient().get(str(source.url), timeout=30)
        response.raise_for_status()
        suffix = Path(str(source.url.path)).suffix.lower() or ".img"
        file_id = f"{uuid.uuid4().hex}{suffix}"
        target = settings.input_dir / file_id
        target.write_bytes(response.content)
        return target
    return None


def copy_if_exists(source: Path | None, target: Path) -> str | None:
    if source is None or not source.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return str(target)
