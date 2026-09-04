"""Export immutable stage evidence for a completed real Vest human-wearing task.

This script deliberately reads existing task artifacts only.  It does not alter
placement, masks, prompts, ComfyUI settings, or the generated result.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy(source: Path, destination: Path) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"Diagnostic source does not exist: {source}")
    shutil.copy2(source, destination)
    return destination


def _neckline_mask(foreground_mask_path: Path, placement: dict, destination: Path) -> Path:
    """Extract the already-applied shallow collar region from the saved foreground mask."""
    with Image.open(foreground_mask_path) as source:
        foreground = source.convert("L")
    left = float(placement["rendered_x"])
    top = float(placement["rendered_y"])
    width = float(placement["rendered_width"])
    height = float(placement["rendered_height"])
    center_x = left + width / 2
    collar = Image.new("L", foreground.size, 0)
    ImageDraw.Draw(collar).polygon(
        [
            (round(center_x - width * 0.115), round(top)),
            (round(center_x + width * 0.115), round(top)),
            (round(center_x + width * 0.045), round(top + height * 0.15)),
            (round(center_x), round(top + height * 0.285)),
            (round(center_x - width * 0.045), round(top + height * 0.15)),
        ],
        fill=255,
    )
    ImageChops.multiply(foreground, collar).save(destination, format="PNG")
    return destination


def _contact_sheet(items: list[tuple[str, Path]], destination: Path) -> Path:
    cell_width, cell_height, header_height = 276, 244, 26
    columns = 3
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), (30, 34, 42))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (label, path) in enumerate(items):
        with Image.open(path) as source:
            image = source.convert("RGB")
        image.thumbnail((cell_width - 8, cell_height - header_height - 8), Image.Resampling.LANCZOS)
        column, row = index % columns, index // columns
        x0, y0 = column * cell_width, row * cell_height
        draw.rectangle((x0, y0, x0 + cell_width - 1, y0 + cell_height - 1), outline=(105, 120, 145))
        draw.text((x0 + 6, y0 + 6), label, fill=(242, 245, 250), font=font)
        sheet.paste(image, (x0 + (cell_width - image.width) // 2, y0 + header_height + (cell_height - header_height - image.height) // 2))
    sheet.save(destination, format="PNG")
    return destination


def _difference_ratio(raw_path: Path, final_path: Path) -> float:
    with Image.open(raw_path) as raw_source, Image.open(final_path) as final_source:
        raw = raw_source.convert("RGB")
        final = final_source.convert("RGB")
    if raw.size != final.size:
        raise ValueError("Raw and final outputs have different dimensions.")
    difference = ImageChops.difference(raw, final).convert("L")
    changed = sum(difference.histogram()[1:])
    return round(changed / float(raw.width * raw.height), 6)


def export_task(task_id: str) -> Path:
    root = settings.output_dir
    engine_dir = root / task_id
    wearing_dir = root / f"{task_id}-human-wearing-0"
    engine_metadata = _read_json(engine_dir / "metadata.json")
    wearing_metadata = _read_json(wearing_dir / "human_wearing_metadata.json")
    diagnostics_dir = engine_dir / "stage_diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)

    masked_refinement = engine_metadata.get("masked_refinement") or {}
    sources = {
        "original_human.png": Path(wearing_metadata["base_path"]),
        "vest_torso_quad_pre_composite.png": Path(
            wearing_metadata.get("torso_quad_pre_composite_path") or wearing_metadata["product_layer_path"]
        ),
        "foreground_occlusion_mask.png": Path(wearing_metadata["foreground_occlusion_mask_path"]),
        "pre_sd_composite_input.png": Path(engine_metadata["product_image_local_path"]),
        "diffusion_mask.png": Path(engine_metadata["mask_image_local_path"]),
        "comfyui_raw_output.png": Path(masked_refinement["raw_output_path"]),
        "final_after_python_lock.png": Path(masked_refinement["final_output_path"]),
    }
    exported = {name: _copy(source, diagnostics_dir / name) for name, source in sources.items()}
    placement = wearing_metadata["placements"][0]
    exported["neckline_keep_or_cut_mask.png"] = _neckline_mask(
        exported["foreground_occlusion_mask.png"], placement, diagnostics_dir / "neckline_keep_or_cut_mask.png"
    )
    sheet_items = [
        ("original human", exported["original_human.png"]),
        ("vest torso quad", exported["vest_torso_quad_pre_composite.png"]),
        ("foreground occlusion", exported["foreground_occlusion_mask.png"]),
        ("neckline keep/cut", exported["neckline_keep_or_cut_mask.png"]),
        ("pre-SD composite", exported["pre_sd_composite_input.png"]),
        ("diffusion mask", exported["diffusion_mask.png"]),
        ("ComfyUI raw", exported["comfyui_raw_output.png"]),
        ("final Python lock", exported["final_after_python_lock.png"]),
    ]
    exported["stage_contact_sheet.png"] = _contact_sheet(
        sheet_items, diagnostics_dir / "stage_contact_sheet.png"
    )
    report = {
        "task_id": task_id,
        "diagnostic_only": True,
        "view": wearing_metadata.get("view"),
        "framing": wearing_metadata.get("framing"),
        "vest_geometry": wearing_metadata.get("vest_geometry"),
        "placement": placement,
        "foreground_occlusion": (wearing_metadata.get("blend") or {}).get("foreground_occlusion"),
        "engine": engine_metadata.get("engine"),
        "denoise": engine_metadata.get("denoise"),
        "raw_to_final_difference_ratio": _difference_ratio(
            exported["comfyui_raw_output.png"], exported["final_after_python_lock.png"]
        ),
        "artifacts": {name: str(path) for name, path in exported.items()},
        "stage_order": [
            "original_human.png",
            "vest_torso_quad_pre_composite.png",
            "foreground_occlusion_mask.png",
            "neckline_keep_or_cut_mask.png",
            "pre_sd_composite_input.png",
            "diffusion_mask.png",
            "comfyui_raw_output.png",
            "final_after_python_lock.png",
        ],
    }
    report_path = diagnostics_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"VEST_STAGE_DIAGNOSTICS_OK:{task_id}:{diagnostics_dir}")
    return diagnostics_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Export real Vest task stage evidence without changing generation.")
    parser.add_argument("task_ids", nargs="+", help="Completed human-wearing task IDs")
    args = parser.parse_args()
    for task_id in args.task_ids:
        export_task(task_id)


if __name__ == "__main__":
    main()
