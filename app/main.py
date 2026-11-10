import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.application.get_similar_products import GetSimilarProducts
from app.config import Settings
from app.infrastructure.http_api.product_router import register_exception_handlers, router
from app.infrastructure.product_client.cached_product_repository import CachedProductRepository
from app.infrastructure.product_client.circuit_breaker import CircuitBreakerProductRepository
from app.infrastructure.product_client.http_product_repository import HttpProductRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Composition root: the only place that knows every concrete adapter."""
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One shared client: a single connection pool for every request.
        async with httpx.AsyncClient(
            base_url=settings.products_api_base_url,
            timeout=settings.upstream_timeout_seconds,
            limits=httpx.Limits(
                max_connections=settings.upstream_max_connections,
                max_keepalive_connections=settings.upstream_max_connections,
            ),
        ) as client:
            # Decorators around the same port: cache -> circuit breaker -> HTTP.
            repository = CachedProductRepository(
                CircuitBreakerProductRepository(
                    HttpProductRepository(client),
                    failure_threshold=settings.circuit_failure_threshold,
                    reset_timeout_seconds=settings.circuit_reset_timeout_seconds,
                ),
                ttl_seconds=settings.cache_ttl_seconds,
                not_found_ttl_seconds=settings.cache_not_found_ttl_seconds,
            )
            app.state.get_similar_products = GetSimilarProducts(repository, settings.detail_timeout_seconds)
            yield

    app = FastAPI(title="Similar Products API", version="1.0.0", lifespan=lifespan)
    app.include_router(router)
    register_exception_handlers(app)
    return app


app = create_app()
