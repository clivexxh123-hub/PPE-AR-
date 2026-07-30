import hashlib
from pathlib import Path

from PIL import Image

from app.schemas.business_protocol import TaskResult


def build_business_task_result(
    tenant_id: str,
    job_id: str,
    attempt: int,
    image_path: Path,
    asset_key: str | None = None,
) -> TaskResult:
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    with Image.open(image_path) as image:
        width, height = image.size

    ext = image_path.suffix.lstrip(".").lower() or "png"
    return TaskResult(
        assetKey=asset_key or f"results/{tenant_id}/{job_id}/attempt-{attempt}/result.{ext}",
        width=width,
        height=height,
        hash=digest,
    )
