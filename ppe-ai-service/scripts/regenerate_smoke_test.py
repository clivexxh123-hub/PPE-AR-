"""Verify SRS-level image regeneration through fresh image_generation jobs."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.main import app


def _payload(job_id: str, *, scene: str, style: str, overrides: dict[str, str]) -> dict:
    return {
        "jobId": job_id,
        "type": "image_generation",
        "tenantId": "local-regenerate-smoke",
        "traceId": f"trace-{job_id}",
        "modelProfileId": "local-test-profile",
        "workflowVersion": "local-test-v1",
        "parameters": {
            "sync": True,
            "product_name": "safety helmet",
            "product_category": "PPE/head protection",
            "scene": scene,
            "style": style,
            "prompt_overrides": overrides,
            "size": "512x512",
            "output_format": "png",
        },
    }


def _completed_task(client: TestClient, payload: dict) -> dict:
    response = client.post("/ai/tasks", json=payload)
    assert response.status_code == 200, response.text
    accepted = response.json()
    assert accepted["status"] == "succeeded", accepted

    completed = client.get(f"/ai/tasks/{accepted['jobId']}")
    assert completed.status_code == 200, completed.text
    task = completed.json()
    assert task["status"] == "succeeded", task
    assert task["result_url"]
    assert task["metadata_url"]
    assert client.get(task["result_url"]).status_code == 200
    return task


def main() -> None:
    original_output_dir = settings.output_dir
    original_task_dir = settings.task_dir
    original_input_dir = settings.input_dir
    original_engine = settings.ai_engine
    original_contract = settings.ai_task_require_formal_contract
    with tempfile.TemporaryDirectory(prefix="ppe-ai-regenerate-smoke-") as temp_dir:
        temporary_root = Path(temp_dir)
        settings.output_dir = temporary_root / "outputs"
        settings.task_dir = temporary_root / "tasks"
        settings.input_dir = temporary_root / "inputs"
        settings.ai_engine = "mock"
        settings.ai_task_require_formal_contract = False
        try:
            with TestClient(app) as client:
                original = _completed_task(
                    client,
                    _payload(
                        "regenerate-original",
                        scene="clean industrial studio",
                        style="commercial product photography",
                        overrides={},
                    ),
                )
                original_bytes = client.get(original["result_url"]).content

                repeated = _completed_task(
                    client,
                    _payload(
                        "regenerate-repeat",
                        scene="clean industrial studio",
                        style="commercial product photography",
                        overrides={},
                    ),
                )
                assert repeated["jobId"] != original["jobId"]
                assert repeated["result_url"] != original["result_url"]

                updated = _completed_task(
                    client,
                    _payload(
                        "regenerate-updated",
                        scene="professional warehouse safety display",
                        style="realistic catalog advertising",
                        overrides={"lighting": "soft daylight"},
                    ),
                )
                assert updated["jobId"] not in {original["jobId"], repeated["jobId"]}
                assert updated["result_url"] not in {original["result_url"], repeated["result_url"]}

                original_after = client.get(f"/ai/tasks/{original['jobId']}").json()
                assert original_after["status"] == "succeeded"
                assert client.get(original_after["result_url"]).content == original_bytes

                updated_metadata = client.get(updated["metadata_url"])
                assert updated_metadata.status_code == 200, updated_metadata.text
                parameters = updated_metadata.json()["business_protocol"]["parameters"]
                assert parameters["scene"] == "professional warehouse safety display"
                assert parameters["style"] == "realistic catalog advertising"
                assert parameters["prompt_overrides"] == {"lighting": "soft daylight"}
            print("REGENERATE_SMOKE_OK")
        finally:
            settings.output_dir = original_output_dir
            settings.task_dir = original_task_dir
            settings.input_dir = original_input_dir
            settings.ai_engine = original_engine
            settings.ai_task_require_formal_contract = original_contract


if __name__ == "__main__":
    main()
