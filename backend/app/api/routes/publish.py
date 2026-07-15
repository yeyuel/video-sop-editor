from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session

from app.api.deps import require_project_editor
from app.api.meta import merge_response_meta
from app.api.sse_stream import run_streaming_task
from app.db import get_session
from app.models.schemas import (
    ApiResponse,
    ExportPlanWriteRequest,
    VoiceoverGenerateRequest,
    VoiceoverPreviewRequest,
    VoiceoverProviderRead,
)
from app.services.capcut_draft_export import build_native_voiceover_preview
from app.services.repository import repository
from app.services.voiceover_provider import list_voiceover_providers

router = APIRouter(
    prefix="/projects/{project_id}",
    tags=["export-plan"],
    dependencies=[Depends(require_project_editor)],
)


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


@router.post("/export-plan/voiceover:prepare", response_model=ApiResponse)
def prepare_voiceover_generation(
    project_id: str,
    payload: VoiceoverGenerateRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    export_plan = repository.prepare_export_voiceover_generation(session, project_id, payload)
    if export_plan is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=export_plan)


@router.get("/export-plan/voiceover/providers", response_model=ApiResponse)
def get_voiceover_providers(project_id: str, session: Session = Depends(get_session)) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    providers = [
        VoiceoverProviderRead(
            id=provider.id,
            label=provider.label,
            description=provider.description,
            isEnabled=provider.is_enabled,
            isRealTts=provider.is_real_tts,
            outputFormat=provider.output_format,
            recommendedFor=provider.recommended_for,
        )
        for provider in list_voiceover_providers()
    ]
    return ApiResponse(data=providers)


@router.post("/export-plan/voiceover:preview", response_model=ApiResponse)
def preview_voiceover_density(
    project_id: str,
    payload: VoiceoverPreviewRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    workspace = repository.get_workspace(session, project_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Project not found")
    workspace.exportPlan.voiceoverDensity = payload.voiceoverDensity
    workspace.exportPlan.voiceoverSpeed = max(0.7, min(1.3, payload.voiceoverSpeed))
    if payload.voiceoverScript.strip():
        workspace.exportPlan.voiceoverScript = payload.voiceoverScript.strip()
    return ApiResponse(data=build_native_voiceover_preview(workspace))


@router.delete("/export-plan/voiceover/audio", response_model=ApiResponse)
def delete_voiceover_audio(
    project_id: str,
    session: Session = Depends(get_session),
) -> ApiResponse:
    export_plan = repository.clear_export_voiceover_audio(session, project_id)
    if export_plan is None:
        raise HTTPException(status_code=404, detail="Voiceover audio not found")
    return ApiResponse(data=export_plan)


@router.get("/export-plan/voiceover/audio")
def download_voiceover_audio(
    project_id: str,
    session: Session = Depends(get_session),
) -> FileResponse:
    audio_path = repository.get_export_voiceover_audio_path(session, project_id)
    if not audio_path:
        raise HTTPException(status_code=404, detail="Voiceover audio not found")
    return FileResponse(
        path=audio_path,
        media_type="audio/wav",
        filename=f"{project_id}-voiceover.wav",
        headers={"Cache-Control": "private, max-age=60"},
    )


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
