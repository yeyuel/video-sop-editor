import hashlib
import json
import os
import re
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlmodel import Session, delete, select

from app.models.entities import (
    AssetEntity,
    ProjectEntity,
    PublishPlanEntity,
    RhythmPlanEntity,
    StoryboardSegmentEntity,
    ThemeEntity,
    UserEntity,
)
from app.models.schemas import (
    AssetCreateRequest,
    AssetRead,
    AssetUpdateRequest,
    AuthUserCreateRequest,
    AuthLoginOptionRead,
    AuthUserRead,
    AuthUserUpdateRequest,
    BgmRecommendationRead,
    BgmSelectionRequest,
    CapcutDraftDeployRead,
    CapcutDraftDeployRequest,
    CapcutExportDefaultsRead,
    ExportDocumentRead,
    ExportCsvImportRequest,
    ExportJsonImportRequest,
    ExportImportResultRead,
    ExportPlanRead,
    ExportPlanWriteRequest,
    NarrativeThemeRead,
    ProjectCreateRequest,
    ProjectRead,
    ProjectUpdateRequest,
    RhythmPlanRead,
    RhythmPlanWriteRequest,
    StoryboardBundleRead,
    StoryboardGenerateRequest,
    StoryboardInsertRequest,
    StoryboardReorderRequest,
    StoryboardSaveRequest,
    StoryboardSegmentRead,
    StoryboardSegmentWrite,
    StoryboardVoiceoverFillRequest,
    ThemeSelectRequest,
    VoiceoverGenerateRequest,
    WorkspaceDataRead,
)
from app.core.config import settings
from app.services.audio_analysis import AudioAnalysisError, audio_beat_analyzer
from app.services.bgm_recommendation import (
    build_llm_bgm_recommendations,
    format_bgm_track_name,
)
from app.services.rhythm_readiness import rhythm_ready_for_storyboard, rhythm_requirement_message
from app.services.auth import hash_password, verify_password
from app.services.export_generation import (
    apply_export_captions_to_segments,
    build_llm_export_plan,
    build_rule_export_fallback,
    merge_storyboard_subtitle_updates,
    render_export_content,
)
from app.services.export_import import (
    apply_storyboard_import_plan,
    build_storyboard_import_plan,
    finalize_import_result,
    parse_export_csv_document,
    parse_export_json_document,
    segments_from_export_json,
)
from app.services.export_validation import build_export_validation
from app.services.rhythm_generation import (
    build_audio_rhythm_payload,
    build_photo_motion_suggestions,
    build_rule_dark_cuts,
    build_rule_fallback_rhythm_payload,
    build_rule_rhythm_payload,
    recommend_beat_mode,
)
from app.services.rhythm_profile import build_attention_beats, build_rhythm_profile
from app.services.beat_grid import (
    apply_beat_calibration,
    estimate_beat_calibration_from_reference,
    filter_beats_for_capcut_mode,
    normalize_beat_times,
    recommend_capcut_density_mode_from_reference,
)
from app.services.serialization import dumps_list, loads_float_list, loads_str_list
from app.services.storyboard_generation import (
    asset_order_key,
    build_llm_storyboard_plan,
    build_storyboard_validation,
    generate_storyboard_segments,
    generate_storyboard_segments_from_plan,
    normalize_storyboard_segments,
    parse_route_locations,
    resolve_storyboard_beat_points,
    segment_read_to_write,
)
from app.services.theme_generation import build_llm_theme_candidates, build_rule_theme_candidates
from app.services.voiceover_provider import (
    get_voiceover_provider,
    get_voiceover_voice,
    is_voiceover_provider_enabled,
)
from app.services.voiceover_synthesis import VoiceoverSynthesisError, synthesize_edge_voiceover
from app.services.llm.progress import ProgressReporter, emit_progress
from app.services.session_service import delete_user_sessions, revoke_user_sessions


