import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TypeVar

from app.domain.exceptions import ProductNotFoundError, ProductUnavailableError
from app.domain.models import ProductDetail
from app.domain.ports import ProductRepository

Clock = Callable[[], float]
T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"  # calls pass through
    OPEN = "open"  # calls fail fast, the upstream is left alone
    HALF_OPEN = "half_open"  # one trial call decides whether to close again


class CircuitBreaker:
    """Classic three-state circuit breaker.

    After `failure_threshold` consecutive failures it opens and rejects calls for
    `reset_timeout_seconds`. Then it lets ONE trial call through: success closes it,
    failure opens it again.
    """

    def __init__(self, failure_threshold: int, reset_timeout_seconds: float, clock: Clock = time.monotonic) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout_seconds
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0

    @property
    def state(self) -> CircuitState:
        return self._state

    def allow_request(self) -> bool:
        if self._state is CircuitState.CLOSED:
            return True
        if self._state is CircuitState.OPEN and self._clock() - self._opened_at >= self._reset_timeout:
            self._state = CircuitState.HALF_OPEN
            return True  # the single trial call
        return False

    def record_success(self) -> None:
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._state is CircuitState.HALF_OPEN or self._consecutive_failures >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = self._clock()


class CircuitBreakerProductRepository:
    """ProductRepository decorator with one circuit breaker per upstream resource.

    Per resource (e.g. "product:6") and not global: one broken product must not cut off
    the healthy ones. "Not found" is a valid answer, so it counts as a success.
    """

    def __init__(
        self,
        inner: ProductRepository,
        failure_threshold: int,
        reset_timeout_seconds: float,
        clock: Clock = time.monotonic,
    ) -> None:
        self._inner = inner
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout_seconds
        self._clock = clock
        self._breakers: dict[str, CircuitBreaker] = {}

    async def get_similar_ids(self, product_id: str) -> list[str]:
        breaker = self._breaker(f"similar-ids:{product_id}", product_id)
        return await self._call(breaker, self._inner.get_similar_ids(product_id))

    async def get_product(self, product_id: str) -> ProductDetail:
        breaker = self._breaker(f"product:{product_id}", product_id)
        return await self._call(breaker, self._inner.get_product(product_id))

    def _breaker(self, key: str, product_id: str) -> CircuitBreaker:
        breaker = self._breakers.get(key)
        if breaker is None:
            breaker = CircuitBreaker(self._failure_threshold, self._reset_timeout, self._clock)
            self._breakers[key] = breaker
        if not breaker.allow_request():
            raise ProductUnavailableError(product_id, "circuit open")
        return breaker

    @staticmethod
    async def _call(breaker: CircuitBreaker, call: Awaitable[T]) -> T:
        try:
            result = await call
        except ProductNotFoundError:
            breaker.record_success()
            raise
        except (ProductUnavailableError, asyncio.CancelledError):
            # A cancelled trial call must not leave the breaker stuck in HALF_OPEN.
            breaker.record_failure()
            raise
        breaker.record_success()
        return result
