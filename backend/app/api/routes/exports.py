from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import require_project_editor
from app.db import get_session
from app.models.schemas import ApiResponse, CapcutDraftDeployRequest
from app.services.repository import repository

router = APIRouter(
    prefix="/projects/{project_id}/exports",
    tags=["exports"],
    dependencies=[Depends(require_project_editor)],
)


@router.get("/capcut-defaults", response_model=ApiResponse)
def get_capcut_export_defaults(
    project_id: str, session: Session = Depends(get_session)
) -> ApiResponse:
    defaults = repository.get_capcut_export_defaults(session, project_id)
    if defaults is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=defaults)


@router.post("/capcut/deploy", response_model=ApiResponse)
def deploy_capcut_draft(
    project_id: str,
    payload: CapcutDraftDeployRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        result = repository.deploy_capcut_draft(session, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=result)


@router.post("/{fmt}", response_model=ApiResponse)
def export_project(
    project_id: str, fmt: str, session: Session = Depends(get_session)
) -> ApiResponse:
    normalized = fmt.lower()
    if normalized not in {"markdown", "json", "yaml", "csv", "capcut", "edl"}:
        raise HTTPException(status_code=400, detail="Unsupported export format")

    document = repository.build_export_document(session, project_id, normalized)
    if document is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=document)
