from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session

from app import db
from app.models.schemas import AuthUserRead
from app.services.repository import repository
from app.services.session_service import resolve_auth_session

AUTH_SESSION_COOKIE = "travel_edit_session"


def extract_session_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        return token or None

    header_token = request.headers.get("X-Session-Token", "").strip()
    if header_token:
        return header_token

    cookie_token = request.cookies.get(AUTH_SESSION_COOKIE, "").strip()
    if cookie_token:
        return cookie_token

    return None


def require_authenticated_user(request: Request) -> AuthUserRead:
    token = extract_session_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或会话已失效",
        )

    with Session(db.engine) as session:
        user = resolve_auth_session(session, token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录或会话已失效",
            )
        return repository._map_user(user)


def require_project_editor(
    current_user: AuthUserRead = Depends(require_authenticated_user),
) -> AuthUserRead:
    if current_user.role not in {"director", "editor"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号无权执行此操作",
        )
    return current_user


def require_director_user(
    current_user: AuthUserRead = Depends(require_authenticated_user),
) -> AuthUserRead:
    if current_user.role != "director":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号无权执行此操作",
        )
    return current_user
