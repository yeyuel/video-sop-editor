from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.models.schemas import ApiResponse, RhythmPlanWriteRequest
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
