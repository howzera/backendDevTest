class ProductNotFoundError(Exception):
    """The requested product does not exist. A valid business answer, not a failure."""

    def __init__(self, product_id: str) -> None:
        super().__init__(f"Product '{product_id}' not found")
        self.product_id = product_id


class ProductUnavailableError(Exception):
    """The product source failed (error, timeout, open circuit). The product may exist."""

    def __init__(self, product_id: str, reason: str) -> None:
        super().__init__(f"Product '{product_id}' unavailable: {reason}")
        self.product_id = product_id
        self.reason = reason
