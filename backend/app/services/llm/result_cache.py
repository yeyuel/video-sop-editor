from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.entities import LlmResultCacheEntity
from app.services.llm.types import ResolvedLlmConfig

CACHE_SCHEMA_VERSION = "llm-result-v1"


def build_llm_input_fingerprint(
    *,
    config: ResolvedLlmConfig,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int | None,
) -> str:
    payload = {
        "version": CACHE_SCHEMA_VERSION,
        "providerId": config.provider_id,
        "authType": config.auth_type,
        "model": config.model,
        "systemPrompt": system_prompt,
        "userPrompt": user_prompt,
        "temperature": round(float(temperature), 4),
        "maxTokens": max_tokens,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_cached_llm_result(
    session: Session,
    input_fingerprint: str,
) -> dict[str, Any] | None:
    row = session.exec(
        select(LlmResultCacheEntity).where(
            LlmResultCacheEntity.input_fingerprint == input_fingerprint
        )
    ).first()
    if not row:
        return None
    try:
        payload = json.loads(row.response_json)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    row.hit_count += 1
    row.last_hit_at = datetime.now(timezone.utc).isoformat()
    session.add(row)
    session.commit()
    return payload


def store_llm_result(
    session: Session,
    *,
    input_fingerprint: str,
    config: ResolvedLlmConfig,
    payload: dict[str, Any],
) -> None:
    existing = session.exec(
        select(LlmResultCacheEntity).where(
            LlmResultCacheEntity.input_fingerprint == input_fingerprint
        )
    ).first()
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        existing.response_json = serialized
        existing.provider_id = config.provider_id
        existing.model = config.model
        session.add(existing)
    else:
        session.add(
            LlmResultCacheEntity(
                id=f"llm_cache_{uuid4().hex[:12]}",
                input_fingerprint=input_fingerprint,
                provider_id=config.provider_id,
                model=config.model,
                response_json=serialized,
                created_at=now,
                last_hit_at="",
            )
        )
    try:
        session.commit()
    except IntegrityError:
        # Another identical request may have populated the unique fingerprint first.
        # Its successful result is equivalent, so cache persistence must not fail the request.
        session.rollback()
