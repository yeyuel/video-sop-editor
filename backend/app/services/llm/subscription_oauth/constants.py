from __future__ import annotations

CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_REDIRECT_URI = "http://localhost:1455/auth/callback"
CODEX_LOOPBACK_PORT = 1455
CODEX_SCOPES = (
    "openid profile email offline_access "
    "api.connectors.read api.connectors.invoke"
)
CODEX_ORIGINATOR = "video_sop_editor"
CODEX_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"

GEMINI_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GEMINI_TOKEN_URL = "https://oauth2.googleapis.com/token"
GEMINI_SCOPES = " ".join(
    [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]
)
GEMINI_CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com/v1internal"
GEMINI_GENAI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"
