from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class LlmErrorCode(StrEnum):
    NOT_CONFIGURED = "not_configured"
    AUTH_INVALID = "auth_invalid"
    TIMEOUT = "timeout"
    NETWORK = "network"
    HTTP_ERROR = "http_error"
    EMPTY_RESPONSE = "empty_response"
    PARSE_ERROR = "parse_error"
    UNSUPPORTED_AUTH = "unsupported_auth"
    NOT_IMPLEMENTED = "not_implemented"


class LlmProviderStatus(StrEnum):
    CONFIGURED = "configured"
    AUTHORIZED = "authorized"
    NOT_CONFIGURED = "not_configured"
    EXPIRED = "expired"
    INVALID = "invalid"


@dataclass
class LlmCallResult:
    ok: bool
    data: dict[str, Any] | None = None
    error_code: LlmErrorCode | None = None
    message: str = ""
    provider_id: str = ""
    model: str = ""
    attempts: int = 1

    @classmethod
    def success(
        cls,
        data: dict[str, Any],
        *,
        provider_id: str,
        model: str,
        attempts: int = 1,
    ) -> LlmCallResult:
        return cls(
            ok=True,
            data=data,
            provider_id=provider_id,
            model=model,
            attempts=attempts,
        )

    @classmethod
    def failure(
        cls,
        error_code: LlmErrorCode,
        message: str,
        *,
        provider_id: str = "",
        model: str = "",
        attempts: int = 1,
    ) -> LlmCallResult:
        return cls(
            ok=False,
            error_code=error_code,
            message=message,
            provider_id=provider_id,
            model=model,
            attempts=attempts,
        )


@dataclass
class ModelOption:
    model_id: str
    label: str
    description: str = ""
    recommended: bool = False


@dataclass
class ProviderDefinition:
    provider_id: str
    provider_name: str
    auth_types: list[str]
    default_base_url: str
    default_model: str
    openai_compatible: bool = True
    docs_url: str = ""
    supported_models: list[ModelOption] = field(default_factory=list)


@dataclass
class ResolvedLlmConfig:
    provider_id: str
    provider_name: str
    auth_type: str
    base_url: str
    model: str
    api_key: str = ""
    timeout_sec: int = 45
    max_retries: int = 0
    status: LlmProviderStatus = LlmProviderStatus.NOT_CONFIGURED


@dataclass
class LlmMeta:
    llmStatus: str
    llmMessage: str
    llmProviderId: str = ""
    llmUsedFallback: str = "false"

    def as_dict(self) -> dict[str, str]:
        return {
            "llmStatus": self.llmStatus,
            "llmMessage": self.llmMessage,
            "llmProviderId": self.llmProviderId,
            "llmUsedFallback": self.llmUsedFallback,
        }


def build_llm_meta(
    result: LlmCallResult,
    *,
    used_fallback: bool = False,
    fallback_message: str = "",
) -> LlmMeta:
    if result.ok:
        return LlmMeta(
            llmStatus="success",
            llmMessage="LLM 建议生成成功。",
            llmProviderId=result.provider_id,
            llmUsedFallback="false",
        )

    status = result.error_code.value if result.error_code else "unknown"
    message = result.message or fallback_message or "LLM 调用失败。"
    if used_fallback:
        message = f"{message} 已回退到规则生成。"
    return LlmMeta(
        llmStatus=status if not used_fallback else "fallback_rule",
        llmMessage=message,
        llmProviderId=result.provider_id,
        llmUsedFallback="true" if used_fallback else "false",
    )
