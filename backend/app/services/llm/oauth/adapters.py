from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class OAuthAdapter:
    provider_id: str
    authorize_url: str
    token_url: str
    client_id: str
    client_secret: str
    scopes: str
    redirect_uri: str


def _redirect_uri() -> str:
    return settings.resolved_llm_oauth_redirect_uri


def get_oauth_adapter(provider_id: str) -> OAuthAdapter | None:
    if provider_id == "openai":
        client_id = settings.openai_oauth_client_id.strip()
        client_secret = settings.openai_oauth_client_secret.strip()
        if not client_id and not settings.llm_oauth_mock:
            return None
        return OAuthAdapter(
            provider_id="openai",
            authorize_url=settings.openai_oauth_authorize_url,
            token_url=settings.openai_oauth_token_url,
            client_id=client_id or "mock-openai-client",
            client_secret=client_secret or "mock-openai-secret",
            scopes=settings.openai_oauth_scopes,
            redirect_uri=_redirect_uri(),
        )

    if provider_id == "google":
        client_id = settings.google_oauth_client_id.strip()
        client_secret = settings.google_oauth_client_secret.strip()
        if not client_id and not settings.llm_oauth_mock:
            return None
        return OAuthAdapter(
            provider_id="google",
            authorize_url=settings.google_oauth_authorize_url,
            token_url=settings.google_oauth_token_url,
            client_id=client_id or "mock-google-client",
            client_secret=client_secret or "mock-google-secret",
            scopes=settings.google_oauth_scopes,
            redirect_uri=_redirect_uri(),
        )

    return None


def oauth_mock_enabled(adapter: OAuthAdapter | None) -> bool:
    if settings.llm_oauth_mock:
        return True
    if not adapter:
        return False
    return adapter.client_id.startswith("mock-")
