from __future__ import annotations

from pathlib import Path

from app.models.schemas import AssetRead, WorkspaceDataRead

DEFAULT_EDL_FPS = 30


def seconds_to_edl_timecode(seconds: float, *, fps: int = DEFAULT_EDL_FPS) -> str:
    safe_seconds = max(0.0, seconds)
    total_frames = int(round(safe_seconds * fps))
    frame = total_frames % fps
    total_seconds = total_frames // fps
    second = total_seconds % 60
    minute = (total_seconds // 60) % 60
    hour = total_seconds // 3600
    return f"{hour:02d}:{minute:02d}:{second:02d}:{frame:02d}"


def edl_reel_name(asset_id: str) -> str:
    normalized = "".join(ch for ch in asset_id.upper() if ch.isalnum() or ch in {"_", "-"})
    if not normalized:
        return "CLIP"
    return normalized[:8].ljust(8)


def resolve_clip_path(media_root: str, relative_path: str) -> str:
    root = media_root.strip()
    rel = relative_path.strip()
    if not rel:
        return ""
    if root:
        return str(Path(root) / rel).replace("\\", "/")
    return rel.replace("\\", "/")


def _segment_source_duration(segment_duration: float) -> float:
    return max(segment_duration, 1.0 / DEFAULT_EDL_FPS)


def render_edl(workspace: WorkspaceDataRead, *, fps: int = DEFAULT_EDL_FPS) -> str:
    asset_map: dict[str, AssetRead] = {asset.assetId: asset for asset in workspace.assets}
    lines = [
        f"TITLE: {workspace.project.name or workspace.project.id}",
        f"* PROJECT: {workspace.project.destination}",
        "FCM: NON-DROP FRAME",
        "",
    ]

    for index, segment in enumerate(workspace.storyboard, start=1):
        asset = asset_map.get(segment.assetId)
        reel = edl_reel_name(segment.assetId)
        record_in = seconds_to_edl_timecode(segment.startTime, fps=fps)
        record_out = seconds_to_edl_timecode(segment.endTime, fps=fps)
        source_duration = _segment_source_duration(segment.endTime - segment.startTime)
        source_in = seconds_to_edl_timecode(0.0, fps=fps)
        source_out = seconds_to_edl_timecode(source_duration, fps=fps)

        lines.append(
            f"{index:03d}  {reel} V     C        {source_in} {source_out} {record_in} {record_out}"
        )
        lines.append(f"* SEGMENT ID: {segment.id}")
        if asset:
            clip_path = resolve_clip_path(workspace.project.mediaRoot, asset.relativePath)
            if clip_path:
                lines.append(f"* FROM CLIP NAME: {clip_path}")
            if asset.location.strip():
                lines.append(f"* LOCATION: {asset.location.strip()}")
        if segment.subtitle.strip():
            lines.append(f"* COMMENT: {segment.subtitle.strip()}")
        if segment.shotDescription.strip():
            lines.append(f"* SHOT: {segment.shotDescription.strip()}")
        lines.append("")

    if workspace.rhythmPlan.audioFileName.strip():
        lines.append(f"* BGM FILE: {workspace.rhythmPlan.audioFileName.strip()}")
    if workspace.exportPlan.title.strip():
        lines.append(f"* EXPORT TITLE: {workspace.exportPlan.title.strip()}")

    return "\n".join(lines).rstrip() + "\n"
