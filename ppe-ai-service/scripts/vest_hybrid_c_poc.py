"""Vest Hybrid C PoC: graded identity-aware mask vs the formal 1d51e36 mask.

The formal pipeline is not touched.  This script reuses the exact geometry and
scene intermediates produced by the vest-ab-20260831 A/B run, so the only things
that differ between the two arms below are the mask and the denoise:

    A2  formal contact-band mask, denoise 0.38   (re-baseline on the repaired input)
    C1  Hybrid C graded mask,     denoise 0.60

Both arms go through the same single-composite workflow, and both are composited
back onto the same input in Python exactly once.  The formal workflow applies its
mask twice (ImageCompositeMasked plus the Python lock), which is harmless for a
binary mask but would square a graded one.

Run the mask preview first; it needs no GPU:

    python scripts/vest_hybrid_c_poc.py --dry-run

Then the real run against ComfyUI on 127.0.0.1:8188:

    python scripts/vest_hybrid_c_poc.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageChops, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.vest_hybrid_c_mask import (  # noqa: E402
    binary,
    build_hybrid_c_mask,
    repair_subject_mask,
)

POC_ROOT = Path(
    r"D:\Don't Click it\JOB\XVison\PPE_Test\PPE-AR-VEST-AB-POC-20260831"
    r"\ppe-ai-service\storage\outputs"
)
DEFAULT_GEOMETRY_DIR = POC_ROOT / "vest-ab-20260831-geometry"
DEFAULT_SCENE_DIR = POC_ROOT / "vest-ab-20260831-scene"
DEFAULT_EVIDENCE = POC_ROOT / "vest-ab-20260831-evidence" / "report.json"
DEFAULT_REFERENCE_A = POC_ROOT / "vest-ab-20260831-A-formal" / "result.png"
DEFAULT_OUT = POC_ROOT / "vest-hybridc-20260831"

NEGATIVE_PROMPT = (
    "flat sticker, pasted-on product, floating PPE, rigid cardboard clothing, duplicate vest, duplicate helmet, "
    "duplicate gloves, duplicate shoes, old PPE visible, green underlayer, fluorescent lime old vest, "
    "second vest inside neckline, wrong body position, broken neckline, sealed armholes, deformed PPE, extra PPE, "
    "distorted product structure, distorted face, changed identity, extra limbs, extra fingers, extra hands, "
    "extra feet, text, watermark, collage, low quality, unnatural pose"
)


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Same scene fit as human_scene_service._cover."""
    scale = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - size[0]) // 2)
    top = max(0, (resized.height - size[1]) // 2)
    return resized.crop((left, top, left + size[0], top + size[1]))


def _region_metrics(
    original: Image.Image, final: Image.Image, region: Image.Image
) -> dict[str, Any]:
    region_binary = binary(region, 128)
    pixels = sum(region_binary.histogram()[128:])
    if not pixels:
        return {"pixels": 0, "changed_pixels": 0, "changed_pct": 0.0, "mean_max_channel_delta": 0.0}
    delta = ImageChops.difference(original.convert("RGB"), final.convert("RGB"))
    per_pixel_max = ImageChops.lighter(
        ImageChops.lighter(delta.getchannel("R"), delta.getchannel("G")),
        delta.getchannel("B"),
    )
    masked = ImageChops.multiply(per_pixel_max, region_binary)
    histogram = masked.histogram()
    changed = sum(histogram[1:])
    total = sum(value * count for value, count in enumerate(histogram))
    return {
        "pixels": pixels,
        "changed_pixels": changed,
        "changed_pct": round(changed * 100.0 / pixels, 2),
        "mean_max_channel_delta": round(total / pixels, 2),
    }


class ComfyClient:
    def __init__(self, base_url: str, timeout: float = 300.0) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def check(self) -> dict[str, Any]:
        response = self._client.get("/system_stats")
        response.raise_for_status()
        return response.json()

    def upload(self, path: Path, name: str) -> str:
        with path.open("rb") as handle:
            response = self._client.post(
                "/upload/image",
                files={"image": (name, handle, "application/octet-stream")},
                data={"type": "input", "overwrite": "true"},
            )
        response.raise_for_status()
        payload = response.json()
        uploaded = payload.get("name") or name
        subfolder = payload.get("subfolder")
        return f"{subfolder}/{uploaded}" if subfolder else uploaded

    def run(self, workflow: dict[str, Any], client_id: str) -> tuple[bytes, dict[str, Any]]:
        response = self._client.post("/prompt", json={"prompt": workflow, "client_id": client_id})
        response.raise_for_status()
        prompt_id = response.json().get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI 未返回 prompt_id: {response.text}")
        for _ in range(200):
            history = self._client.get(f"/history/{prompt_id}")
            history.raise_for_status()
            item = history.json().get(prompt_id)
            if item:
                status = item.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI 执行失败: {status}")
                for node_output in item.get("outputs", {}).values():
                    for image in node_output.get("images", []):
                        if image.get("filename"):
                            view = self._client.get("/view", params=image)
                            view.raise_for_status()
                            return view.content, {"prompt_id": prompt_id, **item.get("status", {})}
            time.sleep(1.5)
        raise RuntimeError("等待 ComfyUI 结果超时。")


def _patch_workflow(
    template: dict[str, Any],
    *,
    prompt: str,
    input_name: str,
    mask_name: str,
    denoise: float,
    seed: int,
    prefix: str,
) -> dict[str, Any]:
    workflow = json.loads(json.dumps(template))
    workflow["6"]["inputs"]["text"] = prompt
    workflow["7"]["inputs"]["text"] = NEGATIVE_PROMPT
    workflow["10"]["inputs"]["image"] = input_name
    workflow["12"]["inputs"]["image"] = mask_name
    workflow["3"]["inputs"]["denoise"] = denoise
    workflow["3"]["inputs"]["seed"] = seed
    workflow["9"]["inputs"]["filename_prefix"] = prefix
    return workflow


def _contact_sheet(cells: list[list[tuple[str, Image.Image]]], path: Path) -> None:
    cell_width, cell_height = cells[0][0][1].size
    columns = max(len(row) for row in cells)
    sheet = Image.new(
        "RGB", (cell_width * columns, (cell_height + 28) * len(cells)), (248, 248, 248)
    )
    draw = ImageDraw.Draw(sheet)
    for row_index, row in enumerate(cells):
        for column_index, (label, image) in enumerate(row):
            x = cell_width * column_index
            y = (cell_height + 28) * row_index
            sheet.paste(image.convert("RGB").resize((cell_width, cell_height)), (x, y + 28))
            draw.text((x + 8, y + 8), label, fill=(20, 20, 20))
    sheet.save(path, format="PNG")


def main() -> int:
    parser = argparse.ArgumentParser(description="Vest Hybrid C PoC")
    parser.add_argument("--geometry-dir", type=Path, default=DEFAULT_GEOMETRY_DIR)
    parser.add_argument("--scene-dir", type=Path, default=DEFAULT_SCENE_DIR)
    parser.add_argument("--evidence-report", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--reference-a", type=Path, default=DEFAULT_REFERENCE_A)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--comfyui", default="http://127.0.0.1:8188")
    parser.add_argument("--seed", type=int, default=2026083101)
    parser.add_argument("--denoise-c", type=float, default=0.60)
    parser.add_argument("--denoise-a", type=float, default=0.38)
    parser.add_argument("--no-rebaseline", action="store_true")
    parser.add_argument("--no-repair-subject-mask", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="只产出 mask 证据，不调用 ComfyUI")
    args = parser.parse_args()

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    evidence = json.loads(args.evidence_report.read_text(encoding="utf-8"))
    prompt: str = evidence["prompt"]
    geometry = json.loads(
        (args.geometry_dir / "human_wearing_metadata.json").read_text(encoding="utf-8")
    )
    anchors = geometry["body_anchors"]
    placement = geometry["placements"][0]

    with Image.open(args.geometry_dir / "human_wearing_product_layer.png") as source:
        product_layer = source.convert("RGBA")
    with Image.open(args.geometry_dir / "human_wearing_base.png") as source:
        base_human = source.convert("RGB")
    with Image.open(args.geometry_dir / "human_wearing_input.png") as source:
        human_composite = source.convert("RGB")
    with Image.open(args.geometry_dir / "human_wearing_mask.png") as source:
        formal_mask = source.convert("L")
    with Image.open(args.scene_dir / "human_scene_subject_mask.png") as source:
        subject_mask = source.convert("L")
    with Image.open(args.scene_dir / "human_scene_shape_prior.png") as source:
        shape_prior = source.convert("L")

    scene_metadata = json.loads(
        (args.scene_dir / "human_scene_metadata.json").read_text(encoding="utf-8")
    )
    with Image.open(scene_metadata["scene_reference_path"]) as source:
        scene = _cover(source.convert("RGB"), human_composite.size)

    if args.no_repair_subject_mask:
        effective_subject_mask = subject_mask
        repair_metadata: dict[str, Any] = {"applied": False}
    else:
        effective_subject_mask, repair_metadata = repair_subject_mask(
            subject_mask, shape_prior, anchors
        )
        repair_metadata["applied"] = True
        effective_subject_mask.save(out_dir / "subject_mask_repaired.png", format="PNG")
        ImageChops.difference(binary(subject_mask, 96), binary(effective_subject_mask, 96)).save(
            out_dir / "subject_mask_repair_delta.png", format="PNG"
        )
        print(f"SUBJECT_MASK_REPAIR recovered={repair_metadata['recovered_pixels']}px")

    scene_input = Image.composite(human_composite, scene, effective_subject_mask)
    scene_input_path = out_dir / "hybridc_scene_input.png"
    scene_input.save(scene_input_path, format="PNG")

    hybrid = build_hybrid_c_mask(
        product_layer=product_layer,
        base_human=base_human,
        subject_mask=effective_subject_mask,
        anchors=anchors,
        placement=placement,
    )
    hybrid_mask_path = out_dir / "hybridc_mask.png"
    hybrid.mask.save(hybrid_mask_path, format="PNG")
    hybrid.overlay.save(out_dir / "hybridc_mask_overlay.png", format="PNG")
    print(
        "HYBRID_C_MASK "
        f"coverage_any={hybrid.metadata['coverage_any']} "
        f"coverage_strong={hybrid.metadata['coverage_strong']} "
        f"mean_grade_over_vest={hybrid.metadata['mean_grade_over_vest']} "
        f"identity_share={hybrid.metadata['identity_core_share_of_vest']} "
        f"(formal A coverage_strong=0.1327)"
    )
    if hybrid.metadata["identity_core_share_of_vest"] > 0.45:
        print(
            "WARN  identity_core 占马甲比例过高，Hybrid C 会退化成 A；"
            "需要收紧 product_identity_mask 的阈值。"
        )

    report: dict[str, Any] = {
        "run": "vest-hybridc-20260831",
        "formal_baseline_commit": "1d51e36",
        "derived_from": str(args.evidence_report),
        "seed": args.seed,
        "prompt": prompt,
        "subject_mask_repair": repair_metadata,
        "shared_scene_input": str(scene_input_path),
        "hybrid_c_mask": str(hybrid_mask_path),
        "hybrid_c_mask_metadata": hybrid.metadata,
        "arms": {},
        "metrics": {},
    }

    if args.dry_run:
        (out_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _contact_sheet(
            [
                [
                    ("input (repaired)", scene_input),
                    ("formal mask (A)", formal_mask),
                    ("hybrid C mask", hybrid.mask),
                    ("hybrid C overlay", hybrid.overlay),
                ]
            ],
            out_dir / "hybridc_mask_preview.png",
        )
        print(f"DRY_RUN_OK  {out_dir / 'hybridc_mask_preview.png'}")
        return 0

    client = ComfyClient(args.comfyui)
    stats = client.check()
    print(f"COMFYUI_OK  {args.comfyui}  {stats.get('system', {}).get('comfyui_version', 'unknown')}")
    template = json.loads(
        (PROJECT_ROOT / "app" / "templates" / "comfyui" / "vest_hybrid_c_workflow.json").read_text(
            encoding="utf-8-sig"
        )
    )

    arms = [("C1", hybrid_mask_path, hybrid.mask, args.denoise_c)]
    if not args.no_rebaseline:
        arms.insert(0, ("A2", args.geometry_dir / "human_wearing_mask.png", formal_mask, args.denoise_a))

    results: dict[str, Image.Image] = {}
    input_name = client.upload(scene_input_path, "vest_hybrid_c_input.png")
    for arm, mask_path, mask_image, denoise in arms:
        mask_name = client.upload(mask_path, f"vest_hybrid_c_{arm}_mask.png")
        workflow = _patch_workflow(
            template,
            prompt=prompt,
            input_name=input_name,
            mask_name=mask_name,
            denoise=denoise,
            seed=args.seed,
            prefix=f"ppe_vest_hybridc_{arm}",
        )
        raw_bytes, status = client.run(workflow, f"vest-hybridc-{arm}")
        raw_path = out_dir / f"{arm}_raw_decode.png"
        raw_path.write_bytes(raw_bytes)
        with Image.open(raw_path) as source:
            generated = source.convert("RGB")
        # The single, authoritative application of the mask.  mask=0 is now a
        # real byte-level invariant; gray values blend proportionally.
        final = Image.composite(generated, scene_input, mask_image)
        final_path = out_dir / f"{arm}_final.png"
        final.save(final_path, format="PNG")
        results[arm] = final

        locked = binary(mask_image, 1).point(lambda value: 255 - value)
        leak = sum(
            ImageChops.multiply(
                ImageChops.difference(final, scene_input).convert("L"), locked
            ).histogram()[1:]
        )
        report["arms"][arm] = {
            "denoise": denoise,
            "mask": str(mask_path),
            "raw_decode": str(raw_path),
            "final": str(final_path),
            "hard_locked_leak_pixels": leak,
            "comfyui_status": status,
        }
        print(f"ARM_DONE    {arm} denoise={denoise} leak={leak}px -> {final_path}")
        report["metrics"][arm] = {
            name: _region_metrics(scene_input, final, region)
            for name, region in hybrid.regions.items()
        }

    for arm, metrics in report["metrics"].items():
        print(f"\nMETRICS {arm}")
        for name, values in metrics.items():
            print(
                f"  {name:16s} px={values['pixels']:>7d} "
                f"changed={values['changed_pct']:>6.2f}% "
                f"meanDelta={values['mean_max_channel_delta']:>6.2f}"
            )

    sheet_rows = [
        [
            ("input (repaired)", scene_input),
            ("formal mask (A)", formal_mask),
            ("hybrid C mask", hybrid.mask),
            ("hybrid C overlay", hybrid.overlay),
        ]
    ]
    bottom: list[tuple[str, Image.Image]] = []
    if args.reference_a.exists():
        with Image.open(args.reference_a) as source:
            bottom.append(("A original (1d51e36)", source.convert("RGB")))
    if "A2" in results:
        bottom.append((f"A2 formal mask d={args.denoise_a}", results["A2"]))
    bottom.append((f"C1 hybrid d={args.denoise_c}", results["C1"]))
    sheet_rows.append(bottom)
    sheet_path = out_dir / "hybridc_contact_sheet.png"
    _contact_sheet(sheet_rows, sheet_path)

    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nVISUAL_EVIDENCE {sheet_path}")
    print(f"REPORT          {out_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
