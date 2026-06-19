from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.models.schemas import ApiResponse, StoryboardGenerateRequest, StoryboardSaveRequest
from app.services.repository import repository

router = APIRouter(prefix="/projects/{project_id}", tags=["storyboard"])


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
    bundle = repository.generate_storyboard(session, project_id, request)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=bundle)


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
