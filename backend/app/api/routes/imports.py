from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import require_project_editor
from app.db import get_session
from app.models.schemas import ApiResponse, ExportCsvImportRequest, ExportJsonImportRequest
from app.services.repository import repository

router = APIRouter(
    prefix="/projects/{project_id}/import",
    tags=["import"],
    dependencies=[Depends(require_project_editor)],
)


@router.post("/export-json", response_model=ApiResponse)
def import_export_json(
    project_id: str,
    payload: ExportJsonImportRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    result = repository.import_export_json(session, project_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if result.errors and result.updateCount == 0 and not result.applied:
        raise HTTPException(status_code=400, detail=result.errors[0])
    return ApiResponse(data=result)


@router.post("/export-csv", response_model=ApiResponse)
def import_export_csv(
    project_id: str,
    payload: ExportCsvImportRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    result = repository.import_export_csv(session, project_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if result.errors and result.updateCount == 0 and not result.applied:
        raise HTTPException(status_code=400, detail=result.errors[0])
    return ApiResponse(data=result)
