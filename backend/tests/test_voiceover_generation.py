from __future__ import annotations

import wave
from pathlib import Path

from sqlmodel import Session

from app.models.schemas import ExportPlanWriteRequest, VoiceoverGenerateRequest
from app.services.repository import repository


def test_mock_voiceover_audio_matches_storyboard_timeline(regression_env: dict) -> None:
    engine = regression_env["engine"]
    project_id = "proj_001"

    with Session(engine) as session:
        storyboard = repository.get_storyboard_bundle(session, project_id)
        timeline_duration = max(segment.endTime for segment in storyboard.segments)

        repository.upsert_export_plan(
            session,
            project_id,
            ExportPlanWriteRequest(
                title="口播占位测试",
                shortTitle="口播测试",
                description="短句",
                tags=["测试"],
                coverSuggestion="",
                voiceoverScript="短句",
                voiceoverProvider="mock_silence",
                voiceoverStyle="natural",
                voiceoverSpeed=1.0,
                voiceoverEmotion="calm",
            ),
        )

        plan = repository.prepare_export_voiceover_generation(
            session,
            project_id,
            VoiceoverGenerateRequest(dryRun=False),
        )

    assert plan is not None
    assert plan.voiceoverGenerationStatus == "generated"
    assert plan.voiceoverDurationSec == timeline_duration

    audio_path = Path(plan.voiceoverAudioPath)
    assert audio_path.is_file()
    with wave.open(str(audio_path), "rb") as wav_file:
        actual_duration = wav_file.getnframes() / wav_file.getframerate()

    assert round(actual_duration, 2) == timeline_duration
    assert plan.voiceoverProviderMeta["estimatedSpeechDurationSec"] < timeline_duration
    assert plan.voiceoverProviderMeta["placeholderDurationPolicy"] == "match_timeline"


def test_voiceover_provider_catalog_endpoint_marks_enabled_state(regression_env: dict) -> None:
    client = regression_env["client"]

    response = client.get("/api/v1/projects/proj_001/export-plan/voiceover/providers")

    assert response.status_code == 200
    providers = response.json()["data"]
    by_id = {provider["id"]: provider for provider in providers}
    assert by_id["mock_silence"]["isEnabled"] is True
    assert by_id["mock_silence"]["isRealTts"] is False
    assert by_id["jianying_native_tts"]["isEnabled"] is True
    assert by_id["jianying_native_tts"]["outputFormat"] == "jianying_text_track"
    assert by_id["openai"]["isEnabled"] is False
    assert by_id["openai"]["isRealTts"] is True


def test_jianying_native_tts_provider_prepares_manual_handoff(regression_env: dict) -> None:
    engine = regression_env["engine"]
    project_id = "proj_001"

    with Session(engine) as session:
        repository.upsert_export_plan(
            session,
            project_id,
            ExportPlanWriteRequest(
                title="剪映朗读测试",
                shortTitle="朗读测试",
                description="短句",
                tags=["测试"],
                coverSuggestion="",
                voiceoverScript="请用剪映朗读这段口播。",
                voiceoverProvider="jianying_native_tts",
                voiceoverStyle="natural",
                voiceoverSpeed=1.0,
                voiceoverEmotion="calm",
            ),
        )

        plan = repository.prepare_export_voiceover_generation(
            session,
            project_id,
            VoiceoverGenerateRequest(dryRun=False),
        )

    assert plan is not None
    assert plan.voiceoverGenerationStatus == "manual_required"
    assert plan.voiceoverAudioPath == ""
    assert plan.voiceoverProviderMeta["handoff"] == "capcut_native_text_to_speech"
    assert plan.voiceoverProviderMeta["audioKind"] == "jianying_native_tts_pending"


def test_unenabled_real_tts_provider_returns_not_supported(regression_env: dict) -> None:
    engine = regression_env["engine"]
    project_id = "proj_001"

    with Session(engine) as session:
        repository.upsert_export_plan(
            session,
            project_id,
            ExportPlanWriteRequest(
                title="真实 TTS 预留测试",
                shortTitle="TTS 测试",
                description="短句",
                tags=["测试"],
                coverSuggestion="",
                voiceoverScript="短句",
                voiceoverProvider="openai",
                voiceoverStyle="natural",
                voiceoverSpeed=1.0,
                voiceoverEmotion="calm",
            ),
        )

        plan = repository.prepare_export_voiceover_generation(
            session,
            project_id,
            VoiceoverGenerateRequest(dryRun=True),
        )

    assert plan is not None
    assert plan.voiceoverGenerationStatus == "provider_not_supported"
    assert plan.voiceoverAudioPath == ""
    assert plan.voiceoverProviderMeta["providerEnabled"] is False
    assert plan.voiceoverProviderMeta["realTts"] is True
