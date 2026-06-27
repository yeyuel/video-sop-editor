from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from io import StringIO
from typing import Literal

from app.models.schemas import ExportImportChangeRead, ExportImportResultRead, StoryboardSegmentRead
from app.services.storyboard_generation import segment_read_to_write

EXPORT_JSON_SCHEMA_VERSION = "1.0"

ImportField = Literal["subtitle", "function"]
ConflictStrategy = Literal["overwrite", "skip"]

SUPPORTED_IMPORT_FIELDS: tuple[ImportField, ...] = ("subtitle", "function")
DEFAULT_CSV_COLUMNS: dict[str, str] = {
    "segmentId": "segmentId",
    "startTime": "startTime",
    "endTime": "endTime",
    "assetId": "assetId",
    "function": "function",
    "rhythm": "rhythm",
    "beatMode": "beatMode",
    "subtitle": "subtitle",
}


@dataclass
class ParsedImportSegment:
    segment_id: str
    subtitle: str | None = None
    function: str | None = None


def parse_export_json_document(content: str) -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        return {}, [f"JSON 解析失败：{exc.msg}"]

    if not isinstance(payload, dict):
        return {}, ["导出 JSON 根节点必须是 object。"]

    schema_version = str(payload.get("schemaVersion", "")).strip()
    if schema_version and schema_version != EXPORT_JSON_SCHEMA_VERSION:
        errors.append(
            f"不支持的 schemaVersion：{schema_version}（当前支持 {EXPORT_JSON_SCHEMA_VERSION}）。"
        )

    storyboard = payload.get("storyboard")
    if not isinstance(storyboard, list):
        errors.append("缺少 storyboard 数组。")
        return payload, errors

    return payload, errors


def parse_export_csv_document(
    content: str,
    *,
    column_map: dict[str, str] | None = None,
) -> tuple[list[ParsedImportSegment], list[str]]:
    errors: list[str] = []
    if not content.strip():
        return [], ["CSV 内容为空。"]

    reader = csv.DictReader(StringIO(content))
    if not reader.fieldnames:
        return [], ["CSV 缺少表头行。"]

    resolved_map = {**DEFAULT_CSV_COLUMNS, **(column_map or {})}
    header_lookup = {name.strip(): name for name in reader.fieldnames if name}
    missing_required = [
        logical
        for logical in ("segmentId", "subtitle")
        if resolved_map[logical] not in header_lookup
    ]
    if missing_required:
        return [], [f"CSV 缺少必要列：{', '.join(missing_required)}。"]

    segments: list[ParsedImportSegment] = []
    for row_index, row in enumerate(reader, start=2):
        segment_id = _cell(row, header_lookup, resolved_map["segmentId"])
        if not segment_id:
            errors.append(f"第 {row_index} 行缺少 segmentId，已跳过。")
            continue
        segments.append(
            ParsedImportSegment(
                segment_id=segment_id,
                subtitle=_optional_cell(row, header_lookup, resolved_map.get("subtitle", "subtitle")),
                function=_optional_cell(row, header_lookup, resolved_map.get("function", "function")),
            )
        )

    if not segments:
        errors.append("CSV 未解析到有效分镜行。")
    return segments, errors


def build_storyboard_import_plan(
    *,
    current_segments: list[StoryboardSegmentRead],
    incoming_segments: list[ParsedImportSegment],
    fields: list[str],
    conflict_strategy: ConflictStrategy,
) -> ExportImportResultRead:
    normalized_fields = _normalize_fields(fields)
    current_by_id = {segment.id: segment for segment in current_segments}
    changes: list[ExportImportChangeRead] = []
    unknown_segment_ids: list[str] = []
    seen_ids: set[str] = set()

    for incoming in incoming_segments:
        if incoming.segment_id in seen_ids:
            continue
        seen_ids.add(incoming.segment_id)

        current = current_by_id.get(incoming.segment_id)
        if not current:
            unknown_segment_ids.append(incoming.segment_id)
            continue

        for field in normalized_fields:
            incoming_value = _incoming_field_value(incoming, field)
            if incoming_value is None:
                continue

            current_value = _segment_field_value(current, field)
            if incoming_value == current_value:
                changes.append(
                    ExportImportChangeRead(
                        segmentId=incoming.segment_id,
                        field=field,
                        currentValue=current_value,
                        incomingValue=incoming_value,
                        action="unchanged",
                    )
                )
                continue

            action = _resolve_action(
                conflict_strategy=conflict_strategy,
                current_value=current_value,
            )
            changes.append(
                ExportImportChangeRead(
                    segmentId=incoming.segment_id,
                    field=field,
                    currentValue=current_value,
                    incomingValue=incoming_value,
                    action=action,
                )
            )

    update_count = sum(1 for item in changes if item.action == "update")
    skipped_count = sum(1 for item in changes if item.action == "skip")
    unchanged_count = sum(1 for item in changes if item.action == "unchanged")

    return ExportImportResultRead(
        schemaVersion=EXPORT_JSON_SCHEMA_VERSION,
        dryRun=True,
        applied=False,
        fields=normalized_fields,
        conflictStrategy=conflict_strategy,
        changes=changes,
        updateCount=update_count,
        skippedCount=skipped_count,
        unchangedCount=unchanged_count,
        unknownSegmentIds=unknown_segment_ids,
        errors=[],
    )


