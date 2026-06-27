from __future__ import annotations

import json

from app.models.schemas import (
    ExportPlanRead,
    ExportValidationRead,
    ProjectRead,
    RhythmPlanRead,
    StoryboardSegmentRead,
    StoryboardValidationRead,
    WorkspaceDataRead,
)
from app.services.export_generation import EXPORT_JSON_SCHEMA_VERSION, render_export_content
from app.services.export_import import (
    apply_storyboard_import_plan,
    build_storyboard_import_plan,
    parse_export_csv_document,
    parse_export_json_document,
    segments_from_export_json,
)


def _segment(segment_id: str, subtitle: str = "原字幕", function: str = "supporting") -> StoryboardSegmentRead:
    return StoryboardSegmentRead(
        id=segment_id,
        startTime=0.0,
        endTime=1.0,
        assetId="HEMU_001",
        shotDescription="测试镜头",
        function=function,
        rhythm="balanced",
        beatMode="none",
        beatPoints=[0.0, 1.0],
        subtitle=subtitle,
    )


def test_parse_export_json_document_requires_storyboard() -> None:
    payload, errors = parse_export_json_document('{"schemaVersion":"1.0"}')
    assert payload["schemaVersion"] == "1.0"
    assert any("storyboard" in item for item in errors)


def test_build_storyboard_import_plan_overwrite_subtitle() -> None:
    current = [_segment("seg_a", "旧文案"), _segment("seg_b", "保留")]
    incoming, _ = segments_from_export_json(
        {"storyboard": [{"id": "seg_a", "subtitle": "新文案"}, {"id": "seg_b", "subtitle": "保留"}]}
    )

    plan = build_storyboard_import_plan(
        current_segments=current,
        incoming_segments=incoming,
        fields=["subtitle"],
        conflict_strategy="overwrite",
    )

    assert plan.updateCount == 1
    assert plan.changes[0].action == "update"
    assert plan.changes[0].incomingValue == "新文案"


def test_build_storyboard_import_plan_skip_nonempty_current() -> None:
    current = [_segment("seg_a", "旧文案")]
    incoming, _ = segments_from_export_json({"storyboard": [{"id": "seg_a", "subtitle": "新文案"}]})

    plan = build_storyboard_import_plan(
        current_segments=current,
        incoming_segments=incoming,
        fields=["subtitle"],
        conflict_strategy="skip",
    )

    assert plan.updateCount == 0
    assert plan.skippedCount == 1
    assert plan.changes[0].action == "skip"


def test_apply_storyboard_import_plan_updates_only_marked_fields() -> None:
    current = [_segment("seg_a", "旧文案", "supporting")]
    incoming, _ = segments_from_export_json(
        {"storyboard": [{"id": "seg_a", "subtitle": "新文案", "function": "opening"}]}
    )
    plan = build_storyboard_import_plan(
        current_segments=current,
        incoming_segments=incoming,
        fields=["subtitle", "function"],
        conflict_strategy="overwrite",
    )

    merged = apply_storyboard_import_plan(current, plan)

    assert merged[0].subtitle == "新文案"
    assert merged[0].function == "opening"


def test_parse_export_csv_document_with_default_columns() -> None:
    content = (
        "segmentId,startTime,endTime,assetId,function,rhythm,beatMode,subtitle\n"
        "seg_a,0.00,1.00,HEMU_001,supporting,balanced,none,新字幕\n"
    )
    segments, errors = parse_export_csv_document(content)

    assert not errors
    assert len(segments) == 1
    assert segments[0].segment_id == "seg_a"
    assert segments[0].subtitle == "新字幕"


def test_render_export_content_includes_schema_version() -> None:
    workspace = WorkspaceDataRead(
        project=ProjectRead(
            id="proj_test",
            name="测试",
            destination="阿勒泰",
            platform="小红书",
            targetDurationSec=60,
            videoType="vlog",
            stylePreference="治愈",
            styleNotes="",
            routeText="",
            mediaRoot="",
            status="active",
            selectedThemeId="theme_1",
            validateLocationOrder=False,
        ),
        assets=[],
        themes=[],
        storyboard=[_segment("seg_a")],
        storyboardValidation=StoryboardValidationRead(
            allSegmentsBoundToAsset=True,
            locationContinuityPassed=True,
            beatAlignmentPassed=True,
            beatAdaptationEnabled=False,
            totalDurationSec=1.0,
            targetDurationReached=True,
        ),
        exportValidation=ExportValidationRead(
            destinationMentioned=True,
            themeConsistencyPassed=True,
        ),
        rhythmPlan=RhythmPlanRead(
            bgmStyle="",
            selectedTrackName="",
            audioFileName="",
            analysisSource="manual",
            analysisNotes=[],
            detectedBpm=0,
            audioDurationSec=0.0,
            rawBeatPoints=[],
            coarseBeatPoints=[],
            beatMode="none",
            beatPoints=[],
            rhythmNotes=[],
            darkCutSuggestions=[],
            photoMotionSuggestions=[],
        ),
        exportPlan=ExportPlanRead(
            title="标题",
            shortTitle="",
            description="描述",
            tags=[],
            coverSuggestion="",
        ),
    )

    content = render_export_content(workspace, "json")
    payload = json.loads(content)

    assert payload["schemaVersion"] == EXPORT_JSON_SCHEMA_VERSION
    assert payload["projectId"] == "proj_test"
    assert payload["storyboard"][0]["id"] == "seg_a"
