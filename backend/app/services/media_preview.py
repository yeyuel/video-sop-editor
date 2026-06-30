from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.runtime.shutdown import is_shutting_down
from app.services.file_fingerprint import source_file_fingerprint as _source_fingerprint
from app.services.subprocess_runner import run_command
from app.services.video_frames import VideoFrameError, _require_ffmpeg


class MediaPreviewError(Exception):
    pass


@dataclass
class PreviewBuildResult:
    path: Path
    cached: bool
    mode: str


_build_lock_guard = threading.Lock()
_build_locks: dict[str, threading.Lock] = {}


def _build_lock(key: str) -> threading.Lock:
    with _build_lock_guard:
        lock = _build_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _build_locks[key] = lock
        return lock


def _temp_part_path(final_path: Path) -> Path:
    """Temp file for atomic rename; suffix must stay a normal media extension for ffmpeg."""
    return final_path.parent / f"{final_path.stem}.tmp{final_path.suffix}"


def preview_cache_dir(project_id: str) -> Path:
    return Path(settings.storage_dir) / "media-preview-cache" / project_id


def fast_preview_cache_path(project_id: str, source: Path) -> Path:
    return preview_cache_dir(project_id) / f"{_source_fingerprint(source)}.preview.mp4"


def poster_cache_path(project_id: str, source: Path) -> Path:
    return preview_cache_dir(project_id) / f"{_source_fingerprint(source)}.poster.jpg"


def ensure_fast_preview_video(project_id: str, source: Path) -> PreviewBuildResult:
    if not source.is_file():
        raise MediaPreviewError("源文件不存在。")

    cache_path = fast_preview_cache_path(project_id, source)
    if cache_path.is_file() and cache_path.stat().st_size > 0:
        return PreviewBuildResult(path=cache_path, cached=True, mode="fast")

    lock_key = f"{project_id}:{_source_fingerprint(source)}:preview"
    with _build_lock(lock_key):
        if cache_path.is_file() and cache_path.stat().st_size > 0:
            return PreviewBuildResult(path=cache_path, cached=True, mode="fast")

        ffmpeg_path = _require_ffmpeg()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = _temp_part_path(cache_path)

        max_width = max(640, int(settings.media_preview_max_width))
        crf = max(23, min(int(settings.media_preview_crf), 36))

        # 低码率 H.264 + faststart：牺牲画质/音频，换首帧与拖动加载速度
        command = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            f"scale='min({max_width},iw)':-2",
            "-c:v",
            "libx264",
            "-preset",
            settings.media_preview_preset,
            "-crf",
            str(crf),
            "-movflags",
            "+faststart",
            "-an",
            str(temp_path),
        ]

        result = run_command(command)
        if is_shutting_down():
            temp_path.unlink(missing_ok=True)
            raise MediaPreviewError("服务正在关闭，预览转码已取消。")
        if result.returncode != 0 or not temp_path.is_file():
            temp_path.unlink(missing_ok=True)
            detail = (result.stderr or "").strip()[:240]
            raise MediaPreviewError(f"快速预览转码失败。{detail}")

        temp_path.replace(cache_path)
        return PreviewBuildResult(path=cache_path, cached=False, mode="fast")


def ensure_poster_image(project_id: str, source: Path) -> PreviewBuildResult:
    if not source.is_file():
        raise MediaPreviewError("源文件不存在。")

    cache_path = poster_cache_path(project_id, source)
    if cache_path.is_file() and cache_path.stat().st_size > 0:
        return PreviewBuildResult(path=cache_path, cached=True, mode="poster")

    lock_key = f"{project_id}:{_source_fingerprint(source)}:poster"
    with _build_lock(lock_key):
        if cache_path.is_file() and cache_path.stat().st_size > 0:
            return PreviewBuildResult(path=cache_path, cached=True, mode="poster")

        ffmpeg_path = _require_ffmpeg()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = _temp_part_path(cache_path)

        command = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            "0.5",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-q:v",
            "4",
            str(temp_path),
        ]
        result = run_command(command)
        if is_shutting_down():
            temp_path.unlink(missing_ok=True)
            raise MediaPreviewError("服务正在关闭，预览转码已取消。")
        if result.returncode != 0 or not temp_path.is_file():
            temp_path.unlink(missing_ok=True)
            detail = (result.stderr or "").strip()[:240]
            raise MediaPreviewError(f"封面抽帧失败。{detail}")

        temp_path.replace(cache_path)
        return PreviewBuildResult(path=cache_path, cached=False, mode="poster")


def resolve_preview_file(
    project_id: str,
    source: Path,
    *,
    quality: str = "fast",
) -> PreviewBuildResult:
    normalized = quality.strip().lower()
    if normalized == "original":
        return PreviewBuildResult(path=source, cached=True, mode="original")

    if normalized != "fast":
        raise MediaPreviewError("不支持的预览质量参数。")

    try:
        return ensure_fast_preview_video(project_id, source)
    except VideoFrameError as exc:
        raise MediaPreviewError(str(exc)) from exc
