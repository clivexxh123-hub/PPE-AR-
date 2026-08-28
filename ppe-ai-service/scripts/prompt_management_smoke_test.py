"""Smoke coverage for the local PPE Prompt management MVP."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.prompt_templates import (  # noqa: E402
    HUMAN_WEARING_TEMPLATE_ID,
    PRODUCT_DISPLAY_TEMPLATE_ID,
    SCENE_MARKETING_TEMPLATE_ID,
    build_managed_prompt,
    list_prompt_template_ids,
)
from app.services.task_store import load_task_payload  # noqa: E402


def _assert_template_selection_and_overrides() -> None:
    assert set(list_prompt_template_ids()) == {
        PRODUCT_DISPLAY_TEMPLATE_ID,
        SCENE_MARKETING_TEMPLATE_ID,
        HUMAN_WEARING_TEMPLATE_ID,
    }

    default_prompt = build_managed_prompt("安全帽", "头部防护", "studio", "catalog")
    assert default_prompt.template_id == PRODUCT_DISPLAY_TEMPLATE_ID
    assert default_prompt.selection_rule == "generation_mode_default"

    scene_prompt = build_managed_prompt(
        "安全帽",
        "头部防护",
        "original scene",
        "original style",
        {"scene": "override warehouse", "style": "override cinematic", "audience": "PPE buyers"},
        template_id=SCENE_MARKETING_TEMPLATE_ID,
    )
    assert scene_prompt.template_id == SCENE_MARKETING_TEMPLATE_ID
    assert scene_prompt.selection_rule == "explicit_template_id"
    assert "override warehouse" in scene_prompt.prompt and "original scene" not in scene_prompt.prompt
    assert "override cinematic" in scene_prompt.prompt and "original style" not in scene_prompt.prompt
    assert "audience: PPE buyers" in scene_prompt.prompt

    human_prompt = build_managed_prompt(
        "reflective vest",
        "body protection",
        "construction site",
        "realistic",
        generation_mode="human_wearing",
    )
    assert human_prompt.template_id == HUMAN_WEARING_TEMPLATE_ID

    multi_product_prompt = build_managed_prompt(
        "升级加厚多口袋反光马甲、P10 安全帽、PVC 点塑手套",
        "反光马甲、头部防护、手部防护",
        "construction site",
        "realistic",
        generation_mode="human_wearing",
        view="front",
        framing="full_body",
    )
    assert "complete supplied PPE outfit" in multi_product_prompt.prompt
    assert "every supplied PPE reference" in multi_product_prompt.prompt
    assert "helmet on the crown" in multi_product_prompt.prompt
    assert "glove on each visible hand" in multi_product_prompt.prompt
    assert "safety vest" in multi_product_prompt.prompt

    compositions = {
        ("front", "half_body"),
        ("front", "full_body"),
        ("slight_side", "half_body"),
        ("slight_side", "full_body"),
    }
    prompts = {
        pair: build_managed_prompt(
            "安全帽",
            "头部防护",
            "site",
            "photo",
            generation_mode="human_wearing",
            view=pair[0],
            framing=pair[1],
        )
        for pair in compositions
    }
    assert len({result.prompt for result in prompts.values()}) == 4
    for (view, framing), result in prompts.items():
        assert result.template_id == HUMAN_WEARING_TEMPLATE_ID
        assert result.metadata()["view"] == view
        assert result.metadata()["framing"] == framing
        assert "Composition:" in result.prompt

    try:
        build_managed_prompt("helmet", "PPE", "site", "photo", view="front")
    except ValueError as exc:
        assert "成对构图参数" in str(exc)
    else:
        raise AssertionError("incomplete composition should fail")

    try:
        build_managed_prompt("helmet", "PPE", "site", "photo", template_id="unknown-template")
    except ValueError as exc:
        assert "未知 Prompt template_id" in str(exc)
    else:
        raise AssertionError("unknown template_id should fail")

    try:
        build_managed_prompt(
            "helmet",
            "PPE",
            "site",
            "photo",
            template_id=PRODUCT_DISPLAY_TEMPLATE_ID,
            generation_mode="scene_generation",
        )
    except ValueError as exc:
        assert "仅兼容" in str(exc)
    else:
        raise AssertionError("mode/template mismatch should fail")


def _assert_generation_metadata() -> None:
    original_settings = {
        name: getattr(settings, name)
        for name in (
            "storage_dir",
            "input_dir",
            "output_dir",
            "task_dir",
            "ai_engine",
            "storage_backend",
            "ai_task_require_formal_contract",
        )
    }
    with tempfile.TemporaryDirectory(prefix="prompt-management-smoke-") as temp_dir:
        root = Path(temp_dir)
        settings.storage_dir = root / "storage"
        settings.input_dir = settings.storage_dir / "inputs"
        settings.output_dir = settings.storage_dir / "outputs"
        settings.task_dir = settings.storage_dir / "tasks"
        settings.ai_engine = "mock"
        settings.storage_backend = "local"
        settings.ai_task_require_formal_contract = False

        client = TestClient(app)
        common_parameters = {
            "product_name": "industrial safety helmet",
            "product_category": "head protection",
            "scene": "clean studio",
            "style": "catalog photo",
            "size": "512x512",
            "output_format": "png",
            "prompt_overrides": {"scene": "modern warehouse", "audience": "industrial buyers"},
            "sync": True,
        }
        try:
            local_response = client.post(
                "/ai/generate",
                json={**common_parameters, "template_id": SCENE_MARKETING_TEMPLATE_ID},
            )
            local_response.raise_for_status()
            local_result = local_response.json()
            assert local_result["status"] == "succeeded"
            local_metadata = json.loads(
                (settings.output_dir / local_result["task_id"] / "metadata.json").read_text(encoding="utf-8")
            )
            assert local_metadata["prompt_template_id"] == SCENE_MARKETING_TEMPLATE_ID
            assert local_metadata["prompt_template_selection"] == "explicit_template_id"
            assert "modern warehouse" in local_metadata["final_prompt_summary"]
            local_record = load_task_payload(local_result["task_id"])
            assert local_record is not None
            assert local_record["prompt_template_id"] == SCENE_MARKETING_TEMPLATE_ID

            for view, framing in (
                ("front", "half_body"),
                ("front", "full_body"),
                ("slight_side", "half_body"),
                ("slight_side", "full_body"),
            ):
                composition_response = client.post(
                    "/ai/generate",
                    json={**common_parameters, "view": view, "framing": framing},
                )
                composition_response.raise_for_status()
                composition_result = composition_response.json()
                composition_metadata = json.loads(
                    (settings.output_dir / composition_result["task_id"] / "metadata.json").read_text(encoding="utf-8")
                )
                assert composition_metadata["prompt_template_id"] == PRODUCT_DISPLAY_TEMPLATE_ID
                assert composition_metadata["view"] == view
                assert composition_metadata["framing"] == framing
                assert "Composition:" in composition_metadata["final_prompt_summary"]

            legacy_response = client.post("/ai/generate", json=common_parameters)
            legacy_response.raise_for_status()
            legacy_result = legacy_response.json()
            assert legacy_result["status"] == "succeeded"
            legacy_metadata = json.loads(
                (settings.output_dir / legacy_result["task_id"] / "metadata.json").read_text(encoding="utf-8")
            )
            assert legacy_metadata["prompt_template_id"] == PRODUCT_DISPLAY_TEMPLATE_ID
            assert legacy_metadata["prompt_template_selection"] == "generation_mode_default"
            assert "view" not in legacy_metadata and "framing" not in legacy_metadata

            business_response = client.post(
                "/ai/tasks",
                json={
                    "jobId": "prompt-management-business",
                    "type": "image_generation",
                    "tenantId": "smoke-tenant",
                    "traceId": "trace-prompt-management",
                    "modelProfileId": "mock",
                    "workflowVersion": "prompt-mvp",
                    "parameters": {
                        **common_parameters,
                        "template_id": SCENE_MARKETING_TEMPLATE_ID,
                        "view": "slight_side",
                        "framing": "full_body",
                    },
                },
            )
            business_response.raise_for_status()
            assert business_response.json()["status"] == "succeeded"
            business_metadata = json.loads(
                (settings.output_dir / "prompt-management-business" / "metadata.json").read_text(encoding="utf-8")
            )
            assert business_metadata["prompt_template_id"] == SCENE_MARKETING_TEMPLATE_ID
            assert business_metadata["final_prompt_summary"]
            assert business_metadata["view"] == "slight_side"
            assert business_metadata["framing"] == "full_body"
            business_record = load_task_payload("prompt-management-business")
            assert business_record is not None
            assert business_record["prompt_template_id"] == SCENE_MARKETING_TEMPLATE_ID
        finally:
            for name, value in original_settings.items():
                setattr(settings, name, value)


def main() -> None:
    _assert_template_selection_and_overrides()
    _assert_generation_metadata()
    print("PROMPT_MANAGEMENT_SMOKE_OK")


if __name__ == "__main__":
    main()
