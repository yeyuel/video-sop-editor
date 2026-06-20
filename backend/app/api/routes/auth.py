from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db import get_session
from app.models.schemas import ApiResponse, AuthLoginRequest
from app.services.repository import repository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse)
def login(payload: AuthLoginRequest, session: Session = Depends(get_session)) -> ApiResponse:
    user = repository.authenticate_user(session, payload.username.strip(), payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码不正确，或当前账号暂未开放登录",
        )
    return ApiResponse(data=user)
