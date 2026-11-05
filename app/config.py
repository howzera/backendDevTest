import os
from dataclasses import dataclass


def _float_env(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    """Runtime configuration, read from environment variables (12-factor style)."""

    products_api_base_url: str = "http://localhost:3001"
    # Max time a request waits for one similar product before leaving it out.
    detail_timeout_seconds: float = 1.5
    # Hard limit for any single upstream HTTP call.
    upstream_timeout_seconds: float = 10.0
    upstream_max_connections: int = 200
    cache_ttl_seconds: float = 300.0
    cache_not_found_ttl_seconds: float = 60.0
    circuit_failure_threshold: int = 5
    circuit_reset_timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            products_api_base_url=os.getenv("PRODUCTS_API_BASE_URL", cls.products_api_base_url),
            detail_timeout_seconds=_float_env("DETAIL_TIMEOUT_SECONDS", cls.detail_timeout_seconds),
            upstream_timeout_seconds=_float_env("UPSTREAM_TIMEOUT_SECONDS", cls.upstream_timeout_seconds),
            upstream_max_connections=_int_env("UPSTREAM_MAX_CONNECTIONS", cls.upstream_max_connections),
            cache_ttl_seconds=_float_env("CACHE_TTL_SECONDS", cls.cache_ttl_seconds),
            cache_not_found_ttl_seconds=_float_env("CACHE_NOT_FOUND_TTL_SECONDS", cls.cache_not_found_ttl_seconds),
            circuit_failure_threshold=_int_env("CIRCUIT_FAILURE_THRESHOLD", cls.circuit_failure_threshold),
            circuit_reset_timeout_seconds=_float_env("CIRCUIT_RESET_TIMEOUT_SECONDS", cls.circuit_reset_timeout_seconds),
        )
