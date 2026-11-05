from typing import Protocol

from app.domain.models import ProductDetail


class ProductRepository(Protocol):
    """Output port: what the domain needs from the outside world to get products.

    Implementations must raise ProductNotFoundError when the product does not exist
    and ProductUnavailableError when the source fails.
    """

    async def get_similar_ids(self, product_id: str) -> list[str]:
        """Ids of the products similar to `product_id`, ordered by similarity."""
        ...

    async def get_product(self, product_id: str) -> ProductDetail:
        """Detail of a single product."""
        ...
