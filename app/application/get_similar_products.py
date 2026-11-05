import asyncio
import logging

from app.domain.exceptions import ProductNotFoundError, ProductUnavailableError
from app.domain.models import ProductDetail
from app.domain.ports import ProductRepository

logger = logging.getLogger(__name__)


class GetSimilarProducts:
    """Use case: detail of the products similar to a given one, ordered by similarity.

    Business rules:
    - If the product does not exist, ProductNotFoundError propagates (the API answers 404).
    - Details are fetched concurrently; the similarity order is preserved.
    - A similar product that fails, does not exist or is slower than `detail_timeout`
      is left out (partial response): a missing recommendation is better than no page.
    """

    def __init__(self, repository: ProductRepository, detail_timeout_seconds: float) -> None:
        self._repository = repository
        self._detail_timeout = detail_timeout_seconds

    async def execute(self, product_id: str) -> list[ProductDetail]:
        similar_ids = await self._repository.get_similar_ids(product_id)
        details = await asyncio.gather(*(self._fetch_detail(similar_id) for similar_id in similar_ids))
        return [detail for detail in details if detail is not None]

    async def _fetch_detail(self, product_id: str) -> ProductDetail | None:
        try:
            return await asyncio.wait_for(self._repository.get_product(product_id), self._detail_timeout)
        except ProductNotFoundError:
            logger.debug("Similar product %s not found, skipped", product_id)
        except ProductUnavailableError as error:
            logger.debug("Similar product %s unavailable (%s), skipped", product_id, error.reason)
        except TimeoutError:
            logger.debug("Similar product %s exceeded %.2fs, skipped", product_id, self._detail_timeout)
        return None
