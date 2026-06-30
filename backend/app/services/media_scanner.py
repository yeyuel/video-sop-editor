from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass, field
from pathlib import Path

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".webm",
    ".mts",
    ".m2ts",
    ".wmv",
    ".flv",
    ".3gp",
}
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
    ".dng",
    ".raw",
}
AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".flac",
    ".aac",
    ".m4a",
    ".ogg",
    ".wma",
    ".aiff",
    ".aif",
}

SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS

SKIP_DIR_NAMES = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".next",
    "Thumbs.db",
    "$recycle.bin",
    "System Volume Information",
}

DEFAULT_MAX_FILES = 8000
DEFAULT_MAX_DEPTH = 12


class MediaScanError(Exception):
    pass


@dataclass
class MediaLibraryNode:
    name: str
    relative_path: str
    node_type: str
    media_kind: str | None = None
    media_type: str | None = None
    size_bytes: int = 0
    has_asset: bool = False
    children: list[MediaLibraryNode] = field(default_factory=list)


def normalize_media_root_path(path: str) -> str:
    return path.replace("\\", "/").strip().rstrip("/").lower()


def media_roots_match(left: str, right: str) -> bool:
    return normalize_media_root_path(left) == normalize_media_root_path(right)


def normalize_relative_path(path: str) -> str:
    cleaned = path.replace("\\", "/").strip().lstrip("/")
    return cleaned


def resolve_safe_media_path(media_root: str, relative_path: str = "") -> Path:
    if not media_root.strip():
        raise MediaScanError("项目未配置素材根目录。")

    root = Path(media_root).expanduser().resolve()
    if not root.is_dir():
        raise MediaScanError(f"素材根目录不存在或不可访问：{root}")

    rel = normalize_relative_path(relative_path)
    if rel in {"", "."}:
        return root

    parts = [part for part in rel.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        raise MediaScanError("非法相对路径。")

    target = root.joinpath(*parts).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise MediaScanError("非法相对路径。") from exc
    return target


def detect_media_kind(extension: str) -> str | None:
    lowered = extension.lower()
    if lowered in VIDEO_EXTENSIONS:
        return "video"
    if lowered in IMAGE_EXTENSIONS:
        return "image"
    if lowered in AUDIO_EXTENSIONS:
        return "audio"
    return None


def infer_asset_media_type(relative_path: str, media_kind: str | None) -> str:
    lowered = relative_path.lower().replace("\\", "/")
    filename = lowered.rsplit("/", 1)[-1]

    if media_kind == "image":
        return "photo"
    if media_kind == "audio":
        return "audio"

    if any(token in lowered for token in ("/drone/", "/dji/", "/航拍/")):
        return "drone_video"
    if "dji_" in filename or filename.startswith("drone"):
        return "drone_video"
    if any(token in lowered for token in ("/mobile/", "/phone/", "/手机/")):
        return "mobile_video"
    if any(token in lowered for token in ("/camera/", "/相机/")):
        return "camera_video"
    return "video"


def infer_location_from_path(relative_path: str) -> str:
    normalized = normalize_relative_path(relative_path)
    if not normalized:
        return ""
    parts = [part for part in normalized.split("/") if part]
    if len(parts) <= 1:
        return ""
    # 取第一级目录作为地点；若只有两层则取父目录名
    if len(parts) == 2:
        return parts[0]
    return parts[0]


def guess_preview_mime(relative_path: str, media_kind: str | None) -> str:
    mime, _ = mimetypes.guess_type(relative_path.replace("\\", "/"))
    if mime:
        return mime
    if media_kind == "video":
        return "video/mp4"
    if media_kind == "image":
        return "image/jpeg"
    if media_kind == "audio":
        return "audio/mpeg"
    return "application/octet-stream"


def _should_skip_dir(name: str) -> bool:
    return name.startswith(".") and name not in {".", ".."} or name in SKIP_DIR_NAMES


def scan_media_library(
    media_root: str,
    *,
    existing_relative_paths: set[str] | None = None,
    max_files: int = DEFAULT_MAX_FILES,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> tuple[MediaLibraryNode, dict[str, int | str]]:
    root_path = resolve_safe_media_path(media_root)
    existing = {
        normalize_relative_path(item).lower()
        for item in (existing_relative_paths or set())
        if item.strip()
    }

    stats = {
        "fileCount": 0,
        "directoryCount": 0,
        "truncated": False,
        "mediaRoot": str(root_path),
    }

    def walk(current: Path, depth: int) -> MediaLibraryNode:
        rel = normalize_relative_path(os.path.relpath(current, root_path))
        if rel == ".":
            rel = ""

        node = MediaLibraryNode(
            name=current.name if rel else root_path.name,
            relative_path=rel,
            node_type="directory",
        )

        if depth >= max_depth:
            return node

        try:
            entries = sorted(
                current.iterdir(),
                key=lambda item: (not item.is_dir(), item.name.lower()),
            )
        except OSError as exc:
            raise MediaScanError(f"无法读取目录：{current}") from exc

        for entry in entries:
            if entry.is_dir():
                if _should_skip_dir(entry.name):
                    continue
                stats["directoryCount"] = int(stats["directoryCount"]) + 1
                node.children.append(walk(entry, depth + 1))
                continue

            extension = entry.suffix.lower()
            media_kind = detect_media_kind(extension)
            if not media_kind:
                continue

            if int(stats["fileCount"]) >= max_files:
                stats["truncated"] = True
                break

            rel_file = normalize_relative_path(os.path.relpath(entry, root_path))
            stats["fileCount"] = int(stats["fileCount"]) + 1
            node.children.append(
                MediaLibraryNode(
                    name=entry.name,
                    relative_path=rel_file,
                    node_type="file",
                    media_kind=media_kind,
                    media_type=infer_asset_media_type(rel_file, media_kind),
                    size_bytes=entry.stat().st_size,
                    has_asset=rel_file.lower() in existing,
                )
            )

        return node

    tree = walk(root_path, 0)
    return tree, stats


def node_to_dict(node: MediaLibraryNode) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": node.name,
        "relativePath": node.relative_path,
        "nodeType": node.node_type,
        "mediaKind": node.media_kind,
        "mediaType": node.media_type,
        "sizeBytes": node.size_bytes,
        "hasAsset": node.has_asset,
    }
    if node.children:
        payload["children"] = [node_to_dict(child) for child in node.children]
    return payload
