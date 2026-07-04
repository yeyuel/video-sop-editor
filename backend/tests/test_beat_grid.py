from app.services.beat_grid import (
    apply_beat_offset,
    filter_beats_for_capcut_mode,
    recommend_capcut_beat_mode,
)


def test_filter_beats_for_capcut_mode_beat_2_keeps_all_fine() -> None:
    all_beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    result = filter_beats_for_capcut_mode(all_beats, "beat_2", 3.0)
    assert result == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def test_apply_beat_offset_shifts_points_within_target() -> None:
    result = apply_beat_offset([0.0, 1.0, 2.0, 3.0], 3.0, 0.2)
    assert result == [0.0, 0.2, 1.2, 2.2, 3.0]


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
