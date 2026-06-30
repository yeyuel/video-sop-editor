from __future__ import annotations

from app.services.llm.model_capabilities import infer_vision_support


def test_kimi_k26_supports_vision() -> None:
    assert infer_vision_support("kimi-k2.6") is True


def test_kimi_k25_supports_vision() -> None:
    assert infer_vision_support("kimi-k2.5") is True


def test_moonshot_v1_does_not_support_vision() -> None:
    assert infer_vision_support("moonshot-v1-8k") is False


def test_gpt4o_supports_vision() -> None:
    assert infer_vision_support("gpt-4o") is True


def test_gpt41_mini_does_not_support_vision() -> None:
    assert infer_vision_support("gpt-4.1-mini") is False


def test_gemini_supports_vision() -> None:
    assert infer_vision_support("gemini-2.0-flash") is True
