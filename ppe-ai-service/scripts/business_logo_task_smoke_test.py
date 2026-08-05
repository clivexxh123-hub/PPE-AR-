"""Minimal /ai/tasks regression test for all currently supported operations."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.main import app


OUTPUT_ROOT = Path(r"D:\Don't Click it\JOB\XVison\PPE_AI\output\business_logo_task_smoke")


def _task_payload(job_id: str, operation: str, parameters: dict) -> dict:
    return {
        "jobId": job_id,
        "type": operation,
        "tenantId": "local-smoke",
        "traceId": f"trace-{job_id}",
        "modelProfileId": "local-test-profile",
        "workflowVersion": "local-test-v1",
        "parameters": {"sync": True, **parameters},
    }


def main() -> None:
    original_output_dir = settings.output_dir
    original_task_dir = settings.task_dir
    original_input_dir = settings.input_dir
    original_engine = settings.ai_engine
    settings.output_dir = OUTPUT_ROOT / "outputs"
    settings.task_dir = OUTPUT_ROOT / "tasks"
    settings.input_dir = OUTPUT_ROOT / "inputs"
    settings.ai_engine = "mock"
    try:
        inputs = OUTPUT_ROOT / "fixtures"
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
        print("BUSINESS_LOGO_TASK_SMOKE_OK")
    finally:
        settings.output_dir = original_output_dir
        settings.task_dir = original_task_dir
        settings.input_dir = original_input_dir
        settings.ai_engine = original_engine


if __name__ == "__main__":
    main()
