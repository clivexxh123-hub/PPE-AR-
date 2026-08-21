"""Small local store for reusable Logo placement templates.

This is intentionally file-backed for the AI Service MVP: it has no database,
tenant model, versioning, or public CRUD contract.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.core.config import settings


_TEMPLATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_PLACEMENT_FIELDS = frozenset(
    {"position", "position_x_ratio", "position_y_ratio", "logo_width_ratio", "scale", "opacity"}
)
_NUMERIC_FIELDS = frozenset({"position_x_ratio", "position_y_ratio", "logo_width_ratio", "scale", "opacity"})


@dataclass(frozen=True)
class LogoPlacementTemplate:
    template_id: str
    placement: dict[str, str | float]


@dataclass(frozen=True)
class LogoPlacementResolution:
    template_id: str | None
    template_hit: bool
    placement: dict[str, str | float | None]
    manual_override_fields: tuple[str, ...]

    def render_kwargs(self) -> dict[str, str | float | None]:
        return {
            "position": self.placement["position"],
            "position_x_ratio": self.placement["position_x_ratio"],
            "position_y_ratio": self.placement["position_y_ratio"],
            "logo_width_ratio": self.placement["logo_width_ratio"],
            "opacity": self.placement["opacity"],
        }

    def metadata(self, final_placement: dict[str, Any]) -> dict[str, Any]:
        return {
            "logo_template_id": self.template_id,
            "logo_template_hit": self.template_hit,
            "logo_template_manual_override_fields": list(self.manual_override_fields),
            "final_placement": final_placement,
        }


def _store_path() -> Path:
    return settings.storage_dir / "logo_templates.json"


def _read_store() -> dict[str, dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"本地 Logo 模板存储不可读取：{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("本地 Logo 模板存储格式无效。")
    return payload


def _validate_template_id(template_id: str) -> str:
    normalized = template_id.strip()
    if not _TEMPLATE_ID_PATTERN.fullmatch(normalized):
        raise ValueError("logo template_id 仅支持 1-64 位字母、数字、点、下划线或连字符。")
    return normalized


def _validate_placement(placement: Mapping[str, Any]) -> dict[str, str | float]:
    normalized: dict[str, str | float] = {}
    unknown = sorted(set(placement) - _PLACEMENT_FIELDS)
    if unknown:
        raise ValueError(f"Logo 模板包含不支持的 placement 字段：{', '.join(unknown)}。")
    for key, value in placement.items():
        if value is None:
            continue
        if key == "position":
            position = str(value).strip()
            if position:
                normalized[key] = position
            continue
        numeric = float(value)
        if not 0 <= numeric <= 1:
            raise ValueError(f"{key} 必须在 0 到 1 之间。")
        if key in {"logo_width_ratio", "scale"} and numeric <= 0:
            raise ValueError(f"{key} 必须大于 0。")
        normalized[key] = numeric
    if not normalized:
        raise ValueError("Logo 模板至少需要一个 placement 参数。")
    return normalized


def save_logo_template(template_id: str, placement: Mapping[str, Any]) -> LogoPlacementTemplate:
    """Create or replace one local, stable-ID Logo placement template."""
    normalized_id = _validate_template_id(template_id)
    normalized_placement = _validate_placement(placement)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    store = _read_store()
    store[normalized_id] = normalized_placement
    path = _store_path()
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(path)
    return LogoPlacementTemplate(template_id=normalized_id, placement=normalized_placement)


def load_logo_template(template_id: str) -> LogoPlacementTemplate:
    normalized_id = _validate_template_id(template_id)
    store = _read_store()
    stored_placement = store.get(normalized_id)
    if not isinstance(stored_placement, dict):
        raise ValueError(f"未知 Logo template_id：{normalized_id}。")
    return LogoPlacementTemplate(template_id=normalized_id, placement=_validate_placement(stored_placement))


def resolve_logo_placement(
    template_id: str | None,
    manual_parameters: Mapping[str, Any] | None = None,
) -> LogoPlacementResolution:
    """Merge manual placement values over a local template and existing defaults."""
    manual = _validate_placement(manual_parameters or {}) if manual_parameters else {}
    template: LogoPlacementTemplate | None = None
    if template_id is not None and template_id.strip():
        template = load_logo_template(template_id)

    merged: dict[str, str | float | None] = {
        "position": None,
        "position_x_ratio": None,
        "position_y_ratio": None,
        "logo_width_ratio": None,
        "opacity": 1.0,
    }
    if template is not None:
        merged.update(template.placement)
    merged.update(manual)

    # A manually named position is a complete position override. Keep explicitly
    # supplied x/y values, but do not let template coordinates defeat the name.
    if "position" in manual:
        merged["position_x_ratio"] = manual.get("position_x_ratio")
        merged["position_y_ratio"] = manual.get("position_y_ratio")

    manual_width = "logo_width_ratio" in manual or "scale" in manual
    if manual_width:
        merged["logo_width_ratio"] = manual.get("logo_width_ratio", manual.get("scale"))
    elif "logo_width_ratio" not in merged and "scale" in merged:
        merged["logo_width_ratio"] = merged["scale"]
    merged.pop("scale", None)
    if merged.get("opacity") is None:
        merged["opacity"] = 1.0

    return LogoPlacementResolution(
        template_id=template.template_id if template else None,
        template_hit=template is not None,
        placement=merged,
        manual_override_fields=tuple(sorted(manual)),
    )