def segments_from_export_json(payload: dict[str, object]) -> tuple[list[ParsedImportSegment], list[str]]:
    storyboard = payload.get("storyboard")
    if not isinstance(storyboard, list):
        return [], ["缺少 storyboard 数组。"]

    segments: list[ParsedImportSegment] = []
    errors: list[str] = []
    for index, item in enumerate(storyboard, start=1):
        if not isinstance(item, dict):
            errors.append(f"storyboard[{index - 1}] 不是 object，已跳过。")
            continue
        segment_id = str(item.get("id", "")).strip()
        if not segment_id:
            errors.append(f"storyboard[{index - 1}] 缺少 id，已跳过。")
            continue
        segments.append(
            ParsedImportSegment(
                segment_id=segment_id,
                subtitle=_optional_str(item.get("subtitle")),
                function=_optional_str(item.get("function")),
            )
        )
    return segments, errors


def apply_storyboard_import_plan(
    current_segments: list[StoryboardSegmentRead],
    plan: ExportImportResultRead,
) -> list:
    from app.models.schemas import StoryboardSegmentWrite

    update_map: dict[str, dict[str, str]] = {}
    for change in plan.changes:
        if change.action != "update":
            continue
        update_map.setdefault(change.segmentId, {})[change.field] = change.incomingValue

    merged: list[StoryboardSegmentWrite] = []
    for segment in current_segments:
        write = segment_read_to_write(segment)
        field_updates = update_map.get(segment.id)
        if field_updates:
            if "subtitle" in field_updates:
                write.subtitle = field_updates["subtitle"]
            if "function" in field_updates:
                write.function = field_updates["function"]
        merged.append(write)
    return merged


def finalize_import_result(
    plan: ExportImportResultRead,
    *,
    dry_run: bool,
    applied: bool,
    errors: list[str] | None = None,
) -> ExportImportResultRead:
    merged_errors = [*plan.errors, *(errors or [])]
    return plan.model_copy(
        update={
            "dryRun": dry_run,
            "applied": applied,
            "errors": merged_errors,
        }
    )


def _normalize_fields(fields: list[str]) -> list[ImportField]:
    normalized: list[ImportField] = []
    for field in fields:
        if field in SUPPORTED_IMPORT_FIELDS and field not in normalized:
            normalized.append(field)  # type: ignore[arg-type]
    return normalized or ["subtitle"]


def _resolve_action(*, conflict_strategy: ConflictStrategy, current_value: str) -> str:
    if conflict_strategy == "skip" and current_value.strip():
        return "skip"
    return "update"


def _segment_field_value(segment: StoryboardSegmentRead, field: ImportField) -> str:
    if field == "subtitle":
        return segment.subtitle
    return segment.function


def _incoming_field_value(segment: ParsedImportSegment, field: ImportField) -> str | None:
    if field == "subtitle":
        return segment.subtitle
    return segment.function


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(row: dict[str, str], header_lookup: dict[str, str], logical_name: str) -> str:
    header = header_lookup.get(logical_name, logical_name)
    return (row.get(header) or "").strip()


def _optional_cell(
    row: dict[str, str],
    header_lookup: dict[str, str],
    logical_name: str | None,
) -> str | None:
    if not logical_name:
        return None
    value = _cell(row, header_lookup, logical_name)
    return value or None
