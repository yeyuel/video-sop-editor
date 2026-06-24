from __future__ import annotations

import os
import re

from app.models.entities import ProjectEntity
from app.models.schemas import NarrativeThemeRead


_DEMO_TRACK_SUFFIX = re.compile(r"-demo-track$", re.IGNORECASE)


def resolve_selected_track_name(
    project: ProjectEntity,
    theme: NarrativeThemeRead | None,
    *,
    audio_file_name: str = "",
    existing_name: str = "",
) -> str:
    if audio_file_name.strip():
        return os.path.splitext(os.path.basename(audio_file_name.strip()))[0]

    cleaned_existing = existing_name.strip()
    if cleaned_existing and not _DEMO_TRACK_SUFFIX.search(cleaned_existing):
        return cleaned_existing

    if theme and theme.title.strip():
        return f"{theme.title.strip()}-参考曲"

    if project.name.strip():
        return f"{project.name.strip()}-参考曲"

    return f"{project.id}-参考曲"
