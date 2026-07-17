from __future__ import annotations

import threading
from urllib import error, request

from app.services.llm.subscription_oauth.loopback import (
    GEMINI_CALLBACK_PATH,
    start_loopback_server,
    stop_loopback_server,
)


def test_loopback_ignores_requests_without_oauth_params() -> None:
    calls: list[dict[str, str]] = []

    def on_callback(params: dict[str, str]) -> None:
        calls.append(params)

    server, _thread = start_loopback_server(
        host="127.0.0.1",
        port=0,
        expected_path=GEMINI_CALLBACK_PATH,
        on_callback=on_callback,
    )
    port = server.server_address[1]
    try:
        with request.urlopen(f"http://127.0.0.1:{port}{GEMINI_CALLBACK_PATH}") as response:
            assert response.status == 200
        try:
            request.urlopen(f"http://127.0.0.1:{port}/favicon.ico")
        except error.HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("expected 404 for favicon.ico")
        assert calls == []
    finally:
        stop_loopback_server(server)


def test_loopback_invokes_callback_for_code_and_state() -> None:
    received = threading.Event()
    payload: dict[str, str] = {}

    def on_callback(params: dict[str, str]) -> None:
        payload.update(params)
        received.set()

    server, _thread = start_loopback_server(
        host="127.0.0.1",
        port=0,
        expected_path=GEMINI_CALLBACK_PATH,
        on_callback=on_callback,
    )
    port = server.server_address[1]
    try:
        url = f"http://127.0.0.1:{port}{GEMINI_CALLBACK_PATH}?code=abc&state=xyz"
        with request.urlopen(url) as response:
            assert response.status == 200
        assert received.wait(timeout=2)
        assert payload == {"code": "abc", "state": "xyz"}
    finally:
        stop_loopback_server(server)


def test_loopback_returns_error_when_callback_processing_fails() -> None:
    def on_callback(_params: dict[str, str]) -> None:
        raise ValueError("state mismatch")

    server, _thread = start_loopback_server(
        host="127.0.0.1",
        port=0,
        expected_path=GEMINI_CALLBACK_PATH,
        on_callback=on_callback,
    )
    port = server.server_address[1]
    try:
        url = f"http://127.0.0.1:{port}{GEMINI_CALLBACK_PATH}?code=abc&state=wrong"
        try:
            request.urlopen(url)
        except error.HTTPError as exc:
            assert exc.code == 500
            assert "授权处理失败" in exc.read().decode("utf-8")
        else:
            raise AssertionError("expected callback processing to return 500")
    finally:
        stop_loopback_server(server)
