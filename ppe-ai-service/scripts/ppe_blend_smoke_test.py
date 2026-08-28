"""Regression coverage for the masked contact-band refinement inputs.

The mask is the safety mechanism: everything it covers gets repainted at a high
denoise.  These checks assert what it must never cover - the product interior
and the wearer's face - and that the masked workflow wires both the composite
and the mask into ComfyUI.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402
from app.services.comfyui_engine import (  # noqa: E402
    ComfyUIError,
    _load_workflow,
    _patch_workflow,
    resolve_generation_denoise,
)
from app.services.human_wearing_service import (  # noqa: E402
    render_human_wearing_design,
    resolve_human_wearing_placement,
)
from app.services.ppe_blend_service import build_contact_mask, prepare_blend_inputs  # noqa: E402
from app.services.prompt_templates import build_ppe_blend_prompt  # noqa: E402

SKIN = (224, 175, 135)
HEAD_BOX = (150, 40, 250, 170)


def _make_wearer(path: Path) -> None:
    image = Image.new("RGB", (400, 800), (208, 214, 220))
    draw = ImageDraw.Draw(image)
    draw.rectangle((110, 210, 290, 620), fill=(60, 90, 120))
    draw.ellipse(HEAD_BOX, fill=SKIN)
    draw.rectangle((165, 95, 235, 110), fill=(40, 40, 40))
    draw.rectangle((185, 165, 215, 215), fill=SKIN)
    image.save(path, format="PNG")


def _make_ppe(path: Path, size: tuple[int, int], colour: tuple[int, int, int]) -> None:
    image = Image.new("RGBA", (size[0] * 3, size[1] * 3), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle(
        (size[0], size[1], size[0] * 2, size[1] * 2), fill=(*colour, 255)
    )
    image.save(path, format="PNG")


def _mask_value(mask: Image.Image, xy: tuple[int, int]) -> int:
    return mask.getpixel(xy)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ppe-blend-smoke-") as raw:
        temp = Path(raw)
        human, helmet, vest = temp / "h.png", temp / "helmet.png", temp / "vest.png"
        _make_wearer(human)
        _make_ppe(helmet, (220, 200), (240, 100, 20))
        _make_ppe(vest, (300, 430), (250, 160, 20))

        for category, ppe, name, product_category in (
            ("helmet", helmet, "安全帽 P10", "安全帽"),
            ("vest", vest, "反光马甲", "马甲"),
        ):
            placement = resolve_human_wearing_placement(name, product_category, {})
            composite, meta_path = render_human_wearing_design(
                f"blend-smoke-{category}", human, ppe, size="512x768",
                position_x_ratio=placement["position_x_ratio"],
                position_y_ratio=placement["position_y_ratio"],
                ppe_width_ratio=placement["ppe_width_ratio"],
                human_top_padding_ratio=placement["human_top_padding_ratio"],
                opacity=placement["opacity"], ppe_category=category,
            )
            meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
            assert meta["placement_strategy"] == "body_anchor", meta
            anchor = meta["body_anchor"]

            with Image.open(ppe) as opened:
                foreground = opened.convert("RGBA")
            foreground = foreground.crop(foreground.getchannel("A").getbbox()).resize(
                (meta["ppe_rendered_width"], meta["ppe_rendered_height"]), Image.Resampling.LANCZOS
            )
            paste = (meta["paste_x"], meta["paste_y"])
            mask, mask_meta = build_contact_mask((512, 768), foreground, paste, category, anchor)

            # A band, not a blanket: enough to rebuild contact, far from a full repaint.
            assert 0.002 < mask_meta["mask_coverage_ratio"] < 0.30, mask_meta

            # The wearer's face must stay untouched or the model's identity changes.
            face_cx = int((anchor["face_box"]["x0"] + anchor["face_box"]["x1"]) / 2)
            face_cy = int(anchor["hairline_y"] + 0.52 * anchor["head_height"])
            assert _mask_value(mask, (face_cx, face_cy)) < 8, (category, "face not protected")

            if category == "helmet":
                # The dome carries the product colour and shape; never repaint it.
                dome = (paste[0] + meta["ppe_rendered_width"] // 2,
                        paste[1] + int(meta["ppe_rendered_height"] * 0.30))
                assert _mask_value(mask, dome) < 8, (category, "helmet dome not protected")
                brim_y = paste[1] + meta["ppe_rendered_height"]
                assert _mask_value(mask, (dome[0], brim_y)) > 100, (category, "brim band missing")
            else:
                core = (paste[0] + meta["ppe_rendered_width"] // 2,
                        paste[1] + int(meta["ppe_rendered_height"] * 0.55))
                assert _mask_value(mask, core) < 8, (category, "vest core not protected")
                edge_y = paste[1] + int(meta["ppe_rendered_height"] * 0.55)
                assert _mask_value(mask, (paste[0], edge_y)) > 100, (category, "side band missing")

            blend = prepare_blend_inputs(composite, foreground, paste, category, anchor)
            assert blend.composite.size == (512, 768)
            assert blend.mask.size == (512, 768)
            assert blend.metadata["contact_shadow_strength"] > 0
            assert build_ppe_blend_prompt(category)

        # Blend denoise is far above the global path, because it is local.
        blend_denoise = resolve_generation_denoise("human_wearing_blend", "image_to_image")
        assert blend_denoise == settings.comfyui_human_wearing_blend_denoise
        assert blend_denoise > resolve_generation_denoise("human_wearing", "image_to_image")

        workflow = _patch_workflow(
            _load_workflow(settings.comfyui_image_to_image_masked_workflow_path),
            "smoke", "POSITIVE", "512x768", "image_to_image", "input.png",
            negative_prompt="NEGATIVE", denoise=0.75, comfyui_mask_name="mask.png",
        )
        text_nodes = [n for n in workflow.values() if n.get("class_type") == "CLIPTextEncode"]
        assert [n["inputs"]["text"] for n in text_nodes] == ["POSITIVE", "NEGATIVE"], text_nodes
        load = [n for n in workflow.values() if n.get("class_type") == "LoadImage"]
        mask_nodes = [n for n in workflow.values() if n.get("class_type") == "LoadImageMask"]
        assert load[0]["inputs"]["image"] == "input.png"
        assert mask_nodes[0]["inputs"]["image"] == "mask.png"
        assert mask_nodes[0]["inputs"]["channel"] == "red"
        sampler = [n for n in workflow.values() if n.get("class_type") == "KSampler"][0]
        assert sampler["inputs"]["denoise"] == 0.75
        assert sampler["inputs"]["latent_image"][0] == "12"  # SetLatentNoiseMask
        assert any(n.get("class_type") == "SetLatentNoiseMask" for n in workflow.values())

        # A masked workflow with no mask supplied must fail loudly, not silently
        # repaint the whole frame at blend denoise.
        try:
            _patch_workflow(
                _load_workflow(settings.comfyui_image_to_image_masked_workflow_path),
                "smoke", "P", "512x768", "image_to_image", "input.png", denoise=0.75,
            )
        except ComfyUIError:
            pass
        else:
            raise AssertionError("missing mask must raise")

    print("PPE_BLEND_SMOKE_OK")


if __name__ == "__main__":
    main()
