"""Check presigned PUT uploads use raw bytes and preserve required headers."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.business_protocol import TaskOutputSpec
from app.services.storage_service import upload_result


class FakeAsyncClient:
    def __init__(self) -> None:
        self.request: dict[str, object] = {}

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def put(self, url: str, *, content: bytes, headers: dict[str, str]) -> httpx.Response:
        self.request = {"url": url, "content": content, "headers": headers}
        return httpx.Response(200, text="OK")


async def _run() -> None:
    output = TaskOutputSpec(
        assetKey="results/tenant/upload-smoke/attempt-1/result.png",
        uploadUrl="https://uploads.example/result.png?signature=temporary",
        method="PUT",
        requiredHeaders={"content-type": "image/png", "x-oss-meta-trace": "trace-1"},
        expiresAt="2026-08-18T12:00:00Z",
    )
    with tempfile.TemporaryDirectory(prefix="ppe-presigned-upload-") as temp_dir:
        image_path = Path(temp_dir) / "result.png"
        image_bytes = b"png-bytes-for-upload-smoke"
        image_path.write_bytes(image_bytes)
        client = FakeAsyncClient()
        with patch("app.services.storage_service.validate_public_http_url"):
            with patch("app.services.storage_service.httpx.AsyncClient", return_value=client):
                result = await upload_result(image_path, output.assetKey, output=output)
    assert result.uploaded is True
    assert result.pending is False
    assert result.assetKey == output.assetKey
    assert client.request["content"] == image_bytes
    assert client.request["headers"] == output.requiredHeaders


def main() -> None:
    asyncio.run(_run())
    print("PRESIGNED_UPLOAD_PROTOCOL_SMOKE_OK")


if __name__ == "__main__":
    main()
