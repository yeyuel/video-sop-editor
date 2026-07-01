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

# CapCut default caption export used 15; user feedback prefers half size.
DEFAULT_CAPTION_FONT_SIZE = 15.0
CAPTION_FONT_SIZE = DEFAULT_CAPTION_FONT_SIZE * 0.5

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


def build_text_content(text: str, *, font_size: float = CAPTION_FONT_SIZE) -> str:
    payload = {
        "styles": [
            {
                "fill": {
                    "alpha": 1.0,
                    "content": {
                        "render_type": "solid",
                        "solid": {"alpha": 1.0, "color": [1, 1, 1]},
                    },
                },
                "range": text_style_range(text),
                "size": font_size,
                "bold": False,
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
    clip["transform"] = {"x": 0, "y": -0.75}
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
        "common_keyframes": [],
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


def _text_material(*, material_id: str, text: str) -> dict[str, Any]:
    # Match pyJianYingDraft TextSegment.export_material(): font lives in content JSON.
    return {
        "id": material_id,
        "type": "text",
        "content": build_text_content(text),
        "alignment": 1,
        "typesetting": 0,
        "letter_spacing": 0.0,
        "line_spacing": 0.02,
        "line_feed": 1,
        "line_max_width": 0.82,
        "force_apply_line_max_width": False,
        "check_flag": 7,
        "global_alpha": 1.0,
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
) -> list[str]:
    if timeline_duration_us <= 0:
        return companion_refs
    fade_out_us = min(
        seconds_to_microseconds(fade_out_sec),
        max(seconds_to_microseconds(0.2), timeline_duration_us // 2),
    )
    fade_id = _new_id("fade")
    materials["audio_fades"].append(
        _audio_fade_material(fade_id=fade_id, fade_out_us=fade_out_us)
    )
    return [*companion_refs, fade_id]


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


def build_capcut_draft(workspace: WorkspaceDataRead, *, bgm_path: str = "") -> dict[str, Any]:
    asset_map: dict[str, AssetRead] = {asset.assetId: asset for asset in workspace.assets}
    draft_id = _new_id("draft")
    draft_name = workspace.exportPlan.title.strip() or workspace.project.name or workspace.project.id

    materials = _empty_materials()
    video_track_id = _new_id("track-video")
    audio_track_id = _new_id("track-audio")
    text_track_id = _new_id("track-text")
    video_segments: list[dict[str, Any]] = []
    audio_segments: list[dict[str, Any]] = []
    text_segments: list[dict[str, Any]] = []
    video_material_ids_by_path: dict[str, str] = {}
    total_duration_us = 0

    for index, segment in enumerate(workspace.storyboard):
        duration_us = seconds_to_microseconds(segment.endTime - segment.startTime)
        start_us = seconds_to_microseconds(segment.startTime)
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
            video_segments.append(
                _base_segment(
                    segment_id=_new_id("seg-video"),
                    material_id=material_id,
                    track_id=video_track_id,
                    start_us=start_us,
                    duration_us=duration_us,
                    companion_refs=companion_refs,
                    render_index=14000 + index,
                )
            )

        subtitle = segment.subtitle.strip()
        if subtitle:
            text_material_id = _new_id("mat-text")
            materials["texts"].append(_text_material(material_id=text_material_id, text=subtitle))
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

    effective_bgm_path = bgm_path.strip() or resolve_bgm_path(workspace)
    bgm_included = False
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
                volume=0.8,
            )
        )
        bgm_included = True

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
    if text_segments:
        tracks.append(
            {
                "id": text_track_id,
                "type": "text",
                "name": "字幕",
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
    )
