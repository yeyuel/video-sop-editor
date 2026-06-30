from __future__ import annotations

from pathlib import Path

import pytest

from app.services.media_scanner import (
    MediaScanError,
    infer_asset_media_type,
    infer_location_from_path,
    normalize_relative_path,
    resolve_safe_media_path,
    scan_media_library,
)


def test_normalize_relative_path() -> None:
    assert normalize_relative_path(r"喀纳斯\drone\a.mp4") == "喀纳斯/drone/a.mp4"


def test_resolve_safe_media_path_blocks_traversal(tmp_path: Path) -> None:
    root = tmp_path / "media"
    root.mkdir()
    (root / "clip.mp4").write_bytes(b"demo")

    resolved = resolve_safe_media_path(str(root), "clip.mp4")
    assert resolved.name == "clip.mp4"

    with pytest.raises(MediaScanError):
        resolve_safe_media_path(str(root), "../secret.mp4")


def test_scan_media_library_builds_tree(tmp_path: Path) -> None:
    root = tmp_path / "library"
    (root / "喀纳斯").mkdir(parents=True)
    (root / "喀纳斯" / "drone").mkdir()
    (root / "喀纳斯" / "drone" / "DJI_001.mp4").write_bytes(b"video")
    (root / "喀纳斯" / "photo.jpg").write_bytes(b"image")
    (root / "喀纳斯" / "bgm.wav").write_bytes(b"audio")
    (root / "喀纳斯" / "notes.txt").write_text("skip", encoding="utf-8")

    tree, stats = scan_media_library(str(root))
    assert stats["fileCount"] == 3
    assert tree.node_type == "directory"
    assert any(child.name == "喀纳斯" for child in tree.children)

    kanas = next(child for child in tree.children if child.name == "喀纳斯")
    drone = next(child for child in kanas.children if child.name == "drone")
    top_files = {child.name for child in kanas.children if child.node_type == "file"}
    nested_files = {child.name for child in drone.children if child.node_type == "file"}
    assert top_files == {"photo.jpg", "bgm.wav"}
    assert nested_files == {"DJI_001.mp4"}


def test_infer_asset_media_type_for_drone() -> None:
    assert infer_asset_media_type("喀纳斯/drone/DJI_001.mp4", "video") == "drone_video"
    assert infer_asset_media_type("喀纳斯/photo.jpg", "image") == "photo"
    assert infer_asset_media_type("喀纳斯/bgm.wav", "audio") == "audio"


def test_infer_location_from_path() -> None:
    assert infer_location_from_path("喀纳斯/drone/DJI_001.mp4") == "喀纳斯"
    assert infer_location_from_path("clip.mp4") == ""
