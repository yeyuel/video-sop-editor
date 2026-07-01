"""Phase 3 acceptance freeze — validates locked decisions and closure smoke."""

from __future__ import annotations

import json
from pathlib import Path

from app.migrations.runner import MIGRATIONS


def _login(client, *, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["data"]["sessionToken"]


def test_phase3_migrations_frozen_at_latest_version() -> None:
    assert len(MIGRATIONS) >= 17
    assert MIGRATIONS[-1][0] == len(MIGRATIONS)


def test_decision1_editor_can_export_but_not_manage_users(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client, username="editor", password="edit123")
    headers = {"X-Session-Token": token}

    workspace = client.get("/api/v1/projects/proj_001/workspace", headers=headers)
    assert workspace.status_code == 200

    export_preview = client.post("/api/v1/projects/proj_001/exports/json", headers=headers)
    assert export_preview.status_code == 200

    users = client.get("/api/v1/auth/users", headers=headers)
    assert users.status_code == 403


def test_decision2_vision_mock_prefills_fields(regression_env: dict, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.vision_use_mock", True)

    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]
    asset_id = client.get(f"/api/v1/projects/{project_id}/assets").json()["data"][0]["assetId"]

    response = client.post(
        f"/api/v1/projects/{project_id}/assets/{asset_id}/vision-analyze/stream",
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 200
    assert "complete" in response.text

    asset = client.get(f"/api/v1/projects/{project_id}/assets/{asset_id}").json()["data"]
    assert asset["visionAnalysisStatus"] == "ready"
    assert len(asset["visionPrefilledFields"]) >= 3


def test_decision3_allow_asset_reuse_toggle(regression_env: dict) -> None:
    client = regression_env["client"]
    project = client.get("/api/v1/projects/proj_001").json()["data"]
    assert project["allowAssetReuse"] is False

    project["allowAssetReuse"] = True
    updated = client.put("/api/v1/projects/proj_001", json=project)
    assert updated.status_code == 200
    assert updated.json()["data"]["allowAssetReuse"] is True


def test_decision4_oauth_mock_authorizes_openai(regression_env: dict) -> None:
    client = regression_env["client"]
    start = client.post("/api/v1/llm/providers/openai/oauth/start").json()["data"]
    callback = client.post(
        "/api/v1/llm/providers/openai/oauth/callback",
        json={"code": "mock_authorization_code", "state": start["state"]},
    )
    assert callback.status_code == 200
    status = callback.json()["data"]
    assert status["authType"] == "oauth"
    assert status["status"] == "authorized"


def test_decision5_sqlite_session_without_redis_dependency() -> None:
    requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
    content = requirements.read_text(encoding="utf-8").lower()
    assert "redis" not in content


def test_phase3_export_json_round_trip(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = "proj_001"

    export_doc = client.post(f"/api/v1/projects/{project_id}/exports/json").json()["data"]
    bundle = json.loads(export_doc["content"])
    assert bundle["schemaVersion"] == "1.0"

    segment_id = client.get(f"/api/v1/projects/{project_id}/storyboard").json()["data"]["segments"][0]["id"]
    incoming = json.dumps(
        {
            "schemaVersion": "1.0",
            "storyboard": [
                {
                    "id": segment_id,
                    "subtitle": "三期验收字幕写回测试",
                }
            ],
        },
        ensure_ascii=False,
    )
    dry_run = client.post(
        f"/api/v1/projects/{project_id}/import/export-json",
        json={"content": incoming, "dryRun": True, "fields": ["subtitle"]},
    )
    assert dry_run.status_code == 200
    assert dry_run.json()["data"]["dryRun"] is True


def test_phase3_capcut_deploy_writes_draft_files(regression_env: dict, tmp_path: Path) -> None:
    client = regression_env["client"]
    draft_root = tmp_path / "jianying-drafts"
    draft_root.mkdir()

    response = client.post(
        "/api/v1/projects/proj_001/exports/capcut/deploy",
        json={"jianyingDraftRoot": str(draft_root), "persistConfig": False},
    )
    assert response.status_code == 200
    result = response.json()["data"]
    folder = Path(result["draftFolderPath"])
    draft = json.loads((folder / "draft_content.json").read_text(encoding="utf-8"))
    text_material = draft["materials"]["texts"][0]
    content = json.loads(text_material["content"])
    assert content["styles"][0]["font"]["id"] == "6740436145831678467"
