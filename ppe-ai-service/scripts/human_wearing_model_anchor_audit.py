"""Audit every configured base model against the body-anchor contract."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.human_anchor_service import analyze_body_anchors, public_anchor_metadata  # noqa: E402
from app.services.human_wearing_service import _fit_human_frame  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit PPE model body anchors.")
    parser.add_argument(
        "model_dir",
        nargs="?",
        default="../ppe-product-admin/server/uploads/models",
    )
    args = parser.parse_args()
    model_dir = Path(args.model_dir).resolve()
    failures: list[str] = []
    reports: list[dict] = []
    for path in sorted(model_dir.glob("*.png")):
        framing = "full_body" if "fullbody" in path.name else "half_body"
        view = "slight_side" if "slight-side" in path.name or path.name.endswith("-02.png") else "front"
        try:
            with Image.open(path) as source:
                fitted = _fit_human_frame(source, (512, 512), framing)
            anchors = public_anchor_metadata(
                analyze_body_anchors(fitted, view=view, framing=framing)
            )
            if framing == "full_body" and not anchors["feet_visible"]:
                failures.append(f"{path.name}: full-body feet not visible")
            reports.append({
                "model": path.name,
                "view": view,
                "framing": framing,
                "hands_visible": anchors["hands_visible"],
                "feet_visible": anchors["feet_visible"],
                "face_box": anchors["face_box"],
                "hands": anchors["hands"],
                "feet": anchors["feet"],
            })
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{path.name}: {exc}")
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit("\n".join(failures))
    print("HUMAN_WEARING_MODEL_ANCHOR_AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
