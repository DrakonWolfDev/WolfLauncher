"""DayZ product definitions used by detection, discovery and native launch.

Stable and Experimental are separate Steam applications.  Keeping their
identities together prevents an Experimental choice from silently reusing
Stable launch, server, or mod assumptions.
"""

from dataclasses import dataclass

STABLE_PRODUCT_KEY = "stable"
EXPERIMENTAL_PRODUCT_KEY = "experimental"


@dataclass(frozen=True)
class DayZProduct:
    key: str
    label: str
    client_app_id: int
    server_app_id: int
    experimental: bool = False


STABLE = DayZProduct(STABLE_PRODUCT_KEY, "DayZ Stable", 221100, 223350)
EXPERIMENTAL = DayZProduct(
    EXPERIMENTAL_PRODUCT_KEY,
    "DayZ Experimental",
    1024020,
    1042420,
    experimental=True,
)


def product_from_key(value: object) -> DayZProduct:
    return EXPERIMENTAL if str(value).strip().lower() == EXPERIMENTAL_PRODUCT_KEY else STABLE


def product_warning(product: DayZProduct) -> str:
    if not product.experimental:
        return ""
    return (
        "DayZ Experimental mode is active. Servers, favourites, mod sources, and launch "
        "history are separate from DayZ Stable. Experimental updates may be unstable, "
        "wipe progress, or require different mod versions."
    )
