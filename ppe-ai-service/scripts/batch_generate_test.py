import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402


def _read_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _resolve_output_path(result_url: str | None) -> str | None:
    if not result_url:
        return None
    parts = result_url.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "outputs":
        return None
    return str(ROOT / "storage" / "outputs" / parts[1] / parts[2])


def _run_sample(client: TestClient, sample_path: Path) -> dict[str, Any]:
    payload = _read_payload(sample_path)
    response = client.post("/ai/generate", json=payload)
    response_data = response.json()

    result_url = response_data.get("result_url") if isinstance(response_data, dict) else None
    metadata_url = response_data.get("metadata_url") if isinstance(response_data, dict) else None
    result_path = _resolve_output_path(result_url)
    metadata_path = _resolve_output_path(metadata_url)

    return {
        "sample_file": str(sample_path),
        "product_name": payload.get("product_name"),
        "http_status": response.status_code,
        "status": response_data.get("status") if isinstance(response_data, dict) else None,
        "task_id": response_data.get("task_id") if isinstance(response_data, dict) else None,
        "result_url": result_url,
        "metadata_url": metadata_url,
        "result_path": result_path,
        "metadata_path": metadata_path,
        "result_exists": Path(result_path).exists() if result_path else False,
        "metadata_exists": Path(metadata_path).exists() if metadata_path else False,
        "error": response_data if response.status_code >= 400 else None,
    }


def _sample_files(samples_dir: Path, limit: int | None) -> list[Path]:
    files = sorted(samples_dir.glob("*.json"))
    if limit is not None:
        return files[: max(limit, 0)]
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="批量调用 /ai/generate 验证 PPE 产品样例。")
    parser.add_argument(
        "--samples-dir",
        type=Path,
        default=ROOT / "samples" / "product_payloads",
        help="样例 JSON 目录，默认 samples/product_payloads。",
    )
    parser.add_argument("--limit", type=int, default=None, help="只运行前 N 个样例，避免一次生成太多。")
    args = parser.parse_args()

    samples_dir = args.samples_dir
    if not samples_dir.is_absolute():
        samples_dir = ROOT / samples_dir
    if not samples_dir.exists():
        raise SystemExit(f"样例目录不存在：{samples_dir}")

    files = _sample_files(samples_dir, args.limit)
    if not files:
        raise SystemExit(f"样例目录下没有 JSON 文件：{samples_dir}")

    client = TestClient(app)
    results = [_run_sample(client, sample_path) for sample_path in files]
    summary = {
        "samples_dir": str(samples_dir),
        "total": len(results),
        "succeeded": sum(1 for item in results if item["status"] == "succeeded"),
        "failed": sum(1 for item in results if item["status"] != "succeeded"),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
