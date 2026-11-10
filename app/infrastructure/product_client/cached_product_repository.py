import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.domain.exceptions import ProductNotFoundError
from app.domain.models import ProductDetail
from app.domain.ports import ProductRepository

Clock = Callable[[], float]


@dataclass
class _Entry:
    task: asyncio.Task
    expires_at: float | None = None  # None while the upstream call is still in flight

    def is_valid(self, now: float) -> bool:
        return self.expires_at is None or now < self.expires_at


class CachedProductRepository:
    """ProductRepository decorator: in-memory TTL cache with single-flight.

    Concurrent requests for the same key share one upstream call. The call is shielded,
    so a caller that times out does not cancel it and its result is still cached.
    Successes and "not found" are cached; failures are not.
    """

    def __init__(
        self,
        inner: ProductRepository,
        ttl_seconds: float,
        not_found_ttl_seconds: float,
        clock: Clock = time.monotonic,
    ) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._not_found_ttl = not_found_ttl_seconds
        self._clock = clock
        self._entries: dict[str, _Entry] = {}

    async def get_similar_ids(self, product_id: str) -> list[str]:
        return await self._get_or_load(f"similar-ids:{product_id}", lambda: self._inner.get_similar_ids(product_id))

    async def get_product(self, product_id: str) -> ProductDetail:
        return await self._get_or_load(f"product:{product_id}", lambda: self._inner.get_product(product_id))

    async def _get_or_load(self, key: str, load: Callable[[], Awaitable[Any]]) -> Any:
        entry = self._entries.get(key)
        if entry is None or not entry.is_valid(self._clock()):
            task = asyncio.ensure_future(load())
            entry = _Entry(task)
            self._entries[key] = entry
            task.add_done_callback(lambda done: self._on_loaded(key, done))
        # shield: cancelling one waiting caller (timeout) must not cancel the shared call.
        return await asyncio.shield(entry.task)

    def _on_loaded(self, key: str, task: asyncio.Task) -> None:
        entry = self._entries.get(key)
        if entry is None or entry.task is not task:
            return
        error = None if task.cancelled() else task.exception()  # reading it marks it as retrieved
        if task.cancelled() or (error is not None and not isinstance(error, ProductNotFoundError)):
            del self._entries[key]
            return
        ttl = self._not_found_ttl if isinstance(error, ProductNotFoundError) else self._ttl
        entry.expires_at = self._clock() + ttl
