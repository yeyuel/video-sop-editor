from app.services.rhythm_track import resolve_selected_track_name


class _Project:
    id = "proj_test"
    name = "阿勒泰雪国片"


class _Theme:
    title = "冷蓝雪线"


def test_resolve_selected_track_name_prefers_audio_filename() -> None:
    result = resolve_selected_track_name(
        _Project(),
        _Theme(),
        audio_file_name="my-track.mp3",
        existing_name="old-name",
    )
    assert result == "my-track"


def test_resolve_selected_track_name_uses_theme_when_no_audio() -> None:
    result = resolve_selected_track_name(_Project(), _Theme())
    assert result == "冷蓝雪线-参考曲"


def test_resolve_selected_track_name_keeps_user_value() -> None:
    result = resolve_selected_track_name(
        _Project(),
        _Theme(),
        existing_name="用户自定义曲名",
    )
    assert result == "用户自定义曲名"
