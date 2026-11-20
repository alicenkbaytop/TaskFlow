from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import auth


def test_validated_supabase_identity_is_returned(monkeypatch):
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(
            supabase_url="https://project.supabase.co", supabase_anon_key="public-key"
        ),
    )
    seen = {}

    def fake_get(url, headers, timeout):
        seen.update(url=url, headers=headers, timeout=timeout)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"id": "verified-user", "email": "person@example.com"},
        )

    monkeypatch.setattr(auth.httpx, "get", fake_get)
    identity = auth.get_current_user(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="access-token")
    )
    assert identity["id"] == "verified-user"
    assert seen["headers"]["Authorization"] == "Bearer access-token"
    assert seen["headers"]["apikey"] == "public-key"


def test_rejected_supabase_token_returns_401(monkeypatch):
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(
            supabase_url="https://project.supabase.co", supabase_anon_key="public-key"
        ),
    )

    def reject(*args, **kwargs):
        request = httpx.Request("GET", "https://project.supabase.co/auth/v1/user")
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    monkeypatch.setattr(auth.httpx, "get", reject)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(credentials)
    assert exc.value.status_code == 401
