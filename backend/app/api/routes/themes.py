from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

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
