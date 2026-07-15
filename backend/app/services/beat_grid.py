"""
剪映（CapCut）音频踩点语义对齐。

- beat_1 / 踩节拍1：粗密度，优先使用强拍/beat_track 或强起音序列。
- beat_2 / 踩节拍2：细密度，使用全量起音/细粒度节拍序列。
- strong_weak / 强弱拍：在粗密度基础上再稀疏，保留强拍。
"""

from __future__ import annotations

from statistics import median

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


def apply_beat_offset(
    beat_points: list[float],
    target_duration_sec: float,
    offset_sec: float,
) -> list[float]:
    if not beat_points:
        return []
    if abs(offset_sec) < 0.001:
        return normalize_beat_times(beat_points, target_duration_sec)

    shifted = [
        round(point + offset_sec, 2)
        for point in beat_points
        if 0 <= point + offset_sec <= float(target_duration_sec)
    ]
    return normalize_beat_times(shifted, target_duration_sec)


def apply_beat_calibration(
    beat_points: list[float],
    target_duration_sec: float,
    *,
    offset_sec: float = 0.0,
    scale: float = 1.0,
) -> list[float]:
    if not beat_points:
        return []
    if abs(offset_sec) < 0.001 and abs(scale - 1.0) < 0.0001:
        return normalize_beat_times(beat_points, target_duration_sec)

    transformed = [
        round((point * scale) + offset_sec, 2)
        for point in beat_points
        if 0 <= (point * scale) + offset_sec <= float(target_duration_sec)
    ]
    return normalize_beat_times(transformed, target_duration_sec)


def estimate_beat_offset_from_reference(
    system_beat_points: list[float],
    reference_beat_points: list[float],
    *,
    max_abs_offset_sec: float = 0.5,
) -> float:
    """Estimate global offset by comparing CapCut reference beats with nearest system beats."""
    if not system_beat_points or not reference_beat_points:
        return 0.0

    offsets: list[float] = []
    for reference in reference_beat_points:
        nearest = min(system_beat_points, key=lambda point: abs(point - reference))
        offsets.append(reference - nearest)

    estimated = round(float(median(offsets)), 2)
    return min(max_abs_offset_sec, max(-max_abs_offset_sec, estimated))


def estimate_beat_calibration_from_reference(
    system_beat_points: list[float],
    reference_beat_points: list[float],
    *,
    max_abs_offset_sec: float = 0.5,
    min_scale: float = 0.95,
    max_scale: float = 1.05,
) -> tuple[float, float]:
    """Estimate a small linear calibration: reference ~= system * scale + offset."""
    offset = estimate_beat_offset_from_reference(
        system_beat_points,
        reference_beat_points,
        max_abs_offset_sec=max_abs_offset_sec,
    )
    if len(system_beat_points) < 2 or len(reference_beat_points) < 2:
        return offset, 1.0

    pairs: list[tuple[float, float]] = []
    used_system_points: set[float] = set()
    for reference in sorted(reference_beat_points):
        nearest = min(system_beat_points, key=lambda point: abs(point - reference))
        if nearest in used_system_points:
            continue
        used_system_points.add(nearest)
        pairs.append((nearest, reference))

    if len(pairs) < 2:
        return offset, 1.0

    system_values = [pair[0] for pair in pairs]
    reference_values = [pair[1] for pair in pairs]
    mean_system = sum(system_values) / len(system_values)
    mean_reference = sum(reference_values) / len(reference_values)
    denominator = sum((value - mean_system) ** 2 for value in system_values)
    if denominator <= 0:
        return offset, 1.0

    scale = sum(
        (system - mean_system) * (reference - mean_reference)
        for system, reference in pairs
    ) / denominator
    scale = min(max_scale, max(min_scale, scale))
    offset = mean_reference - (scale * mean_system)
    offset = min(max_abs_offset_sec, max(-max_abs_offset_sec, offset))
    return round(offset, 2), round(scale, 4)


def beat_reference_match_error(
    system_beat_points: list[float],
    reference_beat_points: list[float],
) -> float:
    if not system_beat_points or not reference_beat_points:
        return float("inf")
    distances = [
        min(abs(system - reference) for system in system_beat_points)
        for reference in reference_beat_points
    ]
    return float(median(distances))


def recommend_capcut_density_mode_from_reference(
    fine_beats: list[float],
    reference_beat_points: list[float],
    target_duration_sec: float,
    *,
    coarse_beats: list[float] | None = None,
    current_mode: str = "beat_1",
) -> str:
    """Pick the CapCut beat density whose calibrated grid best matches reference beats."""
    if not fine_beats or len(reference_beat_points) < 2:
        return current_mode if current_mode in CAPCUT_BEAT_MODES else "beat_1"

    best_mode = current_mode if current_mode in CAPCUT_BEAT_MODES else "beat_1"
    best_score = float("inf")
    reference_count = len(reference_beat_points)
    for mode in ("beat_1", "beat_2", "strong_weak"):
        candidate = filter_beats_for_capcut_mode(
            fine_beats,
            mode,
            target_duration_sec,
            coarse_beats=coarse_beats,
        )
        offset, scale = estimate_beat_calibration_from_reference(
            candidate,
            reference_beat_points,
        )
        calibrated = apply_beat_calibration(
            candidate,
            target_duration_sec,
            offset_sec=offset,
            scale=scale,
        )
        density_gap = abs(len(calibrated) - reference_count) / max(reference_count, 1)
        score = beat_reference_match_error(calibrated, reference_beat_points) + density_gap * 0.03
        if score < best_score:
            best_score = score
            best_mode = mode

    return best_mode


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
