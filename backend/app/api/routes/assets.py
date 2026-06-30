from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session

from app.api.deps import require_project_editor
from app.api.sse_stream import run_streaming_task
from app import db
from app.db import get_session
from app.models.schemas import (
    ApiResponse,
    AssetCreateRequest,
    AssetUpdateRequest,
    AuthUserRead,
    LlmVisionCapabilityRead,
    MediaLibraryNodeRead,
    MediaLibraryScanRead,
)
from app.services.llm.audit_log import record_llm_call_from_meta
from app.services.llm.config_store import resolve_active_config
from app.services.llm.model_capabilities import model_supports_vision
from app.services.media_preview import MediaPreviewError, ensure_poster_image, resolve_preview_file
from app.services.media_scanner import (
    MediaScanError,
    detect_media_kind,
    guess_preview_mime,
    node_to_dict,
    normalize_relative_path,
    resolve_safe_media_path,
    scan_media_library,
)
from app.services.project_access import get_project_media_root, get_project_media_scan_context
from app.services.repository import repository
from app.services.vision_analysis import vision_analysis_service

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


@router.get("/vision-capability", response_model=ApiResponse)
def get_asset_vision_capability(
    project_id: str,
    session: Session = Depends(get_session),
    model: str | None = None,
) -> ApiResponse:
    project = repository.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    config = resolve_active_config(session)
    target_model = model or config.model
    supports, source, message = model_supports_vision(
        session,
        config,
        model_id=target_model,
        prefer_live=True,
    )
    hint = ""
    if not supports:
        hint = (
            f"当前生效模型 {target_model} 不支持图像分析。"
            "请联系导演在 LLM 设置中切换到 gpt-4o、gemini-2.0-flash 或 kimi-k2.5/k2.6。"
        )
    return ApiResponse(
        data=LlmVisionCapabilityRead(
            providerId=config.provider_id,
            providerName=config.provider_name,
            model=target_model,
            supportsVision=supports,
            visionSource=source,
            message=hint or message,
            configured=bool(config.api_key.strip()),
        )
    )


@router.get("/media-library/health", response_model=ApiResponse)
def media_library_health(project_id: str) -> ApiResponse:
    media_root = get_project_media_root(project_id)
    if not media_root.strip():
        return ApiResponse(
            data={
                "ok": False,
                "mediaRoot": "",
                "message": "项目未配置素材根目录，请在项目设置中填写 mediaRoot。",
            }
        )

    try:
        root = resolve_safe_media_path(media_root)
    except MediaScanError as exc:
        return ApiResponse(
            data={
                "ok": False,
                "mediaRoot": media_root,
                "message": str(exc),
            }
        )

    return ApiResponse(
        data={
            "ok": True,
            "mediaRoot": str(root),
            "message": "",
        }
    )


@router.get("/media-library/scan", response_model=ApiResponse)
def scan_project_media_library(project_id: str) -> ApiResponse:
    media_root, existing_paths = get_project_media_scan_context(project_id)

    try:
        tree, stats = scan_media_library(
            media_root,
            existing_relative_paths=existing_paths,
        )
    except MediaScanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ApiResponse(
        data=MediaLibraryScanRead(
            mediaRoot=str(stats["mediaRoot"]),
            fileCount=int(stats["fileCount"]),
            directoryCount=int(stats["directoryCount"]),
            truncated=bool(stats["truncated"]),
            tree=MediaLibraryNodeRead.model_validate(node_to_dict(tree)),
        )
    )


@router.get("/media-library/preview")
def preview_project_media_file(
    project_id: str,
    relativePath: str = Query(..., min_length=1),
    quality: str = Query(default="fast", pattern="^(fast|original)$"),
) -> FileResponse:
    media_root = get_project_media_root(project_id)

    try:
        file_path = resolve_safe_media_path(media_root, relativePath)
    except MediaScanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")

    rel = normalize_relative_path(relativePath)
    media_kind = detect_media_kind(file_path.suffix)
    if media_kind is None:
        raise HTTPException(status_code=400, detail="不支持的媒体文件类型。")

    serve_path = file_path
    cache_control = "private, max-age=3600"
    if media_kind == "video" and quality == "fast":
        try:
            preview = resolve_preview_file(project_id, file_path, quality="fast")
            serve_path = preview.path
            cache_control = "private, max-age=86400"
        except MediaPreviewError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return FileResponse(
        path=serve_path,
        media_type=guess_preview_mime(rel, media_kind),
        filename=serve_path.name,
        headers={"Cache-Control": cache_control},
    )


@router.get("/media-library/poster")
def poster_project_media_file(
    project_id: str,
    relativePath: str = Query(..., min_length=1),
) -> FileResponse:
    media_root = get_project_media_root(project_id)

    try:
        file_path = resolve_safe_media_path(media_root, relativePath)
    except MediaScanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")

    media_kind = detect_media_kind(file_path.suffix)
    if media_kind != "video":
        raise HTTPException(status_code=400, detail="仅视频文件支持封面预览。")

    try:
        poster = ensure_poster_image(project_id, file_path)
    except MediaPreviewError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return FileResponse(
        path=poster.path,
        media_type="image/jpeg",
        filename=poster.path.name,
        headers={"Cache-Control": "private, max-age=86400"},
    )


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


@router.post("/{asset_id}/vision-analyze/stream")
def analyze_asset_vision_stream(
    project_id: str,
    asset_id: str,
    current_user: AuthUserRead = Depends(require_project_editor),
) -> StreamingResponse:
    endpoint = f"/projects/{project_id}/assets/{asset_id}/vision-analyze/stream"

    def serialize_complete(result: object) -> tuple[dict, dict[str, str] | None]:
        if result is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        prefill, llm_meta = result  # type: ignore[misc]
        with Session(db.engine) as audit_session:
            record_llm_call_from_meta(
                audit_session,
                user_id=current_user.id,
                endpoint=endpoint,
                llm_meta=llm_meta,
            )
        return prefill.model_dump(), llm_meta

    def task(session: Session, report) -> object:
        return vision_analysis_service.analyze_asset(
            session,
            project_id,
            asset_id,
            on_progress=report,
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
