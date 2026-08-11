"""Minimal regression coverage for the scene_generation task mode."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api import routes  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.schemas.business_protocol import GenerationTaskInput  # noqa: E402
from app.schemas.tasks import TaskStatus  # noqa: E402
from app.services.task_store import create_task, load_task, load_task_payload  # noqa: E402


def _make_product(path: Path) -> None:
    image = Image.new("RGB", (220, 180), (246, 246, 246))
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 24, 200, 140), fill=(240, 190, 20), outline=(45, 45, 45), width=4)
    draw.rectangle((48, 105, 172, 150), fill=(240, 190, 20), outline=(45, 45, 45), width=4)
    image.save(path, format="PNG")


def _task(job_id: str, parameters: dict) -> GenerationTaskInput:
    return GenerationTaskInput(
        jobId=job_id,
        type="image_generation",
        tenantId="smoke-tenant",
        traceId=f"trace-{job_id}",
        modelProfileId="sd15-smoke",
        workflowVersion="smoke",
        parameters={
            "product_name": "industrial safety helmet",
            "product_category": "head protection",
            "scene": "clean industrial warehouse marketing background",
            "style": "realistic commercial PPE product photography",
            "size": "512x512",
            "output_format": "png",
            "sync": True,
            **parameters,
        },
    )


async def main() -> None:
    original_generate = routes.generate_ai_image
    original_settings = {
        name: getattr(settings, name)
        for name in ("storage_dir", "input_dir", "output_dir", "task_dir", "ai_engine", "storage_backend")
    }

    with tempfile.TemporaryDirectory(prefix="scene-generation-smoke-") as temp_dir:
        root = Path(temp_dir)
        settings.storage_dir = root / "storage"
        settings.input_dir = settings.storage_dir / "inputs"
        settings.output_dir = settings.storage_dir / "outputs"
        settings.task_dir = settings.storage_dir / "tasks"
        settings.ai_engine = "mock"
        settings.storage_backend = "local"

        product_path = root / "helmet.png"
        _make_product(product_path)
        captured: dict[str, object] = {}

        async def fake_generate(
            task_id: str,
            prompt: str,
            size: str,
            output_format: str = "png",
            product_image_path: Path | None = None,
            **kwargs: object,
        ) -> tuple[Path, Path, str]:
            captured[task_id] = {
                "prompt": prompt,
                "product_image_path": str(product_image_path) if product_image_path else None,
                "generation_mode": kwargs.get("generation_mode"),
            }
            output_dir = settings.output_dir / task_id
            output_dir.mkdir(parents=True, exist_ok=True)
            image_path = output_dir / f"result.{output_format}"
            Image.open(product_image_path).convert("RGB").save(image_path, format=output_format.upper())
            metadata_path = output_dir / "metadata.json"
            metadata_path.write_text(json.dumps({"engine": "mock"}), encoding="utf-8")
            return image_path, metadata_path, "mock"

        routes.generate_ai_image = fake_generate

        async def execute(task: GenerationTaskInput) -> dict:
            create_task(f"ai.business_{task.type}", task.model_dump(mode="json"), task_id=task.jobId)
            await routes._run_business_generate_task(task)
            record = load_task(task.jobId)
            payload = load_task_payload(task.jobId)
            assert record is not None, "task record missing"
            assert payload is not None, "task payload missing"
            return {"record": record, "payload": payload}

        try:
            scene_task = await execute(
                _task(
                    "scene-generation-success",
                    {
                        "generation_mode": "scene_generation",
                        "product_image": {"local_path": str(product_path)},
                    },
                )
            )
            assert scene_task["record"].status == TaskStatus.succeeded
            assert scene_task["payload"]["generation_mode"] == "scene_generation"
            assert scene_task["payload"]["scene_generation_used"] is True
            assert scene_task["payload"]["product_reference_used"] is True
            assert scene_task["payload"]["denoise"] == settings.comfyui_scene_generation_denoise
            assert scene_task["payload"]["business_protocol"]["scene"] == "clean industrial warehouse marketing background"
            assert scene_task["payload"]["business_protocol"]["style"] == "realistic commercial PPE product photography"
            assert scene_task["payload"]["business_protocol"]["denoise"] == settings.comfyui_scene_generation_denoise
            assert captured["scene-generation-success"]["generation_mode"] == "scene_generation"
            assert captured["scene-generation-success"]["product_image_path"] == str(product_path)
            assert "exactly one industrial safety helmet" in str(captured["scene-generation-success"]["prompt"])

            missing_product = await execute(
                _task("scene-generation-missing-product", {"generation_mode": "scene_generation"})
            )
            assert missing_product["record"].status == TaskStatus.failed
            assert missing_product["payload"]["business_error"]["errorCode"] == "AI_400_INPUT_INVALID"

            normal_task = await execute(
                _task("scene-generation-normal-regression", {"product_image": {"local_path": str(product_path)}})
            )
            assert normal_task["record"].status == TaskStatus.succeeded
            assert normal_task["payload"]["generation_mode"] is None
            assert normal_task["payload"]["scene_generation_used"] is False
            assert captured["scene-generation-normal-regression"]["generation_mode"] is None
        finally:
            routes.generate_ai_image = original_generate
            for name, value in original_settings.items():
                setattr(settings, name, value)

    print("SCENE_GENERATION_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
