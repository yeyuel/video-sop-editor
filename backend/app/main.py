from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.llm import router as llm_router
from app.api.routes.auth import router as auth_router
from app.api.routes.assets import router as assets_router
from app.api.routes.exports import router as exports_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.api.routes.publish import router as publish_router
from app.api.routes.rhythm import router as rhythm_router
from app.api.routes.storyboard import router as storyboard_router
from app.api.routes.themes import router as themes_router
from app.core.config import settings
from app.db import create_db_and_tables, engine
from app.migrations import run_sqlite_migrations
from app.services.seed import seed_demo_data
from sqlmodel import Session


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    run_sqlite_migrations()
    with Session(engine) as session:
        seed_demo_data(session)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api/v1"


app.include_router(llm_router, prefix=api_prefix)
app.include_router(health_router, prefix=api_prefix)
app.include_router(auth_router, prefix=api_prefix)
app.include_router(projects_router, prefix=api_prefix)
app.include_router(assets_router, prefix=api_prefix)
app.include_router(themes_router, prefix=api_prefix)
app.include_router(storyboard_router, prefix=api_prefix)
app.include_router(rhythm_router, prefix=api_prefix)
app.include_router(publish_router, prefix=api_prefix)
app.include_router(exports_router, prefix=api_prefix)
