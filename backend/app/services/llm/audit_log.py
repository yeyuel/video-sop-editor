from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Session, select

from app.models.entities import LlmCallLogEntity
from app.models.schemas import LlmCallLogRead


def record_llm_call(
    session: Session,
    *,
    user_id: str,
    endpoint: str,
    provider_id: str = "",
    model: str = "",
    status: str,
    token_estimate: int = 0,
    message: str = "",
) -> None:
    session.add(
        LlmCallLogEntity(
            id=f"llm_log_{uuid4().hex[:10]}",
            user_id=user_id,
            endpoint=endpoint.strip(),
            provider_id=provider_id.strip(),
            model=model.strip(),
            status=status.strip() or "unknown",
            token_estimate=max(int(token_estimate), 0),
            message=message.strip(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    )
    session.commit()


def record_llm_call_from_meta(
    session: Session,
    *,
    user_id: str,
    endpoint: str,
    llm_meta: dict[str, str] | None,
) -> None:
    meta = llm_meta or {}
    status = meta.get("llmStatus", "unknown")
    if status in {"", "ok", "success"}:
        normalized = "ok"
    elif status in {"rule_fallback", "fallback"}:
        normalized = "fallback"
    else:
        normalized = status

    record_llm_call(
        session,
        user_id=user_id,
        endpoint=endpoint,
        provider_id=meta.get("llmProviderId", meta.get("providerId", "")),
        model=meta.get("llmModel", meta.get("model", "")),
        status=normalized,
        token_estimate=int(meta.get("llmTokenEstimate", "0") or 0),
        message=meta.get("llmMessage", ""),
    )


def list_recent_llm_calls(session: Session, *, limit: int = 50) -> list[LlmCallLogRead]:
    capped = max(1, min(int(limit), 200))
    rows = session.exec(
        select(LlmCallLogEntity)
        .order_by(LlmCallLogEntity.created_at.desc())
        .limit(capped)
    ).all()
    return [
        LlmCallLogRead(
            id=row.id,
            userId=row.user_id,
            endpoint=row.endpoint,
            providerId=row.provider_id,
            model=row.model,
            status=row.status,
            tokenEstimate=row.token_estimate,
            message=row.message,
            createdAt=row.created_at,
        )
        for row in rows
    ]
