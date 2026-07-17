from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.deps import require_project_editor
from app.api.sse_stream import run_streaming_task
from app.db import get_session
from app.models.schemas import ApiResponse, AuthUserRead, RoughCutGenerateRequest
from app.services.repository import repository
from app.services.rough_cut_pipeline import (
    generate_rough_cut_plan,
    list_rough_cut_versions,
    rerun_rough_cut_step,
    restore_rough_cut_version,
)

router = APIRouter(
    prefix="/projects/{project_id}/rough-cut",
    tags=["rough-cut"],
    dependencies=[Depends(require_project_editor)],
)


@router.post("/generate/stream")
def generate_rough_cut_stream(
    project_id: str,
    payload: RoughCutGenerateRequest | None = None,
    current_user: AuthUserRead = Depends(require_project_editor),
) -> StreamingResponse:
    def task(session: Session, report):
        return generate_rough_cut_plan(
            session,
            project_id,
            mode=payload.mode if payload else "fill_missing",
            on_progress=report,
        )

    def serialize_complete(result: object):
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        data, meta = result  # type: ignore[misc]
        return data, meta

    return StreamingResponse(
        run_streaming_task(
            task,
            serialize_complete=serialize_complete,
            user_id=current_user.id,
            project_id=project_id,
            operation="rough_cut_generation",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/versions", response_model=ApiResponse)
def list_versions(
    project_id: str,
    session: Session = Depends(get_session),
) -> ApiResponse:
    if not repository.get_project_entity(session, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=list_rough_cut_versions(session, project_id))


@router.post("/versions/{version_id}/restore", response_model=ApiResponse)
def restore_version(
    project_id: str,
    version_id: str,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        result = restore_rough_cut_version(session, project_id, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return ApiResponse(data=result)


@router.post("/rerun/{step}/stream")
def rerun_step_stream(
    project_id: str,
    step: str,
    current_user: AuthUserRead = Depends(require_project_editor),
) -> StreamingResponse:
    def task(session: Session, report):
        return rerun_rough_cut_step(
            session,
            project_id,
            step,
            on_progress=report,
        )

    def serialize_complete(result: object):
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        data, meta = result  # type: ignore[misc]
        return data, meta

    return StreamingResponse(
        run_streaming_task(
            task,
            serialize_complete=serialize_complete,
            user_id=current_user.id,
            project_id=project_id,
            operation=f"rough_cut_rerun_{step}",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
