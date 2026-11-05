from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.application.get_similar_products import GetSimilarProducts
from app.domain.exceptions import ProductNotFoundError, ProductUnavailableError
from app.infrastructure.http_api.schemas import ErrorResponse, ProductDetailResponse

router = APIRouter()


def get_use_case(request: Request) -> GetSimilarProducts:
    return request.app.state.get_similar_products


@router.get(
    "/product/{product_id}/similar",
    response_model=list[ProductDetailResponse],
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Product Not found"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse, "description": "Product source unavailable"},
    },
)
async def get_similar_products(product_id: str, request: Request) -> list[ProductDetailResponse]:
    products = await get_use_case(request).execute(product_id)
    return [ProductDetailResponse.from_domain(product) for product in products]


def register_exception_handlers(app: FastAPI) -> None:
    """Translates domain errors into consistent HTTP error responses."""

    @app.exception_handler(ProductNotFoundError)
    async def handle_not_found(_: Request, error: ProductNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)})

    @app.exception_handler(ProductUnavailableError)
    async def handle_unavailable(_: Request, error: ProductUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": f"Similar products for '{error.product_id}' are temporarily unavailable"},
        )
