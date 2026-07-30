import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://129.204.115.36:9531/api"
DEFAULT_SERVICE_URL = "http://127.0.0.1:8000"


PRODUCT_PROFILES = {
    "helmet": {
        "keywords": ["安全帽", "头部", "矿帽", "头盔"],
        "scene_hint": "中性浅灰产品摄影背景，少量现代工厂安全生产氛围",
        "product_focus": "单个工业安全帽，帽壳轮廓清晰，正面或三分之二角度展示，材质细节清楚",
    },
    "gloves": {
        "keywords": ["手套", "手部"],
        "scene_hint": "中性浅灰产品摄影背景，少量工业仓储和生产线安全作业氛围",
        "product_focus": "一副防护手套作为唯一主体，掌面和纹理清晰，平铺或轻微立体摆放",
    },
    "face": {
        "keywords": ["面罩", "口罩", "呼吸", "面部"],
        "scene_hint": "中性浅灰产品摄影背景，少量洁净车间安全防护氛围",
        "product_focus": "单个防护面罩或面部防护产品，透明部件清晰，边缘和结构完整",
    },
    "eyewear": {
        "keywords": ["护目镜", "眼镜", "眼部", "防护镜"],
        "scene_hint": "中性浅灰产品摄影背景，少量实验室或工业安全检测氛围",
        "product_focus": "单个护目镜或防护眼镜，镜片透明，镜框轮廓清晰，产品居中",
    },
    "vest": {
        "keywords": ["反光", "背心", "身体", "防护服", "雨衣"],
        "scene_hint": "中性浅灰产品摄影背景，少量施工现场安全作业氛围",
        "product_focus": "单件反光背心或身体防护用品，平整展开，反光条和颜色清晰",
    },
    "fall": {
        "keywords": ["坠落", "安全带", "连接件"],
        "scene_hint": "中性浅灰产品摄影背景，少量高空作业安全防护氛围",
        "product_focus": "单个高空防护装备或连接件，结构清楚，金属和织带细节清晰",
    },
}


def _request_json(url: str, method: str = "GET", data: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=120) as response:
        text = response.read().decode("utf-8")
    return json.loads(text)


def _fetch_products(base_url: str, page: int, size: int) -> dict[str, Any]:
    query = urlencode({"page": page, "size": size})
    return _request_json(f"{base_url.rstrip('/')}/products?{query}")


def _category_path(product: dict[str, Any]) -> str:
    cate_full_name = str(product.get("cate_full_name") or "").strip()
    if cate_full_name:
        return cate_full_name

    parts = [
        str(product.get("category_level_1") or "").strip(),
        str(product.get("category_level_2") or "").strip(),
        str(product.get("category_level_3") or "").strip(),
    ]
    return "/".join(part for part in parts if part) or "PPE 安全防护用品"


def _default_scene(category_path: str, product_name: str) -> str:
    profile = _product_profile(category_path, product_name)
    return f"{profile['scene_hint']}，场景只作为风格暗示，不绘制完整工厂、人物或复杂环境"


def _product_profile(category_path: str, product_name: str) -> dict[str, str]:
    text = f"{category_path} {product_name}"
    for profile in PRODUCT_PROFILES.values():
        if any(keyword in text for keyword in profile["keywords"]):
            return profile
    return {
        "scene_hint": "中性浅灰产品摄影背景，少量现代工业安全防护氛围",
        "product_focus": "单个 PPE 安全防护产品作为唯一主体，产品轮廓清晰，材质细节清楚",
    }


