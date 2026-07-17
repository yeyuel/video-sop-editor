from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete
from sqlmodel import Session, select

from app.models.entities import RoughCutVersionEntity, ThemeEntity
from app.models.schemas import (
    ExportPlanWriteRequest,
    StoryboardGenerateRequest,
    StoryboardPartialRegenerateRequest,
    StoryboardSegmentWrite,
    ThemeSelectRequest,
    WorkspaceDataRead,
)
from app.services.serialization import dumps_list
from app.services.llm.config_store import resolve_active_config
from app.services.llm.progress import ProgressReporter, emit_progress
from app.services.repository import repository
from app.services.rhythm_readiness import rhythm_ready_for_storyboard


ROUGH_CUT_MODES = {"fill_missing", "regenerate_creative"}
ROUGH_CUT_RERUN_STEPS = {"theme", "storyboard", "export"}


def _phase_reporter(
    report: ProgressReporter | None,
    *,
    phase: str,
    start: int,
    end: int,
) -> ProgressReporter | None:
    if report is None:
        return None

    def scoped_report(
        *,
        stage: str,
        message: str,
        progress: int | None = None,
        detail: str = "",
    ) -> None:
        ratio = max(0, min(progress or 0, 100)) / 100
        mapped = int(round(start + (end - start) * ratio))
        report(
            stage=phase,
            message=message,
            progress=mapped,
            detail=detail or f"当前子阶段：{stage}",
        )

    return scoped_report


def _workspace_has_creative_content(workspace: Any) -> bool:
    return bool(
        workspace
        and (
            workspace.themes
            or workspace.storyboard
            or workspace.exportPlan.title.strip()
        )
    )


