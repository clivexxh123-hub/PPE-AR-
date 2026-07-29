"""检查本机 ComfyUI 是否具备被 PPE AI 服务调用的基本条件。"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

COMFYUI_BASE_URL = "http://127.0.0.1:8188"
MODEL_ROOT = Path(r"D:\Comfy-Desktop\ComfyUI-Shared\models")
MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".gguf"}


def request_json(path: str) -> dict[str, Any]:
    url = f"{COMFYUI_BASE_URL}{path}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def list_model_files() -> list[Path]:
    if not MODEL_ROOT.exists():
        return []
    return [path for path in MODEL_ROOT.rglob("*") if path.is_file() and path.suffix.lower() in MODEL_EXTENSIONS]


def get_available_names(node: str, input_name: str) -> list[str]:
    try:
        info = request_json(f"/object_info/{node}")
    except Exception:
        return []
    node_info = info.get(node, {})
    required = node_info.get("input", {}).get("required", {})
    value = required.get(input_name, [])
    if isinstance(value, list) and value and isinstance(value[0], list):
        return [str(item) for item in value[0]]
    return []


def main() -> int:
    print("检查 ComfyUI 连接...")
    try:
        stats = request_json("/system_stats")
    except urllib.error.URLError as exc:
        print(f"失败：无法连接 {COMFYUI_BASE_URL}。请先启动 ComfyUI Desktop。")
        print(f"详细错误：{exc}")
        return 1

    system = stats.get("system", {})
    devices = stats.get("devices", [])
    print(f"ComfyUI 版本：{system.get('comfyui_version', '未知')}")
    print(f"PyTorch 版本：{system.get('pytorch_version', '未知')}")

    if devices:
        device = devices[0]
        vram_gb = round(float(device.get("vram_total", 0)) / 1024 / 1024 / 1024, 2)
        print(f"GPU：{device.get('name', '未知')}，显存约 {vram_gb} GB")
    else:
        print("警告：ComfyUI 没有返回 GPU 信息。")

    model_files = list_model_files()
    checkpoint_names = get_available_names("CheckpointLoaderSimple", "ckpt_name")
    unet_names = get_available_names("UNETLoader", "unet_name")

    print(f"模型目录：{MODEL_ROOT}")
    print(f"扫描到模型文件数量：{len(model_files)}")
    print(f"ComfyUI 可选 checkpoint 数量：{len(checkpoint_names)}")
    print(f"ComfyUI 可选 diffusion/UNet 数量：{len(unet_names)}")

    for path in model_files[:10]:
        size_gb = round(path.stat().st_size / 1024 / 1024 / 1024, 2)
        print(f"- {path.relative_to(MODEL_ROOT)}（{size_gb} GB）")

    print("\n结论：")
    if not model_files and not checkpoint_names and not unet_names:
        print("ComfyUI 后端已经可用，但当前还没有可用于出图的模型。下一步请在 ComfyUI Desktop 里下载或导入模型。")
        return 2

    print("ComfyUI 后端和模型基础条件已具备。下一步请在 ComfyUI Desktop 里跑通一次文生图，并导出 API Format 工作流 JSON。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
