"""Opt-in synthetic UI validation inside the actual frozen Linux application.

Requires isolated temporary XDG directories. No fixture paths, commands, server
targets or Python code can be supplied through the environment.
"""

import json
import subprocess
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QPixmap

from . import server_cache
from .host_environment import host_process_environment
from .models import DiscoveredServer, Server
from .mods import ModCheckResult, RequiredMod
from .paths import user_config_dir, user_data_dir
from .status import gamedig_command
from .thumbnail_cache import ThumbnailCache


def isolated_root(environment, window):
    root = Path(environment.get("WOLFLAUNCHER_SMOKE_ROOT", "/")).resolve()
    temporary = Path(tempfile.gettempdir()).resolve()
    if root == temporary or not root.is_relative_to(temporary):
        raise ValueError("UI validation requires a dedicated temporary root")
    for path in (
        user_config_dir(),
        user_data_dir(),
        Path(window.server_cache.execute("PRAGMA database_list").fetchone()[2]),
    ):
        if not path.resolve().is_relative_to(root):
            raise ValueError("UI validation requires isolated config, data and database paths")
    return root


class PackagedValidation:
    def __init__(self, app, window, environment):
        self.app, self.window, self.environment = app, window, environment
        self.phase = 0
        self.started = self.last_tick = time.monotonic()
        self.max_tick_gap_ms = 0
        self.results = {}
        self.timer = QTimer(window)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.tick)

    def start(self):
        self.timer.start()

    def tick(self):
        try:
            now = time.monotonic()
            self.max_tick_gap_ms = max(self.max_tick_gap_ms, (now - self.last_tick) * 1000)
            self.last_tick = now
            if now - self.started > 20:
                raise RuntimeError("Synthetic UI validation timed out")
            self.step()
        except Exception as exc:
            self.timer.stop()
            self.app.setProperty("packagedValidationFailed", True)
            print(
                json.dumps(
                    {"packaged_validation": "failed", "phase": self.phase, "error": str(exc)}
                ),
                flush=True,
            )
            self.window.close()

    def step(self):
        window = self.window
        if self.phase == 0:
            self.root = isolated_root(self.environment, window)
            # A synthetic pause suppresses optional polling; it launches no game.
            window._game_session_active = True
            window.timer.stop()
            rows = [
                DiscoveredServer(
                    f"Validation Stable {i:04}",
                    f"127.1.{i // 250}.{i % 250 + 1}",
                    2302,
                    2303,
                    product="stable",
                    map_name="chernarusplus",
                    source="wolfapi",
                )
                for i in range(1000)
            ]
            rows.extend(
                DiscoveredServer(
                    f"Validation Experimental {i}",
                    f"127.2.0.{i + 1}",
                    2302,
                    2303,
                    product="experimental",
                    source="wolfapi_experimental",
                )
                for i in range(10)
            )
            server_cache.upsert_servers(window.server_cache, rows)
            with QSignalBlocker(window.browser_limit):
                window.browser_limit.setCurrentText("1000")
            window.tabs.setCurrentIndex(window.server_browser_tab_index)
            window.refresh_server_browser()
            self.phase = 1
        elif window.browser_snapshot_worker is not None:
            return
        elif self.phase == 1:
            if window.browser_table.rowCount() != 1000:
                raise AssertionError("Expected 1000 Stable browser rows")
            window.browser_table.selectRow(42)
            window.browser_table.verticalScrollBar().setValue(300)
            for query in (
                "Validation Stable 0001",
                "Validation Stable 0002",
                "Validation Stable 0999",
            ):
                window.browser_search.setText(query)
                window.browser_filter_timer.stop()
                window.remote_search_timer.stop()
                window.refresh_server_browser()
            self.phase = 2
        elif self.phase == 2:
            if [server.name for server in window.browser_servers] != ["Validation Stable 0999"]:
                raise AssertionError("Latest browser search did not win")
            window.browser_edition.setCurrentIndex(window.browser_edition.findData("experimental"))
            if window.browser_table.rowCount() != 0:
                raise AssertionError("Previous edition rows remained visible")
            window.browser_search.clear()
            window.browser_filter_timer.stop()
            window.remote_search_timer.stop()
            window.refresh_server_browser()
            self.phase = 3
        elif self.phase == 3:
            if len(window.browser_servers) != 10 or any(
                s.product != "experimental" for s in window.browser_servers
            ):
                raise AssertionError("Experimental isolation failed")
            self.results["browser"] = {
                "stable_rows": 1000,
                "experimental_rows": 10,
                "latest_search": True,
                "scroll_and_selection": True,
            }
            required = [
                RequiredMod(str(i + 1), f"Validation Mod {i:03}", installed=True)
                for i in range(200)
            ]
            result = ModCheckResult(
                True, Server("Validation", "Test", "127.0.0.1", 2302, 2303), required
            )
            window.last_mod_result = result
            window.display_mods_result(result)
            window.mods_table.selectRow(150)
            identity = window.mods_table.item(150, 2).text()
            item = window.mods_table.item(150, 1)
            window.display_mods_result(result)
            if window.mods_table.item(150, 1) is not item:
                raise AssertionError("Unchanged mod items were replaced")
            required[0].workshop_file_size = 1024
            window.display_mods_result(result)
            if window.mods_table.item(window.mods_table.currentRow(), 2).text() != identity:
                raise AssertionError("Mod selection was lost")
            window.mod_thumbnail_cache = ThumbnailCache()
            preview = QPixmap(64, 32)
            preview.fill(Qt.red)
            key = ("https://validation.invalid/preview.png", 1)
            window.mod_thumbnail_cache.put(key, preview)
            window.load_mod_thumbnail(key[0], revision=1)
            if (
                window.mod_detail_thumbnail.pixmap().isNull()
                or window.mod_thumbnail_reply is not None
            ):
                raise AssertionError("Cached preview was not rendered")
            window.tabs.setCurrentIndex(window.mods_tab_index)
            if not window.grab().save(str(self.root / "validation-ui.png")):
                raise AssertionError("Could not save synthetic UI preview")
            self.results["mods"] = {
                "rows": 200,
                "items_reused": True,
                "selection_preserved": True,
                "cached_thumbnail": True,
            }
            self.phase = 4
        elif self.phase == 4:
            command = gamedig_command()
            if not command or len(command) < 2 or not Path(command[1]).is_file():
                raise AssertionError("Bundled GameDig entry is unavailable")
            node = subprocess.run(
                [command[0], "--version"], capture_output=True, text=True, timeout=5, check=True
            )
            child = subprocess.run(
                [
                    "/usr/bin/python3",
                    "-c",
                    "import json,ssl;from pathlib import Path;print(json.dumps({'ssl':ssl.OPENSSL_VERSION,'bundle_ssl':any('_internal' in line and 'libssl' in line for line in Path('/proc/self/maps').read_text().splitlines())}))",
                ],
                env=host_process_environment(),
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            host = json.loads(child.stdout)
            if host["bundle_ssl"]:
                raise AssertionError("Host child loaded bundled SSL")
            self.results["runtime"] = {"node": node.stdout.strip(), "host_child": host}
            self.timer.stop()
            print(
                json.dumps(
                    {
                        "packaged_validation": "passed",
                        "checks": self.results,
                        "elapsed_ms": round((time.monotonic() - self.started) * 1000),
                        "max_tick_gap_ms": round(self.max_tick_gap_ms, 1),
                    }
                ),
                flush=True,
            )
            window.close()


def schedule_validation(app, window, environment):
    validation = PackagedValidation(app, window, environment)
    window.packaged_validation = validation
    validation.start()
