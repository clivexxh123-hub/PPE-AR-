"""Minimal regression coverage for the scene_generation task mode."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
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
from app.services.comfyui_engine import prepare_img2img_input  # noqa: E402
from app.services.task_store import create_task, load_task, load_task_payload  # noqa: E402


def _make_product(path: Path) -> None:
    image = Image.new("RGBA", (220, 180), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 24, 200, 140), fill=(240, 190, 20, 255), outline=(45, 45, 45, 255), width=4)
    draw.rectangle((48, 105, 172, 150), fill=(240, 190, 20, 255), outline=(45, 45, 45, 255), width=4)
    image.save(path, format="PNG")


def _make_opaque_product(path: Path) -> None:
    Image.new("RGB", (220, 180), (240, 190, 20)).save(path, format="PNG")


def _make_scene_reference(path: Path) -> None:
    image = Image.new("RGB", (640, 360), (28, 92, 132))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 180, 640, 360), fill=(72, 118, 66))
    draw.rectangle((40, 35, 210, 160), fill=(190, 205, 215))
    image.save(path, format="PNG")


def _verify_img2img_input_sizing(root: Path) -> None:
    source_path = root / "large-helmet.png"
    prepared_path = root / "prepared-img2img-input.png"
    Image.new("RGB", (2048, 1024), (240, 190, 20)).save(source_path, format="PNG")

    details = prepare_img2img_input(source_path, "512x512", prepared_path)
    with Image.open(prepared_path) as prepared:
        assert prepared.size == (512, 512)

    assert details["original_width"] == 2048
    assert details["original_height"] == 1024
    assert details["processed_width"] == 512
    assert details["processed_height"] == 512
    assert details["content_width"] == 512
    assert details["content_height"] == 256


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
        _verify_img2img_input_sizing(root)
        settings.storage_dir = root / "storage"
        settings.input_dir = settings.storage_dir / "inputs"
        settings.output_dir = settings.storage_dir / "outputs"
        settings.task_dir = settings.storage_dir / "tasks"
        settings.ai_engine = "mock"
        settings.storage_backend = "local"

        product_path = root / "helmet.png"
        scene_reference_path = root / "warehouse-reference.png"
        _make_product(product_path)
        _make_scene_reference(scene_reference_path)
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
            if product_image_path is None:
                Image.new("RGB", (512, 512), (84, 102, 116)).save(image_path, format=output_format.upper())
            else:
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
            assert scene_task["payload"]["scene_generation_strategy"] == "generated_background_composite"
            assert scene_task["payload"]["background_generated"] is True
            assert scene_task["payload"]["product_composited"] is True
            assert scene_task["payload"]["denoise"] is None
            assert scene_task["payload"]["business_protocol"]["scene"] == "clean industrial warehouse marketing background"
            assert scene_task["payload"]["business_protocol"]["style"] == "realistic commercial PPE product photography"
            assert captured["scene-generation-success-scene-background"]["generation_mode"] == "scene_generation"
            assert captured["scene-generation-success-scene-background"]["product_image_path"] is None
            assert "empty foreground space" in str(captured["scene-generation-success-scene-background"]["prompt"])

            reference_scene = await execute(
                _task(
                    "scene-generation-reference",
                    {
                        "generation_mode": "scene_generation",
                        "product_image": {"local_path": str(product_path)},
                        "scene_reference": {"local_path": str(scene_reference_path)},
                    },
                )
            )
            assert reference_scene["record"].status == TaskStatus.succeeded
            reference_payload = reference_scene["payload"]
            assert reference_payload["scene_generation_strategy"] == "reference_background_composite"
            assert reference_payload["background_generated"] is False
            assert reference_payload["product_composited"] is True
            assert reference_payload["scene_reference_used"] is True
            assert reference_payload["input_asset_validation"]["scene_reference"]["validation_status"] == "passed"
            assert "scene-generation-reference-scene-background" not in captured
            reference_metadata = json.loads(
                Path(reference_scene["record"].metadata_path).read_text(encoding="utf-8")
            )
            assert reference_metadata["scene_reference_used"] is True
            assert reference_metadata["printed_design"]["scene_reference_path"] == str(scene_reference_path)
            with Image.open(reference_scene["record"].output_path) as result_image:
                # The upper-left reference color survives cover-resize, proving
                # the supplied scene is part of the final pixels.
                assert result_image.convert("RGB").getpixel((5, 5)) == (28, 92, 132)
            visual_output = os.environ.get("PPE_VISUAL_OUTPUT_DIR")
            if visual_output:
                target_dir = Path(visual_output)
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(reference_scene["record"].output_path, target_dir / "scene_reference_composite.png")

            missing_product = await execute(
                _task("scene-generation-missing-product", {"generation_mode": "scene_generation"})
            )
            assert missing_product["record"].status == TaskStatus.failed
            assert missing_product["payload"]["business_error"]["errorCode"] == "AI_400_INPUT_INVALID"

            opaque_product_path = root / "opaque-helmet.png"
            _make_opaque_product(opaque_product_path)
            opaque_product = await execute(
                _task(
                    "scene-generation-opaque-product",
                    {
                        "generation_mode": "scene_generation",
                        "product_image": {"local_path": str(opaque_product_path)},
                    },
                )
            )
            assert opaque_product["record"].status == TaskStatus.failed
            assert opaque_product["payload"]["business_error"]["errorCode"] == "AI_400_INPUT_INVALID"

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
