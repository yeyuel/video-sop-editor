import tempfile
import wave

from app.services.audio_analysis import audio_beat_analyzer


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


def test_analyze_click_track_returns_beat_points() -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name

    _write_click_track(temp_path, duration_sec=6.0, bpm=120)
    result = audio_beat_analyzer.analyze(temp_path, target_duration_sec=6)

    assert len(result.beat_points) >= 3
    assert result.beat_points[0] == 0.0
    assert result.beat_points[-1] == 6.0
    assert 80 <= result.bpm <= 140
    assert result.analysis_engine in {"librosa", "energy"}
    assert len(result.raw_beat_times) >= len(result.beat_points)
    assert result.beat_mode in {"beat_1", "beat_2", "strong_weak"}


def test_analyze_click_track_capcut_mode_filters_raw_beats() -> None:
    from app.services.beat_grid import filter_beats_for_capcut_mode

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name

    _write_click_track(temp_path, duration_sec=4.0, bpm=120)
    result = audio_beat_analyzer.analyze(temp_path, target_duration_sec=4)

    for mode in ("beat_1", "beat_2", "strong_weak"):
        filtered = filter_beats_for_capcut_mode(result.raw_beat_times, mode, 4.0)
        assert filtered[0] == 0.0
        assert filtered[-1] == 4.0
        if mode == "beat_2":
            assert len(filtered) >= len(filter_beats_for_capcut_mode(result.raw_beat_times, "beat_1", 4.0))
