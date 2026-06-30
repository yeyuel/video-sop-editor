from __future__ import annotations

import base64
import shutil
import tempfile
from pathlib import Path

from app.runtime.shutdown import is_shutting_down
from app.services.subprocess_runner import SubprocessInterruptedError, run_command


class VideoFrameError(Exception):
    pass


def _require_ffmpeg() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise VideoFrameError(
            "未检测到 ffmpeg，无法从视频抽帧。请安装 ffmpeg 或将视频转为可访问的本地文件。"
        )
    return ffmpeg_path


def _probe_duration_sec(video_path: Path, ffmpeg_path: str) -> float:
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-f",
        "null",
        "-",
    ]
    result = run_command(command)
    if is_shutting_down():
        raise VideoFrameError("服务正在关闭，视频探测已取消。")
    stderr = result.stderr or ""
    for token in stderr.split():
        if token.startswith("Duration:"):
            raw = token.split(":", 1)[1].rstrip(",")
            hours, minutes, seconds = raw.split(":")
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    return 0.0


def extract_video_frames(
    video_path: Path,
    *,
    interval_sec: float = 2.0,
    max_frames: int = 6,
) -> list[Path]:
    if not video_path.is_file():
        raise VideoFrameError(f"视频文件不存在：{video_path}")

    ffmpeg_path = _require_ffmpeg()
    duration_sec = _probe_duration_sec(video_path, ffmpeg_path)
    if duration_sec <= 0:
        duration_sec = max(interval_sec * max_frames, interval_sec)

    sample_times: list[float] = []
    cursor = 0.0
    while len(sample_times) < max_frames and cursor < duration_sec:
        sample_times.append(min(cursor, max(duration_sec - 0.05, 0)))
        cursor += max(interval_sec, 0.5)

    output_dir = Path(tempfile.mkdtemp(prefix="vision-frames-"))
    frame_paths: list[Path] = []
    for index, timestamp in enumerate(sample_times):
        frame_path = output_dir / f"frame_{index:03d}.jpg"
        command = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(frame_path),
        ]
        result = run_command(command)
        if is_shutting_down():
            raise VideoFrameError("服务正在关闭，抽帧已取消。")
        if result.returncode == 0 and frame_path.is_file():
            frame_paths.append(frame_path)

    if not frame_paths:
        raise VideoFrameError("ffmpeg 未能从视频中抽取有效帧。")
    return frame_paths


def encode_image_base64(image_path: Path) -> str:
    payload = image_path.read_bytes()
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
