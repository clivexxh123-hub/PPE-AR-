"""Product-specific print zones derived from the supplied print standards.

Millimetre values are retained as audit metadata.  Pixel placement is resolved
against the detected product bounds so the same rule works across source sizes.
"""
from __future__ import annotations

from typing import Any, Mapping


def resolve_print_standard(parameters: Mapping[str, Any]) -> dict[str, Any]:
    name = str(parameters.get("product_name", ""))
    code = str(parameters.get("product_code", ""))
    category = str(parameters.get("ppe_category", "")).strip().lower()
    view = str(parameters.get("product_view", "front")).strip().lower()
    source = f"{code} {name}".lower()

    if category == "helmet":
        is_p10 = "p10" in source or "豪华v型透气" in source or "豪华v型" in source
        if view in {"left", "right", "左侧", "右侧"}:
            return {
                "standard_id": "helmet-p10-side" if is_p10 else "helmet-side",
                "position": "helmet-side-center",
                "logo_width_ratio": 0.24,
                "regular_mm": {"width": 90, "height": 40} if is_p10 else None,
                "maximum_mm": {"width": 100, "height": 45} if is_p10 else None,
                "text_maximum_mm": {"width": 120, "height": 20} if is_p10 else None,
            }
        return {
            "standard_id": "helmet-p10-front-back" if is_p10 else "helmet-front-back",
            "position": "helmet-back-center" if view in {"back", "背面"} else "helmet-front-center",
            "logo_width_ratio": 0.22,
            "regular_mm": {"width": 70, "height": 50} if is_p10 else None,
            "maximum_mm": {"width": 90, "height": 58} if is_p10 else None,
            "text_maximum_mm": {"width": 120, "height": 20} if is_p10 else None,
        }

    if category == "vest":
        is_multi_pocket = "升级加厚多口袋" in name
        if view in {"back", "背面"}:
            return {
                "standard_id": "vest-multi-pocket-back" if is_multi_pocket else "vest-back",
                "position": "vest-back-center",
                "logo_width_ratio": 0.42,
                "regular_mm": {"width": 220, "height": 200} if is_multi_pocket else {"width": 250, "height": 220},
                "maximum_mm": {"width": 260, "height": 240} if is_multi_pocket else None,
            }
        return {
            "standard_id": "vest-multi-pocket-front" if is_multi_pocket else "vest-front",
            "position": "vest-front-left-chest",
            "logo_width_ratio": 0.16,
            "regular_mm": {"width": 90, "height": 70} if is_multi_pocket else {"width": 100, "height": 88},
            "maximum_mm": {"width": 100, "height": 90} if is_multi_pocket else None,
        }

    return {
        "standard_id": f"{category or 'ppe'}-default",
        "position": "center",
        "logo_width_ratio": 0.22,
        "regular_mm": None,
        "maximum_mm": None,
    }
