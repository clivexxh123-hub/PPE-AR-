"""Real-ComfyUI A/B for human_wearing, for the demo evidence pack.

Runs in-process so the two stages are proven separately:

  stage 1  Pillow body-anchored pre-composite   -> human_wearing_input.png
  stage 2  ComfyUI img2img at several denoise   -> result.png

Requires a live ComfyUI on COMFYUI_BASE_URL and AI_ENGINE=comfyui.

    python scripts/demo_human_wearing_ab.py ^
        --human "D:\\...\\human_workwear_twoPersonBoard.jpg" --crop-left-half ^
        --helmet "D:\\...\\helmet_P10_orange_front.png" ^
        --vest   "D:\\...\\vest_multiPocket_orange_front.png"
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
from app.services.prompt_templates import build_managed_prompt  # noqa: E402

CASES = (
    ("helmet", "安全帽 P10", "安全帽"),
    ("vest", "多口袋反光马甲", "马甲"),
)


def _check_engine() -> None:
    if settings.ai_engine != "comfyui":
        raise SystemExit("AI_ENGINE 必须为 comfyui；mock 结果不能作为视觉验收依据。")
    try:
        response = httpx.get(f"{settings.comfyui_base_url}/system_stats", timeout=10)
        response.raise_for_status()
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
        ppe = Path(getattr(args, category) or "")
        if not ppe.is_file():
            print(f"SKIP {category}: 未提供素材")
            continue
        placement = resolve_human_wearing_placement(product_name, product_category, {})
        composite, composite_meta_path = render_human_wearing_design(
            f"{args.tag}-{category}", human, ppe, size=args.size,
            position_x_ratio=placement["position_x_ratio"],
            position_y_ratio=placement["position_y_ratio"],
            ppe_width_ratio=placement["ppe_width_ratio"],
            human_top_padding_ratio=placement["human_top_padding_ratio"],
            opacity=placement["opacity"],
            ppe_category=placement["ppe_category"],
        )
        composite_meta = json.loads(Path(composite_meta_path).read_text(encoding="utf-8"))
        print(f"COMPOSITE_PASS {category:6s} strategy={composite_meta['placement_strategy']} "
              f"paste=({composite_meta['paste_x']},{composite_meta['paste_y']}) "
              f"size={composite_meta['ppe_rendered_width']}x{composite_meta['ppe_rendered_height']}")

        prompt = build_managed_prompt(
            product_name=product_name, product_category=product_category,
            scene=args.scene, style=args.style, overrides=None, template_id=None,
            generation_mode="human_wearing", view=args.view,
            framing=args.framing, gender=args.gender,
        ).prompt

        cells: list[tuple[str, Path]] = [("composite", Path(composite))]
        for denoise in args.denoise:
            task_id = f"{args.tag}-{category}-d{int(denoise * 100)}"
            try:
                result, meta_path = await generate_comfyui_image(
                    task_id, prompt, args.size, "png",
                    product_image_path=Path(composite),
                    generation_mode="human_wearing", denoise=denoise,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"IMG2IMG_FAIL {category} denoise={denoise}: {exc}")
                continue
            meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
            print(f"IMG2IMG_PASS   {category:6s} denoise={meta['denoise']} -> {result}")
            cells.append((f"denoise {denoise}", Path(result)))
            report.append({"category": category, "denoise": denoise,
                           "result": str(result), "composite": composite_meta})
        rows.append((category, cells))

    if not rows:
        print("没有可用结果。")
        return 1

    width = max(len(cells) for _, cells in rows)
    with Image.open(rows[0][1][0][1]) as first:
        cell_w, cell_h = first.size
    sheet = Image.new("RGB", (cell_w * width, (cell_h + 40) * len(rows)), (250, 250, 250))
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
    parser = argparse.ArgumentParser(description="human_wearing 真实 ComfyUI A/B。")
    parser.add_argument("--human", required=True)
    parser.add_argument("--crop-left-half", action="store_true",
                        help="甲方人物图为两人拼版时，取左侧单人。")
    parser.add_argument("--helmet")
    parser.add_argument("--vest")
    parser.add_argument("--size", default="512x768")
    parser.add_argument("--scene", default="工地作业现场")
    parser.add_argument("--style", default="商业摄影")
    parser.add_argument("--view", default="front")
    parser.add_argument("--framing", default="half_body")
    parser.add_argument("--gender", default="female")
    parser.add_argument("--denoise", type=float, nargs="+", default=[0.30, 0.40, 0.50])
    parser.add_argument("--tag", default="demo-human-wearing-ab")
    parser.add_argument("--out", default="storage/outputs/demo_ab")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
