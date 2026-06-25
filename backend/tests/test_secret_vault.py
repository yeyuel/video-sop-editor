from __future__ import annotations

from sqlmodel import Session, select

from app.models.entities import LlmProviderConfigEntity
from app.services.secret_vault import decrypt_secret, encrypt_secret, is_encrypted


def test_encrypt_secret_roundtrip() -> None:
    plaintext = "sk-test-key-12345"
    encrypted = encrypt_secret(plaintext)

    assert is_encrypted(encrypted)
    assert decrypt_secret(encrypted) == plaintext


def test_decrypt_secret_supports_legacy_plaintext() -> None:
    assert decrypt_secret("plain-key") == "plain-key"


def test_encrypt_secret_idempotent() -> None:
    encrypted = encrypt_secret("secret")
    assert encrypt_secret(encrypted) == encrypted


def test_llm_config_save_encrypts_api_key(regression_env: dict) -> None:
    client = regression_env["client"]
    engine = regression_env["engine"]
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "director", "password": "root123"},
    )
    token = login.json()["data"]["sessionToken"]

    response = client.post(
        "/api/v1/llm/providers/kimi/config",
        json={
            "authType": "api_key",
            "baseUrl": "https://api.moonshot.cn/v1",
            "model": "moonshot-v1-8k",
            "apiKey": "test-kimi-key",
        },
        headers={"X-Session-Token": token},
    )
    assert response.status_code == 200

    with Session(engine) as session:
        stored = session.exec(
            select(LlmProviderConfigEntity).where(
                LlmProviderConfigEntity.provider_id == "kimi"
            )
        ).first()
        assert stored is not None
        assert is_encrypted(stored.api_key)
        assert decrypt_secret(stored.api_key) == "test-kimi-key"
