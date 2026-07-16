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
