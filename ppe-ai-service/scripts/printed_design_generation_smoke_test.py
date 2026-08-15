from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.api import routes
from app.core.config import settings
from app.schemas.business_protocol import GenerationTaskInput
from app.schemas.tasks import TaskStatus
from app.services.task_store import create_task, load_task, load_task_payload


def _create_inputs(test_root: Path) -> tuple[Path, Path]:
    input_dir = test_root / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    base_path = input_dir / "base.png"
    logo_path = input_dir / "logo.png"

    base = Image.new("RGBA", (160, 100), (235, 235, 235, 255))
    ImageDraw.Draw(base).rectangle((10, 10, 150, 90), outline=(40, 80, 120, 255), width=3)
    base.save(base_path, format="PNG")

    logo = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    ImageDraw.Draw(logo).rectangle((0, 0, 39, 19), fill=(220, 30, 30, 220))
    logo.save(logo_path, format="PNG")
    return base_path, logo_path


def _build_task(job_id: str, base_path: Path, logo_path: Path | None) -> GenerationTaskInput:
    parameters = {
        "product_name": "工业安全帽",
        "product_category": "个人防护/头部防护/安全帽",
        "scene": "干净的工业产品展示背景",
        "style": "真实商业产品图风格",
        "size": "512x512",
        "output_format": "png",
        "sync": True,
        "product_image": {"local_path": str(base_path)},
        "position_x_ratio": 0.5,
        "position_y_ratio": 0.5,
        "logo_width_ratio": 0.25,
        "opacity": 0.8,
    }
    if logo_path is not None:
        parameters["logo_image"] = {"local_path": str(logo_path)}
    return GenerationTaskInput(
        jobId=job_id,
        taskType="image_generation",
        tenantId="smoke-tenant",
        traceId=f"trace-{job_id}",
        modelProfileId="smoke-model",
        workflowVersion="smoke-workflow",
        parameters=parameters,
    )


async def main() -> None:
    temporary_output = tempfile.TemporaryDirectory(prefix="ppe-printed-design-smoke-")
    test_root = Path(temporary_output.name)
    base_path, logo_path = _create_inputs(test_root)
    captured_inputs: dict[str, Path | None] = {}

    async def fake_generate(
        task_id: str,
        prompt: str,
        size: str,
        output_format: str = "png",
        product_image_path: Path | None = None,
    ) -> tuple[Path, Path, str]:
        del prompt, size, output_format
        captured_inputs[task_id] = product_image_path
        output_dir = settings.output_dir / task_id
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / "result.png"
        metadata_path = output_dir / "metadata.json"
        if product_image_path is None:
            Image.new("RGB", (160, 100), "white").save(image_path, format="PNG")
        else:
            with Image.open(product_image_path) as source:
                source.convert("RGBA").save(image_path, format="PNG")
        metadata_path.write_text(
            json.dumps({"engine": "printed-design-smoke", "input_path": str(product_image_path)}, ensure_ascii=False),
            encoding="utf-8",
        )
        return image_path, metadata_path, "smoke"

    original_generate = routes.generate_ai_image
    original_output_dir = settings.output_dir
    original_input_dir = settings.input_dir
    original_task_dir = settings.task_dir
    original_storage_backend = settings.storage_backend
    settings.output_dir = test_root / "outputs"
    settings.input_dir = test_root / "validated_inputs"
    settings.task_dir = test_root / "tasks"
    settings.storage_backend = "local"
    routes.generate_ai_image = fake_generate
    try:
        with_logo = _build_task("printed-design-with-logo", base_path, logo_path)
        create_task("ai.business_generate", with_logo.model_dump(mode="json"), task_id=with_logo.jobId)
        await routes._run_business_generate_task(with_logo)
        with_logo_record = load_task(with_logo.jobId)
        with_logo_payload = load_task_payload(with_logo.jobId) or {}
        assert with_logo_record is not None and with_logo_record.status == TaskStatus.succeeded
        assert with_logo_payload["printed_design_used"] is True
        printed_path = Path(with_logo_payload["printed_design"]["path"])
        assert printed_path.exists() and printed_path.name == "printed_design.png"
        assert captured_inputs[with_logo.jobId] == printed_path
        final_metadata = json.loads(Path(with_logo_record.metadata_path).read_text(encoding="utf-8"))
        assert final_metadata["printed_design_used"] is True
        assert final_metadata["printed_design"]["path"] == str(printed_path)

        without_logo = _build_task("printed-design-without-logo", base_path, None)
        create_task("ai.business_generate", without_logo.model_dump(mode="json"), task_id=without_logo.jobId)
        await routes._run_business_generate_task(without_logo)
        without_logo_record = load_task(without_logo.jobId)
        without_logo_payload = load_task_payload(without_logo.jobId) or {}
        assert without_logo_record is not None and without_logo_record.status == TaskStatus.succeeded
        assert without_logo_payload["printed_design_used"] is False
        assert captured_inputs[without_logo.jobId] == base_path
    finally:
        routes.generate_ai_image = original_generate
        settings.output_dir = original_output_dir
        settings.input_dir = original_input_dir
        settings.task_dir = original_task_dir
        settings.storage_backend = original_storage_backend
        temporary_output.cleanup()

    print("PRINTED_DESIGN_GENERATION_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
