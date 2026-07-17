from __future__ import annotations

import json


def _parse_sse_events(body: str) -> list[dict]:
    events: list[dict] = []
    for chunk in body.split("\n\n"):
        line = next(
            (item.strip() for item in chunk.splitlines() if item.strip().startswith("data: ")),
            None,
        )
        if line:
            events.append(json.loads(line.removeprefix("data: ").strip()))
    return events


def test_one_click_rough_cut_returns_resumable_result(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]

    response = client.post(f"/api/v1/projects/{project_id}/rough-cut/generate/stream")

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert any(event.get("type") == "task" for event in events)
    complete = next(event for event in events if event.get("type") == "complete")
    assert complete["data"]["status"] in {"waiting_audio", "completed"}
    assert "theme" in complete["data"]["completedSteps"]
    assert complete["data"]["nextPath"].startswith(f"/projects/{project_id}/")

    task_id = next(event["taskId"] for event in events if event.get("type") == "task")
    snapshot = client.get(f"/api/v1/llm/tasks/{task_id}").json()["data"]
    assert snapshot["status"] == "completed"
    assert snapshot["data"]["status"] == complete["data"]["status"]


def test_partial_storyboard_rerun_preserves_timeline_and_saves_versions(
    regression_env: dict,
) -> None:
    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]
    before = client.get(f"/api/v1/projects/{project_id}/workspace").json()["data"]
    segments = before["storyboard"]
    assert len(segments) >= 4
    selected_ids = [segments[1]["id"], segments[2]["id"]]

    response = client.post(
        f"/api/v1/projects/{project_id}/storyboard/rerun-partial/stream",
        json={"segmentIds": selected_ids, "instruction": "保持路线顺序，增强过渡"},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    complete = next(event for event in events if event.get("type") == "complete")
    after_segments = complete["data"]["segments"]
    assert len(after_segments) == len(segments)
    assert after_segments[0] == segments[0]
    assert after_segments[3:] == segments[3:]
    for before_segment, after_segment in zip(segments[1:3], after_segments[1:3]):
        for key in ("id", "startTime", "endTime", "beatMode", "beatPoints", "function", "attentionRole"):
            assert after_segment[key] == before_segment[key]

    after = client.get(f"/api/v1/projects/{project_id}/workspace").json()["data"]
    assert after["rhythmPlan"] == before["rhythmPlan"]
    versions = client.get(
        f"/api/v1/projects/{project_id}/rough-cut/versions"
    ).json()["data"]
    assert {item["generationMode"] for item in versions} >= {
        "pre_rerun_storyboard_range",
        "rerun_storyboard_range",
    }


def test_partial_storyboard_rerun_rejects_non_contiguous_range_without_version(
    regression_env: dict,
) -> None:
    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]
    segments = client.get(
        f"/api/v1/projects/{project_id}/storyboard"
    ).json()["data"]["segments"]
    versions_before = client.get(
        f"/api/v1/projects/{project_id}/rough-cut/versions"
    ).json()["data"]

    response = client.post(
        f"/api/v1/projects/{project_id}/storyboard/rerun-partial/stream",
        json={"segmentIds": [segments[0]["id"], segments[2]["id"]]},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    error = next(event for event in events if event.get("type") == "error")
    assert "连续" in error["message"]
    versions_after = client.get(
        f"/api/v1/projects/{project_id}/rough-cut/versions"
    ).json()["data"]
    assert len(versions_after) == len(versions_before)


def test_regenerate_creative_keeps_real_rhythm_and_saves_versions(
    regression_env: dict,
) -> None:
    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]
    before = client.get(f"/api/v1/projects/{project_id}/workspace").json()["data"]
    before_rhythm = before["rhythmPlan"]

    response = client.post(
        f"/api/v1/projects/{project_id}/rough-cut/generate/stream",
        json={"mode": "regenerate_creative"},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    complete = next(event for event in events if event.get("type") == "complete")
    assert complete["data"]["status"] == "completed"
    assert complete["data"]["generationMode"] == "regenerate_creative"
    assert complete["data"]["baselineVersionId"]
    assert complete["data"]["generatedVersionId"]
    assert complete["data"]["preservedAudioRhythm"] is True

    after = client.get(f"/api/v1/projects/{project_id}/workspace").json()["data"]
    after_rhythm = after["rhythmPlan"]
    for key in (
        "audioFileName",
        "analysisSource",
        "selectedBgmId",
        "beatPoints",
        "beatCalibration",
    ):
        assert after_rhythm[key] == before_rhythm[key]

    versions = client.get(
        f"/api/v1/projects/{project_id}/rough-cut/versions"
    ).json()["data"]
    assert len(versions) >= 2
    assert {item["generationMode"] for item in versions} >= {
        "baseline",
        "regenerate_creative",
    }


def test_restore_version_reverts_creative_plan_and_preserves_rhythm(
    regression_env: dict,
) -> None:
    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]
    response = client.post(
        f"/api/v1/projects/{project_id}/rough-cut/generate/stream",
        json={"mode": "regenerate_creative"},
    )
    events = _parse_sse_events(response.text)
    complete = next(event for event in events if event.get("type") == "complete")
    version_id = complete["data"]["generatedVersionId"]

    generated_workspace = client.get(
        f"/api/v1/projects/{project_id}/workspace"
    ).json()["data"]
    original_title = generated_workspace["exportPlan"]["title"]
    original_rhythm = generated_workspace["rhythmPlan"]
    changed_export = {
        **generated_workspace["exportPlan"],
        "title": "人工修改后的对比标题",
    }
    save_response = client.put(
        f"/api/v1/projects/{project_id}/export-plan",
        json=changed_export,
    )
    assert save_response.status_code == 200

    versions_before = client.get(
        f"/api/v1/projects/{project_id}/rough-cut/versions"
    ).json()["data"]
    target = next(item for item in versions_before if item["id"] == version_id)
    assert target["diff"]["exportTitleChanged"] is True

    restore_response = client.post(
        f"/api/v1/projects/{project_id}/rough-cut/versions/{version_id}/restore",
        json={},
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["data"]["backupVersionId"]

    restored_workspace = client.get(
        f"/api/v1/projects/{project_id}/workspace"
    ).json()["data"]
    assert restored_workspace["exportPlan"]["title"] == original_title
    for key in (
        "audioFileName",
        "analysisSource",
        "selectedBgmId",
        "beatPoints",
        "beatCalibration",
    ):
        assert restored_workspace["rhythmPlan"][key] == original_rhythm[key]

    versions_after = client.get(
        f"/api/v1/projects/{project_id}/rough-cut/versions"
    ).json()["data"]
    assert {item["generationMode"] for item in versions_after} >= {
        "pre_restore",
        "restore",
    }


def test_single_step_export_rerun_preserves_storyboard_and_rhythm(
    regression_env: dict,
) -> None:
    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]
    before = client.get(f"/api/v1/projects/{project_id}/workspace").json()["data"]

    response = client.post(
        f"/api/v1/projects/{project_id}/rough-cut/rerun/export/stream",
        json={},
    )
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    complete = next(event for event in events if event.get("type") == "complete")
    assert complete["data"]["status"] == "completed"
    assert complete["data"]["rerunStep"] == "export"
    assert complete["data"]["baselineVersionId"]
    assert complete["data"]["generatedVersionId"]

    after = client.get(f"/api/v1/projects/{project_id}/workspace").json()["data"]
    assert [item["id"] for item in after["storyboard"]] == [
        item["id"] for item in before["storyboard"]
    ]
    assert after["rhythmPlan"]["beatPoints"] == before["rhythmPlan"]["beatPoints"]
    assert after["rhythmPlan"]["beatCalibration"] == before["rhythmPlan"]["beatCalibration"]

    versions = client.get(
        f"/api/v1/projects/{project_id}/rough-cut/versions"
    ).json()["data"]
    assert {item["generationMode"] for item in versions} >= {
        "pre_rerun_export",
        "rerun_export",
    }
