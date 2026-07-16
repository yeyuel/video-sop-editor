from __future__ import annotations

import json
import queue
import threading
from collections.abc import Callable, Iterator
from typing import Any

from sqlmodel import Session

from app import db
from app.api.meta import merge_response_meta
from app.runtime.shutdown import is_shutting_down
from app.services.llm.task_store import (
    LlmTaskCancelled,
    create_llm_task,
    mark_task_cancelled,
    mark_task_completed,
    mark_task_failed,
    mark_task_running,
    update_task_progress,
)

QUEUE_POLL_SEC = 1.0


def format_sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def run_streaming_task(
    task: Callable[[Session, Callable[..., None]], Any],
    *,
    serialize_complete: Callable[[Any], tuple[Any, dict[str, str] | None]],
    user_id: str = "",
    project_id: str = "",
    operation: str = "llm_generation",
) -> Iterator[str]:
    event_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
    task_id = create_llm_task(user_id=user_id, project_id=project_id, operation=operation)
    event_queue.put(
        {
            "type": "task",
            "taskId": task_id,
            "status": "queued",
            "operation": operation,
        }
    )

    def report(
        *,
        stage: str,
        message: str,
        progress: int | None = None,
        detail: str = "",
    ) -> None:
        update_task_progress(
            task_id,
            stage=stage,
            message=message,
            progress=progress,
            detail=detail,
        )
        payload: dict[str, Any] = {
            "type": "progress",
            "taskId": task_id,
            "stage": stage,
            "message": message,
        }
        if progress is not None:
            payload["progress"] = progress
        if detail:
            payload["detail"] = detail
        event_queue.put(payload)

    def worker() -> None:
        try:
            if is_shutting_down():
                raise RuntimeError("服务正在关闭。")
            mark_task_running(task_id)
            with Session(db.engine) as session:
                result = task(session, report)
            data, llm_meta = serialize_complete(result)
            meta = merge_response_meta(llm_meta)
            mark_task_completed(task_id, data=data, meta=meta)
            event_queue.put(
                {
                    "type": "complete",
                    "taskId": task_id,
                    "progress": 100,
                    "stage": "complete",
                    "message": "生成完成",
                    "data": data,
                    "meta": meta,
                }
            )
        except LlmTaskCancelled:
            mark_task_cancelled(task_id)
            event_queue.put(
                {
                    "type": "error",
                    "taskId": task_id,
                    "status": "cancelled",
                    "message": "任务已取消。",
                }
            )
        except Exception as exc:  # noqa: BLE001 - task failures must be persisted
            mark_task_failed(task_id, str(exc))
            event_queue.put(
                {
                    "type": "error",
                    "taskId": task_id,
                    "status": "failed",
                    "message": str(exc),
                }
            )
        finally:
            event_queue.put(None)

    threading.Thread(target=worker, daemon=True).start()

    while not is_shutting_down():
        try:
            item = event_queue.get(timeout=QUEUE_POLL_SEC)
        except queue.Empty:
            continue
        if item is None:
            break
        yield format_sse(item)

    if is_shutting_down():
        yield format_sse(
            {
                "type": "error",
                "taskId": task_id,
                "message": "服务正在关闭，任务已中断。",
            }
        )
