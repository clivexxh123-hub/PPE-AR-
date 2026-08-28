"""Run the local PPE AI regression suite with a compact final summary."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


@dataclass(frozen=True)
class Check:
    name: str
    command: list[str]
    engine: str | None = None


def _run(check: Check) -> tuple[bool, str]:
    environment = os.environ.copy()
    if check.engine:
        environment["AI_ENGINE"] = check.engine
    result = subprocess.run(
        check.command,
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return True, ""
    output = (result.stdout + result.stderr).strip().splitlines()
    return False, "\n".join(output[-8:]) or f"exit code {result.returncode}"


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 PPE AI 一期本地回归测试。")
    parser.add_argument(
        "--comfyui",
        action="store_true",
        help="额外执行一次真实 ComfyUI 的 /ai/generate 回归；需要先启动 ComfyUI。",
    )
    args = parser.parse_args()

    checks = [
        Check(
            "Python 编译检查",
            [
                PYTHON,
                "-m",
                "compileall",
                "-q",
                "app",
                "scripts/business_logo_task_smoke_test.py",
                "scripts/logo_remove_bg_smoke_test.py",
                "scripts/printed_design_generation_smoke_test.py",
                "scripts/scene_generation_smoke_test.py",
                "scripts/security_smoke_test.py",
                "scripts/async_task_lifecycle_smoke_test.py",
                "scripts/regenerate_smoke_test.py",
                "scripts/human_wearing_smoke_test.py",
                "scripts/logo_auto_placement_smoke_test.py",
                "scripts/helmet_print_centering_smoke_test.py",
                "scripts/formal_task_protocol_smoke_test.py",
                "scripts/callback_protocol_smoke_test.py",
                "scripts/presigned_upload_protocol_smoke_test.py",
                "scripts/image_url_security_smoke_test.py",
                "scripts/prompt_management_smoke_test.py",
                "scripts/logo_template_smoke_test.py",
                "scripts/human_wearing_categories_smoke_test.py",
                "scripts/human_wearing_model_anchor_audit.py",
                "scripts/logo_archive_smoke_test.py",
                "scripts/runtime_metadata_smoke_test.py",
            ],
        ),
        Check("/ai/generate mock 回归", [PYTHON, "scripts/api_smoke_test.py"], engine="mock"),
        Check("统一 /ai/tasks 回归", [PYTHON, "scripts/business_logo_task_smoke_test.py"], engine="mock"),
        Check("Logo 抠图回归", [PYTHON, "scripts/logo_remove_bg_smoke_test.py"], engine="mock"),
        Check("printed_design 到 image_generation 回归", [PYTHON, "scripts/printed_design_generation_smoke_test.py"], engine="mock"),
        Check("metadata 脱敏与 SSRF 防护", [PYTHON, "scripts/security_smoke_test.py"], engine="mock"),
        Check("异步任务状态回归", [PYTHON, "scripts/async_task_lifecycle_smoke_test.py"], engine="mock"),
        Check("图片重新生成回归", [PYTHON, "scripts/regenerate_smoke_test.py"], engine="mock"),
        Check("human_wearing 回归", [PYTHON, "scripts/human_wearing_smoke_test.py"], engine="mock"),
        Check("Logo 自动定位与缩放", [PYTHON, "scripts/logo_auto_placement_smoke_test.py"], engine="mock"),
        Check("安全帽正背面印刷居中", [PYTHON, "scripts/helmet_print_centering_smoke_test.py"], engine="mock"),
        Check("正式任务协议适配", [PYTHON, "scripts/formal_task_protocol_smoke_test.py"], engine="mock"),
        Check("签名 callback 协议", [PYTHON, "scripts/callback_protocol_smoke_test.py"], engine="mock"),
        Check("预签名 PUT 上传协议", [PYTHON, "scripts/presigned_upload_protocol_smoke_test.py"], engine="mock"),
        Check("输入图片 URL 安全", [PYTHON, "scripts/image_url_security_smoke_test.py"], engine="mock"),
        Check("Prompt 管理 MVP", [PYTHON, "scripts/prompt_management_smoke_test.py"], engine="mock"),
        Check("Logo 模板保存读取 MVP", [PYTHON, "scripts/logo_template_smoke_test.py"], engine="mock"),
        Check("human_wearing 多 PPE 类别兼容", [PYTHON, "scripts/human_wearing_categories_smoke_test.py"], engine="mock"),
        Check("标准模特人体锚点审计", [PYTHON, "scripts/human_wearing_model_anchor_audit.py"], engine="mock"),
        Check("Logo 素材归档 MVP", [PYTHON, "scripts/logo_archive_smoke_test.py"], engine="mock"),
        Check("运行引擎与 denoise metadata", [PYTHON, "scripts/runtime_metadata_smoke_test.py"], engine="mock"),
        Check("Git diff 检查", ["git", "diff", "--check", "--", "."]),
        Check("scene_generation regression", [PYTHON, "scripts/scene_generation_smoke_test.py"], engine="mock"),
    ]
    skipped = []
    if args.comfyui:
        checks.append(Check("/ai/generate 真实 ComfyUI 回归", [PYTHON, "scripts/api_smoke_test.py"], engine="comfyui"))
    else:
        skipped.append("/ai/generate 真实 ComfyUI 回归（使用 --comfyui 启用）")

    passed: list[str] = []
    failed: list[tuple[str, str]] = []
    for check in checks:
        ok, detail = _run(check)
        if ok:
            passed.append(check.name)
        else:
            failed.append((check.name, detail))

    print("\nPPE_AI_REGRESSION_SUMMARY")
    print(f"PASSED ({len(passed)}):")
    for name in passed:
        print(f"  - {name}")
    print(f"FAILED ({len(failed)}):")
    for name, detail in failed:
        print(f"  - {name}")
        print(f"    {detail}")
    print(f"SKIPPED ({len(skipped)}):")
    for name in skipped:
        print(f"  - {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
