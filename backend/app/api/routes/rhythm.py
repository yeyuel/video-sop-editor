import os
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from app.core.config import settings
from app.db import get_session
from app.models.schemas import ApiResponse, RhythmPlanWriteRequest
from app.services.audio_analysis import AudioAnalysisError
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
    rhythm_plan = repository.generate_rhythm_plan(session, project_id)
    if rhythm_plan is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=rhythm_plan)


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
        rhythm_plan = repository.analyze_rhythm_audio(
            session,
            project_id,
            audio.filename,
            stored_path,
        )
    except AudioAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if rhythm_plan is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=rhythm_plan)
