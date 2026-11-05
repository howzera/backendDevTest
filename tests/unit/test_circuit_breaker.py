import pytest

from app.domain.exceptions import ProductNotFoundError, ProductUnavailableError
from app.infrastructure.product_client.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerProductRepository,
    CircuitState,
)
from tests.fakes import FakeClock, FakeProductRepository, product

THRESHOLD = 3
RESET = 10


def breaker(clock: FakeClock) -> CircuitBreaker:
    return CircuitBreaker(THRESHOLD, RESET, clock)


def test_opens_after_consecutive_failures():
    cb = breaker(FakeClock())
    for _ in range(THRESHOLD):
        assert cb.allow_request()
        cb.record_failure()

    assert cb.state is CircuitState.OPEN
    assert not cb.allow_request()


def test_success_resets_the_failure_count():
    cb = breaker(FakeClock())
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    cb.record_failure()

    assert cb.state is CircuitState.CLOSED


def test_allows_a_single_trial_call_after_reset_timeout():
    clock = FakeClock()
    cb = breaker(clock)
    for _ in range(THRESHOLD):
        cb.record_failure()

    clock.advance(RESET)

    assert cb.allow_request()
    assert cb.state is CircuitState.HALF_OPEN
    assert not cb.allow_request()  # only one trial at a time


def test_trial_success_closes_and_trial_failure_reopens():
    clock = FakeClock()
    cb = breaker(clock)
    for _ in range(THRESHOLD):
        cb.record_failure()
    clock.advance(RESET)
    cb.allow_request()
    cb.record_failure()
    assert cb.state is CircuitState.OPEN

    clock.advance(RESET)
    cb.allow_request()
    cb.record_success()
    assert cb.state is CircuitState.CLOSED


async def test_repository_fails_fast_when_circuit_is_open():
    inner = FakeProductRepository(failing={"6"})
    repository = CircuitBreakerProductRepository(inner, THRESHOLD, RESET, FakeClock())

    for _ in range(THRESHOLD + 2):
        with pytest.raises(ProductUnavailableError):
            await repository.get_product("6")

    assert inner.product_calls == ["6"] * THRESHOLD


async def test_one_broken_product_does_not_open_the_circuit_of_others():
    inner = FakeProductRepository(products={"1": product("1")}, failing={"6"})
    repository = CircuitBreakerProductRepository(inner, THRESHOLD, RESET, FakeClock())
    for _ in range(THRESHOLD):
        with pytest.raises(ProductUnavailableError):
            await repository.get_product("6")

    assert await repository.get_product("1") == product("1")


async def test_not_found_does_not_count_as_failure():
    inner = FakeProductRepository()
    repository = CircuitBreakerProductRepository(inner, THRESHOLD, RESET, FakeClock())

    for _ in range(THRESHOLD + 2):
        with pytest.raises(ProductNotFoundError):
            await repository.get_product("5")

    assert len(inner.product_calls) == THRESHOLD + 2
