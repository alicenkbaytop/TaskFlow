import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import OAuthState

OAUTH_STATE_TTL = timedelta(minutes=10)


def _is_expired(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value <= datetime.now(UTC)


def start_google_signin(db: Session) -> str:
    settings = get_settings()
    if not settings.supabase_google_signin_enabled:
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is not enabled in TaskFlow configuration.",
        )
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=503, detail="Supabase Auth is not configured.")

    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    challenge = challenge.decode("ascii").rstrip("=")
    redirect_uri = settings.google_signin_redirect_uri
    separator = "&" if "?" in redirect_uri else "?"
    redirect_uri = f"{redirect_uri}{separator}{urlencode({'auth_state': state})}"

    db.add(
        OAuthState(
            id=state,
            code_verifier=verifier,
            expires_at=datetime.now(UTC) + OAUTH_STATE_TTL,
        )
    )
    db.commit()

    query = urlencode(
        {
            "provider": "google",
            "redirect_to": redirect_uri,
            "code_challenge": challenge,
            "code_challenge_method": "s256",
        }
    )
    return f"{settings.supabase_url.rstrip('/')}/auth/v1/authorize?{query}"


def exchange_google_signin_code(db: Session, state: str, code: str) -> dict:
    settings = get_settings()
    row = db.get(OAuthState, state)
    if row is None or _is_expired(row.expires_at) or not row.code_verifier:
        raise HTTPException(
            status_code=400, detail="Google sign-in state is invalid or expired."
        )

    verifier = row.code_verifier
    db.delete(row)
    db.commit()

    try:
        response = httpx.post(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=pkce",
            headers={
                "apikey": settings.supabase_anon_key,
                "Content-Type": "application/json",
            },
            json={"auth_code": code, "code_verifier": verifier},
            timeout=10,
        )
        response.raise_for_status()
        token_data = response.json()
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=401, detail="Supabase could not complete Google sign-in."
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=503, detail="Supabase Auth could not be reached."
        ) from error

    if not token_data.get("access_token"):
        raise HTTPException(
            status_code=401, detail="Supabase returned no access token."
        )
    return token_data
