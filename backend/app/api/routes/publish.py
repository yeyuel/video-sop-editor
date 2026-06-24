from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.meta import merge_response_meta
from app.api.sse_stream import run_streaming_task
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


@router.post("/export-plan:suggest", response_model=ApiResponse)
def suggest_export_plan(project_id: str, session: Session = Depends(get_session)) -> ApiResponse:
    result = repository.suggest_export_plan_with_llm(session, project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    export_plan, llm_meta = result
    return ApiResponse(data=export_plan, meta=merge_response_meta(llm_meta))


@router.post("/export-plan/suggest/stream")
def suggest_export_plan_stream(project_id: str) -> StreamingResponse:
    def serialize_complete(result: object) -> tuple[object, dict[str, str] | None]:
        if result is None:
            raise HTTPException(status_code=404, detail="Project not found")
        export_plan, llm_meta = result  # type: ignore[misc]
        return export_plan.model_dump(), llm_meta

    def task(session: Session, report) -> object:
        return repository.suggest_export_plan_with_llm(
            session, project_id, on_progress=report
        )

    return StreamingResponse(
        run_streaming_task(task, serialize_complete=serialize_complete),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
