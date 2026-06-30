from __future__ import annotations


def _project_payload(client, project_id: str) -> dict:
    return client.get(f"/api/v1/projects/{project_id}").json()["data"]


def test_project_allow_asset_reuse_defaults_false(regression_env: dict) -> None:
    client = regression_env["client"]
    project = _project_payload(client, "proj_001")
    assert project["allowAssetReuse"] is False


def test_project_update_allow_asset_reuse(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = "proj_001"
    payload = _project_payload(client, project_id)
    payload["allowAssetReuse"] = True

    response = client.put(f"/api/v1/projects/{project_id}", json=payload)
    assert response.status_code == 200
    assert response.json()["data"]["allowAssetReuse"] is True

    payload["allowAssetReuse"] = False
    reset = client.put(f"/api/v1/projects/{project_id}", json=payload)
    assert reset.status_code == 200
    assert reset.json()["data"]["allowAssetReuse"] is False


def test_storyboard_generate_without_reuse_uses_each_asset_once(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = "proj_001"
    request_body = {
        "themeId": "theme_001",
        "alignToBeat": False,
    }

    response = client.post(
        f"/api/v1/projects/{project_id}/storyboard:generate",
        json=request_body,
    )
    assert response.status_code == 200
    bundle = response.json()["data"]
    asset_ids = [segment["assetId"] for segment in bundle["segments"]]
    assert len(asset_ids) == len(set(asset_ids))
    assert bundle["validation"]["assetReuseEnabled"] is False
    assert bundle["validation"]["reusedAssetCount"] == 0


def test_storyboard_generate_with_reuse_cycles_assets(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = "proj_001"
    payload = _project_payload(client, project_id)
    payload["allowAssetReuse"] = True
    update = client.put(f"/api/v1/projects/{project_id}", json=payload)
    assert update.status_code == 200

    response = client.post(
        f"/api/v1/projects/{project_id}/storyboard:generate",
        json={
            "themeId": "theme_001",
            "alignToBeat": False,
        },
    )
    assert response.status_code == 200
    bundle = response.json()["data"]
    asset_ids = [segment["assetId"] for segment in bundle["segments"]]
    assert len(asset_ids) > len(set(asset_ids))
    validation = bundle["validation"]
    assert validation["assetReuseEnabled"] is True
    assert validation["reusedAssetCount"] >= 1
    assert validation["reusedSegmentCount"] >= 1
    assert any("复用" in issue for issue in validation["issues"])

    payload["allowAssetReuse"] = False
    client.put(f"/api/v1/projects/{project_id}", json=payload)
