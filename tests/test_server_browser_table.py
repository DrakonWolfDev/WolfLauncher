import os
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QItemSelectionModel, QSize, Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QHeaderView, QPushButton, QTableWidget

from wolflauncher.app import MainWindow, persist_enriched_server
from wolflauncher.server_browser_feature import ServerBrowserMixin
from wolflauncher.models import DiscoveredServer
from wolflauncher.server_browser_table import (
    BROWSER_COLUMN_COUNT,
    BROWSER_FAVOURITE_COLUMN,
    BROWSER_PASSWORD_COLUMN,
    populate_browser_table,
    selected_browser_cache_key,
    update_browser_mod_cell,
    update_browser_table_row,
)
from wolflauncher.table_items import SortableTableWidgetItem
from wolflauncher.theme import STATUS_COLOURS


class ServerBrowserTableTests(unittest.TestCase):
    def test_wolfapi_refresh_uses_background_worker_not_child_process(self):
        worker = Mock()
        discovery_limit = Mock()
        discovery_limit.value.return_value = 250
        hide_quality_flagged = Mock()
        hide_quality_flagged.isChecked.return_value = True
        window = SimpleNamespace(
            browser_summary=Mock(),
            _set_database_refresh_enabled=Mock(),
            discovery_limit=discovery_limit,
            browser_hide_quality_flagged=hide_quality_flagged,
            handle_wolfapi_ready=Mock(),
        )

        with patch("wolflauncher.server_browser_feature.WolfApiDiscoveryWorker", return_value=worker) as create_worker:
            ServerBrowserMixin.start_wolfapi_refresh_process(window, automatic=True, use_v1=True)

        create_worker.assert_called_once_with(
            limit=250,
            automatic=True,
            use_v1=True,
            unflagged_only=True,
        )
        worker.discovery_ready.connect.assert_called_once_with(window.handle_wolfapi_ready)
        worker.start.assert_called_once_with()

    def test_manual_wolfapi_refresh_waits_to_start_freshness(self):
        window = SimpleNamespace(
            discovery_provider_key=Mock(return_value="wolfapi_v1"),
            save_user_settings=Mock(),
            pending_provider_refresh=False,
            results_freshness_worker=None,
            _start_configured_provider_refresh=Mock(),
        )

        MainWindow.refresh_from_configured_provider(window)

        window._start_configured_provider_refresh.assert_called_once_with("wolfapi_v1")

    def test_manual_refresh_defers_until_running_freshness_worker_finishes(self):
        worker = Mock()
        window = SimpleNamespace(
            discovery_provider_key=Mock(return_value="wolfapi_v1"),
            save_user_settings=Mock(),
            pending_provider_refresh=False,
            pending_results_freshness=True,
            initial_results_freshness_batches_remaining=3,
            results_freshness_visible_only=True,
            results_freshness_worker=worker,
            _set_database_refresh_enabled=Mock(),
            statusBar=Mock(return_value=Mock()),
            _start_configured_provider_refresh=Mock(),
        )

        MainWindow.refresh_from_configured_provider(window)

        self.assertTrue(window.pending_provider_refresh)
        self.assertFalse(window.pending_results_freshness)
        self.assertEqual(window.initial_results_freshness_batches_remaining, 0)
        self.assertFalse(window.results_freshness_visible_only)
        window._set_database_refresh_enabled.assert_called_once_with(False)
        worker.cancel.assert_called_once_with()
        window._start_configured_provider_refresh.assert_not_called()

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_population_preserves_display_sort_key_tooltip_and_status_colour(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        server = DiscoveredServer(
            name="Cached Name",
            server_name="Live Name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            players_current=12,
            players_max=60,
            ping_ms=42,
            online=True,
            status_source="local",
            country_code="DE",
            country_source="battlemetrics",
        )

        populate_browser_table(table, [server])

        self.assertEqual(table.rowCount(), 1)
        self.assertEqual(table.item(0, 2).text(), "Live Name")
        self.assertEqual(table.item(0, 8).text(), "12/60")
        self.assertIsInstance(table.item(0, 8), SortableTableWidgetItem)
        self.assertEqual(table.item(0, 8).sort_value, 12)
        self.assertEqual(table.columnCount(), 18)
        self.assertEqual(table.item(0, 1).data(Qt.UserRole), server.cache_key)
        self.assertIn("Locally validated live name", table.item(0, 1).toolTip())
        self.assertEqual(
            table.item(0, 6).foreground().color().name(),
            STATUS_COLOURS["positive"],
        )
        self.assertTrue(table.isSortingEnabled())

    def test_game_time_uses_a_large_scalable_phase_icon(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        server = DiscoveredServer(
            "Timed",
            "host",
            2302,
            27016,
            game_time="17:07",
            day_acceleration=3,
        )

        populate_browser_table(table, [server])

        self.assertEqual(table.iconSize(), QSize(20, 20))
        self.assertFalse(table.item(0, 16).icon().isNull())
        self.assertEqual(table.item(0, 16).text(), "17:07 · 3×")

    def test_password_protection_has_a_lock_next_to_the_favourite_column(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        server = DiscoveredServer("Locked", "host", 2302, 27016, password=True)

        populate_browser_table(table, [server])

        marker = table.cellWidget(0, BROWSER_FAVOURITE_COLUMN)
        self.assertIsNotNone(marker)

    def test_visible_selection_wins_over_a_stale_current_row(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        first = DiscoveredServer("First", "one", 2302, 27016)
        second = DiscoveredServer("Second", "two", 2302, 27016)
        populate_browser_table(table, [first, second])
        first_row = next(
            row
            for row in range(table.rowCount())
            if table.item(row, 1).data(Qt.UserRole) == first.cache_key
        )
        second_row = 1 - first_row
        table.selectRow(first_row)
        table.setCurrentCell(second_row, 0, QItemSelectionModel.NoUpdate)

        self.assertEqual(selected_browser_cache_key(table), first.cache_key)

    def test_browser_next_actions_require_a_selected_server(self):
        buttons = [QPushButton(), QPushButton(), QPushButton()]
        window = SimpleNamespace(
            browser_promote_button=buttons[0],
            browser_inspect_button=buttons[1],
            browser_launch_button=buttons[2],
            selected_discovered_server=lambda: None,
        )

        MainWindow.update_browser_selection_context(window)

        self.assertFalse(any(button.isEnabled() for button in buttons))
        self.assertEqual(buttons[2].text(), "Launch selected server")

    def test_browser_primary_action_names_the_selected_server(self):
        buttons = [QPushButton(), QPushButton(), QPushButton()]
        selected = DiscoveredServer(
            name="Namalsk Adventure",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
        )
        window = SimpleNamespace(
            browser_promote_button=buttons[0],
            browser_inspect_button=buttons[1],
            browser_launch_button=buttons[2],
            selected_discovered_server=lambda: selected,
        )

        MainWindow.update_browser_selection_context(window)

        self.assertTrue(all(button.isEnabled() for button in buttons))
        self.assertEqual(buttons[2].text(), "Launch Namalsk Adventure")

    def test_browser_primary_action_uses_the_same_locally_validated_name_as_the_row(self):
        button = QPushButton()
        selected = DiscoveredServer(
            name="Provider Name",
            server_name="Locally Validated Name",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            status_source="local",
        )
        window = SimpleNamespace(
            browser_promote_button=QPushButton(),
            browser_inspect_button=QPushButton(),
            browser_launch_button=button,
            selected_discovered_server=lambda: selected,
        )

        MainWindow.update_browser_selection_context(window)

        self.assertEqual(button.text(), "Launch Locally Validated Name")

    def test_missing_mods_do_not_turn_online_status_pill_red(self):
        server = DiscoveredServer(
            name="Online but missing mods",
            host="203.0.113.10",
            game_port=2302,
            query_port=27016,
            online=True,
            status_source="local",
        )
        labels = [Mock() for _ in range(10)]
        card = Mock()
        card.style.return_value = Mock()
        status = labels[1]
        status.style.return_value = Mock()
        mod_status = Mock()
        mod_status.style.return_value = Mock()
        window = SimpleNamespace(
            selected_discovered_server=lambda: server,
            browser_mod_results={},
            browser_detail_card=card,
            browser_detail_eyebrow=labels[0],
            browser_detail_status=status,
            browser_detail_mod_status=mod_status,
            browser_detail_title=labels[2],
            browser_detail_endpoint=labels[3],
            browser_detail_atmosphere=Mock(),
            browser_detail_map=labels[4],
            browser_detail_players=labels[5],
            browser_detail_ping=labels[6],
            browser_detail_context=labels[7],
            browser_detail_truth=labels[8],
            browser_detail_features=labels[9],
            browser_detail_mods=Mock(),
            browser_detail_diagnostics=Mock(),
        )

        MainWindow.update_browser_detail_card(window, server, "3 missing locally")

        card.setProperty.assert_any_call("serverStatus", "offline")
        status.setText.assert_called_once_with("ONLINE")
        status.setProperty.assert_any_call("serverStatus", "ready")
        mod_status.setText.assert_called_once_with("3 MODS MISSING")
        mod_status.setProperty.assert_any_call("serverStatus", "offline")
        mod_status.setVisible.assert_called_once_with(True)

    @patch("wolflauncher.server_browser_feature.local_enrichment_due", return_value=True)
    def test_selected_server_check_is_debounced_when_local_data_is_due(self, _due):
        timer = Mock()
        server = DiscoveredServer(
            name="Selected", host="203.0.113.10", game_port=2302, query_port=27016
        )
        window = SimpleNamespace(
            browser_selection_timer=timer,
            selected_discovered_server=lambda: server,
        )

        MainWindow.schedule_selected_discovered_server_check(window)

        timer.stop.assert_called_once_with()
        timer.start.assert_called_once_with()

    @patch("wolflauncher.server_browser_feature.local_enrichment_due", return_value=False)
    def test_selected_server_check_reuses_recent_local_data(self, _due):
        timer = Mock()
        server = DiscoveredServer(
            name="Selected", host="203.0.113.10", game_port=2302, query_port=27016
        )
        window = SimpleNamespace(
            browser_selection_timer=timer,
            selected_discovered_server=lambda: server,
        )

        MainWindow.schedule_selected_discovered_server_check(window)

        timer.stop.assert_called_once_with()
        timer.start.assert_not_called()

    def test_rapid_selection_retains_only_newest_pending_live_check(self):
        newest = DiscoveredServer(
            name="Newest", host="203.0.113.12", game_port=2302, query_port=27016
        )
        window = SimpleNamespace(
            selection_enrichment_workers={"running": Mock()},
            pending_selection_checks={"older": object()},
        )

        MainWindow.start_selected_discovered_enrichment(window, newest)

        self.assertEqual(window.pending_selection_checks, {newest.cache_key: newest})

    @patch("wolflauncher.server_browser_feature.ServerEnrichmentWorker")
    @patch("wolflauncher.server_browser_feature.local_enrichment_due", return_value=True)
    def test_results_freshness_is_bounded_and_runs_in_background(self, _due, worker_class):
        servers = [
            DiscoveredServer(
                name=f"Match {index}",
                host=f"203.0.113.{index + 1}",
                game_port=2302,
                query_port=27016,
            )
            for index in range(12)
        ]
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        populate_browser_table(table, servers)
        table.resize(1000, 220)
        worker = worker_class.return_value
        window = SimpleNamespace(
            browser_servers=list(reversed(servers)),
            browser_table=table,
            results_freshness_worker=None,
            pending_results_freshness=False,
            initial_results_freshness_batches_remaining=0,
            results_freshness_context="",
            results_freshness_attempted_keys=set(),
            selection_enrichment_workers={},
            statusBar=Mock(return_value=Mock()),
            handle_results_freshness_progress=Mock(),
            handle_results_freshness_finished=Mock(),
        )

        MainWindow.schedule_results_freshness_check(window)

        queued = worker_class.call_args.args[0]
        self.assertEqual(len(queued), 6)
        visual_keys = [table.item(row, 1).data(Qt.UserRole) for row in range(6)]
        self.assertEqual([server.cache_key for server in queued], visual_keys)
        self.assertFalse(worker_class.call_args.kwargs["probe_fallbacks"])
        worker.start.assert_called_once_with()
        self.assertIs(window.results_freshness_worker, worker)
        self.assertEqual(
            window.results_freshness_attempted_keys,
            {server.cache_key for server in queued},
        )

        window.results_freshness_worker = None
        MainWindow.schedule_results_freshness_check(window)

        second_batch = worker_class.call_args.args[0]
        self.assertEqual(len(second_batch), 6)
        self.assertEqual(
            window.results_freshness_attempted_keys,
            {server.cache_key for server in servers},
        )

    def test_results_freshness_coalesces_without_cancelling_same_context_batch(self):
        running = Mock()
        running.isRunning.return_value = True
        window = SimpleNamespace(
            browser_servers=[],
            results_freshness_worker=running,
            pending_results_freshness=False,
            initial_results_freshness_batches_remaining=0,
            results_freshness_context="",
            results_freshness_attempted_keys=set(),
        )

        MainWindow.schedule_results_freshness_check(window)

        self.assertTrue(window.pending_results_freshness)
        running.cancel.assert_not_called()

    def test_results_freshness_cancels_running_batch_when_search_changes(self):
        running = Mock()
        running.isRunning.return_value = True
        window = SimpleNamespace(
            browser_servers=[],
            browser_search=Mock(text=Mock(return_value="new dawn")),
            results_freshness_worker=running,
            pending_results_freshness=False,
            initial_results_freshness_batches_remaining=0,
            results_freshness_context="new hope",
            results_freshness_attempted_keys={"old-result"},
        )

        MainWindow.schedule_results_freshness_check(window)

        self.assertTrue(window.pending_results_freshness)
        self.assertEqual(window.results_freshness_context, "new dawn")
        self.assertEqual(window.results_freshness_attempted_keys, set())
        running.cancel.assert_called_once_with()

    @patch("wolflauncher.server_browser_feature.QTimer.singleShot")
    def test_results_freshness_completion_schedules_the_next_batch_without_rebuild(
        self, single_shot
    ):
        window = SimpleNamespace(
            results_freshness_worker=Mock(),
            pending_results_freshness=False,
            pending_provider_refresh=False,
            initial_results_freshness_batches_remaining=0,
            refresh_server_browser=Mock(),
            schedule_selected_discovered_server_check=Mock(),
            schedule_results_freshness_check=Mock(),
        )

        MainWindow.handle_results_freshness_finished(window)

        self.assertIsNone(window.results_freshness_worker)
        window.refresh_server_browser.assert_not_called()
        window.schedule_selected_discovered_server_check.assert_not_called()
        single_shot.assert_called_once_with(0, window.schedule_results_freshness_check)

    @patch("wolflauncher.server_browser_feature.QTimer.singleShot")
    def test_results_freshness_completion_starts_deferred_provider_refresh(self, single_shot):
        window = SimpleNamespace(
            results_freshness_worker=Mock(),
            pending_provider_refresh=True,
            pending_results_freshness=True,
            initial_results_freshness_batches_remaining=3,
            results_freshness_visible_only=True,
            results_freshness_attempted_keys={"checked"},
            _run_pending_configured_provider_refresh=Mock(),
        )

        MainWindow.handle_results_freshness_finished(window)

        self.assertIsNone(window.results_freshness_worker)
        self.assertFalse(window.pending_results_freshness)
        self.assertEqual(window.initial_results_freshness_batches_remaining, 0)
        self.assertFalse(window.results_freshness_visible_only)
        self.assertEqual(window.results_freshness_attempted_keys, set())
        single_shot.assert_called_once_with(0, window._run_pending_configured_provider_refresh)

    @patch("wolflauncher.server_browser_feature.QTimer.singleShot")
    def test_initial_freshness_completion_continues_until_four_batches(self, single_shot):
        window = SimpleNamespace(
            results_freshness_worker=Mock(),
            pending_results_freshness=False,
            initial_results_freshness_batches_remaining=4,
            results_freshness_attempted_keys={"checked"},
            statusBar=Mock(return_value=Mock()),
            continue_initial_results_freshness_check=Mock(),
            schedule_selected_discovered_server_check=Mock(),
        )

        MainWindow.handle_results_freshness_finished(window)

        self.assertIsNone(window.results_freshness_worker)
        self.assertEqual(window.initial_results_freshness_batches_remaining, 3)
        self.assertEqual(window.results_freshness_attempted_keys, {"checked"})
        single_shot.assert_called_once_with(0, window.continue_initial_results_freshness_check)
        window.schedule_selected_discovered_server_check.assert_not_called()

    def test_initial_freshness_completion_stops_after_fourth_batch(self):
        window = SimpleNamespace(
            results_freshness_worker=Mock(),
            pending_results_freshness=False,
            initial_results_freshness_batches_remaining=1,
            results_freshness_attempted_keys={"checked"},
            statusBar=Mock(return_value=Mock()),
            schedule_selected_discovered_server_check=Mock(),
        )

        MainWindow.handle_results_freshness_finished(window)

        self.assertEqual(window.initial_results_freshness_batches_remaining, 0)
        self.assertEqual(window.results_freshness_attempted_keys, set())
        window.schedule_selected_discovered_server_check.assert_called_once_with()

    def test_first_two_search_characters_do_not_rebuild_the_table(self):
        timer = Mock()
        summary = Mock()
        window = SimpleNamespace(browser_filter_timer=timer, browser_summary=summary)

        MainWindow.schedule_browser_search_refresh(window, "n")
        MainWindow.schedule_browser_search_refresh(window, "ne")

        self.assertEqual(timer.stop.call_count, 2)
        timer.start.assert_not_called()
        summary.setText.assert_called_with("Type at least 3 characters to search servers.")

    def test_three_search_characters_schedule_one_debounced_rebuild(self):
        timer = Mock()
        window = SimpleNamespace(browser_filter_timer=timer, browser_summary=Mock())

        MainWindow.schedule_browser_search_refresh(window, "new")

        timer.stop.assert_called_once_with()
        timer.start.assert_called_once_with()

    def test_scrolling_restarts_the_viewport_freshness_debounce(self):
        timer = Mock()
        window = SimpleNamespace(browser_scroll_timer=timer)

        MainWindow.schedule_browser_scroll_freshness_check(window, 12)

        timer.stop.assert_called_once_with()
        timer.start.assert_called_once_with()

    @patch.object(ServerBrowserMixin, "_schedule_results_freshness_check")
    def test_scrolled_freshness_is_four_visible_only_batches(self, schedule):
        window = SimpleNamespace()

        MainWindow.start_browser_scroll_freshness_check(window)

        self.assertEqual(window.initial_results_freshness_batches_remaining, 4)
        self.assertTrue(window.results_freshness_visible_only)
        schedule.assert_called_once_with(window)

    def test_enrichment_identity_collision_is_rolled_back_and_skipped(self):
        connection = Mock()
        server = DiscoveredServer("Conflict", "203.0.113.20", 2302, 27016)

        with patch(
            "wolflauncher.app.server_cache.replace_server_key",
            side_effect=ValueError("Corrected endpoint belongs to another stable server."),
        ):
            persisted = persist_enriched_server(connection, "old-key", server)

        self.assertFalse(persisted)
        connection.rollback.assert_called_once_with()

    def test_enrichment_ignores_closed_cache_during_shutdown(self):
        connection = Mock()
        server = DiscoveredServer("Updated", "203.0.113.10", 2302, 27016)

        with patch(
            "wolflauncher.app.server_cache.replace_server_key",
            side_effect=sqlite3.ProgrammingError("Cannot operate on a closed database."),
        ):
            persisted = persist_enriched_server(connection, "old-key", server)

        self.assertFalse(persisted)
        connection.rollback.assert_not_called()

    @patch("wolflauncher.server_browser_feature.QTimer.singleShot")
    def test_opening_browser_schedules_background_refresh_without_reloading_view(self, single_shot):
        window = SimpleNamespace(
            server_browser_tab_index=1,
            mods_tab_index=2,
            active_main_tab_index=0,
            schedule_selected_discovered_server_check=Mock(),
            schedule_initial_results_freshness_check=Mock(),
            maybe_auto_refresh_configured_provider=Mock(),
            refresh_server_browser=Mock(),
        )

        MainWindow.handle_main_tab_changed(window, 1)

        window.schedule_selected_discovered_server_check.assert_called_once_with()
        window.refresh_server_browser.assert_not_called()
        self.assertEqual(
            single_shot.call_args_list,
            [
                call(0, window.schedule_initial_results_freshness_check),
                call(0, window.maybe_auto_refresh_configured_provider),
            ],
        )
        self.assertEqual(window.active_main_tab_index, 1)

    def test_required_mods_sort_handles_known_and_unknown_counts(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        unknown = DiscoveredServer(
            name="Unknown mods", host="203.0.113.11", game_port=2302, query_port=27016
        )
        known = DiscoveredServer(
            name="Known mods",
            host="203.0.113.12",
            game_port=2302,
            query_port=27016,
            required_mod_count=17,
        )

        populate_browser_table(table, [unknown, known])
        table.sortItems(12, Qt.AscendingOrder)

        self.assertEqual(table.item(0, 12).text(), "17")
        self.assertEqual(table.item(1, 12).text(), "–")

    def test_detailed_view_keeps_internal_live_name_hidden(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        checkbox = QCheckBox()
        checkbox.setChecked(True)
        window = SimpleNamespace(
            browser_table=table,
            browser_detailed_columns=checkbox,
        )

        MainWindow.configure_browser_columns(window, True)

        self.assertTrue(table.isColumnHidden(2))
        self.assertFalse(table.isColumnHidden(3))

    def test_compact_columns_follow_the_requested_scan_order(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        checkbox = QCheckBox()
        window = SimpleNamespace(
            browser_table=table,
            browser_detailed_columns=checkbox,
        )

        MainWindow.configure_browser_columns(window, False)

        header = table.horizontalHeader()
        self.assertEqual(header.sectionResizeMode(1), QHeaderView.Stretch)
        self.assertEqual(header.sectionResizeMode(BROWSER_FAVOURITE_COLUMN), QHeaderView.Fixed)
        self.assertTrue(table.isColumnHidden(BROWSER_PASSWORD_COLUMN))
        self.assertEqual(table.columnWidth(BROWSER_FAVOURITE_COLUMN), 74)
        self.assertEqual(
            [header.logicalIndex(index) for index in range(10)],
            [0, 1, 6, 7, 16, 8, 9, 11, 12, 2],
        )

    def test_population_replaces_existing_rows_and_keeps_missing_ping_guidance(self):
        table = QTableWidget(3, BROWSER_COLUMN_COUNT)
        server = DiscoveredServer(
            name="Offline Server",
            host="203.0.113.11",
            game_port=2302,
            query_port=27016,
            status_source="local",
        )

        populate_browser_table(table, [server])

        self.assertEqual(table.rowCount(), 1)
        self.assertIn("when you select", table.item(0, 9).toolTip())
        self.assertEqual(
            table.item(0, 6).foreground().color().name(),
            STATUS_COLOURS["negative"],
        )

    def test_single_enrichment_updates_only_the_selected_table_row(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        original = DiscoveredServer(
            name="Selected", host="203.0.113.11", game_port=2302, query_port=27016
        )
        neighbour = DiscoveredServer(
            name="Neighbour", host="203.0.113.12", game_port=2302, query_port=27016
        )
        populate_browser_table(table, [original, neighbour])
        neighbour_item = (
            table.item(0, 1) if table.item(0, 1).text() == "Neighbour" else table.item(1, 1)
        )
        enriched = DiscoveredServer(
            name="Selected",
            host="203.0.113.11",
            game_port=2302,
            query_port=27016,
            online=True,
            status_source="local",
            ping_ms=42,
        )

        self.assertTrue(update_browser_table_row(table, original.cache_key, enriched))

        self.assertEqual(table.rowCount(), 2)
        self.assertEqual(neighbour_item.text(), "Neighbour")
        selected_items = [
            table.item(row, 1)
            for row in range(table.rowCount())
            if table.item(row, 1).data(Qt.UserRole) == enriched.cache_key
        ]
        self.assertEqual(len(selected_items), 1)
        selected_row = selected_items[0].row()
        self.assertEqual(table.item(selected_row, 6).text(), "ONLINE")
        self.assertEqual(table.item(selected_row, 9).text(), "42ms")

    def test_enrichment_preserves_a_favourite_star(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        original = DiscoveredServer(
            name="Selected", host="203.0.113.11", game_port=2302, query_port=27016
        )
        populate_browser_table(
            table,
            [original],
            {(original.host, original.game_port, original.query_port)},
        )

        enriched = DiscoveredServer(
            name="Selected",
            host="203.0.113.11",
            game_port=2302,
            query_port=27016,
            online=True,
            status_source="local",
        )

        self.assertTrue(update_browser_table_row(table, original.cache_key, enriched))
        self.assertEqual(table.item(0, BROWSER_FAVOURITE_COLUMN).text(), "")

    def test_local_mod_preview_replaces_only_the_matching_mods_cell(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        selected = DiscoveredServer(
            name="Selected", host="203.0.113.11", game_port=2302, query_port=27016
        )
        populate_browser_table(table, [selected])

        self.assertTrue(
            update_browser_mod_cell(
                table,
                selected.cache_key,
                "3 MISSING",
                "Launch will run pre-flight.",
                STATUS_COLOURS["negative"],
            )
        )

        self.assertEqual(table.item(0, 12).text(), "3 MISSING")
        self.assertIn("pre-flight", table.item(0, 12).toolTip())

    def test_background_mod_preview_does_not_steal_visible_selection(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        selected = DiscoveredServer("Selected", "one", 2302, 27016)
        background = DiscoveredServer("Background", "two", 2302, 27016)
        populate_browser_table(table, [selected, background])
        selected_row = next(
            row
            for row in range(table.rowCount())
            if table.item(row, 1).data(Qt.UserRole) == selected.cache_key
        )
        table.selectRow(selected_row)

        update_browser_mod_cell(
            table,
            background.cache_key,
            "3 MISSING",
            "Background preview.",
            STATUS_COLOURS["negative"],
        )

        current = table.item(table.currentRow(), 1)
        self.assertEqual(current.data(Qt.UserRole), selected.cache_key)

    def test_dynamic_mod_text_yields_name_width_without_horizontal_overflow(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        table.resize(1200, 300)
        table.setHorizontalHeaderLabels(
            [
                "Server Name",
                "Live Name",
                "Host",
                "Game Port",
                "Query Port",
                "Status",
                "Map",
                "Players",
                "Ping",
                "Version",
                "Features",
                "Mods",
                "Last Checked",
                "Last Seen",
                "Source",
                "Game Time",
            ]
        )
        server = DiscoveredServer(
            "A deliberately long server name that should flex",
            "one",
            2302,
            27016,
            map_name="chernarusplus",
            players_current=12,
            players_max=60,
            ping_ms=42,
            modded=True,
            game_time="13:26",
        )
        populate_browser_table(table, [server])
        window = SimpleNamespace(
            browser_table=table,
            browser_detailed_columns=QCheckBox(),
        )
        MainWindow.configure_browser_columns(window, False)
        table.show()
        self.app.processEvents()

        update_browser_mod_cell(
            table,
            server.cache_key,
            "31 MISSING",
            "Missing mods.",
            STATUS_COLOURS["negative"],
        )
        self.app.processEvents()

        self.assertEqual(table.horizontalScrollBar().maximum(), 0)

    def test_ping_colours_follow_dayz_warning_thresholds(self):
        table = QTableWidget(0, BROWSER_COLUMN_COUNT)
        servers = [
            DiscoveredServer(
                name="Warning", host="one", game_port=2302, query_port=27016, ping_ms=200
            ),
            DiscoveredServer(
                name="Critical", host="two", game_port=2302, query_port=27016, ping_ms=250
            ),
        ]

        populate_browser_table(table, servers)

        self.assertEqual(
            table.item(0, 9).foreground().color().name(),
            STATUS_COLOURS["warning"],
        )
        self.assertEqual(
            table.item(1, 9).foreground().color().name(),
            STATUS_COLOURS["negative"],
        )


if __name__ == "__main__":
    unittest.main()
