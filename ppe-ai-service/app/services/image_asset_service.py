import uuid
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

from app.core.config import ensure_storage_dirs, settings
from app.schemas.tasks import GenerateRequest, ImageSource

MAX_IMAGE_BYTES = 25 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "BMP"}


class ImageAssetValidationError(ValueError):
    def __init__(self, message: str, validation_result: dict[str, Any] | None = None):
        super().__init__(message)
        self.validation_result = validation_result or {}


def validate_alpha_channel(path: Path, role: str) -> dict[str, Any]:
    """Require a real transparent region for PPE reference compositing."""
    try:
        with Image.open(path) as image:
            if "A" not in image.getbands() and "transparency" not in image.info:
                raise ImageAssetValidationError(
                    f"{role} 图片必须包含 alpha 透明通道。",
                    {"validation_status": "failed", "has_alpha": False, "error": "alpha channel is missing"},
                )
            alpha_min, alpha_max = image.convert("RGBA").getchannel("A").getextrema()
    except ImageAssetValidationError:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageAssetValidationError(
            f"{role} 图片无法读取 alpha 通道：{exc}",
            {"validation_status": "failed", "has_alpha": False, "error": str(exc)},
        ) from exc
    if alpha_min >= 255:
        raise ImageAssetValidationError(
            f"{role} 图片没有透明区域。",
            {"validation_status": "failed", "has_alpha": True, "alpha_min": alpha_min, "alpha_max": alpha_max, "error": "alpha channel has no transparent pixels"},
        )
    return {"validation_status": "passed", "has_alpha": True, "alpha_min": alpha_min, "alpha_max": alpha_max}


async def validate_generate_request_images(payload: GenerateRequest) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if payload.product_image is not None:
        try:
            result["product_image"] = await validate_image_source(payload.product_image, "product_reference")
        except ImageAssetValidationError as exc:
            raise ImageAssetValidationError(str(exc), {"product_image": exc.validation_result}) from exc
    if payload.logo_image is not None:
        try:
            result["logo_image"] = await validate_image_source(payload.logo_image, "logo")
        except ImageAssetValidationError as exc:
            raise ImageAssetValidationError(str(exc), {"logo_image": exc.validation_result}) from exc
    return result


async def validate_image_source(source: ImageSource, role: str) -> dict[str, Any]:
    local_path, source_type, original_url, content_type = await _resolve_for_validation(source, role)
    return _validate_local_image(local_path, role, source_type, original_url, content_type)


async def _resolve_for_validation(source: ImageSource, role: str) -> tuple[Path, str, str | None, str | None]:
    ensure_storage_dirs()
    if source.file_id:
        return settings.input_dir / source.file_id, "file_id", None, None
    if source.local_path:
        return Path(source.local_path), "local_path", None, None
    if source.url:
        return await _download_image_url(str(source.url), role)
    raise ImageAssetValidationError(
        f"{role} 图片来源为空。",
        _failed_result(role=role, source_type="unknown", error="image source is empty"),
    )


async def _download_image_url(url: str, role: str) -> tuple[Path, str, str | None, str | None]:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        raise ImageAssetValidationError(
            f"{role} 图片下载失败：{exc}",
            _failed_result(role=role, source_type="url", original_url=url, error=str(exc)),
        ) from exc

    if response.status_code >= 400:
        raise ImageAssetValidationError(
            f"{role} 图片 URL 返回 HTTP {response.status_code}。",
            _failed_result(
                role=role,
                source_type="url",
                original_url=url,
                content_type=response.headers.get("content-type"),
                error=f"http_status={response.status_code}",
            ),
        )

    content_type = response.headers.get("content-type")
    if content_type and not content_type.lower().startswith("image/"):
        raise ImageAssetValidationError(
            f"{role} URL 返回内容不是图片：{content_type}。",
            _failed_result(
                role=role,
                source_type="url",
                original_url=url,
                content_type=content_type,
                error="content-type is not image/*",
            ),
        )

    content = response.content
    if not content:
        raise ImageAssetValidationError(
            f"{role} 图片内容为空。",
            _failed_result(role=role, source_type="url", original_url=url, content_type=content_type, error="empty body"),
        )
    if len(content) > MAX_IMAGE_BYTES:
        raise ImageAssetValidationError(
            f"{role} 图片过大，超过 {MAX_IMAGE_BYTES} bytes。",
            _failed_result(
                role=role,
                source_type="url",
                original_url=url,
                content_type=content_type,
                file_size_bytes=len(content),
                error="image too large",
            ),
        )

    suffix = Path(httpx.URL(url).path).suffix.lower() or ".img"
    target = settings.input_dir / f"{uuid.uuid4().hex}{suffix}"
    target.write_bytes(content)
    return target, "url", url, content_type


def _validate_local_image(
    path: Path,
    role: str,
    source_type: str,
    original_url: str | None,
    content_type: str | None,
) -> dict[str, Any]:
    base = {
        "role": role,
        "source_type": source_type,
        "original_url": original_url,
        "local_path": str(path),
        "content_type": content_type,
    }
    if not path.exists():
        result = {**base, "validation_status": "failed", "error": "local file does not exist"}
        raise ImageAssetValidationError(f"{role} 图片文件不存在：{path}", result)

    file_size = path.stat().st_size
    if file_size <= 0:
        result = {**base, "file_size_bytes": file_size, "validation_status": "failed", "error": "empty file"}
        raise ImageAssetValidationError(f"{role} 图片文件为空：{path}", result)
    if file_size > MAX_IMAGE_BYTES:
        result = {**base, "file_size_bytes": file_size, "validation_status": "failed", "error": "image too large"}
        raise ImageAssetValidationError(f"{role} 图片过大，超过 {MAX_IMAGE_BYTES} bytes。", result)

    try:
        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format or "UNKNOWN"
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        result = {**base, "file_size_bytes": file_size, "validation_status": "failed", "error": str(exc)}
        raise ImageAssetValidationError(f"{role} 文件不是有效图片：{exc}", result) from exc

    if image_format not in ALLOWED_IMAGE_FORMATS:
        result = {
            **base,
            "width": width,
            "height": height,
            "format": image_format.lower(),
            "file_size_bytes": file_size,
            "validation_status": "failed",
            "error": "unsupported image format",
        }
        raise ImageAssetValidationError(f"{role} 图片格式暂不支持：{image_format}", result)

    return {
        **base,
        "width": width,
        "height": height,
        "format": image_format.lower(),
        "file_size_bytes": file_size,
        "validation_status": "passed",
    }


def _failed_result(
    role: str,
    source_type: str,
    original_url: str | None = None,
    content_type: str | None = None,
    file_size_bytes: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "role": role,
        "source_type": source_type,
        "original_url": original_url,
        "content_type": content_type,
        "validation_status": "failed",
        "error": error,
    }
    if file_size_bytes is not None:
        result["file_size_bytes"] = file_size_bytes
    return result

