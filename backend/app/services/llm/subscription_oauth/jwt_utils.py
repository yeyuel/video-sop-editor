from __future__ import annotations

import base64
import json
from typing import Any


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        parsed = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def extract_chatgpt_account_id(*tokens: str) -> str:
    for token in tokens:
        if not token.strip():
            continue
        payload = _decode_jwt_payload(token.strip())
        if not payload:
            continue
        direct = payload.get("chatgpt_account_id")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        auth_claim = payload.get("https://api.openai.com/auth")
        if isinstance(auth_claim, dict):
            nested = auth_claim.get("chatgpt_account_id")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
        organizations = payload.get("organizations")
        if isinstance(organizations, list) and organizations:
            first = organizations[0]
            if isinstance(first, dict):
                org_id = first.get("id")
                if isinstance(org_id, str) and org_id.strip():
                    return org_id.strip()
    return ""
