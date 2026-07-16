from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.voiceover_provider import EDGE_VOICES, get_voiceover_voice


class VoiceoverSynthesisError(RuntimeError):
    pass


@dataclass(frozen=True)
class VoiceoverSynthesisResult:
    audio_path: str
    duration_sec: float
    provider_meta: dict[str, Any]


_STYLE_VOICES = {
    "natural": "zh-CN-XiaoxiaoNeural",
    "documentary": "zh-CN-YunjianNeural",
    "guide": "zh-CN-YunxiNeural",
    "energetic": "zh-CN-YunxiNeural",
    "soft": "zh-CN-XiaoxiaoNeural",
}

_EMOTION_VOICES = {
    "curious": "zh-CN-YunxiNeural",
    "excited": "zh-CN-YunxiNeural",
    "nostalgic": "zh-CN-YunjianNeural",
}


def _resolve_voice(style: str, emotion: str, selected_voice: str = "auto") -> tuple[str, str]:
    requested = selected_voice.strip() or "auto"
    configured = get_voiceover_voice("edge", requested)
    if configured and configured.id != "auto":
        return configured.id, configured.label

    resolved = _EMOTION_VOICES.get(emotion) or _STYLE_VOICES.get(
        style, "zh-CN-XiaoxiaoNeural"
    )
    label = next((voice.label for voice in EDGE_VOICES if voice.id == resolved), resolved)
    return resolved, label


def _format_rate(speed: float) -> str:
    safe_speed = max(0.5, min(float(speed or 1.0), 2.0))
    percentage = round((safe_speed - 1.0) * 100)
    return f"{percentage:+d}%"


def _measure_audio_duration(output_path: Path, boundary_duration_sec: float) -> tuple[float, str]:
    try:
        import librosa

        measured_duration = float(librosa.get_duration(path=str(output_path)))
        if measured_duration > 0:
            return round(measured_duration, 3), "audio_file"
    except Exception:
        pass
    return boundary_duration_sec, "speech_boundary"


def _spoken_text_length(text: str) -> int:
    return len(re.sub(r"[^\w\u4e00-\u9fff]", "", text, flags=re.UNICODE))


def _build_caption_timings(
    caption_blocks: list[str],
    word_boundaries: list[dict[str, Any]],
    audio_duration_sec: float,
) -> list[dict[str, Any]]:
    normalized_blocks = [text.strip() for text in caption_blocks if text.strip()]
    if not normalized_blocks:
        return []

    if not word_boundaries:
        total_chars = max(1, sum(_spoken_text_length(text) for text in normalized_blocks))
        cursor = 0.0
        timings: list[dict[str, Any]] = []
        for index, text in enumerate(normalized_blocks):
            share = _spoken_text_length(text) / total_chars
            end = audio_duration_sec if index == len(normalized_blocks) - 1 else cursor + audio_duration_sec * share
            timings.append(
                {
                    "startTime": round(cursor, 3),
                    "endTime": round(max(cursor + 0.1, end), 3),
                    "text": text,
                }
            )
            cursor = end
        return timings

    boundary_index = 0
    timings = []
    for text in normalized_blocks:
        target_chars = max(1, _spoken_text_length(text))
        consumed_chars = 0
        start_time = float(word_boundaries[min(boundary_index, len(word_boundaries) - 1)]["startTime"])
        end_time = start_time
        while boundary_index < len(word_boundaries) and consumed_chars < target_chars:
            boundary = word_boundaries[boundary_index]
            consumed_chars += max(1, _spoken_text_length(str(boundary.get("text", ""))))
            end_time = max(end_time, float(boundary["endTime"]))
            boundary_index += 1
        timings.append(
            {
                "startTime": round(start_time, 3),
                "endTime": round(max(start_time + 0.1, end_time), 3),
                "text": text,
            }
        )
    return timings


async def _stream_edge_audio(
    *,
    script: str,
    voice: str,
    rate: str,
    output_path: Path,
) -> tuple[float, list[dict[str, Any]]]:
    try:
        import edge_tts
    except ImportError as exc:
        raise VoiceoverSynthesisError(
            "Edge TTS 依赖尚未安装，请先执行 pip install -r requirements.txt。"
        ) from exc

    last_boundary_end = 0
    word_boundaries: list[dict[str, Any]] = []
    communicate = edge_tts.Communicate(
        script,
        voice=voice,
        rate=rate,
        boundary="WordBoundary",
    )
    with output_path.open("wb") as audio_file:
        async for chunk in communicate.stream():
            chunk_type = chunk.get("type")
            if chunk_type == "audio":
                audio_file.write(chunk["data"])
            elif chunk_type in {"WordBoundary", "SentenceBoundary"}:
                offset = int(chunk.get("offset", 0))
                duration = int(chunk.get("duration", 0))
                last_boundary_end = max(last_boundary_end, offset + duration)
                if chunk_type == "WordBoundary":
                    word_boundaries.append(
                        {
                            "startTime": round(offset / 10_000_000, 3),
                            "endTime": round((offset + duration) / 10_000_000, 3),
                            "text": str(chunk.get("text", "")),
                        }
                    )

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise VoiceoverSynthesisError("Edge TTS 未返回有效音频，请检查网络后重试。")

    # Edge boundary timestamps use 100-nanosecond units.
    duration_sec = round(last_boundary_end / 10_000_000, 3) if last_boundary_end else 0.0
    return duration_sec, word_boundaries


def synthesize_edge_voiceover(
    *,
    script: str,
    output_dir: Path,
    file_stem: str,
    style: str,
    emotion: str,
    speed: float,
    selected_voice: str = "auto",
    caption_blocks: list[str] | None = None,
) -> VoiceoverSynthesisResult:
    normalized_script = script.strip()
    if not normalized_script:
        raise VoiceoverSynthesisError("口播稿为空，无法生成音频。")

    output_dir.mkdir(parents=True, exist_ok=True)
    generation_id = uuid4().hex[:10]
    output_path = output_dir / f"{file_stem}-{generation_id}-edge-tts.mp3"
    temporary_path = output_dir / f"{file_stem}-{generation_id}-edge-tts.tmp.mp3"
    voice, voice_label = _resolve_voice(style, emotion, selected_voice)
    rate = _format_rate(speed)

    try:
        duration_sec, word_boundaries = asyncio.run(
            _stream_edge_audio(
                script=normalized_script,
                voice=voice,
                rate=rate,
                output_path=temporary_path,
            )
        )
        temporary_path.replace(output_path)
        duration_sec, duration_source = _measure_audio_duration(output_path, duration_sec)
        caption_timings = _build_caption_timings(
            caption_blocks or [normalized_script],
            word_boundaries,
            duration_sec,
        )
    except VoiceoverSynthesisError:
        temporary_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        raise VoiceoverSynthesisError(f"Edge TTS 生成失败：{exc}") from exc

    return VoiceoverSynthesisResult(
        audio_path=str(output_path),
        duration_sec=duration_sec,
        provider_meta={
            "audioKind": "edge_tts_mp3",
            "voice": voice,
            "voiceLabel": voice_label,
            "voiceSelection": selected_voice.strip() or "auto",
            "rate": rate,
            "outputFormat": "mp3",
            "durationSource": duration_source,
            "captionTimings": caption_timings,
            "captionTimingSource": "edge_word_boundary" if word_boundaries else "duration_ratio",
        },
    )
