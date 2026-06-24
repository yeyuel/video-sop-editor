"""
剪映（CapCut）音频踩点语义对齐。

- beat_1 / 踩节拍1：粗密度，优先使用强拍/beat_track 或强起音序列。
- beat_2 / 踩节拍2：细密度，使用全量起音/细粒度节拍序列。
- strong_weak / 强弱拍：在粗密度基础上再稀疏，保留强拍。
"""

from __future__ import annotations

CAPCUT_BEAT_MODES = {"none", "beat_1", "beat_2", "strong_weak"}


def normalize_beat_times(
    candidate_times: list[float],
    target_duration_sec: float,
    *,
    min_gap_sec: float = 0.08,
) -> list[float]:
    unique_points: list[float] = []
    for raw_time in sorted({0.0, *candidate_times, float(target_duration_sec)}):
        rounded = round(raw_time, 2)
        if rounded < 0 or rounded > float(target_duration_sec):
            continue
        if unique_points and rounded - unique_points[-1] < min_gap_sec:
            continue
        unique_points.append(rounded)

    if not unique_points:
        return [0.0, float(target_duration_sec)]
    if unique_points[0] != 0.0:
        unique_points.insert(0, 0.0)
    if unique_points[-1] < float(target_duration_sec):
        unique_points.append(float(target_duration_sec))
    return unique_points


def filter_beats_for_capcut_mode(
    fine_beats: list[float],
    beat_mode: str,
    target_duration_sec: float,
    *,
    coarse_beats: list[float] | None = None,
) -> list[float]:
    if beat_mode == "none" or not fine_beats:
        return [0.0, float(target_duration_sec)]

    if beat_mode not in CAPCUT_BEAT_MODES:
        beat_mode = "beat_1"

    normalized_fine = normalize_beat_times(fine_beats, target_duration_sec)
    normalized_coarse = (
        normalize_beat_times(coarse_beats, target_duration_sec)
        if coarse_beats
        else normalized_fine
    )

    if beat_mode == "beat_2":
        return normalized_fine

    if beat_mode == "beat_1":
        if coarse_beats and len(normalized_coarse) >= 2:
            return normalized_coarse
        stride = 2
        filtered = [
            normalized_fine[index] for index in range(0, len(normalized_fine), stride)
        ]
        return normalize_beat_times(filtered, target_duration_sec)

    source = normalized_coarse if coarse_beats else normalized_fine
    if coarse_beats:
        filtered = [source[index] for index in range(0, len(source), 2)]
    else:
        filtered = [source[index] for index in range(0, len(source), 4)]
        if len(filtered) < 2:
            filtered = [source[index] for index in range(0, len(source), 2)]
    return normalize_beat_times(filtered, target_duration_sec)


def recommend_capcut_beat_mode(bpm: int, beat_interval_sec: float | None = None) -> str:
    """根据曲速推荐默认踩点模式（与剪映手动选模式的常见习惯一致）。"""
    interval = beat_interval_sec or (60 / bpm if bpm > 0 else 1.0)

    if bpm >= 120 or interval <= 0.45:
        return "beat_2"
    if bpm >= 80 or interval <= 0.75:
        return "beat_1"
    return "strong_weak"


def capcut_beat_mode_label(beat_mode: str) -> str:
    labels = {
        "none": "不启用节拍",
        "beat_1": "踩节拍1（粗密度）",
        "beat_2": "踩节拍2（细密度）",
        "strong_weak": "强弱拍（强拍）",
    }
    return labels.get(beat_mode, beat_mode)


def capcut_beat_mode_description(beat_mode: str) -> str:
    descriptions = {
        "beat_1": "对齐剪映「踩节拍1」：标记较稀疏，优先使用强拍/beat_track 序列。",
        "beat_2": "对齐剪映「踩节拍2」：标记较稠密，使用全量起音/细粒度节拍序列。",
        "strong_weak": "对齐剪映「强弱拍」：只保留强拍/重拍位置，密度低于踩节拍1。",
    }
    return descriptions.get(beat_mode, "")
