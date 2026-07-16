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


class LlmCallLogEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    endpoint: str = Field(default="")
    provider_id: str = Field(default="")
    model: str = Field(default="")
    status: str = Field(default="")
    token_estimate: int = Field(default=0)
    message: str = Field(default="")
    created_at: str = Field(default="")


class LlmResultCacheEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    input_fingerprint: str = Field(index=True, unique=True)
    provider_id: str = Field(default="", index=True)
    model: str = Field(default="")
    response_json: str = Field(default="{}")
    hit_count: int = Field(default=0)
    created_at: str = Field(default="")
    last_hit_at: str = Field(default="")


class LlmTaskEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    user_id: str = Field(default="", index=True)
    project_id: str = Field(default="", index=True)
    operation: str = Field(default="", index=True)
    status: str = Field(default="queued", index=True)
    stage: str = Field(default="queued")
    message: str = Field(default="")
    detail: str = Field(default="")
    progress: int = Field(default=0)
    result_json: str = Field(default="")
    meta_json: str = Field(default="")
    error_message: str = Field(default="")
    cancel_requested: bool = Field(default=False)
    created_at: str = Field(default="")
    updated_at: str = Field(default="")
    completed_at: str = Field(default="")


class RoughCutVersionEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    label: str = Field(default="")
    generation_mode: str = Field(default="")
    provider_id: str = Field(default="")
    model: str = Field(default="")
    snapshot_json: str = Field(default="{}")
    created_at: str = Field(default="")


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
    jianying_draft_root: str = ""
    status: str
    selected_theme_id: str = ""
    validate_location_order: bool = False
    allow_asset_reuse: bool = False
    duration_fill_max_consecutive_route: int = 2


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
    vision_analysis_json: str = ""
    vision_analysis_status: str = "empty"


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
    attention_role: str = ""
    visual_strength: str = ""
    motion_policy: str = ""
    transition_policy: str = ""
    subtitle_policy: str = ""
    selection_trace: str = ""
    voiceover_text: str = ""
    voiceover_role: str = ""
    voiceover_timing: str = ""


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
    recommended_bgm: str = "[]"
    selected_bgm_id: str = ""
    bgm_phase: str = "empty"
    rhythm_profile_json: str = "{}"
    attention_beats_json: str = "[]"
    beat_calibration_json: str = "{}"
    audio_fingerprint: str = ""
    audio_analysis_version: str = ""


class PublishPlanEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    title: str
    short_title: str
    description: str
    tags: str
    cover_suggestion: str
    voiceover_script: str = ""
    voiceover_provider: str = ""
    voiceover_voice: str = "auto"
    voiceover_style: str = "natural"
    voiceover_speed: float = 1.0
    voiceover_emotion: str = "calm"
    voiceover_density: str = "standard"
    voiceover_generation_status: str = "not_generated"
    voiceover_audio_path: str = ""
    voiceover_duration_sec: float = 0.0
    voiceover_provider_meta: str = "{}"
    voiceover_generated_at: str = ""


class LlmProviderConfigEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    provider_id: str = Field(index=True, unique=True)
    auth_type: str = "api_key"
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    status: str = "not_configured"


class LlmOAuthPendingEntity(SQLModel, table=True):
    state: str = Field(primary_key=True)
    provider_id: str = Field(index=True)
    user_id: str = Field(index=True)
    code_verifier: str = ""
    redirect_uri: str = ""
    oauth_mode: str = "platform"
    loopback_port: int = 0
    flow_status: str = "pending"
    error_message: str = ""
    created_at: str = ""
    expires_at: str = ""


class LlmOAuthTokenEntity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    provider_id: str = Field(index=True)
    oauth_mode: str = Field(default="platform", index=True)
    user_id: str = Field(index=True)
    access_token: str = ""
    refresh_token: str = ""
    id_token: str = ""
    account_id: str = ""
    project_id: str = ""
    expires_at: str = ""
    scopes: str = ""
    status: str = "authorized"
    updated_at: str = ""


class AppSettingEntity(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = ""
