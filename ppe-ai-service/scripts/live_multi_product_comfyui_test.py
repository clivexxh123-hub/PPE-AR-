"""Submit one real three-product wearing task to the running local AI service."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.task_store import load_task, load_task_payload  # noqa: E402


def _asset(*parts: str) -> Path:
    path = WORKSPACE_ROOT.joinpath(*parts).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one live ComfyUI multi-product validation task.")
    parser.add_argument("--run", action="store_true", help="Actually submit the GPU task.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if not args.run:
        parser.error("Pass --run to submit a real GPU generation task.")

    vest = _asset(
        "ppe-product-admin", "server", "uploads", "products", "test-dataset-20260826",
        "vest_multiPocket_railwayyellow_front.png",
    )
    helmet = _asset(
        "ppe-product-admin", "server", "uploads", "products", "test-dataset-20260826",
        "helmet_P10_orange_front.png",
    )
    gloves = _asset(
        "ppe-product-admin", "server", "uploads", "products", "test-dataset-20260826",
        "gloves_PVC_pair_front.png",
    )
    human = _asset(
        "ppe-product-admin", "server", "uploads", "models",
        "female-fullbody-front-generated-v1.png",
    )
    scene = _asset(
        "ppe-product-admin", "server", "uploads", "scenes",
        "construction-site-steel-02.png",
    )
    logo = _asset(
        "ppe-product-admin", "server", "uploads", "client-demo", "state-grid-logo.png",
    )

    job_id = f"live-multi-product-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    source = lambda path: {"local_path": str(path)}  # noqa: E731
    outfit_items = [
        {
            "product_name": "升级加厚多口袋反光马甲（铁路黄色）",
            "product_category": "反光马甲",
            "product_code": "VEST-MULTI",
            "product_view": "front",
            "product_surface": "vest",
            "ppe_category": "vest",
            "ppe_reference": source(vest),
            "logo_image": source(logo),
        },
        {
            "product_name": "P10 安全帽（橙色）",
            "product_category": "安全帽",
            "product_code": "P10",
            "product_view": "front",
            "product_surface": "helmet",
            "ppe_category": "helmet",
            "ppe_reference": source(helmet),
            "logo_image": source(logo),
        },
        {
            "product_name": "PVC 点塑手套",
            "product_category": "防护手套",
            "product_code": "PVC",
            "product_view": "front",
            "product_surface": "gloves",
            "ppe_category": "gloves",
            "ppe_reference": source(gloves),
        },
    ]
    request = {
        "jobId": job_id,
        "type": "image_generation",
        "tenantId": "live-local-validation",
        "traceId": f"trace-{job_id}",
        "modelProfileId": "comfyui-sd15-human-wearing",
        "workflowVersion": "multi-product-selected-scene-v1",
        "parameters": {
            "product_name": "升级加厚多口袋反光马甲（铁路黄色）、P10 安全帽（橙色）、PVC 点塑手套",
            "product_category": "反光马甲、安全帽、防护手套",
            "scene": "钢结构工业施工现场",
            "style": "真实专业工业商业摄影，自然光照，真实穿戴接触，产品细节清晰",
            "size": "512x512",
            "output_format": "png",
            "sync": True,
            "generation_mode": "human_wearing",
            "view": "front",
            "framing": "full_body",
            "ppe_category": "vest",
            "product_view": "front",
            "product_image": source(vest),
            "logo_image": source(logo),
            "human_reference": source(human),
            "scene_reference": source(scene),
            "outfit_items": outfit_items,
            "prompt_overrides": {
                "product_surface": "multi_ppe_outfit",
                "outfit_summary": "反光马甲、P10 安全帽、PVC 点塑手套全部真实穿戴",
                "scene_name": "钢结构工业施工现场",
            },
        },
    }

    with httpx.Client(base_url=args.base_url, timeout=900) as client:
        health = client.get("/health")
        health.raise_for_status()
        if health.json().get("engine") != "comfyui":
            raise RuntimeError(f"Live validation requires comfyui, got {health.text}")
        response = client.post("/ai/tasks", json=request)
        response.raise_for_status()
        result = response.json()

    record = load_task(job_id)
    task_payload = load_task_payload(job_id)
    if record is None or task_payload is None:
        raise RuntimeError(f"Task state was not persisted: {job_id}")
    if result.get("status") != "succeeded":
        raise RuntimeError(json.dumps(result, ensure_ascii=False, indent=2))
    details = task_payload.get("printed_design") or {}
    items = details.get("outfit_items") or []
    checks = {
        "engine": "comfyui",
        "outfit_item_count": details.get("outfit_item_count"),
        "outfit_categories": [item.get("ppe_category") for item in items],
        "selected_scene_used": details.get("selected_scene_used"),
        "vest_logo_applied": bool(items and items[0].get("logo_applied")),
        "helmet_logo_applied": bool(len(items) > 1 and items[1].get("logo_applied")),
        "vest_print_standard": items[0].get("print_standard", {}).get("standard_id") if items else None,
        "helmet_print_standard": items[1].get("print_standard", {}).get("standard_id") if len(items) > 1 else None,
    }
    assert checks == {
        "engine": "comfyui",
        "outfit_item_count": 3,
        "outfit_categories": ["vest", "helmet", "gloves"],
        "selected_scene_used": True,
        "vest_logo_applied": True,
        "helmet_logo_applied": True,
        "vest_print_standard": "vest-multi-pocket-front",
        "helmet_print_standard": "helmet-p10-front-back",
    }, checks
    output_path = Path(record.output_path or "")
    if not output_path.is_file():
        raise RuntimeError(f"Missing output image: {output_path}")
    report = {
        "job_id": job_id,
        "status": result["status"],
        "result_url": result.get("result_url"),
        "output_path": str(output_path),
        "metadata_path": record.metadata_path,
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
