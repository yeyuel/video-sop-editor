import os
import re
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
    AuthUserRead,
    ExportDocumentRead,
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
    ThemeSelectRequest,
    WorkspaceDataRead,
)
from app.services.audio_analysis import AudioAnalysisError, audio_beat_analyzer
from app.services.auth import verify_password
from app.services.export_generation import (
    build_llm_export_plan,
    build_rule_export_fallback,
    render_export_content,
)
from app.services.rhythm_generation import (
    build_audio_rhythm_payload,
    build_rule_fallback_rhythm_payload,
    build_rule_rhythm_payload,
)
from app.services.beat_grid import filter_beats_for_capcut_mode, normalize_beat_times
from app.services.serialization import dumps_list, loads_float_list, loads_str_list
from app.services.storyboard_generation import (
    asset_order_key,
    build_llm_storyboard_plan,
    build_storyboard_validation,
    generate_storyboard_segments,
    generate_storyboard_segments_from_plan,
    normalize_storyboard_segments,
    segment_read_to_write,
)
from app.services.theme_generation import build_llm_theme_candidates, build_rule_theme_candidates
from app.services.llm.progress import ProgressReporter, emit_progress


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
            route_text=payload.routeText,
            media_root=payload.mediaRoot,
            status=payload.status,
            selected_theme_id="",
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
        project.route_text = payload.routeText
        project.media_root = payload.mediaRoot
        project.status = payload.status

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

        session.add(asset)
        session.commit()
        session.refresh(asset)
        return self._map_asset(asset)

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
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        emit_progress(on_progress, "preparing", "正在加载项目与主题…", progress=8)
        assets = self.list_assets(session, project_id)
        theme = self.get_selected_theme(session, project_id)
        rhythm_payload, llm_meta = build_rule_rhythm_payload(
            project, assets, theme, on_progress=on_progress
        )
        emit_progress(on_progress, "saving", "正在保存节奏规划…", progress=94)
        plan = self.upsert_rhythm_plan(session, project_id, rhythm_payload)
        return plan, llm_meta

    def analyze_rhythm_audio(
        self,
        session: Session,
        project_id: str,
        audio_file_name: str,
        audio_file_path: str,
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
                on_progress=on_progress,
            )
            if previous_audio_path and previous_audio_path != audio_file_path:
                self._remove_stored_audio(previous_audio_path)
            emit_progress(on_progress, "saving", "正在保存节奏规划…", progress=94)
            plan = self.upsert_rhythm_plan(
                session,
                project_id,
                rhythm_payload,
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
            plan = self.upsert_rhythm_plan(session, project_id, rhythm_payload)
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
        if rhythm.analysis_source == "audio_upload":
            rhythm.analysis_source = "manual"
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
            beat_points = filter_beats_for_capcut_mode(
                raw_beats,
                payload.beatMode,
                float(project.target_duration_sec),
                coarse_beats=coarse_beats or None,
            )
            rhythm.raw_beat_points = dumps_list(raw_beats)
            rhythm.coarse_beat_points = dumps_list(coarse_beats)
        else:
            beat_points = payload.beatPoints
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
        rhythm.rhythm_notes = dumps_list(payload.rhythmNotes)
        rhythm.dark_cut_suggestions = dumps_list(payload.darkCutSuggestions)
        rhythm.photo_motion_suggestions = dumps_list(payload.photoMotionSuggestions)

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

        theme = self._resolve_theme(session, project_id, request.themeId)
        assets = self.list_assets(session, project_id)
        rhythm = self.get_rhythm_plan(session, project_id)
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
        beat_points = rhythm.beatPoints if rhythm and align_to_beat else []

        segments = generate_storyboard_segments(
            assets=assets,
            theme_id=theme.id,
            target_duration_sec=target_duration,
            beat_mode=beat_mode,
            beat_points=beat_points,
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
        beat_points = rhythm.beatPoints if rhythm and align_to_beat else []
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
            )
        else:
            segments = generate_storyboard_segments(
                assets=assets,
                theme_id=theme.id,
                target_duration_sec=target_duration,
                beat_mode=beat_mode,
                beat_points=beat_points,
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
            )

        publish.title = payload.title
        publish.short_title = payload.shortTitle
        publish.description = payload.description
        publish.tags = dumps_list(payload.tags)
        publish.cover_suggestion = payload.coverSuggestion

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

        payload = ExportPlanWriteRequest(
            title=str(suggestion.get("title", "")).strip(),
            shortTitle=str(suggestion.get("shortTitle", "")).strip(),
            description=str(suggestion.get("description", "")).strip(),
            tags=self._normalize_tag_list(suggestion.get("tags")),
            coverSuggestion=str(suggestion.get("coverSuggestion", "")).strip(),
        )
        emit_progress(on_progress, "saving", "正在保存导出文案…", progress=94)
        plan = self.upsert_export_plan(session, project_id, payload)
        return plan, meta

    def build_export_document(
        self, session: Session, project_id: str, fmt: str
    ) -> ExportDocumentRead | None:
        workspace = self.get_workspace(session, project_id)
        if not workspace:
            return None

        content = render_export_content(workspace, fmt)
        extension = "md" if fmt == "markdown" else fmt
        return ExportDocumentRead(
            projectId=project_id,
            format=fmt,
            fileName=f"{project_id}-timeline.{extension}",
            content=content,
        )

    def get_workspace(self, session: Session, project_id: str) -> WorkspaceDataRead | None:
        project = self.get_project(session, project_id)
        if not project:
            return None
        rhythm = self.get_rhythm_plan(session, project_id)
        export_plan = self.get_export_plan(session, project_id)
        storyboard_bundle = self.get_storyboard_bundle(session, project_id)
        return WorkspaceDataRead(
            project=project,
            assets=self.list_assets(session, project_id),
            themes=self.list_themes(session, project_id),
            storyboard=storyboard_bundle.segments,
            storyboardValidation=storyboard_bundle.validation,
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
            ),
            exportPlan=export_plan if export_plan else ExportPlanRead(
                title="",
                shortTitle="",
                description="",
                tags=[],
                coverSuggestion="",
            ),
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
            status=item.status,
            selectedThemeId=item.selected_theme_id,
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
        )

    @staticmethod
    def _map_rhythm(item: RhythmPlanEntity) -> RhythmPlanRead:
        return RhythmPlanRead(
            bgmStyle=item.bgm_style,
            selectedTrackName=item.selected_track_name,
            audioFileName=item.audio_file_name,
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
        )

    @staticmethod
    def _map_export_plan(item: PublishPlanEntity) -> ExportPlanRead:
        return ExportPlanRead(
            title=item.title,
            shortTitle=item.short_title,
            description=item.description,
            tags=loads_str_list(item.tags),
            coverSuggestion=item.cover_suggestion,
        )

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
        candidates: list[dict[str, str]],
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
                )
            )
        session.commit()


    @staticmethod
    def _remove_stored_audio(file_path: str) -> None:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


repository = SqlRepository()
