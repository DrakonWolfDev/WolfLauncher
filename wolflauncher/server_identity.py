"""Pure Phase 0 identity contract; launch/UI integration follows in later phases.

Times are monotonic seconds from the current process. Never restore live evidence
from disk as launch authority. Endpoint is (resolved IP, game port, query port).
"""

from dataclasses import dataclass
from math import isfinite

from .dayz_product import EXPERIMENTAL, STABLE

IDENTITY_MAX_AGE_SECONDS = 30.0
Endpoint = tuple[str, int, int]


def product_from_app_id(value: object) -> str:
    """Accept the corrected numeric GameDig raw.appId, never names or versions."""
    if type(value) is not int:
        return "unknown"
    for product in (STABLE, EXPERIMENTAL):
        if value == product.client_app_id:
            return product.key
    return "unknown"


def directory_identity(rows: list[dict]) -> str:
    """Summarize already endpoint-matched directory evidence, not launch authority."""
    products: set[str] = set()
    for row in rows:
        value = row.get("product")
        if isinstance(value, str):
            products.add(value)
    if not rows or any(row.get("product") not in ("stable", "experimental") for row in rows):
        return "unknown"
    return next(iter(products)) if len(products) == 1 else "conflict"


@dataclass(frozen=True)
class LiveIdentity:
    endpoint: Endpoint
    request_id: str
    observed_at: float
    app_id: object
    complete: bool = True


def resolve_launch_identity(
    evidence: LiveIdentity | None,
    *,
    endpoint: Endpoint,
    request_id: str,
    now: float,
) -> str:
    """A fresh successful exact-context query may settle directory conflicts.

    Unknown means refresh/retry before mods or launching, never fall back to Stable.
    The caller must also invalidate evidence when a newer check fails or is cancelled.
    """
    if evidence is None or not evidence.complete:
        return "unknown"
    if evidence.endpoint != endpoint or evidence.request_id != request_id:
        return "unknown"
    age = now - evidence.observed_at
    if not isfinite(age) or not 0 <= age <= IDENTITY_MAX_AGE_SECONDS:
        return "unknown"
    return product_from_app_id(evidence.app_id)
