from typing import Any

import httpx

from app.schemas.business_protocol import WorkerCallbackEvent
from app.services.url_security import UnsafeUrlError, redact_url, validate_public_http_url


async def send_worker_callback(callback_url: str | None, event: WorkerCallbackEvent) -> dict[str, Any]:
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

    try:
        validate_public_http_url(callback_url, purpose="callback")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(callback_url, json=event.model_dump(mode="json", exclude_none=True))
        return {
            "sent": response.is_success,
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
            "callback": callback_url,
            "error": str(exc),
        }
