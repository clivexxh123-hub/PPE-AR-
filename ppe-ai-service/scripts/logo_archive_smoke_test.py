"""Local smoke coverage for SHA-256 Logo archive and Logo metadata links."""

from __future__ import annotations

import asyncio
import hashlib
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
from app.services.logo_archive_service import archive_logo_asset  # noqa: E402
from app.services.logo_service import normalize_logo  # noqa: E402
from app.services.task_store import create_task, load_task  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _create_inputs(root: Path) -> tuple[Path, Path, Path]:
    inputs = root / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    original = inputs / "original-logo.jpg"
    different = inputs / "different-logo.jpg"
    base = inputs / "base.png"
    logo = Image.new("RGB", (180, 120), "white")
    ImageDraw.Draw(logo).rounded_rectangle((35, 30, 145, 90), radius=12, fill=(11, 103, 194))
    logo.save(original, format="JPEG")
    different_logo = Image.new("RGB", (180, 120), "white")
    ImageDraw.Draw(different_logo).ellipse((45, 25, 135, 95), fill=(210, 45, 45))
    different_logo.save(different, format="JPEG")
    Image.new("RGBA", (220, 140), (245, 245, 245, 255)).save(base, format="PNG")
    return original, different, base


def _task(job_id: str, task_type: str, original: Path, base: Path | None = None) -> GenerationTaskInput:
    parameters = {"logo_image": {"local_path": str(original)}, "output_format": "png", "sync": True}
    if base is not None:
        parameters["base_image"] = {"local_path": str(base)}
        parameters.update({"position_x_ratio": 0.5, "position_y_ratio": 0.5, "logo_width_ratio": 0.25})
    return GenerationTaskInput(
        jobId=job_id,
        type=task_type,
        tenantId="smoke-tenant",
        traceId=f"trace-{job_id}",
        modelProfileId="local",
        workflowVersion="logo-archive-mvp",
        parameters=parameters,
    )


async def _execute(task: GenerationTaskInput) -> dict:
    create_task(f"ai.business_{task.type}", task.model_dump(mode="json"), task_id=task.jobId)
    await routes._run_business_logo_task(task)
    record = load_task(task.jobId)
    assert record is not None
    return record.model_dump()


async def main() -> None:
    original_settings = {
        name: getattr(settings, name)
        for name in ("storage_dir", "input_dir", "output_dir", "task_dir", "storage_backend")
    }
    with tempfile.TemporaryDirectory(prefix="logo-archive-smoke-") as temp_dir:
        root = Path(temp_dir)
        settings.storage_dir = root / "storage"
        settings.input_dir = settings.storage_dir / "inputs"
        settings.output_dir = settings.storage_dir / "outputs"
        settings.task_dir = settings.storage_dir / "tasks"
        settings.storage_backend = "local"
        original, different, base = _create_inputs(root)
        try:
            original_asset = archive_logo_asset(original, "original")
            assert original_asset.sha256 == _sha256(original)
            assert original_asset.asset_id == f"logo-sha256:{_sha256(original)}"
            assert Path(original_asset.archive_path).exists()
            assert Path(original_asset.archive_path).parts[-4:-1] == ("logo_archive", _sha256(original)[:2], _sha256(original))
            duplicate_asset = archive_logo_asset(original, "original")
            assert duplicate_asset.asset_id == original_asset.asset_id
            assert duplicate_asset.archive_path == original_asset.archive_path
            assert len(list((settings.storage_dir / "logo_archive" / _sha256(original)[:2]).glob("*/asset.bin"))) == 1
            different_asset = archive_logo_asset(different, "original")
            assert different_asset.asset_id != original_asset.asset_id
            assert different_asset.sha256 == _sha256(different)

            transparent_path, _ = normalize_logo("transparent-fixture", original)
            transparent_asset = archive_logo_asset(transparent_path, "transparent")
            assert transparent_asset.sha256 == _sha256(transparent_path)
            assert transparent_asset.file_format == "PNG"
            assert transparent_asset.asset_id != original_asset.asset_id

            remove_record = await _execute(_task("logo-archive-remove", "logo_remove_bg", original))
            assert remove_record["status"] == TaskStatus.succeeded
            remove_metadata = json.loads(Path(remove_record["metadata_path"]).read_text(encoding="utf-8"))
            assert remove_metadata["logo_original_asset"]["asset_id"] == original_asset.asset_id
            assert remove_metadata["logo_transparent_asset"]["sha256"] == _sha256(Path(remove_record["output_path"]))
            assert "original" in remove_metadata["logo_original_asset"]["asset_types"]
            assert "transparent" in remove_metadata["logo_transparent_asset"]["asset_types"]

            print_record = await _execute(_task("logo-archive-print", "print_render", original, base))
            assert print_record["status"] == TaskStatus.succeeded
            print_metadata = json.loads(Path(print_record["metadata_path"]).read_text(encoding="utf-8"))
            assert print_metadata["logo_used_asset"]["asset_id"] == original_asset.asset_id
            assert "used_in_print_render" in print_metadata["logo_used_asset"]["asset_types"]
        finally:
            for name, value in original_settings.items():
                setattr(settings, name, value)

    print("LOGO_ARCHIVE_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
