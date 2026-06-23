import json
import re
from uuid import uuid4

from sqlmodel import Session, delete, select

from app.core.config import settings
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
    StoryboardValidationRead,
    ThemeSelectRequest,
    WorkspaceDataRead,
)
from app.services.audio_analysis import audio_beat_analyzer
from app.services.auth import verify_password
from app.services.export_generation import build_llm_export_plan, build_rule_export_fallback
from app.services.llm import llm_suggestion_service
from app.services.rhythm_generation import build_audio_rhythm_payload, build_rule_rhythm_payload
from app.services.theme_generation import build_llm_theme_candidates, build_rule_theme_candidates


def _loads_str_list(value: str) -> list[str]:
    if not value:
        return []
    return list(json.loads(value))


def _loads_float_list(value: str) -> list[float]:
    if not value:
        return []
    return [float(item) for item in json.loads(value)]


def _dumps(value: list[str] | list[float]) -> str:
    return json.dumps(value, ensure_ascii=False)


class SqlRepository:
    STORYBOARD_CHAPTER_PRIORITY = {
        "opening_hook": 0,
        "supporting": 1,
        "slow_climax": 2,
        "main_climax": 3,
        "ending": 4,
    }

    STORYBOARD_MODIFIER_PRIORITY = {
        "base": 0,
        "rhythm_hit": 1,
        "transition_buffer": 2,
    }

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
        return sorted(mapped_assets, key=self._asset_order_key)

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
            emotion_tags=_dumps(payload.emotionTags),
            visual_tags=_dumps(payload.visualTags),
            information_density=payload.informationDensity,
            suggested_duration_sec=payload.suggestedDurationSec,
            function_tags=_dumps(payload.functionTags),
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
        asset.emotion_tags = _dumps(payload.emotionTags)
        asset.visual_tags = _dumps(payload.visualTags)
        asset.information_density = payload.informationDensity
        asset.suggested_duration_sec = payload.suggestedDurationSec
        asset.function_tags = _dumps(payload.functionTags)

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
        self, session: Session, project_id: str, count: int = 3
    ) -> list[NarrativeThemeRead] | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        assets = self.list_assets(session, project_id)
        current_selected = project.selected_theme_id
        candidates = build_llm_theme_candidates(project, assets, count)
        if not candidates:
            candidates = build_rule_theme_candidates(project, assets)[: max(1, min(count, 5))]

        return self._replace_theme_candidates(
            session,
            project=project,
            project_id=project_id,
            candidates=candidates,
            current_selected=current_selected,
        )

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

    def generate_rhythm_plan(self, session: Session, project_id: str) -> RhythmPlanRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        assets = self.list_assets(session, project_id)
        theme = self.get_selected_theme(session, project_id)
        rhythm_payload = build_rule_rhythm_payload(project, assets, theme)
        return self.upsert_rhythm_plan(session, project_id, rhythm_payload)


    def analyze_rhythm_audio(
        self,
        session: Session,
        project_id: str,
        audio_file_name: str,
        audio_file_path: str,
    ) -> RhythmPlanRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        assets = self.list_assets(session, project_id)
        theme = self.get_selected_theme(session, project_id)
        analysis = audio_beat_analyzer.analyze(audio_file_path, project.target_duration_sec)
        rhythm_payload = build_audio_rhythm_payload(
            project,
            assets,
            theme,
            audio_file_name,
            analysis,
        )
        return self.upsert_rhythm_plan(
            session,
            project_id,
            rhythm_payload,
            audio_file_path=audio_file_path,
        )


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
        rhythm.analysis_notes = _dumps(payload.analysisNotes)
        rhythm.beat_mode = payload.beatMode
        rhythm.beat_points = _dumps(payload.beatPoints)
        rhythm.rhythm_notes = _dumps(payload.rhythmNotes)
        rhythm.dark_cut_suggestions = _dumps(payload.darkCutSuggestions)
        rhythm.photo_motion_suggestions = _dumps(payload.photoMotionSuggestions)

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
            validation=self._build_storyboard_validation(
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
                validation=self._build_storyboard_validation(
                    project,
                    [],
                    rhythm,
                    assets,
                ),
            )

        target_duration = request.targetDurationSec or project.target_duration_sec
        align_to_beat = request.alignToBeat
        beat_mode = (
            request.beatMode or (rhythm.beatMode if rhythm else "none")
            if align_to_beat
            else "none"
        )
        beat_points = rhythm.beatPoints if rhythm and align_to_beat else []

        segments = self._generate_storyboard_segments(
            assets=assets,
            theme_id=theme.id,
            target_duration_sec=target_duration,
            beat_mode=beat_mode,
            beat_points=beat_points,
        )
        self._replace_storyboard_segments(session, project_id, theme.id, segments)
        return self.get_storyboard_bundle(session, project_id)

    def generate_storyboard_with_llm(
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
                validation=self._build_storyboard_validation(
                    project,
                    [],
                    rhythm,
                    assets,
                ),
            )

        target_duration = request.targetDurationSec or project.target_duration_sec
        align_to_beat = request.alignToBeat
        beat_mode = (
            request.beatMode or (rhythm.beatMode if rhythm else "none")
            if align_to_beat
            else "none"
        )
        beat_points = rhythm.beatPoints if rhythm and align_to_beat else []
        llm_plan = self._build_llm_storyboard_plan(
            project=project,
            theme=theme,
            assets=assets,
            rhythm=rhythm,
            target_duration_sec=target_duration,
            beat_mode=beat_mode,
        )
        if llm_plan:
            segments = self._generate_storyboard_segments_from_plan(
                assets=assets,
                theme_id=theme.id,
                target_duration_sec=target_duration,
                beat_mode=beat_mode,
                beat_points=beat_points,
                llm_plan=llm_plan,
            )
        else:
            segments = self._generate_storyboard_segments(
                assets=assets,
                theme_id=theme.id,
                target_duration_sec=target_duration,
                beat_mode=beat_mode,
                beat_points=beat_points,
            )

        self._replace_storyboard_segments(session, project_id, theme.id, segments)
        return self.get_storyboard_bundle(session, project_id)

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
        ordered_segments = [self._segment_read_to_write(item) for item in current_segments]
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

        normalized_segments = self._normalize_storyboard_segments(
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
        segment_map = {segment.id: self._segment_read_to_write(segment) for segment in current_segments}
        current_ids = list(segment_map.keys())
        if sorted(current_ids) != sorted(payload.orderedSegmentIds):
            raise ValueError("Reorder request must include every storyboard segment exactly once")

        ordered_segments = [segment_map[segment_id] for segment_id in payload.orderedSegmentIds]
        normalized_segments = self._normalize_storyboard_segments(
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
        segment.beat_points = _dumps(payload.beatPoints)
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
        publish.tags = _dumps(payload.tags)
        publish.cover_suggestion = payload.coverSuggestion

        session.add(publish)
        session.commit()
        session.refresh(publish)
        return self._map_export_plan(publish)

    def suggest_export_plan_with_llm(
        self, session: Session, project_id: str
    ) -> ExportPlanRead | None:
        project = self.get_project_entity(session, project_id)
        if not project:
            return None

        assets = self.list_assets(session, project_id)
        theme = self.get_selected_theme(session, project_id)
        storyboard_bundle = self.get_storyboard_bundle(session, project_id)
        current_plan = self.get_export_plan(session, project_id)
        suggestion = build_llm_export_plan(
            project=project,
            assets=assets,
            theme=theme,
            storyboard=storyboard_bundle.segments,
            current_plan=current_plan,
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
        return self.upsert_export_plan(session, project_id, payload)


    def build_export_document(
        self, session: Session, project_id: str, fmt: str
    ) -> ExportDocumentRead | None:
        workspace = self.get_workspace(session, project_id)
        if not workspace:
            return None

        content = self._render_export_content(workspace, fmt)
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
            emotionTags=_loads_str_list(item.emotion_tags),
            visualTags=_loads_str_list(item.visual_tags),
            informationDensity=item.information_density,
            suggestedDurationSec=item.suggested_duration_sec,
            functionTags=_loads_str_list(item.function_tags),
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
            beatPoints=_loads_float_list(item.beat_points),
            subtitle=item.subtitle,
        )

    @staticmethod
    def _map_rhythm(item: RhythmPlanEntity) -> RhythmPlanRead:
        return RhythmPlanRead(
            bgmStyle=item.bgm_style,
            selectedTrackName=item.selected_track_name,
            audioFileName=item.audio_file_name,
            analysisSource=item.analysis_source,
            analysisNotes=_loads_str_list(item.analysis_notes),
            beatMode=item.beat_mode,
            beatPoints=_loads_float_list(item.beat_points),
            rhythmNotes=_loads_str_list(item.rhythm_notes),
            darkCutSuggestions=_loads_float_list(item.dark_cut_suggestions),
            photoMotionSuggestions=_loads_str_list(item.photo_motion_suggestions),
        )

    @staticmethod
    def _map_export_plan(item: PublishPlanEntity) -> ExportPlanRead:
        return ExportPlanRead(
            title=item.title,
            shortTitle=item.short_title,
            description=item.description,
            tags=_loads_str_list(item.tags),
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
    def _generate_storyboard_segments(
        assets: list[AssetRead],
        theme_id: str,
        target_duration_sec: int,
        beat_mode: str,
        beat_points: list[float],
    ) -> list[StoryboardSegmentWrite]:
        if not assets:
            return []

        ordered_assets = SqlRepository._order_assets_for_storyboard(assets)
        segments: list[StoryboardSegmentWrite] = []
        beat_index = 0
        current_time = 0.0
        safe_beats = beat_points if len(beat_points) >= 2 and beat_mode != "none" else []
        for asset in ordered_assets:
            if current_time >= float(target_duration_sec):
                break

            if safe_beats:
                beat_index = SqlRepository._advance_beat_index(safe_beats, current_time, beat_index)
                duration = max(asset.suggestedDurationSec, 0.5)
                interval = safe_beats[1] - safe_beats[0]
                beats_needed = max(1, round(duration / max(interval, 0.25)))
                next_index = min(beat_index + beats_needed, len(safe_beats) - 1)
                end_time = safe_beats[next_index]
                if end_time <= current_time:
                    end_time = min(float(target_duration_sec), current_time + duration)
                segment_beats = [point for point in safe_beats if current_time <= point <= end_time]
                beat_index = next_index
            else:
                end_time = min(float(target_duration_sec), current_time + asset.suggestedDurationSec)
                segment_beats = [round(current_time, 2), round(end_time, 2)]

            function_name = asset.functionTags[0] if asset.functionTags else "supporting"
            segments.append(
                StoryboardSegmentWrite(
                    id=f"seg_{uuid4().hex[:8]}",
                    startTime=round(current_time, 2),
                    endTime=round(end_time, 2),
                    assetId=asset.assetId,
                    shotDescription=f"{asset.location} - {asset.scene}",
                    function=function_name,
                    rhythm=SqlRepository._rhythm_label(asset.informationDensity),
                    beatMode=beat_mode,
                    beatPoints=segment_beats,
                    subtitle=SqlRepository._subtitle_from_asset(asset),
                )
            )
            current_time = round(end_time, 2)

        return segments

    @staticmethod
    def _generate_storyboard_segments_from_plan(
        assets: list[AssetRead],
        theme_id: str,
        target_duration_sec: int,
        beat_mode: str,
        beat_points: list[float],
        llm_plan: list[dict[str, str]],
    ) -> list[StoryboardSegmentWrite]:
        asset_map = {asset.assetId: asset for asset in assets}
        planned_assets: list[tuple[AssetRead, dict[str, str] | None]] = []
        used_asset_ids: set[str] = set()

        for item in llm_plan:
            asset_id = str(item.get("assetId", "")).strip()
            asset = asset_map.get(asset_id)
            if not asset or asset.assetId in used_asset_ids:
                continue
            planned_assets.append((asset, item))
            used_asset_ids.add(asset.assetId)

        for asset in SqlRepository._order_assets_for_storyboard(assets):
            if asset.assetId not in used_asset_ids:
                planned_assets.append((asset, None))

        segments: list[StoryboardSegmentWrite] = []
        beat_index = 0
        current_time = 0.0
        safe_beats = beat_points if len(beat_points) >= 2 and beat_mode != "none" else []
        for asset, plan_item in planned_assets:
            if current_time >= float(target_duration_sec):
                break

            if safe_beats:
                beat_index = SqlRepository._advance_beat_index(safe_beats, current_time, beat_index)
                duration = max(asset.suggestedDurationSec, 0.5)
                interval = safe_beats[1] - safe_beats[0]
                beats_needed = max(1, round(duration / max(interval, 0.25)))
                next_index = min(beat_index + beats_needed, len(safe_beats) - 1)
                end_time = safe_beats[next_index]
                if end_time <= current_time:
                    end_time = min(float(target_duration_sec), current_time + duration)
                segment_beats = [point for point in safe_beats if current_time <= point <= end_time]
                beat_index = next_index
            else:
                end_time = min(float(target_duration_sec), current_time + asset.suggestedDurationSec)
                segment_beats = [round(current_time, 2), round(end_time, 2)]

            fallback_function = asset.functionTags[0] if asset.functionTags else "supporting"
            fallback_rhythm = SqlRepository._rhythm_label(asset.informationDensity)
            fallback_subtitle = SqlRepository._subtitle_from_asset(asset)
            shot_description = (
                str(plan_item.get("shotDescription", "")).strip()
                if plan_item
                else ""
            ) or f"{asset.location} - {asset.scene}"
            function_name = SqlRepository._normalize_storyboard_function(
                str(plan_item.get("function", "")).strip() if plan_item else fallback_function,
                fallback_function,
            )
            rhythm_text = (
                str(plan_item.get("rhythm", "")).strip() if plan_item else ""
            ) or fallback_rhythm
            subtitle = (
                str(plan_item.get("subtitle", "")).strip() if plan_item else ""
            ) or fallback_subtitle

            segments.append(
                StoryboardSegmentWrite(
                    id=f"seg_{uuid4().hex[:8]}",
                    startTime=round(current_time, 2),
                    endTime=round(end_time, 2),
                    assetId=asset.assetId,
                    shotDescription=shot_description,
                    function=function_name,
                    rhythm=rhythm_text,
                    beatMode=beat_mode,
                    beatPoints=segment_beats,
                    subtitle=subtitle,
                )
            )
            current_time = round(end_time, 2)

        return segments

    @staticmethod
    def _order_assets_for_storyboard(assets: list[AssetRead]) -> list[AssetRead]:
        indexed_assets = list(enumerate(assets))
        indexed_assets.sort(
            key=lambda item: (
                SqlRepository._asset_storyboard_chapter_priority(item[1]),
                SqlRepository._asset_storyboard_modifier_priority(item[1]),
                SqlRepository._asset_sequence_number(item[1].assetId),
                item[0],
            )
        )
        return [asset for _, asset in indexed_assets]

    @staticmethod
    def _asset_storyboard_chapter_priority(asset: AssetRead) -> int:
        priorities = [
            SqlRepository.STORYBOARD_CHAPTER_PRIORITY[tag]
            for tag in asset.functionTags
            if tag in SqlRepository.STORYBOARD_CHAPTER_PRIORITY
        ]
        if priorities:
            return min(priorities)
        return SqlRepository.STORYBOARD_CHAPTER_PRIORITY["supporting"]

    @staticmethod
    def _asset_storyboard_modifier_priority(asset: AssetRead) -> int:
        if "transition_buffer" in asset.functionTags:
            return SqlRepository.STORYBOARD_MODIFIER_PRIORITY["transition_buffer"]
        if "rhythm_hit" in asset.functionTags:
            return SqlRepository.STORYBOARD_MODIFIER_PRIORITY["rhythm_hit"]
        return SqlRepository.STORYBOARD_MODIFIER_PRIORITY["base"]

    @staticmethod
    def _asset_sequence_number(asset_id: str) -> int:
        if "_" not in asset_id:
            return 10**9
        suffix = asset_id.rsplit("_", 1)[-1]
        return int(suffix) if suffix.isdigit() else 10**9

    @staticmethod
    def _advance_beat_index(beat_points: list[float], current_time: float, beat_index: int) -> int:
        while beat_index < len(beat_points) - 1 and beat_points[beat_index] < current_time:
            beat_index += 1
        return beat_index

    @staticmethod
    def _rhythm_label(information_density: str) -> str:
        return {
            "high": "tight_cut",
            "medium": "balanced",
            "low": "linger",
        }.get(information_density, "balanced")

    @staticmethod
    def _subtitle_from_asset(asset: AssetRead) -> str:
        return f"{asset.location} / {asset.scene}"

    @staticmethod
    def _normalize_storyboard_function(candidate: str, fallback: str) -> str:
        allowed = set(SqlRepository.STORYBOARD_CHAPTER_PRIORITY) | set(
            SqlRepository.STORYBOARD_MODIFIER_PRIORITY
        )
        if candidate in allowed:
            return candidate
        return fallback if fallback in allowed else "supporting"

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
                    beat_points=_dumps(segment.beatPoints),
                    subtitle=segment.subtitle,
                )
            )
        session.commit()

    @staticmethod
    def _segment_read_to_write(segment: StoryboardSegmentRead) -> StoryboardSegmentWrite:
        return StoryboardSegmentWrite(
            id=segment.id,
            startTime=segment.startTime,
            endTime=segment.endTime,
            assetId=segment.assetId,
            shotDescription=segment.shotDescription,
            function=segment.function,
            rhythm=segment.rhythm,
            beatMode=segment.beatMode,
            beatPoints=segment.beatPoints,
            subtitle=segment.subtitle,
        )

    @staticmethod
    def _normalize_storyboard_segments(
        segments: list[StoryboardSegmentWrite],
        rhythm: RhythmPlanRead | None,
    ) -> list[StoryboardSegmentWrite]:
        normalized: list[StoryboardSegmentWrite] = []
        current_time = 0.0
        for segment in segments:
            duration = max(round(segment.endTime - segment.startTime, 2), 0.5)
            start_time = round(current_time, 2)
            end_time = round(start_time + duration, 2)
            beat_mode = rhythm.beatMode if rhythm and rhythm.beatMode != "none" else segment.beatMode
            beat_points = SqlRepository._slice_beat_points(
                rhythm.beatPoints if rhythm else [],
                start_time,
                end_time,
            )
            normalized.append(
                segment.model_copy(
                    update={
                        "startTime": start_time,
                        "endTime": end_time,
                        "beatMode": beat_mode,
                        "beatPoints": beat_points,
                    }
                )
            )
            current_time = end_time
        return normalized

    @staticmethod
    def _slice_beat_points(
        beat_points: list[float], start_time: float, end_time: float
    ) -> list[float]:
        scoped_points = [
            round(point, 2) for point in beat_points if start_time <= point <= end_time
        ]
        if scoped_points:
            return scoped_points
        return [start_time, end_time]

    @staticmethod
    def _build_storyboard_validation(
        project: ProjectEntity | None,
        segments: list[StoryboardSegmentRead],
        rhythm: RhythmPlanRead | None,
        assets: list[AssetRead],
    ) -> StoryboardValidationRead:
        asset_map = {asset.assetId: asset for asset in assets}
        all_bound = all(bool(segment.assetId) and segment.assetId in asset_map for segment in segments)
        total_duration = round(segments[-1].endTime if segments else 0.0, 2)
        beat_adaptation_enabled = any(segment.beatMode != "none" for segment in segments)
        route_locations = (
            SqlRepository._parse_route_locations(project.route_text)
            if project and project.route_text
            else []
        )
        location_continuity = SqlRepository._check_location_continuity(
            segments,
            asset_map,
            route_locations,
        )
        beat_alignment = (
            SqlRepository._check_beat_alignment(segments, rhythm.beatPoints if rhythm else [])
            if beat_adaptation_enabled
            else False
        )
        target_duration_reached = total_duration >= float(project.target_duration_sec if project else 0)

        if not segments:
            message = "当前还没有可用分镜，请先确认素材和主题。"
        elif target_duration_reached:
            message = "当前分镜总时长已经落在目标时长范围内。"
        else:
            message = "素材已全部使用完，但当前总时长还未达到目标时长。建议补充素材，或先将长素材切分后分别录入。"

        return StoryboardValidationRead(
            allSegmentsBoundToAsset=all_bound,
            locationContinuityPassed=location_continuity,
            beatAlignmentPassed=beat_alignment,
            beatAdaptationEnabled=beat_adaptation_enabled,
            totalDurationSec=total_duration,
            targetDurationReached=target_duration_reached,
            message=message,
        )

    @staticmethod
    def _parse_route_locations(route_text: str) -> list[str]:
        return [
            item.strip()
            for item in re.split(
                r"\s*(?:->|\u2192|\u2014|-|,|\uff0c|\u3001|\r?\n)\s*",
                route_text,
            )
            if item.strip()
        ]

    @staticmethod
    def _check_location_continuity(
        segments: list[StoryboardSegmentRead],
        asset_map: dict[str, AssetRead],
        route_locations: list[str],
    ) -> bool:
        if not segments:
            return False

        segment_locations: list[str] = []
        for segment in segments:
            asset = asset_map.get(segment.assetId)
            if not asset or not asset.location:
                return False
            segment_locations.append(asset.location)

        if route_locations:
            route_index_map = {location: index for index, location in enumerate(route_locations)}
            route_indexes = [route_index_map.get(location) for location in segment_locations]
            if all(index is not None for index in route_indexes):
                last_index = -1
                for index in route_indexes:
                    if index is not None and index < last_index:
                        return False
                    if index is not None:
                        last_index = index
                return True

        seen_order: dict[str, int] = {}
        last_seen_index = -1
        for location in segment_locations:
            if location not in seen_order:
                seen_order[location] = len(seen_order)
            current_index = seen_order[location]
            if current_index < last_seen_index:
                return False
            last_seen_index = current_index
        return True

    @staticmethod
    def _check_beat_alignment(
        segments: list[StoryboardSegmentRead],
        beat_points: list[float],
        tolerance: float = 0.05,
    ) -> bool:
        if not segments or len(beat_points) < 2:
            return False

        for segment in segments:
            if not segment.beatPoints:
                return False
            if not SqlRepository._is_on_beat(segment.startTime, beat_points, tolerance):
                return False
            if not SqlRepository._is_on_beat(segment.endTime, beat_points, tolerance):
                return False
        return True

    @staticmethod
    def _is_on_beat(time_point: float, beat_points: list[float], tolerance: float) -> bool:
        return any(abs(point - time_point) <= tolerance for point in beat_points)

    @staticmethod
    def _asset_order_key(asset: AssetRead) -> tuple[int, str]:
        match = re.search(r"_(\d+)$", asset.assetId)
        if match:
            return (int(match.group(1)), asset.assetId)
        return (10**9, asset.assetId)

    def _render_export_content(self, workspace: WorkspaceDataRead, fmt: str) -> str:
        export_payload = {
            "project": workspace.project.model_dump(),
            "selectedTheme": next(
                (theme.model_dump() for theme in workspace.themes if theme.isSelected),
                None,
            ),
            "rhythmPlan": workspace.rhythmPlan.model_dump(),
            "exportPlan": workspace.exportPlan.model_dump(),
            "storyboard": [segment.model_dump() for segment in workspace.storyboard],
            "storyboardValidation": workspace.storyboardValidation.model_dump(),
        }

        if fmt == "json":
            return json.dumps(export_payload, ensure_ascii=False, indent=2)
        if fmt == "yaml":
            return self._to_yaml(export_payload)
        return self._to_markdown(workspace)

    @staticmethod
    def _to_markdown(workspace: WorkspaceDataRead) -> str:
        lines = [
            f"# {workspace.project.name} 导出脚本",
            "",
            "## 导出信息",
            f"- 标题：{workspace.exportPlan.title}",
            f"- 短标题：{workspace.exportPlan.shortTitle or '未填写'}",
            f"- 标签：{', '.join(workspace.exportPlan.tags) if workspace.exportPlan.tags else '未填写'}",
            f"- 描述：{workspace.exportPlan.description}",
            f"- 封面建议：{workspace.exportPlan.coverSuggestion or '未填写'}",
            "",
            "## 节奏信息",
            f"- BGM 风格：{workspace.rhythmPlan.bgmStyle}",
            f"- 参考曲目：{workspace.rhythmPlan.selectedTrackName}",
            f"- 节拍模式：{workspace.rhythmPlan.beatMode}",
            f"- 节拍点：{', '.join(str(point) for point in workspace.rhythmPlan.beatPoints)}",
            "",
            "## 分镜时间线",
            "",
            "| 开始 | 结束 | 素材 ID | 功能标签 | 节奏 | 字幕 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for segment in workspace.storyboard:
            lines.append(
                f"| {segment.startTime:.2f} | {segment.endTime:.2f} | {segment.assetId} | "
                f"{segment.function} | {segment.rhythm} | {segment.subtitle} |"
            )
        return "\n".join(lines)
    @staticmethod
    def _to_yaml(value: object, indent: int = 0) -> str:
        prefix = "  " * indent
        if isinstance(value, dict):
            lines: list[str] = []
            for key, item in value.items():
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}{key}:")
                    lines.append(SqlRepository._to_yaml(item, indent + 1))
                else:
                    lines.append(f"{prefix}{key}: {SqlRepository._yaml_scalar(item)}")
            return "\n".join(lines)
        if isinstance(value, list):
            lines = []
            for item in value:
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}-")
                    lines.append(SqlRepository._to_yaml(item, indent + 1))
                else:
                    lines.append(f"{prefix}- {SqlRepository._yaml_scalar(item)}")
            return "\n".join(lines)
        return f"{prefix}{SqlRepository._yaml_scalar(value)}"

    @staticmethod
    def _yaml_scalar(value: object) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        text = str(value).replace('"', '\\"')
        return f'"{text}"'


repository = SqlRepository()

