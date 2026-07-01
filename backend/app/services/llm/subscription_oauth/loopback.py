from __future__ import annotations

import logging
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib import parse

logger = logging.getLogger(__name__)

CODEX_CALLBACK_PATH = "/auth/callback"
GEMINI_CALLBACK_PATH = "/oauth2callback"


def pick_free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def ensure_loopback_port_available(host: str, port: int) -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind((host, port))
    except OSError as exc:
        raise ValueError(
            f"本地端口 {port} 已被占用，无法接收 OAuth 回调。"
            "请关闭 Codex CLI、Codex VS Code 插件或其他占用 1455 端口的程序后重试。"
        ) from exc
    finally:
        probe.close()


def start_loopback_server(
    *,
    host: str,
    port: int,
    expected_path: str,
    on_callback: Callable[[dict[str, str]], None],
) -> tuple[ThreadingHTTPServer, threading.Thread]:
    callback = on_callback
    expected = expected_path.rstrip("/") or "/"

    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            params = {key: values[0] for key, values in parse.parse_qs(parsed.query).items()}
            logger.info("OAuth loopback request %s %s", self.path, list(params.keys()))

            has_oauth_params = bool(params.get("code") or params.get("error") or params.get("state"))
            if path != expected and not params.get("code"):
                self._respond(
                    404,
                    "<html><body><h2>Not Found</h2></body></html>",
                )
                return
            if not has_oauth_params:
                self._respond(
                    200,
                    "<html><body><p>等待 OAuth 授权回调…</p></body></html>",
                )
                return

            try:
                callback(params)
                body = (
                    "<html><body><h2>授权成功</h2>"
                    "<p>可以关闭此窗口并返回视频 SOP 编辑器。</p>"
                    "<script>setTimeout(function(){window.close();}, 1500);</script>"
                    "</body></html>"
                )
                self._respond(200, body)
            except Exception:  # noqa: BLE001
                logger.exception("OAuth loopback callback failed")
                body = (
                    "<html><body><h2>授权处理失败</h2>"
                    "<p>请返回 LLM 设置页查看错误信息并重试。</p></body></html>"
                )
                self._respond(500, body)

        def _respond(self, status: int, body_html: str) -> None:
            body = body_html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    bind_host = host if host else "127.0.0.1"
    server = ThreadingHTTPServer((bind_host, port), OAuthCallbackHandler)
    server.daemon_threads = True
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("OAuth loopback listening on http://%s:%s%s", bind_host, port, expected_path)
    return server, thread


def stop_loopback_server(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()
