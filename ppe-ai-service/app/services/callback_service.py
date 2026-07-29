from typing import Any

import httpx

from app.schemas.business_protocol import WorkerCallbackEvent


async def send_worker_callback(callback: str | None, event: WorkerCallbackEvent) -> dict[str, Any]:
    if not callback:
        return {"sent": False, "reason": "callback 为空"}
    if callback.startswith("internal://"):
        return {"sent": False, "reason": "internal callback 当前只记录，不发送", "callback": callback}
    if not (callback.startswith("http://") or callback.startswith("https://")):
        return {"sent": False, "reason": "callback 协议暂不支持", "callback": callback}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(callback, json=event.model_dump(mode="json", exclude_none=True))
        return {"sent": response.is_success, "status_code": response.status_code, "body": response.text[:500]}
    except Exception as exc:  # 回调失败不覆盖生成结果，只记录。
        return {"sent": False, "error": str(exc), "callback": callback}
