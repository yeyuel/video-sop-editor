from app.services.audio_structure import suggest_dark_cuts_from_energy


def test_suggest_dark_cuts_from_energy_picks_local_minima() -> None:
    energy_points = [
        (0.0, 0.8),
        (1.0, 0.9),
        (2.0, 0.2),
        (3.0, 0.85),
        (4.0, 0.15),
        (5.0, 0.9),
        (6.0, 0.2),
        (7.0, 0.88),
        (8.0, 0.7),
    ]
    result = suggest_dark_cuts_from_energy(energy_points, 8.0)
    assert len(result) >= 2
    assert all(0 < point < 8.0 for point in result)


def test_suggest_dark_cuts_fallback_to_fixed_ratios() -> None:
    result = suggest_dark_cuts_from_energy([], 60.0)
    assert result == [15.0, 30.0, 45.0]
