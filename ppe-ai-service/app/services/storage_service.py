from pathlib import Path

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.schemas.business_protocol import TaskOutputSpec


class StorageUploadError(RuntimeError):
    """结果存储上传失败。"""


class StorageInputError(ValueError):
    """结果上传输入参数或本地文件不合法。"""


class StorageRetryableUploadError(StorageUploadError):
    """结果上传遇到可重试的网络或远端服务错误。"""


class StorageUploadResult(BaseModel):
    assetKey: str
    storage_backend: str
    uploaded: bool
    pending: bool
    local_path: str | None = None
    local_url: str | None = None
    method: str | None = None
    required_headers: dict[str, str] | None = None
    upload_url_present: bool = False
    expiresAt: str | None = None
    status_code: int | None = None
    error: str | None = None


def _normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {str(key): str(value) for key, value in headers.items()}


def _status_is_retryable(status_code: int) -> bool:
    return status_code == 403 or status_code == 429 or status_code >= 500


async def upload_result(
    local_path: Path,
    asset_key: str,
    local_url: str | None = None,
    output: TaskOutputSpec | None = None,
) -> StorageUploadResult:
    if not local_path.exists():
        raise StorageInputError(f"结果文件不存在：{local_path}")
    if not local_path.is_file():
        raise StorageInputError(f"结果路径不是文件：{local_path}")

    if output is not None:
        if output.method != "PUT":
            raise StorageInputError(f"不支持的上传方法：{output.method}")
        headers = _normalize_headers(output.requiredHeaders)
        try:
            file_bytes = local_path.read_bytes()
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.put(str(output.uploadUrl), content=file_bytes, headers=headers)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            raise StorageRetryableUploadError(f"OSS 预签名上传网络异常：{exc}") from exc
        except httpx.HTTPError as exc:
            raise StorageRetryableUploadError(f"OSS 预签名上传异常：{exc}") from exc

        if not response.is_success:
            message = f"OSS 预签名上传失败，HTTP {response.status_code}: {response.text[:300]}"
            if _status_is_retryable(response.status_code):
                raise StorageRetryableUploadError(message)
            raise StorageInputError(message)

        return StorageUploadResult(
            assetKey=output.assetKey,
            storage_backend="presigned_put",
            uploaded=True,
            pending=False,
            local_path=str(local_path),
            local_url=local_url,
            method=output.method,
            required_headers=headers,
            upload_url_present=True,
            expiresAt=output.expiresAt,
            status_code=response.status_code,
        )

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
        raise StorageRetryableUploadError(
            "OSS storage backend is not implemented. Use GenerationTaskInput.output.uploadUrl for presigned PUT upload."
        )

    raise StorageInputError(f"不支持的 STORAGE_BACKEND：{backend}")

