"""Verify /ai/tasks asynchronous queued-to-terminal task behavior in mock mode."""

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


def _payload(job_id: str, task_type: str, parameters: dict) -> dict:
    return {
        "jobId": job_id,
        "taskType": task_type,
        "tenantId": "local-smoke",
        "traceId": f"trace-{job_id}",
        "modelProfileId": "local-test-profile",
        "workflowVersion": "local-test-v1",
        "parameters": {"sync": False, **parameters},
    }


def main() -> None:
    original_output_dir = settings.output_dir
    original_task_dir = settings.task_dir
    original_input_dir = settings.input_dir
    original_engine = settings.ai_engine
    temporary_output = tempfile.TemporaryDirectory(prefix="ppe-ai-async-smoke-")
    output_root = Path(temporary_output.name)
    settings.output_dir = output_root / "outputs"
    settings.task_dir = output_root / "tasks"
    settings.input_dir = output_root / "inputs"
    settings.ai_engine = "mock"
    try:
        with TestClient(app) as client:
            accepted = client.post(
                "/ai/tasks",
                json=_payload(
                    "async-image-success",
                    "image_generation",
                    {
                        "product_name": "safety helmet",
                        "product_category": "PPE/head protection",
                        "scene": "studio",
                        "style": "commercial product photo",
                        "size": "512x512",
                        "output_format": "png",
                    },
                ),
            )
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["status"] == "queued"
            completed = client.get("/ai/tasks/async-image-success")
            assert completed.status_code == 200, completed.text
            assert completed.json()["status"] == "succeeded"
            assert completed.json()["result_url"]

            failed_accept = client.post(
                "/ai/tasks",
                json=_payload("async-print-failure", "print_render", {}),
            )
            assert failed_accept.status_code == 200, failed_accept.text
            assert failed_accept.json()["status"] == "queued"
            failed = client.get("/ai/tasks/async-print-failure")
            assert failed.status_code == 200, failed.text
            assert failed.json()["status"] == "failed"
            assert failed.json()["errorCode"] == "AI_400_INPUT_INVALID"
            assert failed.json()["retryable"] is False
        print("ASYNC_TASK_LIFECYCLE_SMOKE_OK")
    finally:
        settings.output_dir = original_output_dir
        settings.task_dir = original_task_dir
        settings.input_dir = original_input_dir
        settings.ai_engine = original_engine
        temporary_output.cleanup()


if __name__ == "__main__":
    main()
