from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session

from app import db
from app.services.repository import repository


def get_project_media_root(project_id: str) -> str:
    with Session(db.engine) as session:
        project = repository.get_project(session, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project.mediaRoot


def get_project_media_scan_context(project_id: str) -> tuple[str, set[str]]:
    with Session(db.engine) as session:
        project = repository.get_project(session, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        assets = repository.list_assets(session, project_id)
        existing_paths = {item.relativePath for item in assets if item.relativePath.strip()}
        return project.mediaRoot, existing_paths
