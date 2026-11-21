import random
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
_failures: dict[str, deque[float]] = defaultdict(deque)
_cooldown_until: dict[str, float] = {}

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def is_retryable_provider_error(error: Exception) -> bool:
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    if status in RETRYABLE_STATUS_CODES:
        return True
    error_name = type(error).__name__.lower()
    return "timeout" in error_name or "connection" in error_name


def is_fallback_eligible(error: Exception) -> bool:
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    return is_retryable_provider_error(error) or status in {400, 401, 403, 404, 422}


def provider_available(provider: str, *, now: float | None = None) -> bool:
    return _cooldown_until.get(provider, 0) <= (
        time.monotonic() if now is None else now
    )


def record_provider_result(provider: str, success: bool) -> None:
    from app.core.config import get_settings

    now = time.monotonic()
    failures = _failures[provider]
    if success:
        failures.clear()
        _cooldown_until.pop(provider, None)
        return
    failures.append(now)
    threshold = max(1, get_settings().ai_failure_threshold)
    while failures and failures[0] < now - 300:
        failures.popleft()
    if len(failures) >= threshold:
        _cooldown_until[provider] = now + max(1, get_settings().ai_cooldown_seconds)


def reset_provider_state() -> None:
    _failures.clear()
    _cooldown_until.clear()


def with_retries(
    operation: Callable[[], T],
    *,
    attempts: int,
    base_delay_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> tuple[T, int]:
    attempts = max(1, attempts)
    for attempt in range(attempts):
        try:
            return operation(), attempt + 1
        except Exception as error:
            if attempt + 1 >= attempts or not is_retryable_provider_error(error):
                raise
            delay = min(base_delay_seconds * (2**attempt), 2.0)
            sleep(delay * (0.75 + 0.5 * random_value()))
    raise RuntimeError("Provider operation ended without a result")
