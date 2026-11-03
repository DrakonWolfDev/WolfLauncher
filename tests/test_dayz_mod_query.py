import unittest
from unittest.mock import patch

from wolflauncher.dayz_mod_query import (
    DayzModQueryError,
    DayzRequiredMod,
    decode_dayz_mod_rules,
    query_dayz_required_mods,
)


def _stuff(payload: bytes) -> bytes:
    result = bytearray()
    for value in payload:
        if value == 0:
            result.extend((1, 2))
        elif value == 255:
            result.extend((1, 3))
        elif value == 1:
            result.extend((1, 1))
        else:
            result.append(value)
    return bytes(result)


def _manifest(*mods, overflow=0, signatures=(), protocol=2, hashes=None) -> bytes:
    payload = bytearray((protocol, overflow, 0, 0, len(mods)))
    for index, (workshop_id, name) in enumerate(mods):
        encoded_id = int(workshop_id).to_bytes(8, "little").rstrip(b"\0")
        encoded_name = name.encode("utf-8")
        mod_hash = hashes[index] if hashes is not None else 0x12345678
        payload.extend(mod_hash.to_bytes(4, "little"))
        payload.append(len(encoded_id))
        payload.extend(encoded_id)
        payload.append(len(encoded_name))
        payload.extend(encoded_name)
    payload.append(len(signatures))
    for signature in signatures:
        encoded = signature.encode("utf-8")
        payload.append(len(encoded))
        payload.extend(encoded)
    return _stuff(bytes(payload))


def _rules(payload: bytes, split_at: int | None = None):
    if split_at is None:
        split_at = len(payload)
    return {
        b"\x02\x08": payload[split_at:],
        b"\x01\x08": payload[:split_at],
        b"island": b"ChernarusPlus",
    }


class DecodeDayzModRulesTests(unittest.TestCase):
    def test_decodes_sorted_chunks_split_inside_a_record(self):
        payload = _manifest(
            (1559212036, "Community Framework"),
            (2116151222, "Namalsk Island"),
            signatures=("server",),
        )
        self.assertEqual(
            decode_dayz_mod_rules(_rules(payload, split_at=17)),
            [
                DayzRequiredMod(1559212036, "Community Framework", 0x12345678),
                DayzRequiredMod(2116151222, "Namalsk Island", 0x12345678),
            ],
        )

    def test_preserves_distinct_unsigned_hashes_including_stuffed_bytes(self):
        hashes = [0, 0xFF0100FF, 0xFFFFFFFF]
        mods = decode_dayz_mod_rules(
            _rules(
                _manifest((0, "Local"), (111, "One"), (222, "Two"), hashes=hashes),
                split_at=9,
            )
        )
        self.assertEqual([mod.server_hash for mod in mods], hashes)
        self.assertEqual([mod.workshop_id for mod in mods], [None, 111, 222])

    def test_accepts_complete_zero_mod_manifest(self):
        self.assertEqual(decode_dayz_mod_rules(_rules(_manifest())), [])

    def test_rejects_truncated_manifest_atomically(self):
        with self.assertRaisesRegex(DayzModQueryError, "ended while reading"):
            decode_dayz_mod_rules(_rules(_manifest((111, "Example"))[:-2]))

    def test_rejects_overflow_as_incomplete(self):
        with self.assertRaisesRegex(DayzModQueryError, "incomplete"):
            decode_dayz_mod_rules(_rules(_manifest((111, "Example"), overflow=1)))

    def test_rejects_duplicate_workshop_ids(self):
        with self.assertRaisesRegex(DayzModQueryError, "duplicate"):
            decode_dayz_mod_rules(_rules(_manifest((111, "One"), (111, "Two"))))

    def test_accepts_bounded_opaque_server_extension(self):
        self.assertEqual(
            decode_dayz_mod_rules(_rules(_manifest() + b"\x00\xffserver-extension")),
            [],
        )

    def test_rejects_oversized_server_extension(self):
        with self.assertRaisesRegex(DayzModQueryError, "extension is too large"):
            decode_dayz_mod_rules(_rules(_manifest() + (b"x" * 2049)))


class QueryDayzRequiredModsTests(unittest.TestCase):
    @patch("wolflauncher.dayz_mod_query.a2s.rules")
    def test_queries_raw_rules_with_a_bounded_timeout(self, rules):
        rules.return_value = _rules(_manifest((111, "Example")))
        self.assertEqual(
            query_dayz_required_mods("203.0.113.10", 27016),
            [DayzRequiredMod(111, "Example", 0x12345678)],
        )
        rules.assert_called_once_with(("203.0.113.10", 27016), timeout=10.0, encoding=None)

    @patch("wolflauncher.dayz_mod_query.a2s.rules", side_effect=TimeoutError("timed out"))
    def test_wraps_network_failure_without_partial_data(self, rules):
        with self.assertRaisesRegex(DayzModQueryError, "direct server mod query failed"):
            query_dayz_required_mods("203.0.113.10", 27016)


if __name__ == "__main__":
    unittest.main()


class UnpublishedManifestTests(unittest.TestCase):
    def test_mixed_local_and_workshop_entries_preserve_order_and_names(self):
        mods = decode_dayz_mod_rules(
            _rules(_manifest((0, "Local First"), (111, "CF"), (0, "Local Last")))
        )
        self.assertEqual(
            mods,
            [
                DayzRequiredMod(None, "Local First", 0x12345678),
                DayzRequiredMod(111, "CF", 0x12345678),
                DayzRequiredMod(None, "Local Last", 0x12345678),
            ],
        )

    def test_truncated_unpublished_entry_still_rejects_atomically(self):
        with self.assertRaises(DayzModQueryError):
            decode_dayz_mod_rules(_rules(_manifest((0, "Local"), (111, "CF"))[:-3]))

    def test_nonempty_zero_id_is_still_invalid(self):
        payload = b"\x02\x00\x00\x00\x01" + bytes(4) + b"\x01\x00\x00\x00"
        with self.assertRaisesRegex(DayzModQueryError, "invalid or duplicate"):
            decode_dayz_mod_rules(_rules(_stuff(payload)))

    def test_unpublished_entries_keep_signature_framing_checks(self):
        with self.assertRaisesRegex(DayzModQueryError, "signature"):
            decode_dayz_mod_rules(_rules(_manifest((0, "Local"), signatures=("key",))[:-1]))
