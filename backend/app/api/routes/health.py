from fastapi import APIRouter

from app.models.schemas import ApiResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse)
def healthcheck() -> ApiResponse:
    return ApiResponse(data={"status": "ok"})
