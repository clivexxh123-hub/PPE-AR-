"""Minimal local checks for task metadata redaction and URL SSRF protection."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.routes import _business_extra
from app.schemas.business_protocol import GenerationTaskInput
from app.services.url_security import UnsafeUrlError, validate_public_http_url


def _expect_unsafe(url: str) -> None:
    try:
        validate_public_http_url(url, purpose="smoke URL")
    except UnsafeUrlError:
        return
    raise AssertionError(f"Expected unsafe URL to be rejected: {url}")


def main() -> None:
    task = GenerationTaskInput(
        jobId="security-smoke",
        type="image_generation",
        tenantId="local-smoke",
        traceId="trace-security-smoke",
        modelProfileId="local-test-profile",
        workflowVersion="local-test-v1",
        parameters={"Authorization": "Bearer parameter-secret"},
        output={
            "assetKey": "results/local-smoke/security-smoke/attempt-0/result.png",
            "uploadUrl": "https://example.com/upload",
            "requiredHeaders": {
                "Authorization": "Bearer upload-secret",
                "Cookie": "session=secret",
                "X-Api-Key": "api-secret",
                "Content-Type": "image/png",
            },
        },
    )
    extra = _business_extra(task)
    protocol = extra["business_protocol"]
    headers = protocol["output"]["requiredHeaders"]
    assert all(value == "[REDACTED]" for value in headers.values())
    assert protocol["parameters"]["Authorization"] == "[REDACTED]"
    assert "upload-secret" not in str(extra)
    assert "parameter-secret" not in str(extra)

    for url in (
        "http://localhost:8000/callback",
        "http://127.0.0.1:8000/callback",
        "http://0.0.0.0:8000/callback",
        "http://10.0.0.1/callback",
        "http://172.16.0.1/callback",
        "http://192.168.1.1/callback",
        "http://169.254.1.1/callback",
        "http://[::1]/callback",
    ):
        _expect_unsafe(url)

    print("SECURITY_SMOKE_OK")


if __name__ == "__main__":
    main()
