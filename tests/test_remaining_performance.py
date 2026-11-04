import os
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget

from wolflauncher import mods, server_cache
from wolflauncher.browser_snapshot import BrowserSnapshotLoader, BrowserSnapshotWorker
from wolflauncher.mod_name_cache import ModNameCache
from wolflauncher.mod_table import KEY_ROLE, populate_mod_table
from wolflauncher.models import DiscoveredServer, Server
from wolflauncher.mods import ModCheckResult, RequiredMod
from wolflauncher.mods_feature import ModsFeatureMixin
from wolflauncher.server_browser_controller import BrowserQuery, load_browser_snapshot
from wolflauncher.thumbnail_cache import ThumbnailCache
from wolflauncher.workshop_subscription import (
    ITEM_STATE_DOWNLOADING,
    ITEM_STATE_INSTALLED,
    WorkshopItemProgress,
)


class QtCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])


class ThumbnailReuseTests(QtCase):
    def view(self):
        view = ModsFeatureMixin()
        view.mod_thumbnail_reply = None
        view.mod_detail_thumbnail = QLabel()
        view.mod_detail_thumbnail.resize(320, 180)
        view.mod_thumbnail_placeholder = QPixmap()
        view.mod_thumbnail_manager = Mock()
        self.addCleanup(view.mod_detail_thumbnail.close)
        return view

    def png(self):
        pixmap = QPixmap(64, 32)
        pixmap.fill(Qt.red)
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        self.assertTrue(pixmap.save(buffer, "PNG"))
        return bytes(data)

    def reply(self, payload=None, content_type="image/png", url="https://images.test/a.png"):
        reply = Mock()
        reply.error.return_value = QNetworkReply.NoError
        reply.isReadable.return_value = True
        reply.url.return_value = QUrl(url)
        reply.header.return_value = content_type
        reply.readAll.return_value = self.png() if payload is None else payload
        return reply

    def test_same_pending_request_and_valid_cached_preview_are_reused(self):
        view = self.view()
        reply = self.reply()
        view.mod_thumbnail_manager.get.return_value = reply
        with patch("wolflauncher.mods_feature.QTimer.singleShot"):
            view.load_mod_thumbnail("https://images.test/a.png", revision=10)
            view.load_mod_thumbnail("https://images.test/a.png", revision=10)
            view.mod_thumbnail_manager.get.assert_called_once()
            reply.abort.assert_not_called()
            view.finish_mod_thumbnail_load(reply)
            view.load_mod_thumbnail("https://images.test/a.png", revision=10)
        view.mod_thumbnail_manager.get.assert_called_once()
        self.assertFalse(view.mod_detail_thumbnail.pixmap().isNull())
        reply.deleteLater.assert_called_once()

    def test_revision_and_expiry_refresh_same_url_and_late_reply_is_ignored(self):
        view = self.view()
        first, second = self.reply(), self.reply()
        view.mod_thumbnail_manager.get.side_effect = [first, second, self.reply()]
        with (
            patch("wolflauncher.mods_feature.QTimer.singleShot"),
            patch("wolflauncher.thumbnail_cache.time.monotonic", return_value=1),
        ):
            view.load_mod_thumbnail("https://images.test/a.png", revision=10)
            view.load_mod_thumbnail("https://images.test/a.png", revision=11)
            first.abort.assert_called_once()
            view.finish_mod_thumbnail_load(first)
            self.assertIs(view.mod_thumbnail_reply, second)
            self.assertEqual(view.mod_thumbnail_cache.entries, {})
            view.finish_mod_thumbnail_load(second)
        with (
            patch("wolflauncher.mods_feature.QTimer.singleShot"),
            patch("wolflauncher.thumbnail_cache.time.monotonic", return_value=302),
        ):
            view.load_mod_thumbnail("https://images.test/a.png", revision=11)
        self.assertEqual(view.mod_thumbnail_manager.get.call_count, 3)

    def test_invalid_payload_type_redirect_and_dimensions_never_enter_cache(self):
        for reply in (
            self.reply(b"not a raster"),
            self.reply(content_type="image/svg+xml"),
            self.reply(url="http://images.test/a.png"),
        ):
            view = self.view()
            view.mod_thumbnail_manager.get.return_value = reply
            with patch("wolflauncher.mods_feature.QTimer.singleShot"):
                view.load_mod_thumbnail("https://images.test/a.png")
                view.finish_mod_thumbnail_load(reply)
            self.assertEqual(view.mod_thumbnail_cache.entries, {})
        view = self.view()
        reply = self.reply()
        view.mod_thumbnail_manager.get.return_value = reply
        with (
            patch("wolflauncher.mods_feature.QTimer.singleShot"),
            patch("wolflauncher.mods_feature.QImageReader") as reader,
        ):
            reader.return_value.format.return_value = QByteArray(b"png")
            reader.return_value.size.return_value.width.return_value = 999999
            reader.return_value.size.return_value.height.return_value = 999999
            view.load_mod_thumbnail("https://images.test/a.png")
            view.finish_mod_thumbnail_load(reply)
            reader.return_value.read.assert_not_called()

    def test_memory_entry_limits_and_expiry_are_enforced(self):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.red)
        cache = ThumbnailCache(max_bytes=2048, max_entries=1, ttl=5)
        with patch("wolflauncher.thumbnail_cache.time.monotonic", return_value=1):
            cache.put("one", pixmap)
            pixmap.fill(Qt.blue)
            self.assertEqual(cache.get("one").toImage().pixelColor(0, 0), Qt.red)
            cache.put("two", pixmap)
            self.assertIsNone(cache.get("one"))
            cache.put("too large", QPixmap(100, 100))
            self.assertIsNone(cache.get("too large"))
        with patch("wolflauncher.thumbnail_cache.time.monotonic", return_value=6):
            self.assertIsNone(cache.get("two"))
            self.assertEqual(cache.bytes, 0)

    def test_unsafe_selection_aborts_pending_reply_and_does_not_request_or_cache(self):
        view = self.view()
        reply = self.reply()
        view.mod_thumbnail_manager.get.return_value = reply
        with patch("wolflauncher.mods_feature.QTimer.singleShot"):
            view.load_mod_thumbnail("https://images.test/a.png")
            view.load_mod_thumbnail("file:///tmp/preview.png")
            view.finish_mod_thumbnail_load(reply)
        reply.abort.assert_called_once()
        view.mod_thumbnail_manager.get.assert_called_once()
        self.assertIsNone(view.mod_thumbnail_reply)
        self.assertEqual(view.mod_thumbnail_cache.entries, {})


