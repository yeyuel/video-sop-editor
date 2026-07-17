from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime, timedelta
from http.server import HTTPServer, ThreadingHTTPServer
from typing import Any
from urllib import error, parse, request
from uuid import uuid4

from sqlmodel import Session, select

from app.core.config import settings
from app.models.entities import LlmOAuthPendingEntity, LlmOAuthTokenEntity
from app.services.llm.oauth.modes import OAUTH_MODE_CODEX, OAUTH_MODE_GEMINI_SUBSCRIPTION, auth_type_to_oauth_mode
from app.services.llm.oauth.pkce import generate_code_challenge, generate_code_verifier, generate_oauth_state
from app.services.llm.provider_ids import normalize_provider_id
from app.services.llm.subscription_oauth.adapters import (
    SubscriptionOAuthAdapter,
    get_codex_adapter,
    get_gemini_subscription_adapter,
    subscription_mock_enabled,
)
from app.services.llm.subscription_oauth.constants import GEMINI_CODE_ASSIST_ENDPOINT
from app.services.llm.subscription_oauth.jwt_utils import extract_chatgpt_account_id
from app.services.llm.subscription_oauth.loopback import (
    CODEX_CALLBACK_PATH,
    GEMINI_CALLBACK_PATH,
    ensure_loopback_port_available,
    localhost_bind_hosts,
    pick_free_loopback_port,
    start_loopback_servers,
    stop_loopback_server,
)
from app.services.llm.types import LlmProviderStatus
from app.services.secret_vault import decrypt_api_key_if_needed, encrypt_api_key_if_needed

_loopback_servers: dict[str, list[ThreadingHTTPServer]] = {}
_loopback_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _pending_expiry_minutes() -> int:
    return 15


def start_subscription_oauth(
    session: Session,
    *,
    provider_id: str,
    user_id: str,
    auth_type: str,
) -> tuple[str, str, str, bool]:
    """Return authorization_url, state, message, requires_poll."""
    canonical = normalize_provider_id(provider_id)
    oauth_mode = auth_type_to_oauth_mode(auth_type)
    if oauth_mode not in {OAUTH_MODE_CODEX, OAUTH_MODE_GEMINI_SUBSCRIPTION}:
        raise ValueError(f"不支持的订阅登录类型：{auth_type}")

    _clear_previous_pending_flows(
        session,
        provider_id=canonical,
        user_id=user_id,
        oauth_mode=oauth_mode,
    )

    state = generate_oauth_state()
    code_verifier = generate_code_verifier()
    expires_at = _utc_now() + timedelta(minutes=_pending_expiry_minutes())

    loopback_port = 0
    redirect_uri = ""
    adapter: SubscriptionOAuthAdapter
    if oauth_mode == OAUTH_MODE_CODEX:
        adapter = get_codex_adapter()
        loopback_port = adapter.loopback_port
        redirect_uri = adapter.redirect_uri
        for host in localhost_bind_hosts():
            ensure_loopback_port_available(host, loopback_port)
    else:
        loopback_port = pick_free_loopback_port()
        redirect_uri = f"http://127.0.0.1:{loopback_port}{GEMINI_CALLBACK_PATH}"
        adapter = get_gemini_subscription_adapter(redirect_uri=redirect_uri, loopback_port=loopback_port)

    session.add(
        LlmOAuthPendingEntity(
            state=state,
            provider_id=canonical,
            user_id=user_id,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            oauth_mode=oauth_mode,
            loopback_port=loopback_port,
            flow_status="pending",
            created_at=_iso(_utc_now()),
            expires_at=_iso(expires_at),
        )
    )
    session.commit()

    if subscription_mock_enabled():
        query = parse.urlencode(
            {
                "code": "mock_subscription_code",
                "state": state,
                "provider": canonical,
                "authType": auth_type,
            }
        )
        authorization_url = f"{settings.resolved_llm_oauth_redirect_uri}?{query}"
        return (
            authorization_url,
            state,
            "订阅登录 Mock 模式：将跳转到本地回调页完成授权。",
            False,
        )

    if oauth_mode == OAUTH_MODE_CODEX:
        _start_loopback_listener(session, state=state, user_id=user_id, adapter=adapter)
    else:
        _start_loopback_listener(session, state=state, user_id=user_id, adapter=adapter)

    params: dict[str, str] = {
        "response_type": "code",
        "client_id": adapter.client_id,
        "redirect_uri": adapter.redirect_uri,
        "scope": adapter.scopes,
        "state": state,
        "code_challenge": generate_code_challenge(code_verifier),
        "code_challenge_method": "S256",
    }
    if oauth_mode == OAUTH_MODE_CODEX:
        params["id_token_add_organizations"] = "true"
        params["codex_cli_simplified_flow"] = "true"
        params["originator"] = "video_sop_editor"
    else:
        params["access_type"] = "offline"
        params["prompt"] = "consent"

    authorization_url = f"{adapter.authorize_url}?{parse.urlencode(params)}"
    return authorization_url, state, "请在浏览器中完成授权，完成后请保持本页打开。", True


