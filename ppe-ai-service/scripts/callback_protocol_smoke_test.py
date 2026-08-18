"""Check the signed callback wire format without sending a network request."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import sys
from pathlib import Path
from unittest.mock import patch

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.business_protocol import TaskResult, WorkerCallbackEvent
from app.schemas.tasks import TaskStatus
from app.services.callback_service import send_worker_callback


class FakeAsyncClient:
    def __init__(self, response_body: dict[str, bool]) -> None:
        self.response_body = response_body
        self.request: dict[str, object] = {}

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> httpx.Response:
        self.request = {"url": url, "content": content, "headers": headers}
        return httpx.Response(200, json=self.response_body)


async def _run() -> None:
    event = WorkerCallbackEvent(
        jobId="callback-protocol-smoke",
        attempt=3,
        status=TaskStatus.succeeded,
        result=TaskResult(
            assetKey="results/tenant/callback-protocol-smoke/attempt-3/result.png",
            width=512,
            height=512,
            hash="a" * 64,
        ),
    )
    client = FakeAsyncClient({"ok": True})
    secret = "callback-smoke-secret"
    timestamp = 1_700_000_000
    with patch("app.services.callback_service.validate_public_http_url"):
        with patch("app.services.callback_service.httpx.AsyncClient", return_value=client):
            result = await send_worker_callback(
                "https://tasks.example/internal/v1/jobs/callback-protocol-smoke/events?token=temporary",
                event,
                hmac_secret=secret,
                timestamp=timestamp,
            )
    assert result["sent"] is True
    assert result["callback"] == "https://tasks.example/internal/v1/jobs/callback-protocol-smoke/events?[REDACTED]"
    body = client.request["content"]
    headers = client.request["headers"]
    assert isinstance(body, bytes)
    assert isinstance(headers, dict)
    assert json.loads(body) == {
        "jobId": "callback-protocol-smoke",
        "attempt": 3,
        "status": "succeeded",
        "result": {
            "assetKey": "results/tenant/callback-protocol-smoke/attempt-3/result.png",
            "width": 512,
            "height": 512,
            "hash": "a" * 64,
        },
    }
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + body,
        hashlib.sha256,
    ).hexdigest()
    assert headers["x-ppe-callback-timestamp"] == str(timestamp)
    assert headers["x-ppe-callback-signature"] == f"sha256={expected_signature}"

    rejected_client = FakeAsyncClient({"ok": False})
    with patch("app.services.callback_service.validate_public_http_url"):
        with patch("app.services.callback_service.httpx.AsyncClient", return_value=rejected_client):
            rejected = await send_worker_callback(
                "https://tasks.example/events",
                event,
                hmac_secret=secret,
                timestamp=timestamp,
            )
    assert rejected["sent"] is False


def main() -> None:
    asyncio.run(_run())
    print("CALLBACK_PROTOCOL_SMOKE_OK")


if __name__ == "__main__":
    main()
