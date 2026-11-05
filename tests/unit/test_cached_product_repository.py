import asyncio

import pytest

from app.domain.exceptions import ProductNotFoundError, ProductUnavailableError
from app.infrastructure.product_client.cached_product_repository import CachedProductRepository
from tests.fakes import FakeClock, FakeProductRepository, product

TTL = 300
NOT_FOUND_TTL = 60


def cached(inner: FakeProductRepository, clock: FakeClock | None = None) -> CachedProductRepository:
    return CachedProductRepository(inner, TTL, NOT_FOUND_TTL, clock=clock or FakeClock())


async def test_second_call_is_served_from_cache():
    inner = FakeProductRepository(products={"1": product("1")})
    repository = cached(inner)

    await repository.get_product("1")
    await repository.get_product("1")

    assert inner.product_calls == ["1"]


async def test_similar_ids_are_cached_too():
    inner = FakeProductRepository(similar_ids={"1": ["2"]})
    repository = cached(inner)

    assert await repository.get_similar_ids("1") == ["2"]
    assert await repository.get_similar_ids("1") == ["2"]
    assert inner.similar_calls == ["1"]


async def test_concurrent_calls_share_one_upstream_call():
    inner = FakeProductRepository(products={"1": product("1")}, delays={"1": 0.05})
    repository = cached(inner)

    results = await asyncio.gather(*(repository.get_product("1") for _ in range(200)))

    assert len(results) == 200
    assert inner.product_calls == ["1"]


async def test_entry_expires_after_ttl():
    clock = FakeClock()
    inner = FakeProductRepository(products={"1": product("1")})
    repository = cached(inner, clock)

    await repository.get_product("1")
    clock.advance(TTL + 1)
    await repository.get_product("1")

    assert inner.product_calls == ["1", "1"]


async def test_not_found_is_cached_with_its_own_ttl():
    clock = FakeClock()
    inner = FakeProductRepository()
    repository = cached(inner, clock)

    for _ in range(2):
        with pytest.raises(ProductNotFoundError):
            await repository.get_product("5")
    assert inner.product_calls == ["5"]

    clock.advance(NOT_FOUND_TTL + 1)
    with pytest.raises(ProductNotFoundError):
        await repository.get_product("5")
    assert inner.product_calls == ["5", "5"]


async def test_failures_are_not_cached():
    inner = FakeProductRepository(failing={"6"})
    repository = cached(inner)

    for _ in range(2):
        with pytest.raises(ProductUnavailableError):
            await repository.get_product("6")

    assert inner.product_calls == ["6", "6"]


async def test_slow_call_keeps_running_after_caller_timeout_and_is_cached():
    inner = FakeProductRepository(products={"100": product("100")}, delays={"100": 0.1})
    repository = cached(inner)

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(repository.get_product("100"), timeout=0.01)

    await asyncio.sleep(0.15)  # the shielded upstream call finishes in the background
    assert await asyncio.wait_for(repository.get_product("100"), timeout=0.01) == product("100")
    assert inner.product_calls == ["100"]
