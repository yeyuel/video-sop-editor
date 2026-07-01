from __future__ import annotations

PROVIDER_ALIASES: dict[str, str] = {
    "openai-compatible": "openai",
}

CANONICAL_PROVIDER_ORDER: list[str] = [
    "openai",
    "google",
    "kimi",
    "deepseek",
    "glm",
]


def normalize_provider_id(provider_id: str) -> str:
    normalized = provider_id.strip().lower()
    if not normalized:
        return normalized
    return PROVIDER_ALIASES.get(normalized, normalized)
