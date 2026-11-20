from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.database import get_db
from app.services.supabase_oauth_service import (
    exchange_google_signin_code,
    start_google_signin,
)

router = APIRouter()


class ExchangeCode(BaseModel):
    state: str = Field(min_length=20, max_length=64)
    code: str = Field(min_length=1, max_length=4096)


@router.post("/google/start")
@limiter.limit("10/minute")
def google_signin_start(request: Request, db: Session = Depends(get_db)):
    return {"url": start_google_signin(db)}


@router.post("/google/exchange")
@limiter.limit("10/minute")
def google_signin_exchange(
    payload: ExchangeCode, request: Request, db: Session = Depends(get_db)
):
    return exchange_google_signin_code(db, payload.state, payload.code)
