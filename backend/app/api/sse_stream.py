from __future__ import annotations

import json
import queue
import threading
from collections.abc import Callable, Iterator
from typing import Any

from sqlmodel import Session

from app.api.meta import merge_response_meta
from app.db import engine


def format_sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def run_streaming_task(
    task: Callable[[Session, Callable[..., None]], Any],
    *,
    serialize_complete: Callable[[Any], tuple[Any, dict[str, str] | None]],
) -> Iterator[str]:
    event_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def report(
        *,
        stage: str,
        message: str,
        progress: int | None = None,
        detail: str = "",
    ) -> None:
        payload: dict[str, Any] = {
            "type": "progress",
            "stage": stage,
            "message": message,
        }
        if progress is not None:
            payload["progress"] = progress
        if detail:
            payload["detail"] = detail
        event_queue.put(payload)

    result_box: dict[str, Any] = {"value": None, "error": None}

    def worker() -> None:
        try:
            with Session(engine) as session:
                result_box["value"] = task(session, report)
        except Exception as exc:  # noqa: BLE001 - stream endpoint must surface errors
            result_box["error"] = exc
        finally:
            event_queue.put(None)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        item = event_queue.get()
        if item is None:
            break
        yield format_sse(item)

    thread.join(timeout=0.2)

    if result_box["error"] is not None:
        yield format_sse(
            {
                "type": "error",
                "message": str(result_box["error"]),
            }
        )
        return

    data, llm_meta = serialize_complete(result_box["value"])
    yield format_sse(
        {
            "type": "complete",
            "progress": 100,
            "stage": "complete",
            "message": "生成完成",
            "data": data,
            "meta": merge_response_meta(llm_meta),
        }
    )
