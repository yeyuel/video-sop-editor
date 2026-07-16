from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlmodel import Session, select

from app.models.entities import RoughCutVersionEntity
from app.models.schemas import StoryboardGenerateRequest, ThemeSelectRequest
from app.services.llm.config_store import resolve_active_config
from app.services.llm.progress import ProgressReporter, emit_progress
from app.services.repository import repository
from app.services.rhythm_readiness import rhythm_ready_for_storyboard


ROUGH_CUT_MODES = {"fill_missing", "regenerate_creative"}


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


def list_rough_cut_versions(session: Session, project_id: str) -> list[dict[str, str]]:
    entities = session.exec(
        select(RoughCutVersionEntity)
        .where(RoughCutVersionEntity.project_id == project_id)
        .order_by(RoughCutVersionEntity.created_at.desc())
    ).all()
    return [
        {
            "id": item.id,
            "label": item.label,
            "generationMode": item.generation_mode,
            "providerId": item.provider_id,
            "model": item.model,
            "createdAt": item.created_at,
        }
        for item in entities
    ]


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
