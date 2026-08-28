"""Targeted checks for the main-based customer print-rule migration."""

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
from app.services.helmet_print_validation import validate_helmet_print_view  # noqa: E402
from app.services.logo_service import render_printed_design  # noqa: E402
from app.services.official_print_rules import (  # noqa: E402
    PrintRuleError,
    contained_logo_size,
    resolve_official_print_rule,
    rule_context_from_parameters,
)


def _must_fail(callback) -> None:
    try:
        callback()
    except (PrintRuleError, ValueError):
        return
    raise AssertionError("expected validation failure")


def _render(root: Path, task_id: str, base_color: tuple[int, int, int], logo_color: tuple[int, int, int], **kwargs: object) -> dict:
    base_path = root / f"{task_id}-base.png"
    logo_path = root / f"{task_id}-logo.png"
    Image.new("RGBA", (1000, 700), (*base_color, 255)).save(base_path)
    logo = Image.new("RGBA", (400, 100), (0, 0, 0, 0))
    ImageDraw.Draw(logo).rectangle((0, 0, 399, 99), fill=(*logo_color, 255))
    logo.save(logo_path)
    _, metadata_path = render_printed_design(task_id, base_path, logo_path, **kwargs)
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def main() -> None:
    p6_front = resolve_official_print_rule(
        product_type="helmet", product_model="P6", product_view="front", print_zone="logo_vertical"
    )
    assert p6_front.recommended_size == {"horizontal": 70.0, "vertical": 50.0, "unit": "mm"}
    assert p6_front.maximum_size == {"horizontal": 80.0, "vertical": 58.0, "unit": "mm"}
    assert contained_logo_size(400, 100, p6_front.recommended_size, 2.0) == (140, 35)
    p7_back = resolve_official_print_rule(
        product_type="helmet", product_model="P7", product_view="back", print_zone="logo_horizontal"
    )
    vest_back = resolve_official_print_rule(
        product_type="vest", product_model="环卫马甲", product_view="back", print_zone="back"
    )
    assert p7_back.maximum_size["vertical"] == 40.0
    assert vest_back.maximum_size["horizontal"] == 300.0
    _must_fail(lambda: resolve_official_print_rule(product_type="helmet", product_model="P6", product_view="back", print_zone="logo_vertical"))
    _must_fail(lambda: resolve_official_print_rule(product_type="helmet", product_model="unknown", product_view="front", print_zone="logo_vertical"))
    _must_fail(lambda: rule_context_from_parameters({"product_type": "helmet", "product_model": "P6", "product_view": "front", "print_zone": "logo_vertical"}))
    assert rule_context_from_parameters({"product_view": "front"}) == (None, None)

    assert validate_helmet_print_view(
        {"product_type": "helmet", "product_view": "front", "helmet_brim_direction": "front"},
        require_declared_brim=True,
    )["helmet_view_validation"] == "declared_view_and_brim_direction_matched"
    _must_fail(lambda: validate_helmet_print_view({"product_type": "helmet", "product_view": "front"}, require_declared_brim=True))
    _must_fail(lambda: validate_helmet_print_view({"product_type": "helmet", "product_view": "front", "helmet_brim_direction": "back"}, require_declared_brim=True))

    previous_output_dir = settings.output_dir
    with tempfile.TemporaryDirectory(prefix="ppe-client-print-rules-") as temp_dir:
        root = Path(temp_dir)
        settings.output_dir = root / "outputs"
        try:
            official = _render(
                root,
                "official-recommended",
                (230, 230, 230),
                (25, 40, 180),
                position="front",
                official_print_rule=p6_front,
                print_scale_px_per_mm=2.0,
            )
            capped = _render(
                root,
                "official-maximum",
                (230, 230, 230),
                (25, 40, 180),
                position="front",
                logo_width_ratio=0.9,
                official_print_rule=p6_front,
                print_scale_px_per_mm=2.0,
            )
            dark = _render(root, "dark-collision", (20, 20, 20), (22, 22, 22), position="center", logo_width_ratio=0.20)
            light = _render(root, "light-collision", (235, 235, 235), (238, 238, 238), position="center", logo_width_ratio=0.20)
        finally:
            settings.output_dir = previous_output_dir

    assert official["official_print_rule"]["product_model"] == "P6"
    assert official["official_print_rule"]["actual_size"] == {"horizontal": 70.0, "vertical": 17.5, "unit": "mm"}
    assert capped["official_print_rule"]["actual_size"]["horizontal"] <= 80.0
    assert capped["official_print_rule"]["actual_size"]["vertical"] <= 58.0
    assert abs(capped["logo_width"] / capped["logo_height"] - 4.0) < 0.05
    assert dark["logo_color_collision"] is True and dark["logo_color_adjustment"] == "pure_white"
    assert light["logo_color_collision"] is True and light["logo_color_adjustment"] == "pure_black"
    assert dark["print_color_sample_bounds"]["right"] - dark["print_color_sample_bounds"]["left"] == dark["logo_width"]
    print("CLIENT_PRINT_RULES_SMOKE_OK")


if __name__ == "__main__":
    main()
