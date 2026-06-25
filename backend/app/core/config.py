from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="video-sop-editor-api", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    database_url: str = Field(default="sqlite:///./video_sop.db", alias="DATABASE_URL")
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

    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True)

    @property
    def resolved_llm_provider(self) -> str:
        return (self.llm_provider or "openai-compatible").strip() or "openai-compatible"

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
