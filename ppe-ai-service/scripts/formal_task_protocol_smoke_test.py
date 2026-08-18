"""Check the frozen /ai/tasks contract without requiring external services."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.routes import _parameters_with_input_assets
from app.core.config import settings
from app.main import app
from app.schemas.business_protocol import GenerationTaskInput
from app.services.image_asset_service import ALLOWED_IMAGE_FORMATS, MAX_IMAGE_BYTES


def _formal_payload() -> dict:
    return {
        "jobId": "formal-contract-smoke",
        "type": "image_generation",
        "tenantId": "tenant-smoke",
        "traceId": "trace-formal-contract-smoke",
        "attempt": 2,
        "modelProfileId": "sd15-smoke",
        "workflowVersion": "v1",
        "inputAssets": [
            {
                "assetId": "product-1",
                "role": "product_reference",
                "version": 3,
                "url": "https://assets.example/product.png?signature=temporary",
                "expiresAt": "2026-08-18T12:00:00Z",
            }
        ],
        "parameters": {"scene": "industrial studio", "style": "commercial PPE photography"},
        "callback": "https://tasks.example/internal/v1/jobs/formal-contract-smoke/events",
        "output": {
            "assetKey": "results/tenant-smoke/formal-contract-smoke/attempt-2/result.png",
            "uploadUrl": "https://uploads.example/result.png?signature=temporary",
            "method": "PUT",
            "requiredHeaders": {"content-type": "image/png"},
            "expiresAt": "2026-08-18T12:00:00Z",
        },
    }


def _expect_invalid(payload: dict) -> None:
    try:
        GenerationTaskInput.model_validate(payload).validate_formal_contract()
    except ValueError:
        return
    raise AssertionError("invalid formal task contract was accepted")


def main() -> None:
    task = GenerationTaskInput.model_validate(_formal_payload())
    task.validate_formal_contract()
    parameters = _parameters_with_input_assets(task)
    assert parameters["product_image"]["url"].startswith("https://assets.example/product.png")
    assert task.attempt == 2
    assert task.output is not None
    assert task.output.assetKey.endswith("attempt-2/result.png")
    assert MAX_IMAGE_BYTES == 20 * 1024 * 1024
    assert ALLOWED_IMAGE_FORMATS == {"JPEG", "PNG", "WEBP"}

    missing_output = _formal_payload()
    missing_output.pop("output")
    _expect_invalid(missing_output)

    missing_asset_url = _formal_payload()
    missing_asset_url["inputAssets"][0].pop("url")
    _expect_invalid(missing_asset_url)

    missing_product_role = _formal_payload()
    missing_product_role["inputAssets"][0]["role"] = "logo"
    _expect_invalid(missing_product_role)

    original_strict_mode = settings.ai_task_require_formal_contract
    settings.ai_task_require_formal_contract = True
    try:
        with TestClient(app) as client:
            strict_response = client.post("/ai/tasks", json=missing_output)
        assert strict_response.status_code == 422
        assert "output" in str(strict_response.json())
    finally:
        settings.ai_task_require_formal_contract = original_strict_mode

    print("FORMAL_TASK_PROTOCOL_SMOKE_OK")


if __name__ == "__main__":
    main()