def poll_subscription_oauth(
    session: Session,
    *,
    state: str,
    user_id: str,
) -> tuple[str, str, LlmOAuthTokenEntity | None]:
    pending = session.get(LlmOAuthPendingEntity, state)
    if not pending or pending.user_id != user_id:
        raise ValueError("OAuth state 无效或已过期，请重新发起授权。")

    expires_at = _parse_iso(pending.expires_at)
    if not expires_at or expires_at < _utc_now():
        session.delete(pending)
        session.commit()
        raise ValueError("OAuth 授权已超时，请重新发起连接。")

    if pending.flow_status == "error":
        message = pending.error_message or "OAuth 授权失败。"
        session.delete(pending)
        session.commit()
        raise ValueError(message)

    if pending.flow_status == "complete":
        entity = session.exec(
            select(LlmOAuthTokenEntity).where(
                LlmOAuthTokenEntity.provider_id == pending.provider_id,
                LlmOAuthTokenEntity.oauth_mode == pending.oauth_mode,
            )
        ).first()
        session.delete(pending)
        session.commit()
        return "complete", "订阅登录授权成功。", entity

    return "pending", "等待浏览器授权完成…", None


def complete_subscription_oauth_callback(
    session: Session,
    *,
    provider_id: str,
    user_id: str,
    auth_type: str,
    code: str,
    state: str,
) -> LlmOAuthTokenEntity:
    canonical = normalize_provider_id(provider_id)
    oauth_mode = auth_type_to_oauth_mode(auth_type)
    pending = session.get(LlmOAuthPendingEntity, state)
    if not pending or pending.provider_id != canonical or pending.oauth_mode != oauth_mode:
        raise ValueError("OAuth state 无效或已过期，请重新发起授权。")
    if pending.user_id != user_id:
        raise ValueError("OAuth 授权用户不匹配。")

    expires_at = _parse_iso(pending.expires_at)
    if not expires_at or expires_at < _utc_now():
        session.delete(pending)
        session.commit()
        raise ValueError("OAuth 授权已超时，请重新发起连接。")

    adapter = _adapter_from_pending(pending)
    token_payload = _exchange_authorization_code(adapter, code=code, code_verifier=pending.code_verifier)
    entity = _persist_subscription_token(session, adapter, user_id, token_payload)
    session.delete(pending)
    session.commit()
    session.refresh(entity)
    return entity


def revoke_subscription_oauth(session: Session, *, provider_id: str, auth_type: str) -> bool:
    canonical = normalize_provider_id(provider_id)
    oauth_mode = auth_type_to_oauth_mode(auth_type)
    entity = session.exec(
        select(LlmOAuthTokenEntity).where(
            LlmOAuthTokenEntity.provider_id == canonical,
            LlmOAuthTokenEntity.oauth_mode == oauth_mode,
        )
    ).first()
    if not entity:
        return False
    entity.status = LlmProviderStatus.INVALID.value
    entity.access_token = ""
    entity.refresh_token = ""
    entity.id_token = ""
    entity.account_id = ""
    entity.project_id = ""
    entity.expires_at = ""
    entity.updated_at = _iso(_utc_now())
    session.add(entity)
    session.commit()
    return True


