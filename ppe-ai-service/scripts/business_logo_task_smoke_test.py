"""Minimal /ai/tasks regression test for all currently supported operations."""

import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.main import app


def _task_payload(
    job_id: str,
    operation: str | None,
    parameters: dict,
    *,
    task_type: str | None = None,
) -> dict:
    payload = {
        "jobId": job_id,
        "tenantId": "local-smoke",
        "traceId": f"trace-{job_id}",
        "modelProfileId": "local-test-profile",
        "workflowVersion": "local-test-v1",
        "parameters": {"sync": True, **parameters},
    }
    if operation is not None:
        payload["type"] = operation
    if task_type is not None:
        payload["taskType"] = task_type
    return payload


def main() -> None:
    temporary_output = tempfile.TemporaryDirectory(prefix="ppe-business-task-smoke-")
    output_root = Path(temporary_output.name)
    original_output_dir = settings.output_dir
    original_task_dir = settings.task_dir
    original_input_dir = settings.input_dir
    original_engine = settings.ai_engine
    settings.output_dir = output_root / "outputs"
    settings.task_dir = output_root / "tasks"
    settings.input_dir = output_root / "inputs"
    settings.ai_engine = "mock"
    try:
        inputs = output_root / "fixtures"
        inputs.mkdir(parents=True, exist_ok=True)
        base_path = inputs / "product.png"
        logo_path = inputs / "logo.jpg"
        Image.new("RGB", (160, 120), "#F8FAFC").save(base_path)
        logo = Image.new("RGB", (90, 45), "white")
        ImageDraw.Draw(logo).rectangle((15, 10, 75, 35), fill="#2563EB")
        logo.save(logo_path, format="JPEG")

        with TestClient(app) as client:
            remove = client.post(
                "/ai/tasks",
                json=_task_payload("smoke-logo-remove", "logo_remove_bg", {"logo_image": {"local_path": str(logo_path)}}),
            )
            assert remove.status_code == 200, remove.text
            assert remove.json()["status"] == "succeeded"
            remove_metadata = client.get(remove.json()["metadata_url"]).json()
            assert remove_metadata["engine"] == "pillow-simple-background-removal"
            assert client.get(f"/ai/tasks/{remove.json()['jobId']}").json()["status"] == "succeeded"

            print_render = client.post(
                "/ai/tasks",
                json=_task_payload(
                    "smoke-print-render",
                    "print_render",
                    {
                        "base_image": {"local_path": str(base_path)},
                        "logo_image": {"local_path": str(logo_path)},
                        "position_x_ratio": 0.5,
                        "position_y_ratio": 0.5,
                        "logo_width_ratio": 0.25,
                        "opacity": 0.9,
                    },
                ),
            )
            assert print_render.status_code == 200, print_render.text
            assert print_render.json()["status"] == "succeeded"
            print_metadata = client.get(print_render.json()["metadata_url"]).json()
            assert print_metadata["business_protocol"]["operation"] == "print_render"
            assert client.get(print_render.json()["result_url"]).status_code == 200

            missing_logo = client.post(
                "/ai/tasks",
                json=_task_payload("smoke-logo-missing", "logo_remove_bg", {}),
            ).json()
            assert missing_logo["status"] == "failed"
            assert missing_logo["errorCode"] == "AI_400_INPUT_INVALID"

            missing_base = client.post(
                "/ai/tasks",
                json=_task_payload("smoke-render-missing", "print_render", {"logo_image": {"local_path": str(logo_path)}}),
            ).json()
            assert missing_base["status"] == "failed"
            assert missing_base["errorCode"] == "AI_400_INPUT_INVALID"

            generation = client.post(
                "/ai/tasks",
                json=_task_payload(
                    "smoke-image-generation",
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
            assert generation.status_code == 200, generation.text
            assert generation.json()["status"] == "succeeded"

            for operation, parameters in (
                ("logo_remove_bg", {"logo_image": {"local_path": str(logo_path)}}),
                (
                    "print_render",
                    {
                        "base_image": {"local_path": str(base_path)},
                        "logo_image": {"local_path": str(logo_path)},
                        "position_x_ratio": 0.5,
                        "position_y_ratio": 0.5,
                        "logo_width_ratio": 0.25,
                        "opacity": 0.9,
                    },
                ),
                (
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
            ):
                alias_response = client.post(
                    "/ai/tasks",
                    json=_task_payload(f"smoke-task-type-{operation}", None, parameters, task_type=operation),
                )
                assert alias_response.status_code == 200, alias_response.text
                assert alias_response.json()["status"] == "succeeded"

            matching = client.post(
                "/ai/tasks",
                json=_task_payload(
                    "smoke-matching-task-type",
                    "logo_remove_bg",
                    {"logo_image": {"local_path": str(logo_path)}},
                    task_type="logo_remove_bg",
                ),
            )
            assert matching.status_code == 200, matching.text
            assert matching.json()["status"] == "succeeded"

            conflict = client.post(
                "/ai/tasks",
                json=_task_payload(
                    "smoke-conflicting-task-type",
                    "logo_remove_bg",
                    {"logo_image": {"local_path": str(logo_path)}},
                    task_type="print_render",
                ),
            )
            assert conflict.status_code == 422, conflict.text
            assert "detail" in conflict.json()

            default_generation = client.post(
                "/ai/tasks",
                json=_task_payload(
                    "smoke-default-task-type",
                    None,
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
            assert default_generation.status_code == 200, default_generation.text
            assert default_generation.json()["status"] == "succeeded"

            unknown = client.post(
                "/ai/tasks",
                json=_task_payload("smoke-unknown-task-type", None, {}, task_type="unknown_task"),
            )
            assert unknown.status_code == 422, unknown.text
            assert "detail" in unknown.json()
        print("BUSINESS_LOGO_TASK_SMOKE_OK")
    finally:
        settings.output_dir = original_output_dir
        settings.task_dir = original_task_dir
        settings.input_dir = original_input_dir
        settings.ai_engine = original_engine
        temporary_output.cleanup()


if __name__ == "__main__":
    main()
