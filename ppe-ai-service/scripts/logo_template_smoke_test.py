"""Smoke coverage for local Logo placement template save/load and print_render."""

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
from app.services.logo_template_store import load_logo_template, save_logo_template  # noqa: E402
from app.services.task_store import create_task, load_task, load_task_payload  # noqa: E402


def _create_inputs(root: Path) -> tuple[Path, Path]:
    base_path = root / "inputs" / "base.png"
    logo_path = root / "inputs" / "logo.png"
    base_path.parent.mkdir(parents=True, exist_ok=True)
    base = Image.new("RGBA", (200, 120), (245, 245, 245, 255))
    ImageDraw.Draw(base).rounded_rectangle((30, 18, 170, 102), radius=16, fill=(245, 190, 36, 255))
    base.save(base_path, format="PNG")
    logo = Image.new("RGBA", (80, 40), (0, 0, 0, 0))
    ImageDraw.Draw(logo).rounded_rectangle((2, 2, 77, 37), radius=5, fill=(28, 78, 190, 230))
    logo.save(logo_path, format="PNG")
    return base_path, logo_path


def _task(job_id: str, base_path: Path, logo_path: Path, placement: dict) -> GenerationTaskInput:
    return GenerationTaskInput(
        jobId=job_id,
        type="print_render",
        tenantId="smoke-tenant",
        traceId=f"trace-{job_id}",
        modelProfileId="mock",
        workflowVersion="logo-template-mvp",
        parameters={
            "base_image": {"local_path": str(base_path)},
            "logo_image": {"local_path": str(logo_path)},
            "output_format": "png",
            "sync": True,
            **placement,
        },
    )


async def _execute(task: GenerationTaskInput) -> tuple[dict, dict]:
    create_task(f"ai.business_{task.type}", task.model_dump(mode="json"), task_id=task.jobId)
    await routes._run_business_logo_task(task)
    record = load_task(task.jobId)
    payload = load_task_payload(task.jobId)
    assert record is not None and payload is not None
    return record.model_dump(), payload


def _metadata(record: dict) -> dict:
    return json.loads(Path(record["metadata_path"]).read_text(encoding="utf-8"))


async def main() -> None:
    original_settings = {
        name: getattr(settings, name)
        for name in ("storage_dir", "input_dir", "output_dir", "task_dir", "storage_backend")
    }
    with tempfile.TemporaryDirectory(prefix="logo-template-smoke-") as temp_dir:
        root = Path(temp_dir)
        settings.storage_dir = root / "storage"
        settings.input_dir = settings.storage_dir / "inputs"
        settings.output_dir = settings.storage_dir / "outputs"
        settings.task_dir = settings.storage_dir / "tasks"
        settings.storage_backend = "local"
        base_path, logo_path = _create_inputs(root)
        try:
            saved = save_logo_template(
                "brand-corner-v1",
                {
                    "position_x_ratio": 0.70,
                    "position_y_ratio": 0.20,
                    "logo_width_ratio": 0.24,
                    "opacity": 0.55,
                },
            )
            loaded = load_logo_template("brand-corner-v1")
            assert loaded == saved
            assert (settings.storage_dir / "logo_templates.json").exists()

            template_record, template_payload = await _execute(
                _task("logo-template-applied", base_path, logo_path, {"template_id": "brand-corner-v1"})
            )
            assert template_record["status"] == TaskStatus.succeeded
            template_metadata = _metadata(template_record)
            assert template_metadata["logo_template_id"] == "brand-corner-v1"
            assert template_metadata["logo_template_hit"] is True
            assert abs(template_metadata["final_placement"]["final_x_ratio"] - 0.70) < 0.02
            assert abs(template_metadata["final_placement"]["final_y_ratio"] - 0.20) < 0.02
            assert abs(template_metadata["final_placement"]["final_width_ratio"] - 0.24) < 0.01
            assert template_metadata["final_placement"]["opacity"] == 0.55
            assert template_payload["logo_template_id"] == "brand-corner-v1"

            manual_record, _ = await _execute(
                _task(
                    "logo-template-manual-overrides",
                    base_path,
                    logo_path,
                    {
                        "template_id": "brand-corner-v1",
                        "position_x_ratio": 0.10,
                        "position_y_ratio": 0.80,
                        "scale": 0.32,
                        "opacity": 0.90,
                    },
                )
            )
            manual_metadata = _metadata(manual_record)
            assert abs(manual_metadata["final_placement"]["final_x_ratio"] - 0.10) < 0.02
            assert abs(manual_metadata["final_placement"]["final_y_ratio"] - 0.80) < 0.02
            assert abs(manual_metadata["final_placement"]["final_width_ratio"] - 0.32) < 0.01
            assert manual_metadata["final_placement"]["opacity"] == 0.90
            assert set(manual_metadata["logo_template_manual_override_fields"]) == {
                "opacity",
                "position_x_ratio",
                "position_y_ratio",
                "scale",
            }

            named_position_record, _ = await _execute(
                _task(
                    "logo-template-named-position",
                    base_path,
                    logo_path,
                    {"template_id": "brand-corner-v1", "position": "bottom-right"},
                )
            )
            named_metadata = _metadata(named_position_record)
            assert named_metadata["final_placement"]["final_x_ratio"] > 0.90
            assert named_metadata["final_placement"]["final_y_ratio"] > 0.90

            legacy_record, _ = await _execute(_task("logo-template-legacy", base_path, logo_path, {}))
            legacy_metadata = _metadata(legacy_record)
            assert legacy_metadata["logo_template_id"] is None
            assert legacy_metadata["logo_template_hit"] is False
            assert legacy_metadata["placement_mode"] == "auto"

            unknown_record, _ = await _execute(
                _task("logo-template-unknown", base_path, logo_path, {"template_id": "missing-template"})
            )
            assert unknown_record["status"] == TaskStatus.failed
            assert "未知 Logo template_id" in str(unknown_record["error"])
        finally:
            for name, value in original_settings.items():
                setattr(settings, name, value)

    print("LOGO_TEMPLATE_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
