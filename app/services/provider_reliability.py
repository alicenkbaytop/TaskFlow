import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def is_retryable_provider_error(error: Exception) -> bool:
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    if status in RETRYABLE_STATUS_CODES:
        return True
    error_name = type(error).__name__.lower()
    return "timeout" in error_name or "connection" in error_name


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
