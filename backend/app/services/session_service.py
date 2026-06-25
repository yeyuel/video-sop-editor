from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, delete, select

from app.models.entities import AuthSessionEntity, UserEntity

SESSION_TTL = timedelta(hours=8)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_auth_session(db: Session, user_id: str) -> AuthSessionEntity:
    now = _utc_now()
    entity = AuthSessionEntity(
        token=secrets.token_urlsafe(32),
        user_id=user_id,
        created_at=now.isoformat(),
        expires_at=(now + SESSION_TTL).isoformat(),
        revoked=False,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def resolve_auth_session(db: Session, token: str) -> UserEntity | None:
    normalized = token.strip()
    if not normalized:
        return None

    session_entity = db.get(AuthSessionEntity, normalized)
    if not session_entity or session_entity.revoked:
        return None

    expires_at = datetime.fromisoformat(session_entity.expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < _utc_now():
        return None

    user = db.get(UserEntity, session_entity.user_id)
    if not user or not user.ui_enabled:
        return None
    return user


def revoke_auth_session(db: Session, token: str) -> None:
    normalized = token.strip()
    if not normalized:
        return

    session_entity = db.get(AuthSessionEntity, normalized)
    if not session_entity or session_entity.revoked:
        return

    session_entity.revoked = True
    db.add(session_entity)
    db.commit()


def revoke_user_sessions(db: Session, user_id: str) -> None:
    rows = db.exec(select(AuthSessionEntity).where(AuthSessionEntity.user_id == user_id)).all()
    if not rows:
        return
    for row in rows:
        row.revoked = True
        db.add(row)
    db.commit()


def delete_user_sessions(db: Session, user_id: str) -> None:
    db.exec(delete(AuthSessionEntity).where(AuthSessionEntity.user_id == user_id))
    db.commit()
