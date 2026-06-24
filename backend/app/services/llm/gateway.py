from __future__ import annotations

import json
import threading
import time
from typing import Any
from urllib import error, request

from sqlmodel import Session

from app.db import engine
from app.services.llm.auth import resolve_authorization_header
from app.services.llm.config_store import resolve_active_config
from app.services.llm.model_catalog import (
    resolve_temperature,
    should_disable_kimi_thinking,
    supports_json_response_format,
)
from app.services.llm.progress import ProgressReporter, emit_progress
from app.services.llm.types import LlmCallResult, LlmErrorCode, ResolvedLlmConfig


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


class LlmGateway:
    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        session: Session | None = None,
        on_progress: ProgressReporter | None = None,
    ) -> LlmCallResult:
        with Session(engine) as owned_session:
            active_session = session or owned_session
            config = resolve_active_config(active_session)
            emit_progress(
                on_progress,
                "configuring",
                f"已加载 {config.provider_name} / {config.model}",
                progress=20,
            )
            return self.generate_json_with_config(
                config=config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                on_progress=on_progress,
            )

    def generate_json_with_config(
        self,
        *,
        config: ResolvedLlmConfig,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        max_attempts: int | None = None,
        on_progress: ProgressReporter | None = None,
    ) -> LlmCallResult:
        auth_header, auth_error, auth_message = resolve_authorization_header(config)
        if auth_error:
            return LlmCallResult.failure(
                auth_error,
                auth_message,
                provider_id=config.provider_id,
                model=config.model,
            )

        payload = {
            "model": config.model,
            "temperature": resolve_temperature(config.model, temperature),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if supports_json_response_format(config.provider_id, config.model):
            payload["response_format"] = {"type": "json_object"}
        if should_disable_kimi_thinking(config.provider_id, config.model):
            payload["thinking"] = {"type": "disabled"}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        url = _chat_completions_url(config.base_url)
        raw_payload = json.dumps(payload).encode("utf-8")
        attempts_limit = max_attempts if max_attempts is not None else max(1, config.max_retries + 1)
        last_error = LlmCallResult.failure(
            LlmErrorCode.NETWORK,
            "LLM 请求失败。",
            provider_id=config.provider_id,
            model=config.model,
        )

        for attempt in range(1, attempts_limit + 1):
            http_request = request.Request(
                url,
                data=raw_payload,
                headers={
                    "Authorization": auth_header or "",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            emit_progress(
                on_progress,
                "calling_llm",
                f"正在请求 {config.provider_name} 生成内容…",
                progress=35,
                detail=f"模型 {config.model}，超时 {config.timeout_sec}s",
            )
            stop_heartbeat = threading.Event()
            heartbeat_error: list[Exception] = []

            def heartbeat() -> None:
                elapsed = 0
                while not stop_heartbeat.wait(5):
                    elapsed += 5
                    try:
                        emit_progress(
                            on_progress,
                            "calling_llm",
                            f"模型仍在生成，已等待 {elapsed}s…",
                            progress=min(35 + elapsed // 2, 78),
                            detail="复杂任务通常需要 30–90 秒",
                        )
                    except Exception as exc:  # noqa: BLE001
                        heartbeat_error.append(exc)
                        return

            heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
            if on_progress is not None:
                heartbeat_thread.start()
            try:
                with request.urlopen(http_request, timeout=config.timeout_sec) as response:
                    response_payload = json.loads(response.read().decode("utf-8"))
            except TimeoutError:
                last_error = LlmCallResult.failure(
                    LlmErrorCode.TIMEOUT,
                    f"LLM 请求超时（>{config.timeout_sec}s）。",
                    provider_id=config.provider_id,
                    model=config.model,
                    attempts=attempt,
                )
            except error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")[:240]
                if exc.code in {401, 403}:
                    return LlmCallResult.failure(
                        LlmErrorCode.AUTH_INVALID,
                        "LLM API Key 无效或无权访问当前模型。",
                        provider_id=config.provider_id,
                        model=config.model,
                        attempts=attempt,
                    )
                detail = f"LLM 服务返回 HTTP {exc.code}。"
                if exc.code == 404:
                    detail = f"LLM 接口不存在（HTTP 404），请检查 Base URL 是否为 {url}。"
                if error_body:
                    detail = f"{detail} {error_body}"
                last_error = LlmCallResult.failure(
                    LlmErrorCode.HTTP_ERROR,
                    detail,
                    provider_id=config.provider_id,
                    model=config.model,
                    attempts=attempt,
                )
            except error.URLError as exc:
                last_error = LlmCallResult.failure(
                    LlmErrorCode.NETWORK,
                    f"无法连接 LLM 服务：{exc.reason}",
                    provider_id=config.provider_id,
                    model=config.model,
                    attempts=attempt,
                )
            except json.JSONDecodeError:
                last_error = LlmCallResult.failure(
                    LlmErrorCode.PARSE_ERROR,
                    "LLM 响应不是合法 JSON。",
                    provider_id=config.provider_id,
                    model=config.model,
                    attempts=attempt,
                )
            else:
                emit_progress(
                    on_progress,
                    "parsing",
                    "正在解析模型返回的 JSON…",
                    progress=82,
                )
                parsed = self._extract_json_payload(response_payload)
                if parsed is None:
                    detail = self._describe_empty_llm_response(response_payload)
                    return LlmCallResult.failure(
                        LlmErrorCode.EMPTY_RESPONSE,
                        detail,
                        provider_id=config.provider_id,
                        model=config.model,
                        attempts=attempt,
                    )
                return LlmCallResult.success(
                    parsed,
                    provider_id=config.provider_id,
                    model=config.model,
                    attempts=attempt,
                )
            finally:
                stop_heartbeat.set()
                if on_progress is not None:
                    heartbeat_thread.join(timeout=0.2)
                if heartbeat_error:
                    raise heartbeat_error[0]

            if attempt < attempts_limit and last_error.error_code not in {
                LlmErrorCode.TIMEOUT,
                LlmErrorCode.AUTH_INVALID,
                LlmErrorCode.NOT_CONFIGURED,
                LlmErrorCode.UNSUPPORTED_AUTH,
            }:
                time.sleep(0.4 * attempt)

        return last_error

    def test_connection(self, config: ResolvedLlmConfig) -> tuple[LlmCallResult, int, str]:
        started = time.perf_counter()
        result = self.generate_json_with_config(
            config=config,
            system_prompt='Return JSON only: {"ok": true, "message": "pong"}',
            user_prompt='{"task": "connectivity_test"}',
            temperature=resolve_temperature(config.model, 0),
            max_attempts=1,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        endpoint = _chat_completions_url(config.base_url)
        return result, latency_ms, endpoint

    @staticmethod
    def _flatten_message_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
                    continue
                if item.get("type") == "text":
                    nested = item.get("content")
                    if isinstance(nested, str) and nested:
                        parts.append(nested)
            return "".join(parts)
        return ""

    @staticmethod
    def _strip_markdown_fence(text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @classmethod
    def _parse_json_object(cls, text: str) -> dict[str, Any] | None:
        candidate = cls._strip_markdown_fence(text)
        if not candidate:
            return None
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

    @classmethod
    def _describe_empty_llm_response(cls, response_payload: dict[str, Any]) -> str:
        choice = response_payload.get("choices", [{}])[0]
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        finish_reason = str(choice.get("finish_reason", "")) if isinstance(choice, dict) else ""
        content_text = cls._flatten_message_content(message.get("content"))
        reasoning_text = message.get("reasoning_content")
        has_reasoning = isinstance(reasoning_text, str) and bool(reasoning_text.strip())

        if finish_reason == "length":
            return "LLM 输出被 max_tokens 截断，无法解析 JSON。"
        if has_reasoning and not content_text.strip():
            return (
                "LLM 思考过程占满了输出配额，未返回 JSON 正文。"
                "请关闭 thinking 模式、增大 max_tokens，或改用 moonshot-v1-8k。"
            )
        return "LLM 未返回可解析的内容。"

    @classmethod
    def _extract_json_payload(cls, response_payload: dict[str, Any]) -> dict[str, Any] | None:
        choice = response_payload.get("choices", [{}])[0]
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        content_text = cls._flatten_message_content(message.get("content"))
        if not content_text.strip():
            return None
        return cls._parse_json_object(content_text)


llm_gateway = LlmGateway()


class LlmSuggestionService:
    """兼容旧调用方：返回 dict 或 None。"""

    @property
    def enabled(self) -> bool:
        with Session(engine) as session:
            config = resolve_active_config(session)
            return bool(config.api_key.strip())

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
    ) -> dict[str, Any] | None:
        result = llm_gateway.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )
        return result.data if result.ok else None

    def generate_json_result(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        session: Session | None = None,
        on_progress: ProgressReporter | None = None,
    ) -> LlmCallResult:
        return llm_gateway.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            session=session,
            on_progress=on_progress,
        )


llm_suggestion_service = LlmSuggestionService()
