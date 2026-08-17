from __future__ import annotations

import asyncio
import io
import ipaddress
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
from PIL import Image

from app.core.config import settings
from app.services.image_asset_service import ImageAssetValidationError, _download_image_url


def _png_bytes() -> bytes:
    image = Image.new("RGBA", (2, 2), (255, 255, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class FakeAsyncClient:
    def __init__(self, *, redirect: bool = False, **_: object) -> None:
        self.redirect = redirect
        self.requests: list[str] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str) -> httpx.Response:
        self.requests.append(url)
        if self.redirect:
            return httpx.Response(302, headers={"location": "http://127.0.0.1/private.png"})
        return httpx.Response(200, headers={"content-type": "image/png"}, content=_png_bytes())


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