def subscription_connection_status(
    session: Session,
    *,
    provider_id: str,
    auth_type: str,
) -> tuple[LlmProviderStatus, str]:
    access_token, status, message, _, _ = get_valid_subscription_access_token(
        session,
        provider_id=provider_id,
        auth_type=auth_type,
    )
    if status == LlmProviderStatus.AUTHORIZED:
        label = "ChatGPT (Codex)" if auth_type == "codex_oauth" else "Google 订阅"
        return status, f"{label} 已连接。"
    entity = session.exec(
        select(LlmOAuthTokenEntity).where(
            LlmOAuthTokenEntity.provider_id == normalize_provider_id(provider_id),
            LlmOAuthTokenEntity.oauth_mode == auth_type_to_oauth_mode(auth_type),
        )
    ).first()
    if entity and entity.status == LlmProviderStatus.INVALID.value:
        return LlmProviderStatus.NOT_CONFIGURED, "订阅登录连接已断开。"
    return status, message


def get_valid_subscription_access_token(
    session: Session,
    *,
    provider_id: str,
    auth_type: str,
) -> tuple[str, LlmProviderStatus, str, str, str]:
    """Return access_token, status, message, account_id, project_id."""
    canonical = normalize_provider_id(provider_id)
    oauth_mode = auth_type_to_oauth_mode(auth_type)
    entity = session.exec(
        select(LlmOAuthTokenEntity).where(
            LlmOAuthTokenEntity.provider_id == canonical,
            LlmOAuthTokenEntity.oauth_mode == oauth_mode,
        )
    ).first()
    if not entity or entity.status == LlmProviderStatus.INVALID.value:
        return "", LlmProviderStatus.NOT_CONFIGURED, "尚未完成订阅登录，请先连接账号。", "", ""

    if entity.status == LlmProviderStatus.EXPIRED.value:
        return "", LlmProviderStatus.EXPIRED, "订阅登录已过期，请重新连接。", "", ""

    if entity.oauth_mode == OAUTH_MODE_GEMINI_SUBSCRIPTION and entity.project_id:
        entity.project_id = ""
        entity.updated_at = _iso(_utc_now())
        session.add(entity)
        session.commit()

    project_id = "" if entity.oauth_mode == OAUTH_MODE_GEMINI_SUBSCRIPTION else entity.project_id
    access_token = decrypt_api_key_if_needed(entity.access_token)
    expires_at = _parse_iso(entity.expires_at)
    if access_token and expires_at and expires_at > _utc_now() + timedelta(seconds=30):
        return (
            access_token,
            LlmProviderStatus.AUTHORIZED,
            "",
            entity.account_id,
            project_id,
        )

    refresh_token = decrypt_api_key_if_needed(entity.refresh_token)
    if not refresh_token:
        if access_token:
            return access_token, LlmProviderStatus.AUTHORIZED, "", entity.account_id, project_id
        entity.status = LlmProviderStatus.EXPIRED.value
        session.add(entity)
        session.commit()
        return "", LlmProviderStatus.EXPIRED, "订阅登录已失效，请重新连接。", "", ""

    adapter = _adapter_from_token_entity(entity)
    try:
        refreshed = _refresh_access_token(adapter, refresh_token)
    except ValueError as exc:
        entity.status = LlmProviderStatus.EXPIRED.value
        session.add(entity)
        session.commit()
        return "", LlmProviderStatus.EXPIRED, str(exc), "", ""

    entity = _persist_subscription_token(session, adapter, entity.user_id, refreshed, existing=entity)
    session.commit()
    return (
        decrypt_api_key_if_needed(entity.access_token),
        LlmProviderStatus.AUTHORIZED,
        "",
        entity.account_id,
        "" if entity.oauth_mode == OAUTH_MODE_GEMINI_SUBSCRIPTION else entity.project_id,
    )


def _adapter_from_pending(pending: LlmOAuthPendingEntity) -> SubscriptionOAuthAdapter:
    if pending.oauth_mode == OAUTH_MODE_CODEX:
        return get_codex_adapter()
    return get_gemini_subscription_adapter(
        redirect_uri=pending.redirect_uri,
        loopback_port=pending.loopback_port,
    )


def _adapter_from_token_entity(entity: LlmOAuthTokenEntity) -> SubscriptionOAuthAdapter:
    if entity.oauth_mode == OAUTH_MODE_CODEX:
        return get_codex_adapter()
    return get_gemini_subscription_adapter(
        redirect_uri="http://127.0.0.1/oauth2callback",
        loopback_port=0,
    )


