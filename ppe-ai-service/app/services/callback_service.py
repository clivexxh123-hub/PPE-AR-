from typing import Any

import httpx

from app.schemas.business_protocol import WorkerCallbackEvent


async def send_worker_callback(task_center_base_url: str | None, event: WorkerCallbackEvent) -> dict[str, Any]:
    if not task_center_base_url:
        return {
            "sent": False,
            "callback_skipped": True,
            "reason": "TASK_CENTER_BASE_URL \u672a\u914d\u7f6e",
        }

    callback_url = f"{task_center_base_url.rstrip('/')}/internal/v1/jobs/{event.jobId}/events"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(callback_url, json=event.model_dump(mode="json", exclude_none=True))
        return {
            "sent": response.is_success,
            "callback_skipped": False,
            "callback": callback_url,
            "status_code": response.status_code,
            "body": response.text[:500],
        }
    except Exception as exc:
        return {
            "sent": False,
            "callback_skipped": False,
            "callback": callback_url,
            "error": str(exc),
        }
