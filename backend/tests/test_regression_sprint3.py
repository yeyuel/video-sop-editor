from __future__ import annotations

import tempfile
import wave

import pytest
from sqlalchemy import inspect, text
from sqlmodel import Session, create_engine

from app.migrations.runner import (
    MIGRATIONS,
    _current_version,
    _ensure_schema_version_table,
    _migration_003_rhythm_raw_beats,
    _set_version,
)
from app.models.schemas import RhythmPlanWriteRequest
from app.services.beat_grid import filter_beats_for_capcut_mode
from app.services.repository import repository
from app.services.storyboard_generation import segment_read_to_write


def _write_click_track(path: str, *, duration_sec: float = 4.0, bpm: int = 120) -> None:
    sample_rate = 44100
    frame_count = int(duration_sec * sample_rate)
    interval_frames = int(sample_rate * 60 / bpm)
    frames = bytearray(frame_count * 2)

    for frame_index in range(frame_count):
        amplitude = 12000 if frame_index % interval_frames == 0 else 0
        frames[frame_index * 2 : frame_index * 2 + 2] = int(amplitude).to_bytes(
            2, byteorder="little", signed=True
        )

    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(frames))


def test_migration_003_upgrades_legacy_rhythm_table(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "legacy.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr("app.migrations.runner.engine", engine)

    with Session(engine) as session:
        session.exec(
            text(
                """
                CREATE TABLE schemaversionentity (
                    id INTEGER PRIMARY KEY,
                    version INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )
        session.exec(text("INSERT INTO schemaversionentity (id, version) VALUES (1, 2)"))
        session.exec(
            text(
                """
                CREATE TABLE rhythmplanentity (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    bgm_style TEXT,
                    selected_track_name TEXT,
                    audio_file_name TEXT DEFAULT '',
                    audio_file_path TEXT DEFAULT '',
                    analysis_source TEXT DEFAULT 'manual',
                    analysis_notes TEXT DEFAULT '[]',
                    detected_bpm INTEGER DEFAULT 0,
                    audio_duration_sec REAL DEFAULT 0.0,
                    beat_mode TEXT,
                    beat_points TEXT,
                    rhythm_notes TEXT,
                    dark_cut_suggestions TEXT,
                    photo_motion_suggestions TEXT
                )
                """
            )
        )
        session.commit()

        _migration_003_rhythm_raw_beats(session)
        session.commit()

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("rhythmplanentity")}
    assert "raw_beat_points" in columns


def test_migrations_idempotent(regression_env) -> None:
    from app.migrations.runner import run_migrations

    engine = regression_env["engine"]
    run_migrations()
    with Session(engine) as session:
        version = _current_version(session)
    assert version >= 3


def test_login_and_workspace_unlock_steps(regression_env) -> None:
    client = regression_env["client"]

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "director", "password": "root123"},
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()["data"]
    assert login_payload["user"]["username"] == "director"
    assert login_payload["sessionToken"]

    workspace_response = client.get("/api/v1/projects/proj_001/workspace")
    assert workspace_response.status_code == 200
    workspace = workspace_response.json()["data"]

    assert workspace["project"]["selectedThemeId"]
    assert len(workspace["assets"]) > 0
    assert len(workspace["themes"]) > 0
    assert len(workspace["rhythmPlan"]["beatPoints"]) > 0


def _prepare_bgm_selection(client, project_id: str) -> None:
    recommend_response = client.post(f"/api/v1/projects/{project_id}/rhythm-plan/bgm-recommend")
    assert recommend_response.status_code == 200
    plan = recommend_response.json()["data"]
    assert plan["recommendedBgm"]
    recommendation_id = plan["recommendedBgm"][0]["id"]
    select_response = client.put(
        f"/api/v1/projects/{project_id}/rhythm-plan/bgm-selection",
        json={"recommendationId": recommendation_id},
    )
    assert select_response.status_code == 200


def test_rhythm_bgm_recommend_and_save(regression_env) -> None:
    client = regression_env["client"]
    project_id = "proj_001"

    generate_response = client.post(f"/api/v1/projects/{project_id}/rhythm-plan/bgm-recommend")
    assert generate_response.status_code == 200
    plan = generate_response.json()["data"]
    assert plan["bgmPhase"] == "recommended"
    assert len(plan["recommendedBgm"]) >= 2
    assert plan["beatPoints"] == []

    save_response = client.put(
        f"/api/v1/projects/{project_id}/rhythm-plan/bgm-selection",
        json={"recommendationId": plan["recommendedBgm"][0]["id"]},
    )
    assert save_response.status_code == 200
    selected = save_response.json()["data"]
    assert selected["selectedBgmId"] == plan["recommendedBgm"][0]["id"]
    assert selected["selectedTrackName"]


def test_rhythm_beat_mode_refilter_on_save(regression_env) -> None:
    engine = regression_env["engine"]
    project_id = "proj_001"
    target_duration_sec = 60.0
    raw_beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]

    with Session(engine) as session:
        dense = filter_beats_for_capcut_mode(raw_beats, "beat_2", target_duration_sec)
        coarse = filter_beats_for_capcut_mode(
            raw_beats,
            "beat_1",
            target_duration_sec,
            coarse_beats=[raw_beats[index] for index in range(0, len(raw_beats), 2)],
        )
        assert len(dense) > len(coarse)

        payload = RhythmPlanWriteRequest(
            bgmStyle="regression BGM",
            selectedTrackName="regression-track",
            analysisSource="audio_upload",
            analysisNotes=["regression"],
            detectedBpm=120,
            audioDurationSec=4.0,
            rawBeatPoints=raw_beats,
            coarseBeatPoints=[raw_beats[index] for index in range(0, len(raw_beats), 2)],
            beatMode="beat_2",
            beatPoints=dense,
            rhythmNotes=["regression"],
            darkCutSuggestions=[1.0, 2.0],
            photoMotionSuggestions=["slow push"],
            selectedBgmId="bgm_test",
            bgmPhase="analyzed",
        )
        saved = repository.upsert_rhythm_plan(session, project_id, payload)
        assert saved is not None
        assert saved.beatMode == "beat_2"
        assert len(saved.beatPoints) == len(dense)

        payload.beatMode = "beat_1"
        payload.beatPoints = dense
        refiltered = repository.upsert_rhythm_plan(session, project_id, payload)
        assert refiltered is not None
        assert refiltered.beatMode == "beat_1"
        assert len(refiltered.beatPoints) == len(coarse)
        assert len(refiltered.beatPoints) < len(saved.beatPoints)


def test_audio_upload_and_delete_audio(regression_env) -> None:
    client = regression_env["client"]
    project_id = "proj_001"
    _prepare_bgm_selection(client, project_id)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        wav_path = temp_file.name
    _write_click_track(wav_path, duration_sec=4.0, bpm=120)

    with open(wav_path, "rb") as audio_file:
        upload_response = client.post(
            f"/api/v1/projects/{project_id}/rhythm-plan/audio-upload",
            files={"audio": ("regression.wav", audio_file, "audio/wav")},
        )
    assert upload_response.status_code == 200
    uploaded = upload_response.json()["data"]
    assert uploaded["analysisSource"] in {"audio_upload", "rule_fallback"}
    assert len(uploaded["beatPoints"]) >= 2
    if uploaded["analysisSource"] == "audio_upload":
        assert uploaded["detectedBpm"] > 0
        assert len(uploaded["rawBeatPoints"]) >= len(uploaded["beatPoints"])

    delete_response = client.delete(f"/api/v1/projects/{project_id}/rhythm-plan/audio")
    assert delete_response.status_code == 200
    cleared = delete_response.json()["data"]
    assert cleared["audioFileName"] == ""
    assert cleared["detectedBpm"] == 0
    assert cleared["beatPoints"] == []
    assert cleared["bgmPhase"] == "recommended"


def test_rule_fallback_on_invalid_audio(regression_env) -> None:
    client = regression_env["client"]
    project_id = "proj_001"
    _prepare_bgm_selection(client, project_id)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_file.write(b"not-a-valid-wav")
        bad_path = temp_file.name

    with open(bad_path, "rb") as audio_file:
        upload_response = client.post(
            f"/api/v1/projects/{project_id}/rhythm-plan/audio-upload",
            files={"audio": ("broken.wav", audio_file, "audio/wav")},
        )

    assert upload_response.status_code == 200
    plan = upload_response.json()["data"]
    assert plan["analysisSource"] == "rule_fallback"
    assert plan["bgmPhase"] == "recommended"
    assert plan["beatPoints"] == []


def test_storyboard_generate_rule_and_llm_fallback(regression_env) -> None:
    client = regression_env["client"]
    project_id = "proj_001"
    request_body = {
        "themeId": "theme_001",
        "alignToBeat": True,
    }

    rule_response = client.post(
        f"/api/v1/projects/{project_id}/storyboard:generate",
        json=request_body,
    )
    assert rule_response.status_code == 200
    rule_bundle = rule_response.json()["data"]
    assert len(rule_bundle["segments"]) > 0

    llm_response = client.post(
        f"/api/v1/projects/{project_id}/storyboard:generate-llm",
        json=request_body,
    )
    assert llm_response.status_code == 200
    llm_bundle = llm_response.json()["data"]
    assert len(llm_bundle["segments"]) > 0


def test_storyboard_segment_update(regression_env) -> None:
    engine = regression_env["engine"]
    project_id = "proj_001"

    with Session(engine) as session:
        bundle = repository.get_storyboard_bundle(session, project_id)
        assert bundle.segments
        segment = bundle.segments[0]
        payload = segment_read_to_write(segment)
        payload.shotDescription = "回归测试镜头描述"
        updated = repository.update_storyboard_segment(
            session,
            project_id,
            segment.id,
            payload,
        )
        assert updated is not None
        assert updated.shotDescription == "回归测试镜头描述"


def test_export_markdown_json_yaml(regression_env) -> None:
    client = regression_env["client"]
    project_id = "proj_001"

    for fmt in ("markdown", "json", "yaml", "csv"):
        response = client.post(f"/api/v1/projects/{project_id}/exports/{fmt}")
        assert response.status_code == 200
        document = response.json()["data"]
        assert document["format"] == fmt
        assert document["content"].strip()
        if fmt == "csv":
            assert "segmentId" in document["content"]


def test_run_all_migrations_from_zero(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "fresh.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr("app.migrations.runner.engine", engine)

    with Session(engine) as session:
        _ensure_schema_version_table(session)
        session.commit()
        for version, _name, migration in MIGRATIONS:
            if version <= _current_version(session):
                continue
            migration(session)
            _set_version(session, version)
            session.commit()
        final_version = _current_version(session)

    assert final_version == len(MIGRATIONS)
    assert final_version >= 9