def _start_loopback_listener(
    session: Session,
    *,
    state: str,
    user_id: str,
    adapter: SubscriptionOAuthAdapter,
) -> None:
    port = adapter.loopback_port
    expected_path = CODEX_CALLBACK_PATH if adapter.oauth_mode == OAUTH_MODE_CODEX else GEMINI_CALLBACK_PATH
    hosts = localhost_bind_hosts() if adapter.oauth_mode == OAUTH_MODE_CODEX else ["127.0.0.1"]

    def handle_callback(params: dict[str, str]) -> None:
        if not params:
            return

        callback_state = str(params.get("state", "")).strip()
        if callback_state and callback_state != state:
            message = "OAuth 回调状态不匹配，请重新发起连接。"
            _mark_pending_error(state, message)
            raise ValueError(message)

        if params.get("error"):
            message = str(params.get("error_description") or params["error"])
            _mark_pending_error(state, message)
            raise ValueError(message)

        code = str(params.get("code", "")).strip()
        if not code:
            message = "OAuth 回调缺少 code。"
            _mark_pending_error(state, message)
            raise ValueError(message)
        try:
            from app.db import engine

            with Session(engine) as callback_session:
                pending = callback_session.get(LlmOAuthPendingEntity, state)
                if not pending:
                    raise ValueError("OAuth state 无效或已过期，请重新发起授权。")
                token_payload = _exchange_authorization_code(
                    adapter,
                    code=code,
                    code_verifier=pending.code_verifier,
                )
                _persist_subscription_token(callback_session, adapter, user_id, token_payload)
                pending.flow_status = "complete"
                callback_session.add(pending)
                callback_session.commit()
        except ValueError as exc:
            _mark_pending_error(state, str(exc))
            raise
        except Exception as exc:  # noqa: BLE001
            message = f"OAuth 回调处理异常：{exc}"
            _mark_pending_error(state, message)
            raise RuntimeError(message) from exc
        finally:
            with _loopback_lock:
                servers = _loopback_servers.pop(state, [])
            for server in servers:
                stop_loopback_server(server)

    servers, _threads = start_loopback_servers(
        hosts=hosts,
        port=port,
        expected_path=expected_path,
        on_callback=handle_callback,
    )
    with _loopback_lock:
        previous = _loopback_servers.pop(state, [])
        for server in previous:
            stop_loopback_server(server)
        _loopback_servers[state] = servers


def _clear_previous_pending_flows(
    session: Session,
    *,
    provider_id: str,
    user_id: str,
    oauth_mode: str,
) -> None:
    pending_flows = session.exec(
        select(LlmOAuthPendingEntity).where(
            LlmOAuthPendingEntity.provider_id == provider_id,
            LlmOAuthPendingEntity.user_id == user_id,
            LlmOAuthPendingEntity.oauth_mode == oauth_mode,
        )
    ).all()
    for pending in pending_flows:
        with _loopback_lock:
            servers = _loopback_servers.pop(pending.state, [])
        for server in servers:
            stop_loopback_server(server)
        session.delete(pending)
    if pending_flows:
        session.commit()


def _mark_pending_error(state: str, message: str) -> None:
    from app.db import engine

    with Session(engine) as session:
        pending = session.get(LlmOAuthPendingEntity, state)
        if not pending:
            return
        pending.flow_status = "error"
        pending.error_message = message[:240]
        session.add(pending)
        session.commit()


