import logging
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.chat import router as chat_router
from app.api.tasks import router as tasks_router
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.rate_limit import limiter
from app.core.telemetry import setup_tracing
from app.database import get_db

setup_logging()
# Configure OpenTelemetry
setup_tracing()

# Create FastAPI application
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in get_settings().cors_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Automatically trace incoming HTTP requests
FastAPIInstrumentor.instrument_app(app)
logger = logging.getLogger(__name__)


@app.middleware("http")
async def log_requests(request: Request, call_next):

    start_time = time.perf_counter()

    response = await call_next(request)

    duration = (time.perf_counter() - start_time) * 1000

    logger.info(
        "HTTP %s %s | Status: %s | Duration: %.2f ms",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    return response


app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}
