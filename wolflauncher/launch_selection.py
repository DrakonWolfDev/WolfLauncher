from dataclasses import replace
from ipaddress import AddressValueError, IPv4Address

from .models import Server


def server_with_resolved_ipv4(server: Server, candidate: str) -> Server:
    """Use a status result only when it is a valid IPv4 launch target."""
    value = candidate.strip()
    try:
        resolved_ip = str(IPv4Address(value))
    except AddressValueError:
        return server
    return replace(server, host=resolved_ip)
