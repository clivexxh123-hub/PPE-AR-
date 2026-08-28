"""Masked contact-band refinement A/B against the current global img2img baseline.

Three arms per PPE category, no wider sweep:

  baseline  current whole-frame img2img at the best measured denoise (0.40)
  blendA    masked refinement of the PPE/body contact band, denoise 0.65
  blendB    same mask, denoise 0.85

Requires a live ComfyUI on COMFYUI_BASE_URL and AI_ENGINE=comfyui.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402
from app.services.comfyui_engine import generate_comfyui_image  # noqa: E402
from app.services.human_wearing_service import (  # noqa: E402
    render_human_wearing_design,
    resolve_human_wearing_placement,
)
from app.services.ppe_blend_service import prepare_blend_inputs  # noqa: E402
from app.services.prompt_templates import build_managed_prompt, build_ppe_blend_prompt  # noqa: E402

CASES = (
    ("helmet", "安全帽 P10", "安全帽"),
    ("vest", "多口袋反光马甲", "马甲"),
)


def _check_engine() -> None:
    if settings.ai_engine != "comfyui":
        raise SystemExit("AI_ENGINE 必须为 comfyui；mock 结果不能作为视觉验收依据。")
    try:
        httpx.get(f"{settings.comfyui_base_url}/system_stats", timeout=10).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"ComfyUI 不可达 {settings.comfyui_base_url}：{exc}") from exc
    print(f"ENGINE_PASS  comfyui @ {settings.comfyui_base_url}")


def _prepare_human(path: Path, crop_left_half: bool, out_dir: Path) -> Path:
    with Image.open(path) as source:
        human = source.convert("RGB")
        if crop_left_half:
            human = human.crop((0, 0, human.width // 2, human.height))
        target = out_dir / "human_reference.png"
        human.save(target, format="PNG")
    return target


async def _run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    _check_engine()
    human = _prepare_human(Path(args.human), args.crop_left_half, out_dir)

    rows: list[tuple[str, list[tuple[str, Path]]]] = []
    report: list[dict] = []
    for category, product_name, product_category in CASES:
        ppe_path = Path(getattr(args, category) or "")
        if not ppe_path.is_file():
            print(f"SKIP {category}: 未提供素材")
            continue

        placement = resolve_human_wearing_placement(product_name, product_category, {})
        composite, composite_meta_path = render_human_wearing_design(
            f"{args.tag}-{category}", human, ppe_path, size=args.size,
            position_x_ratio=placement["position_x_ratio"],
            position_y_ratio=placement["position_y_ratio"],
            ppe_width_ratio=placement["ppe_width_ratio"],
            human_top_padding_ratio=placement["human_top_padding_ratio"],
            opacity=placement["opacity"],
            ppe_category=placement["ppe_category"],
        )
        cmeta = json.loads(Path(composite_meta_path).read_text(encoding="utf-8"))
        if cmeta["placement_strategy"] != "body_anchor":
            print(f"SKIP {category}: 未能测到人体锚点，masked refinement 需要 body_anchor。")
            continue
        print(f"COMPOSITE_PASS {category:6s} paste=({cmeta['paste_x']},{cmeta['paste_y']}) "
              f"size={cmeta['ppe_rendered_width']}x{cmeta['ppe_rendered_height']}")

        with Image.open(ppe_path) as opened:
            foreground = opened.convert("RGBA")
        foreground = foreground.crop(foreground.getchannel("A").getbbox()).resize(
            (cmeta["ppe_rendered_width"], cmeta["ppe_rendered_height"]), Image.Resampling.LANCZOS
        )
        blend = prepare_blend_inputs(
            composite, foreground, (cmeta["paste_x"], cmeta["paste_y"]),
            category, cmeta["body_anchor"], edge_strength=args.edge_strength,
        )
        treated_path = out_dir / f"{args.tag}-{category}-treated.png"
        mask_path = out_dir / f"{args.tag}-{category}-mask.png"
        overlay_path = out_dir / f"{args.tag}-{category}-mask_overlay.png"
        blend.composite.save(treated_path)
        blend.mask.save(mask_path)
        blend.debug.save(overlay_path)
        print(f"MASK_PASS      {category:6s} coverage={blend.metadata['mask_coverage_ratio']:.3f} "
              f"feather={blend.metadata['feather_px']}px -> {overlay_path}")

        baseline_prompt = build_managed_prompt(
            product_name=product_name, product_category=product_category,
            scene=args.scene, style=args.style, overrides=None, template_id=None,
            generation_mode="human_wearing", view=args.view,
            framing=args.framing, gender=args.gender,
        ).prompt
        blend_prompt = build_ppe_blend_prompt(category, args.style)

        arms = [
            ("baseline global", args.baseline_denoise, None, baseline_prompt, "human_wearing", Path(composite)),
            (f"blendA {args.blend_a}", args.blend_a, mask_path, blend_prompt, "human_wearing_blend", treated_path),
            (f"blendB {args.blend_b}", args.blend_b, mask_path, blend_prompt, "human_wearing_blend", treated_path),
        ]
        cells: list[tuple[str, Path]] = [("composite", Path(composite))]
        for label, denoise, mask, prompt, mode, source in arms:
            task_id = f"{args.tag}-{category}-{label.split()[0]}"
            try:
                result, meta_path = await generate_comfyui_image(
                    task_id, prompt, args.size, "png",
                    product_image_path=source, generation_mode=mode,
                    denoise=denoise, mask_path=mask,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"IMG2IMG_FAIL   {category} {label}: {exc}")
                continue
            meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
            print(f"IMG2IMG_PASS   {category:6s} {label:16s} masked={meta['masked_refinement']} "
                  f"denoise={meta['denoise']} -> {result}")
            cells.append((label, Path(result)))
            report.append({"category": category, "arm": label, "denoise": denoise,
                           "masked": meta["masked_refinement"], "prompt_id": meta.get("prompt_id"),
                           "result": str(result), "mask": str(mask) if mask else None,
                           "blend": blend.metadata, "composite": cmeta})
        cells.append(("mask overlay", overlay_path))
        rows.append((category, cells))

    if not rows:
        print("没有可用结果。")
        return 1

    columns = max(len(cells) for _, cells in rows)
    with Image.open(rows[0][1][0][1]) as first:
        cell_w, cell_h = first.size
    sheet = Image.new("RGB", (cell_w * columns, (cell_h + 40) * len(rows)), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    for r, (category, cells) in enumerate(rows):
        for c, (label, path) in enumerate(cells):
            with Image.open(path) as im:
                sheet.paste(im.convert("RGB").resize((cell_w, cell_h)), (cell_w * c, (cell_h + 40) * r + 40))
            draw.text((cell_w * c + 10, (cell_h + 40) * r + 14), f"{category}  {label}", fill=(0, 0, 0))
    sheet_path = out_dir / f"{args.tag}_contact_sheet.png"
    sheet.save(sheet_path)
    (out_dir / f"{args.tag}_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"VISUAL_EVIDENCE {sheet_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="human_wearing 局部融合 A/B。")
    parser.add_argument("--human", required=True)
    parser.add_argument("--crop-left-half", action="store_true")
    parser.add_argument("--helmet")
    parser.add_argument("--vest")
    parser.add_argument("--size", default="512x768")
    parser.add_argument("--scene", default="工地作业现场")
    parser.add_argument("--style", default="商业摄影")
    parser.add_argument("--view", default="front")
    parser.add_argument("--framing", default="half_body")
    parser.add_argument("--gender", default="female")
    parser.add_argument("--baseline-denoise", type=float, default=0.40)
    parser.add_argument("--blend-a", type=float, default=0.65)
    parser.add_argument("--blend-b", type=float, default=0.85)
    parser.add_argument("--edge-strength", type=float, default=1.0)
    parser.add_argument("--tag", default="demo-blend-ab")
    parser.add_argument("--out", default="storage/outputs/demo_blend_ab")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
