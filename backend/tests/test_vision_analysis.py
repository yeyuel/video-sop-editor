from __future__ import annotations

from app.services.vision_analysis import (
    _build_prefill,
    _collect_prefilled_fields,
    _normalize_vision_payload,
    _vision_payload_from_cache,
    relative_path_fingerprint,
    resolve_vision_file_fingerprint,
)


def test_normalize_snake_case_payload() -> None:
    normalized = _normalize_vision_payload(
        {
            "scene": "蓝冰河流",
            "shot_type": "close_up",
            "emotion_tags": ["冷", "静"],
            "visual_tags": ["白雪"],
            "information_density": "medium",
            "suggested_duration_sec": 2.5,
        }
    )
    assert _collect_prefilled_fields(normalized) == [
        "scene",
        "shotType",
        "emotionTags",
        "visualTags",
        "informationDensity",
        "suggestedDurationSec",
    ]


def test_build_prefill_does_not_reference_self_during_construction() -> None:
    prefill = _build_prefill(
        {
            "scene": "测试画面",
            "shotType": "medium",
            "emotionTags": ["静"],
            "visualTags": ["蓝"],
            "informationDensity": "low",
            "suggestedDurationSec": 1.5,
        }
    )
    updated = prefill.model_copy(
        update={"message": f"Vision 分析完成，已预填 {len(prefill.prefilledFields)} 个字段。"}
    )
    assert updated.visionAnalysisStatus == "ready"
    assert "已预填 6 个字段" in updated.message


def test_error_only_payload_has_no_prefill_fields() -> None:
    normalized = _normalize_vision_payload({"message": "cannot prefill"})
    assert _collect_prefilled_fields(normalized) == []


def test_relative_path_fingerprint_stable() -> None:
    first = relative_path_fingerprint("proj-1", r"喀纳斯\drone\KANAS_001.mp4")
    second = relative_path_fingerprint("proj-1", r"喀纳斯\drone\KANAS_001.mp4")
    different = relative_path_fingerprint("proj-2", r"喀纳斯\drone\KANAS_001.mp4")
    assert first == second
    assert first != different


def test_vision_payload_from_cache_keeps_prefill_fields() -> None:
    cached = {
        "scene": "缓存画面",
        "shotType": "wide",
        "emotionTags": ["静"],
        "visualTags": ["蓝"],
        "informationDensity": "low",
        "suggestedDurationSec": 2.0,
        "fileFingerprint": "abc123",
        "providerId": "kimi",
    }
    payload = _vision_payload_from_cache(cached)
    assert payload["scene"] == "缓存画面"
    assert "fileFingerprint" not in payload
    assert _collect_prefilled_fields(payload) == [
        "scene",
        "shotType",
        "emotionTags",
        "visualTags",
        "informationDensity",
        "suggestedDurationSec",
    ]


def test_resolve_vision_file_fingerprint_falls_back_to_relative_path() -> None:
    fingerprint = resolve_vision_file_fingerprint(
        "proj-1",
        "/missing/media/root",
        r"禾木\wide\HEMU_002.mp4",
    )
    assert fingerprint == relative_path_fingerprint("proj-1", r"禾木\wide\HEMU_002.mp4")
