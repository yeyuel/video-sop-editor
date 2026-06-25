from app.models.schemas import AssetRead
from app.services.export_generation import resolve_platform_export_guide
from app.services.theme_generation import (
    _enforce_theme_diversity,
    _normalize_theme_payload,
    _sanitize_asset_ids,
    build_rule_theme_candidates,
)
from app.services.llm.types import LlmCallResult


def _asset(asset_id: str, location: str) -> AssetRead:
    return AssetRead(
        assetId=asset_id,
        location=location,
        scene="测试镜头",
        relativePath=f"{asset_id}.mp4",
        mediaType="video",
        shotType="wide",
        emotionTags=["静"],
        visualTags=["蓝调"],
        informationDensity="medium",
        suggestedDurationSec=1.0,
        functionTags=["supporting"],
    )


def test_build_rule_theme_candidates_include_evidence() -> None:
    from app.models.entities import ProjectEntity

    project = ProjectEntity(
        id="proj_test",
        name="测试项目",
        destination="阿勒泰",
        platform="xiaohongshu",
        target_duration_sec=60,
        video_type="emotion_film",
        style_preference="情绪氛围片",
        style_notes="",
        route_text="将军山 - 禾木",
        media_root="",
        status="draft",
        selected_theme_id="",
    )
    assets = [
        _asset("HEMU_002", "禾木"),
        _asset("GENERAL_003", "将军山"),
    ]

    candidates = build_rule_theme_candidates(project, assets)

    assert len(candidates) == 3
    assert candidates[0]["usedAssetIds"]
    assert "禾木" in candidates[0]["usedLocations"]
    emotions = {item["coreEmotion"] for item in candidates}
    assert len(emotions) == 3


def test_enforce_theme_diversity_filters_duplicate_emotions() -> None:
    themes = [
        {"coreEmotion": "沉浸", "title": "A"},
        {"coreEmotion": "沉浸", "title": "B"},
        {"coreEmotion": "纪实", "title": "C"},
    ]

    result = _enforce_theme_diversity(themes)

    assert len(result) == 2
    assert result[0]["title"] == "A"
    assert result[1]["title"] == "C"


def test_normalize_theme_payload_keeps_evidence_and_diversity() -> None:
    assets = [_asset("HEMU_002", "禾木"), _asset("GENERAL_003", "将军山")]
    result = LlmCallResult.success(
        {
            "themes": [
                {
                    "title": "主题 A",
                    "summary": "摘要 A",
                    "coreEmotion": "沉浸",
                    "usedAssetIds": ["HEMU_002"],
                    "usedLocations": ["禾木"],
                },
                {
                    "title": "主题 B",
                    "summary": "摘要 B",
                    "coreEmotion": "沉浸",
                    "usedAssetIds": ["GENERAL_003"],
                    "usedLocations": ["将军山"],
                },
                {
                    "title": "主题 C",
                    "summary": "摘要 C",
                    "coreEmotion": "纪实",
                    "usedAssetIds": ["GENERAL_003", "INVALID"],
                    "usedLocations": ["将军山", "虚构地点"],
                },
            ]
        },
        provider_id="kimi",
        model="kimi-k2.6",
    )

    normalized = _normalize_theme_payload(result, assets, 3)

    assert len(normalized) == 2
    assert normalized[0]["usedAssetIds"] == ["HEMU_002"]
    assert normalized[1]["coreEmotion"] == "纪实"
    assert normalized[1]["usedAssetIds"] == ["GENERAL_003"]


def test_sanitize_asset_ids_rejects_unknown_assets() -> None:
    assets = [_asset("HEMU_002", "禾木")]

    assert _sanitize_asset_ids(["HEMU_002", "UNKNOWN"], assets) == ["HEMU_002"]


def test_resolve_platform_export_guide() -> None:
    assert resolve_platform_export_guide("xiaohongshu")["label"] == "小红书"
    assert resolve_platform_export_guide("douyin")["label"] == "抖音"
    assert resolve_platform_export_guide("other")["label"] == "通用短视频"
