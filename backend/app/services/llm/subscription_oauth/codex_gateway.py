from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

import httpx

from app.core.config import settings
from app.services.llm.progress import ProgressReporter, emit_progress
from app.services.llm.subscription_oauth.constants import CODEX_RESPONSES_URL
from app.services.llm.types import LlmCallResult, LlmErrorCode, ResolvedLlmConfig


def codex_responses_endpoint() -> str:
    return CODEX_RESPONSES_URL


def _mock_enabled(config: ResolvedLlmConfig) -> bool:
    if settings.llm_oauth_mock:
        return True
    return config.access_token.startswith("mock-")


def _ensure_json_keyword_in_input(user_prompt: str) -> str:
    if "json" in user_prompt.lower():
        return user_prompt
    return f"{user_prompt}\n\nRespond with valid JSON only."


def _build_codex_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    image_urls: list[str] | None = None,
) -> dict[str, Any]:
    normalized_user_prompt = _ensure_json_keyword_in_input(user_prompt)
    if image_urls:
        content: list[dict[str, Any]] = [
            {"type": "input_text", "text": normalized_user_prompt},
        ]
        for image_url in image_urls:
            content.append(
                {
                    "type": "input_image",
                    "image_url": image_url,
                    "detail": "auto",
                }
            )
        user_content: list[dict[str, Any]] | str = content
    else:
        user_content = normalized_user_prompt

    return {
        "model": model,
        "store": False,
        "stream": True,
        "instructions": system_prompt,
        "input": [{"role": "user", "content": user_content}],
        "text": {"format": {"type": "json_object"}},
    }


def _build_codex_headers(config: ResolvedLlmConfig) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {config.access_token.strip()}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "OpenAI-Beta": "responses=v1",
        "originator": "video_sop_editor",
        "User-Agent": "video-sop-editor/1.0",
    }
    if config.account_id.strip():
        headers["ChatGPT-Account-Id"] = config.account_id.strip()
    return headers


