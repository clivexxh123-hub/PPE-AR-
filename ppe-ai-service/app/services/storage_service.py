from pathlib import Path

from pydantic import BaseModel

from app.core.config import settings


class StorageUploadError(RuntimeError):
    """结果存储上传失败。"""


class StorageUploadResult(BaseModel):
    assetKey: str
    storage_backend: str
    uploaded: bool
    pending: bool
    local_path: str | None = None
    local_url: str | None = None
    error: str | None = None


def upload_result(local_path: Path, asset_key: str, local_url: str | None = None) -> StorageUploadResult:
    if not local_path.exists():
        raise StorageUploadError(f"结果文件不存在：{local_path}")

    backend = settings.storage_backend
    if backend in {"local", "mock"}:
        return StorageUploadResult(
            assetKey=asset_key,
            storage_backend="local",
            uploaded=False,
            pending=True,
            local_path=str(local_path),
            local_url=local_url,
        )

    if backend == "oss":
        raise StorageUploadError("OSS storage backend is not implemented yet.")

    raise StorageUploadError(f"不支持的 STORAGE_BACKEND：{backend}")
