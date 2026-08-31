"""Deterministic direction checks for helmet print jobs.

Only the explicit, product-level ``product_view`` is trusted.  The generation
``view`` prompt is deliberately not used to infer the direction of a supplied
helmet image.
"""

from __future__ import annotations

from typing import Any, Mapping


_VIEWS = {
    "front": "front", "正面": "front", "前": "front",
    "left": "left", "左侧": "left", "左": "left",
    "right": "right", "右侧": "right", "右": "right",
    "back": "back", "背面": "back", "后": "back",
}
_HELMET_MARKERS = ("helmet", "hard hat", "安全帽", "头盔")


def _canonical_view(value: object) -> str | None:
    return _VIEWS.get(str(value).strip().lower()) if value is not None else None


def _is_helmet(parameters: Mapping[str, Any]) -> bool:
    source = " ".join(
        str(parameters.get(key, "")).lower()
        for key in ("product_type", "ppe_category", "product_category", "product_name")
    )
    return any(marker in source for marker in _HELMET_MARKERS)


def validate_helmet_print_view(
    parameters: Mapping[str, Any], *, require_declared_brim: bool = False
) -> dict[str, str]:
    """Validate an explicitly declared helmet direction and brim direction.

    Existing tasks that do not opt in to the official physical-size catalog are
    not retroactively rejected for omitted brim metadata.  Once an official
    helmet rule is requested, view and brim must both be declared and agree.
    """
    if not _is_helmet(parameters):
        return {}
    product_view = _canonical_view(parameters.get("product_view"))
    if product_view is None:
        if require_declared_brim:
            raise ValueError("Helmet official print requires parameters.product_view; do not infer the supplied product direction.")
        return {"helmet_view_validation": "legacy_view_not_declared"}
    brim = _canonical_view(parameters.get("helmet_brim_direction"))
    if brim is None:
        if require_declared_brim:
            raise ValueError("Helmet official print requires parameters.helmet_brim_direction to verify the supplied product image.")
        return {"helmet_product_view": product_view, "helmet_view_validation": "declared_view_without_brim"}
    if brim != product_view:
        raise ValueError(
            f"Helmet product_view={product_view} conflicts with helmet_brim_direction={brim}; correct product image is required."
        )
    print_region = _canonical_view(parameters.get("print_region") or parameters.get("placement_region"))
    if print_region is not None and print_region != product_view:
        raise ValueError(
            f"Helmet print region={print_region} does not match product_view={product_view}; do not infer another product direction."
        )
    return {
        "helmet_product_view": product_view,
        "helmet_brim_direction": brim,
        "helmet_view_validation": "declared_view_and_brim_direction_matched",
    }
