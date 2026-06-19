from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.models.schemas import ApiResponse, ExportPlanWriteRequest
from app.services.repository import repository

router = APIRouter(prefix="/projects/{project_id}", tags=["export-plan"])


@router.get("/export-plan", response_model=ApiResponse)
def get_export_plan(project_id: str, session: Session = Depends(get_session)) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=repository.get_export_plan(session, project_id))


@router.put("/export-plan", response_model=ApiResponse)
def save_export_plan(
    project_id: str,
    payload: ExportPlanWriteRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    export_plan = repository.upsert_export_plan(session, project_id, payload)
    if export_plan is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=export_plan)
