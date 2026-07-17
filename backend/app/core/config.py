from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="video-sop-editor-api", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    database_url: str = Field(default="sqlite:///./video_sop.db", alias="DATABASE_URL")
    sqlite_busy_timeout_ms: int = Field(default=5000, alias="SQLITE_BUSY_TIMEOUT_MS")
    storage_dir: str = Field(default="./storage", alias="STORAGE_DIR")
    cors_origins: list[str] = Field(
        default=["http://127.0.0.1:3000", "http://localhost:3000"],
        alias="CORS_ORIGINS",
    )
    llm_provider: str = Field(
        default="openai-compatible",
        alias="LLM_PROVIDER",
        validation_alias=AliasChoices("LLM_PROVIDER", "OPENAI_PROVIDER"),
    )
    llm_api_key: str = Field(
        default="",
        alias="LLM_API_KEY",
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"),
    )
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        alias="LLM_BASE_URL",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    llm_model: str = Field(
        default="gpt-4.1-mini",
        alias="LLM_MODEL",
        validation_alias=AliasChoices("LLM_MODEL", "OPENAI_MODEL"),
    )
    llm_timeout_sec: int = Field(
        default=120,
        alias="LLM_TIMEOUT_SEC",
        validation_alias=AliasChoices("LLM_TIMEOUT_SEC", "OPENAI_TIMEOUT_SEC"),
    )
    llm_max_retries: int = Field(
        default=0,
        alias="LLM_MAX_RETRIES",
        validation_alias=AliasChoices("LLM_MAX_RETRIES", "OPENAI_MAX_RETRIES"),
    )
    app_secret_key: str = Field(default="", alias="APP_SECRET_KEY")
    vision_frame_interval_sec: float = Field(default=2.0, alias="VISION_FRAME_INTERVAL_SEC")
    vision_max_frames: int = Field(default=6, alias="VISION_MAX_FRAMES")
    vision_use_mock: bool = Field(default=False, alias="VISION_USE_MOCK")
    media_preview_max_width: int = Field(default=1280, alias="MEDIA_PREVIEW_MAX_WIDTH")
    media_preview_crf: int = Field(default=28, alias="MEDIA_PREVIEW_CRF")
    media_preview_preset: str = Field(default="ultrafast", alias="MEDIA_PREVIEW_PRESET")
    app_graceful_shutdown_sec: int = Field(default=5, alias="APP_GRACEFUL_SHUTDOWN_SEC")
    llm_oauth_redirect_uri: str = Field(
        default="http://127.0.0.1:3000/settings/llm/oauth/callback",
        alias="LLM_OAUTH_REDIRECT_URI",
    )
    llm_oauth_mock: bool = Field(default=False, alias="LLM_OAUTH_MOCK")
    openai_oauth_client_id: str = Field(default="", alias="OPENAI_OAUTH_CLIENT_ID")
    openai_oauth_client_secret: str = Field(default="", alias="OPENAI_OAUTH_CLIENT_SECRET")
    openai_oauth_authorize_url: str = Field(
        default="https://auth.openai.com/authorize",
        alias="OPENAI_OAUTH_AUTHORIZE_URL",
    )
    openai_oauth_token_url: str = Field(
        default="https://auth.openai.com/oauth/token",
        alias="OPENAI_OAUTH_TOKEN_URL",
    )
    openai_oauth_scopes: str = Field(
        default="openid profile email offline_access",
        alias="OPENAI_OAUTH_SCOPES",
    )
    google_oauth_client_id: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_SECRET")
    google_oauth_authorize_url: str = Field(
        default="https://accounts.google.com/o/oauth2/v2/auth",
        alias="GOOGLE_OAUTH_AUTHORIZE_URL",
    )
    google_oauth_token_url: str = Field(
        default="https://oauth2.googleapis.com/token",
        alias="GOOGLE_OAUTH_TOKEN_URL",
    )
    google_oauth_scopes: str = Field(
        default="openid email https://www.googleapis.com/auth/generative-language",
        alias="GOOGLE_OAUTH_SCOPES",
    )

    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True)

    @property
    def resolved_llm_provider(self) -> str:
        from app.services.llm.provider_ids import normalize_provider_id

        raw = (self.llm_provider or "openai").strip() or "openai"
        return normalize_provider_id(raw)

    @property
    def resolved_llm_oauth_redirect_uri(self) -> str:
        return self.llm_oauth_redirect_uri.strip() or "http://127.0.0.1:3000/settings/llm/oauth/callback"

    @property
    def resolved_llm_api_key(self) -> str:
        if self.llm_api_key.strip():
            return self.llm_api_key.strip()
        return ""

    @property
    def resolved_llm_base_url(self) -> str:
        if self.llm_base_url.strip():
            return self.llm_base_url.strip()
        return "https://api.openai.com/v1"

    @property
    def resolved_llm_model(self) -> str:
        if self.llm_model.strip():
            return self.llm_model.strip()
        return "gpt-4.1-mini"

    @property
    def resolved_llm_timeout_sec(self) -> int:
        return self.llm_timeout_sec or 45

    @property
    def resolved_llm_max_retries(self) -> int:
        return max(0, min(self.llm_max_retries or 1, 5))

    @property
    def resolved_app_secret_key(self) -> str:
        if self.app_secret_key.strip():
            return self.app_secret_key.strip()
        return "video-sop-editor-dev-secret-change-me"


settings = Settings()
