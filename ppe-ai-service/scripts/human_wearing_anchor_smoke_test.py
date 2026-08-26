"""Regression coverage for body-anchored human_wearing placement.

The canvas-ratio placement it replaces could not tell a head from a chest, so
these checks assert anatomy, not pixels: the helmet has to overlap the head and
stay off the torso, the vest has to sit below the face on the torso, and an
undetectable reference has to fall back to the old ratio path unchanged.
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

from app.services.human_anchor_service import detect_face_box  # noqa: E402
from app.services.human_wearing_service import (  # noqa: E402
    render_human_wearing_design,
    resolve_human_wearing_placement,
)

SKIN = (224, 175, 135)
HEAD_BOX = (150, 40, 250, 170)     # left, top, right, bottom
TORSO_TOP = 210


def _make_wearer(path: Path) -> None:
    image = Image.new("RGB", (400, 800), (208, 214, 220))
    draw = ImageDraw.Draw(image)
    draw.rectangle((110, TORSO_TOP, 290, 620), fill=(60, 90, 120))
    draw.ellipse(HEAD_BOX, fill=SKIN)
    draw.rectangle((165, 95, 235, 110), fill=(40, 40, 40))  # spectacles
    draw.rectangle((185, 165, 215, 215), fill=SKIN)         # neck
    image.save(path, format="PNG")


def _make_ppe(path: Path, size: tuple[int, int], colour: tuple[int, int, int]) -> None:
    """A transparent export with the generous unused canvas real assets have."""
    image = Image.new("RGBA", (size[0] * 3, size[1] * 3), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle(
        (size[0], size[1], size[0] * 2, size[1] * 2), fill=(*colour, 255)
    )
    image.save(path, format="PNG")


def _render(temp: Path, task: str, human: Path, ppe: Path, name: str, category: str, **extra):
    placement = resolve_human_wearing_placement(name, category, {})
    image_path, metadata_path = render_human_wearing_design(
        task, human, ppe, size="512x768",
        position_x_ratio=placement["position_x_ratio"],
        position_y_ratio=placement["position_y_ratio"],
        ppe_width_ratio=placement["ppe_width_ratio"],
        human_top_padding_ratio=placement["human_top_padding_ratio"],
        opacity=placement["opacity"],
        **extra,
    )
    return image_path, json.loads(Path(metadata_path).read_text(encoding="utf-8")), placement


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ppe-anchor-smoke-") as raw:
        temp = Path(raw)
        human = temp / "human.png"
        helmet = temp / "helmet.png"
        vest = temp / "vest.png"
        _make_wearer(human)
        _make_ppe(helmet, (220, 200), (240, 100, 20))
        _make_ppe(vest, (300, 430), (250, 160, 20))

        with Image.open(human) as opened:
            face = detect_face_box(opened.convert("RGB"))
        assert face is not None, "face detection failed on the synthetic wearer"
        assert HEAD_BOX[0] - 20 <= face.x0 and face.x1 <= HEAD_BOX[2] + 20, face
        assert abs(face.y0 - HEAD_BOX[1]) < 30, face

        _, helmet_meta, helmet_placement = _render(
            temp, "anchor-helmet", human, helmet, "安全帽 P10", "安全帽",
            ppe_category="helmet",
        )
        assert helmet_placement["ppe_category"] == "helmet"
        assert helmet_meta["placement_strategy"] == "body_anchor", helmet_meta
        anchor = helmet_meta["body_anchor"]
        assert anchor["anchor"] == "head_crown"
        helmet_bottom = helmet_meta["paste_y"] + helmet_meta["ppe_rendered_height"]
        # The shell must overlap the skull and must not reach the torso.
        assert helmet_meta["paste_y"] < anchor["hairline_y"], helmet_meta
        assert helmet_bottom < anchor["shoulder_y"], helmet_meta
        assert 0.9 <= helmet_meta["ppe_rendered_width"] / anchor["head_width"] <= 1.6, helmet_meta

        _, vest_meta, vest_placement = _render(
            temp, "anchor-vest", human, vest, "反光马甲", "马甲", ppe_category="vest",
        )
        assert vest_placement["ppe_category"] == "vest"
        assert vest_meta["placement_strategy"] == "body_anchor", vest_meta
        vest_anchor = vest_meta["body_anchor"]
        assert vest_anchor["anchor"] == "shoulder_torso"
        # A vest never covers the face.
        assert vest_meta["paste_y"] > vest_anchor["face_box"]["y0"], vest_meta
        assert vest_meta["ppe_rendered_width"] > vest_anchor["head_width"], vest_meta

        # Category without a body anchor keeps the historical ratio placement.
        _, glove_meta, _ = _render(
            temp, "anchor-gloves", human, vest, "防护手套", "手套", ppe_category="gloves",
        )
        assert glove_meta["placement_strategy"] == "canvas_ratio", glove_meta

        # An unreadable reference must degrade to the ratio path, not raise.
        blank = temp / "blank.png"
        Image.new("RGB", (400, 800), (30, 30, 30)).save(blank)
        _, blank_meta, _ = _render(
            temp, "anchor-blank", blank, helmet, "安全帽 P10", "安全帽", ppe_category="helmet",
        )
        assert blank_meta["placement_strategy"] == "canvas_ratio", blank_meta
        assert blank_meta["body_anchor"] is None

    print("HUMAN_WEARING_ANCHOR_SMOKE_OK")


if __name__ == "__main__":
    main()
