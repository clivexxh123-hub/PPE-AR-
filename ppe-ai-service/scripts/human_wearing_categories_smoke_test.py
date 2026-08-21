"""Deterministic compatibility coverage for non-helmet human_wearing PPE fixtures.

Fixtures are synthetic technical assets, not commercial-quality validation images.
"""

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
from app.services.comfyui_engine import prepare_img2img_input  # noqa: E402
from app.services.task_store import create_task, load_task, load_task_payload  # noqa: E402


def _make_human(path: Path) -> None:
    image = Image.new("RGB", (360, 300), (210, 220, 225))
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 145, 270, 300), fill=(60, 92, 116))
    draw.ellipse((125, 40, 235, 165), fill=(224, 175, 135))
    draw.rectangle((118, 86, 242, 109), fill=(45, 45, 45))
    image.save(path, format="PNG")


def _make_goggles(path: Path, *, transparent: bool = True) -> None:
    image = Image.new("RGBA", (180, 70), (0, 0, 0, 0) if transparent else (40, 40, 40, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 16, 82, 52), radius=8, outline=(25, 70, 140, 255), width=7)
    draw.rounded_rectangle((98, 16, 160, 52), radius=8, outline=(25, 70, 140, 255), width=7)
    draw.rectangle((82, 30, 98, 38), fill=(25, 70, 140, 255))
    image.save(path, format="PNG")


def _make_gloves(path: Path) -> None:
    image = Image.new("RGBA", (150, 130), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((45, 45, 112, 122), radius=12, fill=(230, 155, 30, 255))
    for index in range(4):
        x = 40 + index * 18
        draw.rounded_rectangle((x, 12, x + 16, 68), radius=8, fill=(230, 155, 30, 255))
    draw.rounded_rectangle((15, 48, 62, 72), radius=10, fill=(230, 155, 30, 255))
    image.save(path, format="PNG")


def _task(job_id: str, product_name: str, category: str, human_path: Path, ppe_path: Path, extra: dict | None = None) -> GenerationTaskInput:
    return GenerationTaskInput(
        jobId=job_id,
        type="image_generation",
        tenantId="smoke-tenant",
        traceId=f"trace-{job_id}",
        modelProfileId="mock-img2img",
        workflowVersion="human-wearing-category-mvp",
        parameters={
            "product_name": product_name,
            "product_category": category,
            "scene": "synthetic technical compatibility fixture",
            "style": "technical test composite",
            "size": "512x512",
            "output_format": "png",
            "generation_mode": "human_wearing",
            "human_reference": {"local_path": str(human_path)},
            "ppe_reference": {"local_path": str(ppe_path)},
            "sync": True,
            **(extra or {}),
        },
    )


async def main() -> None:
    original_generate = routes.generate_ai_image
    original_settings = {
        name: getattr(settings, name)
        for name in ("storage_dir", "input_dir", "output_dir", "task_dir", "ai_engine", "storage_backend")
    }
    with tempfile.TemporaryDirectory(prefix="human-wearing-categories-") as temp_dir:
        root = Path(temp_dir)
        settings.storage_dir = root / "storage"
        settings.input_dir = settings.storage_dir / "inputs"
        settings.output_dir = settings.storage_dir / "outputs"
        settings.task_dir = settings.storage_dir / "tasks"
        settings.ai_engine = "mock"
        settings.storage_backend = "local"
        human_path = root / "synthetic-human.png"
        goggles_path = root / "synthetic-goggles.png"
        gloves_path = root / "synthetic-gloves.png"
        opaque_goggles_path = root / "synthetic-opaque-goggles.png"
        _make_human(human_path)
        _make_goggles(goggles_path)
        _make_gloves(gloves_path)
        _make_goggles(opaque_goggles_path, transparent=False)
        captured: dict[str, dict[str, object]] = {}

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
            metadata_path.write_text(json.dumps({"engine": "mock-img2img"}), encoding="utf-8")
            return image_path, metadata_path, "mock"

        async def execute(task: GenerationTaskInput) -> tuple[dict, dict]:
            create_task(f"ai.business_{task.type}", task.model_dump(mode="json"), task_id=task.jobId)
            await routes._run_business_generate_task(task)
            record = load_task(task.jobId)
            payload = load_task_payload(task.jobId)
            assert record is not None and payload is not None
            return record.model_dump(), payload

        routes.generate_ai_image = fake_generate
        try:
            cases = (
                ("goggles", "industrial safety goggles", "eye protection", goggles_path, 0.31, 0.30),
                ("gloves", "protective work gloves", "hand protection", gloves_path, 0.57, 0.36),
            )
            for name, product, category, ppe_path, expected_y, expected_width in cases:
                record, payload = await execute(_task(f"human-wearing-{name}", product, category, human_path, ppe_path))
                assert record["status"] == TaskStatus.succeeded
                assert payload["human_wearing_used"] is True
                validation = payload["input_asset_validation"]
                assert validation["ppe_reference"]["has_alpha"] is True
                composite = payload["printed_design"]
                assert composite["human_wearing_placement_profile"] == name
                assert composite["position_y_ratio"] == expected_y
                assert composite["ppe_width_ratio"] == expected_width
                composite_path = Path(composite["path"])
                assert composite_path.exists()
                assert captured[f"human-wearing-{name}"]["generation_mode"] == "human_wearing"
                assert captured[f"human-wearing-{name}"]["product_image_path"] == str(composite_path)
                prepared_path = root / f"prepared-{name}.png"
                details = prepare_img2img_input(composite_path, "512x512", prepared_path)
                assert prepared_path.exists() and details["processed_width"] == 512 and details["processed_height"] == 512
                composite_metadata = json.loads(Path(composite["metadata_path"]).read_text(encoding="utf-8"))
                assert composite_metadata["human_wearing_placement_profile"] == name
                output_metadata = json.loads(Path(record["metadata_path"]).read_text(encoding="utf-8"))
                assert output_metadata["printed_design"]["human_wearing_placement_profile"] == name

            manual_record, manual_payload = await execute(
                _task(
                    "human-wearing-goggles-manual",
                    "industrial safety goggles",
                    "eye protection",
                    human_path,
                    goggles_path,
                    {"position_y_ratio": 0.40, "ppe_width_ratio": 0.24, "opacity": 0.75},
                )
            )
            assert manual_record["status"] == TaskStatus.succeeded
            manual_composite = manual_payload["printed_design"]
            assert manual_composite["human_wearing_placement_profile"] == "goggles"
            assert manual_composite["position_y_ratio"] == 0.40
            assert manual_composite["ppe_width_ratio"] == 0.24
            assert manual_composite["opacity"] == 0.75
            assert set(manual_composite["human_wearing_manual_override_fields"]) == {
                "opacity",
                "position_y_ratio",
                "ppe_width_ratio",
            }

            invalid_record, invalid_payload = await execute(
                _task(
                    "human-wearing-goggles-invalid-alpha",
                    "industrial safety goggles",
                    "eye protection",
                    human_path,
                    opaque_goggles_path,
                )
            )
            assert invalid_record["status"] == TaskStatus.failed
            assert invalid_payload["business_error"]["errorCode"] == "AI_400_INPUT_INVALID"
        finally:
            routes.generate_ai_image = original_generate
            for name, value in original_settings.items():
                setattr(settings, name, value)

    print("HUMAN_WEARING_CATEGORIES_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
