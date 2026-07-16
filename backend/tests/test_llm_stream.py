from __future__ import annotations

import json


def _parse_sse_events(body: str) -> list[dict]:
    events: list[dict] = []
    for chunk in body.split("\n\n"):
        line = next(
            (item.strip() for item in chunk.splitlines() if item.strip().startswith("data: ")),
            None,
        )
        if not line:
            continue
        events.append(json.loads(line.removeprefix("data: ").strip()))
    return events


def _project_id(client) -> str:
    return client.get("/api/v1/projects").json()["data"][0]["id"]


def test_theme_generate_llm_stream_returns_sse_complete(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = _project_id(client)

    response = client.post(
        f"/api/v1/projects/{project_id}/themes/generate-llm/stream",
        json={"count": 3},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    events = _parse_sse_events(response.text)
    task_event = next(event for event in events if event.get("type") == "task")
    assert task_event["taskId"].startswith("llm_task_")
    assert any(event.get("type") == "progress" for event in events)
    complete = next(event for event in events if event.get("type") == "complete")
    assert isinstance(complete.get("data"), list)
    assert len(complete["data"]) >= 1
    assert complete["meta"]["llmStatus"] in {
        "success",
        "fallback_rule",
        "not_configured",
        "timeout",
        "network",
        "empty_response",
        "parse_error",
        "http_error",
    }

    task_response = client.get(f"/api/v1/llm/tasks/{task_event['taskId']}")
    assert task_response.status_code == 200
    task_snapshot = task_response.json()["data"]
    assert task_snapshot["status"] == "completed"
    assert task_snapshot["progress"] == 100
    assert isinstance(task_snapshot["data"], list)


def test_completed_llm_task_cancel_is_idempotent(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = _project_id(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/themes/generate-llm/stream",
        json={"count": 3},
    )
    events = _parse_sse_events(response.text)
    task_id = next(event["taskId"] for event in events if event.get("type") == "task")

    cancel_response = client.post(f"/api/v1/llm/tasks/{task_id}/cancel")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["data"]["status"] == "completed"


def test_storyboard_generate_llm_stream_returns_sse_complete(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = _project_id(client)

    response = client.post(
        f"/api/v1/projects/{project_id}/storyboard/generate-llm/stream",
        json={"themeId": "theme_001", "alignToBeat": True},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    complete = next(event for event in events if event.get("type") == "complete")
    assert "segments" in complete["data"]
    assert "validation" in complete["data"]
    assert "llmStatus" in complete["meta"]


def test_export_plan_suggest_stream_returns_sse_complete(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = _project_id(client)

    response = client.post(f"/api/v1/projects/{project_id}/export-plan/suggest/stream")

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    complete = next(event for event in events if event.get("type") == "complete")
    assert complete["data"]["title"]
    assert "llmStatus" in complete["meta"]


def test_rhythm_plan_generate_stream_returns_sse_complete(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = _project_id(client)

    response = client.post(f"/api/v1/projects/{project_id}/rhythm-plan/generate/stream")

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    complete = next(event for event in events if event.get("type") == "complete")
    assert complete["data"]["recommendedBgm"]
    assert "llmStatus" in complete["meta"]
