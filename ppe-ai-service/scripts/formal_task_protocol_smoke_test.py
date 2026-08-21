"""Check the frozen /ai/tasks contract without requiring external services."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_PATH = PROJECT_ROOT / "samples" / "business_task_examples.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.routes import _ensure_formal_input_assets_current, _parameters_with_input_assets
from app.core.config import settings
from app.main import app
from app.schemas.business_protocol import GenerationTaskInput
from app.services.error_codes import map_exception_to_error
from app.services.image_asset_service import ALLOWED_IMAGE_FORMATS, MAX_IMAGE_BYTES, RetryableImageAssetError


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
                "expiresAt": "2099-08-18T12:00:00Z",
            }
        ],
        "parameters": {"scene": "industrial studio", "style": "commercial PPE photography"},
        "callback": "https://tasks.example/internal/v1/jobs/formal-contract-smoke/events",
        "output": {
            "assetKey": "results/tenant-smoke/formal-contract-smoke/attempt-2/result.png",
            "uploadUrl": "https://uploads.example/result.png?signature=temporary",
            "method": "PUT",
            "requiredHeaders": {"content-type": "image/png"},
            "expiresAt": "2099-08-18T12:00:00Z",
        },
    }


def _expect_invalid(payload: dict) -> None:
    try:
        GenerationTaskInput.model_validate(payload).validate_formal_contract()
    except ValueError:
        return
    raise AssertionError("invalid formal task contract was accepted")


def _expect_valid(payload: dict) -> GenerationTaskInput:
    task = GenerationTaskInput.model_validate(payload)
    task.validate_formal_contract()
    return task


def main() -> None:
    invalid_http_payloads: list[dict] = []
    task = _expect_valid(_formal_payload())
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

    for callback in ("https://tasks.example/events", "http://tasks.example/events"):
        valid_callback = _formal_payload()
        valid_callback["callback"] = callback
        _expect_valid(valid_callback)
    for callback in ("/events", "tasks.example/events", "ftp://tasks.example/events", "not a url"):
        invalid_callback = _formal_payload()
        invalid_callback["callback"] = callback
        _expect_invalid(invalid_callback)
        invalid_http_payloads.append(invalid_callback)

    for field_path in ("input", "output"):
        for invalid_expiry in ("not-a-datetime", "2099-08-18T12:00:00", "2020-01-01T00:00:00Z"):
            invalid_expiration = _formal_payload()
            target = invalid_expiration["inputAssets"][0] if field_path == "input" else invalid_expiration["output"]
            target["expiresAt"] = invalid_expiry
            _expect_invalid(invalid_expiration)
            invalid_http_payloads.append(invalid_expiration)
        valid_expiration = _formal_payload()
        target = valid_expiration["inputAssets"][0] if field_path == "input" else valid_expiration["output"]
        target["expiresAt"] = "2099-08-18T20:00:00+08:00"
        _expect_valid(valid_expiration)

    printed_design = _formal_payload()
    printed_design["inputAssets"][0]["role"] = "printed_design"
    printed_design["parameters"] = {
        "product_image": {"url": "https://assets.example/product.png?signature=temporary"}
    }
    printed_task = _expect_valid(printed_design)
    printed_parameters = _parameters_with_input_assets(printed_task)
    assert printed_parameters["product_image"]["url"] == "https://assets.example/product.png?signature=temporary"

    text_to_image = _formal_payload()
    text_to_image["inputAssets"] = []
    text_to_image["parameters"] = {"scene": "industrial studio"}
    _expect_valid(text_to_image)

    conflicting_references = _formal_payload()
    conflicting_references["inputAssets"].append(
        {
            "assetId": "printed-1",
            "role": "printed_design",
            "version": 1,
            "url": "https://assets.example/printed.png?signature=temporary",
            "expiresAt": "2099-08-18T12:00:00Z",
        }
    )
    _expect_invalid(conflicting_references)

    conflicting_parameter_url = _formal_payload()
    conflicting_parameter_url["parameters"] = {
        "product_image": {"url": "https://assets.example/other-product.png?signature=temporary"}
    }
    _expect_invalid(conflicting_parameter_url)

    logo_task = _formal_payload()
    logo_task["type"] = "logo_remove_bg"
    logo_task["inputAssets"][0]["role"] = "logo"
    logo_task["parameters"] = {"logo_image": {"url": "https://assets.example/product.png?signature=temporary"}}
    _expect_valid(logo_task)

    print_task = _formal_payload()
    print_task["type"] = "print_render"
    print_task["inputAssets"].append(
        {
            "assetId": "logo-1",
            "role": "logo",
            "version": 1,
            "url": "https://assets.example/logo.png?signature=temporary",
            "expiresAt": "2099-08-18T12:00:00Z",
        }
    )
    print_task["parameters"] = {
        "product_image": {"url": "https://assets.example/product.png?signature=temporary"},
        "logo_image": {"url": "https://assets.example/logo.png?signature=temporary"},
    }
    _expect_valid(print_task)

    samples = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))["examples"]
    for name, sample in samples.items():
        _expect_valid(copy.deepcopy(sample))
        assert name

    original_strict_mode = settings.ai_task_require_formal_contract
    settings.ai_task_require_formal_contract = True
    try:
        strict_asset_task = _expect_valid(_formal_payload())
        strict_asset_task.parameters = {"product_image": {"local_path": "not-used-in-formal-mode.png"}}
        strict_parameters = _parameters_with_input_assets(strict_asset_task)
        assert strict_parameters["product_image"] == {
            "url": "https://assets.example/product.png?signature=temporary",
            "retryable_auth_failure": True,
        }
        expired_at_use = GenerationTaskInput.model_validate(_formal_payload())
        expired_at_use.inputAssets[0].expiresAt = "2020-01-01T00:00:00Z"
        try:
            _ensure_formal_input_assets_current(expired_at_use)
        except RetryableImageAssetError as exc:
            assert map_exception_to_error(exc)[2] is True
        else:
            raise AssertionError("expired formal input URL was accepted at use time")
        with TestClient(app) as client:
            strict_response = client.post("/ai/tasks", json=missing_output)
            conflicting_roles_response = client.post("/ai/tasks", json=conflicting_references)
            conflicting_url_response = client.post("/ai/tasks", json=conflicting_parameter_url)
            strict_validation_responses = [
                client.post("/ai/tasks", json=payload) for payload in invalid_http_payloads
            ]
        assert strict_response.status_code == 422
        assert "output" in str(strict_response.json())
        assert conflicting_roles_response.status_code == 422
        assert conflicting_url_response.status_code == 422
        assert all(response.status_code == 422 for response in strict_validation_responses)
    finally:
        settings.ai_task_require_formal_contract = original_strict_mode

    print("FORMAL_TASK_PROTOCOL_SMOKE_OK")


if __name__ == "__main__":
    main()