def generate_codex_json(
    *,
    config: ResolvedLlmConfig,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.4,
    max_tokens: int | None = None,
    on_progress: ProgressReporter | None = None,
) -> LlmCallResult:
    del temperature, max_tokens

    if not config.access_token.strip():
        return LlmCallResult.failure(
            LlmErrorCode.NOT_CONFIGURED,
            "尚未完成 ChatGPT (Codex) 登录，请先在 LLM 设置页连接账号。",
            provider_id=config.provider_id,
            model=config.model,
        )

    if _mock_enabled(config):
        emit_progress(on_progress, "calling_llm", "Codex Mock 模式生成 JSON…", progress=55)
        return LlmCallResult.success(
            {"ok": True, "message": "pong", "source": "codex_mock"},
            provider_id=config.provider_id,
            model=config.model,
        )

    payload = _build_codex_payload(
        model=config.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    headers = _build_codex_headers(config)

    emit_progress(
        on_progress,
        "calling_llm",
        f"正在通过 ChatGPT (Codex) 请求 {config.model}…",
        progress=55,
    )

    timeout = httpx.Timeout(config.timeout_sec, connect=30.0)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, http2=False) as client:
            with client.stream(
                "POST",
                CODEX_RESPONSES_URL,
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code in {401, 403}:
                    return LlmCallResult.failure(
                        LlmErrorCode.AUTH_INVALID,
                        "ChatGPT (Codex) 授权无效或订阅不可用，请重新登录。",
                        provider_id=config.provider_id,
                        model=config.model,
                    )
                if response.status_code >= 400:
                    error_body = response.read().decode("utf-8", errors="replace")[:240]
                    detail = f"Codex 服务返回 HTTP {response.status_code}。"
                    if error_body:
                        detail = f"{detail} {error_body}"
                    return LlmCallResult.failure(
                        LlmErrorCode.HTTP_ERROR,
                        detail,
                        provider_id=config.provider_id,
                        model=config.model,
                    )
                parsed = _collect_and_parse_codex_sse(response)
    except httpx.TimeoutException:
        return LlmCallResult.failure(
            LlmErrorCode.TIMEOUT,
            f"Codex 请求超时（>{config.timeout_sec}s）。",
            provider_id=config.provider_id,
            model=config.model,
        )
    except httpx.HTTPError as exc:
        return LlmCallResult.failure(
            LlmErrorCode.NETWORK,
            f"无法连接 Codex 服务：{exc}",
            provider_id=config.provider_id,
            model=config.model,
        )

    if parsed is None:
        return LlmCallResult.failure(
            LlmErrorCode.EMPTY_RESPONSE,
            "Codex 未返回可解析的 JSON 内容。",
            provider_id=config.provider_id,
            model=config.model,
        )
    return LlmCallResult.success(
        parsed,
        provider_id=config.provider_id,
        model=config.model,
    )


def generate_codex_vision_json(
    *,
    config: ResolvedLlmConfig,
    system_prompt: str,
    user_prompt: str,
    image_urls: list[str],
    temperature: float = 0.2,
    max_tokens: int | None = None,
    on_progress: ProgressReporter | None = None,
) -> LlmCallResult:
    del temperature, max_tokens

    if not config.access_token.strip():
        return LlmCallResult.failure(
            LlmErrorCode.NOT_CONFIGURED,
            "尚未完成 ChatGPT (Codex) 登录，请先在 LLM 设置页连接账号。",
            provider_id=config.provider_id,
            model=config.model,
        )

    if _mock_enabled(config):
        emit_progress(on_progress, "calling_llm", "Codex Vision Mock 模式…", progress=55)
        return LlmCallResult.success(
            {
                "summary": "mock vision analysis",
                "source": "codex_vision_mock",
                "frameCount": len(image_urls),
            },
            provider_id=config.provider_id,
            model=config.model,
        )

    payload = _build_codex_payload(
        model=config.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        image_urls=image_urls,
    )
    headers = _build_codex_headers(config)

    emit_progress(
        on_progress,
        "calling_llm",
        f"正在通过 ChatGPT (Codex) Vision 分析 {len(image_urls)} 帧（{config.model}）…",
        progress=55,
    )

    timeout = httpx.Timeout(config.timeout_sec, connect=30.0)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, http2=False) as client:
            with client.stream(
                "POST",
                CODEX_RESPONSES_URL,
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code in {401, 403}:
                    return LlmCallResult.failure(
                        LlmErrorCode.AUTH_INVALID,
                        "ChatGPT (Codex) 授权无效或当前模型不支持 Vision，请重新登录或更换模型。",
                        provider_id=config.provider_id,
                        model=config.model,
                    )
                if response.status_code >= 400:
                    error_body = response.read().decode("utf-8", errors="replace")[:240]
                    detail = f"Codex Vision 服务返回 HTTP {response.status_code}。"
                    if error_body:
                        detail = f"{detail} {error_body}"
                    return LlmCallResult.failure(
                        LlmErrorCode.HTTP_ERROR,
                        detail,
                        provider_id=config.provider_id,
                        model=config.model,
                    )
                parsed = _collect_and_parse_codex_sse(response)
    except httpx.TimeoutException:
        return LlmCallResult.failure(
            LlmErrorCode.TIMEOUT,
            f"Codex Vision 请求超时（>{config.timeout_sec}s）。",
            provider_id=config.provider_id,
            model=config.model,
        )
    except httpx.HTTPError as exc:
        return LlmCallResult.failure(
            LlmErrorCode.NETWORK,
            f"无法连接 Codex Vision 服务：{exc}",
            provider_id=config.provider_id,
            model=config.model,
        )

    if parsed is None:
        return LlmCallResult.failure(
            LlmErrorCode.EMPTY_RESPONSE,
            "Codex Vision 未返回可解析的 JSON 内容。",
            provider_id=config.provider_id,
            model=config.model,
        )
    return LlmCallResult.success(
        parsed,
        provider_id=config.provider_id,
        model=config.model,
    )


def _collect_and_parse_codex_sse(response: httpx.Response) -> dict[str, Any] | None:
    lines: list[str] = []
    try:
        for line in response.iter_lines():
            if line:
                lines.append(line)
    except httpx.ReadError:
        pass
    if lines:
        parsed = _parse_codex_sse_lines(lines)
        if parsed:
            return parsed
    body = response.text.strip()
    if body:
        return _parse_codex_sse_lines(body.splitlines())
    return None


def _parse_codex_sse_lines(lines: Iterable[str]) -> dict[str, Any] | None:
    text_parts: list[str] = []
    final_response: dict[str, Any] | None = None
    current_event = ""

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if not line:
            continue
        if line.startswith("event: "):
            current_event = line[7:].strip()
            continue
        if not line.startswith("data: "):
            continue

        data_str = line[6:].strip()
        if not data_str or data_str == "[DONE]":
            continue
        try:
            payload = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue

        event_type = str(payload.get("type") or current_event or "").strip()
        if event_type == "response.output_text.delta":
            delta = payload.get("delta")
            if isinstance(delta, str):
                text_parts.append(delta)
            continue
        if event_type == "response.content_part.delta":
            delta = payload.get("delta")
            if isinstance(delta, dict):
                part_text = delta.get("text") or delta.get("content")
                if isinstance(part_text, str):
                    text_parts.append(part_text)
            continue
        if event_type in {"response.completed", "response.done"}:
            nested = payload.get("response")
            if isinstance(nested, dict):
                extracted = _extract_codex_json(nested)
                if extracted:
                    final_response = extracted
            continue
        if event_type == "response.output_item.done":
            item = payload.get("item")
            if isinstance(item, dict):
                extracted = _extract_codex_json({"output": [item]})
                if extracted:
                    final_response = extracted
            continue
        nested_response = payload.get("response")
        if isinstance(nested_response, dict):
            extracted = _extract_codex_json(nested_response)
            if extracted:
                final_response = extracted

    if text_parts:
        parsed = _parse_json_object("".join(text_parts))
        if parsed:
            return parsed
    return final_response


def _extract_codex_json(response_payload: dict[str, Any]) -> dict[str, Any] | None:
    output = response_payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        text = part.get("text")
                        if isinstance(text, str) and text.strip():
                            return _parse_json_object(text)
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return _parse_json_object(output_text)
    return None


def _parse_json_object(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
