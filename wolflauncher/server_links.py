"""Versioned server links carry endpoint data, never launch arguments or secrets."""

import re
from dataclasses import dataclass
from ipaddress import IPv4Address
from urllib.parse import parse_qsl, urlencode, urlsplit

MAX_SERVER_LINK_BYTES = 2048
JOIN_ORIGIN = "https://wolf-forge.co.uk/join/"
REQUIRED_FIELDS = {"v", "host", "game_port", "query_port"}
OPTIONAL_FIELDS = {"server_id", "product"}


class ServerLinkError(ValueError):
    pass


@dataclass(frozen=True)
class ServerLinkTarget:
    host: str
    game_port: int
    query_port: int
    server_id: str = ""
    product: str = "unknown"

    def query(self):
        fields = {
            "v": "1",
            "host": self.host,
            "game_port": str(self.game_port),
            "query_port": str(self.query_port),
        }
        if self.server_id:
            fields["server_id"] = self.server_id
        if self.product != "unknown":
            fields["product"] = self.product
        return urlencode(fields)

    def url(self, *, https=True):
        return (JOIN_ORIGIN if https else "wolflauncher://join") + "?" + self.query()


def _host(value):
    if not value or len(value) > 253:
        raise ServerLinkError("The link needs a valid IPv4 address or hostname.")
    try:
        return str(IPv4Address(value))
    except ValueError:
        pass
    if value.replace(".", "").isdigit() or not all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in value.split(".")
    ):
        raise ServerLinkError("The link needs a valid IPv4 address or hostname.")
    return value.lower()


def parse_server_link(value: str) -> ServerLinkTarget:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_SERVER_LINK_BYTES
        or any(not 33 <= ord(char) <= 126 for char in value)
        or "#" in value
        or re.search(r"%(?![0-9a-fA-F]{2})", value)
        or not value.startswith(("wolflauncher://join", "https://wolf-forge.co.uk/join"))
    ):
        raise ServerLinkError("This server link is malformed or too long.")
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme == "wolflauncher" and parsed.netloc == "join" and parsed.path in ("", "/")
        ) or (
            parsed.scheme == "https"
            and parsed.netloc == "wolf-forge.co.uk"
            and parsed.path in ("/join", "/join/")
        )
        if not valid:
            raise ServerLinkError("Use a WolfLauncher link or a wolf-forge.co.uk/join/ link.")
        pairs = parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
            encoding="ascii",
            errors="strict",
            max_num_fields=6,
        )
        fields = dict(pairs)
        if (
            len(fields) != len(pairs)
            or not REQUIRED_FIELDS <= fields.keys()
            or (fields.keys() - REQUIRED_FIELDS - OPTIONAL_FIELDS)
        ):
            raise ServerLinkError("The link has missing, repeated or unsupported fields.")
        if fields["v"] != "1":
            raise ServerLinkError(
                "This server-link version is not supported. Check for a launcher update."
            )
        ports = []
        for key in ("game_port", "query_port"):
            if not re.fullmatch(r"[0-9]{1,5}", fields[key]) or not 1 <= int(fields[key]) <= 65535:
                raise ServerLinkError("The link needs game and query ports from 1 to 65535.")
            ports.append(int(fields[key]))
        identity = fields.get("server_id", "")
        if "server_id" in fields and not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", identity
        ):
            raise ServerLinkError("The directory server reference is invalid.")
        product = fields.get("product", "unknown")
        if product not in {"stable", "experimental", "unknown"}:
            raise ServerLinkError("The link's DayZ edition hint is invalid.")
        return ServerLinkTarget(_host(fields["host"]), *ports, identity, product)
    except ServerLinkError:
        raise
    except (ValueError, UnicodeError):
        raise ServerLinkError("This server link is malformed.") from None


def build_server_link(server) -> str:
    target = ServerLinkTarget(
        server.host,
        server.game_port,
        server.query_port,
        getattr(server, "stable_server_id", ""),
        getattr(server, "product", "unknown"),
    )
    # Apply precisely the same schema to outbound and inbound links.
    return parse_server_link(target.url()).url()


def parse_startup_arguments(arguments):
    import argparse

    from . import __version__

    parser = argparse.ArgumentParser(
        description="WolfLauncher — browse and join DayZ servers.", allow_abbrev=False
    )
    parser.add_argument("url", nargs="?", help="A shared WolfLauncher server link")
    parser.add_argument("--open-url", dest="open_url", help="Open a shared server link for review")
    parser.add_argument("--version", action="version", version=f"WolfLauncher {__version__}")
    args = parser.parse_args(arguments)
    if args.url is not None and args.open_url is not None:
        parser.error("Supply one server link at a time.")
    return args.open_url if args.open_url is not None else args.url
