"""Exponential backoff retry decorator."""

import functools
import time
from typing import Any, Callable, TypeVar, cast

from googleapiclient.errors import HttpError

from .exceptions import RateLimitError
from .logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def exponential_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry with exponential backoff for transient errors.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = base_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except HttpError as e:
                    last_exception = e

                    # Don't retry client errors (except 429 rate limit)
                    if e.resp.status < 500 and e.resp.status != 429:
                        raise

                    if attempt == max_retries:
                        if e.resp.status == 429:
                            raise RateLimitError("Rate limit exceeded") from e
                        raise

                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)
                except Exception as e:
                    # Don't retry other exceptions
                    raise

            # Should never reach here, but mypy needs it
            raise last_exception or Exception("Unexpected retry loop exit")

        return wrapper
    return decorator