class IncrementalModTableTests(QtCase):
    def table(self):
        table = QTableWidget(0, 4)
        table.resize(800, 300)
        self.addCleanup(table.close)
        return table

    def test_unchanged_refresh_allocates_no_items_and_preserves_user_widths(self):
        table = self.table()
        items = [RequiredMod("1", "One", installed=True), RequiredMod("2", "Two")]
        populate_mod_table(table, items)
        first = table.item(0, 0)
        table.setColumnWidth(2, 250)
        table.selectRow(1)
        with patch(
            "wolflauncher.mod_table.QTableWidgetItem", side_effect=AssertionError("reallocated")
        ):
            populate_mod_table(table, items, preserve_position=True)
        self.assertIs(table.item(0, 0), first)
        self.assertEqual(table.item(table.currentRow(), 2).text(), "2")
        self.assertEqual(table.columnWidth(2), 250)

    def test_changed_rows_reuse_items_and_preserve_sort_and_local_identity(self):
        table = self.table()
        items = [
            RequiredMod("1", "One"),
            RequiredMod("2", "Two"),
            RequiredMod("", "Manual A"),
            RequiredMod("", "Manual B"),
        ]
        populate_mod_table(table, items)
        table.setSortingEnabled(True)
        table.sortItems(1, Qt.DescendingOrder)
        selected = next(row for row in range(4) if table.item(row, 1).text() == "Manual B")
        table.selectRow(selected)
        key = table.item(selected, 1).data(KEY_ROLE)
        cells = {table.item(row, 1).text(): table.item(row, 0) for row in range(4)}
        items[0].installed = True
        populate_mod_table(table, items, preserve_position=True)
        self.assertTrue(table.isSortingEnabled())
        self.assertEqual(table.item(table.currentRow(), 1).data(KEY_ROLE), key)
        for row in range(4):
            self.assertIs(table.item(row, 0), cells[table.item(row, 1).text()])
        self.assertEqual(table.item(0, 1).text(), "Two")

    def test_progress_remains_id_bound_when_sorted_and_terminal_state_removes_widget(self):
        table = self.table()
        result = ModCheckResult(
            True,
            Server("S", "G", "127.0.0.1", 2302, 2303),
            [RequiredMod("1", "One", installed=True), RequiredMod("2", "Two", installed=True)],
        )
        populate_mod_table(table, result.required_mods)
        table.setSortingEnabled(True)
        table.sortItems(0, Qt.DescendingOrder)
        view = ModsFeatureMixin()
        view.mods_table = table
        view._selected_mod_result = lambda **_: result
        progress = [
            WorkshopItemProgress("1", ITEM_STATE_DOWNLOADING, 10, 100),
            WorkshopItemProgress("2", ITEM_STATE_DOWNLOADING, 80, 100),
        ]
        view.update_mod_progress_rows(progress)
        for row in range(2):
            expected = 10 if table.item(row, 2).text() == "1" else 80
            self.assertEqual(table.cellWidget(row, 0).value(), expected)
        widget = table.cellWidget(0, 0)
        view.update_mod_progress_rows(progress)
        self.assertIs(table.cellWidget(0, 0), widget)
        view.update_mod_progress_rows(
            [WorkshopItemProgress(item, ITEM_STATE_INSTALLED) for item in ("1", "2")]
        )
        self.assertTrue(all(table.cellWidget(row, 0) is None for row in range(2)))
        self.assertTrue(all("Installed" in table.item(row, 0).text() for row in range(2)))

    def test_failed_refresh_restores_signal_paint_and_sort_state(self):
        table = self.table()
        table.setSortingEnabled(True)
        with patch("wolflauncher.mod_table.QTableWidgetItem", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                populate_mod_table(table, [RequiredMod("1", "One")], preserve_position=True)
        self.assertTrue(table.updatesEnabled())
        self.assertTrue(table.isSortingEnabled())
        self.assertFalse(table.signalsBlocked())

    def test_table_refresh_removes_a_completed_download_overlay(self):
        from PySide6.QtWidgets import QProgressBar

        table = self.table()
        item = RequiredMod("1", "One", installed=True)
        populate_mod_table(table, [item])
        table.setCellWidget(0, 0, QProgressBar())
        populate_mod_table(table, [item], preserve_position=True)
        self.assertIsNone(table.cellWidget(0, 0))
        self.assertIn("Installed", table.item(0, 0).text())


class ModScanReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = ModNameCache(max_entries=2)
        self.patch = patch("wolflauncher.mod_name_cache.mod_name_cache", self.cache)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def make_mod(self, item, name, root=None):
        path = (root or self.root) / item
        path.mkdir(parents=True)
        (path / "meta.cpp").write_text(f'name="{name}";')
        return path

    def test_unchanged_names_skip_read_but_changes_and_deletion_are_seen(self):
        path = self.make_mod("1", "One")
        with patch("wolflauncher.mods._read_mod_name_file", wraps=mods._read_mod_name_file) as read:
            self.assertEqual(mods.scan_installed_mods(self.root), {"1": "One"})
            self.assertEqual(mods.scan_installed_mods(self.root), {"1": "One"})
            self.assertEqual(read.call_count, 1)
            (path / "meta.cpp").write_text('name="Changed";')
            self.assertEqual(mods.scan_installed_mods(self.root), {"1": "Changed"})
            self.assertEqual(read.call_count, 2)
            (path / "meta.cpp").unlink()
            path.rmdir()
            self.assertEqual(mods.scan_installed_mods(self.root), {})

    def test_library_identity_replacement_limits_and_concurrent_edits(self):
        a = self.make_mod("1", "A", self.root / "library-a") / "meta.cpp"
        b = self.make_mod("1", "B", self.root / "library-b") / "meta.cpp"
        self.assertEqual(mods._read_mod_name(a), "A")
        self.assertEqual(mods._read_mod_name(b), "B")
        replacement = a.with_suffix(".new")
        replacement.write_text('name="Replacement";')
        replacement.replace(a)
        self.assertEqual(mods._read_mod_name(a), "Replacement")
        c = self.make_mod("3", "C") / "meta.cpp"
        self.assertEqual(mods._read_mod_name(c), "C")
        self.assertEqual(len(self.cache._entries), 2)

        def changing(path):
            path.write_text('name="new";')
            return "old"

        self.assertEqual(ModNameCache().read(c, changing), "")
        reader = Mock(side_effect=[OSError("temporary read failure"), "Recovered"])
        cache = ModNameCache()
        self.assertEqual(cache.read(c, reader), "")
        self.assertEqual(cache.read(c, reader), "Recovered")
        self.assertEqual(reader.call_count, 2)

    def test_server_check_reads_only_required_names_and_retains_total_installed_count(self):
        for i in range(1, 11):
            self.make_mod(str(i), f"Mod {i}")
        server = Server("S", "G", "127.0.0.1", 2302, 2303)
        with (
            patch("wolflauncher.mods.fetch_required_mods", return_value=[RequiredMod("2")]),
            patch("wolflauncher.mods._read_mod_name_file", wraps=mods._read_mod_name_file) as read,
        ):
            result = mods.check_server_mods(server, self.root)
        self.assertEqual(result.installed_count, 10)
        self.assertEqual(result.required_mods[0].installed_name, "Mod 2")
        read.assert_called_once_with(self.root / "2" / "meta.cpp")
        with (
            patch("wolflauncher.mods.fetch_required_mods", side_effect=OSError("offline")),
            patch("wolflauncher.mods._read_mod_name_file") as read,
        ):
            result = mods.check_server_mods(server, self.root)
        self.assertFalse(result.ok)
        self.assertEqual(result.installed_count, 10)
        read.assert_not_called()


class BrowserSnapshotTests(QtCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "cache.sqlite3"
        self.connection = server_cache.connect(self.path)
        self.addCleanup(self.connection.close)
        server_cache.upsert_servers(
            self.connection,
            [
                DiscoveredServer("Stable", "127.0.0.1", 2302, 2303, product="stable"),
                DiscoveredServer("Experimental", "127.0.0.2", 2302, 2303, product="experimental"),
            ],
        )

    def test_worker_reads_consistent_edition_scoped_snapshot_with_read_only_connection(self):
        worker = BrowserSnapshotWorker(self.path, BrowserQuery(products=("stable",)), "")
        results = []
        worker.ready.connect(lambda *args: results.append(args))
        worker.run()
        snapshot, options, error = results[0]
        self.assertEqual([server.name for server in snapshot.servers], ["Stable"])
        self.assertEqual(snapshot.match_count, 1)
        self.assertEqual(snapshot.cache_summary["total"], 1)
        self.assertEqual(error, "")
        with patch(
            "wolflauncher.browser_snapshot.load_browser_snapshot",
            side_effect=lambda connection, *_a, **_kw: connection.execute(
                "DELETE FROM discovered_servers"
            ),
        ):
            worker.run()
        self.assertIn("readonly", results[-1][2])
        self.assertEqual(server_cache.cache_summary(self.connection)["total"], 2)

    def test_cancelled_worker_emits_nothing_and_missing_database_is_not_created(self):
        missing = self.path.with_name("missing.sqlite3")
        worker = BrowserSnapshotWorker(missing, BrowserQuery(), "")
        ready = Mock()
        worker.ready.connect(ready)
        worker.cancel()
        worker.run()
        ready.assert_not_called()
        worker = BrowserSnapshotWorker(missing, BrowserQuery(), "")
        worker.ready.connect(ready)
        worker.run()
        self.assertFalse(missing.exists())
        self.assertTrue(ready.call_args.args[2])

    def test_rows_counts_and_summary_share_a_transaction_during_external_write(self):
        worker = BrowserSnapshotWorker(self.path, BrowserQuery(products=("stable",)), "")
        results = []
        worker.ready.connect(lambda *args: results.append(args))
        count = server_cache.count_search_servers

        def write_during_count(connection, **filters):
            writer = server_cache.connect(self.path)
            try:
                server_cache.upsert_server(
                    writer, DiscoveredServer("Added", "127.0.0.9", 2302, 2303, product="stable")
                )
            finally:
                writer.close()
            return count(connection, **filters)

        with patch(
            "wolflauncher.server_cache.count_search_servers", side_effect=write_during_count
        ):
            worker.run()
        snapshot = results[0][0]
        self.assertEqual(len(snapshot.servers), 1)
        self.assertEqual(snapshot.match_count, 1)
        self.assertEqual(snapshot.cache_summary["total"], 1)
        self.assertEqual(
            server_cache.cache_summary(self.connection, products=("stable",))["total"], 2
        )

    def test_cancel_during_query_and_shutdown_cancel_registered_worker(self):
        from wolflauncher.lifecycle import begin_runtime_shutdown

        worker = BrowserSnapshotWorker(self.path, BrowserQuery(products=("stable",)), "")
        ready = Mock()
        worker.ready.connect(ready)

        def cancel_during_query(connection, query, **kwargs):
            worker.cancel()
            return load_browser_snapshot(connection, query, **kwargs)

        with patch(
            "wolflauncher.browser_snapshot.load_browser_snapshot", side_effect=cancel_during_query
        ):
            worker.run()
        ready.assert_not_called()
        active = Mock()
        active.isRunning.return_value = True
        window = SimpleNamespace(browser_snapshot_worker=active)
        begin_runtime_shutdown(window)
        active.cancel.assert_called_once()
        active.requestInterruption.assert_called_once()

    def test_external_commit_invalidates_auxiliary_and_queued_result(self):
        window, loader = self.window()
        with patch("wolflauncher.browser_snapshot.BrowserSnapshotWorker") as factory:
            loader.request(window.query)
            old_token = loader._database_token()
            writer = server_cache.connect(self.path)
            try:
                server_cache.upsert_server(
                    writer, DiscoveredServer("External", "127.0.0.8", 2302, 2303, product="stable")
                )
            finally:
                writer.close()
            self.assertNotEqual(loader._database_token(), old_token)
            factory.return_value.ready.connect.call_args.args[0](None, None, "")
        window.apply_browser_snapshot.assert_not_called()
        self.assertIsNotNone(loader.pending)

    def test_requested_freshness_waits_for_new_rows_and_resumes_after_worker_finishes(self):
        from wolflauncher.server_browser_feature import ServerBrowserMixin

        window, loader = self.window()
        window.browser_snapshot_loader = loader
        window.continue_initial_results_freshness_check = Mock()
        loader.request(window.query)
        with patch(
            "wolflauncher.server_browser_feature.optional_polling_paused", return_value=False
        ):
            ServerBrowserMixin._schedule_results_freshness_check(window)
        self.assertTrue(loader.pending_freshness)
        self.wait_until(lambda: window.browser_snapshot_worker is None)
        window.apply_browser_snapshot.assert_called_once()
        window.continue_initial_results_freshness_check.assert_called_once()
        self.assertFalse(loader.pending_freshness)

    def test_removed_filter_option_requeries_resulting_controls(self):
        window, loader = self.window()
        window.query = replace(window.query, version="old")
        with patch("wolflauncher.browser_snapshot.BrowserSnapshotWorker") as factory:
            loader.request(window.query)
            window.apply_browser_filter_options.side_effect = lambda _: setattr(
                window, "query", replace(window.query, version="")
            )
            snapshot = load_browser_snapshot(self.connection, window.query)
            factory.return_value.ready.connect.call_args.args[0](snapshot, {}, "")
            self.assertEqual(loader.pending[1].version, "")
            window.apply_browser_snapshot.assert_not_called()

    def window(self):
        window = SimpleNamespace(
            server_cache=self.connection,
            _shutting_down=False,
            query=BrowserQuery(products=("stable",)),
            apply_browser_filter_options=Mock(),
            apply_browser_snapshot=Mock(),
            statusBar=Mock(return_value=Mock()),
        )
        window.current_browser_query = lambda: window.query
        loader = BrowserSnapshotLoader(window, self.path)
        return window, loader

    def wait_until(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.002)
        self.assertTrue(predicate())

    def test_real_worker_applies_results_and_reuses_auxiliary_until_database_changes(self):
        window, loader = self.window()
        with patch(
            "wolflauncher.browser_snapshot.browser_filter_options",
            wraps=__import__(
                "wolflauncher.server_browser_controller", fromlist=["browser_filter_options"]
            ).browser_filter_options,
        ) as options:
            loader.request(window.query)
            self.wait_until(lambda: window.browser_snapshot_worker is None)
            self.assertEqual(window.apply_browser_snapshot.call_count, 1)
            window.query = replace(window.query, text="Stable")
            loader.request(window.query)
            self.wait_until(lambda: window.browser_snapshot_worker is None)
            self.assertEqual(options.call_count, 1)
            server_cache.upsert_server(
                self.connection, DiscoveredServer("More", "127.0.0.3", 2302, 2303, product="stable")
            )
            loader.request(window.query)
            self.wait_until(lambda: window.browser_snapshot_worker is None)
            self.assertEqual(options.call_count, 2)

    def test_only_latest_queued_query_runs_and_stale_filter_edition_results_are_rejected(self):
        window, loader = self.window()
        with patch("wolflauncher.browser_snapshot.BrowserSnapshotWorker") as factory:
            worker = factory.return_value
            loader.request(window.query)
            ready = worker.ready.connect.call_args.args[0]
            window.query = replace(window.query, text="old")
            loader.request(window.query)
            window.query = BrowserQuery(products=("experimental",))
            loader.request(window.query)
            self.assertEqual(factory.call_count, 1)
            ready(
                load_browser_snapshot(self.connection, BrowserQuery(products=("stable",))), {}, ""
            )
            window.apply_browser_snapshot.assert_not_called()
            worker.finished.connect.call_args.args[0]()
            self.assertEqual(factory.call_count, 2)
            self.assertEqual(factory.call_args.args[1].products, ("experimental",))

    def test_database_change_and_shutdown_reject_queued_result(self):
        window, loader = self.window()
        with patch("wolflauncher.browser_snapshot.BrowserSnapshotWorker") as factory:
            loader.request(window.query)
            ready = factory.return_value.ready.connect.call_args.args[0]
            server_cache.upsert_server(
                self.connection, DiscoveredServer("Changed", "127.0.0.5", 2302, 2303)
            )
            ready(None, None, "")
            window.apply_browser_snapshot.assert_not_called()
            self.assertIsNotNone(loader.pending)
            window._shutting_down = True
            factory.return_value.finished.connect.call_args.args[0]()
            self.assertIsNone(loader.pending)
            ready(None, None, "")
            window.apply_browser_snapshot.assert_not_called()
