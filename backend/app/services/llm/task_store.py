from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlmodel import Session, select

from app import db
from app.models.entities import LlmTaskEntity

ACTIVE_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "interrupted"}


class LlmTaskCancelled(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_llm_task(*, user_id: str, project_id: str, operation: str) -> str:
    task_id = f"llm_task_{uuid4().hex[:16]}"
    now = _now()
    with Session(db.engine) as session:
        session.add(
            LlmTaskEntity(
                id=task_id,
                user_id=user_id,
                project_id=project_id,
                operation=operation,
                status="queued",
                stage="queued",
                message="任务已创建，正在等待执行。",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    return task_id


def mark_task_running(task_id: str) -> None:
    _update_task(task_id, status="running", stage="preparing", message="正在准备生成任务。")


def update_task_progress(
    task_id: str,
    *,
    stage: str,
    message: str,
    progress: int | None = None,
    detail: str = "",
) -> None:
    with Session(db.engine) as session:
        row = session.get(LlmTaskEntity, task_id)
        if not row:
            return
        if row.cancel_requested:
            raise LlmTaskCancelled("任务已取消。")
        row.status = "running"
        row.stage = stage
        row.message = message
        row.detail = detail
        if progress is not None:
            row.progress = max(0, min(int(progress), 99))
        row.updated_at = _now()
        session.add(row)
        session.commit()


def mark_task_completed(
    task_id: str,
    *,
    data: Any,
    meta: dict[str, Any] | None,
) -> None:
    now = _now()
    _update_task(
        task_id,
        status="completed",
        stage="complete",
        message="生成完成。",
        progress=100,
        result_json=json.dumps(data, ensure_ascii=False),
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
        completed_at=now,
    )


def mark_task_failed(task_id: str, message: str) -> None:
    now = _now()
    _update_task(
        task_id,
        status="failed",
        stage="failed",
        message="生成失败。",
        error_message=message,
        completed_at=now,
    )


def mark_task_cancelled(task_id: str) -> None:
    now = _now()
    _update_task(
        task_id,
        status="cancelled",
        stage="cancelled",
        message="任务已取消。",
        error_message="任务已取消。",
        completed_at=now,
    )


def request_task_cancel(task_id: str, *, user_id: str) -> LlmTaskEntity | None:
    with Session(db.engine) as session:
        row = session.get(LlmTaskEntity, task_id)
        if not row or (row.user_id and row.user_id != user_id):
            return None
        if row.status in TERMINAL_STATUSES:
            return row
        row.cancel_requested = True
        row.message = "正在取消任务，请稍候。"
        row.updated_at = _now()
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def get_llm_task(task_id: str, *, user_id: str) -> LlmTaskEntity | None:
    with Session(db.engine) as session:
        row = session.get(LlmTaskEntity, task_id)
        if not row or (row.user_id and row.user_id != user_id):
            return None
        session.expunge(row)
        return row


def recover_interrupted_llm_tasks() -> int:
    now = _now()
    with Session(db.engine) as session:
        rows = session.exec(select(LlmTaskEntity).where(LlmTaskEntity.status.in_(ACTIVE_STATUSES))).all()
        for row in rows:
            row.status = "interrupted"
            row.stage = "interrupted"
            row.message = "服务重启导致任务中断，请重新生成。"
            row.error_message = row.message
            row.updated_at = now
            row.completed_at = now
            session.add(row)
        session.commit()
        return len(rows)


def task_to_dict(row: LlmTaskEntity) -> dict[str, Any]:
    data: Any = None
    meta: dict[str, Any] = {}
    if row.result_json:
        try:
            data = json.loads(row.result_json)
        except json.JSONDecodeError:
            data = None
    if row.meta_json:
        try:
            decoded_meta = json.loads(row.meta_json)
            if isinstance(decoded_meta, dict):
                meta = decoded_meta
        except json.JSONDecodeError:
            pass
    return {
        "taskId": row.id,
        "projectId": row.project_id,
        "operation": row.operation,
        "status": row.status,
        "stage": row.stage,
        "message": row.message,
        "detail": row.detail,
        "progress": row.progress,
        "data": data,
        "meta": meta,
        "errorMessage": row.error_message,
        "cancelRequested": row.cancel_requested,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
        "completedAt": row.completed_at,
    }


def _update_task(task_id: str, **values: Any) -> None:
    with Session(db.engine) as session:
        row = session.get(LlmTaskEntity, task_id)
        if not row:
            return
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = _now()
        session.add(row)
        session.commit()
