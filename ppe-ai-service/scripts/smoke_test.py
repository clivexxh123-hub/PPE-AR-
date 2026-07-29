import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.schemas.tasks import GenerateRequest, TaskStatus  # noqa: E402
from app.services.mock_engine import generate_mock_image  # noqa: E402
from app.services.prompt_templates import build_prompt  # noqa: E402
from app.services.task_store import create_task, load_task, save_task  # noqa: E402


def main() -> None:
    request_path = ROOT / "samples" / "generate_request.json"
    payload = GenerateRequest.model_validate(json.loads(request_path.read_text(encoding="utf-8-sig")))
    task = create_task("smoke.ai.generate", payload.model_dump(mode="json"))
    task.status = TaskStatus.running
    task.message = "Smoke test running."
    save_task(task)

    prompt = build_prompt(
        product_name=payload.product_name,
        product_category=payload.product_category,
        scene=payload.scene,
        style=payload.style,
        overrides=payload.prompt_overrides,
    )
    image_path, metadata_path = generate_mock_image(task.task_id, prompt, payload.size, payload.output_format)

    task.status = TaskStatus.succeeded
    task.message = "Smoke test succeeded."
    task.output_path = str(image_path)
    task.metadata_path = str(metadata_path)
    task.result_url = f"/outputs/{task.task_id}/{image_path.name}"
    task.metadata_url = f"/outputs/{task.task_id}/{metadata_path.name}"
    save_task(task)

    saved = load_task(task.task_id)
    print(json.dumps(saved.model_dump() if saved else {}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
