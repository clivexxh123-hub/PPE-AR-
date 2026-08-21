"""Minimal regression coverage for the human_wearing task mode."""

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


def _make_human(path: Path) -> None:
    image = Image.new("RGB", (320, 240), (210, 220, 225))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 120, 240, 240), fill=(65, 95, 120))
    draw.ellipse((115, 35, 205, 130), fill=(224, 175, 135))
    draw.rectangle((108, 75, 212, 98), fill=(45, 45, 45))
    image.save(path, format="PNG")


def _make_ppe(path: Path, *, transparent: bool) -> None:
    image = Image.new("RGBA", (180, 100), (0, 0, 0, 0) if transparent else (240, 190, 20, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((12, 8, 168, 82), fill=(240, 190, 20, 255))
    draw.rectangle((18, 55, 162, 90), fill=(240, 190, 20, 255))
    draw.rectangle((62, 78, 118, 96), fill=(45, 45, 45, 255))
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
            "scene": "clean industrial background",
            "style": "realistic commercial PPE marketing photo",
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

    with tempfile.TemporaryDirectory(prefix="human-wearing-smoke-") as temp_dir:
        root = Path(temp_dir)
        settings.storage_dir = root / "storage"
        settings.input_dir = settings.storage_dir / "inputs"
        settings.output_dir = settings.storage_dir / "outputs"
        settings.task_dir = settings.storage_dir / "tasks"
        settings.ai_engine = "mock"
        settings.storage_backend = "local"

        human_path = root / "human.png"
        ppe_path = root / "ppe.png"
        opaque_ppe_path = root / "opaque-ppe.png"
        _make_human(human_path)
        _make_ppe(ppe_path, transparent=True)
        _make_ppe(opaque_ppe_path, transparent=False)

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
            if product_image_path:
                Image.open(product_image_path).convert("RGB").save(image_path, format=output_format.upper())
            else:
                Image.new("RGB", (512, 512), (245, 245, 245)).save(image_path, format=output_format.upper())
            metadata_path = output_dir / "metadata.json"
            metadata_path.write_text(json.dumps({"engine": "mock"}), encoding="utf-8")
            return image_path, metadata_path, "mock"

        routes.generate_ai_image = fake_generate

        async def execute(task: GenerationTaskInput) -> dict:
            record = create_task(f"ai.business_{task.type}", task.model_dump(mode="json"), task_id=task.jobId)
            await routes._run_business_generate_task(task)
            saved = load_task(task.jobId)
            payload = load_task_payload(task.jobId)
            assert saved is not None, f"task record missing: {task.jobId}"
            assert payload is not None, f"task payload missing: {task.jobId}"
            return {"record": saved, "payload": payload, "created": record}

        try:
            success = await execute(
                _task(
                    "human-wearing-success",
                    {
                        "generation_mode": "human_wearing",
                        "human_reference": {"local_path": str(human_path)},
                        "ppe_reference": {"local_path": str(ppe_path)},
                        "view": "front",
                        "framing": "half_body",
                    },
                )
            )
            assert success["record"].status == TaskStatus.succeeded
            assert success["payload"]["generation_mode"] == "human_wearing"
            assert success["payload"]["human_wearing_used"] is True
            printed_design = success["payload"]["printed_design"]
            assert printed_design["human_wearing_used"] is True
            assert Path(printed_design["path"]).exists()
            validation = success["payload"]["input_asset_validation"]
            assert validation["ppe_reference"]["has_alpha"] is True
            assert captured["human-wearing-success"]["generation_mode"] == "human_wearing"
            assert captured["human-wearing-success"]["product_image_path"] == printed_design["path"]
            assert "front-facing person" in captured["human-wearing-success"]["prompt"]
            output_metadata = json.loads(Path(success["record"].metadata_path).read_text(encoding="utf-8"))
            assert output_metadata["view"] == "front"
            assert output_metadata["framing"] == "half_body"
            assert output_metadata["prompt_template_id"] == "ppe_human_wearing"

            missing_human = await execute(
                _task(
                    "human-wearing-missing-human",
                    {
                        "generation_mode": "human_wearing",
                        "ppe_reference": {"local_path": str(ppe_path)},
                    },
                )
            )
            assert missing_human["record"].status == TaskStatus.failed
            assert missing_human["payload"]["business_error"]["errorCode"] == "AI_400_INPUT_INVALID"

            missing_ppe = await execute(
                _task(
                    "human-wearing-missing-ppe",
                    {
                        "generation_mode": "human_wearing",
                        "human_reference": {"local_path": str(human_path)},
                    },
                )
            )
            assert missing_ppe["record"].status == TaskStatus.failed
            assert missing_ppe["payload"]["business_error"]["errorCode"] == "AI_400_INPUT_INVALID"

            invalid_alpha = await execute(
                _task(
                    "human-wearing-invalid-alpha",
                    {
                        "generation_mode": "human_wearing",
                        "human_reference": {"local_path": str(human_path)},
                        "ppe_reference": {"local_path": str(opaque_ppe_path)},
                    },
                )
            )
            assert invalid_alpha["record"].status == TaskStatus.failed
            assert invalid_alpha["payload"]["business_error"]["errorCode"] == "AI_400_INPUT_INVALID"

            normal = await execute(_task("human-wearing-normal-regression", {}))
            assert normal["record"].status == TaskStatus.succeeded
            assert normal["payload"]["human_wearing_used"] is False
            assert normal["payload"]["generation_mode"] is None
            assert captured["human-wearing-normal-regression"]["generation_mode"] is None
        finally:
            routes.generate_ai_image = original_generate
            for name, value in original_settings.items():
                setattr(settings, name, value)

    print("HUMAN_WEARING_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
