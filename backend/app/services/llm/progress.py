from __future__ import annotations

from collections.abc import Callable
from typing import Any

ProgressReporter = Callable[..., None]


def emit_progress(
    reporter: ProgressReporter | None,
    stage: str,
    message: str,
    *,
    progress: int | None = None,
    detail: str = "",
) -> None:
    if reporter is None:
        return
    reporter(
        stage=stage,
        message=message,
        progress=progress,
        detail=detail,
    )


def progress_event_payload(
    stage: str,
    message: str,
    *,
    progress: int | None = None,
    detail: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "progress",
        "stage": stage,
        "message": message,
    }
    if progress is not None:
        payload["progress"] = progress
    if detail:
        payload["detail"] = detail
    return payload
