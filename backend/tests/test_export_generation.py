from app.models.schemas import StoryboardSegmentRead
from app.services.export_generation import (
    apply_export_captions_to_segments,
    merge_storyboard_subtitle_updates,
    resolve_platform_export_guide,
)


def _segment(segment_id: str, subtitle: str = "原字幕") -> StoryboardSegmentRead:
    return StoryboardSegmentRead(
        id=segment_id,
        startTime=0.0,
        endTime=1.0,
        assetId="HEMU_001",
        shotDescription="测试镜头",
        function="supporting",
        rhythm="balanced",
        beatMode="none",
        beatPoints=[0.0, 1.0],
        subtitle=subtitle,
    )


def test_resolve_platform_export_guide_for_douyin() -> None:
    guide = resolve_platform_export_guide("抖音短视频")

    assert guide["label"] == "抖音"
    assert "钩子" in guide["titleStyle"]


def test_apply_export_captions_to_segments_updates_matching_ids() -> None:
    segments = [_segment("seg_a", "旧文案"), _segment("seg_b", "保留")]

    updates, count = apply_export_captions_to_segments(
        segments,
        [{"segmentId": "seg_a", "subtitle": "新文案"}, {"segmentId": "missing", "subtitle": "忽略"}],
    )

    assert count == 1
    assert len(updates) == 1
    assert updates[0].id == "seg_a"
    assert updates[0].subtitle == "新文案"


def test_merge_storyboard_subtitle_updates_preserves_order() -> None:
    segments = [_segment("seg_a", "旧文案"), _segment("seg_b", "保留")]
    updates, _ = apply_export_captions_to_segments(
        segments,
        [{"segmentId": "seg_a", "subtitle": "新文案"}],
    )

    merged = merge_storyboard_subtitle_updates(segments, updates)

    assert [item.id for item in merged] == ["seg_a", "seg_b"]
    assert merged[0].subtitle == "新文案"
    assert merged[1].subtitle == "保留"
