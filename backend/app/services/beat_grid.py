"""
剪映（CapCut）音频踩点语义对齐。

- beat_1 / 踩节拍1：标记较稀疏（粗密度），适合慢歌、重拍明显的音乐。
- beat_2 / 踩节拍2：标记较稠密（细密度），捕捉更多细碎节奏点，适合快切。
- strong_weak / 强弱拍：仅保留强拍，比踩节拍1更稀疏。
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
    all_beats: list[float],
    beat_mode: str,
    target_duration_sec: float,
) -> list[float]:
    if beat_mode == "none" or not all_beats:
        return [0.0, float(target_duration_sec)]

    if beat_mode not in CAPCUT_BEAT_MODES:
        beat_mode = "beat_1"

    sorted_beats = normalize_beat_times(all_beats, target_duration_sec)
    if beat_mode == "beat_2":
        return sorted_beats

    stride = 2 if beat_mode == "beat_1" else 4
    filtered = [sorted_beats[index] for index in range(0, len(sorted_beats), stride)]
    if beat_mode == "strong_weak" and len(filtered) < 2:
        filtered = [sorted_beats[index] for index in range(0, len(sorted_beats), 2)]

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
        "beat_1": "对齐剪映「踩节拍1」：标记较稀疏，适合慢歌或只需跟重拍切镜。",
        "beat_2": "对齐剪映「踩节拍2」：标记较稠密，捕捉更多细碎节奏点，适合快切。",
        "strong_weak": "对齐剪映「强弱拍」：只保留强拍/重拍位置，密度低于踩节拍1。",
    }
    return descriptions.get(beat_mode, "")
