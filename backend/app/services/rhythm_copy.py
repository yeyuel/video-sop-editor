from __future__ import annotations

import json

from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead, NarrativeThemeRead
from app.services.beat_grid import capcut_beat_mode_label
from app.services.llm import llm_suggestion_service


def build_llm_rhythm_copy(
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
    *,
    bpm: int,
    beat_mode: str,
    beat_point_count: int,
    analysis_source: str,
    bgm_style_fallback: str,
) -> tuple[str, list[str]] | None:
    if not llm_suggestion_service.enabled:
        return None

    payload = llm_suggestion_service.generate_json(
        system_prompt=(
            "You are a travel short-video rhythm director. "
            "Return JSON only with keys bgmStyle (string) and rhythmNotes (array of 3-5 short Chinese strings). "
            "Each rhythm note must be actionable for editing: mention timing, beat usage, or emotional pacing."
        ),
        user_prompt=json.dumps(
            {
                "project": {
                    "name": project.name,
                    "destination": project.destination,
                    "platform": project.platform,
                    "videoType": project.video_type,
                    "targetDurationSec": project.target_duration_sec,
                    "stylePreference": project.style_preference,
                    "styleNotes": project.style_notes,
                },
                "theme": theme.model_dump() if theme else None,
                "assetsSummary": [
                    {
                        "assetId": asset.assetId,
                        "scene": asset.scene,
                        "location": asset.location,
                        "mediaType": asset.mediaType,
                    }
                    for asset in assets[:8]
                ],
                "rhythmContext": {
                    "analysisSource": analysis_source,
                    "bpm": bpm,
                    "beatMode": beat_mode,
                    "beatModeLabel": capcut_beat_mode_label(beat_mode),
                    "beatPointCount": beat_point_count,
                    "bgmStyleFallback": bgm_style_fallback,
                },
            },
            ensure_ascii=False,
        ),
        temperature=0.55,
    )
    if not payload:
        return None

    bgm_style = str(payload.get("bgmStyle", "")).strip()
    rhythm_notes_raw = payload.get("rhythmNotes")
    if not bgm_style or not isinstance(rhythm_notes_raw, list):
        return None

    rhythm_notes = [str(item).strip() for item in rhythm_notes_raw if str(item).strip()]
    if len(rhythm_notes) < 2:
        return None

    return bgm_style, rhythm_notes


def resolve_rhythm_copy(
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
    *,
    bpm: int,
    beat_mode: str,
    beat_point_count: int,
    analysis_source: str,
    bgm_style_fallback: str,
    rhythm_notes_fallback: list[str],
) -> tuple[str, list[str]]:
    llm_copy = build_llm_rhythm_copy(
        project,
        assets,
        theme,
        bpm=bpm,
        beat_mode=beat_mode,
        beat_point_count=beat_point_count,
        analysis_source=analysis_source,
        bgm_style_fallback=bgm_style_fallback,
    )
    if llm_copy:
        return llm_copy

    return bgm_style_fallback, rhythm_notes_fallback
