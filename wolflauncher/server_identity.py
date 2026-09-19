"""Pure Phase 0 identity contract; launch/UI integration follows in later phases.

Times are monotonic seconds from the current process. Never restore live evidence
from disk as launch authority. Endpoint is (resolved IP, game port, query port).
"""

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

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


def normalize_product(value: object) -> str:
    """Validate persisted/provider identity without the UI's Stable default."""
    return value if isinstance(value, str) and value in {"stable", "experimental"} else "unknown"


def identity_fields(value: object) -> dict:
    """Serializable historical evidence, never a restored LiveIdentity.

    Unknown metadata is retained for diagnostics. Legacy hints do not establish
    a product, and conflicting assertions remain visible until a live resolution.
    """
    from collections.abc import Mapping

    def read(key, default=None):
        return (
            value.get(key, default) if isinstance(value, Mapping) else getattr(value, key, default)
        )

    evidence = read("identity_evidence", ())
    if not isinstance(evidence, (tuple, list)):
        evidence = ()
    evidence = tuple(dict(item) for item in evidence if isinstance(item, dict))
    product = normalize_product(read("product"))
    state = read("identity_state", "")
    if state not in {"known", "unknown", "conflict"}:
        state = "known" if product != "unknown" else "unknown"
    if state != "conflict" and product == "unknown":
        state = "unknown"
    return {"product": product, "identity_state": state, "identity_evidence": evidence}


def provider_identity(product: object, source: str, observed_at: str = "") -> dict:
    key = normalize_product(product)
    if product is None:
        return identity_fields({})
    return identity_fields(
        {
            "product": key,
            "identity_evidence": (
                {
                    "product": product,
                    "source": source,
                    "observed_at": observed_at,
                    "verified": False,
                },
            ),
        }
    )


def merge_identity(previous: object, incoming: object) -> dict:
    """Merge history conservatively; status-only updates cannot erase identity."""
    old, new = identity_fields(previous), identity_fields(incoming)
    evidence = list(old["identity_evidence"])
    for item in new["identity_evidence"]:
        if item not in evidence:
            evidence.append(item)
    products = {p for p in (old["product"], new["product"]) if p != "unknown"}
    conflict = "conflict" in {old["identity_state"], new["identity_state"]} or len(products) > 1
    return {
        "product": old["product"] if conflict else next(iter(products), "unknown"),
        "identity_state": "conflict" if conflict else "known" if products else "unknown",
        "identity_evidence": tuple(evidence),
    }


class ServerEndpoint(Protocol):
    host: str
    game_port: int
    query_port: int


def endpoint_key(server: ServerEndpoint) -> str:
    return f"{server.host.strip().lower()}:{server.game_port}:{server.query_port}"


def identity_key(server: ServerEndpoint) -> str:
    product = normalize_product(getattr(server, "product", None))
    endpoint = endpoint_key(server)
    # Keep legacy unknown cache keys readable; concrete identities are scoped.
    return endpoint if product == "unknown" else f"{product}|{endpoint}"


def saved_server_fields(value: object) -> dict:
    """Identity and provider aliases carried by saved-server conversions."""
    from collections.abc import Mapping

    def read(key, default):
        return (
            value.get(key, default) if isinstance(value, Mapping) else getattr(value, key, default)
        )

    aliases = read("endpoint_aliases", ())
    return {
        **identity_fields(value),
        "stable_server_id": str(read("stable_server_id", "") or ""),
        "endpoint_aliases": tuple(a for a in aliases if isinstance(a, str))
        if isinstance(aliases, (list, tuple))
        else (),
    }


def saved_launch_error(server: object, selected_product: str) -> str:
    identity = identity_fields(server)
    if identity["identity_state"] == "conflict":
        return "Server edition evidence conflicts. Resolve the live server identity before joining."
    if identity["product"] == "unknown":
        return "Server edition is unresolved. Live identity resolution is required before joining; the saved profile is only a hint."
    if identity["product"] != normalize_product(selected_product):
        return "This server uses a different DayZ edition. Select its edition in Settings before joining."
    return ""


def saved_edition_label(server, availability=None) -> str:
    if server.identity_state == "conflict":
        return "Edition conflict"
    if server.product == "unknown":
        return "Version unverified"
    label = "EXPERIMENTAL" if server.product == "experimental" else ""
    state = (availability or {}).get(server.product)
    if state is not None and state.state in {"missing", "steam_missing", "incomplete"}:
        label = " · ".join(filter(None, (label, "Installation required")))
    return label
