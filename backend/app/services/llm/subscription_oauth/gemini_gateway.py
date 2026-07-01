from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request

from app.core.config import settings
from app.services.llm.progress import ProgressReporter, emit_progress
from app.services.llm.subscription_oauth.constants import GEMINI_CODE_ASSIST_ENDPOINT, GEMINI_GENAI_ENDPOINT
from app.services.llm.types import LlmCallResult, LlmErrorCode, ResolvedLlmConfig


def _mock_enabled(config: ResolvedLlmConfig) -> bool:
    if settings.llm_oauth_mock:
        return True
    return config.access_token.startswith("mock-")


def generate_gemini_subscription_json(
    *,
    config: ResolvedLlmConfig,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.4,
    max_tokens: int | None = None,
    on_progress: ProgressReporter | None = None,
) -> LlmCallResult:
    if not config.access_token.strip():
        return LlmCallResult.failure(
            LlmErrorCode.NOT_CONFIGURED,
            "尚未完成 Google 订阅登录，请先在 LLM 设置页连接账号。",
            provider_id=config.provider_id,
            model=config.model,
        )

    if _mock_enabled(config):
        emit_progress(on_progress, "calling_llm", "Gemini 订阅 Mock 模式生成 JSON…", progress=55)
        return LlmCallResult.success(
            {"ok": True, "message": "pong", "source": "gemini_subscription_mock"},
            provider_id=config.provider_id,
            model=config.model,
        )

    emit_progress(
        on_progress,
        "calling_llm",
        f"正在通过 Gemini 订阅请求 {config.model}…",
        progress=55,
    )

    project_id = config.project_id.strip()
    if project_id:
        result = _generate_via_code_assist(
            config=config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if result.ok or result.error_code != LlmErrorCode.AUTH_INVALID:
            return result
        emit_progress(
            on_progress,
            "calling_llm",
            "Code Assist 不可用，改用 Gemini API…",
            progress=58,
        )

    return _generate_via_genai(
        config=config,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _generate_via_code_assist(
    *,
    config: ResolvedLlmConfig,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int | None,
) -> LlmCallResult:
    payload: dict[str, Any] = {
        "model": config.model,
        "project": config.project_id.strip(),
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        },
    }
    if max_tokens is not None:
        payload["request"]["generationConfig"]["maxOutputTokens"] = max_tokens

    http_request = request.Request(
        f"{GEMINI_CODE_ASSIST_ENDPOINT}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.access_token.strip()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    return _execute_request(config, http_request, parser=_parse_code_assist_response)


def _generate_via_genai(
    *,
    config: ResolvedLlmConfig,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int | None,
) -> LlmCallResult:
    model = config.model.removeprefix("models/")
    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
        },
    }
    if max_tokens is not None:
        payload["generationConfig"]["maxOutputTokens"] = max_tokens

    query = parse.urlencode({"alt": "json"})
    url = f"{GEMINI_GENAI_ENDPOINT}/models/{model}:generateContent?{query}"
    headers = {
        "Authorization": f"Bearer {config.access_token.strip()}",
        "Content-Type": "application/json",
    }
    if config.project_id.strip():
        headers["x-goog-user-project"] = config.project_id.strip()
    http_request = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    return _execute_request(config, http_request, parser=_parse_genai_response)


def _execute_request(
    config: ResolvedLlmConfig,
    http_request: request.Request,
    *,
    parser: Any,
) -> LlmCallResult:
    try:
        with request.urlopen(http_request, timeout=config.timeout_sec) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except TimeoutError:
        return LlmCallResult.failure(
            LlmErrorCode.TIMEOUT,
            f"Gemini 订阅请求超时（>{config.timeout_sec}s）。",
            provider_id=config.provider_id,
            model=config.model,
        )
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:240]
        if exc.code in {401, 403}:
            detail = "Google 订阅授权无效或配额不可用，请重新登录或使用 API Key。"
            if error_body:
                detail = f"{detail} ({error_body})"
            return LlmCallResult.failure(
                LlmErrorCode.AUTH_INVALID,
                detail,
                provider_id=config.provider_id,
                model=config.model,
            )
        detail = f"Gemini 订阅服务返回 HTTP {exc.code}。"
        if error_body:
            detail = f"{detail} {error_body}"
        return LlmCallResult.failure(
            LlmErrorCode.HTTP_ERROR,
            detail,
            provider_id=config.provider_id,
            model=config.model,
        )
    except error.URLError as exc:
        return LlmCallResult.failure(
            LlmErrorCode.NETWORK,
            f"无法连接 Gemini 订阅服务：{exc.reason}",
            provider_id=config.provider_id,
            model=config.model,
        )
    except json.JSONDecodeError:
        return LlmCallResult.failure(
            LlmErrorCode.PARSE_ERROR,
            "Gemini 订阅响应不是合法 JSON。",
            provider_id=config.provider_id,
            model=config.model,
        )

    parsed = parser(response_payload)
    if parsed is None:
        return LlmCallResult.failure(
            LlmErrorCode.EMPTY_RESPONSE,
            "Gemini 订阅未返回可解析的 JSON 内容。",
            provider_id=config.provider_id,
            model=config.model,
        )
    return LlmCallResult.success(
        parsed,
        provider_id=config.provider_id,
        model=config.model,
    )


def _parse_code_assist_response(response_payload: dict[str, Any]) -> dict[str, Any] | None:
    response = response_payload.get("response")
    if isinstance(response, dict):
        return _parse_genai_response(response)
    return _parse_genai_response(response_payload)


def _parse_genai_response(response_payload: dict[str, Any]) -> dict[str, Any] | None:
    candidates = response_payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    first = candidates[0]
    if not isinstance(first, dict):
        return None
    content = first.get("content")
    if not isinstance(content, dict):
        return None
    parts = content.get("parts")
    if not isinstance(parts, list):
        return None
    for part in parts:
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                try:
                    parsed = json.loads(text)
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    start = text.find("{")
                    end = text.rfind("}")
                    if start != -1 and end > start:
                        try:
                            parsed = json.loads(text[start : end + 1])
                            return parsed if isinstance(parsed, dict) else None
                        except json.JSONDecodeError:
                            return None
    return None
