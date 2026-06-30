from __future__ import annotations


def _project_id(client) -> str:
    return client.get("/api/v1/projects").json()["data"][0]["id"]


def _first_asset_id(client, project_id: str) -> str:
    assets = client.get(f"/api/v1/projects/{project_id}/assets").json()["data"]
    assert assets
    return assets[0]["assetId"]


def test_asset_vision_capability_endpoint(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = _project_id(client)

    response = client.get(f"/api/v1/projects/{project_id}/assets/vision-capability")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert "supportsVision" in payload
    assert "model" in payload
    assert "providerId" in payload


def test_llm_live_models_endpoint(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/llm/providers/kimi/models?live=false")
    assert response.status_code == 200
    models = response.json()["data"]
    assert any(item["modelId"] == "kimi-k2.6" for item in models)
    k26 = next(item for item in models if item["modelId"] == "kimi-k2.6")
    assert k26["supportsVision"] is True
    v1 = next(item for item in models if item["modelId"] == "moonshot-v1-8k")
    assert v1["supportsVision"] is False


def test_asset_vision_analyze_mock_stream(regression_env: dict, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.vision_use_mock", True)

    client = regression_env["client"]
    project_id = _project_id(client)
    asset_id = _first_asset_id(client, project_id)

    response = client.post(
        f"/api/v1/projects/{project_id}/assets/{asset_id}/vision-analyze/stream",
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 200
    body = response.text
    assert "event-stream" in response.headers.get("content-type", "") or "text/event-stream" in body or '"type": "complete"' in body or '"type": "progress"' in body
    assert "complete" in body
    assert "prefilledFields" in body

    asset = client.get(f"/api/v1/projects/{project_id}/assets/{asset_id}").json()["data"]
    assert asset["visionAnalysisStatus"] in {"ready", "failed"}
    if asset["visionAnalysisStatus"] == "ready":
        assert len(asset["visionPrefilledFields"]) >= 3
        assert asset["scene"].strip()
        assert asset["emotionTags"]
        assert asset["visualTags"]


def test_asset_vision_analyze_reuses_same_file_cache(regression_env: dict, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.vision_use_mock", True)

    client = regression_env["client"]
    project_id = _project_id(client)
    source_asset_id = _first_asset_id(client, project_id)
    source_asset = client.get(f"/api/v1/projects/{project_id}/assets/{source_asset_id}").json()["data"]

    first = client.post(
        f"/api/v1/projects/{project_id}/assets/{source_asset_id}/vision-analyze/stream",
        headers={"Accept": "text/event-stream"},
    )
    assert first.status_code == 200
    assert "complete" in first.text

    duplicate = client.post(
        f"/api/v1/projects/{project_id}/assets",
        json={
            "location": source_asset["location"],
            "scene": "",
            "relativePath": source_asset["relativePath"],
            "mediaType": source_asset["mediaType"],
            "shotType": "wide",
            "emotionTags": [],
            "visualTags": [],
            "informationDensity": "medium",
            "suggestedDurationSec": 2.0,
            "functionTags": [],
        },
    )
    assert duplicate.status_code == 200
    duplicate_asset_id = duplicate.json()["data"]["assetId"]

    second = client.post(
        f"/api/v1/projects/{project_id}/assets/{duplicate_asset_id}/vision-analyze/stream",
        headers={"Accept": "text/event-stream"},
    )
    assert second.status_code == 200
    assert "cache_hit" in second.text
    assert "命中同文件 Vision 缓存" in second.text

    duplicate_asset = client.get(
        f"/api/v1/projects/{project_id}/assets/{duplicate_asset_id}"
    ).json()["data"]
    assert duplicate_asset["visionAnalysisStatus"] == "ready"
    assert len(duplicate_asset["visionPrefilledFields"]) >= 3
