from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.db import get_session
from app.models.schemas import (
    ApiResponse,
    ProjectCreateRequest,
    ProjectUpdateRequest,
)
from app.services.repository import repository

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ApiResponse)
def list_projects(session: Session = Depends(get_session)) -> ApiResponse:
    return ApiResponse(data=repository.list_projects(session))


@router.post("", response_model=ApiResponse)
def create_project(
    payload: ProjectCreateRequest, session: Session = Depends(get_session)
) -> ApiResponse:
    project = repository.create_project(session, payload)
    return ApiResponse(data=project)


@router.get("/{project_id}", response_model=ApiResponse)
def get_project(project_id: str, session: Session = Depends(get_session)) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=project)


@router.put("/{project_id}", response_model=ApiResponse)
def update_project(
    project_id: str, payload: ProjectUpdateRequest, session: Session = Depends(get_session)
) -> ApiResponse:
    project = repository.update_project(session, project_id, payload)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, session: Session = Depends(get_session)) -> Response:
    deleted = repository.delete_project(session, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/workspace", response_model=ApiResponse)
def get_workspace(project_id: str, session: Session = Depends(get_session)) -> ApiResponse:
    workspace = repository.get_workspace(session, project_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=workspace)
