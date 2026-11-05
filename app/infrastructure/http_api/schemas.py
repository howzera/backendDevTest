from pydantic import BaseModel

from app.domain.models import ProductDetail


class ProductDetailResponse(BaseModel):
    """ProductDetail as defined in similarProducts.yaml. HTTP shape, separate from the domain model."""

    id: str
    name: str
    price: float
    availability: bool

    @classmethod
    def from_domain(cls, product: ProductDetail) -> "ProductDetailResponse":
        return cls(id=product.id, name=product.name, price=product.price, availability=product.availability)


class ErrorResponse(BaseModel):
    detail: str
