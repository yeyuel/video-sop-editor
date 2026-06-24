"""从音频能量曲线推断结构变化点（暗场建议等）。"""

from __future__ import annotations


def suggest_dark_cuts_from_energy(
    energy_points: list[tuple[float, float]],
    target_duration_sec: float,
    *,
    max_cuts: int = 3,
) -> list[float]:
    """在能量局部低谷附近选取暗场/转场建议点。"""
    if not energy_points:
        return _fallback_dark_cuts(target_duration_sec)

    window = min(float(target_duration_sec), energy_points[-1][0])
    if window <= 0:
        return _fallback_dark_cuts(target_duration_sec)

    target_ratios = [0.25, 0.5, 0.75]
    target_times = [round(window * ratio, 2) for ratio in target_ratios]
    minima = _local_energy_minima(energy_points, window)

    selected: list[float] = []
    used: set[float] = set()
    for target_time in target_times:
        candidate = _nearest_minimum(minima, target_time, window, used)
        if candidate is None:
            continue
        selected.append(candidate)
        used.add(candidate)

    if len(selected) < max_cuts:
        for point_time, _energy in minima:
            rounded = round(point_time, 2)
            if rounded <= 0 or rounded >= window:
                continue
            if rounded in used:
                continue
            selected.append(rounded)
            used.add(rounded)
            if len(selected) >= max_cuts:
                break

    if not selected:
        return _fallback_dark_cuts(target_duration_sec)

    return sorted({round(time_point, 2) for time_point in selected if 0 < time_point < window})[
        :max_cuts
    ]


def _fallback_dark_cuts(target_duration_sec: float) -> list[float]:
    return sorted(
        {
            round(float(target_duration_sec) * ratio, 2)
            for ratio in (0.25, 0.5, 0.75)
            if 0 < round(float(target_duration_sec) * ratio, 2) < float(target_duration_sec)
        }
    )


def _local_energy_minima(
    energy_points: list[tuple[float, float]],
    window: float,
) -> list[tuple[float, float]]:
    if len(energy_points) < 3:
        return []

    minima: list[tuple[float, float]] = []
    values = [energy for _, energy in energy_points]
    average = sum(values) / max(len(values), 1)

    for index in range(1, len(energy_points) - 1):
        time_point, energy = energy_points[index]
        if time_point <= 0 or time_point >= window:
            continue
        previous = energy_points[index - 1][1]
        following = energy_points[index + 1][1]
        if energy <= previous and energy <= following and energy <= average * 0.85:
            minima.append((time_point, energy))
    return minima


def _nearest_minimum(
    minima: list[tuple[float, float]],
    target_time: float,
    window: float,
    used: set[float],
) -> float | None:
    if not minima:
        fallback = round(target_time, 2)
        if 0 < fallback < window and fallback not in used:
            return fallback
        return None

    best_time: float | None = None
    best_distance = float("inf")
    for time_point, _energy in minima:
        rounded = round(time_point, 2)
        if rounded in used or rounded <= 0 or rounded >= window:
            continue
        distance = abs(rounded - target_time)
        if distance < best_distance:
            best_distance = distance
            best_time = rounded
    return best_time
