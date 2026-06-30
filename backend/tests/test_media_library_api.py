from __future__ import annotations

from pathlib import Path


def test_media_library_health_endpoint(regression_env: dict, tmp_path: Path) -> None:
    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]

    missing = client.get(f"/api/v1/projects/{project_id}/assets/media-library/health")
    assert missing.status_code == 200
    payload = missing.json()["data"]
    assert payload["ok"] is False
    assert payload["message"]

    media_root = tmp_path / "media-health"
    media_root.mkdir()
    project = client.get(f"/api/v1/projects/{project_id}").json()["data"]
    project["mediaRoot"] = str(media_root)
    client.put(f"/api/v1/projects/{project_id}", json=project)

    healthy = client.get(f"/api/v1/projects/{project_id}/assets/media-library/health")
    assert healthy.status_code == 200
    assert healthy.json()["data"]["ok"] is True


def test_media_library_scan_endpoint(regression_env: dict, tmp_path: Path, monkeypatch) -> None:
    media_root = tmp_path / "media"
    (media_root / "scene").mkdir(parents=True)
    (media_root / "scene" / "clip.mp4").write_bytes(b"video")

    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]

    project = client.get(f"/api/v1/projects/{project_id}").json()["data"]
    project["mediaRoot"] = str(media_root)
    client.put(f"/api/v1/projects/{project_id}", json=project)

    response = client.get(f"/api/v1/projects/{project_id}/assets/media-library/scan")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["fileCount"] >= 1
    assert payload["tree"]["nodeType"] == "directory"


def test_media_library_preview_endpoint(regression_env: dict, tmp_path: Path) -> None:
    media_root = tmp_path / "media2"
    (media_root / "scene").mkdir(parents=True)
    (media_root / "scene" / "clip.mp4").write_bytes(b"fake-video")

    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]

    project = client.get(f"/api/v1/projects/{project_id}").json()["data"]
    project["mediaRoot"] = str(media_root)
    client.put(f"/api/v1/projects/{project_id}", json=project)

    response = client.get(
        f"/api/v1/projects/{project_id}/assets/media-library/preview",
        params={"relativePath": "scene/clip.mp4", "quality": "original"},
    )
    assert response.status_code == 200
    assert "video" in response.headers.get("content-type", "")


def test_media_library_poster_endpoint_rejects_non_video(
    regression_env: dict, tmp_path: Path
) -> None:
    media_root = tmp_path / "media3"
    (media_root / "scene").mkdir(parents=True)
    (media_root / "scene" / "still.jpg").write_bytes(b"fake-image")

    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]

    project = client.get(f"/api/v1/projects/{project_id}").json()["data"]
    project["mediaRoot"] = str(media_root)
    client.put(f"/api/v1/projects/{project_id}", json=project)

    response = client.get(
        f"/api/v1/projects/{project_id}/assets/media-library/poster",
        params={"relativePath": "scene/still.jpg"},
    )
    assert response.status_code == 400


def test_media_library_fast_preview_uses_transcode(
    regression_env: dict, tmp_path: Path, monkeypatch
) -> None:
    media_root = tmp_path / "media4"
    (media_root / "scene").mkdir(parents=True)
    source = media_root / "scene" / "clip.mp4"
    source.write_bytes(b"fake-video")

    cached = tmp_path / "cached.preview.mp4"
    cached.write_bytes(b"cached-preview")

    def fake_resolve(project_id: str, file_path: Path, *, quality: str = "fast"):
        assert quality == "fast"
        from app.services.media_preview import PreviewBuildResult

        return PreviewBuildResult(path=cached, cached=True, mode="fast")

    monkeypatch.setattr("app.api.routes.assets.resolve_preview_file", fake_resolve)

    client = regression_env["client"]
    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]

    project = client.get(f"/api/v1/projects/{project_id}").json()["data"]
    project["mediaRoot"] = str(media_root)
    client.put(f"/api/v1/projects/{project_id}", json=project)

    response = client.get(
        f"/api/v1/projects/{project_id}/assets/media-library/preview",
        params={"relativePath": "scene/clip.mp4", "quality": "fast"},
    )
    assert response.status_code == 200
    assert response.content == b"cached-preview"
