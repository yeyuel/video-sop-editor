from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.models.schemas import AssetRead, WorkspaceDataRead
from app.services.rough_cut_export import resolve_clip_path

DEFAULT_CAPCUT_FPS = 30
JIANYING_PLATFORM = {
    "app_source": "lv",
    "app_version": "5.9.0",
    "os": "windows",
}
DRAFT_FILE_NAMES = ("draft_content.json", "draft_meta_info.json")

# JianYing renders imported text larger than the raw size suggests.
DEFAULT_CAPTION_FONT_SIZE = 15.0
CAPTION_FONT_SIZE = DEFAULT_CAPTION_FONT_SIZE * 0.4
MAX_CAPTION_FONT_SIZE = 6.6
MIN_CAPTION_FONT_SIZE = 4.2

# JianYing built-in font metadata (pyJianYingDraft FontType.悠然体 / EffectMeta).
# EffectMeta(resource_id, effect_id): content.styles[].font.id uses resource_id.
JIANYING_FONT_YOURAN = {
    "name": "悠然体",
    "resource_id": "6740436145831678467",
    "effect_id": "349311",
    "md5": "7f7454ea269cfebfef1b104673f05894",
    "path": "D:",
}

DEFAULT_BGM_FADE_OUT_SEC = 1.0
DEFAULT_BGM_FADE_IN_SEC = 0.4
DEFAULT_BGM_VOLUME = 0.8
DUCKED_BGM_VOLUME = 0.35

JIANYING_DISSOLVE_TRANSITION = {
    "name": "叠化",
    "effect_id": "322577",
    "resource_id": "6724845717472416269",
    "is_overlap": True,
}


def default_jianying_draft_root() -> str:
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_app_data:
        return ""
    return str(
        Path(local_app_data)
        / "JianyingPro"
        / "User Data"
        / "Projects"
        / "com.lveditor.draft"
    )


def resolve_jianying_draft_root(configured_root: str) -> str:
    configured = configured_root.strip()
    if configured:
        return str(Path(configured).expanduser())
    return default_jianying_draft_root()


def seconds_to_microseconds(seconds: float) -> int:
    return max(0, int(round(max(0.0, seconds) * 1_000_000)))


def sanitize_draft_folder_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned[:120] or "video-sop-draft"


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def text_style_range(text: str) -> list[int]:
    """JianYing 5.9 (`app_source: lv`) uses character indices in content.styles.range."""
    return [0, len(text)]


