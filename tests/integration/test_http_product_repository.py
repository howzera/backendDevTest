import httpx
import pytest

from app.domain.exceptions import ProductNotFoundError, ProductUnavailableError
from app.domain.models import ProductDetail
from app.infrastructure.product_client.http_product_repository import HttpProductRepository

# Upstream responses copied from shared/simulado/mocks.json and curl.
ROUTES = {
    "/product/1/similarids": httpx.Response(200, json=[2, 3, 4]),
    "/product/6/similarids": httpx.Response(404, text="Not Found"),
    "/product/1": httpx.Response(200, json={"id": "1", "name": "Shirt", "price": 9.99, "availability": True}),
    "/product/5": httpx.Response(404, json={"message": "Product not found"}),
    "/product/6": httpx.Response(500),
    "/product/7": httpx.Response(200, json={"id": "7", "name": "No price"}),
    "/product/8": httpx.Response(200, text="<html>oops</html>"),
}


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/product/9":
        raise httpx.ReadTimeout("slow upstream", request=request)
    if request.url.path == "/product/10":
        raise httpx.ConnectError("connection refused", request=request)
    return ROUTES[request.url.path]


@pytest.fixture
async def repository():
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://upstream") as client:
        yield HttpProductRepository(client)


async def test_similar_ids_are_converted_to_strings(repository):
    assert await repository.get_similar_ids("1") == ["2", "3", "4"]


async def test_similar_ids_plain_text_404_raises_not_found(repository):
    with pytest.raises(ProductNotFoundError):
        await repository.get_similar_ids("6")


async def test_product_is_mapped_to_domain(repository):
    assert await repository.get_product("1") == ProductDetail("1", "Shirt", 9.99, True)


async def test_product_404_raises_not_found(repository):
    with pytest.raises(ProductNotFoundError):
        await repository.get_product("5")


async def test_product_500_with_empty_body_raises_unavailable(repository):
    with pytest.raises(ProductUnavailableError, match="status 500"):
        await repository.get_product("6")


async def test_product_with_missing_fields_raises_unavailable(repository):
    with pytest.raises(ProductUnavailableError, match="invalid product body"):
        await repository.get_product("7")


async def test_product_with_non_json_body_raises_unavailable(repository):
    with pytest.raises(ProductUnavailableError, match="not valid JSON"):
        await repository.get_product("8")


async def test_timeout_raises_unavailable(repository):
    with pytest.raises(ProductUnavailableError, match="timeout"):
        await repository.get_product("9")


async def test_connection_error_raises_unavailable(repository):
    with pytest.raises(ProductUnavailableError, match="connection error"):
        await repository.get_product("10")
