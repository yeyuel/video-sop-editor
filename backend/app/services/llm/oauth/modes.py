from __future__ import annotations

OAUTH_MODE_PLATFORM = "platform"
OAUTH_MODE_CODEX = "codex"
OAUTH_MODE_GEMINI_SUBSCRIPTION = "gemini_subscription"


def auth_type_to_oauth_mode(auth_type: str) -> str:
    if auth_type == "codex_oauth":
        return OAUTH_MODE_CODEX
    if auth_type == "gemini_subscription":
        return OAUTH_MODE_GEMINI_SUBSCRIPTION
    if auth_type == "oauth":
        return OAUTH_MODE_PLATFORM
    return OAUTH_MODE_PLATFORM


def is_subscription_auth_type(auth_type: str) -> bool:
    return auth_type in {"codex_oauth", "gemini_subscription"}


def is_oauth_auth_type(auth_type: str) -> bool:
    return auth_type in {"oauth", "codex_oauth", "gemini_subscription"}