def build_text_content(
    text: str,
    *,
    font_size: float = CAPTION_FONT_SIZE,
    alpha: float = 1.0,
    bold: bool = False,
) -> str:
    clamped_alpha = min(1.0, max(0.0, alpha))
    payload = {
        "styles": [
            {
                "fill": {
                    "alpha": clamped_alpha,
                    "content": {
                        "render_type": "solid",
                        "solid": {"alpha": clamped_alpha, "color": [1, 1, 1]},
                    },
                },
                "range": text_style_range(text),
                "size": font_size,
                "bold": bold,
                "italic": False,
                "underline": False,
                "strokes": [],
                "font": {
                    "id": JIANYING_FONT_YOURAN["resource_id"],
                    "path": JIANYING_FONT_YOURAN["path"],
                },
            }
        ],
        "text": text,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def fit_caption_font_size(text: str, requested_size: float) -> float:
    visible_chars = len(re.sub(r"\s+", "", text))
    safe_size = min(MAX_CAPTION_FONT_SIZE, max(MIN_CAPTION_FONT_SIZE, requested_size))
    if visible_chars > 32:
        safe_size *= 0.7
    elif visible_chars > 24:
        safe_size *= 0.78
    elif visible_chars > 18:
        safe_size *= 0.88
    return round(max(MIN_CAPTION_FONT_SIZE, safe_size), 2)


def _default_clip() -> dict[str, Any]:
    return {
        "alpha": 1,
        "rotation": 0,
        "scale": {"x": 1, "y": 1},
        "transform": {"x": 0, "y": 0},
        "flip": {"horizontal": False, "vertical": False},
    }


def _caption_clip() -> dict[str, Any]:
    clip = _default_clip()
    clip["transform"] = {"x": 0, "y": -0.68}
    return clip


def _create_companion_materials(track_type: str) -> tuple[list[str], dict[str, list[dict[str, Any]]]]:
    speed_id = _new_id("speed")
    placeholder_id = _new_id("placeholder")
    scm_id = _new_id("scm")
    vocal_id = _new_id("vocal")

    materials: dict[str, list[dict[str, Any]]] = {
        "speeds": [
            {
                "id": speed_id,
                "type": "speed",
                "speed": 1,
                "mode": 0,
                "curve_speed": None,
            }
        ],
        "placeholder_infos": [
            {
                "id": placeholder_id,
                "type": "placeholder_info",
                "error_path": "",
                "error_text": "",
                "meta_type": "none",
                "res_path": "",
                "res_text": "",
            }
        ],
        "sound_channel_mappings": [
            {
                "id": scm_id,
                "type": "none",
                "audio_channel_mapping": 0,
                "is_config_open": False,
            }
        ],
        "vocal_separations": [
            {
                "id": vocal_id,
                "type": "vocal_separation",
                "choice": 0,
                "enter_from": "",
                "final_algorithm": "",
                "production_path": "",
                "removed_sounds": [],
                "time_range": None,
            }
        ],
    }
    refs = [speed_id, placeholder_id, scm_id, vocal_id]

    if track_type in {"video", "text"}:
        canvas_id = _new_id("canvas")
        color_id = _new_id("color")
        materials["canvases"] = [
            {
                "id": canvas_id,
                "type": "canvas_color",
                "album_image": "",
                "blur": 0,
                "color": "",
                "image": "",
                "image_id": "",
                "image_name": "",
                "source_platform": 0,
                "team_id": "",
            }
        ]
        materials["material_colors"] = [
            {
                "id": color_id,
                "type": "material_color",
                "gradient_angle": 90,
                "gradient_colors": [],
                "gradient_percents": [],
                "height": 0,
                "is_color_clip": False,
                "is_gradient": False,
                "solid_color": "",
                "width": 0,
            }
        ]
        refs.extend([canvas_id, color_id])

    return refs, materials


def _merge_materials(
    target: dict[str, list[dict[str, Any]]],
    incoming: dict[str, list[dict[str, Any]]],
) -> None:
    for key, items in incoming.items():
        target.setdefault(key, []).extend(items)


def _base_segment(
    *,
    segment_id: str,
    material_id: str,
    track_id: str,
    start_us: int,
    duration_us: int,
    companion_refs: list[str],
    render_index: int,
    clip: dict[str, Any] | None = None,
    volume: float = 1.0,
    common_keyframes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": segment_id,
        "material_id": material_id,
        "raw_segment_id": track_id,
        "target_timerange": {"start": start_us, "duration": duration_us},
        "source_timerange": {"start": 0, "duration": duration_us},
        "speed": 1,
        "volume": volume,
        "visible": True,
        "reverse": False,
        "clip": clip or _default_clip(),
        "render_index": render_index,
        "track_render_index": 0,
        "track_attribute": 0,
        "extra_material_refs": companion_refs,
        "common_keyframes": common_keyframes or [],
        "keyframe_refs": [],
    }


def _video_material(
    *,
    material_id: str,
    path: str,
    duration_us: int,
    asset: AssetRead | None,
) -> dict[str, Any]:
    filename = path.rsplit("/", 1)[-1] or path.rsplit("\\", 1)[-1] or "clip.mp4"
    media_type = (asset.mediaType if asset else "video").lower()
    material_type = "photo" if media_type == "image" else "video"
    return {
        "id": material_id,
        "path": path.replace("\\", "/"),
        "material_name": filename,
        "type": material_type,
        "duration": duration_us,
        "width": 1920,
        "height": 1080,
        "has_audio": material_type == "video",
        "category_id": "",
        "category_name": "local",
        "check_flag": 7,
        "crop": {
            "lower_left_x": 0,
            "lower_left_y": 1,
            "lower_right_x": 1,
            "lower_right_y": 1,
            "upper_left_x": 0,
            "upper_left_y": 0,
            "upper_right_x": 1,
            "upper_right_y": 0,
        },
        "source_platform": 0,
        "stable": {"matrix_path": "", "stable_level": 0, "time_range": {"duration": 0, "start": 0}},
        "video_algorithm": {
            "algorithms": [],
            "deflicker": None,
            "motion_blur_config": None,
            "noise_reduction": None,
            "path": "",
            "quality_enhance": None,
            "time_range": None,
        },
    }


def _audio_material(
    *,
    material_id: str,
    path: str,
    name: str,
    duration_us: int,
) -> dict[str, Any]:
    return {
        "id": material_id,
        "path": path.replace("\\", "/"),
        "name": name,
        "duration": duration_us,
        "type": "music",
        "music_id": "",
        "category_id": "",
        "category_name": "local",
        "source_platform": 0,
        "wave_points": [],
        "tone_category_id": "",
        "tone_category_name": "",
        "tone_effect_id": "",
        "tone_effect_name": "",
    }


def _text_material(
    *,
    material_id: str,
    text: str,
    alpha: float = 1.0,
    font_size: float = CAPTION_FONT_SIZE,
    bold: bool = False,
) -> dict[str, Any]:
    # Match pyJianYingDraft TextSegment.export_material(): font lives in content JSON.
    clamped_alpha = min(1.0, max(0.0, alpha))
    fitted_font_size = fit_caption_font_size(text, font_size)
    return {
        "id": material_id,
        "type": "text",
        "content": build_text_content(
            text,
            alpha=clamped_alpha,
            font_size=fitted_font_size,
            bold=bold,
        ),
        "alignment": 1,
        "typesetting": 0,
        "letter_spacing": 0.0,
        "line_spacing": 0.02,
        "line_feed": 1,
        "line_max_width": 0.82,
        "force_apply_line_max_width": False,
        "check_flag": 7,
        "global_alpha": clamped_alpha,
    }


def _audio_fade_material(*, fade_id: str, fade_out_us: int, fade_in_us: int = 0) -> dict[str, Any]:
    return {
        "id": fade_id,
        "type": "audio_fade",
        "fade_in_duration": fade_in_us,
        "fade_out_duration": fade_out_us,
        "fade_type": 0,
    }


def _attach_bgm_fade_out(
    materials: dict[str, list[Any]],
    companion_refs: list[str],
    *,
    timeline_duration_us: int,
    fade_out_sec: float = DEFAULT_BGM_FADE_OUT_SEC,
    fade_in_sec: float = DEFAULT_BGM_FADE_IN_SEC,
) -> list[str]:
    if timeline_duration_us <= 0:
        return companion_refs
    fade_out_us = min(
        seconds_to_microseconds(fade_out_sec),
        max(seconds_to_microseconds(0.2), timeline_duration_us // 2),
    )
    fade_in_us = min(
        seconds_to_microseconds(fade_in_sec),
        max(seconds_to_microseconds(0.2), timeline_duration_us // 2),
    )
    fade_id = _new_id("fade")
    materials["audio_fades"].append(
        _audio_fade_material(
            fade_id=fade_id,
            fade_out_us=fade_out_us,
            fade_in_us=fade_in_us,
        )
    )
    return [*companion_refs, fade_id]


def _keyframe_list(property_type: str, points: list[tuple[int, float]]) -> dict[str, Any]:
    return {
        "id": _new_id("keyframe-list"),
        "keyframe_list": [
            {
                "curveType": "Line",
                "graphID": "",
                "left_control": {"x": 0.0, "y": 0.0},
                "right_control": {"x": 0.0, "y": 0.0},
                "id": _new_id("keyframe"),
                "time_offset": offset_us,
                "values": [value],
            }
            for offset_us, value in points
        ],
        "material_id": "",
        "property_type": property_type,
    }


def _motion_keyframes(
    *,
    motion_policy: str,
    media_type: str,
    duration_us: int,
) -> list[dict[str, Any]]:
    if duration_us <= 0 or media_type.lower() not in {"image", "photo"}:
        return []
    if motion_policy == "slow_push":
        start_scale, end_scale = 1.0, 1.12
    elif motion_policy == "gentle_zoom":
        start_scale, end_scale = 1.02, 1.08
    else:
        return []
    return [
        _keyframe_list(
            "UNIFORM_SCALE",
            [(0, start_scale), (duration_us, end_scale)],
        )
    ]


def _transition_material(*, transition_id: str, duration_us: int) -> dict[str, Any]:
    return {
        "category_id": "",
        "category_name": "",
        "duration": duration_us,
        "effect_id": JIANYING_DISSOLVE_TRANSITION["effect_id"],
        "id": transition_id,
        "is_overlap": JIANYING_DISSOLVE_TRANSITION["is_overlap"],
        "name": JIANYING_DISSOLVE_TRANSITION["name"],
        "platform": "all",
        "resource_id": JIANYING_DISSOLVE_TRANSITION["resource_id"],
        "type": "transition",
    }


def _attach_transition(
    materials: dict[str, list[Any]],
    companion_refs: list[str],
    *,
    transition_policy: str,
    duration_us: int,
    next_duration_us: int,
) -> list[str]:
    if transition_policy != "fade_or_match_cut" or duration_us <= 0 or next_duration_us <= 0:
        return companion_refs
    transition_duration_us = min(
        seconds_to_microseconds(0.5),
        duration_us // 3,
        next_duration_us // 3,
    )
    if transition_duration_us < seconds_to_microseconds(0.2):
        return companion_refs
    transition_id = _new_id("transition")
    materials["transitions"].append(
        _transition_material(
            transition_id=transition_id,
            duration_us=transition_duration_us,
        )
    )
    return [*companion_refs, transition_id]


def _subtitle_presentation(segment: Any) -> tuple[float, bool, float]:
    policy = (getattr(segment, "subtitlePolicy", "") or "").strip()
    if policy == "emphasis":
        return CAPTION_FONT_SIZE * 1.1, True, 1.0
    if policy == "info":
        return CAPTION_FONT_SIZE, False, 1.0
    if policy == "minimal":
        return CAPTION_FONT_SIZE * 0.85, False, 0.78
    if policy == "standard":
        return CAPTION_FONT_SIZE, False, 1.0

    role = (segment.attentionRole or segment.function or "").strip()
    if role in {
        "hook",
        "opening_hook",
        "turning_point",
        "turn_1",
        "turn_2",
        "climax",
        "main_climax",
        "emotional_climax",
        "payoff",
    }:
        return CAPTION_FONT_SIZE * 1.1, True, 1.0
    if role in {"buffer", "afterglow", "aftertaste", "transition_buffer"}:
        return CAPTION_FONT_SIZE * 0.85, False, 0.78
    if role in {"ending", "closing", "final"}:
        return CAPTION_FONT_SIZE * 1.05, True, 1.0
    return CAPTION_FONT_SIZE, False, 1.0


def _empty_materials() -> dict[str, list[Any]]:
    return {
        "videos": [],
        "audios": [],
        "texts": [],
        "stickers": [],
        "video_effects": [],
        "transitions": [],
        "masks": [],
        "chromas": [],
        "audio_fades": [],
        "audio_effects": [],
        "canvases": [],
        "speeds": [],
        "sound_channel_mappings": [],
        "vocal_separations": [],
        "placeholders": [],
        "common_mask": [],
        "placeholder_infos": [],
        "material_colors": [],
        "material_animations": [],
    }


def resolve_bgm_path(workspace: WorkspaceDataRead) -> str:
    rhythm = workspace.rhythmPlan
    candidate = rhythm.audioFilePath.strip()
    if candidate and Path(candidate).is_file():
        return str(Path(candidate).resolve()).replace("\\", "/")
    return ""


def resolve_voiceover_path(workspace: WorkspaceDataRead) -> str:
    candidate = workspace.exportPlan.voiceoverAudioPath.strip()
    if candidate and Path(candidate).is_file():
        return str(Path(candidate).resolve()).replace("\\", "/")
    return ""


VOICEOVER_DENSITY_CONFIG = {
    "light": {
        "chars_per_sec": 3.2,
        "min_duration": 4.5,
        "max_duration": 8.0,
        "include_supporting": False,
    },
    "standard": {
        "chars_per_sec": 4.2,
        "min_duration": 3.2,
        "max_duration": 7.0,
        "include_supporting": True,
    },
    "info": {
        "chars_per_sec": 5.0,
        "min_duration": 2.4,
        "max_duration": 6.0,
        "include_supporting": True,
    },
}

VOICEOVER_KEY_FUNCTIONS = {
    "opening_hook",
    "hook",
    "turning_point",
    "climax",
    "main_climax",
    "memory_recall",
    "ending",
    "closing",
    "final",
    "route_info",
    "info_point",
}


@dataclass(frozen=True)
class VoiceoverBlock:
    start_sec: float
    end_sec: float
    text: str
    segment_ids: list[str]


def _normalize_voiceover_density(value: str) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in VOICEOVER_DENSITY_CONFIG else "standard"


def _voiceover_source_text(segment: Any) -> str:
    return " ".join((segment.voiceoverText.strip() or segment.subtitle.strip()).split())


def _is_key_voiceover_segment(segment: Any) -> bool:
    values = {
        (segment.function or "").strip(),
        (segment.attentionRole or "").strip(),
    }
    return any(value in VOICEOVER_KEY_FUNCTIONS for value in values if value)


def _split_voiceover_clauses(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", text.strip())
    normalized = re.sub(r"^(开头|正文|收束|补充提示)[:：]", "", normalized)
    return [
        part.strip(" ，,。.!！？、/|")
        for part in re.split(r"[。！？!?；;\n]+", normalized)
        if part.strip(" ，,。.!！？、/|")
    ]


def _shorten_voiceover_clause(clause: str, max_chars: int) -> str:
    if len(clause) <= max_chars:
        return clause

    phrases = [part for part in re.split(r"[，、,:：]+", clause) if part]
    selected: list[str] = []
    used = 0
    for phrase in phrases:
        extra = len(phrase) + (1 if selected else 0)
        if used + extra > max_chars:
            break
        selected.append(phrase)
        used += extra
    if selected:
        return "，".join(selected)

    # An unpunctuated sentence cannot be shortened safely without changing meaning.
    # Keep it complete and let the timing pass borrow idle time from the timeline.
    return clause


def _compact_voiceover_text(texts: list[str], max_chars: int) -> str:
    unique_clauses: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for clause in _split_voiceover_clauses(text):
            fingerprint = re.sub(r"[，、,:：]", "", clause)
            if not fingerprint or fingerprint in seen:
                continue
            seen.add(fingerprint)
            unique_clauses.append(clause)

    if not unique_clauses:
        return ""

    selected: list[str] = []
    used = 0
    for clause in unique_clauses:
        extra = len(clause) + (1 if selected else 0)
        if used + extra > max_chars:
            continue
        selected.append(clause)
        used += extra

    if not selected:
        selected.append(_shorten_voiceover_clause(unique_clauses[0], max_chars))

    return f"{'，'.join(selected)}。"


def _voiceover_spoken_char_count(text: str) -> int:
    return len(re.sub(r"[\s，,。.!！？、/|…；;：:]", "", text))


def _estimate_voiceover_reading_duration(
    text: str,
    *,
    chars_per_sec: float,
    speed: float,
) -> float:
    effective_speed = max(0.7, min(1.3, speed or 1.0))
    spoken_chars = _voiceover_spoken_char_count(text)
    comma_pauses = len(re.findall(r"[，,、：:]", text)) * 0.12
    sentence_pauses = len(re.findall(r"[。.!！？；;]", text)) * 0.22
    # Jianying voices need a small lead-out margin or the final syllable is clipped.
    lead_out = 0.45
    return round(
        max(1.0, spoken_chars / max(1.0, chars_per_sec * effective_speed)
            + comma_pauses + sentence_pauses + lead_out),
        2,
    )


def _recommended_voiceover_speed(
    text: str,
    *,
    available_duration: float,
    chars_per_sec: float,
) -> float:
    spoken_chars = _voiceover_spoken_char_count(text)
    comma_pauses = len(re.findall(r"[，,、：:]", text)) * 0.12
    sentence_pauses = len(re.findall(r"[。.!！？；;]", text)) * 0.22
    speaking_window = available_duration - comma_pauses - sentence_pauses - 0.45
    if speaking_window <= 0:
        return 9.99
    return round(max(0.7, spoken_chars / max(0.1, chars_per_sec * speaking_window)), 2)


def _fit_voiceover_block_timings(
    blocks: list[VoiceoverBlock],
    *,
    timeline_duration: float,
    chars_per_sec: float,
    speed: float,
) -> list[VoiceoverBlock]:
    if not blocks or timeline_duration <= 0:
        return blocks

    fitted: list[VoiceoverBlock] = []
    previous_end = 0.0
    for block in blocks:
        required_duration = _estimate_voiceover_reading_duration(
            block.text,
            chars_per_sec=chars_per_sec,
            speed=speed,
        )
        source_end = min(timeline_duration, max(block.end_sec, block.start_sec))
        latest_start = max(0.0, source_end - required_duration)
        start = max(previous_end, min(block.start_sec, latest_start))
        end = min(timeline_duration, start + required_duration)

        # If the end of the timeline is close, borrow as much earlier idle time as possible.
        if end - start + 0.01 < required_duration:
            start = max(previous_end, timeline_duration - required_duration)
            end = timeline_duration

        fitted.append(
            VoiceoverBlock(
                start_sec=round(start, 2),
                end_sec=round(end, 2),
                text=block.text,
                segment_ids=block.segment_ids,
            )
        )
        previous_end = end

    return fitted


def build_native_voiceover_preview(workspace: WorkspaceDataRead) -> dict[str, Any]:
    density = _normalize_voiceover_density(workspace.exportPlan.voiceoverDensity)
    blocks = build_native_voiceover_blocks(workspace)
    source_texts = [
        _voiceover_source_text(segment)
        for segment in workspace.storyboard
        if _voiceover_source_text(segment)
    ]
    if not source_texts and workspace.exportPlan.voiceoverScript.strip():
        source_texts = [workspace.exportPlan.voiceoverScript.strip()]

    source_chars = sum(len(re.sub(r"[\s，,。.!！？、/|]", "", text)) for text in source_texts)
    output_chars = sum(len(re.sub(r"[\s，,。.!！？、/|…]", "", block.text)) for block in blocks)
    total_block_duration = round(sum(block.end_sec - block.start_sec for block in blocks), 2)
    chars_per_sec = float(VOICEOVER_DENSITY_CONFIG[density]["chars_per_sec"])
    speed = workspace.exportPlan.voiceoverSpeed
    estimated_reading_sec = round(
        sum(
            _estimate_voiceover_reading_duration(
                block.text,
                chars_per_sec=chars_per_sec,
                speed=speed,
            )
            for block in blocks
        ),
        2,
    )
    timing_risk_count = sum(
        1
        for block in blocks
        if _estimate_voiceover_reading_duration(
            block.text,
            chars_per_sec=chars_per_sec,
            speed=speed,
        )
        > block.end_sec - block.start_sec + 0.05
    )
    segment_map = {segment.id: segment for segment in workspace.storyboard}
    block_previews: list[dict[str, Any]] = []
    recommended_speeds: list[float] = []
    alignment_risk_count = 0
    for block in blocks:
        source_segments = [
            segment_map[segment_id]
            for segment_id in block.segment_ids
            if segment_id in segment_map
        ]
        source_start = min(
            (segment.startTime for segment in source_segments),
            default=block.start_sec,
        )
        source_end = max(
            (segment.endTime for segment in source_segments),
            default=block.end_sec,
        )
        source_duration = max(0.1, source_end - source_start)
        recommended_speed = _recommended_voiceover_speed(
            block.text,
            available_duration=source_duration,
            chars_per_sec=chars_per_sec,
        )
        recommended_speeds.append(recommended_speed)
        alignment_shift = round(max(0.0, source_start - block.start_sec), 2)
        if alignment_shift <= 0.05:
            alignment_status = "aligned"
        elif recommended_speed <= 1.3:
            alignment_status = "speed_recommended"
            alignment_risk_count += 1
        else:
            alignment_status = "needs_trim_or_extend"
            alignment_risk_count += 1

        block_previews.append(
            {
                "startTime": block.start_sec,
                "endTime": block.end_sec,
                "sourceStartTime": round(source_start, 2),
                "sourceEndTime": round(source_end, 2),
                "text": block.text,
                "segmentIds": block.segment_ids,
                "estimatedReadingSec": _estimate_voiceover_reading_duration(
                    block.text,
                    chars_per_sec=chars_per_sec,
                    speed=speed,
                ),
                "recommendedSpeed": recommended_speed,
                "alignmentShiftSec": alignment_shift,
                "alignmentStatus": alignment_status,
            }
        )

    overall_recommended_speed = round(
        min(1.3, max([1.0, *recommended_speeds])),
        2,
    )

    return {
        "density": density,
        "sourceChars": source_chars,
        "outputChars": output_chars,
        "compressionRatio": round(output_chars / source_chars, 3) if source_chars else 0.0,
        "blockCount": len(blocks),
        "timelineCoverageSec": total_block_duration,
        "estimatedReadingSec": estimated_reading_sec,
        "timingRiskCount": timing_risk_count,
        "alignmentRiskCount": alignment_risk_count,
        "recommendedSpeed": overall_recommended_speed,
        "blocks": block_previews,
    }


def build_native_voiceover_blocks(workspace: WorkspaceDataRead) -> list[VoiceoverBlock]:
    density = _normalize_voiceover_density(workspace.exportPlan.voiceoverDensity)
    config = VOICEOVER_DENSITY_CONFIG[density]
    chars_per_sec = float(config["chars_per_sec"])
    min_duration = float(config["min_duration"])
    max_duration = float(config["max_duration"])
    include_supporting = bool(config["include_supporting"])

    blocks: list[VoiceoverBlock] = []
    current_start: float | None = None
    current_end = 0.0
    current_texts: list[str] = []
    current_ids: list[str] = []

    def flush() -> None:
        nonlocal current_start, current_end, current_texts, current_ids
        if current_start is None or current_end <= current_start:
            current_start = None
            current_end = 0.0
            current_texts = []
            current_ids = []
            return

        duration = max(0.1, current_end - current_start)
        max_chars = max(4, int(duration * chars_per_sec))
        text = _compact_voiceover_text(current_texts, max_chars)
        if text:
            blocks.append(
                VoiceoverBlock(
                    start_sec=current_start,
                    end_sec=current_end,
                    text=text,
                    segment_ids=[*current_ids],
                )
            )
        current_start = None
        current_end = 0.0
        current_texts = []
        current_ids = []

    for index, segment in enumerate(sorted(workspace.storyboard, key=lambda item: item.startTime)):
        text_value = _voiceover_source_text(segment)
        if not text_value:
            continue

        is_key = _is_key_voiceover_segment(segment)
        should_include = include_supporting or is_key or index == 0 or index == len(workspace.storyboard) - 1
        if not should_include:
            if current_start is not None and segment.endTime - current_start >= min_duration:
                flush()
            continue

        if current_start is None:
            current_start = segment.startTime

        current_end = max(current_end, segment.endTime)
        current_texts.append(text_value)
        current_ids.append(segment.id)

        duration = current_end - current_start
        if duration >= max_duration or (duration >= min_duration and is_key and len(current_texts) > 1):
            flush()

    flush()

    if not blocks and workspace.exportPlan.voiceoverScript.strip():
        timeline_duration = max((segment.endTime for segment in workspace.storyboard), default=0.0)
        if timeline_duration > 0:
            max_chars = max(4, int(timeline_duration * chars_per_sec))
            text = _compact_voiceover_text([workspace.exportPlan.voiceoverScript.strip()], max_chars)
            if text:
                blocks.append(
                    VoiceoverBlock(
                        start_sec=0.0,
                        end_sec=timeline_duration,
                        text=text,
                        segment_ids=[],
                    )
                )

    timeline_duration = max((segment.endTime for segment in workspace.storyboard), default=0.0)
    return _fit_voiceover_block_timings(
        blocks,
        timeline_duration=timeline_duration,
        chars_per_sec=chars_per_sec,
        speed=workspace.exportPlan.voiceoverSpeed,
    )


def build_generated_voiceover_caption_blocks(workspace: WorkspaceDataRead) -> list[VoiceoverBlock]:
    raw_timings = workspace.exportPlan.voiceoverProviderMeta.get("captionTimings", [])
    if not isinstance(raw_timings, list):
        return []

    timeline_duration = max((segment.endTime for segment in workspace.storyboard), default=0.0)
    blocks: list[VoiceoverBlock] = []
    for item in raw_timings:
        if not isinstance(item, dict):
            continue
        try:
            start_sec = max(0.0, float(item.get("startTime", 0.0)))
            end_sec = min(timeline_duration, float(item.get("endTime", 0.0)))
        except (TypeError, ValueError):
            continue
        text = str(item.get("text", "")).strip()
        if not text or end_sec <= start_sec:
            continue
        segment_ids = item.get("segmentIds", [])
        blocks.append(
            VoiceoverBlock(
                start_sec=round(start_sec, 3),
                end_sec=round(end_sec, 3),
                text=text,
                segment_ids=[str(value) for value in segment_ids]
                if isinstance(segment_ids, list)
                else [],
            )
        )
    return blocks


def build_capcut_draft(workspace: WorkspaceDataRead, *, bgm_path: str = "") -> dict[str, Any]:
    asset_map: dict[str, AssetRead] = {asset.assetId: asset for asset in workspace.assets}
    draft_id = _new_id("draft")
    draft_name = workspace.exportPlan.title.strip() or workspace.project.name or workspace.project.id

    materials = _empty_materials()
    video_track_id = _new_id("track-video")
    audio_track_id = _new_id("track-audio")
    voiceover_track_id = _new_id("track-voiceover")
    text_track_id = _new_id("track-text")
    video_segments: list[dict[str, Any]] = []
    audio_segments: list[dict[str, Any]] = []
    voiceover_segments: list[dict[str, Any]] = []
    text_segments: list[dict[str, Any]] = []
    video_material_ids_by_path: dict[str, str] = {}
    use_native_voiceover_text = workspace.exportPlan.voiceoverProvider == "jianying_native_tts"
    use_generated_voiceover_text = (
        workspace.exportPlan.voiceoverProvider == "edge"
        and bool(workspace.exportPlan.voiceoverAudioPath.strip())
    )
    final_voiceover_blocks = (
        build_native_voiceover_blocks(workspace)
        if use_native_voiceover_text
        else build_generated_voiceover_caption_blocks(workspace)
        if use_generated_voiceover_text
        else []
    )
    use_final_voiceover_text = bool(final_voiceover_blocks)
    storyboard_by_id = {segment.id: segment for segment in workspace.storyboard}
    total_duration_us = 0
    transition_count = 0
    motion_keyframe_segment_count = 0
    emphasized_subtitle_count = 0

    for index, segment in enumerate(workspace.storyboard):
        duration_us = seconds_to_microseconds(segment.endTime - segment.startTime)
        start_us = seconds_to_microseconds(segment.startTime)
        next_segment = (
            workspace.storyboard[index + 1]
            if index + 1 < len(workspace.storyboard)
            else None
        )
        next_duration_us = (
            seconds_to_microseconds(next_segment.endTime - next_segment.startTime)
            if next_segment
            else 0
        )
        total_duration_us = max(total_duration_us, start_us + duration_us)

        asset = asset_map.get(segment.assetId)
        clip_path = ""
        if asset:
            clip_path = resolve_clip_path(workspace.project.mediaRoot, asset.relativePath)

        if clip_path:
            material_id = video_material_ids_by_path.get(clip_path)
            if not material_id:
                material_id = _new_id("mat-video")
                video_material_ids_by_path[clip_path] = material_id
                materials["videos"].append(
                    _video_material(
                        material_id=material_id,
                        path=clip_path,
                        duration_us=duration_us,
                        asset=asset,
                    )
                )

            companion_refs, companion_materials = _create_companion_materials("video")
            _merge_materials(materials, companion_materials)
            refs_before_transition = len(companion_refs)
            companion_refs = _attach_transition(
                materials,
                companion_refs,
                transition_policy=segment.transitionPolicy,
                duration_us=duration_us,
                next_duration_us=next_duration_us,
            )
            if len(companion_refs) > refs_before_transition:
                transition_count += 1
            motion_keyframes = _motion_keyframes(
                motion_policy=segment.motionPolicy,
                media_type=asset.mediaType if asset else "video",
                duration_us=duration_us,
            )
            if motion_keyframes:
                motion_keyframe_segment_count += 1
            video_segments.append(
                _base_segment(
                    segment_id=_new_id("seg-video"),
                    material_id=material_id,
                    track_id=video_track_id,
                    start_us=start_us,
                    duration_us=duration_us,
                    companion_refs=companion_refs,
                    render_index=14000 + index,
                    common_keyframes=motion_keyframes,
                )
            )

        subtitle = segment.subtitle.strip()
        if subtitle and not use_final_voiceover_text:
            subtitle_font_size, subtitle_bold, subtitle_alpha = _subtitle_presentation(segment)
            if subtitle_bold:
                emphasized_subtitle_count += 1
            text_material_id = _new_id("mat-text")
            materials["texts"].append(
                _text_material(
                    material_id=text_material_id,
                    text=subtitle,
                    font_size=subtitle_font_size,
                    bold=subtitle_bold,
                    alpha=subtitle_alpha,
                )
            )
            companion_refs, companion_materials = _create_companion_materials("text")
            _merge_materials(materials, companion_materials)
            text_segments.append(
                _base_segment(
                    segment_id=_new_id("seg-text"),
                    material_id=text_material_id,
                    track_id=text_track_id,
                    start_us=start_us,
                    duration_us=duration_us,
                    companion_refs=companion_refs,
                    render_index=15000 + index,
                    clip=_caption_clip(),
                )
            )

    if use_final_voiceover_text:
        for index, block in enumerate(final_voiceover_blocks):
            duration_us = seconds_to_microseconds(block.end_sec - block.start_sec)
            if duration_us <= 0:
                continue
            source_segments = [
                storyboard_by_id[segment_id]
                for segment_id in block.segment_ids
                if segment_id in storyboard_by_id
            ]
            subtitle_font_size = CAPTION_FONT_SIZE
            subtitle_bold = False
            subtitle_alpha = 1.0
            if source_segments:
                presentations = [_subtitle_presentation(segment) for segment in source_segments]
                subtitle_font_size = max(item[0] for item in presentations)
                subtitle_bold = any(item[1] for item in presentations)
                subtitle_alpha = max(item[2] for item in presentations)
            if subtitle_bold:
                emphasized_subtitle_count += 1
            native_text_material_id = _new_id("mat-final-subtitle")
            materials["texts"].append(
                _text_material(
                    material_id=native_text_material_id,
                    text=block.text,
                    font_size=subtitle_font_size,
                    bold=subtitle_bold,
                    alpha=subtitle_alpha,
                )
            )
            companion_refs, companion_materials = _create_companion_materials("text")
            _merge_materials(materials, companion_materials)
            text_segments.append(
                _base_segment(
                    segment_id=_new_id("seg-final-subtitle"),
                    material_id=native_text_material_id,
                    track_id=text_track_id,
                    start_us=seconds_to_microseconds(block.start_sec),
                    duration_us=duration_us,
                    companion_refs=companion_refs,
                    render_index=15000 + index,
                    clip=_caption_clip(),
                )
            )

    effective_bgm_path = bgm_path.strip() or resolve_bgm_path(workspace)
    effective_voiceover_path = resolve_voiceover_path(workspace)
    bgm_included = False
    voiceover_included = False
    if effective_bgm_path and total_duration_us > 0:
        bgm_name = workspace.rhythmPlan.audioFileName.strip() or Path(effective_bgm_path).name
        source_duration_us = seconds_to_microseconds(workspace.rhythmPlan.audioDurationSec)
        if source_duration_us <= 0:
            source_duration_us = total_duration_us
        material_duration_us = max(source_duration_us, total_duration_us)
        timeline_duration_us = total_duration_us

        audio_material_id = _new_id("mat-audio")
        materials["audios"].append(
            _audio_material(
                material_id=audio_material_id,
                path=effective_bgm_path,
                name=bgm_name,
                duration_us=material_duration_us,
            )
        )
        companion_refs, companion_materials = _create_companion_materials("audio")
        _merge_materials(materials, companion_materials)
        companion_refs = _attach_bgm_fade_out(
            materials,
            companion_refs,
            timeline_duration_us=timeline_duration_us,
        )
        audio_segments.append(
            _base_segment(
                segment_id=_new_id("seg-audio"),
                material_id=audio_material_id,
                track_id=audio_track_id,
                start_us=0,
                duration_us=timeline_duration_us,
                companion_refs=companion_refs,
                render_index=0,
                volume=DUCKED_BGM_VOLUME if effective_voiceover_path else DEFAULT_BGM_VOLUME,
            )
        )
        bgm_included = True

    if effective_voiceover_path and total_duration_us > 0:
        voiceover_duration_us = seconds_to_microseconds(workspace.exportPlan.voiceoverDurationSec)
        if voiceover_duration_us <= 0:
            voiceover_duration_us = total_duration_us
        timeline_duration_us = min(voiceover_duration_us, total_duration_us)
        material_duration_us = max(voiceover_duration_us, timeline_duration_us)

        voiceover_material_id = _new_id("mat-voiceover")
        materials["audios"].append(
            _audio_material(
                material_id=voiceover_material_id,
                path=effective_voiceover_path,
                name=Path(effective_voiceover_path).name,
                duration_us=material_duration_us,
            )
        )
        companion_refs, companion_materials = _create_companion_materials("audio")
        _merge_materials(materials, companion_materials)
        voiceover_segments.append(
            _base_segment(
                segment_id=_new_id("seg-voiceover"),
                material_id=voiceover_material_id,
                track_id=voiceover_track_id,
                start_us=0,
                duration_us=timeline_duration_us,
                companion_refs=companion_refs,
                render_index=1000,
                volume=1.0,
            )
        )
        voiceover_included = True

    tracks: list[dict[str, Any]] = []
    if video_segments:
        tracks.append(
            {
                "id": video_track_id,
                "type": "video",
                "name": "主视频",
                "is_default_name": False,
                "attribute": 0,
                "flag": 0,
                "segments": video_segments,
            }
        )
    if audio_segments:
        tracks.append(
            {
                "id": audio_track_id,
                "type": "audio",
                "name": "BGM",
                "is_default_name": False,
                "attribute": 0,
                "flag": 0,
                "segments": audio_segments,
            }
        )
    if voiceover_segments:
        tracks.append(
            {
                "id": voiceover_track_id,
                "type": "audio",
                "name": "口播",
                "is_default_name": False,
                "attribute": 0,
                "flag": 0,
                "segments": voiceover_segments,
            }
        )
    if text_segments:
        text_track_name = "字幕"
        if use_native_voiceover_text:
            voiceover_speed = max(0.7, min(1.3, workspace.exportPlan.voiceoverSpeed or 1.0))
            text_track_name = "最终字幕（剪映朗读源）"
            if abs(voiceover_speed - 1.0) >= 0.01:
                text_track_name += f"（按{voiceover_speed:g}x校准）"
        elif use_generated_voiceover_text:
            text_track_name = "最终字幕（口播同步）"
        tracks.append(
            {
                "id": text_track_id,
                "type": "text",
                "name": text_track_name,
                "is_default_name": False,
                "attribute": 0,
                "flag": 0,
                "segments": text_segments,
            }
        )

    return {
        "id": draft_id,
        "name": draft_name,
        "duration": total_duration_us,
        "fps": DEFAULT_CAPCUT_FPS,
        "canvas_config": {"width": 1920, "height": 1080, "ratio": "16:9"},
        "platform": dict(JIANYING_PLATFORM),
        "tracks": tracks,
        "materials": materials,
        "extra_info": {
            "created_via": "video-sop-editor",
            "project_id": workspace.project.id,
            "segment_count": len(workspace.storyboard),
            "bgm_included": bgm_included,
            "voiceover_included": voiceover_included,
            "jianying_native_tts_text_track_included": bool(
                use_native_voiceover_text and text_segments
            ),
            "jianying_native_tts_block_count": len(final_voiceover_blocks)
            if use_native_voiceover_text
            else 0,
            "generated_voiceover_caption_count": len(final_voiceover_blocks)
            if use_generated_voiceover_text
            else 0,
            "final_subtitles_use_compressed_voiceover": bool(
                use_final_voiceover_text and text_segments
            ),
            "voiceover_density": _normalize_voiceover_density(
                workspace.exportPlan.voiceoverDensity
            ),
            "voiceover_speed": workspace.exportPlan.voiceoverSpeed,
            "transition_count": transition_count,
            "motion_keyframe_segment_count": motion_keyframe_segment_count,
            "emphasized_subtitle_count": emphasized_subtitle_count,
            "bgm_ducking_applied": bool(bgm_included and voiceover_included),
        },
    }


def build_draft_folder_name(workspace: WorkspaceDataRead) -> str:
    draft_name = workspace.exportPlan.title.strip() or workspace.project.name or workspace.project.id
    return sanitize_draft_folder_name(f"{workspace.project.id}-{draft_name}")


def render_capcut_draft(workspace: WorkspaceDataRead) -> str:
    draft = build_capcut_draft(workspace)
    draft_folder_name = build_draft_folder_name(workspace)
    bundle = {
        "schemaVersion": "1.0",
        "targetApp": "jianying",
        "draftFolderName": draft_folder_name,
        "importInstructions": (
            "推荐使用「写入剪映草稿目录」一键落地；若手动导入，请将 sections 中两个 JSON "
            "分别保存为 draft_content.json 与 draft_meta_info.json。"
        ),
        "sections": {
            "draft_content.json": draft,
            "draft_meta_info.json": draft,
        },
        "files": {
            "draft_content.json": draft,
            "draft_meta_info.json": draft,
        },
    }
    return json.dumps(bundle, ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class CapcutDraftDeployResult:
    draft_root: str
    draft_folder_name: str
    draft_folder_path: str
    files: list[str]
    bgm_included: bool
    voiceover_included: bool


class CapcutDraftFolderExistsError(ValueError):
    def __init__(self, *, draft_folder_name: str, draft_folder_path: str) -> None:
        self.draft_folder_name = draft_folder_name
        self.draft_folder_path = draft_folder_path
        super().__init__(
            f"剪映草稿文件夹已存在：{draft_folder_path}。"
            "如需覆盖，请确认清除该文件夹内的现有文件后重新写入。"
        )


def draft_folder_has_contents(folder_path: Path) -> bool:
    return folder_path.is_dir() and any(folder_path.iterdir())


def clear_draft_folder_contents(folder_path: Path) -> None:
    if not folder_path.is_dir():
        return
    for child in folder_path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def deploy_capcut_draft(
    workspace: WorkspaceDataRead,
    *,
    draft_root: str,
    clear_existing: bool = False,
) -> CapcutDraftDeployResult:
    resolved_root = resolve_jianying_draft_root(draft_root)
    if not resolved_root:
        raise ValueError("未配置剪映草稿根目录，且无法解析系统默认路径（需要 LOCALAPPDATA）")

    root_path = Path(resolved_root)
    if not root_path.is_absolute():
        raise ValueError("剪映草稿根目录必须是绝对路径")

    draft = build_capcut_draft(workspace)
    draft_folder_name = build_draft_folder_name(workspace)
    folder_path = root_path / draft_folder_name

    if draft_folder_has_contents(folder_path) and not clear_existing:
        raise CapcutDraftFolderExistsError(
            draft_folder_name=draft_folder_name,
            draft_folder_path=str(folder_path).replace("\\", "/"),
        )

    if clear_existing and folder_path.is_dir():
        clear_draft_folder_contents(folder_path)
    folder_path.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(draft, ensure_ascii=False, indent=2)
    written_files: list[str] = []
    for file_name in DRAFT_FILE_NAMES:
        target = folder_path / file_name
        target.write_text(payload, encoding="utf-8")
        written_files.append(file_name)

    return CapcutDraftDeployResult(
        draft_root=str(root_path).replace("\\", "/"),
        draft_folder_name=draft_folder_name,
        draft_folder_path=str(folder_path).replace("\\", "/"),
        files=written_files,
        bgm_included=bool(draft.get("extra_info", {}).get("bgm_included")),
        voiceover_included=bool(draft.get("extra_info", {}).get("voiceover_included")),
    )
