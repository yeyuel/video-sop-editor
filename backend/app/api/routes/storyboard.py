from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.deps import require_project_editor
from app.api.meta import merge_response_meta
from app.api.sse_stream import run_streaming_task
from app import db
from app.db import get_session
from app.models.schemas import (
    ApiResponse,
    AuthUserRead,
    StoryboardGenerateRequest,
    StoryboardInsertRequest,
    StoryboardPartialRegenerateRequest,
    StoryboardReorderRequest,
    StoryboardSaveRequest,
    StoryboardSegmentWrite,
    StoryboardVoiceoverFillRequest,
)
from app.services.llm.audit_log import record_llm_call_from_meta
from app.services.repository import repository
from app.services.rough_cut_pipeline import rerun_storyboard_range

router = APIRouter(
    prefix="/projects/{project_id}",
    tags=["storyboard"],
    dependencies=[Depends(require_project_editor)],
)


@router.get("/storyboard", response_model=ApiResponse)
def get_storyboard(project_id: str, session: Session = Depends(get_session)) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=repository.get_storyboard_bundle(session, project_id))


@router.post("/storyboard:generate", response_model=ApiResponse)
def generate_storyboard(
    project_id: str,
    request: StoryboardGenerateRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        bundle = repository.generate_storyboard(session, project_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if bundle is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=bundle)


@router.post("/storyboard:generate-llm", response_model=ApiResponse)
def generate_storyboard_with_llm(
    project_id: str,
    request: StoryboardGenerateRequest,
    session: Session = Depends(get_session),
    current_user: AuthUserRead = Depends(require_project_editor),
) -> ApiResponse:
    try:
        result = repository.generate_storyboard_with_llm(session, project_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    bundle, llm_meta = result
    record_llm_call_from_meta(
        session,
        user_id=current_user.id,
        endpoint=f"/projects/{project_id}/storyboard:generate-llm",
        llm_meta=llm_meta,
    )
    return ApiResponse(data=bundle, meta=merge_response_meta(llm_meta))


@router.post("/storyboard/generate-llm/stream")
def generate_storyboard_with_llm_stream(
    project_id: str,
    request: StoryboardGenerateRequest,
    current_user: AuthUserRead = Depends(require_project_editor),
) -> StreamingResponse:
    endpoint = f"/projects/{project_id}/storyboard/generate-llm/stream"

    def serialize_complete(result: object) -> tuple[dict, dict[str, str] | None]:
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        bundle, llm_meta = result  # type: ignore[misc]
        with Session(db.engine) as audit_session:
            record_llm_call_from_meta(
                audit_session,
                user_id=current_user.id,
                endpoint=endpoint,
                llm_meta=llm_meta,
            )
        return bundle.model_dump(), llm_meta

    def task(session: Session, report) -> object:
        return repository.generate_storyboard_with_llm(
            session,
            project_id,
            request,
            on_progress=report,
        )

    return StreamingResponse(
        run_streaming_task(
            task,
            serialize_complete=serialize_complete,
            user_id=current_user.id,
            project_id=project_id,
            operation="storyboard_generation",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/storyboard/rerun-partial/stream")
def rerun_storyboard_range_stream(
    project_id: str,
    request: StoryboardPartialRegenerateRequest,
    current_user: AuthUserRead = Depends(require_project_editor),
) -> StreamingResponse:
    endpoint = f"/projects/{project_id}/storyboard/rerun-partial/stream"

    def serialize_complete(result: object) -> tuple[dict, dict[str, str] | None]:
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        bundle, llm_meta = result  # type: ignore[misc]
        with Session(db.engine) as audit_session:
            record_llm_call_from_meta(
                audit_session,
                user_id=current_user.id,
                endpoint=endpoint,
                llm_meta=llm_meta,
            )
        return bundle.model_dump(), llm_meta

    def task(session: Session, report) -> object:
        return rerun_storyboard_range(
            session,
            project_id,
            request,
            on_progress=report,
        )

    return StreamingResponse(
        run_streaming_task(
            task,
            serialize_complete=serialize_complete,
            user_id=current_user.id,
            project_id=project_id,
            operation="storyboard_partial_rerun",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.put("/storyboard", response_model=ApiResponse)
def save_storyboard(
    project_id: str,
    payload: StoryboardSaveRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    bundle = repository.save_storyboard(session, project_id, payload)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=bundle)


@router.post("/storyboard/insert", response_model=ApiResponse)
def insert_storyboard_segment(
    project_id: str,
    payload: StoryboardInsertRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        bundle = repository.insert_storyboard_segment(session, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if bundle is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=bundle)


@router.put("/storyboard/reorder", response_model=ApiResponse)
def reorder_storyboard(
    project_id: str,
    payload: StoryboardReorderRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        bundle = repository.reorder_storyboard(session, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if bundle is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=bundle)


@router.post("/storyboard/voiceover:fill-from-subtitles", response_model=ApiResponse)
def fill_storyboard_voiceover_from_subtitles(
    project_id: str,
    payload: StoryboardVoiceoverFillRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    bundle = repository.fill_storyboard_voiceover_from_subtitles(session, project_id, payload)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=bundle)


@router.get("/storyboard/{segment_id}", response_model=ApiResponse)
def get_storyboard_segment(
    project_id: str, segment_id: str, session: Session = Depends(get_session)
) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    segment = repository.get_storyboard_segment(session, project_id, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Storyboard segment not found")
    return ApiResponse(data=segment)


@router.put("/storyboard/{segment_id}", response_model=ApiResponse)
def update_storyboard_segment(
    project_id: str,
    segment_id: str,
    payload: StoryboardSegmentWrite,
    session: Session = Depends(get_session),
) -> ApiResponse:
    segment = repository.update_storyboard_segment(session, project_id, segment_id, payload)
    if segment is None:
        raise HTTPException(status_code=404, detail="Storyboard segment not found")
    return ApiResponse(data=segment)


@router.delete("/storyboard/{segment_id}", response_model=ApiResponse)
def delete_storyboard_segment(
    project_id: str,
    segment_id: str,
    session: Session = Depends(get_session),
) -> ApiResponse:
    bundle = repository.delete_storyboard_segment(session, project_id, segment_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Storyboard segment not found")
    return ApiResponse(data=bundle)
