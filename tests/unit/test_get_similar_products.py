import time

import pytest

from app.application.get_similar_products import GetSimilarProducts
from app.domain.exceptions import ProductNotFoundError, ProductUnavailableError
from tests.fakes import FakeProductRepository, product

TIMEOUT = 0.2


def use_case(repository: FakeProductRepository) -> GetSimilarProducts:
    return GetSimilarProducts(repository, detail_timeout_seconds=TIMEOUT)


async def test_returns_similar_products_in_similarity_order():
    repository = FakeProductRepository(
        similar_ids={"1": ["3", "2", "4"]},
        products={"2": product("2"), "3": product("3"), "4": product("4")},
        # The first one is the slowest: order must not depend on arrival time.
        delays={"3": 0.05},
    )

    result = await use_case(repository).execute("1")

    assert [p.id for p in result] == ["3", "2", "4"]


async def test_returns_empty_list_when_product_has_no_similar_products():
    repository = FakeProductRepository(similar_ids={"1": []})

    assert await use_case(repository).execute("1") == []


async def test_raises_not_found_when_product_does_not_exist():
    repository = FakeProductRepository()

    with pytest.raises(ProductNotFoundError):
        await use_case(repository).execute("999")


async def test_raises_unavailable_when_similar_ids_source_fails():
    class FailingSimilarIds(FakeProductRepository):
        async def get_similar_ids(self, product_id):
            raise ProductUnavailableError(product_id, "down")

    with pytest.raises(ProductUnavailableError):
        await use_case(FailingSimilarIds()).execute("1")


async def test_skips_similar_product_that_does_not_exist():
    # k6 "notFound" scenario: product 4 -> [1, 2, 5] and 5 returns 404.
    repository = FakeProductRepository(
        similar_ids={"4": ["1", "2", "5"]},
        products={"1": product("1"), "2": product("2")},
    )

    result = await use_case(repository).execute("4")

    assert [p.id for p in result] == ["1", "2"]


async def test_skips_similar_product_whose_source_fails():
    # k6 "error" scenario: product 5 -> [1, 2, 6] and 6 returns 500.
    repository = FakeProductRepository(
        similar_ids={"5": ["1", "2", "6"]},
        products={"1": product("1"), "2": product("2"), "6": product("6")},
        failing={"6"},
    )

    result = await use_case(repository).execute("5")

    assert [p.id for p in result] == ["1", "2"]


async def test_skips_similar_product_slower_than_timeout():
    # k6 "slow"/"verySlow" scenarios: some similar products take seconds.
    repository = FakeProductRepository(
        similar_ids={"2": ["3", "100"]},
        products={"3": product("3"), "100": product("100")},
        delays={"100": 5},
    )

    started = time.perf_counter()
    result = await use_case(repository).execute("2")
    elapsed = time.perf_counter() - started

    assert [p.id for p in result] == ["3"]
    assert elapsed < TIMEOUT + 0.1


async def test_fetches_details_concurrently():
    repository = FakeProductRepository(
        similar_ids={"1": ["2", "3", "4"]},
        products={"2": product("2"), "3": product("3"), "4": product("4")},
        delays={"2": 0.1, "3": 0.1, "4": 0.1},
    )

    started = time.perf_counter()
    await use_case(repository).execute("1")
    elapsed = time.perf_counter() - started

    # Sequential would take ~0.3s; concurrent takes ~0.1s.
    assert elapsed < 0.2