class SqlRepository:
    def authenticate_user(
        self, session: Session, username: str, password: str
    ) -> AuthUserRead | None:
        user = session.exec(select(UserEntity).where(UserEntity.username == username)).first()
        if not user or not user.ui_enabled:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return self._map_user(user)

    def list_users(self, session: Session) -> list[AuthUserRead]:
        users = session.exec(select(UserEntity).order_by(UserEntity.username)).all()
        return [self._map_user(item) for item in users]

    def list_login_options(self, session: Session) -> list[AuthLoginOptionRead]:
        users = session.exec(
            select(UserEntity)
            .where(UserEntity.ui_enabled == True)  # noqa: E712
            .order_by(UserEntity.username)
        ).all()
        return [
            AuthLoginOptionRead(
                username=item.username,
                displayName=item.display_name,
                role=item.role,
            )
            for item in users
        ]

    def create_user(self, session: Session, payload: AuthUserCreateRequest) -> AuthUserRead:
        username = payload.username.strip()
        if not username:
            raise ValueError("用户名不能为空")
        if len(payload.password.strip()) < 6:
            raise ValueError("密码长度至少 6 位")

        existing = session.exec(select(UserEntity).where(UserEntity.username == username)).first()
        if existing:
            raise ValueError("用户名已存在")

        role = payload.role.strip() or "editor"
        if role not in {"director", "editor"}:
            raise ValueError("角色仅支持 director 或 editor")

        ui_enabled = payload.uiEnabled
        if role == "director" and not ui_enabled:
            ui_enabled = True

        user = UserEntity(
            id=f"user_{uuid4().hex[:8]}",
            username=username,
            display_name=payload.displayName.strip() or username,
            password_hash=hash_password(payload.password),
            role=role,
            ui_enabled=ui_enabled,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return self._map_user(user)

    def update_user(
        self,
        session: Session,
        user_id: str,
        payload: AuthUserUpdateRequest,
        *,
        actor_id: str,
    ) -> AuthUserRead:
        user = session.get(UserEntity, user_id)
        if not user:
            raise ValueError("用户不存在")

        if payload.displayName is not None:
            user.display_name = payload.displayName.strip() or user.username

        next_role = payload.role.strip() if payload.role is not None else user.role
        if next_role not in {"director", "editor"}:
            raise ValueError("角色仅支持 director 或 editor")

        next_ui_enabled = payload.uiEnabled if payload.uiEnabled is not None else user.ui_enabled
        if next_role == "director":
            next_ui_enabled = True

        if user.role == "director" and next_role != "director":
            if self._count_directors(session) <= 1:
                raise ValueError("至少保留一名导演账号")

        if user.id == actor_id:
            if not next_ui_enabled:
                raise ValueError("不能关闭当前登录账号的登录权限")
            if user.role == "director" and next_role != "director":
                raise ValueError("不能修改当前登录账号的角色")

        password_changed = bool(payload.password and payload.password.strip())
        if password_changed:
            if len(payload.password.strip()) < 6:
                raise ValueError("密码长度至少 6 位")
            user.password_hash = hash_password(payload.password.strip())

        login_disabled = user.ui_enabled and not next_ui_enabled
        user.role = next_role
        user.ui_enabled = next_ui_enabled

        if password_changed or login_disabled:
            revoke_user_sessions(session, user.id)

        session.add(user)
        session.commit()
        session.refresh(user)
        return self._map_user(user)

    def delete_user(self, session: Session, user_id: str, *, actor_id: str) -> None:
        if user_id == actor_id:
            raise ValueError("不能删除当前登录账号")

        user = session.get(UserEntity, user_id)
        if not user:
            raise ValueError("用户不存在")

        if user.role == "director" and self._count_directors(session) <= 1:
            raise ValueError("至少保留一名导演账号")

        delete_user_sessions(session, user_id)
        session.delete(user)
        session.commit()

    @staticmethod
    def _count_directors(session: Session) -> int:
        return len(session.exec(select(UserEntity).where(UserEntity.role == "director")).all())

    def list_projects(self, session: Session) -> list[ProjectRead]:
        projects = session.exec(select(ProjectEntity)).all()
        return [self._map_project(item) for item in projects]

    def create_project(self, session: Session, payload: ProjectCreateRequest) -> ProjectRead:
        project = ProjectEntity(
            id=f"proj_{uuid4().hex[:8]}",
            name=payload.name,
            destination=payload.destination,
            platform=payload.platform,
            target_duration_sec=payload.targetDurationSec,
            video_type=payload.videoType,
            style_preference=payload.stylePreference,
            style_notes=payload.styleNotes,
            route_text=payload.routeText.strip(),
            media_root=payload.mediaRoot,
            jianying_draft_root=payload.jianyingDraftRoot.strip(),
            status=payload.status,
            selected_theme_id="",
            validate_location_order=payload.validateLocationOrder,
            allow_asset_reuse=payload.allowAssetReuse,
            duration_fill_max_consecutive_route=payload.durationFillMaxConsecutiveRoute,
        )
        session.add(project)
        session.commit()
        session.refresh(project)
        return self._map_project(project)

    def get_project_entity(self, session: Session, project_id: str) -> ProjectEntity | None:
        return session.get(ProjectEntity, project_id)

    def get_project(self, session: Session, project_id: str) -> ProjectRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None
        return self._map_project(project)

    def update_project(
        self, session: Session, project_id: str, payload: ProjectUpdateRequest
    ) -> ProjectRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        project.name = payload.name
        project.destination = payload.destination
        project.platform = payload.platform
        project.target_duration_sec = payload.targetDurationSec
        project.video_type = payload.videoType
        project.style_preference = payload.stylePreference
        project.style_notes = payload.styleNotes
        project.route_text = payload.routeText.strip()
        project.media_root = payload.mediaRoot
        project.jianying_draft_root = payload.jianyingDraftRoot.strip()
        project.status = payload.status
        project.validate_location_order = payload.validateLocationOrder
        project.allow_asset_reuse = payload.allowAssetReuse
        project.duration_fill_max_consecutive_route = payload.durationFillMaxConsecutiveRoute

        session.add(project)
        session.commit()
        session.refresh(project)
        return self._map_project(project)

    def delete_project(self, session: Session, project_id: str) -> bool:
        project = self.get_project_entity(session, project_id)
        if not project:
            return False

        session.exec(delete(AssetEntity).where(AssetEntity.project_id == project_id))
        session.exec(delete(ThemeEntity).where(ThemeEntity.project_id == project_id))
        session.exec(
            delete(StoryboardSegmentEntity).where(
                StoryboardSegmentEntity.project_id == project_id
            )
        )
        session.exec(delete(RhythmPlanEntity).where(RhythmPlanEntity.project_id == project_id))
        session.exec(delete(PublishPlanEntity).where(PublishPlanEntity.project_id == project_id))
        session.delete(project)
        session.commit()
        return True

    def list_assets(self, session: Session, project_id: str) -> list[AssetRead]:
        assets = session.exec(
            select(AssetEntity).where(AssetEntity.project_id == project_id)
        ).all()
        mapped_assets = [self._map_asset(item) for item in assets]
        return sorted(mapped_assets, key=asset_order_key)

    def get_asset_entity(self, session: Session, asset_id: str) -> AssetEntity | None:
        return session.get(AssetEntity, asset_id)

    def get_asset(self, session: Session, project_id: str, asset_id: str) -> AssetRead | None:
        asset = self.get_asset_entity(session, asset_id)
        if not asset or asset.project_id != project_id:
            return None
        return self._map_asset(asset)

    def create_asset(
        self, session: Session, project_id: str, payload: AssetCreateRequest
    ) -> AssetRead:
        asset = AssetEntity(
            asset_id=self._generate_asset_id(session, project_id, payload.location),
            project_id=project_id,
            location=payload.location,
            scene=payload.scene,
            relative_path=payload.relativePath,
            media_type=payload.mediaType,
            shot_type=payload.shotType,
            emotion_tags=dumps_list(payload.emotionTags),
            visual_tags=dumps_list(payload.visualTags),
            information_density=payload.informationDensity,
            suggested_duration_sec=payload.suggestedDurationSec,
            function_tags=dumps_list(payload.functionTags),
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return self._map_asset(asset)

    def update_asset(
        self, session: Session, project_id: str, asset_id: str, payload: AssetUpdateRequest
    ) -> AssetRead | None:
        asset = self.get_asset_entity(session, asset_id)
        if not asset or asset.project_id != project_id:
            return None

        asset.location = payload.location
        asset.scene = payload.scene
        asset.relative_path = payload.relativePath
        asset.media_type = payload.mediaType
        asset.shot_type = payload.shotType
        asset.emotion_tags = dumps_list(payload.emotionTags)
        asset.visual_tags = dumps_list(payload.visualTags)
        asset.information_density = payload.informationDensity
        asset.suggested_duration_sec = payload.suggestedDurationSec
        asset.function_tags = dumps_list(payload.functionTags)
        asset.vision_analysis_status = "empty"
        asset.vision_analysis_json = ""

        session.add(asset)
        session.commit()
        session.refresh(asset)
        return self._map_asset(asset)

    def find_cached_vision_analysis(
        self,
        session: Session,
        project_id: str,
        *,
        file_fingerprint: str,
        exclude_asset_id: str,
    ) -> tuple[str, dict[str, Any]] | None:
        rows = session.exec(
            select(AssetEntity).where(AssetEntity.project_id == project_id)
        ).all()
        for row in rows:
            if row.asset_id == exclude_asset_id:
                continue
            if row.vision_analysis_status != "ready":
                continue
            try:
                payload = json.loads(row.vision_analysis_json or "{}")
            except json.JSONDecodeError:
                continue
            if payload.get("fileFingerprint") != file_fingerprint:
                continue
            prefilled = payload.get("prefilledFields") or []
            if not prefilled:
                continue
            return row.asset_id, payload
        return None

    def update_asset_vision_status(
        self,
        session: Session,
        project_id: str,
        asset_id: str,
        *,
        status: str,
        analysis_json: dict[str, Any],
        prefilled_fields: list[str],
    ) -> AssetRead | None:
        asset = self.get_asset_entity(session, asset_id)
        if not asset or asset.project_id != project_id:
            return None

        payload = dict(analysis_json)
        payload["prefilledFields"] = prefilled_fields
        asset.vision_analysis_status = status
        asset.vision_analysis_json = json.dumps(payload, ensure_ascii=False)
        if status == "ready" and prefilled_fields:
            self._apply_vision_draft_to_asset(asset, payload, prefilled_fields)
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return self._map_asset(asset)

    @staticmethod
    def _apply_vision_draft_to_asset(
        asset: AssetEntity,
        payload: dict[str, Any],
        prefilled_fields: list[str],
    ) -> None:
        if "scene" in prefilled_fields:
            scene = str(payload.get("scene", "")).strip()
            if scene:
                asset.scene = scene
        if "shotType" in prefilled_fields:
            shot_type = str(payload.get("shotType", "")).strip()
            if shot_type:
                asset.shot_type = shot_type
        if "emotionTags" in prefilled_fields:
            emotion_tags = payload.get("emotionTags", [])
            if isinstance(emotion_tags, list):
                cleaned = [str(item).strip() for item in emotion_tags if str(item).strip()]
                if cleaned:
                    asset.emotion_tags = dumps_list(cleaned)
        if "visualTags" in prefilled_fields:
            visual_tags = payload.get("visualTags", [])
            if isinstance(visual_tags, list):
                cleaned = [str(item).strip() for item in visual_tags if str(item).strip()]
                if cleaned:
                    asset.visual_tags = dumps_list(cleaned)
        if "informationDensity" in prefilled_fields:
            density = str(payload.get("informationDensity", "")).strip()
            if density:
                asset.information_density = density
        if "suggestedDurationSec" in prefilled_fields:
            duration = payload.get("suggestedDurationSec")
            if isinstance(duration, (int, float)) and float(duration) > 0:
                asset.suggested_duration_sec = float(duration)

    def delete_asset(self, session: Session, project_id: str, asset_id: str) -> bool:
        asset = self.get_asset_entity(session, asset_id)
        if not asset or asset.project_id != project_id:
            return False

        session.delete(asset)
        session.commit()
        return True

    def list_themes(self, session: Session, project_id: str) -> list[NarrativeThemeRead]:
        project = self.get_project_entity(session, project_id)
        if not project:
            return []
        themes = session.exec(
            select(ThemeEntity).where(ThemeEntity.project_id == project_id)
        ).all()
        return [self._map_theme(item, project.selected_theme_id) for item in themes]

    def generate_themes(
        self, session: Session, project_id: str, count: int = 3
    ) -> list[NarrativeThemeRead] | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        assets = self.list_assets(session, project_id)
        current_selected = project.selected_theme_id
        candidates = build_rule_theme_candidates(project, assets)[: max(1, min(count, 5))]

        return self._replace_theme_candidates(
            session,
            project=project,
            project_id=project_id,
            candidates=candidates,
            current_selected=current_selected,
        )

    def generate_themes_with_llm(
        self,
        session: Session,
        project_id: str,
        count: int = 3,
        on_progress: ProgressReporter | None = None,
    ) -> tuple[list[NarrativeThemeRead], dict[str, str]] | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        assets = self.list_assets(session, project_id)
        current_selected = project.selected_theme_id
        candidates, meta = build_llm_theme_candidates(
            project, assets, count, on_progress=on_progress
        )
        if not candidates:
            candidates = build_rule_theme_candidates(project, assets)[: max(1, min(count, 5))]

        emit_progress(on_progress, "saving", "正在保存候选主题…", progress=94)
        themes = self._replace_theme_candidates(
            session,
            project=project,
            project_id=project_id,
            candidates=candidates,
            current_selected=current_selected,
        )
        return themes, meta

    def select_theme(
        self, session: Session, project_id: str, payload: ThemeSelectRequest
    ) -> list[NarrativeThemeRead] | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        theme = session.get(ThemeEntity, payload.themeId)
        if not theme or theme.project_id != project_id:
            return None

        project.selected_theme_id = theme.id
        session.add(project)
        session.commit()
        return self.list_themes(session, project_id)

    def get_rhythm_plan(self, session: Session, project_id: str) -> RhythmPlanRead | None:
        rhythm = session.exec(
            select(RhythmPlanEntity).where(RhythmPlanEntity.project_id == project_id)
        ).first()
        if not rhythm:
            return None
        return self._map_rhythm(rhythm)

    def generate_rhythm_plan(
        self,
        session: Session,
        project_id: str,
        on_progress: ProgressReporter | None = None,
    ) -> tuple[RhythmPlanRead, dict[str, str]] | None:
        return self.recommend_bgm(session, project_id, on_progress=on_progress)

    def recommend_bgm(
        self,
        session: Session,
        project_id: str,
        on_progress: ProgressReporter | None = None,
    ) -> tuple[RhythmPlanRead, dict[str, str]] | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        emit_progress(on_progress, "preparing", "正在加载项目与主题…", progress=8)
        assets = self.list_assets(session, project_id)
        theme = self.get_selected_theme(session, project_id)
        existing_rhythm = session.exec(
            select(RhythmPlanEntity).where(RhythmPlanEntity.project_id == project_id)
        ).first()
        if existing_rhythm and existing_rhythm.audio_file_path:
            self._remove_stored_audio(existing_rhythm.audio_file_path)

        recommendations, bgm_style, rhythm_notes, llm_meta = build_llm_bgm_recommendations(
            project,
            assets,
            theme,
            on_progress=on_progress,
        )
        beat_mode = recommend_beat_mode(project.video_type)
        rhythm_profile = build_rhythm_profile(project, assets, theme)
        attention_beats = build_attention_beats(project, rhythm_profile["mode"])
        rhythm_payload = RhythmPlanWriteRequest(
            bgmStyle=bgm_style,
            selectedTrackName="",
            audioFileName="",
            analysisSource="manual",
            analysisNotes=[
                "已生成 BGM 推荐，请先选定曲目，下载后上传音频以识别真实节拍点。"
            ],
            detectedBpm=0,
            audioDurationSec=0.0,
            rawBeatPoints=[],
            coarseBeatPoints=[],
            beatMode=beat_mode,
            beatPoints=[],
            rhythmNotes=rhythm_notes,
            darkCutSuggestions=build_rule_dark_cuts(project.target_duration_sec),
            photoMotionSuggestions=build_photo_motion_suggestions(assets),
            recommendedBgm=recommendations,
            selectedBgmId="",
            bgmPhase="recommended",
            rhythmProfile=rhythm_profile,
            attentionBeats=attention_beats,
            beatCalibration={
                "source": "bgm_recommend",
                "beatOffsetSec": 0,
                "densityMode": beat_mode,
                "referenceBeatPoints": [],
            },
            audioFingerprint="",
            audioAnalysisVersion="",
        )
        emit_progress(on_progress, "saving", "正在保存 BGM 推荐…", progress=94)
        plan = self.upsert_rhythm_plan(session, project_id, rhythm_payload, audio_file_path="")
        return plan, llm_meta

    def select_bgm_recommendation(
        self,
        session: Session,
        project_id: str,
        payload: BgmSelectionRequest,
    ) -> RhythmPlanRead | None:
        rhythm = session.exec(
            select(RhythmPlanEntity).where(RhythmPlanEntity.project_id == project_id)
        ).first()
        if not rhythm:
            return None

        recommendations = self._load_bgm_recommendations(rhythm.recommended_bgm)
        selected = next(
            (item for item in recommendations if item.id == payload.recommendationId),
            None,
        )
        if not selected:
            raise ValueError("未找到对应的 BGM 推荐项")

        updated_recommendations = [
            item.model_copy(update={"isSelected": item.id == selected.id})
            for item in recommendations
        ]
        rhythm.recommended_bgm = self._dump_bgm_recommendations(updated_recommendations)
        rhythm.selected_bgm_id = selected.id
        rhythm.selected_track_name = format_bgm_track_name(selected)
        if rhythm.bgm_phase != "analyzed":
            rhythm.bgm_phase = "recommended"
        session.add(rhythm)
        session.commit()
        session.refresh(rhythm)
        return self._map_rhythm(rhythm)

    def analyze_rhythm_audio(
        self,
        session: Session,
        project_id: str,
        audio_file_name: str,
        audio_file_path: str,
        audio_file_fingerprint: str = "",
        on_progress: ProgressReporter | None = None,
    ) -> tuple[RhythmPlanRead, dict[str, str]] | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        emit_progress(on_progress, "preparing", "正在加载项目上下文…", progress=8)
        assets = self.list_assets(session, project_id)
        theme = self.get_selected_theme(session, project_id)
        existing_rhythm = session.exec(
            select(RhythmPlanEntity).where(RhythmPlanEntity.project_id == project_id)
        ).first()
        if not existing_rhythm or not existing_rhythm.selected_bgm_id:
            raise ValueError("请先在节奏页选定一首 BGM 推荐，再上传音频。")
        previous_audio_path = existing_rhythm.audio_file_path if existing_rhythm else ""

        try:
            emit_progress(
                on_progress,
                "analyzing_audio",
                f"正在分析音频「{audio_file_name}」的节拍…",
                progress=16,
                detail="音频分析可能需要 10–30 秒",
            )
            analysis = audio_beat_analyzer.analyze(audio_file_path, project.target_duration_sec)
            emit_progress(
                on_progress,
                "building_beats",
                f"已识别 BPM {analysis.bpm}，正在整理节拍点…",
                progress=30,
            )
            rhythm_payload, llm_meta = build_audio_rhythm_payload(
                project,
                assets,
                theme,
                audio_file_name,
                analysis,
                audio_file_fingerprint=audio_file_fingerprint,
                on_progress=on_progress,
            )
            rhythm_payload = self._reuse_calibration_for_same_audio(
                rhythm_payload,
                existing_rhythm,
            )
            if previous_audio_path and previous_audio_path != audio_file_path:
                self._remove_stored_audio(previous_audio_path)
            emit_progress(on_progress, "saving", "正在保存节奏规划…", progress=94)
            plan = self.upsert_rhythm_plan(
                session,
                project_id,
                rhythm_payload.model_copy(update={"bgmPhase": "analyzed"}),
                audio_file_path=audio_file_path,
            )
            return plan, llm_meta
        except AudioAnalysisError as exc:
            self._remove_stored_audio(audio_file_path)
            emit_progress(
                on_progress,
                "fallback",
                "音频识别失败，准备回退到规则生成…",
                progress=40,
            )
            rhythm_payload, llm_meta = build_rule_fallback_rhythm_payload(
                project,
                assets,
                theme,
                audio_file_name=audio_file_name,
                failure_reason=str(exc),
                on_progress=on_progress,
            )
            emit_progress(on_progress, "saving", "正在保存回退后的节奏规划…", progress=94)
            plan = self.upsert_rhythm_plan(
                session,
                project_id,
                rhythm_payload.model_copy(update={"bgmPhase": "recommended"}),
            )
            return plan, llm_meta

    def clear_rhythm_audio(self, session: Session, project_id: str) -> RhythmPlanRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        rhythm = session.exec(
            select(RhythmPlanEntity).where(RhythmPlanEntity.project_id == project_id)
        ).first()
        if not rhythm:
            return None

        self._remove_stored_audio(rhythm.audio_file_path)
        rhythm.audio_file_name = ""
        rhythm.audio_file_path = ""
        rhythm.detected_bpm = 0
        rhythm.audio_duration_sec = 0.0
        rhythm.raw_beat_points = "[]"
        rhythm.coarse_beat_points = "[]"
        rhythm.beat_points = "[]"
        rhythm.beat_calibration_json = json.dumps(
            {
                "source": "manual",
                "beatOffsetSec": 0,
                "densityMode": rhythm.beat_mode,
                "referenceBeatPoints": [],
            },
            ensure_ascii=False,
        )
        rhythm.audio_fingerprint = ""
        rhythm.audio_analysis_version = ""
        if rhythm.analysis_source == "audio_upload":
            rhythm.analysis_source = "manual"
        rhythm.bgm_phase = "recommended" if self._load_bgm_recommendations(rhythm.recommended_bgm) else "empty"
        session.add(rhythm)
        session.commit()
        session.refresh(rhythm)
        return self._map_rhythm(rhythm)

    def upsert_rhythm_plan(
        self,
        session: Session,
        project_id: str,
        payload: RhythmPlanWriteRequest,
        audio_file_path: str | None = None,
    ) -> RhythmPlanRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        rhythm = session.exec(
            select(RhythmPlanEntity).where(RhythmPlanEntity.project_id == project_id)
        ).first()
        if not rhythm:
            rhythm = RhythmPlanEntity(
                id=f"rhythm_{uuid4().hex[:8]}",
                project_id=project_id,
                bgm_style="",
                selected_track_name="",
                audio_file_name="",
                audio_file_path="",
                analysis_source="manual",
                analysis_notes="[]",
                detected_bpm=0,
                audio_duration_sec=0.0,
                raw_beat_points="[]",
                coarse_beat_points="[]",
                beat_mode="none",
                beat_points="[]",
                rhythm_notes="[]",
                dark_cut_suggestions="[]",
                photo_motion_suggestions="[]",
                rhythm_profile_json="{}",
                attention_beats_json="[]",
                beat_calibration_json="{}",
                audio_fingerprint="",
                audio_analysis_version="",
            )

        rhythm.bgm_style = payload.bgmStyle
        rhythm.selected_track_name = payload.selectedTrackName
        rhythm.audio_file_name = payload.audioFileName
        if audio_file_path is not None:
            rhythm.audio_file_path = audio_file_path
        elif not payload.audioFileName:
            rhythm.audio_file_path = ""
        rhythm.analysis_source = payload.analysisSource
        rhythm.analysis_notes = dumps_list(payload.analysisNotes)
        rhythm.detected_bpm = payload.detectedBpm
        rhythm.audio_duration_sec = payload.audioDurationSec

        existing_raw = loads_float_list(getattr(rhythm, "raw_beat_points", "[]") or "[]")
        existing_coarse = loads_float_list(getattr(rhythm, "coarse_beat_points", "[]") or "[]")
        if payload.analysisSource == "rule_fallback":
            rhythm.raw_beat_points = "[]"
            rhythm.coarse_beat_points = "[]"
            rhythm.beat_mode = payload.beatMode
            rhythm.beat_points = "[]"
        else:
            if payload.rawBeatPoints:
                raw_beats = payload.rawBeatPoints
            elif existing_raw:
                raw_beats = existing_raw
            elif payload.beatPoints and payload.beatMode != "none":
                raw_beats = normalize_beat_times(
                    payload.beatPoints,
                    float(project.target_duration_sec),
                )
            else:
                raw_beats = []

            if payload.coarseBeatPoints:
                coarse_beats = payload.coarseBeatPoints
            elif existing_coarse:
                coarse_beats = existing_coarse
            elif raw_beats:
                coarse_beats = normalize_beat_times(
                    [raw_beats[index] for index in range(0, len(raw_beats), 2)],
                    float(project.target_duration_sec),
                )
            else:
                coarse_beats = []

            if raw_beats and payload.beatMode != "none":
                reference_points = self._reference_beats_from_payload(payload.beatCalibration)
                if reference_points:
                    payload.beatMode = recommend_capcut_density_mode_from_reference(
                        raw_beats,
                        reference_points,
                        float(project.target_duration_sec),
                        coarse_beats=coarse_beats or None,
                        current_mode=payload.beatMode,
                    )
                beat_points = filter_beats_for_capcut_mode(
                    raw_beats,
                    payload.beatMode,
                    float(project.target_duration_sec),
                    coarse_beats=coarse_beats or None,
                )
                beat_calibration = self._calibrate_beat_payload(
                    payload.beatCalibration,
                    beat_points,
                )
                beat_points = apply_beat_calibration(
                    beat_points,
                    float(project.target_duration_sec),
                    offset_sec=self._beat_offset_from_payload(beat_calibration),
                    scale=self._beat_scale_from_payload(beat_calibration),
                )
                rhythm.raw_beat_points = dumps_list(raw_beats)
                rhythm.coarse_beat_points = dumps_list(coarse_beats)
            else:
                beat_calibration = self._calibrate_beat_payload(
                    payload.beatCalibration,
                    payload.beatPoints,
                )
                beat_points = apply_beat_calibration(
                    payload.beatPoints,
                    float(project.target_duration_sec),
                    offset_sec=self._beat_offset_from_payload(beat_calibration),
                    scale=self._beat_scale_from_payload(beat_calibration),
                )
                if payload.rawBeatPoints:
                    rhythm.raw_beat_points = dumps_list(raw_beats)
                elif raw_beats:
                    rhythm.raw_beat_points = dumps_list(raw_beats)
                elif not existing_raw:
                    rhythm.raw_beat_points = "[]"
                if payload.coarseBeatPoints:
                    rhythm.coarse_beat_points = dumps_list(coarse_beats)
                elif coarse_beats:
                    rhythm.coarse_beat_points = dumps_list(coarse_beats)
                elif not existing_coarse:
                    rhythm.coarse_beat_points = "[]"

            rhythm.beat_mode = payload.beatMode
            rhythm.beat_points = dumps_list(beat_points)
            payload.beatCalibration = beat_calibration

        rhythm.rhythm_notes = dumps_list(payload.rhythmNotes)
        rhythm.dark_cut_suggestions = dumps_list(payload.darkCutSuggestions)
        rhythm.photo_motion_suggestions = dumps_list(payload.photoMotionSuggestions)
        if payload.rhythmProfile:
            rhythm.rhythm_profile_json = json.dumps(payload.rhythmProfile, ensure_ascii=False)
        if payload.attentionBeats:
            rhythm.attention_beats_json = json.dumps(payload.attentionBeats, ensure_ascii=False)
        if payload.beatCalibration:
            rhythm.beat_calibration_json = json.dumps(payload.beatCalibration, ensure_ascii=False)
        if payload.audioFingerprint:
            rhythm.audio_fingerprint = payload.audioFingerprint
        if payload.audioAnalysisVersion:
            rhythm.audio_analysis_version = payload.audioAnalysisVersion

        if payload.recommendedBgm is not None:
            rhythm.recommended_bgm = self._dump_bgm_recommendations(payload.recommendedBgm)
        if payload.selectedBgmId is not None:
            rhythm.selected_bgm_id = payload.selectedBgmId
        if payload.bgmPhase is not None:
            rhythm.bgm_phase = payload.bgmPhase

        session.add(rhythm)
        session.commit()
        session.refresh(rhythm)
        return self._map_rhythm(rhythm)

    def list_storyboard(
        self, session: Session, project_id: str, theme_id: str | None = None
    ) -> list[StoryboardSegmentRead]:
        query = select(StoryboardSegmentEntity).where(
            StoryboardSegmentEntity.project_id == project_id
        )
        if theme_id:
            query = query.where(StoryboardSegmentEntity.theme_id == theme_id)
        query = query.order_by(StoryboardSegmentEntity.start_time)
        segments = session.exec(query).all()
        return [self._map_segment(item) for item in segments]

    def get_storyboard_bundle(self, session: Session, project_id: str) -> StoryboardBundleRead:
        project = self.get_project_entity(session, project_id)
        segments = self.list_storyboard(session, project_id)
        assets = self.list_assets(session, project_id)
        return StoryboardBundleRead(
            segments=segments,
            validation=build_storyboard_validation(
                project,
                segments,
                self.get_rhythm_plan(session, project_id),
                assets,
            ),
        )

    def get_storyboard_segment(
        self, session: Session, project_id: str, segment_id: str
    ) -> StoryboardSegmentRead | None:
        segment = session.get(StoryboardSegmentEntity, segment_id)
        if not segment or segment.project_id != project_id:
            return None
        return self._map_segment(segment)

    def generate_storyboard(
        self, session: Session, project_id: str, request: StoryboardGenerateRequest
    ) -> StoryboardBundleRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        rhythm = self.get_rhythm_plan(session, project_id)
        if not rhythm_ready_for_storyboard(rhythm):
            raise ValueError(rhythm_requirement_message(rhythm))

        theme = self._resolve_theme(session, project_id, request.themeId)
        assets = self.list_assets(session, project_id)
        if not theme or not assets:
            return StoryboardBundleRead(
                segments=[],
                validation=build_storyboard_validation(project, [], rhythm, assets),
            )

        target_duration = request.targetDurationSec or project.target_duration_sec
        align_to_beat = request.alignToBeat
        beat_mode = (
            request.beatMode or (rhythm.beatMode if rhythm else "none")
            if align_to_beat
            else "none"
        )
        beat_points = resolve_storyboard_beat_points(
            rhythm,
            beat_mode=beat_mode,
            target_duration_sec=target_duration,
            align_to_beat=align_to_beat,
        )

        segments = generate_storyboard_segments(
            assets=assets,
            theme_id=theme.id,
            target_duration_sec=target_duration,
            beat_mode=beat_mode,
            beat_points=beat_points,
            allow_asset_reuse=bool(project.allow_asset_reuse),
            attention_beats=rhythm.attentionBeats if rhythm else [],
            rhythm_profile=rhythm.rhythmProfile if rhythm else {},
            route_locations=parse_route_locations(project.route_text),
            duration_fill_max_consecutive_route=int(
                getattr(project, "duration_fill_max_consecutive_route", 2) or 2
            ),
        )
        self._replace_storyboard_segments(session, project_id, theme.id, segments)
        return self.get_storyboard_bundle(session, project_id)

    def generate_storyboard_with_llm(
        self,
        session: Session,
        project_id: str,
        request: StoryboardGenerateRequest,
        on_progress: ProgressReporter | None = None,
    ) -> tuple[StoryboardBundleRead, dict[str, str]] | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        rhythm = self.get_rhythm_plan(session, project_id)
        if not rhythm_ready_for_storyboard(rhythm):
            raise ValueError(rhythm_requirement_message(rhythm))

        theme = self._resolve_theme(session, project_id, request.themeId)
        assets = self.list_assets(session, project_id)
        rhythm = self.get_rhythm_plan(session, project_id)
        if not theme or not assets:
            return StoryboardBundleRead(
                segments=[],
                validation=build_storyboard_validation(project, [], rhythm, assets),
            ), {}

        target_duration = request.targetDurationSec or project.target_duration_sec
        align_to_beat = request.alignToBeat
        beat_mode = (
            request.beatMode or (rhythm.beatMode if rhythm else "none")
            if align_to_beat
            else "none"
        )
        beat_points = resolve_storyboard_beat_points(
            rhythm,
            beat_mode=beat_mode,
            target_duration_sec=target_duration,
            align_to_beat=align_to_beat,
        )
        llm_plan, meta = build_llm_storyboard_plan(
            project=project,
            theme=theme,
            assets=assets,
            rhythm=rhythm,
            target_duration_sec=target_duration,
            beat_mode=beat_mode,
            on_progress=on_progress,
        )
        emit_progress(on_progress, "building", "正在组装时间线与镜头时长…", progress=90)
        if llm_plan:
            segments = generate_storyboard_segments_from_plan(
                assets=assets,
                theme_id=theme.id,
                target_duration_sec=target_duration,
                beat_mode=beat_mode,
                beat_points=beat_points,
                llm_plan=llm_plan,
                allow_asset_reuse=bool(project.allow_asset_reuse),
                attention_beats=rhythm.attentionBeats if rhythm else [],
                rhythm_profile=rhythm.rhythmProfile if rhythm else {},
                route_locations=parse_route_locations(project.route_text),
            )
        else:
            segments = generate_storyboard_segments(
                assets=assets,
                theme_id=theme.id,
                target_duration_sec=target_duration,
                beat_mode=beat_mode,
                beat_points=beat_points,
                allow_asset_reuse=bool(project.allow_asset_reuse),
                attention_beats=rhythm.attentionBeats if rhythm else [],
                rhythm_profile=rhythm.rhythmProfile if rhythm else {},
                route_locations=parse_route_locations(project.route_text),
                duration_fill_max_consecutive_route=int(
                    getattr(project, "duration_fill_max_consecutive_route", 2) or 2
                ),
            )

        emit_progress(on_progress, "saving", "正在保存分镜时间线…", progress=95)
        self._replace_storyboard_segments(session, project_id, theme.id, segments)
        return self.get_storyboard_bundle(session, project_id), meta

    def save_storyboard(
        self, session: Session, project_id: str, payload: StoryboardSaveRequest
    ) -> StoryboardBundleRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None
        theme = self._resolve_theme(session, project_id, payload.themeId)
        theme_id = theme.id if theme else project.selected_theme_id
        self._replace_storyboard_segments(session, project_id, theme_id, payload.segments)
        return self.get_storyboard_bundle(session, project_id)

    def insert_storyboard_segment(
        self, session: Session, project_id: str, payload: StoryboardInsertRequest
    ) -> StoryboardBundleRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        current_segments = self.list_storyboard(session, project_id)
        ordered_segments = [segment_read_to_write(item) for item in current_segments]
        if payload.afterSegmentId:
            insert_index = next(
                (
                    index + 1
                    for index, segment in enumerate(ordered_segments)
                    if segment.id == payload.afterSegmentId
                ),
                None,
            )
            if insert_index is None:
                raise ValueError("Reference storyboard segment not found")
        else:
            insert_index = len(ordered_segments)

        new_segment = payload.segment.model_copy(
            update={"id": payload.segment.id or f"seg_{uuid4().hex[:8]}"}
        )
        ordered_segments.insert(insert_index, new_segment)

        normalized_segments = normalize_storyboard_segments(
            ordered_segments,
            self.get_rhythm_plan(session, project_id),
        )
        theme = self._resolve_theme(session, project_id, payload.themeId)
        theme_id = theme.id if theme else project.selected_theme_id
        self._replace_storyboard_segments(session, project_id, theme_id, normalized_segments)
        return self.get_storyboard_bundle(session, project_id)

    def reorder_storyboard(
        self, session: Session, project_id: str, payload: StoryboardReorderRequest
    ) -> StoryboardBundleRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        current_segments = self.list_storyboard(session, project_id)
        segment_map = {
            segment.id: segment_read_to_write(segment) for segment in current_segments
        }
        current_ids = list(segment_map.keys())
        if sorted(current_ids) != sorted(payload.orderedSegmentIds):
            raise ValueError("Reorder request must include every storyboard segment exactly once")

        ordered_segments = [segment_map[segment_id] for segment_id in payload.orderedSegmentIds]
        normalized_segments = normalize_storyboard_segments(
            ordered_segments,
            self.get_rhythm_plan(session, project_id),
        )
        theme_id = project.selected_theme_id
        self._replace_storyboard_segments(session, project_id, theme_id, normalized_segments)
        return self.get_storyboard_bundle(session, project_id)

    def fill_storyboard_voiceover_from_subtitles(
        self,
        session: Session,
        project_id: str,
        payload: StoryboardVoiceoverFillRequest,
    ) -> StoryboardBundleRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        segments = session.exec(
            select(StoryboardSegmentEntity)
            .where(StoryboardSegmentEntity.project_id == project_id)
            .order_by(StoryboardSegmentEntity.start_time)
        ).all()
        for segment in segments:
            if segment.voiceover_text.strip() and not payload.overwriteExisting:
                continue
            voiceover_text = self._voiceover_text_from_subtitle(segment.subtitle)
            if not voiceover_text:
                continue
            segment.voiceover_text = voiceover_text
            segment.voiceover_role = payload.role or segment.voiceover_role or "narration"
            segment.voiceover_timing = payload.timing or segment.voiceover_timing or "follow_segment"
            session.add(segment)

        session.commit()
        return self.get_storyboard_bundle(session, project_id)

    def update_storyboard_segment(
        self,
        session: Session,
        project_id: str,
        segment_id: str,
        payload: StoryboardSegmentWrite,
    ) -> StoryboardSegmentRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        segment = session.get(StoryboardSegmentEntity, segment_id)
        if not segment or segment.project_id != project_id:
            return None

        segment.start_time = payload.startTime
        segment.end_time = payload.endTime
        segment.asset_id = payload.assetId
        segment.shot_description = payload.shotDescription
        segment.function_name = payload.function
        segment.rhythm = payload.rhythm
        segment.beat_mode = payload.beatMode
        segment.beat_points = dumps_list(payload.beatPoints)
        segment.subtitle = payload.subtitle
        segment.attention_role = payload.attentionRole
        segment.visual_strength = payload.visualStrength
        segment.motion_policy = payload.motionPolicy
        segment.transition_policy = payload.transitionPolicy
        segment.subtitle_policy = payload.subtitlePolicy
        segment.selection_trace = payload.selectionTrace
        segment.voiceover_text = payload.voiceoverText
        segment.voiceover_role = payload.voiceoverRole
        segment.voiceover_timing = payload.voiceoverTiming

        session.add(segment)
        session.commit()
        session.refresh(segment)
        return self._map_segment(segment)

    def delete_storyboard_segment(
        self, session: Session, project_id: str, segment_id: str
    ) -> StoryboardBundleRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        segment = session.get(StoryboardSegmentEntity, segment_id)
        if not segment or segment.project_id != project_id:
            return None

        session.delete(segment)
        session.commit()
        return self.get_storyboard_bundle(session, project_id)

    def get_export_plan(self, session: Session, project_id: str) -> ExportPlanRead | None:
        publish = session.exec(
            select(PublishPlanEntity).where(PublishPlanEntity.project_id == project_id)
        ).first()
        if not publish:
            return None
        return self._map_export_plan(publish)

    def upsert_export_plan(
        self, session: Session, project_id: str, payload: ExportPlanWriteRequest
    ) -> ExportPlanRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        publish = session.exec(
            select(PublishPlanEntity).where(PublishPlanEntity.project_id == project_id)
        ).first()
        if not publish:
            publish = PublishPlanEntity(
                id=f"publish_{uuid4().hex[:8]}",
                project_id=project_id,
                title="",
                short_title="",
                description="",
                tags="[]",
                cover_suggestion="",
                voiceover_script="",
                voiceover_provider="",
                voiceover_voice="auto",
                voiceover_style="natural",
                voiceover_speed=1.0,
                voiceover_emotion="calm",
                voiceover_density="standard",
            )

        publish.title = payload.title
        publish.short_title = payload.shortTitle
        publish.description = payload.description
        publish.tags = dumps_list(payload.tags)
        publish.cover_suggestion = payload.coverSuggestion
        publish.voiceover_script = payload.voiceoverScript
        publish.voiceover_provider = payload.voiceoverProvider
        requested_voice = payload.voiceoverVoice.strip() or "auto"
        publish.voiceover_voice = (
            requested_voice
            if payload.voiceoverProvider == "edge"
            and get_voiceover_voice("edge", requested_voice)
            else "auto"
        )
        publish.voiceover_style = payload.voiceoverStyle
        publish.voiceover_speed = payload.voiceoverSpeed
        publish.voiceover_emotion = payload.voiceoverEmotion
        publish.voiceover_density = self._normalize_voiceover_density(payload.voiceoverDensity)

        session.add(publish)
        session.commit()
        session.refresh(publish)
        return self._map_export_plan(publish)

    def suggest_export_plan_with_llm(
        self,
        session: Session,
        project_id: str,
        on_progress: ProgressReporter | None = None,
    ) -> tuple[ExportPlanRead, dict[str, str]] | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        emit_progress(on_progress, "preparing", "正在加载项目、主题与分镜…", progress=8)
        assets = self.list_assets(session, project_id)
        theme = self.get_selected_theme(session, project_id)
        storyboard_bundle = self.get_storyboard_bundle(session, project_id)
        current_plan = self.get_export_plan(session, project_id)
        suggestion, meta = build_llm_export_plan(
            project=project,
            assets=assets,
            theme=theme,
            storyboard=storyboard_bundle.segments,
            current_plan=current_plan,
            on_progress=on_progress,
        )
        if not suggestion:
            suggestion = build_rule_export_fallback(project=project, theme=theme)

        segment_captions = suggestion.get("segmentCaptions") or []
        payload = ExportPlanWriteRequest(
            title=str(suggestion.get("title", "")).strip(),
            shortTitle=str(suggestion.get("shortTitle", "")).strip(),
            description=str(suggestion.get("description", "")).strip(),
            tags=self._normalize_tag_list(suggestion.get("tags")),
            coverSuggestion=str(suggestion.get("coverSuggestion", "")).strip(),
            voiceoverScript=current_plan.voiceoverScript if current_plan else "",
            voiceoverProvider=current_plan.voiceoverProvider if current_plan else "",
            voiceoverVoice=current_plan.voiceoverVoice if current_plan else "auto",
            voiceoverStyle=current_plan.voiceoverStyle if current_plan else "natural",
            voiceoverSpeed=current_plan.voiceoverSpeed if current_plan else 1.0,
            voiceoverEmotion=current_plan.voiceoverEmotion if current_plan else "calm",
            voiceoverDensity=current_plan.voiceoverDensity if current_plan else "standard",
        )
        emit_progress(on_progress, "saving", "正在保存导出文案…", progress=94)
        plan = self.upsert_export_plan(session, project_id, payload)

        caption_updates, caption_count = apply_export_captions_to_segments(
            storyboard_bundle.segments,
            segment_captions if isinstance(segment_captions, list) else [],
        )
        if caption_updates:
            theme_id = theme.id if theme else project.selected_theme_id
            merged_segments = merge_storyboard_subtitle_updates(
                storyboard_bundle.segments,
                caption_updates,
            )
            self._replace_storyboard_segments(session, project_id, theme_id, merged_segments)
            meta = {**meta, "storyboardCaptionsUpdated": str(caption_count)}
        return plan, meta

    def build_export_document(
        self, session: Session, project_id: str, fmt: str
    ) -> ExportDocumentRead | None:
        workspace = self.get_workspace(session, project_id)
        if not workspace:
            return None

        content = render_export_content(workspace, fmt)
        extension = {
            "markdown": "md",
            "csv": "csv",
            "capcut": "capcut-draft.json",
            "edl": "edl",
            "voiceover": "voiceover.txt",
        }.get(fmt, fmt)
        return ExportDocumentRead(
            projectId=project_id,
            format=fmt,
            fileName=f"{project_id}-timeline.{extension}",
            content=content,
        )

    def prepare_export_voiceover_generation(
        self,
        session: Session,
        project_id: str,
        payload: VoiceoverGenerateRequest,
    ) -> ExportPlanRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        publish = session.exec(
            select(PublishPlanEntity).where(PublishPlanEntity.project_id == project_id)
        ).first()
        if not publish:
            publish = PublishPlanEntity(
                id=f"publish_{uuid4().hex[:8]}",
                project_id=project_id,
                title="",
                short_title="",
                description="",
                tags="[]",
                cover_suggestion="",
            )

        script = publish.voiceover_script.strip()
        if not script and payload.useSegmentFallback:
            storyboard_bundle = self.get_storyboard_bundle(session, project_id)
            script = "\n".join(
                segment.voiceoverText.strip() or segment.subtitle.strip()
                for segment in storyboard_bundle.segments
                if segment.voiceoverText.strip() or segment.subtitle.strip()
            ).strip()

        provider = (publish.voiceover_provider or "").strip()
        provider_config = get_voiceover_provider(provider)
        caption_blocks: list[str] = []
        caption_block_segment_ids: list[list[str]] = []
        if provider == "edge":
            workspace = self.get_workspace(session, project_id)
            if workspace:
                from app.services.capcut_draft_export import build_native_voiceover_blocks

                final_blocks = [
                    block for block in build_native_voiceover_blocks(workspace) if block.text.strip()
                ]
                caption_blocks = [block.text.strip() for block in final_blocks]
                caption_block_segment_ids = [block.segment_ids for block in final_blocks]
                if caption_blocks:
                    script = "\n".join(caption_blocks)
        duration_sec = self._estimate_voiceover_duration_sec(
            script,
            speed=getattr(publish, "voiceover_speed", 1.0) or 1.0,
        )
        timeline_duration_sec = self._storyboard_timeline_duration_sec(session, project_id)
        status = "ready" if script and provider else "provider_required"
        if not script:
            status = "script_required"
        if script and provider and not is_voiceover_provider_enabled(provider):
            status = "provider_not_supported"

        provider_meta = {
            "dryRun": payload.dryRun,
            "provider": provider,
            "voiceSelection": getattr(publish, "voiceover_voice", "auto") or "auto",
            "style": publish.voiceover_style or "natural",
            "speed": getattr(publish, "voiceover_speed", 1.0) or 1.0,
            "emotion": publish.voiceover_emotion or "calm",
            "density": self._normalize_voiceover_density(
                getattr(publish, "voiceover_density", "standard") or "standard"
            ),
            "scriptChars": len(script),
            "estimatedSpeechDurationSec": duration_sec,
            "timelineDurationSec": timeline_duration_sec,
            "providerLabel": provider_config.label if provider_config else "",
            "providerDescription": provider_config.description if provider_config else "",
            "providerEnabled": bool(provider_config and provider_config.is_enabled),
            "realTts": bool(provider_config and provider_config.is_real_tts),
            "source": "export_script" if publish.voiceover_script.strip() else "segment_fallback",
            "synthesisTextSource": "final_caption_blocks" if caption_blocks else "raw_script",
            "captionBlockCount": len(caption_blocks),
            "synthesisTextFingerprint": hashlib.sha256(script.encode("utf-8")).hexdigest()[:16]
            if script
            else "",
            "message": self._voiceover_generation_message(status),
        }
        previous_audio_path = publish.voiceover_audio_path or ""

        if status == "ready" and not payload.dryRun and provider == "mock_silence":
            # mock_silence is a timeline placeholder, not real TTS. Keep it full-length
            # so JianYing/CapCut can validate the complete voiceover track.
            duration_sec = max(duration_sec, timeline_duration_sec)
            audio_path = self._write_mock_voiceover_audio(
                project_id=project_id,
                publish_id=publish.id,
                duration_sec=duration_sec,
            )
            status = "generated"
            provider_meta["message"] = self._voiceover_generation_message(status)
            provider_meta["audioKind"] = "silent_wav_placeholder"
            provider_meta["placeholderDurationPolicy"] = "match_timeline"
            publish.voiceover_audio_path = audio_path
            if previous_audio_path and previous_audio_path != audio_path:
                self._remove_stored_audio(previous_audio_path)
        elif status == "ready" and not payload.dryRun and provider == "jianying_native_tts":
            status = "manual_required"
            provider_meta["message"] = self._voiceover_generation_message(status)
            provider_meta["handoff"] = "capcut_native_text_to_speech"
            provider_meta["audioKind"] = "jianying_native_tts_pending"
        elif status == "ready" and not payload.dryRun and provider == "edge":
            try:
                result = synthesize_edge_voiceover(
                    script=script,
                    output_dir=Path(settings.storage_dir) / "voiceover" / project_id,
                    file_stem=publish.id,
                    style=publish.voiceover_style or "natural",
                    emotion=publish.voiceover_emotion or "calm",
                    speed=getattr(publish, "voiceover_speed", 1.0) or 1.0,
                    selected_voice=getattr(publish, "voiceover_voice", "auto") or "auto",
                    caption_blocks=caption_blocks or [script],
                )
                duration_sec = result.duration_sec or duration_sec
                status = "generated"
                caption_timings = result.provider_meta.get("captionTimings", [])
                if isinstance(caption_timings, list):
                    for index, timing in enumerate(caption_timings):
                        if isinstance(timing, dict) and index < len(caption_block_segment_ids):
                            timing["segmentIds"] = caption_block_segment_ids[index]
                provider_meta.update(result.provider_meta)
                provider_meta["actualDurationSec"] = duration_sec
                provider_meta["message"] = "真实口播已生成，可直接试听、下载或写入剪映草稿。"
                publish.voiceover_audio_path = result.audio_path
                if previous_audio_path and previous_audio_path != result.audio_path:
                    self._remove_stored_audio(previous_audio_path)
            except VoiceoverSynthesisError as exc:
                status = "failed"
                provider_meta["message"] = str(exc)
                provider_meta["errorType"] = "voiceover_synthesis_failed"
                self._remove_stored_audio(previous_audio_path)

        publish.voiceover_generation_status = status
        publish.voiceover_duration_sec = duration_sec
        publish.voiceover_provider_meta = json.dumps(provider_meta, ensure_ascii=False)
        publish.voiceover_generated_at = datetime.now(timezone.utc).isoformat()
        if status not in {"ready", "generated"}:
            publish.voiceover_audio_path = ""

        session.add(publish)
        session.commit()
        session.refresh(publish)
        return self._map_export_plan(publish)

    def clear_export_voiceover_audio(
        self,
        session: Session,
        project_id: str,
    ) -> ExportPlanRead | None:
        publish = session.exec(
            select(PublishPlanEntity).where(PublishPlanEntity.project_id == project_id)
        ).first()
        if not publish:
            return None

        self._remove_stored_audio(getattr(publish, "voiceover_audio_path", "") or "")
        publish.voiceover_generation_status = "not_generated"
        publish.voiceover_audio_path = ""
        publish.voiceover_duration_sec = 0.0
        publish.voiceover_provider_meta = "{}"
        publish.voiceover_generated_at = ""
        session.add(publish)
        session.commit()
        session.refresh(publish)
        return self._map_export_plan(publish)

    def get_export_voiceover_audio_path(self, session: Session, project_id: str) -> str | None:
        publish = session.exec(
            select(PublishPlanEntity).where(PublishPlanEntity.project_id == project_id)
        ).first()
        if not publish or not publish.voiceover_audio_path:
            return None
        path = Path(publish.voiceover_audio_path)
        if not path.is_file():
            return None
        return str(path)

    def get_capcut_export_defaults(
        self, session: Session, project_id: str
    ) -> CapcutExportDefaultsRead | None:
        from app.services.capcut_draft_export import (
            default_jianying_draft_root,
            resolve_jianying_draft_root,
        )

        project = self.get_project(session, project_id)
        if not project:
            return None
        configured = project.jianyingDraftRoot.strip()
        return CapcutExportDefaultsRead(
            defaultDraftRoot=default_jianying_draft_root(),
            configuredDraftRoot=configured,
            effectiveDraftRoot=resolve_jianying_draft_root(configured),
        )

    def deploy_capcut_draft(
        self,
        session: Session,
        project_id: str,
        payload: CapcutDraftDeployRequest,
    ) -> CapcutDraftDeployRead | None:
        from app.services.capcut_draft_export import (
            CapcutDraftFolderExistsError,
            deploy_capcut_draft as write_capcut_draft,
        )

        project_entity = self.get_project_entity(session, project_id)
        workspace = self.get_workspace(session, project_id)
        if not project_entity or not workspace:
            return None

        draft_root = payload.jianyingDraftRoot.strip() or project_entity.jianying_draft_root.strip()
        if payload.persistConfig and payload.jianyingDraftRoot.strip():
            project_entity.jianying_draft_root = payload.jianyingDraftRoot.strip()
            session.add(project_entity)
            session.commit()
            session.refresh(project_entity)

        try:
            result = write_capcut_draft(
                workspace,
                draft_root=draft_root,
                clear_existing=payload.clearExisting,
            )
        except CapcutDraftFolderExistsError:
            raise
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        audio_hints: list[str] = []
        if result.bgm_included:
            audio_hints.append("已包含 BGM 音频轨")
        if result.voiceover_included:
            audio_hints.append("已包含口播音轨")
        if result.bgm_included and result.voiceover_included:
            audio_hints.append("BGM 已自动降低音量")
        audio_hint = f"，{'，'.join(audio_hints)}" if audio_hints else ""
        return CapcutDraftDeployRead(
            projectId=project_id,
            draftRoot=result.draft_root,
            draftFolderName=result.draft_folder_name,
            draftFolderPath=result.draft_folder_path,
            files=result.files,
            bgmIncluded=result.bgm_included,
            voiceoverIncluded=result.voiceover_included,
            message=(
                f"已写入剪映草稿目录：{result.draft_folder_path}（"
                f"{', '.join(result.files)}）{audio_hint}。请重启剪映或刷新草稿列表后打开。"
            ),
        )

    def import_export_json(
        self,
        session: Session,
        project_id: str,
        payload: ExportJsonImportRequest,
    ) -> ExportImportResultRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        document, parse_errors = parse_export_json_document(payload.content)
        if parse_errors and not document.get("storyboard"):
            return ExportImportResultRead(
                schemaVersion="1.0",
                dryRun=payload.dryRun,
                applied=False,
                fields=payload.fields or ["subtitle"],
                conflictStrategy=payload.conflictStrategy,
                changes=[],
                updateCount=0,
                skippedCount=0,
                unchangedCount=0,
                errors=parse_errors,
            )

        incoming_segments, segment_errors = segments_from_export_json(document)
        return self._apply_storyboard_import(
            session,
            project,
            incoming_segments=incoming_segments,
            fields=payload.fields,
            conflict_strategy=self._normalize_conflict_strategy(payload.conflictStrategy),
            dry_run=payload.dryRun,
            extra_errors=[*parse_errors, *segment_errors],
        )

    def import_export_csv(
        self,
        session: Session,
        project_id: str,
        payload: ExportCsvImportRequest,
    ) -> ExportImportResultRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        incoming_segments, parse_errors = parse_export_csv_document(
            payload.content,
            column_map=payload.columnMap,
        )
        return self._apply_storyboard_import(
            session,
            project,
            incoming_segments=incoming_segments,
            fields=payload.fields,
            conflict_strategy=self._normalize_conflict_strategy(payload.conflictStrategy),
            dry_run=payload.dryRun,
            extra_errors=parse_errors,
        )

    def _apply_storyboard_import(
        self,
        session: Session,
        project: ProjectEntity,
        *,
        incoming_segments,
        fields: list[str],
        conflict_strategy: str,
        dry_run: bool,
        extra_errors: list[str],
    ) -> ExportImportResultRead:
        storyboard_bundle = self.get_storyboard_bundle(session, project.id)
        plan = build_storyboard_import_plan(
            current_segments=storyboard_bundle.segments,
            incoming_segments=incoming_segments,
            fields=fields,
            conflict_strategy=conflict_strategy,  # type: ignore[arg-type]
        )
        plan = finalize_import_result(plan, dry_run=dry_run, applied=False, errors=extra_errors)

        if dry_run or plan.updateCount == 0:
            return plan

        merged_segments = apply_storyboard_import_plan(storyboard_bundle.segments, plan)
        theme_id = project.selected_theme_id
        self._replace_storyboard_segments(session, project.id, theme_id, merged_segments)
        return finalize_import_result(plan, dry_run=False, applied=True)

    @staticmethod
    def _normalize_conflict_strategy(value: str) -> str:
        normalized = value.strip().lower()
        return normalized if normalized in {"overwrite", "skip"} else "overwrite"

    def get_workspace(self, session: Session, project_id: str) -> WorkspaceDataRead | None:
        project = self.get_project(session, project_id)
        if not project:
            return None
        rhythm = self.get_rhythm_plan(session, project_id)
        export_plan = self.get_export_plan(session, project_id)
        storyboard_bundle = self.get_storyboard_bundle(session, project_id)
        themes = self.list_themes(session, project_id)
        export_plan_value = export_plan if export_plan else ExportPlanRead(
            title="",
            shortTitle="",
            description="",
            tags=[],
            coverSuggestion="",
            voiceoverScript="",
            voiceoverProvider="",
            voiceoverVoice="auto",
            voiceoverStyle="natural",
            voiceoverSpeed=1.0,
            voiceoverEmotion="calm",
            voiceoverDensity="standard",
        )
        selected_theme = next((theme for theme in themes if theme.isSelected), None)
        return WorkspaceDataRead(
            project=project,
            assets=self.list_assets(session, project_id),
            themes=themes,
            storyboard=storyboard_bundle.segments,
            storyboardValidation=storyboard_bundle.validation,
            exportValidation=build_export_validation(
                project=project,
                theme=selected_theme,
                export_plan=export_plan_value,
            ),
            rhythmPlan=rhythm if rhythm else RhythmPlanRead(
                bgmStyle="",
                selectedTrackName="",
                audioFileName="",
                analysisSource="manual",
                analysisNotes=[],
                detectedBpm=0,
                audioDurationSec=0.0,
                rawBeatPoints=[],
                coarseBeatPoints=[],
                beatMode="none",
                beatPoints=[],
                rhythmNotes=[],
                darkCutSuggestions=[],
                photoMotionSuggestions=[],
                recommendedBgm=[],
                selectedBgmId="",
                bgmPhase="empty",
            ),
            exportPlan=export_plan_value,
        )

    def get_selected_theme(self, session: Session, project_id: str) -> NarrativeThemeRead | None:
        project = self.get_project_entity(session, project_id)
        if not project or not project.selected_theme_id:
            return None
        theme = session.get(ThemeEntity, project.selected_theme_id)
        if not theme or theme.project_id != project_id:
            return None
        return self._map_theme(theme, project.selected_theme_id)

    @staticmethod
    def _map_project(item: ProjectEntity) -> ProjectRead:
        return ProjectRead(
            id=item.id,
            name=item.name,
            destination=item.destination,
            platform=item.platform,
            targetDurationSec=item.target_duration_sec,
            videoType=item.video_type,
            stylePreference=item.style_preference,
            styleNotes=item.style_notes,
            routeText=item.route_text,
            mediaRoot=item.media_root,
            jianyingDraftRoot=getattr(item, "jianying_draft_root", "") or "",
            status=item.status,
            selectedThemeId=item.selected_theme_id,
            validateLocationOrder=bool(getattr(item, "validate_location_order", False)),
            allowAssetReuse=bool(getattr(item, "allow_asset_reuse", False)),
            durationFillMaxConsecutiveRoute=int(
                getattr(item, "duration_fill_max_consecutive_route", 2) or 2
            ),
        )

    @staticmethod
    def _map_user(item: UserEntity) -> AuthUserRead:
        return AuthUserRead(
            id=item.id,
            username=item.username,
            displayName=item.display_name,
            role=item.role,
            uiEnabled=item.ui_enabled,
        )

    @staticmethod
    def _map_asset(item: AssetEntity) -> AssetRead:
        prefilled_fields: list[str] = []
        vision_message = ""
        raw_json = getattr(item, "vision_analysis_json", "") or ""
        if raw_json.strip():
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    raw_fields = parsed.get("prefilledFields", [])
                    if isinstance(raw_fields, list):
                        prefilled_fields = [str(field) for field in raw_fields if str(field).strip()]
                    vision_message = str(parsed.get("message", "")).strip()
            except json.JSONDecodeError:
                pass

        return AssetRead(
            assetId=item.asset_id,
            location=item.location,
            scene=item.scene,
            relativePath=item.relative_path,
            mediaType=item.media_type,
            shotType=item.shot_type,
            emotionTags=loads_str_list(item.emotion_tags),
            visualTags=loads_str_list(item.visual_tags),
            informationDensity=item.information_density,
            suggestedDurationSec=item.suggested_duration_sec,
            functionTags=loads_str_list(item.function_tags),
            visionAnalysisStatus=getattr(item, "vision_analysis_status", "empty") or "empty",
            visionPrefilledFields=prefilled_fields,
            visionAnalysisMessage=vision_message,
        )

    @staticmethod
    def _map_theme(item: ThemeEntity, selected_theme_id: str) -> NarrativeThemeRead:
        return NarrativeThemeRead(
            id=item.id,
            title=item.title,
            summary=item.summary,
            coreEmotion=item.core_emotion,
            rhythmProfile=item.rhythm_profile,
            platformReason=item.platform_reason,
            usedLocations=loads_str_list(getattr(item, "used_locations", "[]") or "[]"),
            usedAssetIds=loads_str_list(getattr(item, "used_asset_ids", "[]") or "[]"),
            isSelected=item.id == selected_theme_id,
        )

    @staticmethod
    def _map_segment(item: StoryboardSegmentEntity) -> StoryboardSegmentRead:
        return StoryboardSegmentRead(
            id=item.id,
            startTime=item.start_time,
            endTime=item.end_time,
            assetId=item.asset_id,
            shotDescription=item.shot_description,
            function=item.function_name,
            rhythm=item.rhythm,
            beatMode=item.beat_mode,
            beatPoints=loads_float_list(item.beat_points),
            subtitle=item.subtitle,
            attentionRole=getattr(item, "attention_role", "") or "",
            visualStrength=getattr(item, "visual_strength", "") or "",
            motionPolicy=getattr(item, "motion_policy", "") or "",
            transitionPolicy=getattr(item, "transition_policy", "") or "",
            subtitlePolicy=getattr(item, "subtitle_policy", "") or "",
            selectionTrace=getattr(item, "selection_trace", "") or "",
            voiceoverText=getattr(item, "voiceover_text", "") or "",
            voiceoverRole=getattr(item, "voiceover_role", "") or "",
            voiceoverTiming=getattr(item, "voiceover_timing", "") or "",
        )

    @staticmethod
    def _map_rhythm(item: RhythmPlanEntity) -> RhythmPlanRead:
        return RhythmPlanRead(
            bgmStyle=item.bgm_style,
            selectedTrackName=item.selected_track_name,
            audioFileName=item.audio_file_name,
            audioFilePath=item.audio_file_path or "",
            analysisSource=item.analysis_source,
            analysisNotes=loads_str_list(item.analysis_notes),
            detectedBpm=item.detected_bpm,
            audioDurationSec=item.audio_duration_sec,
            rawBeatPoints=loads_float_list(getattr(item, "raw_beat_points", "[]") or "[]"),
            coarseBeatPoints=loads_float_list(getattr(item, "coarse_beat_points", "[]") or "[]"),
            beatMode=item.beat_mode,
            beatPoints=loads_float_list(item.beat_points),
            rhythmNotes=loads_str_list(item.rhythm_notes),
            darkCutSuggestions=loads_float_list(item.dark_cut_suggestions),
            photoMotionSuggestions=loads_str_list(item.photo_motion_suggestions),
            recommendedBgm=SqlRepository._load_bgm_recommendations(
                getattr(item, "recommended_bgm", "[]") or "[]"
            ),
            selectedBgmId=getattr(item, "selected_bgm_id", "") or "",
            bgmPhase=getattr(item, "bgm_phase", "empty") or "empty",
            rhythmProfile=SqlRepository._load_json_object(
                getattr(item, "rhythm_profile_json", "{}") or "{}"
            ),
            attentionBeats=SqlRepository._load_json_list(
                getattr(item, "attention_beats_json", "[]") or "[]"
            ),
            beatCalibration=SqlRepository._load_json_object(
                getattr(item, "beat_calibration_json", "{}") or "{}"
            ),
            audioFingerprint=getattr(item, "audio_fingerprint", "") or "",
            audioAnalysisVersion=getattr(item, "audio_analysis_version", "") or "",
        )

    @staticmethod
    def _load_json_object(raw_value: str) -> dict[str, Any]:
        if not raw_value:
            return {}
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _load_json_list(raw_value: str) -> list[dict[str, Any]]:
        if not raw_value:
            return []
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

    @staticmethod
    def _beat_offset_from_payload(payload: dict[str, Any]) -> float:
        try:
            return float(payload.get("beatOffsetSec", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _beat_scale_from_payload(payload: dict[str, Any]) -> float:
        try:
            scale = float(payload.get("beatScale", 1) or 1)
        except (TypeError, ValueError):
            return 1.0
        return min(1.05, max(0.95, scale))

    @staticmethod
    def _voiceover_text_from_subtitle(subtitle: str) -> str:
        text_value = " ".join((subtitle or "").split()).strip(" /｜|")
        if not text_value:
            return ""
        if text_value[-1] not in "。！？!?…":
            text_value = f"{text_value}。"
        return text_value

    @staticmethod
    def _reference_beats_from_payload(payload: dict[str, Any]) -> list[float]:
        raw_reference = payload.get("referenceBeatPoints", [])
        if not isinstance(raw_reference, list):
            return []
        reference_points: list[float] = []
        for item in raw_reference:
            try:
                reference_points.append(float(item))
            except (TypeError, ValueError):
                continue
        return reference_points

    @classmethod
    def _calibrate_beat_payload(
        cls,
        payload: dict[str, Any],
        base_beat_points: list[float],
    ) -> dict[str, Any]:
        beat_calibration = dict(payload or {})
        reference_points = cls._reference_beats_from_payload(beat_calibration)
        if not reference_points:
            return beat_calibration

        estimated_offset, estimated_scale = estimate_beat_calibration_from_reference(
            base_beat_points,
            reference_points,
        )
        beat_calibration["source"] = "capcut_reference"
        beat_calibration["beatOffsetSec"] = estimated_offset
        beat_calibration["beatScale"] = estimated_scale
        beat_calibration["referenceBeatPoints"] = reference_points
        beat_calibration["confidence"] = "reference"
        return beat_calibration

    @classmethod
    def _reuse_calibration_for_same_audio(
        cls,
        payload: RhythmPlanWriteRequest,
        existing_rhythm: RhythmPlanEntity | None,
    ) -> RhythmPlanWriteRequest:
        if not existing_rhythm:
            return payload
        if not payload.audioFingerprint:
            return payload
        if payload.audioFingerprint != (getattr(existing_rhythm, "audio_fingerprint", "") or ""):
            return payload

        previous_calibration = cls._load_json_object(
            getattr(existing_rhythm, "beat_calibration_json", "{}") or "{}"
        )
        previous_offset = cls._beat_offset_from_payload(previous_calibration)
        previous_scale = cls._beat_scale_from_payload(previous_calibration)
        previous_reference = cls._reference_beats_from_payload(previous_calibration)
        if abs(previous_offset) < 0.001 and abs(previous_scale - 1.0) < 0.0001 and not previous_reference:
            return payload

        reused_calibration = {
            **payload.beatCalibration,
            "source": previous_calibration.get("source", "manual"),
            "beatOffsetSec": previous_offset,
            "beatScale": previous_scale,
            "densityMode": payload.beatMode,
            "referenceBeatPoints": previous_reference,
            "confidence": "reused_same_audio",
        }
        analysis_notes = [
            *payload.analysisNotes,
            "检测到同一音频，已复用上次保存的剪映节拍校准参数。",
        ]
        return payload.model_copy(
            update={
                "beatCalibration": reused_calibration,
                "analysisNotes": analysis_notes,
            }
        )

    @staticmethod
    def _load_bgm_recommendations(raw_value: str) -> list[BgmRecommendationRead]:
        if not raw_value:
            return []
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        recommendations: list[BgmRecommendationRead] = []
        for item in payload:
            if isinstance(item, dict):
                recommendations.append(BgmRecommendationRead.model_validate(item))
        return recommendations

    @staticmethod
    def _dump_bgm_recommendations(recommendations: list[BgmRecommendationRead]) -> str:
        return json.dumps(
            [item.model_dump() for item in recommendations],
            ensure_ascii=False,
        )

    @staticmethod
    def _map_export_plan(item: PublishPlanEntity) -> ExportPlanRead:
        return ExportPlanRead(
            title=item.title,
            shortTitle=item.short_title,
            description=item.description,
            tags=loads_str_list(item.tags),
            coverSuggestion=item.cover_suggestion,
            voiceoverScript=getattr(item, "voiceover_script", "") or "",
            voiceoverProvider=getattr(item, "voiceover_provider", "") or "",
            voiceoverVoice=getattr(item, "voiceover_voice", "") or "auto",
            voiceoverStyle=getattr(item, "voiceover_style", "") or "natural",
            voiceoverSpeed=float(getattr(item, "voiceover_speed", 1.0) or 1.0),
            voiceoverEmotion=getattr(item, "voiceover_emotion", "") or "calm",
            voiceoverDensity=SqlRepository._normalize_voiceover_density(
                getattr(item, "voiceover_density", "") or "standard"
            ),
            voiceoverGenerationStatus=getattr(
                item, "voiceover_generation_status", ""
            ) or "not_generated",
            voiceoverAudioPath=getattr(item, "voiceover_audio_path", "") or "",
            voiceoverDurationSec=float(getattr(item, "voiceover_duration_sec", 0.0) or 0.0),
            voiceoverProviderMeta=SqlRepository._loads_json_dict(
                getattr(item, "voiceover_provider_meta", "{}") or "{}"
            ),
            voiceoverGeneratedAt=getattr(item, "voiceover_generated_at", "") or "",
        )

    @staticmethod
    def _estimate_voiceover_duration_sec(script: str, speed: float = 1.0) -> float:
        cleaned = re.sub(r"\s+", "", script)
        if not cleaned:
            return 0.0
        safe_speed = max(0.5, min(speed or 1.0, 2.0))
        # 中文普通旁白约 4.2 字/秒，先用于 TTS 接入前的时长预估。
        return round(len(cleaned) / (4.2 * safe_speed), 2)

    @staticmethod
    def _normalize_voiceover_density(value: str) -> str:
        normalized = (value or "").strip().lower()
        return normalized if normalized in {"light", "standard", "info"} else "standard"

    def _storyboard_timeline_duration_sec(self, session: Session, project_id: str) -> float:
        project = self.get_project_entity(session, project_id)
        segments = session.exec(
            select(StoryboardSegmentEntity).where(StoryboardSegmentEntity.project_id == project_id)
        ).all()
        if segments:
            return round(max(float(segment.end_time or 0.0) for segment in segments), 2)
        if project:
            return float(project.target_duration_sec or 0)
        return 0.0

    @staticmethod
    def _voiceover_generation_message(status: str) -> str:
        if status == "generated":
            return "已生成本地占位静音 WAV，可用于验证音频链路；这还不是真实 AI 口播。"
        if status == "manual_required":
            return "已准备剪映原生朗读方案：写入剪映草稿后，选择口播稿文本轨并点击剪映「开始朗读」。"
        if status == "ready":
            return "口播文本和 Provider 已就绪，后续可接入 TTS 生成音频。"
        if status == "script_required":
            return "请先填写整段口播稿，或在分镜中补充逐镜头口播。"
        if status == "provider_not_supported":
            return "当前 Provider 还没有接入真实 TTS，请先使用本地占位静音或等待后续接入。"
        if status == "failed":
            return "口播音频生成失败，请检查网络和 Provider 配置后重试。"
        return "请先选择口播 Provider，再生成口播音频。"

    @staticmethod
    def _write_mock_voiceover_audio(
        *,
        project_id: str,
        publish_id: str,
        duration_sec: float,
    ) -> str:
        output_dir = Path(settings.storage_dir) / "voiceover" / project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{publish_id}-mock-silence.wav"

        sample_rate = 16000
        channels = 1
        sample_width = 2
        safe_duration = max(0.2, min(duration_sec or 1.0, 300.0))
        frame_count = int(sample_rate * safe_duration)
        silence = b"\x00\x00" * frame_count
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(silence)
        return str(output_path)

    @staticmethod
    def _loads_json_dict(value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _generate_asset_id(session: Session, project_id: str, location: str) -> str:
        base = "".join(ch for ch in location.upper() if ch.isalnum())[:6] or "ASSET"
        existing = session.exec(
            select(AssetEntity).where(AssetEntity.project_id == project_id)
        ).all()
        existing_ids = {item.asset_id for item in existing}
        next_index = len(existing) + 1
        candidate = f"{base}_{next_index:03d}"
        while candidate in existing_ids:
            next_index += 1
            candidate = f"{base}_{next_index:03d}"
        return candidate

    def _replace_theme_candidates(
        self,
        session: Session,
        *,
        project: ProjectEntity,
        project_id: str,
        candidates: list[dict],
        current_selected: str,
    ) -> list[NarrativeThemeRead]:
        session.exec(delete(ThemeEntity).where(ThemeEntity.project_id == project_id))
        themes: list[ThemeEntity] = []
        for candidate in candidates:
            theme = ThemeEntity(
                id=f"theme_{uuid4().hex[:8]}",
                project_id=project_id,
                title=candidate["title"],
                summary=candidate["summary"],
                core_emotion=candidate["coreEmotion"],
                rhythm_profile=candidate["rhythmProfile"],
                platform_reason=candidate["platformReason"],
                used_locations=dumps_list(candidate.get("usedLocations", [])),
                used_asset_ids=dumps_list(candidate.get("usedAssetIds", [])),
            )
            themes.append(theme)
            session.add(theme)

        session.commit()

        selected_theme = next((item for item in themes if item.id == current_selected), None)
        if not selected_theme and themes:
            selected_theme = themes[0]
        project.selected_theme_id = selected_theme.id if selected_theme else ""
        session.add(project)
        session.commit()
        return [self._map_theme(item, project.selected_theme_id) for item in themes]

    def _resolve_theme(
        self, session: Session, project_id: str, theme_id: str | None
    ) -> NarrativeThemeRead | None:
        if theme_id:
            theme = session.get(ThemeEntity, theme_id)
            project = self.get_project_entity(session, project_id)
            if theme and theme.project_id == project_id:
                return self._map_theme(theme, project.selected_theme_id if project else "")
        return self.get_selected_theme(session, project_id) or next(
            iter(self.list_themes(session, project_id)),
            None,
        )

    @staticmethod
    def _normalize_tag_list(value: object) -> list[str]:
        if isinstance(value, str):
            candidates = re.split(r"[,\uff0c\u3001#\s]+", value)
        elif isinstance(value, list):
            candidates = [str(item) for item in value]
        else:
            candidates = []
        return [item.strip() for item in candidates if item and item.strip()]

    def _replace_storyboard_segments(
        self,
        session: Session,
        project_id: str,
        theme_id: str,
        segments: list[StoryboardSegmentWrite],
    ) -> None:
        session.exec(delete(StoryboardSegmentEntity).where(StoryboardSegmentEntity.project_id == project_id))
        for segment in segments:
            session.add(
                StoryboardSegmentEntity(
                    id=segment.id,
                    project_id=project_id,
                    theme_id=theme_id,
                    start_time=segment.startTime,
                    end_time=segment.endTime,
                    asset_id=segment.assetId,
                    shot_description=segment.shotDescription,
                    function_name=segment.function,
                    rhythm=segment.rhythm,
                    beat_mode=segment.beatMode,
                    beat_points=dumps_list(segment.beatPoints),
                    subtitle=segment.subtitle,
                    attention_role=segment.attentionRole,
                    visual_strength=segment.visualStrength,
                    motion_policy=segment.motionPolicy,
                    transition_policy=segment.transitionPolicy,
                    subtitle_policy=segment.subtitlePolicy,
                    selection_trace=segment.selectionTrace,
                    voiceover_text=segment.voiceoverText,
                    voiceover_role=segment.voiceoverRole,
                    voiceover_timing=segment.voiceoverTiming,
                )
            )
        session.commit()


    @staticmethod
    def _remove_stored_audio(file_path: str) -> None:
        if not file_path:
            return
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            # Browsers and JianYing may keep the previous audio open on Windows.
            # A stale file must not make regeneration or state cleanup fail.
            return


repository = SqlRepository()
