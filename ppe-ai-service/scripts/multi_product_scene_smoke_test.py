"""Deterministic coverage for multi-product wearing, scene use and print rules."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api import routes  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.schemas.business_protocol import GenerationTaskInput  # noqa: E402
from app.schemas.tasks import GenerateRequest  # noqa: E402


def _make_human(path: Path) -> None:
    image = Image.new("RGB", (360, 300), (210, 220, 225))
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 145, 270, 300), fill=(60, 92, 116))
    draw.ellipse((125, 40, 235, 165), fill=(224, 175, 135))
    draw.ellipse((150, 88, 162, 98), fill=(45, 45, 45))
    draw.ellipse((198, 88, 210, 98), fill=(45, 45, 45))
    draw.rounded_rectangle((56, 185, 84, 276), radius=12, fill=(224, 175, 135))
    draw.rounded_rectangle((276, 185, 304, 276), radius=12, fill=(224, 175, 135))
    draw.rounded_rectangle((105, 276, 158, 299), radius=10, fill=(224, 175, 135))
    draw.rounded_rectangle((202, 276, 255, 299), radius=10, fill=(224, 175, 135))
    image.save(path, format="PNG")


def _make_vest(path: Path) -> None:
    image = Image.new("RGBA", (240, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.polygon(((56, 12), (100, 12), (120, 80), (140, 12), (184, 12), (224, 290), (16, 290)), fill=(242, 169, 28, 255))
    draw.rectangle((22, 172, 218, 205), fill=(210, 212, 208, 255))
    image.save(path, format="PNG")


def _make_helmet(path: Path) -> None:
    image = Image.new("RGBA", (260, 150), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.pieslice((35, 8, 225, 172), 180, 360, fill=(250, 196, 28, 255))
    draw.rounded_rectangle((18, 100, 242, 126), radius=10, fill=(232, 164, 12, 255))
    image.save(path, format="PNG")


def _make_gloves(path: Path) -> None:
    image = Image.new("RGBA", (190, 135), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for offset in (10, 100):
        draw.rounded_rectangle((offset + 22, 40, offset + 72, 126), radius=15, fill=(45, 90, 165, 255))
        for finger in range(4):
            x = offset + 15 + finger * 15
            draw.rounded_rectangle((x, 7, x + 13, 65), radius=7, fill=(45, 90, 165, 255))
    image.save(path, format="PNG")


def _make_logo(path: Path) -> None:
    image = Image.new("RGBA", (180, 70), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 62, 62), outline=(15, 55, 120, 255), width=7)
    draw.rectangle((72, 20, 170, 50), fill=(15, 55, 120, 255))
    image.save(path, format="PNG")


async def main() -> None:
    original = {
        name: getattr(settings, name)
        for name in ("storage_dir", "input_dir", "output_dir", "task_dir")
    }
    with tempfile.TemporaryDirectory(prefix="multi-product-scene-") as temp_dir:
        root = Path(temp_dir)
        settings.storage_dir = root / "storage"
        settings.input_dir = settings.storage_dir / "inputs"
        settings.output_dir = settings.storage_dir / "outputs"
        settings.task_dir = settings.storage_dir / "tasks"

        human = root / "human.png"
        scene = root / "scene.png"
        vest = root / "vest.png"
        helmet = root / "helmet.png"
        gloves = root / "gloves.png"
        logo = root / "logo.png"
        _make_human(human)
        _make_vest(vest)
        _make_helmet(helmet)
        _make_gloves(gloves)
        _make_logo(logo)
        Image.new("RGB", (900, 540), (35, 108, 72)).save(scene, format="PNG")

        outfit_items = [
            {
                "product_name": "升级加厚多口袋反光马甲（铁路黄色）",
                "product_category": "反光马甲",
                "product_code": "VEST-MULTI",
                "product_view": "front",
                "product_surface": "vest",
                "ppe_category": "vest",
                "ppe_reference": {"local_path": str(vest)},
                "logo_image": {"local_path": str(logo)},
            },
            {
                "product_name": "P10 安全帽（黄色）",
                "product_category": "安全帽",
                "product_code": "P10",
                "product_view": "front",
                "product_surface": "helmet",
                "ppe_category": "helmet",
                "print_text": "安全生产",
                "ppe_reference": {"local_path": str(helmet)},
            },
            {
                "product_name": "PVC 点塑手套",
                "product_category": "手部防护",
                "product_code": "GLOVE-PVC",
                "product_view": "front",
                "product_surface": "gloves",
                "ppe_category": "gloves",
                "ppe_reference": {"local_path": str(gloves)},
            },
        ]
        task = GenerationTaskInput(
            jobId="multi-product-selected-scene",
            type="image_generation",
            tenantId="smoke-tenant",
            traceId="trace-multi-product-selected-scene",
            modelProfileId="mock-img2img",
            workflowVersion="multi-product-scene-v1",
            parameters={
                "generation_mode": "human_wearing",
                "human_reference": {"local_path": str(human)},
                "scene_reference": {"local_path": str(scene)},
                "outfit_items": outfit_items,
            },
        )
        payload = GenerateRequest(
            product_name="升级加厚多口袋反光马甲、P10 安全帽、PVC 点塑手套",
            product_category="PPE 多产品穿戴",
            scene="工业施工现场",
            style="真实工业商业摄影",
            view="front",
            framing="full_body",
            size="512x512",
            output_format="png",
        )

        try:
            output_path, details, validation = await routes._prepare_human_wearing_input(task, payload, {})
            assert output_path.exists()
            assert details["outfit_item_count"] == 3
            assert details["selected_scene_used"] is True
            assert [item["ppe_category"] for item in details["outfit_items"]] == ["vest", "helmet", "gloves"]
            vest_item, helmet_item, gloves_item = details["outfit_items"]
            assert vest_item["logo_applied"] is True
            assert vest_item["print_standard"]["standard_id"] == "vest-multi-pocket-front"
            assert vest_item["print_standard"]["regular_mm"] == {"width": 90, "height": 70}
            assert helmet_item["text_applied"] is True
            assert helmet_item["print_text"] == "安全生产"
            assert helmet_item["print_standard"]["standard_id"] == "helmet-p10-front-back"
            assert helmet_item["print_standard"]["maximum_mm"] == {"width": 90, "height": 58}
            assert gloves_item["logo_applied"] is False and gloves_item["text_applied"] is False
            assert vest_item["body_anchors"]["face_box"] == helmet_item["body_anchors"]["face_box"]
            assert helmet_item["body_anchors"]["face_box"] == gloves_item["body_anchors"]["face_box"]
            assert len(gloves_item["placements"]) == 2
            assert all(item["source_component_count"] == 2 for item in gloves_item["placements"])
            assert all(f"outfit_{index}_ppe_reference" in validation for index in range(3))
            assert validation["scene_reference"]["validation_status"] == "passed"

            metadata = json.loads(Path(details["metadata_path"]).read_text(encoding="utf-8"))
            assert metadata["outfit_item_count"] == 3
            assert metadata["selected_scene_used"] is True
            scene_metadata = json.loads(Path(details["scene_metadata_path"]).read_text(encoding="utf-8"))
            assert scene_metadata["scene_reference_path"] == str(scene)
            assert scene_metadata["subject_mask_strategy"] == "original_model_row_background_plus_ppe_delta"
            pre_scene_path = Path(gloves_item["metadata_path"])
            pre_scene_metadata = json.loads(pre_scene_path.read_text(encoding="utf-8"))
            with Image.open(output_path) as output_image, Image.open(pre_scene_metadata["output_path"]) as pre_scene:
                assert ImageChops.difference(output_image.convert("RGB"), pre_scene.convert("RGB")).getbbox() is not None
            with Image.open(details["mask_path"]) as combined_mask:
                assert combined_mask.convert("L").getbbox() is not None
        finally:
            for name, value in original.items():
                setattr(settings, name, value)

    print("MULTI_PRODUCT_SCENE_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
