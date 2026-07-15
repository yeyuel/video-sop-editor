from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete
from sqlmodel import Session, select

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
from app.services.auth import hash_password
from app.services.repository import repository
from app.services.rhythm_profile import (
    build_attention_beats,
    build_rhythm_profile,
    resolve_rhythm_mode,
)

SEED_PROJECT_ID = "proj_001"
SOURCE_PROJECT_ID = "proj_6241f409"
SEED_DATA_PATH = Path(__file__).resolve().parent / "seed_data" / "taizhou_may.json"
SEED_AUDIO_PATH = Path(__file__).resolve().parent / "seed_data" / "audio" / "1c204ceb019a.mp3"
STALE_PROJECT_IDS = ("proj_eb35c16a", SOURCE_PROJECT_ID)
LEGACY_ASSET_IDS = ("KANAS_001", "HEMU_002", "GENERAL_003")


def seed_demo_data(session: Session) -> None:
    _ensure_default_director(session)
    _ensure_demo_editor(session)
    _purge_stale_projects(session)
    _ensure_taizhou_project(session)


def _ensure_demo_editor(session: Session) -> None:
    editor = session.exec(select(UserEntity).where(UserEntity.username == "editor")).first()
    if editor:
        editor.display_name = "Demo Editor"
        editor.role = "editor"
        editor.ui_enabled = True
        session.add(editor)
        session.commit()
        return

    session.add(
        UserEntity(
            id="user_editor_demo",
            username="editor",
            display_name="Demo Editor",
            password_hash=hash_password("edit123"),
            role="editor",
            ui_enabled=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    )
    session.commit()


def _ensure_default_director(session: Session) -> None:
    default_user = session.exec(select(UserEntity).where(UserEntity.username == "director")).first()
    if default_user:
        default_user.display_name = "Director"
        default_user.role = "director"
        default_user.ui_enabled = True
        session.add(default_user)
        session.commit()
        return

    session.add(
        UserEntity(
            id="user_director",
            username="director",
            display_name="Director",
            password_hash=hash_password("root123"),
            role="director",
            ui_enabled=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    )
    session.commit()


def _load_seed_snapshot() -> dict:
    with SEED_DATA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)

def _ensure_seed_audio() -> str:
    target_dir = Path(settings.storage_dir) / "audio" / SEED_PROJECT_ID
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "1c204ceb019a.mp3"
    if SEED_AUDIO_PATH.is_file() and not target_file.exists():
        shutil.copy2(SEED_AUDIO_PATH, target_file)
    return f"./storage/audio/{SEED_PROJECT_ID}/1c204ceb019a.mp3"


def _purge_stale_projects(session: Session) -> None:
    for project_id in (*STALE_PROJECT_IDS, SEED_PROJECT_ID):
        _delete_project_graph(session, project_id)

    for asset_id in LEGACY_ASSET_IDS:
        asset = session.get(AssetEntity, asset_id)
        if asset:
            session.delete(asset)

    session.commit()


def _delete_project_graph(session: Session, project_id: str) -> None:
    project = session.get(ProjectEntity, project_id)
    if not project:
        return

    session.exec(delete(AssetEntity).where(AssetEntity.project_id == project_id))
    session.exec(delete(ThemeEntity).where(ThemeEntity.project_id == project_id))
    session.exec(
        delete(StoryboardSegmentEntity).where(StoryboardSegmentEntity.project_id == project_id)
    )
    session.exec(delete(RhythmPlanEntity).where(RhythmPlanEntity.project_id == project_id))
    session.exec(delete(PublishPlanEntity).where(PublishPlanEntity.project_id == project_id))
    session.delete(project)


def _ensure_taizhou_project(session: Session) -> None:
    snapshot = _load_seed_snapshot()
    audio_file_path = _ensure_seed_audio()

    project_data = snapshot["project"]
    project = ProjectEntity(
        id=SEED_PROJECT_ID,
        name=project_data["name"],
        destination=project_data["destination"],
        platform=project_data["platform"],
        target_duration_sec=project_data["target_duration_sec"],
        video_type=project_data["video_type"],
        style_preference=project_data["style_preference"],
        style_notes=project_data.get("style_notes", ""),
        route_text=project_data.get("route_text", ""),
        media_root=project_data.get("media_root", ""),
        jianying_draft_root=project_data.get("jianying_draft_root", ""),
        status=project_data["status"],
        selected_theme_id=project_data.get("selected_theme_id", ""),
        validate_location_order=bool(project_data.get("validate_location_order", 0)),
        allow_asset_reuse=bool(project_data.get("allow_asset_reuse", 0)),
        duration_fill_max_consecutive_route=int(
            project_data.get("duration_fill_max_consecutive_route", 2) or 2
        ),
    )
    session.add(project)

    seed_asset_ids: set[str] = set()
    for item in snapshot["assets"]:
        seed_asset_ids.add(item["asset_id"])
        _upsert_asset(
            session,
            AssetEntity(
                asset_id=item["asset_id"],
                project_id=SEED_PROJECT_ID,
                location=item["location"],
                scene=item["scene"],
                relative_path=item.get("relative_path", ""),
                media_type=item["media_type"],
                shot_type=item["shot_type"],
                emotion_tags=item["emotion_tags"],
                visual_tags=item["visual_tags"],
                information_density=item["information_density"],
                suggested_duration_sec=item["suggested_duration_sec"],
                function_tags=item["function_tags"],
                vision_analysis_json=item.get("vision_analysis_json", ""),
                vision_analysis_status=item.get("vision_analysis_status", "empty"),
            ),
        )

    for item in snapshot["themes"]:
        _upsert_theme(
            session,
            ThemeEntity(
                id=item["id"],
                project_id=SEED_PROJECT_ID,
                title=item["title"],
                summary=item["summary"],
                core_emotion=item["core_emotion"],
                rhythm_profile=item["rhythm_profile"],
                platform_reason=item["platform_reason"],
                used_locations=item.get("used_locations", "[]"),
                used_asset_ids=item.get("used_asset_ids", "[]"),
            ),
        )

    for item in snapshot["storyboard"]:
        _upsert_storyboard(
            session,
            StoryboardSegmentEntity(
                id=item["id"],
                project_id=SEED_PROJECT_ID,
                theme_id=item["theme_id"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                asset_id=item["asset_id"],
                shot_description=item["shot_description"],
                function_name=item["function_name"],
                rhythm=item["rhythm"],
                beat_mode=item["beat_mode"],
                beat_points=item["beat_points"],
                subtitle=item["subtitle"],
            ),
        )

    rhythm = snapshot["rhythm"]
    selected_theme = session.get(ThemeEntity, project.selected_theme_id)
    seeded_assets = session.exec(
        select(AssetEntity).where(AssetEntity.project_id == SEED_PROJECT_ID)
    ).all()
    asset_reads = [repository._map_asset(item) for item in seeded_assets]
    theme_read = (
        repository._map_theme(selected_theme, project.selected_theme_id)
        if selected_theme
        else None
    )
    rhythm_mode = resolve_rhythm_mode(project.platform, project.video_type)
    rhythm_profile_json = json.dumps(
        build_rhythm_profile(project, asset_reads, theme_read),
        ensure_ascii=False,
    )
    attention_beats_json = json.dumps(
        build_attention_beats(project, rhythm_mode),
        ensure_ascii=False,
    )
    beat_calibration_json = json.dumps(
        {
            "source": "audio_upload",
            "beatOffsetSec": 0,
            "densityMode": rhythm["beat_mode"],
            "referenceBeatPoints": [],
        },
        ensure_ascii=False,
    )
    _upsert_rhythm(
        session,
        RhythmPlanEntity(
            id=rhythm["id"],
            project_id=SEED_PROJECT_ID,
            bgm_style=rhythm["bgm_style"],
            selected_track_name=rhythm["selected_track_name"],
            audio_file_name=rhythm.get("audio_file_name", ""),
            audio_file_path=audio_file_path,
            analysis_source=rhythm.get("analysis_source", "manual"),
            analysis_notes=rhythm.get("analysis_notes", "[]"),
            detected_bpm=rhythm.get("detected_bpm", 0),
            audio_duration_sec=rhythm.get("audio_duration_sec", 0.0),
            raw_beat_points=rhythm.get("raw_beat_points", "[]"),
            coarse_beat_points=rhythm.get("coarse_beat_points", "[]"),
            beat_mode=rhythm["beat_mode"],
            beat_points=rhythm["beat_points"],
            rhythm_notes=rhythm["rhythm_notes"],
            dark_cut_suggestions=rhythm["dark_cut_suggestions"],
            photo_motion_suggestions=rhythm["photo_motion_suggestions"],
            recommended_bgm=rhythm.get("recommended_bgm", "[]"),
            selected_bgm_id=rhythm.get("selected_bgm_id", ""),
            bgm_phase=rhythm.get("bgm_phase", "empty"),
            rhythm_profile_json=rhythm_profile_json,
            attention_beats_json=attention_beats_json,
            beat_calibration_json=beat_calibration_json,
            audio_fingerprint=f"{rhythm.get('audio_file_name', '')}:{rhythm.get('audio_duration_sec', 0)}:{rhythm.get('detected_bpm', 0)}",
            audio_analysis_version="seed",
        ),
    )

    publish = snapshot["publish"]
    _upsert_publish_plan(
        session,
        PublishPlanEntity(
            id=publish["id"],
            project_id=SEED_PROJECT_ID,
            title=publish["title"],
            short_title=publish["short_title"],
            description=publish["description"],
            tags=publish["tags"],
            cover_suggestion=publish["cover_suggestion"],
            voiceover_script=publish.get("voiceover_script", ""),
            voiceover_provider=publish.get("voiceover_provider", ""),
            voiceover_style=publish.get("voiceover_style", "natural"),
            voiceover_speed=publish.get("voiceover_speed", 1.0),
            voiceover_emotion=publish.get("voiceover_emotion", "calm"),
            voiceover_generation_status=publish.get("voiceover_generation_status", "not_generated"),
            voiceover_audio_path=publish.get("voiceover_audio_path", ""),
            voiceover_duration_sec=publish.get("voiceover_duration_sec", 0.0),
            voiceover_provider_meta=publish.get("voiceover_provider_meta", "{}"),
            voiceover_generated_at=publish.get("voiceover_generated_at", ""),
        ),
    )

    stale_assets = session.exec(
        select(AssetEntity).where(
            AssetEntity.project_id == SEED_PROJECT_ID,
            AssetEntity.asset_id.not_in(seed_asset_ids),
        )
    ).all()
    for asset in stale_assets:
        session.delete(asset)

    session.commit()


def _upsert_asset(session: Session, payload: AssetEntity) -> None:
    current = session.get(AssetEntity, payload.asset_id)
    if current:
        current.project_id = payload.project_id
        current.location = payload.location
        current.scene = payload.scene
        current.relative_path = payload.relative_path
        current.media_type = payload.media_type
        current.shot_type = payload.shot_type
        current.emotion_tags = payload.emotion_tags
        current.visual_tags = payload.visual_tags
        current.information_density = payload.information_density
        current.suggested_duration_sec = payload.suggested_duration_sec
        current.function_tags = payload.function_tags
        current.vision_analysis_json = payload.vision_analysis_json
        current.vision_analysis_status = payload.vision_analysis_status
        session.add(current)
        return
    session.add(payload)


def _upsert_theme(session: Session, payload: ThemeEntity) -> None:
    current = session.get(ThemeEntity, payload.id)
    if current:
        current.project_id = payload.project_id
        current.title = payload.title
        current.summary = payload.summary
        current.core_emotion = payload.core_emotion
        current.rhythm_profile = payload.rhythm_profile
        current.platform_reason = payload.platform_reason
        current.used_locations = payload.used_locations
        current.used_asset_ids = payload.used_asset_ids
        session.add(current)
        return
    session.add(payload)


def _upsert_storyboard(session: Session, payload: StoryboardSegmentEntity) -> None:
    current = session.get(StoryboardSegmentEntity, payload.id)
    if current:
        current.project_id = payload.project_id
        current.theme_id = payload.theme_id
        current.start_time = payload.start_time
        current.end_time = payload.end_time
        current.asset_id = payload.asset_id
        current.shot_description = payload.shot_description
        current.function_name = payload.function_name
        current.rhythm = payload.rhythm
        current.beat_mode = payload.beat_mode
        current.beat_points = payload.beat_points
        current.subtitle = payload.subtitle
        session.add(current)
        return
    session.add(payload)


def _upsert_rhythm(session: Session, payload: RhythmPlanEntity) -> None:
    current = session.get(RhythmPlanEntity, payload.id)
    if current:
        current.project_id = payload.project_id
        current.bgm_style = payload.bgm_style
        current.selected_track_name = payload.selected_track_name
        current.audio_file_name = payload.audio_file_name
        current.audio_file_path = payload.audio_file_path
        current.analysis_source = payload.analysis_source
        current.analysis_notes = payload.analysis_notes
        current.detected_bpm = payload.detected_bpm
        current.audio_duration_sec = payload.audio_duration_sec
        current.raw_beat_points = payload.raw_beat_points
        current.coarse_beat_points = payload.coarse_beat_points
        current.beat_mode = payload.beat_mode
        current.beat_points = payload.beat_points
        current.rhythm_notes = payload.rhythm_notes
        current.dark_cut_suggestions = payload.dark_cut_suggestions
        current.photo_motion_suggestions = payload.photo_motion_suggestions
        current.recommended_bgm = getattr(payload, "recommended_bgm", "[]") or "[]"
        current.selected_bgm_id = getattr(payload, "selected_bgm_id", "") or ""
        current.bgm_phase = getattr(payload, "bgm_phase", "empty") or "empty"
        current.rhythm_profile_json = getattr(payload, "rhythm_profile_json", "{}") or "{}"
        current.attention_beats_json = getattr(payload, "attention_beats_json", "[]") or "[]"
        current.beat_calibration_json = getattr(payload, "beat_calibration_json", "{}") or "{}"
        current.audio_fingerprint = getattr(payload, "audio_fingerprint", "") or ""
        current.audio_analysis_version = getattr(payload, "audio_analysis_version", "") or ""
        session.add(current)
        return
    session.add(payload)


def _upsert_publish_plan(session: Session, payload: PublishPlanEntity) -> None:
    current = session.get(PublishPlanEntity, payload.id)
    if current:
        current.project_id = payload.project_id
        current.title = payload.title
        current.short_title = payload.short_title
        current.description = payload.description
        current.tags = payload.tags
        current.cover_suggestion = payload.cover_suggestion
        current.voiceover_script = getattr(payload, "voiceover_script", "") or ""
        current.voiceover_provider = getattr(payload, "voiceover_provider", "") or ""
        current.voiceover_style = getattr(payload, "voiceover_style", "natural") or "natural"
        current.voiceover_speed = getattr(payload, "voiceover_speed", 1.0) or 1.0
        current.voiceover_emotion = getattr(payload, "voiceover_emotion", "calm") or "calm"
        current.voiceover_generation_status = (
            getattr(payload, "voiceover_generation_status", "not_generated") or "not_generated"
        )
        current.voiceover_audio_path = getattr(payload, "voiceover_audio_path", "") or ""
        current.voiceover_duration_sec = getattr(payload, "voiceover_duration_sec", 0.0) or 0.0
        current.voiceover_provider_meta = getattr(payload, "voiceover_provider_meta", "{}") or "{}"
        current.voiceover_generated_at = getattr(payload, "voiceover_generated_at", "") or ""
        session.add(current)
        return
    session.add(payload)
