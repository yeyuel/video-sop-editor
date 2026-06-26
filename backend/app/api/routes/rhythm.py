import os
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.meta import merge_response_meta
from app.api.sse_stream import run_streaming_task
from app.core.config import settings
from app.db import get_session
from app.models.schemas import ApiResponse, BgmSelectionRequest, RhythmPlanWriteRequest
from app.services.repository import repository

router = APIRouter(prefix="/projects/{project_id}", tags=["rhythm"])


@router.get("/rhythm-plan", response_model=ApiResponse)
def get_rhythm_plan(project_id: str, session: Session = Depends(get_session)) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=repository.get_rhythm_plan(session, project_id))


@router.post("/rhythm-plan:generate", response_model=ApiResponse)
def generate_rhythm_plan(
    project_id: str, session: Session = Depends(get_session)
) -> ApiResponse:
    """Legacy alias for BGM recommendation."""
    result = repository.recommend_bgm(session, project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    rhythm_plan, llm_meta = result
    return ApiResponse(data=rhythm_plan, meta=merge_response_meta(llm_meta))


@router.post("/rhythm-plan/bgm-recommend", response_model=ApiResponse)
def recommend_bgm(project_id: str, session: Session = Depends(get_session)) -> ApiResponse:
    result = repository.recommend_bgm(session, project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    rhythm_plan, llm_meta = result
    return ApiResponse(data=rhythm_plan, meta=merge_response_meta(llm_meta))


@router.post("/rhythm-plan/bgm-recommend/stream")
def recommend_bgm_stream(project_id: str) -> StreamingResponse:
    def serialize_complete(result: object) -> tuple[object, dict[str, str] | None]:
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        rhythm_plan, llm_meta = result  # type: ignore[misc]
        return rhythm_plan.model_dump(), llm_meta

    def task(session: Session, report) -> object:
        return repository.recommend_bgm(session, project_id, on_progress=report)

    return StreamingResponse(
        run_streaming_task(task, serialize_complete=serialize_complete),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.put("/rhythm-plan/bgm-selection", response_model=ApiResponse)
def select_bgm_recommendation(
    project_id: str,
    payload: BgmSelectionRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        rhythm_plan = repository.select_bgm_recommendation(session, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if rhythm_plan is None:
        raise HTTPException(status_code=404, detail="Rhythm plan not found")
    return ApiResponse(data=rhythm_plan)


@router.post("/rhythm-plan/generate/stream")
def generate_rhythm_plan_stream(project_id: str) -> StreamingResponse:
    def serialize_complete(result: object) -> tuple[object, dict[str, str] | None]:
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        rhythm_plan, llm_meta = result  # type: ignore[misc]
        return rhythm_plan.model_dump(), llm_meta

    def task(session: Session, report) -> object:
        return repository.recommend_bgm(session, project_id, on_progress=report)

    return StreamingResponse(
        run_streaming_task(task, serialize_complete=serialize_complete),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.put("/rhythm-plan", response_model=ApiResponse)
def save_rhythm_plan(
    project_id: str,
    payload: RhythmPlanWriteRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    rhythm_plan = repository.upsert_rhythm_plan(session, project_id, payload)
    if rhythm_plan is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=rhythm_plan)


@router.post("/rhythm-plan/audio-upload", response_model=ApiResponse)
async def upload_audio_for_rhythm(
    project_id: str,
    audio: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> ApiResponse:
    if not audio.filename:
        raise HTTPException(status_code=400, detail="Audio file name is required")

    storage_dir = os.path.join(settings.storage_dir, "audio", project_id)
    os.makedirs(storage_dir, exist_ok=True)
    extension = os.path.splitext(audio.filename)[1].lower()
    stored_name = f"{uuid4().hex[:12]}{extension}"
    stored_path = os.path.join(storage_dir, stored_name)

    content = await audio.read()
    with open(stored_path, "wb") as output_file:
        output_file.write(content)

    try:
        result = repository.analyze_rhythm_audio(
            session,
            project_id,
            audio.filename,
            stored_path,
        )
    except ValueError as exc:
        if os.path.exists(stored_path):
            os.remove(stored_path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        if os.path.exists(stored_path):
            os.remove(stored_path)
        raise HTTPException(status_code=404, detail="Project not found")
    rhythm_plan, llm_meta = result
    return ApiResponse(data=rhythm_plan, meta=merge_response_meta(llm_meta))


@router.post("/rhythm-plan/audio-upload/stream")
async def upload_audio_for_rhythm_stream(
    project_id: str,
    audio: UploadFile = File(...),
) -> StreamingResponse:
    if not audio.filename:
        raise HTTPException(status_code=400, detail="Audio file name is required")

    storage_dir = os.path.join(settings.storage_dir, "audio", project_id)
    os.makedirs(storage_dir, exist_ok=True)
    extension = os.path.splitext(audio.filename)[1].lower()
    stored_name = f"{uuid4().hex[:12]}{extension}"
    stored_path = os.path.join(storage_dir, stored_name)

    content = await audio.read()
    with open(stored_path, "wb") as output_file:
        output_file.write(content)

    def serialize_complete(result: object) -> tuple[object, dict[str, str] | None]:
        if result is None:
            if os.path.exists(stored_path):
                os.remove(stored_path)
            raise HTTPException(status_code=404, detail="Project not found")
        rhythm_plan, llm_meta = result  # type: ignore[misc]
        return rhythm_plan.model_dump(), llm_meta

    def task(session: Session, report) -> object:
        return repository.analyze_rhythm_audio(
            session,
            project_id,
            audio.filename or stored_name,
            stored_path,
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


@router.delete("/rhythm-plan/audio", response_model=ApiResponse)
def delete_rhythm_audio(project_id: str, session: Session = Depends(get_session)) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rhythm_plan = repository.clear_rhythm_audio(session, project_id)
    if rhythm_plan is None:
        raise HTTPException(status_code=404, detail="Rhythm plan not found")
    return ApiResponse(data=rhythm_plan)
