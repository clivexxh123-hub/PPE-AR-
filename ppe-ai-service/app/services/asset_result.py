import hashlib
from pathlib import Path

from PIL import Image

from app.schemas.business_protocol import TaskResult


def build_local_task_result(task_id: str, image_path: Path) -> TaskResult:
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    with Image.open(image_path) as image:
        width, height = image.size
    return TaskResult(
        assetKey=f"local://outputs/{task_id}/{image_path.name}",
        width=width,
        height=height,
        hash=digest,
    )
