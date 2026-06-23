from __future__ import annotations

import math
import os
import shutil
import statistics
import struct
import subprocess
import tempfile
import wave
from dataclasses import dataclass


@dataclass
class BeatAnalysisResult:
    beat_mode: str
    beat_points: list[float]
    bpm: int
    dark_cut_suggestions: list[float]
    bgm_style: str
    analysis_notes: list[str]


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
            with wave.open(wav_path, "rb") as wav_file:
                channel_count = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                frame_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()
                frames = wav_file.readframes(frame_count)
        finally:
            if cleanup_path and os.path.exists(cleanup_path):
                os.remove(cleanup_path)

        if sample_width not in {1, 2, 4}:
            raise AudioAnalysisError("当前 WAV 文件采样位深暂不支持，请更换音频文件后重试。")

        samples = self._decode_samples(frames, sample_width)
        mono_samples = self._to_mono(samples, channel_count)
        if not mono_samples:
            raise AudioAnalysisError("音频文件没有读取到有效采样数据，请确认文件内容后重试。")

        window_size = max(frame_rate // 20, 512)
        window_duration = window_size / frame_rate
        energies = self._window_energies(mono_samples, window_size)
        onset_times = self._detect_onset_times(energies, window_duration)

        interval = self._estimate_interval(onset_times, target_duration_sec)
        beat_points = self._build_uniform_beats(target_duration_sec, interval)
        bpm = max(40, min(220, round(60 / max(interval, 0.01))))
        beat_mode = self._classify_beat_mode(bpm)
        dark_cuts = self._suggest_dark_cuts(target_duration_sec)
        bgm_style = self._suggest_bgm_style(bpm)
        notes = [
            f"自动识别节拍间隔：{interval:.2f} 秒",
            f"预估 BPM：{bpm}",
            f"检测到起音点数量：{len(onset_times)}",
        ]
        return BeatAnalysisResult(
            beat_mode=beat_mode,
            beat_points=beat_points,
            bpm=bpm,
            dark_cut_suggestions=dark_cuts,
            bgm_style=bgm_style,
            analysis_notes=notes,
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
        if beat_points[-1] < float(target_duration_sec):
            beat_points.append(float(target_duration_sec))
        return beat_points

    @staticmethod
    def _classify_beat_mode(bpm: int) -> str:
        if bpm >= 110:
            return "beat_1"
        if bpm >= 80:
            return "beat_2"
        return "strong_weak"

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
