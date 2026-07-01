from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib import error, parse, request
from uuid import uuid4

from sqlmodel import Session, select

from app.models.entities import LlmOAuthPendingEntity, LlmOAuthTokenEntity
from app.services.llm.oauth.adapters import OAuthAdapter, get_oauth_adapter, oauth_mock_enabled
from app.services.llm.oauth.modes import OAUTH_MODE_PLATFORM
from app.services.llm.oauth.pkce import generate_code_challenge, generate_code_verifier, generate_oauth_state
from app.services.llm.provider_ids import normalize_provider_id
from app.services.llm.types import LlmProviderStatus
from app.services.secret_vault import decrypt_api_key_if_needed, encrypt_api_key_if_needed


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


def start_oauth_flow(
    session: Session,
    *,
    provider_id: str,
    user_id: str,
) -> tuple[str, str, str]:
    """Return authorization_url, state, message."""
    canonical = normalize_provider_id(provider_id)
    adapter = get_oauth_adapter(canonical)
    if not adapter:
        raise ValueError(
            f"Provider {canonical} 的 OAuth 尚未配置 Client ID。"
            "请在环境变量中设置 OPENAI_OAUTH_CLIENT_ID 或 GOOGLE_OAUTH_CLIENT_ID，"
            "或开启 LLM_OAUTH_MOCK 用于本地测试。"
        )

    state = generate_oauth_state()
    code_verifier = generate_code_verifier()
    expires_at = _utc_now() + timedelta(minutes=_pending_expiry_minutes())

    session.add(
        LlmOAuthPendingEntity(
            state=state,
            provider_id=canonical,
            user_id=user_id,
            code_verifier=code_verifier,
            redirect_uri=adapter.redirect_uri,
            oauth_mode=OAUTH_MODE_PLATFORM,
            created_at=_iso(_utc_now()),
            expires_at=_iso(expires_at),
        )
    )
    session.commit()

    if oauth_mock_enabled(adapter):
        query = parse.urlencode(
            {
                "code": "mock_authorization_code",
                "state": state,
                "provider": canonical,
            }
        )
        authorization_url = f"{adapter.redirect_uri}?{query}"
        return (
            authorization_url,
            state,
            "OAuth Mock 模式：将跳转到本地回调页完成授权。",
        )

    params = {
        "response_type": "code",
        "client_id": adapter.client_id,
        "redirect_uri": adapter.redirect_uri,
        "scope": adapter.scopes,
        "state": state,
        "code_challenge": generate_code_challenge(code_verifier),
        "code_challenge_method": "S256",
    }
    if canonical == "google":
        params["access_type"] = "offline"
        params["prompt"] = "consent"

    authorization_url = f"{adapter.authorize_url}?{parse.urlencode(params)}"
    return authorization_url, state, "请在浏览器中完成授权。"


def complete_oauth_callback(
    session: Session,
    *,
    provider_id: str,
    user_id: str,
    code: str,
    state: str,
) -> LlmOAuthTokenEntity:
    canonical = normalize_provider_id(provider_id)
    pending = session.get(LlmOAuthPendingEntity, state)
    if not pending or pending.provider_id != canonical:
        raise ValueError("OAuth state 无效或已过期，请重新发起授权。")
    if pending.user_id != user_id:
        raise ValueError("OAuth 授权用户不匹配。")

    expires_at = _parse_iso(pending.expires_at)
    if not expires_at or expires_at < _utc_now():
        session.delete(pending)
        session.commit()
        raise ValueError("OAuth 授权已超时，请重新发起连接。")

    adapter = get_oauth_adapter(canonical)
    if not adapter:
        raise ValueError(f"Provider {canonical} OAuth 未配置。")

    token_payload = _exchange_authorization_code(
        adapter,
        code=code,
        code_verifier=pending.code_verifier,
    )
    entity = _persist_token(session, canonical, user_id, token_payload)
    session.delete(pending)
    session.commit()
    session.refresh(entity)
    return entity


def revoke_oauth_token(session: Session, *, provider_id: str) -> bool:
    canonical = normalize_provider_id(provider_id)
    entity = session.exec(
        select(LlmOAuthTokenEntity).where(
            LlmOAuthTokenEntity.provider_id == canonical,
            LlmOAuthTokenEntity.oauth_mode == OAUTH_MODE_PLATFORM,
        )
    ).first()
    if not entity:
        return False
    entity.status = LlmProviderStatus.INVALID.value
    entity.access_token = ""
    entity.refresh_token = ""
    entity.expires_at = ""
    entity.updated_at = _iso(_utc_now())
    session.add(entity)
    session.commit()
    return True


