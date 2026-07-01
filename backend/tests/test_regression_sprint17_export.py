from __future__ import annotations

import json
from pathlib import Path


def test_export_capcut_endpoint(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = "proj_001"

    response = client.post(f"/api/v1/projects/{project_id}/exports/capcut")
    assert response.status_code == 200
    document = response.json()["data"]
    assert document["format"] == "capcut"
    assert document["fileName"].endswith(".capcut-draft.json")
    bundle = json.loads(document["content"])
    assert bundle["targetApp"] == "jianying"
    assert "sections" in bundle
    draft = bundle["sections"]["draft_content.json"]
    assert draft["tracks"][0]["type"] == "video"
    assert len(draft["tracks"][0]["segments"]) >= 1
    assert "五月台州，先在国清寺安静下来" in document["content"]


def test_capcut_defaults_endpoint(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/projects/proj_001/exports/capcut-defaults")
    assert response.status_code == 200
    defaults = response.json()["data"]
    assert "defaultDraftRoot" in defaults
    assert "effectiveDraftRoot" in defaults


def test_capcut_deploy_endpoint(regression_env: dict, tmp_path: Path) -> None:
    client = regression_env["client"]
    project_id = "proj_001"
    draft_root = tmp_path / "jianying-drafts"
    draft_root.mkdir()

    response = client.post(
        f"/api/v1/projects/{project_id}/exports/capcut/deploy",
        json={"jianyingDraftRoot": str(draft_root), "persistConfig": True},
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["files"] == ["draft_content.json", "draft_meta_info.json"]
    folder = Path(result["draftFolderPath"])
    assert folder.is_dir()
    assert (folder / "draft_content.json").is_file()
    assert (folder / "draft_meta_info.json").is_file()


def test_export_edl_endpoint(regression_env: dict) -> None:
    client = regression_env["client"]
    project_id = "proj_001"

    response = client.post(f"/api/v1/projects/{project_id}/exports/edl")
    assert response.status_code == 200
    document = response.json()["data"]
    assert document["format"] == "edl"
    assert document["fileName"].endswith(".edl")
    content = document["content"]
    assert content.startswith("TITLE:")
    assert "001  国清寺_006" in content
    assert "* FROM CLIP NAME:" in content
    assert "五月台州，先在国清寺安静下来" in content
