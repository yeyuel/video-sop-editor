from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.api.deps import require_project_editor
from app.db import get_session
from app.models.schemas import (
    ApiResponse,
    AssetCreateRequest,
    AssetUpdateRequest,
)
from app.services.repository import repository

router = APIRouter(
    prefix="/projects/{project_id}/assets",
    tags=["assets"],
    dependencies=[Depends(require_project_editor)],
)


@router.get("", response_model=ApiResponse)
def list_assets(project_id: str, session: Session = Depends(get_session)) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=repository.list_assets(session, project_id))


@router.post("", response_model=ApiResponse)
def create_asset(
    project_id: str,
    payload: AssetCreateRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    asset = repository.create_asset(session, project_id, payload)
    return ApiResponse(data=asset)


@router.get("/{asset_id}", response_model=ApiResponse)
def get_asset(
    project_id: str, asset_id: str, session: Session = Depends(get_session)
) -> ApiResponse:
    asset = repository.get_asset(session, project_id, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return ApiResponse(data=asset)


@router.put("/{asset_id}", response_model=ApiResponse)
def update_asset(
    project_id: str,
    asset_id: str,
    payload: AssetUpdateRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    asset = repository.update_asset(session, project_id, asset_id, payload)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return ApiResponse(data=asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    project_id: str, asset_id: str, session: Session = Depends(get_session)
) -> Response:
    deleted = repository.delete_asset(session, project_id, asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
