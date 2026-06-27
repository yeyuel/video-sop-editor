from __future__ import annotations

from starlette.testclient import TestClient


class AuthTestClient:
    """TestClient wrapper that attaches the session token to every request."""

    def __init__(self, client: TestClient, token: str) -> None:
        self._client = client
        self._token = token

    @property
    def token(self) -> str:
        return self._token

    def _with_auth(self, kwargs: dict) -> dict:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("X-Session-Token", self._token)
        kwargs["headers"] = headers
        return kwargs

    def get(self, url: str, **kwargs):
        return self._client.get(url, **self._with_auth(kwargs))

    def post(self, url: str, **kwargs):
        return self._client.post(url, **self._with_auth(kwargs))

    def put(self, url: str, **kwargs):
        return self._client.put(url, **self._with_auth(kwargs))

    def patch(self, url: str, **kwargs):
        return self._client.patch(url, **self._with_auth(kwargs))

    def delete(self, url: str, **kwargs):
        return self._client.delete(url, **self._with_auth(kwargs))
