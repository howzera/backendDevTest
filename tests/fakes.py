import asyncio

from app.domain.exceptions import ProductNotFoundError, ProductUnavailableError
from app.domain.models import ProductDetail


def product(product_id: str) -> ProductDetail:
    return ProductDetail(id=product_id, name=f"Product {product_id}", price=10.0, availability=True)


class FakeClock:
    """Controllable time source for TTL and circuit breaker tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeProductRepository:
    """In-memory ProductRepository that can simulate missing, failing and slow products."""

    def __init__(
        self,
        similar_ids: dict[str, list[str]] | None = None,
        products: dict[str, ProductDetail] | None = None,
        failing: set[str] | None = None,
        delays: dict[str, float] | None = None,
    ) -> None:
        self.similar_ids = similar_ids or {}
        self.products = products or {}
        self.failing = failing or set()
        self.delays = delays or {}
        self.product_calls: list[str] = []
        self.similar_calls: list[str] = []

    async def get_similar_ids(self, product_id: str) -> list[str]:
        self.similar_calls.append(product_id)
        if product_id not in self.similar_ids:
            raise ProductNotFoundError(product_id)
        return self.similar_ids[product_id]

    async def get_product(self, product_id: str) -> ProductDetail:
        self.product_calls.append(product_id)
        await asyncio.sleep(self.delays.get(product_id, 0))
        if product_id in self.failing:
            raise ProductUnavailableError(product_id, "simulated failure")
        if product_id not in self.products:
            raise ProductNotFoundError(product_id)
        return self.products[product_id]
