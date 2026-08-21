from __future__ import annotations

import asyncio
import io
import ipaddress
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.schemas.tasks import ImageSource
from app.services.error_codes import map_exception_to_error
from app.services.image_asset_service import (
    MAX_IMAGE_BYTES,
    ImageAssetValidationError,
    RetryableImageAssetError,
    _download_image_url,
    validate_image_source,
)


def _png_bytes() -> bytes:
    image = Image.new("RGBA", (2, 2), (255, 255, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class FakeAsyncClient:
    def __init__(self, *, redirect: bool = False, status_code: int = 200, **_: object) -> None:
        self.redirect = redirect
        self.status_code = status_code
        self.requests: list[str] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str) -> httpx.Response:
        self.requests.append(url)
        if self.redirect:
            return httpx.Response(302, headers={"location": "http://127.0.0.1/private.png"})
        return httpx.Response(self.status_code, headers={"content-type": "image/png"}, content=_png_bytes())


def _resolved_addresses(hostname: str, _: int | None) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return {ipaddress.ip_address(hostname)}
    except ValueError:
        return {ipaddress.ip_address("93.184.216.34")}


async def _run() -> None:
    original_storage_dir = settings.storage_dir
    original_input_dir = settings.input_dir
    original_output_dir = settings.output_dir
    original_task_dir = settings.task_dir
    try:
        with tempfile.TemporaryDirectory(prefix="ppe-image-url-security-") as temp_dir:
            root = Path(temp_dir)
            settings.storage_dir = root / "storage"
            settings.input_dir = settings.storage_dir / "inputs"
            settings.output_dir = settings.storage_dir / "outputs"
            settings.task_dir = settings.storage_dir / "tasks"
            settings.input_dir.mkdir(parents=True, exist_ok=True)

            for image_format, suffix in (("PNG", ".png"), ("JPEG", ".jpg"), ("WEBP", ".webp")):
                image_path = root / f"accepted{suffix}"
                Image.new("RGB", (2, 2), "yellow").save(image_path, format=image_format)
                validation = await validate_image_source(ImageSource(local_path=str(image_path)), "product_reference")
                assert validation["format"] == image_format.lower()

            unsupported_path = root / "unsupported.bmp"
            Image.new("RGB", (2, 2), "yellow").save(unsupported_path, format="BMP")
            try:
                await validate_image_source(ImageSource(local_path=str(unsupported_path)), "product_reference")
            except ImageAssetValidationError:
                pass
            else:
                raise AssertionError("BMP was accepted")

            oversized_path = root / "oversized.png"
            oversized_path.write_bytes(b"x" * (MAX_IMAGE_BYTES + 1))
            try:
                await validate_image_source(ImageSource(local_path=str(oversized_path)), "product_reference")
            except ImageAssetValidationError:
                pass
            else:
                raise AssertionError("image larger than 20 MiB was accepted")

            with patch("app.services.url_security._resolved_addresses", side_effect=_resolved_addresses):
                with patch("app.services.image_asset_service.httpx.AsyncClient", FakeAsyncClient):
                    path, source_type, original_url, content_type = await _download_image_url(
                        "https://public.example/product.png", "product_reference"
                    )
                    assert path.exists()
                    assert source_type == "url"
                    assert original_url == "https://public.example/product.png"
                    assert content_type == "image/png"

                    for unsafe_url in ("http://localhost/image.png", "http://127.0.0.1/image.png", "http://10.0.0.1/image.png"):
                        try:
                            await _download_image_url(unsafe_url, "product_reference")
                        except ImageAssetValidationError:
                            pass
                        else:
                            raise AssertionError(f"unsafe URL was accepted: {unsafe_url}")

                with patch(
                    "app.services.image_asset_service.httpx.AsyncClient",
                    lambda **kwargs: FakeAsyncClient(redirect=True, **kwargs),
                ):
                    try:
                        await _download_image_url("https://public.example/redirect", "product_reference")
                    except ImageAssetValidationError:
                        pass
                    else:
                        raise AssertionError("redirect to a private URL was accepted")

                for status_code in (401, 403):
                    with patch(
                        "app.services.image_asset_service.httpx.AsyncClient",
                        lambda **kwargs: FakeAsyncClient(status_code=status_code, **kwargs),
                    ):
                        try:
                            await _download_image_url(
                                "https://public.example/signed.png",
                                "product_reference",
                                retryable_auth_failure=True,
                            )
                        except RetryableImageAssetError as exc:
                            assert map_exception_to_error(exc)[2] is True
                            assert "signed.png" not in str(exc)
                        else:
                            raise AssertionError(f"formal GET HTTP {status_code} was not retryable")

                with patch(
                    "app.services.image_asset_service.httpx.AsyncClient",
                    lambda **kwargs: FakeAsyncClient(status_code=404, **kwargs),
                ):
                    try:
                        await _download_image_url(
                            "https://public.example/missing.png",
                            "product_reference",
                            retryable_auth_failure=True,
                        )
                    except ImageAssetValidationError as exc:
                        assert map_exception_to_error(exc)[2] is False
                    else:
                        raise AssertionError("ordinary input failure was accepted")

                with patch(
                    "app.services.image_asset_service.httpx.AsyncClient",
                    lambda **kwargs: FakeAsyncClient(status_code=403, **kwargs),
                ):
                    try:
                        await _download_image_url("https://public.example/compat.png", "product_reference")
                    except ImageAssetValidationError as exc:
                        assert not isinstance(exc, RetryableImageAssetError)
                        assert map_exception_to_error(exc)[2] is False
                    else:
                        raise AssertionError("compatibility GET HTTP 403 was accepted")
    finally:
        settings.storage_dir = original_storage_dir
        settings.input_dir = original_input_dir
        settings.output_dir = original_output_dir
        settings.task_dir = original_task_dir


def main() -> None:
    asyncio.run(_run())
    print("IMAGE_URL_SECURITY_SMOKE_OK")


if __name__ == "__main__":
    main()