def _persist_subscription_token(
    session: Session,
    adapter: SubscriptionOAuthAdapter,
    user_id: str,
    payload: dict[str, Any],
    *,
    existing: LlmOAuthTokenEntity | None = None,
) -> LlmOAuthTokenEntity:
    access_token = str(payload.get("access_token", "")).strip()
    if not access_token:
        raise ValueError("OAuth token 响应缺少 access_token。")

    refresh_token = str(payload.get("refresh_token", "")).strip()
    id_token = str(payload.get("id_token", "")).strip()
    expires_in = int(payload.get("expires_in", 3600) or 3600)
    expires_at = _iso(_utc_now() + timedelta(seconds=max(expires_in - 30, 60)))
    scopes = str(payload.get("scope", "")).strip()

    account_id = ""
    project_id = ""
    if adapter.oauth_mode == OAUTH_MODE_CODEX:
        account_id = extract_chatgpt_account_id(id_token, access_token)
    elif adapter.oauth_mode == OAUTH_MODE_GEMINI_SUBSCRIPTION:
        # Personal subscription must not auto-bind cloudaicompanionProject from loadCodeAssist;
        # ghost project IDs route to Code Assist enterprise and return 403 (gemini-cli #25189).
        project_id = ""

    entity = existing or session.exec(
        select(LlmOAuthTokenEntity).where(
            LlmOAuthTokenEntity.provider_id == adapter.provider_id,
            LlmOAuthTokenEntity.oauth_mode == adapter.oauth_mode,
        )
    ).first()
    if not entity:
        entity = LlmOAuthTokenEntity(
            id=f"oauth_{adapter.provider_id}_{adapter.oauth_mode}_{uuid4().hex[:8]}",
            provider_id=adapter.provider_id,
            oauth_mode=adapter.oauth_mode,
            user_id=user_id,
        )

    entity.user_id = user_id
    entity.access_token = encrypt_api_key_if_needed(access_token)
    if refresh_token:
        entity.refresh_token = encrypt_api_key_if_needed(refresh_token)
    if id_token:
        entity.id_token = encrypt_api_key_if_needed(id_token)
    entity.account_id = account_id
    entity.project_id = project_id
    entity.expires_at = expires_at
    entity.scopes = scopes
    entity.status = LlmProviderStatus.AUTHORIZED.value
    entity.updated_at = _iso(_utc_now())
    session.add(entity)
    return entity


def _resolve_gemini_project_id(access_token: str) -> str:
    if subscription_mock_enabled() or access_token.startswith("mock-"):
        return "mock-gemini-project"
    body = json.dumps(
        {
            "metadata": {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
            }
        }
    ).encode("utf-8")
    req = request.Request(
        f"{GEMINI_CODE_ASSIST_ENDPOINT}:loadCodeAssist",
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, json.JSONDecodeError, TimeoutError):
        return ""
    if not isinstance(payload, dict):
        return ""
    project = payload.get("cloudaicompanionProject")
    if isinstance(project, str) and project.strip():
        return project.strip()
    return ""


def _exchange_authorization_code(
    adapter: SubscriptionOAuthAdapter,
    *,
    code: str,
    code_verifier: str,
) -> dict[str, Any]:
    if subscription_mock_enabled() and code in {"mock_subscription_code", "mock_authorization_code"}:
        return {
            "access_token": f"mock-access-{adapter.oauth_mode}",
            "refresh_token": f"mock-refresh-{adapter.oauth_mode}",
            "id_token": f"mock-id-{adapter.oauth_mode}",
            "expires_in": 3600,
            "token_type": "bearer",
            "scope": adapter.scopes,
        }

    fields = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": adapter.redirect_uri,
        "client_id": adapter.client_id,
        "code_verifier": code_verifier,
    }
    if adapter.client_secret:
        fields["client_secret"] = adapter.client_secret
    body = parse.urlencode(fields).encode("utf-8")
    return _post_token(adapter.token_url, body)


def _refresh_access_token(adapter: SubscriptionOAuthAdapter, refresh_token: str) -> dict[str, Any]:
    if subscription_mock_enabled() and refresh_token.startswith("mock-refresh-"):
        return {
            "access_token": f"mock-access-{adapter.oauth_mode}-refreshed",
            "refresh_token": refresh_token,
            "expires_in": 3600,
            "token_type": "bearer",
        }

    fields = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": adapter.client_id,
    }
    if adapter.client_secret:
        fields["client_secret"] = adapter.client_secret
    body = parse.urlencode(fields).encode("utf-8")
    return _post_token(adapter.token_url, body)


def _post_token(url: str, body: bytes) -> dict[str, Any]:
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"OAuth token 交换失败（HTTP {exc.code}）：{detail[:200]}") from exc
    except error.URLError as exc:
        raise ValueError(f"OAuth token 交换网络异常：{exc.reason}") from exc

    if not isinstance(payload, dict):
        raise ValueError("OAuth token 响应格式无效。")
    return payload
