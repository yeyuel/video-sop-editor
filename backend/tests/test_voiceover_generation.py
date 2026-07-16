from __future__ import annotations

import importlib
import wave
from pathlib import Path

from sqlmodel import Session

from app.models.schemas import ExportPlanWriteRequest, VoiceoverGenerateRequest
from app.services.repository import repository
from app.services.voiceover_synthesis import VoiceoverSynthesisResult, synthesize_edge_voiceover


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
    assert by_id["edge"]["isEnabled"] is True
    assert by_id["edge"]["isRealTts"] is True
    assert by_id["edge"]["outputFormat"] == "mp3"
    edge_voices = {voice["id"]: voice for voice in by_id["edge"]["voices"]}
    assert edge_voices["auto"]["label"] == "智能匹配"
    assert edge_voices["zh-CN-XiaoxiaoNeural"]["gender"] == "female"
    assert edge_voices["zh-CN-YunjianNeural"]["gender"] == "male"
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


def test_edge_tts_generates_downloadable_mp3(
    regression_env: dict,
    monkeypatch,
    tmp_path: Path,
) -> None:
    engine = regression_env["engine"]
    client = regression_env["client"]
    project_id = "proj_001"
    generated_path = tmp_path / "voiceover.mp3"
    repository_module = importlib.import_module("app.services.repository")

    def fake_synthesize_edge_voiceover(**kwargs) -> VoiceoverSynthesisResult:
        generated_path.write_bytes(b"ID3-fake-edge-audio")
        assert kwargs["caption_blocks"]
        assert kwargs["script"] == "\n".join(kwargs["caption_blocks"])
        assert kwargs["speed"] == 1.1
        assert kwargs["selected_voice"] == "zh-CN-YunjianNeural"
        return VoiceoverSynthesisResult(
            audio_path=str(generated_path),
            duration_sec=2.75,
            provider_meta={
                "audioKind": "edge_tts_mp3",
                "voice": "zh-CN-XiaoxiaoNeural",
                "rate": "+10%",
                "outputFormat": "mp3",
            },
        )

    monkeypatch.setattr(
        repository_module,
        "synthesize_edge_voiceover",
        fake_synthesize_edge_voiceover,
    )

    with Session(engine) as session:
        repository.upsert_export_plan(
            session,
            project_id,
            ExportPlanWriteRequest(
                title="真实口播测试",
                shortTitle="Edge TTS",
                description="真实音频",
                tags=["测试"],
                coverSuggestion="",
                voiceoverScript="这是一段真实口播测试。",
                voiceoverProvider="edge",
                voiceoverVoice="zh-CN-YunjianNeural",
                voiceoverStyle="natural",
                voiceoverSpeed=1.1,
                voiceoverEmotion="warm",
            ),
        )
        plan = repository.prepare_export_voiceover_generation(
            session,
            project_id,
            VoiceoverGenerateRequest(dryRun=False),
        )

    assert plan is not None
    assert plan.voiceoverGenerationStatus == "generated"
    assert plan.voiceoverAudioPath == str(generated_path)
    assert plan.voiceoverDurationSec == 2.75
    assert plan.voiceoverProviderMeta["audioKind"] == "edge_tts_mp3"
    assert plan.voiceoverProviderMeta["actualDurationSec"] == 2.75
    assert plan.voiceoverProviderMeta["synthesisTextSource"] == "final_caption_blocks"
    assert plan.voiceoverProviderMeta["captionBlockCount"] > 0
    assert plan.voiceoverVoice == "zh-CN-YunjianNeural"

    response = client.get(f"/api/v1/projects/{project_id}/export-plan/voiceover/audio")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/mpeg")
    assert "no-store" in response.headers["cache-control"]
    assert "voiceover.mp3" in response.headers["content-disposition"]


def test_edge_tts_regeneration_uses_unique_output_paths(monkeypatch, tmp_path: Path) -> None:
    synthesis_module = importlib.import_module("app.services.voiceover_synthesis")

    async def fake_stream_edge_audio(**kwargs):
        kwargs["output_path"].write_bytes(b"ID3-fake-edge-audio")
        return 1.2, []

    monkeypatch.setattr(synthesis_module, "_stream_edge_audio", fake_stream_edge_audio)
    monkeypatch.setattr(
        synthesis_module,
        "_measure_audio_duration",
        lambda output_path, boundary_duration_sec: (1.2, "audio_file"),
    )

    first = synthesize_edge_voiceover(
        script="第一次生成。",
        caption_blocks=["第一次生成。"],
        output_dir=tmp_path,
        file_stem="publish_demo",
        style="natural",
        emotion="calm",
        speed=1.0,
        selected_voice="zh-CN-XiaoyiNeural",
    )
    second = synthesize_edge_voiceover(
        script="第二次生成。",
        caption_blocks=["第二次生成。"],
        output_dir=tmp_path,
        file_stem="publish_demo",
        style="natural",
        emotion="calm",
        speed=1.0,
    )

    assert first.audio_path != second.audio_path
    assert first.provider_meta["voice"] == "zh-CN-XiaoyiNeural"
    assert first.provider_meta["voiceLabel"] == "晓伊（女声）"
    assert Path(first.audio_path).is_file()
    assert Path(second.audio_path).is_file()


def test_locked_previous_audio_does_not_break_cleanup(monkeypatch) -> None:
    monkeypatch.setattr("app.services.repository.os.path.exists", lambda path: True)

    def raise_file_in_use(path: str) -> None:
        raise PermissionError("file in use")

    monkeypatch.setattr("app.services.repository.os.remove", raise_file_in_use)

    repository._remove_stored_audio("locked-voiceover.mp3")
