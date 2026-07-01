from __future__ import annotations

from app.services.llm.subscription_oauth.codex_gateway import (
    _build_codex_payload,
    _ensure_json_keyword_in_input,
    _parse_codex_sse_lines,
)


def test_build_codex_payload_requires_stream() -> None:
    payload = _build_codex_payload(
        model="gpt-5.5",
        system_prompt='Return JSON only: {"ok": true}',
        user_prompt='{"task": "connectivity_test"}',
    )
    assert payload["stream"] is True
    assert payload["store"] is False
    assert payload["instructions"]
    assert isinstance(payload["input"], list)
    assert "json" in str(payload["input"][0]["content"]).lower()


def test_ensure_json_keyword_in_input() -> None:
    assert "json" in _ensure_json_keyword_in_input('{"task": "x"}').lower()
    assert _ensure_json_keyword_in_input('Return JSON: {"ok": true}') == 'Return JSON: {"ok": true}'


def test_parse_codex_sse_lines_from_deltas() -> None:
    body = [
        'event: response.output_text.delta',
        'data: {"type":"response.output_text.delta","delta":"{\\"ok\\": "}',
        "",
        'event: response.output_text.delta',
        'data: {"type":"response.output_text.delta","delta":"true, \\"message\\": \\"pong\\"}"}',
        "",
        'event: response.completed',
        'data: {"type":"response.completed"}',
        "",
    ]
    parsed = _parse_codex_sse_lines(body)
    assert parsed == {"ok": True, "message": "pong"}
