import httpx
import pytest
from fastapi import FastAPI

from app.application.get_similar_products import GetSimilarProducts
from app.domain.exceptions import ProductUnavailableError
from app.infrastructure.http_api.product_router import register_exception_handlers, router
from tests.fakes import FakeProductRepository, product


def build_app(repository) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    app.state.get_similar_products = GetSimilarProducts(repository, detail_timeout_seconds=0.2)
    return app


async def call(app: FastAPI, path: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


@pytest.fixture
def repository() -> FakeProductRepository:
    return FakeProductRepository(
        similar_ids={"1": ["2", "3"], "4": ["1", "5"]},
        products={"1": product("1"), "2": product("2"), "3": product("3")},
    )


async def test_returns_contract_shape(repository):
    response = await call(build_app(repository), "/product/1/similar")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "2", "name": "Product 2", "price": 10.0, "availability": True},
        {"id": "3", "name": "Product 3", "price": 10.0, "availability": True},
    ]


async def test_returns_partial_list_when_a_similar_product_is_missing(repository):
    response = await call(build_app(repository), "/product/4/similar")

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == ["1"]


async def test_returns_404_when_product_does_not_exist(repository):
    response = await call(build_app(repository), "/product/999/similar")

    assert response.status_code == 404
    assert response.json() == {"detail": "Product '999' not found"}


async def test_returns_503_when_similar_ids_source_is_unavailable():
    class Down(FakeProductRepository):
        async def get_similar_ids(self, product_id):
            raise ProductUnavailableError(product_id, "down")

    response = await call(build_app(Down()), "/product/1/similar")

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
