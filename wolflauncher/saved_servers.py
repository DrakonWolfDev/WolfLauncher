"""Combined saved-profile adapter; profile locations are never game identity.

Reads are non-destructive. Malformed entries are reported and recoverable entries
remain visible. A damaged profile is read-only until repaired. Multi-file writes
use an undo journal so retry/startup restores an interrupted transaction.
"""

import json
from dataclasses import replace
from pathlib import Path

import yaml

from .config import _load_server_yaml
from .models import Server
from .persistence import atomic_write_bytes, atomic_write_text
from .server_identity import endpoint_key, merge_identity, saved_server_fields
from .settings import normalize_favourite_key, server_key


class SavedServerRepository:
    def __init__(self, directory: Path):
        self.directory = directory
        self.errors: list[str] = []
        self._origins: dict[str, list[tuple[Path, int]]] = {}
        self._data: dict[Path, dict] = {}
        self._damaged: set[Path] = set()
        self.journal = directory / "saved-servers-transaction.json"

    def profile_path(self, product: str) -> Path:
        return self.directory / (
            "servers-experimental.yaml" if product == "experimental" else "servers.yaml"
        )

    def _recover(self):
        if not self.journal.exists():
            return
        entries = json.loads(self.journal.read_text(encoding="utf-8"))
        for name, content in entries.items():
            if name not in {
                "servers.yaml",
                "servers-experimental.yaml",
                "favourites.json",
                "favourites-experimental.json",
            }:
                raise ValueError("Invalid saved-server recovery journal")
            path = self.directory / name
            if content is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write_bytes(path, content.encode("utf-8"))
        self.journal.unlink()

    def load(self) -> list[Server]:
        self._recover()
        self.errors, self._origins, self._data, self._damaged = [], {}, {}, set()
        merged: dict[str, Server] = {}
        for profile in ("stable", "experimental"):
            path = self.profile_path(profile)
            index_path = self.directory / (
                "favourites.json" if profile == "stable" else "favourites-experimental.json"
            )
            try:
                index = (
                    json.loads(index_path.read_text(encoding="utf-8"))
                    if index_path.exists()
                    else None
                )
                if index is not None and (
                    not isinstance(index, list) or not all(isinstance(k, str) for k in index)
                ):
                    raise ValueError("favourites index must contain a list of keys")
                keys = {normalize_favourite_key(k) for k in index} if index is not None else None
            except (OSError, ValueError) as exc:
                self.errors.append(f"{index_path}: {exc}")
                self._damaged.add(index_path)
                keys = None
            try:
                data = _load_server_yaml(path)
                if not isinstance(data.get("servers", []), list):
                    raise ValueError("servers must contain a list")
            except (OSError, ValueError) as exc:
                self.errors.append(f"{path}: {exc}")
                self._damaged.add(path)
                continue
            self._data[path] = data
            for position, row in enumerate(data.get("servers", [])):
                try:
                    if not isinstance(row, dict):
                        raise ValueError("server entry must be a mapping")
                    server = Server(
                        str(row["name"]),
                        str(row.get("group", "Community")),
                        str(row["host"]),
                        int(row["game_port"]),
                        int(row["query_port"]),
                        bool(row.get("favourite", False)),
                        **saved_server_fields(row),
                    )
                    if not server.host.strip() or not all(
                        0 < p <= 65535 for p in (server.game_port, server.query_port)
                    ):
                        raise ValueError("invalid endpoint")
                except (KeyError, TypeError, ValueError) as exc:
                    self.errors.append(f"{path}, entry {position + 1}: {exc}")
                    self._damaged.add(path)
                    continue
                if server.product == "unknown" and not server.identity_evidence:
                    server.identity_evidence = (
                        {
                            "product": profile,
                            "source": "legacy_profile",
                            "observed_at": "",
                            "verified": False,
                        },
                    )
                if keys is not None:
                    server.favourite = server_key(server) in keys or endpoint_key(server) in keys
                key = endpoint_key(server)
                for existing_key, previous in merged.items():
                    previous_aliases = {existing_key, *previous.endpoint_aliases}
                    aliases = {key, *server.endpoint_aliases}
                    if previous_aliases & aliases or (
                        server.stable_server_id
                        and previous.stable_server_id == server.stable_server_id
                        and server.product == previous.product
                        and server.product != "unknown"
                    ):
                        key = existing_key
                        break
                self._origins.setdefault(key, []).append((path, position))
                if key in merged:
                    previous = merged[key]
                    merged[key] = replace(
                        previous,
                        favourite=previous.favourite or server.favourite,
                        endpoint_aliases=tuple(
                            dict.fromkeys(
                                (
                                    *previous.endpoint_aliases,
                                    *server.endpoint_aliases,
                                    endpoint_key(server),
                                )
                            )
                        ),
                        **merge_identity(previous, server),
                    )
                else:
                    merged[key] = server
        return list(merged.values())

    def _commit(self, changes: dict[Path, str]):
        if any(path in self._damaged for path in changes):
            raise ValueError(
                "Saved profile contains damaged data; repair it before saving. "
                + "; ".join(self.errors)
            )
        originals = {
            # read_text performs universal-newline translation. The journal must
            # preserve the original bytes, including CRLF, for exact rollback.
            path.name: path.read_bytes().decode("utf-8") if path.exists() else None
            for path in changes
        }
        atomic_write_text(self.journal, json.dumps(originals))
        try:
            for path, text in changes.items():
                atomic_write_text(path, text, backup=True)
            self.journal.unlink()
        except BaseException:
            self._recover()
            raise

    def _index_changes(self, changes, originals, updated=None):
        for profile in ("stable", "experimental"):
            path = self.profile_path(profile)
            if path not in changes:
                continue
            index_path = self.directory / (
                "favourites.json" if profile == "stable" else "favourites-experimental.json"
            )
            old = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
            if not isinstance(old, list) or not all(isinstance(k, str) for k in old):
                raise ValueError(f"Invalid favourites index: {index_path}")
            keys = {
                normalize_favourite_key(k)
                for k in old
                if normalize_favourite_key(k).split("|")[-1] not in originals
            }
            if updated is not None and updated.favourite:
                keys.add(server_key(updated))
            changes[index_path] = json.dumps(sorted(keys), indent=2) + "\n"

    def update(self, original: Server, updated: Server) -> bool:
        origins = self._origins.get(endpoint_key(original), [])
        if not origins:
            return False
        if (
            endpoint_key(updated) != endpoint_key(original)
            and endpoint_key(updated) in self._origins
        ):
            raise ValueError("Another favourite already uses that endpoint.")
        changes = {}
        for path, index in origins:
            data = yaml.safe_load(changes[path]) if path in changes else _load_server_yaml(path)
            rows = data["servers"]
            if index >= len(rows) or rows[index] != self._data[path]["servers"][index]:
                raise ValueError("Saved server changed; reload before saving.")
            rows[index] = {
                **rows[index],
                "name": updated.name,
                "group": updated.group,
                "host": updated.host,
                "game_port": updated.game_port,
                "query_port": updated.query_port,
                "favourite": updated.favourite,
                **saved_server_fields(updated),
            }
            changes[path] = yaml.safe_dump(data, sort_keys=False)
        self._index_changes(
            changes,
            {endpoint_key(original), endpoint_key(updated), *original.endpoint_aliases},
            updated,
        )
        self._commit(changes)
        self.load()
        return True

    def add(self, server: Server):
        if endpoint_key(server) in self._origins:
            raise ValueError("This server is already in the Favourite Servers list.")
        path = self.profile_path(server.product)
        data = _load_server_yaml(path)
        data.setdefault("servers", []).append(
            {
                "name": server.name,
                "group": server.group,
                "host": server.host,
                "game_port": server.game_port,
                "query_port": server.query_port,
                "favourite": server.favourite,
                **saved_server_fields(server),
            }
        )
        changes = {path: yaml.safe_dump(data, sort_keys=False)}
        self._index_changes(changes, {endpoint_key(server)}, server)
        self._commit(changes)
        self.load()

    def remove(self, server: Server) -> bool:
        origins = self._origins.get(endpoint_key(server), [])
        changes = {}
        for path in {path for path, _ in origins}:
            data = _load_server_yaml(path)
            if data != self._data[path]:
                raise ValueError("Saved servers changed; reload before removing.")
            indices = {index for origin_path, index in origins if origin_path == path}
            data["servers"] = [
                row for index, row in enumerate(data["servers"]) if index not in indices
            ]
            changes[path] = yaml.safe_dump(data, sort_keys=False)
        self._index_changes(changes, {endpoint_key(server), *server.endpoint_aliases})
        self._commit(changes)
        self.load()
        return bool(origins)

    def reorder(self, servers: list[Server]):
        if {endpoint_key(s) for s in servers} != set(self._origins):
            raise ValueError("Saved servers changed; reload before reordering.")
        changes = {}
        for path, data in self._data.items():
            if _load_server_yaml(path) != data:
                raise ValueError("Saved servers changed; reload before reordering.")
            rows = data.get("servers", [])
            data = {
                **data,
                "servers": [
                    rows[i] for s in servers for p, i in self._origins[endpoint_key(s)] if p == path
                ],
            }
            changes[path] = yaml.safe_dump(data, sort_keys=False)
        self._commit(changes)
        self.load()

    def save_favourites(self, keys: set[str]):
        changes = {}
        for profile in ("stable", "experimental"):
            path = self.profile_path(profile)
            index_path = self.directory / (
                "favourites.json" if profile == "stable" else "favourites-experimental.json"
            )
            # Retain orphan legacy stars, including entries not currently in YAML.
            old = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
            if not isinstance(old, list) or not all(isinstance(k, str) for k in old):
                raise ValueError(f"Invalid favourites index: {index_path}")
            managed = {
                key for key, origins in self._origins.items() if any(p == path for p, _ in origins)
            }
            # A displayed favourite can merge differently addressed rows from
            # both profiles. Unstarring it must remove every managed alias.
            for origins in self._origins.values():
                for origin_path, index in origins:
                    if origin_path != path:
                        continue
                    row = self._data[path]["servers"][index]
                    managed.add(
                        normalize_favourite_key(
                            f"{row['host']}:{row['game_port']}:{row['query_port']}"
                        )
                    )
                    managed.update(
                        normalize_favourite_key(alias).split("|")[-1]
                        for alias in saved_server_fields(row)["endpoint_aliases"]
                    )
            retained = {
                normalize_favourite_key(k)
                for k in old
                if normalize_favourite_key(k).split("|")[-1] not in managed
            }
            retained.update(k for k in keys if k.split("|")[-1] in managed)
            changes[index_path] = json.dumps(sorted(retained), indent=2) + "\n"
        self._commit(changes)