def get_valid_access_token(session: Session, *, provider_id: str) -> tuple[str, LlmProviderStatus, str]:
    canonical = normalize_provider_id(provider_id)
    entity = session.exec(
        select(LlmOAuthTokenEntity).where(
            LlmOAuthTokenEntity.provider_id == canonical,
            LlmOAuthTokenEntity.oauth_mode == OAUTH_MODE_PLATFORM,
        )
    ).first()
    if not entity or entity.status == LlmProviderStatus.INVALID.value:
        return "", LlmProviderStatus.NOT_CONFIGURED, "尚未完成 OAuth 授权，请先连接账号。"

    if entity.status == LlmProviderStatus.EXPIRED.value:
        return "", LlmProviderStatus.EXPIRED, "OAuth 授权已过期，请重新连接。"

    access_token = decrypt_api_key_if_needed(entity.access_token)
    expires_at = _parse_iso(entity.expires_at)
    if access_token and expires_at and expires_at > _utc_now() + timedelta(seconds=30):
        return access_token, LlmProviderStatus.AUTHORIZED, ""

    refresh_token = decrypt_api_key_if_needed(entity.refresh_token)
    if not refresh_token:
        if access_token:
            return access_token, LlmProviderStatus.AUTHORIZED, ""
        entity.status = LlmProviderStatus.EXPIRED.value
        session.add(entity)
        session.commit()
        return "", LlmProviderStatus.EXPIRED, "OAuth 授权已失效，请重新连接。"

    adapter = get_oauth_adapter(canonical)
    if not adapter:
        return "", LlmProviderStatus.NOT_CONFIGURED, "OAuth Client 未配置。"

    try:
        refreshed = _refresh_access_token(adapter, refresh_token)
    except ValueError as exc:
        entity.status = LlmProviderStatus.EXPIRED.value
        session.add(entity)
        session.commit()
        return "", LlmProviderStatus.EXPIRED, str(exc)

    entity = _persist_token(session, canonical, entity.user_id, refreshed, existing=entity)
    session.commit()
    return (
        decrypt_api_key_if_needed(entity.access_token),
        LlmProviderStatus.AUTHORIZED,
        "",
    )


def oauth_connection_status(session: Session, *, provider_id: str) -> tuple[LlmProviderStatus, str]:
    canonical = normalize_provider_id(provider_id)
    _, status, message = get_valid_access_token(session, provider_id=canonical)
    if status == LlmProviderStatus.AUTHORIZED:
        return status, "OAuth 已连接。"
    entity = session.exec(
        select(LlmOAuthTokenEntity).where(
            LlmOAuthTokenEntity.provider_id == canonical,
            LlmOAuthTokenEntity.oauth_mode == OAUTH_MODE_PLATFORM,
        )
    ).first()
    if entity and entity.status == LlmProviderStatus.INVALID.value:
        return LlmProviderStatus.NOT_CONFIGURED, "OAuth 连接已断开。"
    return status, message


def _persist_token(
    session: Session,
    provider_id: str,
    user_id: str,
    payload: dict[str, Any],
    *,
    existing: LlmOAuthTokenEntity | None = None,
) -> LlmOAuthTokenEntity:
    access_token = str(payload.get("access_token", "")).strip()
    if not access_token:
        raise ValueError("OAuth token 响应缺少 access_token。")

    refresh_token = str(payload.get("refresh_token", "")).strip()
    expires_in = int(payload.get("expires_in", 3600) or 3600)
    expires_at = _iso(_utc_now() + timedelta(seconds=max(expires_in - 30, 60)))
    scopes = str(payload.get("scope", "")).strip()

    entity = existing or session.exec(
        select(LlmOAuthTokenEntity).where(
            LlmOAuthTokenEntity.provider_id == provider_id,
            LlmOAuthTokenEntity.oauth_mode == OAUTH_MODE_PLATFORM,
        )
    ).first()
    if not entity:
        entity = LlmOAuthTokenEntity(
            id=f"oauth_{provider_id}_{uuid4().hex[:8]}",
            provider_id=provider_id,
            oauth_mode=OAUTH_MODE_PLATFORM,
            user_id=user_id,
        )

    entity.user_id = user_id
    entity.access_token = encrypt_api_key_if_needed(access_token)
    if refresh_token:
        entity.refresh_token = encrypt_api_key_if_needed(refresh_token)
    entity.expires_at = expires_at
    entity.scopes = scopes
    entity.status = LlmProviderStatus.AUTHORIZED.value
    entity.updated_at = _iso(_utc_now())
    session.add(entity)
    return entity


def _exchange_authorization_code(
    adapter: OAuthAdapter,
    *,
    code: str,
    code_verifier: str,
) -> dict[str, Any]:
    if oauth_mock_enabled(adapter) and code == "mock_authorization_code":
        return {
            "access_token": f"mock-access-{adapter.provider_id}",
            "refresh_token": f"mock-refresh-{adapter.provider_id}",
            "expires_in": 3600,
            "token_type": "bearer",
            "scope": adapter.scopes,
        }

    body = parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": adapter.redirect_uri,
            "client_id": adapter.client_id,
            "client_secret": adapter.client_secret,
            "code_verifier": code_verifier,
        }
    ).encode("utf-8")
    return _post_token(adapter.token_url, body)


def _refresh_access_token(adapter: OAuthAdapter, refresh_token: str) -> dict[str, Any]:
    if oauth_mock_enabled(adapter) and refresh_token.startswith("mock-refresh-"):
        return {
            "access_token": f"mock-access-{adapter.provider_id}-refreshed",
            "refresh_token": refresh_token,
            "expires_in": 3600,
            "token_type": "bearer",
        }

    body = parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": adapter.client_id,
            "client_secret": adapter.client_secret,
        }
    ).encode("utf-8")
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
