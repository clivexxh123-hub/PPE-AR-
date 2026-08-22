"""Targeted smoke checks for runtime engine and effective denoise metadata."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.routes import _append_output_metadata, _business_extra, _requested_denoise  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.business_protocol import GenerationTaskInput  # noqa: E402
from app.services.comfyui_engine import resolve_generation_denoise  # noqa: E402


def _task() -> GenerationTaskInput:
    return GenerationTaskInput(
        jobId="runtime-metadata-smoke",
        type="image_generation",
        tenantId="local-smoke",
        traceId="trace-runtime-metadata-smoke",
        modelProfileId="local-test-profile",
        workflowVersion="local-test-v1",
        parameters={"denoise": 0.42},
    )


def main() -> None:
    original_engine = settings.ai_engine
    original_default_denoise = settings.comfyui_denoise
    try:
        with TestClient(app) as client:
            settings.ai_engine = "mock"
            assert client.get("/health").json()["engine"] == "mock"
            settings.ai_engine = "comfyui"
            assert client.get("/health").json()["engine"] == "comfyui"

        settings.comfyui_denoise = 0.6
        assert _requested_denoise(_task().parameters) == 0.42
        assert resolve_generation_denoise("image_to_image", "image_to_image") == 0.6
        assert resolve_generation_denoise("image_to_image", "image_to_image", 0.42) == 0.42
        assert resolve_generation_denoise("human_wearing", "image_to_image") == 0.15
        assert resolve_generation_denoise("text_to_image", "text_to_image") is None

        business_metadata = _business_extra(_task(), actual_denoise=0.42)
        assert business_metadata["denoise"] == 0.42
        assert business_metadata["business_protocol"]["denoise"] == 0.42

        with tempfile.TemporaryDirectory(prefix="ppe-runtime-metadata-") as temp_dir:
            metadata_path = Path(temp_dir) / "metadata.json"
            metadata_path.write_text(
                json.dumps({"engine": "comfyui", "denoise": 0.42}),
                encoding="utf-8",
            )
            _append_output_metadata(metadata_path, {"denoise": None, "business_protocol": {"denoise": 0.42}})
            final_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            assert final_metadata["denoise"] == 0.42
            assert final_metadata["business_protocol"]["denoise"] == 0.42
    finally:
        settings.ai_engine = original_engine
        settings.comfyui_denoise = original_default_denoise

    print("runtime metadata smoke test passed")


if __name__ == "__main__":
    main()
