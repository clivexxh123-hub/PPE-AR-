from typing import Any

import hashlib
import hmac
import json
import time

import httpx

from app.schemas.business_protocol import WorkerCallbackEvent
from app.services.url_security import UnsafeUrlError, redact_url, validate_public_http_url


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
        callback_timestamp = int(time.time()) if timestamp is None else timestamp
        headers = _callback_headers(body, hmac_secret, callback_timestamp)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(callback_url, content=body, headers=headers)
        try:
            response_ok = response.json() == {"ok": True}
        except ValueError:
            response_ok = False
        return {
            "sent": response.status_code == 200 and response_ok,
            "callback_skipped": False,
            "callback": redact_url(callback_url),
            "status_code": response.status_code,
            "body": response.text[:500],
        }
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
