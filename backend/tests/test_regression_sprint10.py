from __future__ import annotations


def test_export_suggest_writes_segment_captions(regression_env, monkeypatch) -> None:
    client = regression_env["client"]
    project_id = "proj_001"

    generate_response = client.post(
        f"/api/v1/projects/{project_id}/storyboard:generate",
        json={"themeId": "theme_001", "alignToBeat": True},
    )
    assert generate_response.status_code == 200
    segment_id = generate_response.json()["data"]["segments"][0]["id"]

    def fake_build_llm_export_plan(**_kwargs):
        return (
            {
                "title": "阿勒泰冬日童话",
                "shortTitle": "雪国童话",
                "description": "把阿勒泰的雪和木屋剪成一段安静但有记忆点的冬日旅程。",
                "tags": ["阿勒泰", "旅行"],
                "coverSuggestion": "禾木木屋群远景",
                "segmentCaptions": [
                    {"segmentId": segment_id, "subtitle": "LLM 导出字幕写回测试"}
                ],
            },
            {"llmStatus": "success", "llmMessage": "mock export suggestion"},
        )

    monkeypatch.setattr(
        "app.services.repository.build_llm_export_plan",
        fake_build_llm_export_plan,
    )

    suggest_response = client.post(f"/api/v1/projects/{project_id}/export-plan:suggest")
    assert suggest_response.status_code == 200
    body = suggest_response.json()
    assert body["data"]["title"] == "阿勒泰冬日童话"
    assert body["meta"]["storyboardCaptionsUpdated"] == "1"

    storyboard_response = client.get(f"/api/v1/projects/{project_id}/storyboard")
    assert storyboard_response.status_code == 200
    segments = storyboard_response.json()["data"]["segments"]
    updated = next(item for item in segments if item["id"] == segment_id)
    assert updated["subtitle"] == "LLM 导出字幕写回测试"
