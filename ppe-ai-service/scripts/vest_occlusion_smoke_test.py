"""Deterministic VEST-EXAMPLE-01 coverage for source-alpha Vest compositing."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.ppe_blend_service import build_contact_mask, prepare_blend_inputs  # noqa: E402


def _fixture() -> tuple[Image.Image, Image.Image, dict, dict]:
    human = Image.new("RGB", (512, 512), (218, 224, 230))
    human_draw = ImageDraw.Draw(human)
    human_draw.rectangle((150, 118, 362, 480), fill=(55, 84, 112))
    human_draw.rectangle((118, 162, 202, 452), fill=(242, 242, 238))
    human_draw.rectangle((310, 162, 394, 452), fill=(242, 242, 238))
    human_draw.polygon(((234, 152), (278, 152), (256, 236)), fill=(238, 188, 148))

    product = Image.new("RGBA", human.size, (0, 0, 0, 0))
    product_draw = ImageDraw.Draw(product)
    product_draw.rectangle((145, 150, 367, 420), fill=(226, 153, 30, 255))
    product_draw.rectangle((145, 300, 367, 320), fill=(205, 205, 200, 255))

    subject_mask = Image.new("L", human.size, 0)
    ImageDraw.Draw(subject_mask).polygon(
        ((118, 118), (394, 118), (394, 480), (118, 480)), fill=255
    )
    anchors = {
        "face_box": {"x0": 216, "y0": 35, "x1": 296, "y1": 125},
        "face_width": 80.0,
        "head_height": 123.0,
        "hairline_y": 35,
        "subject_mask": subject_mask,
    }
    placement = {"rendered_x": 145, "rendered_y": 150, "rendered_width": 222, "rendered_height": 270}
    return human, product, anchors, placement


def main() -> None:
    human, product, anchors, placement = _fixture()
    expected_mask, _ = build_contact_mask(product.getchannel("A"), "vest", [placement], anchors)
    blend = prepare_blend_inputs(human, product, "vest", [placement], anchors)

    # The existing diffusion/contact mask is byte-identical: this experiment
    # changes only the pre-composite foreground layering.
    assert blend.mask.tobytes() == expected_mask.tobytes()
    assert blend.metadata["foreground_occlusion"]["strategy"] == "vest_product_alpha_authoritative_v1"
    assert blend.metadata["foreground_occlusion"]["diffusion_mask_changed"] is False
    assert blend.foreground_occlusion_mask.getbbox() is None

    # The transparent product alpha remains authoritative: no guessed sleeve
    # or collar is pasted inside the real Vest silhouette before diffusion.
    assert blend.composite.getpixel((178, 300)) != human.getpixel((178, 300))
    assert blend.composite.getpixel((256, 205)) != human.getpixel((256, 205))
    assert blend.composite.getpixel((256, 330)) != human.getpixel((256, 330))
    assert blend.composite.getpixel((256, 330))[0] > 180
    print("VEST_EXAMPLE_ALPHA_SMOKE_OK")


if __name__ == "__main__":
    main()
