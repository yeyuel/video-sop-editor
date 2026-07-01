from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.services.llm.oauth.modes import OAUTH_MODE_CODEX, OAUTH_MODE_GEMINI_SUBSCRIPTION
from app.services.llm.subscription_oauth.constants import (
    CODEX_AUTHORIZE_URL,
    CODEX_CLIENT_ID,
    CODEX_LOOPBACK_PORT,
    CODEX_ORIGINATOR,
    CODEX_REDIRECT_URI,
    CODEX_SCOPES,
    CODEX_TOKEN_URL,
    GEMINI_AUTHORIZE_URL,
    GEMINI_SCOPES,
    GEMINI_TOKEN_URL,
)


@dataclass(frozen=True)
class SubscriptionOAuthAdapter:
    provider_id: str
    oauth_mode: str
    authorize_url: str
    token_url: str
    client_id: str
    client_secret: str
    scopes: str
    redirect_uri: str
    loopback_port: int = 0


def subscription_mock_enabled() -> bool:
    return settings.llm_oauth_mock


def get_codex_adapter() -> SubscriptionOAuthAdapter:
    return SubscriptionOAuthAdapter(
        provider_id="openai",
        oauth_mode=OAUTH_MODE_CODEX,
        authorize_url=CODEX_AUTHORIZE_URL,
        token_url=CODEX_TOKEN_URL,
        client_id=CODEX_CLIENT_ID,
        client_secret="",
        scopes=CODEX_SCOPES,
        redirect_uri=CODEX_REDIRECT_URI,
        loopback_port=CODEX_LOOPBACK_PORT,
    )


def get_gemini_subscription_adapter(*, redirect_uri: str, loopback_port: int) -> SubscriptionOAuthAdapter:
    client_id = settings.google_oauth_client_id.strip()
    client_secret = settings.google_oauth_client_secret.strip()
    return SubscriptionOAuthAdapter(
        provider_id="google",
        oauth_mode=OAUTH_MODE_GEMINI_SUBSCRIPTION,
        authorize_url=GEMINI_AUTHORIZE_URL,
        token_url=GEMINI_TOKEN_URL,
        client_id=client_id,
        client_secret=client_secret,
        scopes=GEMINI_SCOPES,
        redirect_uri=redirect_uri,
        loopback_port=loopback_port,
    )


def get_subscription_adapter(auth_type: str, *, redirect_uri: str = "", loopback_port: int = 0) -> SubscriptionOAuthAdapter | None:
    if auth_type == "codex_oauth":
        return get_codex_adapter()
    if auth_type == "gemini_subscription":
        if not redirect_uri or not loopback_port:
            return None
        return get_gemini_subscription_adapter(redirect_uri=redirect_uri, loopback_port=loopback_port)
    return None