def _clean_product_name(name: str) -> str:
    name = re.sub(r"[（）()]+", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def _colors(product: dict[str, Any]) -> list[str]:
    colors = product.get("colors") or []
    if isinstance(colors, str):
        try:
            parsed = json.loads(colors)
            colors = parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            colors = [item.strip() for item in re.split(r"[,，、/]", colors) if item.strip()]
    if not isinstance(colors, list):
        return []
    return [str(item).strip() for item in colors if str(item).strip()]


def _style_prompt(product_focus: str, colors: list[str]) -> str:
    color_text = f"主色参考：{'、'.join(colors)}。" if colors else ""
    return (
        "真实商业产品摄影风格，single product, product-centered, close-up studio product photo. "
        f"{color_text}{product_focus}。"
        "干净白色或浅灰背景，自然阴影，专业布光，清晰对焦，高细节，B2B 产品目录图。"
        "不要文字、不要标签、不要水印、不要海报拼贴、不要网页截图、不要多人或人物佩戴、不要复杂工厂背景。"
    )


def _presentation_requirements(product_focus: str) -> list[str]:
    return [
        "exactly one main PPE product",
        "standalone product, not worn by a person",
        "centered foreground product composition",
        "plain white or light gray studio background",
        "sharp focus, realistic material details",
        product_focus,
    ]


def _generation_constraints() -> list[str]:
    return [
        "no text",
        "no watermark",
        "no logo unless provided later",
        "no collage",
        "no website screenshot",
        "no multiple panels",
        "no person",
        "no face",
        "no worker wearing the product",
        "no full factory room",
        "no machinery as main subject",
        "no duplicated products",
    ]


def _to_generate_payload(product: dict[str, Any]) -> dict[str, Any]:
    product_name = _clean_product_name(str(product.get("product_name") or product.get("goods_name") or "PPE 安全防护用品"))
    category = _category_path(product)
    colors = _colors(product)
    profile = _product_profile(category, product_name)
    product_focus = profile["product_focus"]

    prompt_overrides: dict[str, Any] = {
        "goal": "展示 PPE 产品的专业、安全、可靠",
        "category_path": category,
        "product_focus": product_focus,
        "presentation_requirements": _presentation_requirements(product_focus),
        "generation_constraints": _generation_constraints(),
        "negative_hints": ", ".join(_generation_constraints()),
        "goods_id": product.get("goods_id"),
        "goods_no": product.get("goods_no"),
        "has_files": product.get("has_files"),
        "file_count": product.get("file_count"),
    }
    if colors:
        prompt_overrides["colors"] = colors
        prompt_overrides["color_hint"] = "、".join(colors)

    return {
        "product_name": product_name,
        "product_category": category,
        "scene": _default_scene(category, product_name),
        "style": _style_prompt(product_focus, colors),
        "size": "512x512",
        "prompt_overrides": prompt_overrides,
        "output_format": "png",
        "sync": True,
    }


def _match_category(product: dict[str, Any], category: str | None) -> bool:
    if not category:
        return True
    needle = category.strip().lower()
    haystack = " ".join(
        str(product.get(key) or "")
        for key in (
            "product_name",
            "cate_full_name",
            "category_level_1",
            "category_level_2",
            "category_level_3",
        )
    ).lower()
    return needle in haystack


def _is_test_product(product: dict[str, Any]) -> bool:
    text = " ".join(
        str(product.get(key) or "")
        for key in ("product_name", "goods_no", "goods_id")
    ).lower()
    return "测试" in text or "test" in text


def _payload_filename(product: dict[str, Any]) -> str:
    product_id = product.get("id") or product.get("goods_id") or "unknown"
    return f"real_product_{product_id}.json"


def _save_payload(output_dir: Path, product: dict[str, Any], payload: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / _payload_filename(product)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _generate(service_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json(f"{service_url.rstrip('/')}/ai/generate", method="POST", data=payload)


def _local_output_path(result_url: str | None) -> str | None:
    if not result_url:
        return None
    parts = result_url.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "outputs":
        return None
    return str(ROOT / "storage" / "outputs" / parts[1] / parts[2])


def main() -> None:
    parser = argparse.ArgumentParser(description="从真实商品接口抽样生成 /ai/generate payload。")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="老板商品 API 地址，默认 http://129.204.115.36:9531/api。")
    parser.add_argument("--service-url", default=DEFAULT_SERVICE_URL, help="本地 PPE AI Service 地址，默认 http://127.0.0.1:8000。")
    parser.add_argument("--page", type=int, default=1, help="商品列表页码。")
    parser.add_argument("--size", type=int, default=20, help="每页读取数量。")
    parser.add_argument("--limit", type=int, default=3, help="最多保存多少条 payload，默认 3。")
    parser.add_argument("--category", default=None, help="按商品名或分类关键词过滤，例如 安全帽、手套。")
    parser.add_argument("--generate", action="store_true", help="保存 payload 后直接调用 /ai/generate。")
    parser.add_argument("--include-test-data", action="store_true", help="包含商品名或货号中带测试/test 的记录。默认跳过。")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "samples" / "real_product_payloads",
        help="payload 输出目录，默认 samples/real_product_payloads。",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    response = _fetch_products(args.base_url, args.page, args.size)
    products = response.get("list") or response.get("data") or []
    if not isinstance(products, list):
        raise SystemExit("商品接口返回格式不符合预期：没有 list 或 data 数组。")

    selected = [
        product
        for product in products
        if _match_category(product, args.category)
        and (args.include_test_data or not _is_test_product(product))
    ]
    selected = selected[: max(args.limit, 0)]

    results = []
    for product in selected:
        payload = _to_generate_payload(product)
        payload_path = _save_payload(output_dir, product, payload)

        generation = None
        generation_error = None
        if args.generate:
            try:
                generation = _generate(args.service_url, payload)
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
                generation_error = str(error)

        result_url = generation.get("result_url") if isinstance(generation, dict) else None
        metadata_url = generation.get("metadata_url") if isinstance(generation, dict) else None
        results.append(
            {
                "product_id": product.get("id"),
                "product_name": product.get("product_name"),
                "product_category": payload["product_category"],
                "has_files": product.get("has_files"),
                "file_count": product.get("file_count"),
                "payload_path": str(payload_path),
                "generated": generation is not None,
                "generation": generation,
                "generation_error": generation_error,
                "result_path": _local_output_path(result_url),
                "metadata_path": _local_output_path(metadata_url),
            }
        )

    summary = {
        "base_url": args.base_url,
        "page": args.page,
        "size": args.size,
        "limit": args.limit,
        "category": args.category,
        "api_total": response.get("total"),
        "fetched": len(products),
        "selected": len(selected),
        "output_dir": str(output_dir),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("已取消。")