def _save_version(
    session: Session,
    project_id: str,
    *,
    label: str,
    generation_mode: str,
    provider_id: str = "",
    model: str = "",
) -> RoughCutVersionEntity | None:
    workspace = repository.get_workspace(session, project_id)
    if not workspace:
        return None
    entity = RoughCutVersionEntity(
        id=f"rough_ver_{uuid4().hex[:12]}",
        project_id=project_id,
        label=label,
        generation_mode=generation_mode,
        provider_id=provider_id,
        model=model,
        snapshot_json=json.dumps(
            workspace.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


def _load_version_workspace(entity: RoughCutVersionEntity) -> WorkspaceDataRead:
    try:
        return WorkspaceDataRead.model_validate(json.loads(entity.snapshot_json))
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise ValueError("历史版本数据无法读取。") from exc


def _selected_theme_title(workspace: WorkspaceDataRead) -> str:
    selected = next((theme for theme in workspace.themes if theme.isSelected), None)
    return selected.title if selected else (workspace.themes[0].title if workspace.themes else "")


def _version_summary(workspace: WorkspaceDataRead) -> dict[str, Any]:
    duration = max((segment.endTime for segment in workspace.storyboard), default=0.0)
    return {
        "themeTitle": _selected_theme_title(workspace),
        "storyboardCount": len(workspace.storyboard),
        "durationSec": round(duration, 2),
        "exportTitle": workspace.exportPlan.title,
    }


def _version_diff(
    current: WorkspaceDataRead,
    historical: WorkspaceDataRead,
) -> dict[str, Any]:
    current_assets = [segment.assetId for segment in current.storyboard]
    historical_assets = [segment.assetId for segment in historical.storyboard]
    sequence_changes = sum(
        current_id != historical_id
        for current_id, historical_id in zip(current_assets, historical_assets)
    ) + abs(len(current_assets) - len(historical_assets))
    current_summary = _version_summary(current)
    historical_summary = _version_summary(historical)
    return {
        "themeChanged": current_summary["themeTitle"] != historical_summary["themeTitle"],
        "storyboardCountDelta": (
            historical_summary["storyboardCount"] - current_summary["storyboardCount"]
        ),
        "durationDeltaSec": round(
            historical_summary["durationSec"] - current_summary["durationSec"], 2
        ),
        "sequenceChangeCount": sequence_changes,
        "exportTitleChanged": current_summary["exportTitle"] != historical_summary["exportTitle"],
    }


def list_rough_cut_versions(session: Session, project_id: str) -> list[dict[str, Any]]:
    entities = session.exec(
        select(RoughCutVersionEntity)
        .where(RoughCutVersionEntity.project_id == project_id)
        .order_by(RoughCutVersionEntity.created_at.desc())
    ).all()
    current = repository.get_workspace(session, project_id)
    versions: list[dict[str, Any]] = []
    for item in entities:
        historical = _load_version_workspace(item)
        versions.append({
            "id": item.id,
            "label": item.label,
            "generationMode": item.generation_mode,
            "providerId": item.provider_id,
            "model": item.model,
            "createdAt": item.created_at,
            "summary": _version_summary(historical),
            "diff": _version_diff(current, historical) if current else {},
        })
    return versions


def restore_rough_cut_version(
    session: Session,
    project_id: str,
    version_id: str,
) -> dict[str, Any] | None:
    project = repository.get_project_entity(session, project_id)
    version = session.get(RoughCutVersionEntity, version_id)
    if not project or not version or version.project_id != project_id:
        return None

    historical = _load_version_workspace(version)
    available_asset_ids = {asset.assetId for asset in repository.list_assets(session, project_id)}
    referenced_asset_ids = {segment.assetId for segment in historical.storyboard}
    missing_asset_ids = sorted(referenced_asset_ids - available_asset_ids)
    if missing_asset_ids:
        preview = "、".join(missing_asset_ids[:5])
        suffix = " 等" if len(missing_asset_ids) > 5 else ""
        raise ValueError(f"历史版本引用的素材已被删除：{preview}{suffix}。请补回素材后再恢复。")

    backup = _save_version(
        session,
        project_id,
        label="恢复前备份",
        generation_mode="pre_restore",
    )

    session.exec(delete(ThemeEntity).where(ThemeEntity.project_id == project_id))
    selected_theme_id = ""
    for theme in historical.themes:
        session.add(
            ThemeEntity(
                id=theme.id,
                project_id=project_id,
                title=theme.title,
                summary=theme.summary,
                core_emotion=theme.coreEmotion,
                rhythm_profile=theme.rhythmProfile,
                platform_reason=theme.platformReason,
                used_locations=dumps_list(theme.usedLocations),
                used_asset_ids=dumps_list(theme.usedAssetIds),
            )
        )
        if theme.isSelected:
            selected_theme_id = theme.id
    if not selected_theme_id and historical.themes:
        selected_theme_id = historical.themes[0].id
    project.selected_theme_id = selected_theme_id
    session.add(project)
    session.commit()

    segments = [
        StoryboardSegmentWrite.model_validate(segment.model_dump())
        for segment in historical.storyboard
    ]
    repository._replace_storyboard_segments(
        session,
        project_id,
        selected_theme_id,
        segments,
    )
    export_payload = ExportPlanWriteRequest.model_validate(
        historical.exportPlan.model_dump()
    )
    repository.upsert_export_plan(session, project_id, export_payload)
    repository.clear_export_voiceover_audio(session, project_id)

    restored = _save_version(
        session,
        project_id,
        label=f"已恢复：{version.label}",
        generation_mode="restore",
        provider_id=version.provider_id,
        model=version.model,
    )
    return {
        "restoredVersionId": version.id,
        "backupVersionId": backup.id if backup else "",
        "currentVersionId": restored.id if restored else "",
        "message": "历史方案已恢复。真实音频和节拍校准保持不变，旧口播音频已清除。",
    }


def rerun_rough_cut_step(
    session: Session,
    project_id: str,
    step: str,
    *,
    on_progress: ProgressReporter | None = None,
) -> tuple[dict[str, Any], dict[str, str]] | None:
    if step not in ROUGH_CUT_RERUN_STEPS:
        raise ValueError("不支持的重跑阶段。")
    project = repository.get_project_entity(session, project_id)
    if not project:
        return None
    if not repository.list_assets(session, project_id):
        raise ValueError("请先录入素材，再重跑生成阶段。")

    active_config = resolve_active_config(session)
    baseline = _save_version(
        session,
        project_id,
        label=f"重跑{step}前备份",
        generation_mode=f"pre_rerun_{step}",
    )
    meta: dict[str, str] = {
        "generationMode": "rerun_step",
        "rerunStep": step,
        "providerId": active_config.provider_id,
        "model": active_config.model,
    }

    if step == "theme":
        emit_progress(on_progress, "themes", "正在重新生成主题候选。", progress=8)
        result = repository.generate_themes_with_llm(
            session,
            project_id,
            3,
            on_progress=_phase_reporter(on_progress, phase="themes", start=8, end=88),
        )
        if result is None:
            return None
        themes, step_meta = result
        if not themes:
            raise ValueError("当前素材不足以生成主题。")
        repository.select_theme(
            session,
            project_id,
            ThemeSelectRequest(themeId=themes[0].id),
        )
        next_path = f"/projects/{project_id}/themes"
        message = "主题已重新生成并选择首个候选。现有分镜未覆盖，可按需继续重跑分镜。"
    elif step == "storyboard":
        rhythm = repository.get_rhythm_plan(session, project_id)
        if not rhythm_ready_for_storyboard(rhythm):
            raise ValueError("真实音频节拍尚未就绪，请先在节奏页完成音乐上传和节拍识别。")
        selected_theme = repository.get_selected_theme(session, project_id)
        emit_progress(on_progress, "storyboard", "正在重新生成完整分镜。", progress=8)
        result = repository.generate_storyboard_with_llm(
            session,
            project_id,
            StoryboardGenerateRequest(
                themeId=selected_theme.id if selected_theme else None,
                targetDurationSec=project.target_duration_sec,
                beatMode=rhythm.beatMode,
                alignToBeat=True,
                selectedTrackName=rhythm.selectedTrackName,
            ),
            on_progress=_phase_reporter(
                on_progress, phase="storyboard", start=8, end=88
            ),
        )
        if result is None:
            return None
        _, step_meta = result
        next_path = f"/projects/{project_id}/storyboard"
        message = "完整分镜已重新生成。导出文案未覆盖，可检查分镜后再重跑导出建议。"
    else:
        emit_progress(on_progress, "export", "正在重新生成导出文案。", progress=8)
        result = repository.suggest_export_plan_with_llm(
            session,
            project_id,
            on_progress=_phase_reporter(on_progress, phase="export", start=8, end=88),
        )
        if result is None:
            return None
        _, step_meta = result
        next_path = f"/projects/{project_id}/export"
        message = "标题、标签、字幕和导出文案已重新生成，主题与分镜保持不变。"

    meta.update(step_meta)
    generated = _save_version(
        session,
        project_id,
        label=f"重跑{step}：{active_config.provider_name} / {active_config.model}",
        generation_mode=f"rerun_{step}",
        provider_id=active_config.provider_id,
        model=active_config.model,
    )
    emit_progress(on_progress, "complete", "单步骤重跑完成。", progress=99)
    return (
        {
            "status": "completed",
            "generationMode": "rerun_step",
            "rerunStep": step,
            "completedSteps": [step],
            "nextStep": step,
            "nextPath": next_path,
            "message": message,
            "baselineVersionId": baseline.id if baseline else "",
            "generatedVersionId": generated.id if generated else "",
            "providerId": active_config.provider_id,
            "model": active_config.model,
        },
        meta,
    )


def rerun_storyboard_range(
    session: Session,
    project_id: str,
    request: StoryboardPartialRegenerateRequest,
    *,
    on_progress: ProgressReporter | None = None,
) -> tuple[Any, dict[str, str]] | None:
    """Rerun one contiguous storyboard range and preserve a reversible version pair."""
    current = repository.list_storyboard(session, project_id)
    index_by_id = {segment.id: index for index, segment in enumerate(current)}
    if len(set(request.segmentIds)) != len(request.segmentIds):
        raise ValueError("选中的分镜不能重复。")
    if any(segment_id not in index_by_id for segment_id in request.segmentIds):
        raise ValueError("选中的分镜已不存在，请刷新页面后重试。")
    selected_indexes = sorted(index_by_id[segment_id] for segment_id in request.segmentIds)
    if selected_indexes != list(range(selected_indexes[0], selected_indexes[-1] + 1)):
        raise ValueError("局部重跑只支持连续分镜区间。")

    active_config = resolve_active_config(session)
    baseline = _save_version(
        session,
        project_id,
        label="局部分镜重跑前备份",
        generation_mode="pre_rerun_storyboard_range",
    )
    result = repository.regenerate_storyboard_range_with_llm(
        session,
        project_id,
        request,
        on_progress=on_progress,
    )
    if result is None:
        return None
    bundle, meta = result
    generated = _save_version(
        session,
        project_id,
        label=f"局部分镜重跑：{active_config.provider_name} / {active_config.model}",
        generation_mode="rerun_storyboard_range",
        provider_id=active_config.provider_id,
        model=active_config.model,
    )
    meta.update(
        {
            "baselineVersionId": baseline.id if baseline else "",
            "generatedVersionId": generated.id if generated else "",
            "providerId": active_config.provider_id,
            "model": active_config.model,
        }
    )
    emit_progress(on_progress, "complete", "局部分镜已经更新。", progress=99)
    return bundle, meta


def generate_rough_cut_plan(
    session: Session,
    project_id: str,
    *,
    mode: str = "fill_missing",
    on_progress: ProgressReporter | None = None,
) -> tuple[dict[str, Any], dict[str, str]] | None:
    if mode not in ROUGH_CUT_MODES:
        raise ValueError("不支持的一键生成模式。")

    project = repository.get_project_entity(session, project_id)
    if not project:
        return None
    assets = repository.list_assets(session, project_id)
    if not assets:
        raise ValueError("请先录入至少一条素材，再使用一键生成。")

    regenerate = mode == "regenerate_creative"
    active_config = resolve_active_config(session)
    completed_steps: list[str] = []
    meta: dict[str, str] = {
        "pipelineStatus": "running",
        "generationMode": mode,
        "providerId": active_config.provider_id,
        "model": active_config.model,
    }
    baseline_version: RoughCutVersionEntity | None = None
    if regenerate:
        current_workspace = repository.get_workspace(session, project_id)
        if _workspace_has_creative_content(current_workspace):
            baseline_version = _save_version(
                session,
                project_id,
                label="重新生成前备份",
                generation_mode="baseline",
            )

    emit_progress(on_progress, "themes", "正在确认叙事主题。", progress=5)
    selected_theme = repository.get_selected_theme(session, project_id)
    if regenerate or not selected_theme:
        themes = repository.list_themes(session, project_id)
        if regenerate or not themes:
            result = repository.generate_themes_with_llm(
                session,
                project_id,
                3,
                on_progress=_phase_reporter(
                    on_progress, phase="themes", start=5, end=25
                ),
            )
            if result is None:
                return None
            themes, theme_meta = result
            meta.update(
                {f"theme{key[0].upper()}{key[1:]}": value for key, value in theme_meta.items()}
            )
        if not themes:
            raise ValueError("当前素材不足以生成叙事主题。")
        repository.select_theme(
            session,
            project_id,
            ThemeSelectRequest(themeId=themes[0].id),
        )
        selected_theme = repository.get_selected_theme(session, project_id)
    completed_steps.append("theme")

    rhythm = repository.get_rhythm_plan(session, project_id)
    rhythm_is_ready = rhythm_ready_for_storyboard(rhythm)
    should_recommend_bgm = not rhythm or not rhythm.recommendedBgm
    if regenerate and not rhythm_is_ready:
        should_recommend_bgm = True

    if should_recommend_bgm:
        emit_progress(on_progress, "rhythm", "正在生成 BGM 推荐。", progress=28)
        rhythm_result = repository.recommend_bgm(
            session,
            project_id,
            on_progress=_phase_reporter(
                on_progress, phase="rhythm", start=28, end=48
            ),
        )
        if rhythm_result is None:
            return None
        rhythm, rhythm_meta = rhythm_result
        meta.update(
            {f"rhythm{key[0].upper()}{key[1:]}": value for key, value in rhythm_meta.items()}
        )
    elif regenerate and rhythm_is_ready:
        meta["preservedAudioRhythm"] = "true"
    completed_steps.append("rhythm_recommendation")

    if not rhythm_ready_for_storyboard(rhythm):
        emit_progress(
            on_progress,
            "waiting_audio",
            "BGM 推荐已准备，请选择歌曲并上传音频完成节拍识别。",
            progress=50,
        )
        meta["pipelineStatus"] = "waiting_audio"
        return (
            {
                "status": "waiting_audio",
                "generationMode": mode,
                "completedSteps": completed_steps,
                "nextStep": "rhythm",
                "nextPath": f"/projects/{project_id}/rhythm",
                "message": "主题和 BGM 推荐已完成。上传选定音乐并识别节拍后，可继续生成分镜与导出建议。",
                "baselineVersionId": baseline_version.id if baseline_version else "",
                "providerId": active_config.provider_id,
                "model": active_config.model,
            },
            meta,
        )

    completed_steps.append("rhythm_analysis")
    storyboard = repository.get_storyboard_bundle(session, project_id)
    if regenerate or not storyboard.segments:
        emit_progress(on_progress, "storyboard", "正在生成分镜时间线。", progress=55)
        storyboard_result = repository.generate_storyboard_with_llm(
            session,
            project_id,
            StoryboardGenerateRequest(
                themeId=selected_theme.id if selected_theme else None,
                targetDurationSec=project.target_duration_sec,
                beatMode=rhythm.beatMode,
                alignToBeat=True,
                selectedTrackName=rhythm.selectedTrackName,
            ),
            on_progress=_phase_reporter(
                on_progress, phase="storyboard", start=55, end=78
            ),
        )
        if storyboard_result is None:
            return None
        storyboard, storyboard_meta = storyboard_result
        meta.update(
            {f"storyboard{key[0].upper()}{key[1:]}": value for key, value in storyboard_meta.items()}
        )
    completed_steps.append("storyboard")

    export_plan = repository.get_export_plan(session, project_id)
    if regenerate or not export_plan or not export_plan.title.strip():
        emit_progress(on_progress, "export", "正在生成标题、标签和导出文案。", progress=80)
        export_result = repository.suggest_export_plan_with_llm(
            session,
            project_id,
            on_progress=_phase_reporter(
                on_progress, phase="export", start=80, end=96
            ),
        )
        if export_result is None:
            return None
        export_plan, export_meta = export_result
        meta.update(
            {f"export{key[0].upper()}{key[1:]}": value for key, value in export_meta.items()}
        )
    completed_steps.append("export")

    generated_version = _save_version(
        session,
        project_id,
        label=f"{active_config.provider_name} / {active_config.model}",
        generation_mode=mode,
        provider_id=active_config.provider_id,
        model=active_config.model,
    )
    emit_progress(on_progress, "complete", "初剪方案已准备完成。", progress=99)
    meta["pipelineStatus"] = "completed"
    return (
        {
            "status": "completed",
            "generationMode": mode,
            "completedSteps": completed_steps,
            "nextStep": "export",
            "nextPath": f"/projects/{project_id}/export",
            "message": (
                "已重新生成主题、分镜和导出文案，并保留本次版本。"
                if regenerate
                else "主题、真实节拍分镜和导出建议已经准备完成，可继续检查并写入剪映草稿。"
            ),
            "storyboardCount": len(storyboard.segments),
            "exportTitle": export_plan.title if export_plan else "",
            "baselineVersionId": baseline_version.id if baseline_version else "",
            "generatedVersionId": generated_version.id if generated_version else "",
            "providerId": active_config.provider_id,
            "model": active_config.model,
            "preservedAudioRhythm": regenerate and rhythm_is_ready,
        },
        meta,
    )
