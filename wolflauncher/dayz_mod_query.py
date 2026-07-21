"""Strict decoding for DayZ's binary A2S_RULES mod manifest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import a2s

MAX_BINARY_CHUNKS = 128
MAX_BINARY_BYTES = 1024 * 1024
MAX_DLC_ENTRIES = 16
MAX_MODS = 255
MAX_SIGNATURES = 255
MAX_WORKSHOP_ID_BYTES = 8
MAX_TRAILING_EXTENSION_BYTES = 2048


class DayzModQueryError(RuntimeError):
    """The server did not return a complete, supported DayZ mod manifest."""


@dataclass(frozen=True)
class DayzRequiredMod:
    workshop_id: int
    name: str


class _Reader:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.offset = 0

    def read(self, length: int, label: str) -> bytes:
        end = self.offset + length
        if length < 0 or end > len(self.payload):
            raise DayzModQueryError(f"DayZ mod manifest ended while reading {label}")
        value = self.payload[self.offset : end]
        self.offset = end
        return value

    def uint8(self, label: str) -> int:
        return self.read(1, label)[0]

    def uint16(self, label: str) -> int:
        return int.from_bytes(self.read(2, label), "little")

    def uint32(self, label: str) -> int:
        return int.from_bytes(self.read(4, label), "little")


def _unstuff(payload: bytes) -> bytes:
    result = bytearray()
    index = 0
    replacements = {1: 1, 2: 0, 3: 255}
    while index < len(payload):
        value = payload[index]
        index += 1
        if value != 1:
            result.append(value)
            continue
        if index >= len(payload) or payload[index] not in replacements:
            raise DayzModQueryError("DayZ mod manifest contains invalid byte stuffing")
        result.append(replacements[payload[index]])
        index += 1
    return bytes(result)


def decode_dayz_mod_rules(rules: Mapping[bytes, bytes]) -> list[DayzRequiredMod]:
    """Decode a complete DayZ binary rules manifest or reject it atomically."""
    chunks: list[tuple[int, bytes]] = []
    for key, value in rules.items():
        if isinstance(key, bytes) and len(key) == 2:
            if not isinstance(value, bytes):
                raise DayzModQueryError("DayZ mod manifest contains a non-binary chunk")
            chunks.append((int.from_bytes(key, "little"), value))
    if not chunks:
        raise DayzModQueryError("server returned no DayZ mod manifest")
    if len(chunks) > MAX_BINARY_CHUNKS:
        raise DayzModQueryError("DayZ mod manifest contains too many chunks")

    chunks.sort(key=lambda item: item[0])
    if len({key for key, _ in chunks}) != len(chunks):
        raise DayzModQueryError("DayZ mod manifest contains duplicate chunks")
    raw = b"".join(value for _, value in chunks)
    if len(raw) > MAX_BINARY_BYTES:
        raise DayzModQueryError("DayZ mod manifest is too large")

    reader = _Reader(_unstuff(raw))
    protocol_version = reader.uint8("protocol version")
    if protocol_version != 2:
        raise DayzModQueryError(f"unsupported DayZ mod protocol version: {protocol_version}")
    overflow_flags = reader.uint8("overflow flags")
    if overflow_flags:
        raise DayzModQueryError("server reported an incomplete DayZ mod manifest")

    dlc_flags = reader.uint16("DLC flags")
    dlc_count = dlc_flags.bit_count()
    if dlc_count > MAX_DLC_ENTRIES:
        raise DayzModQueryError("DayZ mod manifest contains too many DLC entries")
    for index in range(dlc_count):
        reader.uint32(f"DLC hash {index + 1}")

    mod_count = reader.uint8("mod count")
    if mod_count > MAX_MODS:
        raise DayzModQueryError("DayZ mod manifest contains too many mods")
    mods: list[DayzRequiredMod] = []
    seen: set[int] = set()
    for index in range(mod_count):
        reader.uint32(f"mod hash {index + 1}")
        encoded_id_length = reader.uint8(f"Workshop ID length {index + 1}")
        id_length = encoded_id_length & 0x0F
        if not 1 <= id_length <= MAX_WORKSHOP_ID_BYTES:
            raise DayzModQueryError("DayZ mod manifest contains an invalid Workshop ID length")
        workshop_id = int.from_bytes(
            reader.read(id_length, f"Workshop ID {index + 1}"), "little"
        )
        if workshop_id == 0 or workshop_id in seen:
            raise DayzModQueryError("DayZ mod manifest contains an invalid or duplicate Workshop ID")
        seen.add(workshop_id)
        name_length = reader.uint8(f"mod name length {index + 1}")
        name = reader.read(name_length, f"mod name {index + 1}").decode(
            "utf-8", errors="replace"
        )
        mods.append(DayzRequiredMod(workshop_id, name))

    signature_count = reader.uint8("signature count")
    if signature_count > MAX_SIGNATURES:
        raise DayzModQueryError("DayZ mod manifest contains too many signatures")
    for index in range(signature_count):
        length = reader.uint8(f"signature length {index + 1}")
        reader.read(length, f"signature {index + 1}")
    trailer = reader.payload[reader.offset :]
    if len(trailer) > MAX_TRAILING_EXTENSION_BYTES:
        raise DayzModQueryError("DayZ mod manifest extension is too large")
    return mods


def query_dayz_required_mods(
    address: str,
    query_port: int,
    *,
    timeout: float = 10.0,
) -> list[DayzRequiredMod]:
    """Query the game server directly; no directory or launcher API is involved."""
    try:
        rules = a2s.rules((address, query_port), timeout=timeout, encoding=None)
    except Exception as exc:
        raise DayzModQueryError(f"direct server mod query failed: {exc}") from exc
    try:
        return decode_dayz_mod_rules(rules)
    except DayzModQueryError:
        raise
    except Exception as exc:
        raise DayzModQueryError(f"could not decode the server's DayZ mod manifest: {exc}") from exc
