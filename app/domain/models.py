from dataclasses import dataclass


@dataclass(frozen=True)
class ProductDetail:
    """A product as the business understands it. Immutable: a value, not a mutable record."""

    id: str
    name: str
    price: float
    availability: bool
