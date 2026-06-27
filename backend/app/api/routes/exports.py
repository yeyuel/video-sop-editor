from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import require_project_editor
from app.db import get_session
from app.models.schemas import ApiResponse
from app.services.repository import repository

router = APIRouter(
    prefix="/projects/{project_id}/exports",
    tags=["exports"],
    dependencies=[Depends(require_project_editor)],
)


@router.post("/{fmt}", response_model=ApiResponse)
def export_project(
    project_id: str, fmt: str, session: Session = Depends(get_session)
) -> ApiResponse:
    normalized = fmt.lower()
    if normalized not in {"markdown", "json", "yaml", "csv"}:
        raise HTTPException(status_code=400, detail="Unsupported export format")

    document = repository.build_export_document(session, project_id, normalized)
    if document is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=document)
