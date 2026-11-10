from dataclasses import dataclass


@dataclass(frozen=True)
class ProductDetail:
    """Product detail (immutable value object)."""

    id: str
    name: str
    price: float
    availability: bool
