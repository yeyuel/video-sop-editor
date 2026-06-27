from __future__ import annotations

import json


def _project_id(client) -> str:
    return client.get("/api/v1/projects").json()["data"][0]["id"]


def _export_json(client, project_id: str) -> dict:
    response = client.post(f"/api/v1/projects/{project_id}/exports/json")
    assert response.status_code == 200
    content = response.json()["data"]["content"]
    payload = json.loads(content)
    assert payload["schemaVersion"] == "1.0"
    return payload


def _first_segment_id(payload: dict) -> str:
    return payload["storyboard"][0]["id"]


def test_export_json_contains_schema_version(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = _project_id(client)
    payload = _export_json(client, project_id)
    assert "exportedAt" in payload
    assert payload["projectId"] == project_id


def test_import_export_json_dry_run_does_not_modify_storyboard(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = _project_id(client)
    payload = _export_json(client, project_id)
    segment_id = _first_segment_id(payload)

    before = client.get(f"/api/v1/projects/{project_id}/storyboard").json()["data"]
    before_subtitle = next(item for item in before["segments"] if item["id"] == segment_id)["subtitle"]

    payload["storyboard"][0]["subtitle"] = "Sprint13 dry-run 字幕"
    dry_run = client.post(
        f"/api/v1/projects/{project_id}/import/export-json",
        json={
            "content": json.dumps(payload, ensure_ascii=False),
            "dryRun": True,
            "conflictStrategy": "overwrite",
            "fields": ["subtitle"],
        },
    )
    assert dry_run.status_code == 200
    result = dry_run.json()["data"]
    assert result["dryRun"] is True
    assert result["applied"] is False
    assert result["updateCount"] >= 1

    after = client.get(f"/api/v1/projects/{project_id}/storyboard").json()["data"]
    after_subtitle = next(item for item in after["segments"] if item["id"] == segment_id)["subtitle"]
    assert after_subtitle == before_subtitle


def test_import_export_json_apply_updates_subtitle(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = _project_id(client)
    payload = _export_json(client, project_id)
    segment_id = _first_segment_id(payload)
    new_subtitle = "Sprint13 applied 字幕"

    for segment in payload["storyboard"]:
        if segment["id"] == segment_id:
            segment["subtitle"] = new_subtitle

    apply_response = client.post(
        f"/api/v1/projects/{project_id}/import/export-json",
        json={
            "content": json.dumps(payload, ensure_ascii=False),
            "dryRun": False,
            "conflictStrategy": "overwrite",
            "fields": ["subtitle"],
        },
    )
    assert apply_response.status_code == 200
    result = apply_response.json()["data"]
    assert result["applied"] is True
    assert result["updateCount"] >= 1

    storyboard = client.get(f"/api/v1/projects/{project_id}/storyboard").json()["data"]
    subtitle = next(item for item in storyboard["segments"] if item["id"] == segment_id)["subtitle"]
    assert subtitle == new_subtitle


def test_import_export_json_round_trip_preserves_segment_ids(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = _project_id(client)
    payload = _export_json(client, project_id)
    original_ids = [item["id"] for item in payload["storyboard"]]

    apply_response = client.post(
        f"/api/v1/projects/{project_id}/import/export-json",
        json={
            "content": json.dumps(payload, ensure_ascii=False),
            "dryRun": False,
            "conflictStrategy": "overwrite",
            "fields": ["subtitle", "function"],
        },
    )
    assert apply_response.status_code == 200

    storyboard = client.get(f"/api/v1/projects/{project_id}/storyboard").json()["data"]
    assert [item["id"] for item in storyboard["segments"]] == original_ids


def test_import_export_csv_dry_run_preview(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = _project_id(client)
    payload = _export_json(client, project_id)
    segment = payload["storyboard"][0]

    csv_content = (
        "segmentId,startTime,endTime,assetId,function,rhythm,beatMode,subtitle\n"
        f"{segment['id']},{segment['startTime']:.2f},{segment['endTime']:.2f},"
        f"{segment['assetId']},{segment['function']},{segment['rhythm']},"
        f"{segment['beatMode']},CSV 导入字幕\n"
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/import/export-csv",
        json={
            "content": csv_content,
            "dryRun": True,
            "conflictStrategy": "overwrite",
            "fields": ["subtitle"],
        },
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["dryRun"] is True
    assert result["updateCount"] >= 1
