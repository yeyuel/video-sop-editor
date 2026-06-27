from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session

from app.api.deps import extract_session_token, require_authenticated_user, require_director_user
from app.db import get_session
from app.models.schemas import (
    ApiResponse,
    AuthLoginOptionRead,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthUserCreateRequest,
    AuthUserRead,
    AuthUserUpdateRequest,
)
from app.services.repository import repository
from app.services.session_service import create_auth_session, revoke_auth_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login-options", response_model=ApiResponse)
def list_login_options(session: Session = Depends(get_session)) -> ApiResponse:
    return ApiResponse(data=repository.list_login_options(session))


@router.post("/login", response_model=ApiResponse)
def login(payload: AuthLoginRequest, session: Session = Depends(get_session)) -> ApiResponse:
    user = repository.authenticate_user(session, payload.username.strip(), payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码不正确，或当前账号暂未开放登录。如需开通请联系导演。",
        )

    auth_session = create_auth_session(session, user.id)
    return ApiResponse(
        data=AuthLoginResponse(
            user=user,
            sessionToken=auth_session.token,
            expiresAt=auth_session.expires_at,
        )
    )


@router.get("/me", response_model=ApiResponse)
def get_current_user(
    current_user: AuthUserRead = Depends(require_authenticated_user),
) -> ApiResponse:
    return ApiResponse(data=current_user)


@router.post("/logout", response_model=ApiResponse)
def logout(request: Request, session: Session = Depends(get_session)) -> ApiResponse:
    token = extract_session_token(request)
    if token:
        revoke_auth_session(session, token)
    return ApiResponse(data={"ok": True})


@router.get("/users", response_model=ApiResponse)
def list_users(
    session: Session = Depends(get_session),
    _: AuthUserRead = Depends(require_director_user),
) -> ApiResponse:
    return ApiResponse(data=repository.list_users(session))


@router.post("/users", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AuthUserCreateRequest,
    session: Session = Depends(get_session),
    _: AuthUserRead = Depends(require_director_user),
) -> ApiResponse:
    try:
        user = repository.create_user(session, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return ApiResponse(data=user)


@router.put("/users/{user_id}", response_model=ApiResponse)
def update_user(
    user_id: str,
    payload: AuthUserUpdateRequest,
    session: Session = Depends(get_session),
    current_user: AuthUserRead = Depends(require_director_user),
) -> ApiResponse:
    try:
        user = repository.update_user(
            session,
            user_id,
            payload,
            actor_id=current_user.id,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return ApiResponse(data=user)


@router.delete("/users/{user_id}", response_model=ApiResponse)
def delete_user(
    user_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUserRead = Depends(require_director_user),
) -> ApiResponse:
    try:
        repository.delete_user(session, user_id, actor_id=current_user.id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return ApiResponse(data={"ok": True})
