from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.models.schemas import (
    ApiResponse,
    StoryboardGenerateRequest,
    StoryboardInsertRequest,
    StoryboardReorderRequest,
    StoryboardSaveRequest,
    StoryboardSegmentWrite,
)
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


@router.post("/storyboard:generate-llm", response_model=ApiResponse)
def generate_storyboard_with_llm(
    project_id: str,
    request: StoryboardGenerateRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    bundle = repository.generate_storyboard_with_llm(session, project_id, request)
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


@router.post("/storyboard/insert", response_model=ApiResponse)
def insert_storyboard_segment(
    project_id: str,
    payload: StoryboardInsertRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        bundle = repository.insert_storyboard_segment(session, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if bundle is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=bundle)


@router.put("/storyboard/reorder", response_model=ApiResponse)
def reorder_storyboard(
    project_id: str,
    payload: StoryboardReorderRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        bundle = repository.reorder_storyboard(session, project_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if bundle is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=bundle)


@router.get("/storyboard/{segment_id}", response_model=ApiResponse)
def get_storyboard_segment(
    project_id: str, segment_id: str, session: Session = Depends(get_session)
) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    segment = repository.get_storyboard_segment(session, project_id, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Storyboard segment not found")
    return ApiResponse(data=segment)


@router.put("/storyboard/{segment_id}", response_model=ApiResponse)
def update_storyboard_segment(
    project_id: str,
    segment_id: str,
    payload: StoryboardSegmentWrite,
    session: Session = Depends(get_session),
) -> ApiResponse:
    segment = repository.update_storyboard_segment(session, project_id, segment_id, payload)
    if segment is None:
        raise HTTPException(status_code=404, detail="Storyboard segment not found")
    return ApiResponse(data=segment)


@router.delete("/storyboard/{segment_id}", response_model=ApiResponse)
def delete_storyboard_segment(
    project_id: str,
    segment_id: str,
    session: Session = Depends(get_session),
) -> ApiResponse:
    bundle = repository.delete_storyboard_segment(session, project_id, segment_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Storyboard segment not found")
    return ApiResponse(data=bundle)
