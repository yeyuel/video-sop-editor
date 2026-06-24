from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.meta import merge_response_meta
from app.api.sse_stream import run_streaming_task
from app.db import get_session
from app.models.schemas import ApiResponse, ThemeGenerateRequest, ThemeSelectRequest
from app.services.repository import repository

router = APIRouter(prefix="/projects/{project_id}/themes", tags=["themes"])


@router.get("", response_model=ApiResponse)
def list_themes(project_id: str, session: Session = Depends(get_session)) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=repository.list_themes(session, project_id))


@router.post("/generate", response_model=ApiResponse)
def generate_themes(
    project_id: str,
    payload: ThemeGenerateRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    themes = repository.generate_themes(session, project_id, payload.count)
    if themes is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=themes)


@router.post("/generate-llm", response_model=ApiResponse)
@router.post("/generate:llm", response_model=ApiResponse)
def generate_themes_with_llm(
    project_id: str,
    payload: ThemeGenerateRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    result = repository.generate_themes_with_llm(session, project_id, payload.count)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    themes, llm_meta = result
    return ApiResponse(data=themes, meta=merge_response_meta(llm_meta))


@router.post("/generate-llm/stream")
def generate_themes_with_llm_stream(
    project_id: str,
    payload: ThemeGenerateRequest,
) -> StreamingResponse:
    def serialize_complete(result: object) -> tuple[list[dict], dict[str, str] | None]:
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        themes, llm_meta = result  # type: ignore[misc]
        return [theme.model_dump() for theme in themes], llm_meta

    def task(session: Session, report) -> object:
        return repository.generate_themes_with_llm(
            session,
            project_id,
            payload.count,
            on_progress=report,
        )

    return StreamingResponse(
        run_streaming_task(task, serialize_complete=serialize_complete),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.put("/select", response_model=ApiResponse)
def select_theme(
    project_id: str,
    payload: ThemeSelectRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    themes = repository.select_theme(session, project_id, payload)
    if themes is None:
        raise HTTPException(status_code=404, detail="Theme or project not found")
    return ApiResponse(data=themes)
