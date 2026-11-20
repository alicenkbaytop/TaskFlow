import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    settings = get_settings()
    if not credentials or not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        response = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.supabase_anon_key,
                "Authorization": f"Bearer {credentials.credentials}",
            },
            timeout=5,
        )
        response.raise_for_status()
        user = response.json()
        if not isinstance(user.get("id"), str):
            raise ValueError("Missing user ID")
        return user
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
