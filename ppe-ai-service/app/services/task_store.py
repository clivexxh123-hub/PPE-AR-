import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import ensure_storage_dirs, settings
from app.schemas.tasks import TaskRecord, TaskResponse, TaskStatus


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _task_path(task_id: str) -> Path:
    return settings.task_dir / f"{task_id}.json"


def create_task(kind: str, request_payload: dict[str, Any]) -> TaskRecord:
    ensure_storage_dirs()
    task_id = uuid.uuid4().hex
    record = TaskRecord(
        task_id=task_id,
        status=TaskStatus.queued,
        message="Task queued.",
        kind=kind,
        request=request_payload,
    )
    save_task(record, extra={"created_at": _now(), "updated_at": _now()})
    return record


def save_task(record: TaskRecord, extra: dict[str, Any] | None = None) -> None:
    ensure_storage_dirs()
    payload = record.model_dump()
    if extra:
        payload.update(extra)
    existing = {}
    path = _task_path(record.task_id)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("created_at", existing.get("created_at", _now()))
    payload["updated_at"] = _now()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_task(task_id: str) -> TaskRecord | None:
    path = _task_path(task_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return TaskRecord.model_validate(payload)


def to_response(record: TaskRecord) -> TaskResponse:
    return TaskResponse(
        task_id=record.task_id,
        status=record.status,
        message=record.message,
        result_url=record.result_url,
        metadata_url=record.metadata_url,
    )
