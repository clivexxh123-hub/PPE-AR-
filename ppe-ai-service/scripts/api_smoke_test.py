import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402


def main() -> None:
    client = TestClient(app)
    health = client.get("/health")
    health.raise_for_status()
    assert health.json()["engine"] == "mock"

    payload = json.loads((ROOT / "samples" / "generate_request.json").read_text(encoding="utf-8-sig"))
    payload["sync"] = True
    generate = client.post("/ai/generate", json=payload)
    generate.raise_for_status()
    generate_data = generate.json()

    task = client.get(f"/tasks/{generate_data['task_id']}")
    task.raise_for_status()

    print(json.dumps({"health": health.json(), "generate": generate_data, "task": task.json()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
