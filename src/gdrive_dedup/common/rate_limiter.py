"""Token bucket rate limiter."""

import time
from threading import Lock
from typing import Optional


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate: float, capacity: Optional[float] = None) -> None:
        """Initialize rate limiter.

        Args:
            rate: Tokens added per second (requests/second)
            capacity: Bucket capacity (defaults to rate)
        """
        self.rate = rate
        self.capacity = capacity or rate
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self.lock = Lock()

    def acquire(self, tokens: int = 1, blocking: bool = True) -> bool:
        """Acquire tokens, optionally blocking until available.

        Args:
            tokens: Number of tokens to acquire
            blocking: If True, wait for tokens; if False, return immediately

        Returns:
            True if tokens acquired, False if not available and non-blocking
        """
        with self.lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True

                if not blocking:
                    return False

                sleep_time = (tokens - self.tokens) / self.rate
                time.sleep(sleep_time)
