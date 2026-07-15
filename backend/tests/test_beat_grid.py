from app.services.beat_grid import (
    apply_beat_calibration,
    apply_beat_offset,
    estimate_beat_calibration_from_reference,
    estimate_beat_offset_from_reference,
    filter_beats_for_capcut_mode,
    recommend_capcut_beat_mode,
    recommend_capcut_density_mode_from_reference,
)


def test_filter_beats_for_capcut_mode_beat_2_keeps_all_fine() -> None:
    all_beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    result = filter_beats_for_capcut_mode(all_beats, "beat_2", 3.0)
    assert result == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def test_apply_beat_offset_shifts_points_within_target() -> None:
    result = apply_beat_offset([0.0, 1.0, 2.0, 3.0], 3.0, 0.2)
    assert result == [0.0, 0.2, 1.2, 2.2, 3.0]


def test_apply_beat_calibration_applies_small_scale_and_offset() -> None:
    result = apply_beat_calibration(
        [0.0, 1.0, 2.0, 3.0],
        3.5,
        offset_sec=0.1,
        scale=1.05,
    )
    assert result == [0.0, 0.1, 1.15, 2.2, 3.25, 3.5]


def test_estimate_beat_offset_from_reference_uses_nearest_median() -> None:
    result = estimate_beat_offset_from_reference(
        [0.0, 1.0, 2.0, 3.0],
        [0.18, 1.19, 2.21],
    )
    assert result == 0.19


def test_estimate_beat_offset_from_reference_clamps_large_error() -> None:
    result = estimate_beat_offset_from_reference(
        [0.0, 10.0],
        [5.0, 15.0, 25.0],
    )
    assert result == 0.5


def test_estimate_beat_calibration_from_reference_detects_small_scale() -> None:
    offset, scale = estimate_beat_calibration_from_reference(
        [0.0, 1.0, 2.0, 3.0],
        [0.1, 1.15, 2.2, 3.25],
    )
    assert offset == 0.1
    assert scale == 1.05


def test_recommend_capcut_density_mode_from_reference_prefers_fine_grid() -> None:
    fine_beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    coarse_beats = [0.0, 1.0, 2.0, 3.0]

    mode = recommend_capcut_density_mode_from_reference(
        fine_beats,
        [0.5, 1.0, 1.5, 2.0, 2.5],
        3.0,
        coarse_beats=coarse_beats,
        current_mode="beat_1",
    )

    assert mode == "beat_2"


def test_recommend_capcut_density_mode_from_reference_prefers_coarse_grid() -> None:
    fine_beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    coarse_beats = [0.0, 1.0, 2.0, 3.0]

    mode = recommend_capcut_density_mode_from_reference(
        fine_beats,
        [1.0, 2.0, 3.0],
        3.0,
        coarse_beats=coarse_beats,
        current_mode="beat_2",
    )

    assert mode == "beat_1"


def test_filter_beats_for_capcut_mode_beat_1_uses_coarse_grid() -> None:
    fine_beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    coarse_beats = [0.0, 1.0, 2.0, 3.0, 4.0]
    result = filter_beats_for_capcut_mode(
        fine_beats,
        "beat_1",
        4.0,
        coarse_beats=coarse_beats,
    )
    assert result == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_filter_beats_for_capcut_mode_beat_1_stride_fallback_without_coarse() -> None:
    all_beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    result = filter_beats_for_capcut_mode(all_beats, "beat_1", 4.0)
    assert result == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_filter_beats_for_capcut_mode_strong_weak_keeps_downbeats() -> None:
    fine_beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    coarse_beats = [0.0, 1.0, 2.0, 3.0, 4.0]
    result = filter_beats_for_capcut_mode(
        fine_beats,
        "strong_weak",
        4.0,
        coarse_beats=coarse_beats,
    )
    assert result == [0.0, 2.0, 4.0]


def test_recommend_capcut_beat_mode() -> None:
    assert recommend_capcut_beat_mode(130) == "beat_2"
    assert recommend_capcut_beat_mode(95) == "beat_1"
    assert recommend_capcut_beat_mode(70) == "strong_weak"
