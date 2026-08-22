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
    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, object]] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> httpx.Response:
        self.requests.append({"url": url, "content": content, "headers": headers})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _assert_signed_requests(requests: list[dict[str, object]], secret: str, timestamps: list[int]) -> None:
    assert len(requests) == len(timestamps)
    for request, timestamp in zip(requests, timestamps, strict=True):
        body = request["content"]
        headers = request["headers"]
        assert isinstance(body, bytes)
        assert isinstance(headers, dict)
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp}.".encode("utf-8") + body,
            hashlib.sha256,
        ).hexdigest()
        assert headers["x-ppe-callback-timestamp"] == str(timestamp)
        assert headers["x-ppe-callback-signature"] == f"sha256={expected_signature}"


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
    client = FakeAsyncClient([httpx.Response(200, json={"ok": True})])
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
    body = client.requests[0]["content"]
    assert isinstance(body, bytes)
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
    _assert_signed_requests(client.requests, secret, [timestamp])

    retry_client = FakeAsyncClient([httpx.Response(500, text="temporary"), httpx.Response(200, json={"ok": True})])
    retry_delays: list[float] = []

    async def record_retry_delay(delay: float) -> None:
        retry_delays.append(delay)

    with patch("app.services.callback_service.validate_public_http_url"):
        with patch("app.services.callback_service.httpx.AsyncClient", return_value=retry_client):
            with patch("app.services.callback_service._wait_before_retry", side_effect=record_retry_delay):
                retried = await send_worker_callback(
                    "https://tasks.example/events",
                    event,
                    hmac_secret=secret,
                    timestamp=timestamp,
                )
    assert retried["sent"] is True
    assert retried["attempts"] == 2
    assert retry_delays == [1.0]
    _assert_signed_requests(retry_client.requests, secret, [timestamp, timestamp + 1])

    network_client = FakeAsyncClient([httpx.ConnectError("offline"), httpx.Response(200, json={"ok": True})])
    network_delays: list[float] = []

    async def record_network_delay(delay: float) -> None:
        network_delays.append(delay)

    with patch("app.services.callback_service.validate_public_http_url"):
        with patch("app.services.callback_service.httpx.AsyncClient", return_value=network_client):
            with patch("app.services.callback_service._wait_before_retry", side_effect=record_network_delay):
                retried = await send_worker_callback(
                    "https://tasks.example/events",
                    event,
                    hmac_secret=secret,
                    timestamp=timestamp,
                )
    assert retried["sent"] is True
    assert network_delays == [1.0]
    _assert_signed_requests(network_client.requests, secret, [timestamp, timestamp + 1])

    for status_code, retry_after, expected_delay in ((429, "7", 7.0), (503, "45", 30.0)):
        retry_after_client = FakeAsyncClient(
            [httpx.Response(status_code, headers={"Retry-After": retry_after}), httpx.Response(200, json={"ok": True})]
        )
        retry_after_delays: list[float] = []

        async def record_retry_after(delay: float) -> None:
            retry_after_delays.append(delay)

        with patch("app.services.callback_service.validate_public_http_url"):
            with patch("app.services.callback_service.httpx.AsyncClient", return_value=retry_after_client):
                with patch("app.services.callback_service._wait_before_retry", side_effect=record_retry_after):
                    retried = await send_worker_callback(
                        "https://tasks.example/events",
                        event,
                        hmac_secret=secret,
                        timestamp=timestamp,
                    )
        assert retried["sent"] is True
        assert retry_after_delays == [expected_delay]

    for status_code in (400, 409):
        rejected_client = FakeAsyncClient([httpx.Response(status_code, text="rejected")])
        with patch("app.services.callback_service.validate_public_http_url"):
            with patch("app.services.callback_service.httpx.AsyncClient", return_value=rejected_client):
                rejected = await send_worker_callback(
                    "https://tasks.example/events",
                    event,
                    hmac_secret=secret,
                    timestamp=timestamp,
                )
        assert rejected["sent"] is False
        assert rejected["attempts"] == 1
        assert len(rejected_client.requests) == 1


def main() -> None:
    asyncio.run(_run())
    print("CALLBACK_PROTOCOL_SMOKE_OK")


if __name__ == "__main__":
    main()
