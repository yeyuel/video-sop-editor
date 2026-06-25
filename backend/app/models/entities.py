from __future__ import annotations

from sqlmodel import Field, SQLModel


class UserEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    username: str = Field(index=True, unique=True)
    display_name: str
    password_hash: str
    role: str
    ui_enabled: bool = True
    created_at: str = ""


class AuthSessionEntity(SQLModel, table=True):
    token: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    created_at: str
    expires_at: str
    revoked: bool = False


class ProjectEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    destination: str
    platform: str
    target_duration_sec: int
    video_type: str
    style_preference: str
    style_notes: str = ""
    route_text: str = ""
    media_root: str = ""
    status: str
    selected_theme_id: str = ""
    validate_location_order: bool = False


class AssetEntity(SQLModel, table=True):
    asset_id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    location: str
    scene: str
    relative_path: str = ""
    media_type: str
    shot_type: str
    emotion_tags: str
    visual_tags: str
    information_density: str
    suggested_duration_sec: float
    function_tags: str


class ThemeEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    title: str
    summary: str
    core_emotion: str
    rhythm_profile: str
    platform_reason: str
    used_locations: str = "[]"
    used_asset_ids: str = "[]"


class StoryboardSegmentEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    theme_id: str = Field(index=True)
    start_time: float
    end_time: float
    asset_id: str = Field(index=True)
    shot_description: str
    function_name: str
    rhythm: str
    beat_mode: str
    beat_points: str
    subtitle: str


class RhythmPlanEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    bgm_style: str
    selected_track_name: str
    audio_file_name: str = ""
    audio_file_path: str = ""
    analysis_source: str = "manual"
    analysis_notes: str = "[]"
    detected_bpm: int = 0
    audio_duration_sec: float = 0.0
    raw_beat_points: str = "[]"
    coarse_beat_points: str = "[]"
    beat_mode: str
    beat_points: str
    rhythm_notes: str
    dark_cut_suggestions: str
    photo_motion_suggestions: str


class PublishPlanEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    title: str
    short_title: str
    description: str
    tags: str
    cover_suggestion: str


class LlmProviderConfigEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    provider_id: str = Field(index=True, unique=True)
    auth_type: str = "api_key"
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    status: str = "not_configured"


class AppSettingEntity(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = ""
