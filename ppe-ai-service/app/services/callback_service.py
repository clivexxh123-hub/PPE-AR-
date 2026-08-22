from typing import Any

import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from app.schemas.business_protocol import WorkerCallbackEvent
from app.services.url_security import UnsafeUrlError, redact_url, validate_public_http_url


MAX_CALLBACK_ATTEMPTS = 3
_RETRYABLE_CALLBACK_STATUS_CODES = {408, 429}
_CALLBACK_RETRY_DELAYS_SECONDS = (1.0, 3.0)
_MAX_RETRY_AFTER_SECONDS = 30.0


def _callback_body(event: WorkerCallbackEvent) -> bytes:
    payload = event.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _callback_headers(body: bytes, secret: str, timestamp: int) -> dict[str, str]:
    signature_source = f"{timestamp}.".encode("utf-8") + body
    signature = hmac.new(secret.encode("utf-8"), signature_source, hashlib.sha256).hexdigest()
    return {
        "content-type": "application/json",
        "x-ppe-callback-timestamp": str(timestamp),
        "x-ppe-callback-signature": f"sha256={signature}",
    }


def _should_retry_status(status_code: int) -> bool:
    return status_code in _RETRYABLE_CALLBACK_STATUS_CODES or 500 <= status_code <= 599


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, min(float(value), _MAX_RETRY_AFTER_SECONDS))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            return max(0.0, min((retry_at - datetime.now(UTC)).total_seconds(), _MAX_RETRY_AFTER_SECONDS))
        except (TypeError, ValueError):
            return None


async def _wait_before_retry(delay_seconds: float) -> None:
    await asyncio.sleep(delay_seconds)


async def send_worker_callback(
    callback_url: str | None,
    event: WorkerCallbackEvent,
    *,
    hmac_secret: str | None,
    timestamp: int | None = None,
) -> dict[str, Any]:
    if not callback_url:
        return {
            "sent": False,
            "callback_skipped": True,
            "reason": "GenerationTaskInput.callback 未配置",
        }

    callback_url = callback_url.strip()
    if not callback_url.lower().startswith(("http://", "https://")):
        return {
            "sent": False,
            "callback_skipped": True,
            "callback": redact_url(callback_url),
            "reason": "callback 不是 HTTP(S) URL",
        }

    if not hmac_secret:
        return {
            "sent": False,
            "callback_skipped": True,
            "callback": redact_url(callback_url),
            "reason": "PPE_CALLBACK_HMAC_SECRET 未配置，未发送未签名 callback。",
        }

    try:
        validate_public_http_url(callback_url, purpose="callback")
        body = _callback_body(event)
        base_timestamp = int(time.time()) if timestamp is None else timestamp
        last_timestamp = base_timestamp - 1
        async with httpx.AsyncClient(timeout=10) as client:
            for attempt_index in range(MAX_CALLBACK_ATTEMPTS):
                callback_timestamp = max(base_timestamp + attempt_index, last_timestamp + 1)
                last_timestamp = callback_timestamp
                headers = _callback_headers(body, hmac_secret, callback_timestamp)
                try:
                    response = await client.post(callback_url, content=body, headers=headers)
                except httpx.RequestError as exc:
                    if attempt_index + 1 == MAX_CALLBACK_ATTEMPTS:
                        return {
                            "sent": False,
                            "callback_skipped": False,
                            "callback": redact_url(callback_url),
                            "attempts": attempt_index + 1,
                            "error": str(exc),
                        }
                    await _wait_before_retry(_CALLBACK_RETRY_DELAYS_SECONDS[attempt_index])
                    continue

                try:
                    response_ok = response.json() == {"ok": True}
                except ValueError:
                    response_ok = False
                if response.status_code == 200 and response_ok:
                    return {
                        "sent": True,
                        "callback_skipped": False,
                        "callback": redact_url(callback_url),
                        "status_code": response.status_code,
                        "body": response.text[:500],
                        "attempts": attempt_index + 1,
                    }
                if not _should_retry_status(response.status_code) or attempt_index + 1 == MAX_CALLBACK_ATTEMPTS:
                    return {
                        "sent": False,
                        "callback_skipped": False,
                        "callback": redact_url(callback_url),
                        "status_code": response.status_code,
                        "body": response.text[:500],
                        "attempts": attempt_index + 1,
                    }

                delay_seconds = _retry_after_seconds(response)
                if delay_seconds is None:
                    delay_seconds = _CALLBACK_RETRY_DELAYS_SECONDS[attempt_index]
                await _wait_before_retry(delay_seconds)
    except UnsafeUrlError as exc:
        return {
            "sent": False,
            "callback_skipped": False,
            "callback": redact_url(callback_url),
            "security_blocked": True,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "sent": False,
            "callback_skipped": False,
            "callback": redact_url(callback_url),
            "error": str(exc),
        }
