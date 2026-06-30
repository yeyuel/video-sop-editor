from __future__ import annotations

from pathlib import Path

from app.services.media_preview import _temp_part_path


def test_temp_part_path_keeps_poster_jpg_extension() -> None:
    final_path = Path("storage/media-preview-cache/proj_001/abc.poster.jpg")
    assert _temp_part_path(final_path).name == "abc.poster.tmp.jpg"


def test_temp_part_path_keeps_preview_mp4_extension() -> None:
    final_path = Path("storage/media-preview-cache/proj_001/abc.preview.mp4")
    assert _temp_part_path(final_path).name == "abc.preview.tmp.mp4"
