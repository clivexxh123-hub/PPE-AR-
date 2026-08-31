"""Official local print-size catalog backed by customer supplied standards.

The catalog deliberately contains only dimensions that are present in the
source files. It never invents a maximum size or an undeclared print zone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


_CATALOG_PATH = Path(__file__).resolve().parents[1] / "templates" / "print" / "official_print_rules.json"


class PrintRuleError(ValueError):
    """A request cannot safely be rendered from the official catalog."""

    code = "needs_rule"


def _normalise(value: object) -> str:
    return str(value or "").strip().casefold().replace("_", "-").replace(" ", "")


def _size(raw: object) -> dict[str, float] | None:
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 2:
        raise RuntimeError("官方印刷规则表尺寸格式无效。")
    horizontal, vertical = (float(value) for value in raw)
    if horizontal <= 0 or vertical <= 0:
        raise RuntimeError("官方印刷规则表尺寸必须大于 0。")
    return {"horizontal": horizontal, "vertical": vertical, "unit": "mm"}


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    try:
        payload = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise RuntimeError(f"官方印刷规则表不可读取：{exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("product_rules"), list):
        raise RuntimeError("官方印刷规则表结构无效。")
    return payload


@dataclass(frozen=True)
class OfficialPrintRule:
    product_type: str
    product_model: str
    product_view: str
    print_zone: str
    recommended_size: dict[str, float]
    maximum_size: dict[str, float]
    source_files: tuple[str, ...]

    def placement_default(self) -> dict[str, str]:
        if self.product_type == "helmet":
            return {"position": self.product_view}
        return {}

    def metadata(self) -> dict[str, Any]:
        return {"official_print_rule": {"status": "matched", "product_type": self.product_type, "product_model": self.product_model, "product_view": self.product_view, "print_zone": self.print_zone, "recommended_size": self.recommended_size, "maximum_size": self.maximum_size, "source_files": list(self.source_files)}}


def _matching_product(product_type: str, product_model: str) -> Mapping[str, Any] | None:
    wanted_type = _normalise(product_type)
    wanted_model = _normalise(product_model)
    for product in _catalog()["product_rules"]:
        if _normalise(product.get("product_type")) != wanted_type:
            continue
        candidates = [product.get("product_model"), *(product.get("aliases") or [])]
        if wanted_model in {_normalise(candidate) for candidate in candidates}:
            return product
    return None


def _view_data(views: Mapping[str, Any], product_view: str) -> Mapping[str, Any] | None:
    key = _normalise(product_view)
    item = views.get(key)
    visited: set[str] = set()
    while isinstance(item, Mapping) and item.get("copy_from"):
        copy_from = str(item["copy_from"])
        if copy_from in visited:
            raise RuntimeError("官方印刷规则表存在循环引用。")
        visited.add(copy_from)
        item = views.get(copy_from)
    return item if isinstance(item, Mapping) else None


def resolve_official_print_rule(*, product_type: str | None, product_model: str | None, product_view: str | None, print_zone: str | None) -> OfficialPrintRule:
    """Look up a complete, safe rule or raise ``needs_rule`` explicitly."""
    fields = {"product_type": product_type, "product_model": product_model, "product_view": product_view, "print_zone": print_zone}
    missing = [name for name, value in fields.items() if not str(value or "").strip()]
    if missing:
        raise PrintRuleError(f"缺少官方印刷规则选择字段：{', '.join(missing)}。")
    product = _matching_product(str(product_type), str(product_model))
    if product is None:
        raise PrintRuleError(f"未定义的产品/型号：{product_type}/{product_model}。")
    view = _view_data(product.get("views", {}), str(product_view))
    if view is None:
        raise PrintRuleError(f"未定义的产品视图：{product_model}/{product_view}。")
    requested_zone = _normalise(print_zone)
    matched_zone = next((zone for zone in view if _normalise(zone) == requested_zone), None)
    if matched_zone is None or not isinstance(view.get(matched_zone), Mapping):
        raise PrintRuleError(f"未定义的印刷区域：{product_model}/{product_view}/{print_zone}。")
    size = view[matched_zone]
    recommended = _size(size.get("recommended"))
    maximum = _size(size.get("maximum"))
    if recommended is None or maximum is None:
        raise PrintRuleError(f"标准文件未定义 {product_model}/{product_view}/{print_zone} 的最大印刷尺寸，需客户确认。")
    return OfficialPrintRule(product_type=str(product["product_type"]), product_model=str(product["product_model"]), product_view=str(product_view).strip().lower(), print_zone=str(matched_zone), recommended_size=recommended, maximum_size=maximum, source_files=tuple(str(item) for item in _catalog().get("sources", [])))


def rule_context_from_parameters(parameters: Mapping[str, Any]) -> tuple[OfficialPrintRule | None, float | None]:
    """Return a rule only when local official-rule fields are requested.

    Legacy calls remain unchanged. Once a caller opts in, every selector and a
    pixel/mm calibration is mandatory, so no unverified physical size is made.
    """
    # The Node adapter emits a catalog-derived state for every product view.
    # A missing calibration is an explicit compatibility-mode wait state: do
    # not invent a physical scale and do not reject local visual generation.
    # Direct callers without the state retain the existing strict behaviour.
    status = str(parameters.get("print_rule_status", "")).strip().upper()
    if status and status != "READY":
        return None, None

    # ``product_view`` predates the official catalog and is already used by
    # helmet placement.  It alone must not opt a legacy call into physical-mm
    # validation; one of the new selectors explicitly activates the catalog.
    selector_names = ("product_type", "product_model", "print_zone")
    if not any(parameters.get(name) is not None for name in selector_names):
        return None, None
    rule = resolve_official_print_rule(product_type=parameters.get("product_type"), product_model=parameters.get("product_model"), product_view=parameters.get("product_view"), print_zone=parameters.get("print_zone"))
    raw_scale = parameters.get("print_scale_px_per_mm")
    if raw_scale is None:
        raise PrintRuleError("启用官方印刷规则时必须提供 print_scale_px_per_mm 校准值。")
    scale = float(raw_scale)
    if scale <= 0:
        raise PrintRuleError("print_scale_px_per_mm 必须大于 0。")
    return rule, scale


def contained_logo_size(logo_width: int, logo_height: int, bounds: Mapping[str, float], pixels_per_mm: float) -> tuple[int, int]:
    """Contain an artwork in a physical rule rectangle without distorting it."""
    if logo_width <= 0 or logo_height <= 0:
        raise ValueError("Logo 尺寸无效。")
    bound_width = float(bounds["horizontal"]) * pixels_per_mm
    bound_height = float(bounds["vertical"]) * pixels_per_mm
    scale = min(bound_width / logo_width, bound_height / logo_height)
    return max(1, round(logo_width * scale)), max(1, round(logo_height * scale))
