from __future__ import annotations

import json

from app.api.routes import _business_extra
from app.schemas.business_protocol import GenerationTaskInput


def _task(callback: str) -> GenerationTaskInput:
    return GenerationTaskInput(
        jobId="callback-metadata-smoke",
        tenantId="tenant-smoke",
        traceId="trace-smoke",
        modelProfileId="sd15",
        workflowVersion="v1",
        callback=callback,
    )


def main() -> None:
    callback = "https://username:password@example.com/hooks/result?token=secret-token&signature=secret-signature"
    metadata = _business_extra(_task(callback), callback_result={"sent": False, "callback": callback, "error": "timeout"})
    serialized = json.dumps(metadata, ensure_ascii=False)

    for secret in ("username", "password", "secret-token", "secret-signature"):
        assert secret not in serialized
    assert metadata["business_protocol"]["raw_callback"] == "https://example.com/hooks/result?[REDACTED]"
    assert metadata["business_protocol"]["callback_url"] == "https://example.com/hooks/result?[REDACTED]"
    assert metadata["business_last_callback"]["callback"] == "https://example.com/hooks/result?[REDACTED]"
    print("CALLBACK_METADATA_SMOKE_OK")


if __name__ == "__main__":
    main()
