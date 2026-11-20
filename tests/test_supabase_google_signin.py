from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, OAuthState
from app.services import supabase_oauth_service as oauth


def test_supabase_google_signin_uses_pkce_and_one_time_state(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    settings = SimpleNamespace(
        supabase_google_signin_enabled=True,
        supabase_url="https://project.supabase.co",
        supabase_anon_key="public-key",
        google_signin_redirect_uri="http://localhost:8501",
    )
    monkeypatch.setattr(oauth, "get_settings", lambda: settings)
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"access_token": "access", "refresh_token": "refresh"}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(oauth.httpx, "post", post)
    with Session(engine) as db:
        url = oauth.start_google_signin(db)
        query = parse_qs(urlparse(url).query)
        assert query["provider"] == ["google"]
        assert query["code_challenge_method"] == ["s256"]
        state = parse_qs(urlparse(query["redirect_to"][0]).query)["auth_state"][0]
        row = db.get(OAuthState, state)
        assert row.expires_at is not None

        session = oauth.exchange_google_signin_code(db, state, "auth-code")
        assert session["access_token"] == "access"
        assert captured["url"].endswith("/auth/v1/token?grant_type=pkce")
        assert captured["json"]["code_verifier"] == row.code_verifier
        assert db.get(OAuthState, state) is None


def test_supabase_google_signin_rejects_unknown_state(monkeypatch):
    from fastapi import HTTPException

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(oauth, "get_settings", lambda: SimpleNamespace())
    with Session(engine) as db:
        try:
            oauth.exchange_google_signin_code(db, "unknown-state", "code")
        except HTTPException as error:
            assert error.status_code == 400
        else:
            raise AssertionError("Unknown OAuth state should be rejected")
