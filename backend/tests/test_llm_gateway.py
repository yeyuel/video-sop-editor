from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from app.services.llm.auth import resolve_authorization_header
from app.services.llm.gateway import LlmGateway
from app.services.llm.registry import get_provider, list_providers
from app.services.llm.types import LlmCallResult, LlmErrorCode, LlmProviderStatus, ResolvedLlmConfig, build_llm_meta


def test_list_providers_includes_openai() -> None:
    providers = list_providers()
    ids = {item.provider_id for item in providers}
    assert "openai" in ids
    assert "openai-compatible" not in ids
    assert "deepseek" in ids


def test_get_provider_normalizes_id_and_alias() -> None:
    provider = get_provider("DeepSeek")
    assert provider is not None
    assert provider.provider_id == "deepseek"
    alias = get_provider("openai-compatible")
    assert alias is not None
    assert alias.provider_id == "openai"


def test_resolve_authorization_header_not_configured() -> None:
    config = ResolvedLlmConfig(
        provider_id="openai",
        provider_name="OpenAI",
        auth_type="api_key",
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        api_key="",
    )
    header, error, message = resolve_authorization_header(config)
    assert header is None
    assert error == LlmErrorCode.NOT_CONFIGURED
    assert "API Key" in message


def test_resolve_authorization_header_api_key() -> None:
    config = ResolvedLlmConfig(
        provider_id="openai",
        provider_name="OpenAI",
        auth_type="api_key",
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        api_key="secret-key",
    )
    header, error, message = resolve_authorization_header(config)
    assert header == "Bearer secret-key"
    assert error is None
    assert message == ""


def test_build_llm_meta_success() -> None:
    meta = build_llm_meta(
        LlmCallResult.success({"themes": []}, provider_id="deepseek", model="deepseek-chat")
    )
    assert meta.llmStatus == "success"
    assert meta.llmUsedFallback == "false"


def test_build_llm_meta_exposes_cache_hit() -> None:
    meta = build_llm_meta(
        LlmCallResult.success(
            {"themes": []},
            provider_id="deepseek",
            model="deepseek-chat",
            attempts=0,
            cached=True,
            input_fingerprint="abc123",
        )
    )
    assert meta.llmStatus == "success"
    assert meta.llmCacheHit == "true"
    assert meta.llmInputFingerprint == "abc123"
    assert meta.llmAttempts == "0"
    assert "复用" in meta.llmMessage


def test_gateway_reuses_successful_result_cache(regression_env: dict, monkeypatch) -> None:
    gateway = LlmGateway()
    engine = regression_env["engine"]
    config = ResolvedLlmConfig(
        provider_id="deepseek",
        provider_name="DeepSeek",
        auth_type="api_key",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        api_key="test-key",
        status=LlmProviderStatus.CONFIGURED,
    )
    calls = 0

    def fake_generate_json_with_config(**kwargs):
        nonlocal calls
        calls += 1
        return LlmCallResult.success(
            {"themes": [{"title": "缓存主题"}]},
            provider_id=config.provider_id,
            model=config.model,
        )

    monkeypatch.setattr(
        "app.services.llm.gateway.resolve_active_config",
        lambda session: config,
    )
    monkeypatch.setattr(
        "app.services.llm.gateway.enrich_config_with_auth",
        lambda session, resolved: resolved,
    )
    monkeypatch.setattr(gateway, "generate_json_with_config", fake_generate_json_with_config)

    with Session(engine) as session:
        first = gateway.generate_json(
            system_prompt="system-v1",
            user_prompt='{"project":"demo"}',
            max_tokens=800,
            session=session,
        )
        second = gateway.generate_json(
            system_prompt="system-v1",
            user_prompt='{"project":"demo"}',
            max_tokens=800,
            session=session,
        )
        changed = gateway.generate_json(
            system_prompt="system-v1",
            user_prompt='{"project":"changed"}',
            max_tokens=800,
            session=session,
        )

    assert first.ok and not first.cached
    assert second.ok and second.cached
    assert second.attempts == 0
    assert second.data == first.data
    assert second.input_fingerprint == first.input_fingerprint
    assert changed.ok and not changed.cached
    assert changed.input_fingerprint != first.input_fingerprint
    assert calls == 2


def test_build_llm_meta_fallback() -> None:
    meta = build_llm_meta(
        LlmCallResult.failure(
            LlmErrorCode.NOT_CONFIGURED,
            "未配置 LLM API Key。",
            provider_id="openai-compatible",
            model="gpt-4.1-mini",
        ),
        used_fallback=True,
    )
    assert meta.llmStatus == "fallback_rule"
    assert meta.llmErrorCode == "not_configured"
    assert meta.llmUsedFallback == "true"
    assert "回退" in meta.llmMessage


def test_gateway_not_configured_short_circuit() -> None:
    gateway = LlmGateway()
    with patch("app.services.llm.gateway.resolve_active_config") as mock_config:
        mock_config.return_value = ResolvedLlmConfig(
            provider_id="openai-compatible",
            provider_name="OpenAI Compatible",
            auth_type="api_key",
            base_url="https://api.openai.com/v1",
            model="gpt-4.1-mini",
            api_key="",
            status=LlmProviderStatus.NOT_CONFIGURED,
        )
        result = gateway.generate_json(
            system_prompt="test",
            user_prompt="{}",
            session=MagicMock(spec=Session),
        )
    assert not result.ok
    assert result.error_code == LlmErrorCode.NOT_CONFIGURED


def test_gateway_includes_max_tokens_in_payload() -> None:
    gateway = LlmGateway()
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"ok": true}',
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout=0):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    config = ResolvedLlmConfig(
        provider_id="openai",
        provider_name="OpenAI",
        auth_type="api_key",
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        api_key="secret-key",
    )

    with patch("app.services.llm.gateway.request.urlopen", fake_urlopen):
        result = gateway.generate_json_with_config(
            config=config,
            system_prompt="test",
            user_prompt="{}",
            max_tokens=1200,
            max_attempts=1,
        )

    assert result.ok
    assert captured["body"]["max_tokens"] == 1200


def test_gateway_disables_kimi_thinking_for_k2_6() -> None:
    gateway = LlmGateway()
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"themes": []}',
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout=0):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    config = ResolvedLlmConfig(
        provider_id="kimi",
        provider_name="Kimi",
        auth_type="api_key",
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k2.6",
        api_key="secret-key",
    )

    with patch("app.services.llm.gateway.request.urlopen", fake_urlopen):
        result = gateway.generate_json_with_config(
            config=config,
            system_prompt="test",
            user_prompt="{}",
            max_attempts=1,
        )

    assert result.ok
    assert captured["body"]["thinking"] == {"type": "disabled"}


def test_extract_json_payload_parses_markdown_fence() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": '```json\n{"themes": [{"title": "A"}]}\n```',
                }
            }
        ]
    }

    parsed = LlmGateway._extract_json_payload(payload)

    assert parsed == {"themes": [{"title": "A"}]}


def test_describe_empty_llm_response_when_reasoning_only() -> None:
    payload = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": "",
                    "reasoning_content": "long internal reasoning...",
                },
            }
        ]
    }

    message = LlmGateway._describe_empty_llm_response(payload)

    assert "思考过程" in message


def test_describe_empty_llm_response_when_truncated() -> None:
    payload = {
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "content": '{"themes": [',
                },
            }
        ]
    }

    message = LlmGateway._describe_empty_llm_response(payload)

    assert "截断" in message
