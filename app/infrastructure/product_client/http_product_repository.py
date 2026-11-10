import httpx

from app.domain.exceptions import ProductNotFoundError, ProductUnavailableError
from app.domain.models import ProductDetail


class HttpProductRepository:
    """ProductRepository adapter for the existing product APIs (see existingApis.yaml).

    404 -> ProductNotFoundError; any other error, timeout or unexpected body ->
    ProductUnavailableError. Only the status code is used: the upstream 404 body is
    sometimes plain text and the 500 body is empty.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get_similar_ids(self, product_id: str) -> list[str]:
        payload = await self._get_json(f"/product/{product_id}/similarids", product_id)
        if not isinstance(payload, list):
            raise ProductUnavailableError(product_id, "similar ids is not a list")
        # The upstream returns numbers ([2, 3, 4]) although the contract says strings.
        return [str(similar_id) for similar_id in payload]

    async def get_product(self, product_id: str) -> ProductDetail:
        payload = await self._get_json(f"/product/{product_id}", product_id)
        try:
            return ProductDetail(
                id=str(payload["id"]),
                name=str(payload["name"]),
                price=float(payload["price"]),
                availability=bool(payload["availability"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ProductUnavailableError(product_id, f"invalid product body: {error!r}") from error

    async def _get_json(self, path: str, product_id: str) -> object:
        try:
            response = await self._client.get(path)
        except httpx.TimeoutException as error:
            raise ProductUnavailableError(product_id, "timeout") from error
        except httpx.HTTPError as error:
            raise ProductUnavailableError(product_id, f"connection error: {error!r}") from error

        if response.status_code == httpx.codes.NOT_FOUND:
            raise ProductNotFoundError(product_id)
        if response.is_error:
            raise ProductUnavailableError(product_id, f"upstream status {response.status_code}")

        try:
            return response.json()
        except ValueError as error:
            raise ProductUnavailableError(product_id, "body is not valid JSON") from error
