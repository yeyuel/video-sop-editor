from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from app.core.config import settings


class LlmSuggestionService:
    @property
    def enabled(self) -> bool:
        return bool(settings.resolved_llm_api_key)

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        payload = {
            "model": settings.resolved_llm_model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        url = f"{settings.resolved_llm_base_url.rstrip('/')}/chat/completions"
        raw_payload = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            url,
            data=raw_payload,
            headers={
                "Authorization": f"Bearer {settings.resolved_llm_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=settings.resolved_llm_timeout_sec) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return None

        message = (
            response_payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if isinstance(message, list):
            message = "".join(
                item.get("text", "") for item in message if isinstance(item, dict)
            )
        if not isinstance(message, str) or not message.strip():
            return None

        try:
            return json.loads(message)
        except json.JSONDecodeError:
            start = message.find("{")
            end = message.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                return json.loads(message[start : end + 1])
            except json.JSONDecodeError:
                return None


llm_suggestion_service = LlmSuggestionService()
