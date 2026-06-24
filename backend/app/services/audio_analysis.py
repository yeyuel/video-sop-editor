from __future__ import annotations

import math
import os
import shutil
import statistics
import struct
import subprocess
import tempfile
import wave
from dataclasses import dataclass, field

from app.services.beat_grid import (
    capcut_beat_mode_description,
    capcut_beat_mode_label,
    filter_beats_for_capcut_mode,
    normalize_beat_times,
    recommend_capcut_beat_mode,
)

try:
    import librosa
    import numpy as np

    LIBROSA_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    librosa = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    LIBROSA_AVAILABLE = False


@dataclass
class BeatAnalysisResult:
    beat_mode: str
    beat_points: list[float]
    raw_beat_times: list[float] = field(default_factory=list)
    bpm: int = 0
    dark_cut_suggestions: list[float] = field(default_factory=list)
    bgm_style: str = ""
    analysis_notes: list[str] = field(default_factory=list)
    analysis_engine: str = "energy"
    audio_duration_sec: float = 0.0


class AudioAnalysisError(ValueError):
    pass


class AudioBeatAnalyzer:
    SUPPORTED_EXTENSIONS = {".wav"}
    CONVERTIBLE_EXTENSIONS = {".mp3", ".m4a", ".aac", ".ogg", ".mgg", ".flac", ".wma"}
    SUPPORTED_UPLOAD_EXTENSIONS = SUPPORTED_EXTENSIONS | CONVERTIBLE_EXTENSIONS

    def analyze(self, file_path: str, target_duration_sec: int) -> BeatAnalysisResult:
        extension = os.path.splitext(file_path)[1].lower()
        if extension not in self.SUPPORTED_UPLOAD_EXTENSIONS:
            raise AudioAnalysisError(
                "暂不支持这种音频格式，请上传 WAV、MP3、M4A、AAC、OGG、MGG、FLAC 或 WMA。"
            )

        wav_path, cleanup_path = self._ensure_wav_input(file_path, extension)
        try:
            if LIBROSA_AVAILABLE:
                try:
                    return self._analyze_with_librosa(wav_path, target_duration_sec)
                except AudioAnalysisError:
                    raise
                except Exception:
                    pass
            return self._analyze_with_energy(wav_path, target_duration_sec)
        finally:
            if cleanup_path and os.path.exists(cleanup_path):
                os.remove(cleanup_path)

    def _finalize_capcut_result(
        self,
        *,
        raw_beat_times: list[float],
        target_duration_sec: int,
        bpm: int,
        beat_interval_sec: float | None,
        analysis_engine: str,
        audio_duration_sec: float,
        analysis_window: float,
        extra_notes: list[str],
    ) -> BeatAnalysisResult:
        normalized_raw = normalize_beat_times(raw_beat_times, float(target_duration_sec))
        if len(normalized_raw) < 2:
            raise AudioAnalysisError("未能从音频中识别到足够节拍点，请更换音频或改用规则生成。")

        beat_mode = recommend_capcut_beat_mode(bpm, beat_interval_sec)
        beat_points = filter_beats_for_capcut_mode(
            normalized_raw,
            beat_mode,
            float(target_duration_sec),
        )
        notes = [
            f"识别引擎：{analysis_engine}",
            f"剪映对标模式：{capcut_beat_mode_label(beat_mode)}",
            capcut_beat_mode_description(beat_mode),
            f"音频时长：{audio_duration_sec} 秒，分析窗口：{analysis_window} 秒",
            f"识别 BPM：{bpm}",
            f"原始节拍点：{len(normalized_raw)} 个",
            f"当前模式输出节拍点：{len(beat_points)} 个",
            *extra_notes,
        ]
        return BeatAnalysisResult(
            beat_mode=beat_mode,
            beat_points=beat_points,
            raw_beat_times=normalized_raw,
            bpm=bpm,
            dark_cut_suggestions=self._suggest_dark_cuts(target_duration_sec),
            bgm_style=self._suggest_bgm_style(bpm),
            analysis_notes=notes,
            analysis_engine=analysis_engine,
            audio_duration_sec=audio_duration_sec,
        )

    def _analyze_with_librosa(self, wav_path: str, target_duration_sec: int) -> BeatAnalysisResult:
        assert librosa is not None and np is not None

        samples, sample_rate = librosa.load(wav_path, sr=44100, mono=True)
        if samples.size == 0:
            raise AudioAnalysisError("音频文件没有读取到有效采样数据，请确认文件内容后重试。")

        audio_duration_sec = round(float(len(samples) / sample_rate), 2)
        analysis_window = min(float(target_duration_sec), audio_duration_sec)

        onset_frames = librosa.onset.onset_detect(
            y=samples,
            sr=sample_rate,
            units="frames",
            backtrack=False,
        )
        onset_times = [
            round(float(time_point), 2)
            for time_point in librosa.frames_to_time(onset_frames, sr=sample_rate)
            if time_point <= analysis_window
        ]

        tempo, beat_frames = librosa.beat.beat_track(y=samples, sr=sample_rate, units="frames")
        beat_times = [
            round(float(time_point), 2)
            for time_point in librosa.frames_to_time(beat_frames, sr=sample_rate)
            if time_point <= analysis_window
        ]

        raw_beats = beat_times if len(beat_times) >= 3 else onset_times
        if len(raw_beats) < 2:
            raise AudioAnalysisError("未能从音频中识别到足够节拍点，请更换音频或改用规则生成。")

        bpm = int(round(float(tempo))) if tempo else 0
        intervals = [
            right - left for left, right in zip(raw_beats, raw_beats[1:]) if right > left
        ]
        beat_interval_sec = statistics.median(intervals) if intervals else None
        if bpm <= 0 and beat_interval_sec:
            bpm = max(40, min(220, round(60 / beat_interval_sec)))
        if bpm <= 0:
            bpm = 90

        return self._finalize_capcut_result(
            raw_beat_times=raw_beats,
            target_duration_sec=target_duration_sec,
            bpm=bpm,
            beat_interval_sec=float(beat_interval_sec) if beat_interval_sec else None,
            analysis_engine="librosa",
            audio_duration_sec=audio_duration_sec,
            analysis_window=analysis_window,
            extra_notes=[f"识别起音点：{len(onset_times)} 个"],
        )

    def _analyze_with_energy(self, wav_path: str, target_duration_sec: int) -> BeatAnalysisResult:
        try:
            with wave.open(wav_path, "rb") as wav_file:
                channel_count = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                frame_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()
                frames = wav_file.readframes(frame_count)
        except wave.Error as exc:
            raise AudioAnalysisError("音频文件无法解析，请确认文件格式后重试。") from exc

        if sample_width not in {1, 2, 4}:
            raise AudioAnalysisError("当前 WAV 文件采样位深暂不支持，请更换音频文件后重试。")

        samples = self._decode_samples(frames, sample_width)
        mono_samples = self._to_mono(samples, channel_count)
        if not mono_samples:
            raise AudioAnalysisError("音频文件没有读取到有效采样数据，请确认文件内容后重试。")

        audio_duration_sec = round(len(mono_samples) / frame_rate, 2)
        analysis_window = min(float(target_duration_sec), audio_duration_sec)

        window_size = max(frame_rate // 20, 512)
        window_duration = window_size / frame_rate
        energies = self._window_energies(mono_samples, window_size)
        onset_times = self._detect_onset_times(energies, window_duration)
        onset_times = [point for point in onset_times if point <= analysis_window]

        if len(onset_times) >= 3:
            raw_beats = onset_times
        else:
            interval = self._estimate_interval(onset_times, target_duration_sec)
            raw_beats = self._build_uniform_beats(int(analysis_window), interval)

        intervals = [
            right - left
            for left, right in zip(raw_beats, raw_beats[1:])
            if 0.25 <= right - left <= 1.5
        ]
        beat_interval_sec = statistics.median(intervals) if intervals else self._estimate_interval(
            onset_times, target_duration_sec
        )
        bpm = max(40, min(220, round(60 / beat_interval_sec)))

        return self._finalize_capcut_result(
            raw_beat_times=raw_beats,
            target_duration_sec=target_duration_sec,
            bpm=bpm,
            beat_interval_sec=float(beat_interval_sec),
            analysis_engine="energy",
            audio_duration_sec=audio_duration_sec,
            analysis_window=analysis_window,
            extra_notes=["librosa 不可用或识别失败时的能量起音兜底"],
        )

    def _ensure_wav_input(self, file_path: str, extension: str) -> tuple[str, str | None]:
        if extension in self.SUPPORTED_EXTENSIONS:
            return file_path, None

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise AudioAnalysisError(
                "当前音频格式需要先完成转码，请先安装 ffmpeg，或先将文件转换成 WAV 再上传。"
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
            temp_wav_path = temp_wav.name

        command = [
            ffmpeg_path,
            "-y",
            "-i",
            file_path,
            "-ac",
            "1",
            "-ar",
            "44100",
            temp_wav_path,
        ]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if result.returncode != 0 or not os.path.exists(temp_wav_path):
            if os.path.exists(temp_wav_path):
                os.remove(temp_wav_path)
            raise AudioAnalysisError(
                "音频转码失败，请确认文件可正常播放，或先手动转换成 WAV 后再上传。"
            )

        return temp_wav_path, temp_wav_path

    @staticmethod
    def _decode_samples(frames: bytes, sample_width: int) -> tuple[int, ...]:
        sample_count = len(frames) // sample_width
        if sample_width == 1:
            return tuple(byte - 128 for byte in frames)

        format_map = {
            2: f"<{sample_count}h",
            4: f"<{sample_count}i",
        }
        return struct.unpack(format_map[sample_width], frames)

    @staticmethod
    def _to_mono(samples: tuple[int, ...], channel_count: int) -> list[float]:
        if channel_count <= 1:
            return [float(sample) for sample in samples]

        mono_samples: list[float] = []
        for index in range(0, len(samples), channel_count):
            chunk = samples[index : index + channel_count]
            if not chunk:
                continue
            mono_samples.append(sum(chunk) / len(chunk))
        return mono_samples

    @staticmethod
    def _window_energies(samples: list[float], window_size: int) -> list[float]:
        energies: list[float] = []
        for index in range(0, len(samples), window_size):
            window = samples[index : index + window_size]
            if not window:
                continue
            square_sum = sum(sample * sample for sample in window)
            energies.append(math.sqrt(square_sum / len(window)))
        return energies

    @staticmethod
    def _detect_onset_times(energies: list[float], window_duration: float) -> list[float]:
        onset_times: list[float] = []
        lookback = 8
        min_gap_windows = 4
        last_onset_index = -min_gap_windows

        for index in range(lookback, len(energies)):
            current = energies[index]
            history = energies[index - lookback : index]
            average = sum(history) / max(len(history), 1)
            local_peak = current >= max(energies[index - 1], energies[index - 2], average)
            is_onset = average > 0 and current > average * 1.35 and local_peak
            if is_onset and index - last_onset_index >= min_gap_windows:
                onset_times.append(round(index * window_duration, 2))
                last_onset_index = index
        return onset_times

    @staticmethod
    def _estimate_interval(onset_times: list[float], target_duration_sec: int) -> float:
        candidate_deltas = [
            round(right - left, 2)
            for left, right in zip(onset_times, onset_times[1:])
            if 0.25 <= right - left <= 1.5
        ]
        if candidate_deltas:
            return max(0.25, min(1.5, statistics.median(candidate_deltas)))

        if target_duration_sec <= 8:
            return 0.5
        if target_duration_sec <= 20:
            return 0.75
        return 1.0

    @staticmethod
    def _build_uniform_beats(target_duration_sec: int, interval: float) -> list[float]:
        beat_points: list[float] = []
        current = 0.0
        while current <= float(target_duration_sec):
            beat_points.append(round(current, 2))
            current += interval
        if beat_points and beat_points[-1] < float(target_duration_sec):
            beat_points.append(float(target_duration_sec))
        return beat_points

    @staticmethod
    def _suggest_dark_cuts(target_duration_sec: int) -> list[float]:
        checkpoints = {round(target_duration_sec * ratio, 2) for ratio in (0.25, 0.5, 0.75)}
        return sorted(point for point in checkpoints if 0 < point < target_duration_sec)

    @staticmethod
    def _suggest_bgm_style(bpm: int) -> str:
        if bpm >= 120:
            return "强节拍电子推进，适合快切和转场强调"
        if bpm >= 90:
            return "稳节拍旅行律动，适合路线推进和情绪抬升"
        return "舒展氛围慢脉冲，适合空镜铺垫和情绪酝酿"


audio_beat_analyzer = AudioBeatAnalyzer()
