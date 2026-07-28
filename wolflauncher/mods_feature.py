from dataclasses import replace

from PySide6.QtCore import QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import server_cache
from .launch_preflight import (
    matching_mod_result,
    usable_mod_result,
)
from .mod_presenter import (
    mod_description_preview,
    mod_detail_status,
    mod_file_size,
    mod_inspector_scale,
    mod_inspector_type_scale,
    mod_readiness_text,
    mod_row,
    mod_server_heading,
    mod_summary_text,
)
from .models import Server
from .mods import (
    ModCheckResult,
    apply_workshop_item_states,
    format_missing_workshop_links,
    format_mod_check_report,
)
from .platform_detection import (
    SteamInstall,
    best_install,
    install_label,
)
from .settings import (
    server_key,
)
from .thumbnail_safety import (
    MAX_THUMBNAIL_BYTES,
    is_safe_thumbnail_content_type,
    is_safe_thumbnail_dimensions,
    is_safe_thumbnail_url,
    normalize_thumbnail_url,
)
from .theme import (
    configure_data_table,
    monospace_font,
    set_ui_role,
    theme_icon,
)
from .ui_sections import set_disclosure_state
from .workers import (
    ModWorker,
)
from .workshop_subscription import (
    ITEM_STATE_DOWNLOADING,
    current_workshop_item,
    launch_block_reason,
    workshop_recovery_state,
)


class ModsFeatureMixin:
    def _build_mods_tab(self) -> QWidget:
        widget = QWidget()
        set_ui_role(widget, "workspace")
        layout = QVBoxLayout(widget)

        self.mod_server_title = QLabel("No server selected")
        set_ui_role(self.mod_server_title, "summary")
        layout.addWidget(self.mod_server_title)
        self.mod_readiness = QLabel(
            "Choose a server from Favourite Servers or Server Browser to inspect its mods."
        )
        set_ui_role(self.mod_readiness, "metadata")
        layout.addWidget(self.mod_readiness)
        self.mod_summary = QLabel("")
        set_ui_role(self.mod_summary, "metadata")
        layout.addWidget(self.mod_summary)

        buttons = QHBoxLayout()
        check = QPushButton("Recheck selected server mods")
        check.setIcon(theme_icon("recheck"))
        set_ui_role(check, "accent")
        check.clicked.connect(lambda _checked=False: self.check_selected_server_mods(force=True))
        native_preview = QPushButton("Native launch preview")
        native_preview.clicked.connect(self.launch_execution.preview_native)
        copy_report = QPushButton("Copy mod report")
        copy_report.clicked.connect(self.copy_mod_check_report)
        copy_missing = QPushButton("Copy missing links")
        copy_missing.clicked.connect(self.copy_missing_workshop_links)
        open_selected = QPushButton("Open selected Workshop page")
        open_selected.clicked.connect(self.open_selected_workshop_page)
        open_missing = QPushButton("Open missing Workshop pages")
        open_missing.clicked.connect(self.open_missing_workshop_pages)
        self.subscribe_missing_button = QPushButton("Install/update missing mods")
        self.subscribe_missing_button.clicked.connect(self.subscribe_missing_workshop_mods)
        self.subscribe_missing_button.setEnabled(False)
        self.force_update_button = QPushButton("Force Steam update selected mod")
        self.force_update_button.clicked.connect(self.force_update_selected_mod)
        self.force_update_button.setEnabled(False)
        buttons.addWidget(check)
        self.mod_filter = QComboBox()
        self.mod_filter.addItems(["All mods", "Missing only", "Installed only"])
        self.mod_filter.currentTextChanged.connect(self.apply_mod_filter)
        buttons.addWidget(self.subscribe_missing_button)
        buttons.addWidget(self.force_update_button)
        buttons.addStretch(1)
        buttons.addWidget(QLabel("Filter"))
        buttons.addWidget(self.mod_filter)
        layout.addLayout(buttons)

        self.mods_advanced_toggle = QPushButton()
        self.mods_advanced_toggle.setCheckable(True)
        advanced_toggle_row = QHBoxLayout()
        advanced_toggle_row.addWidget(self.mods_advanced_toggle)
        advanced_toggle_row.addStretch(1)
        self.mods_back_to_browser_button = QPushButton("Back to Server Browser ←")
        self.mods_back_to_browser_button.clicked.connect(self.back_to_server_browser)
        advanced_toggle_row.addWidget(self.mods_back_to_browser_button)
        self.mods_launch_button = QPushButton("Launch selected server")
        self.mods_launch_button.setIcon(theme_icon("launch"))
        set_ui_role(self.mods_launch_button, "primary")
        self.mods_launch_button.clicked.connect(self.launch_selected)
        advanced_toggle_row.addWidget(self.mods_launch_button)

        self.mods_advanced_panel = QWidget()
        advanced_layout = QHBoxLayout(self.mods_advanced_panel)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.addWidget(native_preview)
        advanced_layout.addWidget(copy_report)
        advanced_layout.addWidget(copy_missing)
        advanced_layout.addWidget(open_selected)
        advanced_layout.addWidget(open_missing)
        advanced_layout.addStretch(1)

        self.mods_advanced_toggle.toggled.connect(
            lambda expanded: set_disclosure_state(
                self.mods_advanced_toggle,
                self.mods_advanced_panel,
                "advanced mod tools",
                expanded,
            )
        )
        set_disclosure_state(
            self.mods_advanced_toggle,
            self.mods_advanced_panel,
            "advanced mod tools",
            False,
        )

        self.mods_table = QTableWidget(0, 4)
        self.mods_table.setAccessibleName("Required Workshop mods")
        self.mods_table.setAccessibleDescription(
            "Workshop mods required by the selected DayZ server and their readiness."
        )
        self.mods_table.setHorizontalHeaderLabels(
            [
                "Status",
                "Name",
                "Workshop ID",
                "Size",
            ]
        )
        self.mods_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.mods_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.mods_table.setSortingEnabled(True)
        self.mods_table.setTabKeyNavigation(False)
        configure_data_table(self.mods_table)
        self.mods_table.itemActivated.connect(
            lambda item: self.handle_mod_double_clicked(item.row(), item.column())
        )
        self.mods_table.itemSelectionChanged.connect(self.update_mod_detail_card)
        self.mods_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mods_table.customContextMenuRequested.connect(self.show_mod_context_menu)
        self.mod_detail_card = QFrame()
        set_ui_role(self.mod_detail_card, "modDetail")
        self.mod_detail_card.setProperty("modStatus", "warning")
        self.mod_detail_base_point_size = max(8.0, QApplication.font().pointSizeF())
        detail_layout = QVBoxLayout(self.mod_detail_card)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(10)
        self.mod_detail_thumbnail = QLabel("No preview")
        self.mod_detail_thumbnail.setAlignment(Qt.AlignCenter)
        self.mod_detail_thumbnail.setFixedSize(320, 180)
        set_ui_role(self.mod_detail_thumbnail, "modThumbnail")
        thumbnail_row = QHBoxLayout()
        thumbnail_row.addStretch(1)
        thumbnail_row.addWidget(self.mod_detail_thumbnail)
        thumbnail_row.addStretch(1)
        detail_layout.addLayout(thumbnail_row)
        self.mod_detail_title = QLabel("Select a mod to see its Workshop details")
        set_ui_role(self.mod_detail_title, "cardTitle")
        self.mod_detail_description = QLabel(
            "Descriptions and preview images are supplied by the mod's Workshop page."
        )
        self.mod_detail_description.setWordWrap(True)
        set_ui_role(self.mod_detail_description, "metadata")
        self.mod_detail_metadata = QLabel("")
        set_ui_role(self.mod_detail_metadata, "metadata")
        detail_layout.addWidget(self.mod_detail_title)
        detail_layout.addWidget(self.mod_detail_description)
        detail_layout.addWidget(self.mod_detail_metadata)
        detail_layout.addStretch(1)
        self.mod_detail_open_button = QPushButton("Open Workshop page")
        self.mod_detail_open_button.setEnabled(False)
        self.mod_detail_open_button.clicked.connect(self.open_selected_workshop_page)
        open_row = QHBoxLayout()
        open_row.addStretch(1)
        open_row.addWidget(self.mod_detail_open_button)
        detail_layout.addLayout(open_row)

        self.mods_splitter = QSplitter(Qt.Horizontal)
        self.mods_splitter.setObjectName("modsSplitter")
        self.mods_splitter.setHandleWidth(10)
        self.mods_splitter.setChildrenCollapsible(False)
        self.mods_splitter.addWidget(self.mods_table)
        self.mods_splitter.addWidget(self.mod_detail_card)
        self.mods_splitter.setStretchFactor(0, 2)
        self.mods_splitter.setStretchFactor(1, 1)
        self.mods_splitter.setSizes([850, 450])
        self.mods_splitter.splitterMoved.connect(
            lambda _position, _index: self.resize_mod_detail_card()
        )
        layout.addWidget(self.mods_splitter, 1)
        self.mod_thumbnail_manager = QNetworkAccessManager(self)
        self.mod_thumbnail_manager.finished.connect(self.finish_mod_thumbnail_load)
        self.mod_thumbnail_url = ""
        self.resize_mod_detail_card()
        layout.addLayout(advanced_toggle_row)
        layout.addWidget(self.mods_advanced_panel)
        QWidget.setTabOrder(check, self.subscribe_missing_button)
        QWidget.setTabOrder(self.subscribe_missing_button, self.force_update_button)
        QWidget.setTabOrder(self.force_update_button, self.mod_filter)
        QWidget.setTabOrder(self.mod_filter, self.mods_table)
        QWidget.setTabOrder(self.mods_table, self.mods_advanced_toggle)
        QWidget.setTabOrder(self.mods_advanced_toggle, self.mods_back_to_browser_button)
        QWidget.setTabOrder(self.mods_back_to_browser_button, self.mods_launch_button)
        self.update_launch_button_text()
        return widget

    def check_initial_server_mods(self):
        if self.servers and self.table.currentRow() < 0:
            last_row = self.saved_selected_row()
            row = last_row if 0 <= last_row < len(self.servers) else 0
            self.table.selectRow(row)
        self.check_selected_server_mods(silent=True)

    def handle_server_selection_changed(self):
        self.active_discovered_server = None
        self.active_discovered_cache_key = ""
        self._sync_curated_card_selection()
        self.update_launch_button_text()
        if not hasattr(self, "mod_summary"):
            return
        self.check_selected_server_mods(silent=True)

    def check_selected_server_mods(self, silent: bool = False, force: bool = False):
        server = self.active_server_context()
        if not server:
            if not silent:
                QMessageBox.warning(self, "No server selected", "Select a server first.")
            return

        self.check_server_mods(server, silent=silent, force=force)

    def check_server_mods_for_row(self, row: int, silent: bool = False, force: bool = False):
        if row < 0 or row >= len(self.servers):
            return

        server = self.servers[row]
        self.check_server_mods(server, silent=silent, force=force)

    def check_server_mods(self, server: Server, silent: bool = False, force: bool = False):
        if not hasattr(self, "mod_summary") or not hasattr(self, "mods_table"):
            return
        selected_key = server_key(server)
        self.mod_server_title.setText(
            f"Required mods for {server.name}  ·  {server.connect_target}"
        )
        self.mod_readiness.setText("Checking required-mod readiness…")
        self.subscribe_missing_button.setEnabled(False)
        self.force_update_button.setEnabled(False)
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
        workshop_dir = install.workshop_dir if install else None
        cached_mod_result = usable_mod_result(server, self.last_mod_result, workshop_dir)
        if not force and cached_mod_result:
            if self.mods_table.rowCount() == 0:
                self.display_mods_result(cached_mod_result)
            self.update_workshop_recovery_state(cached_mod_result, install)
            return

        if self.mod_worker and self.mod_worker.isRunning():
            if self.active_mod_server_key != selected_key:
                self.pending_mod_server = server
                self.mod_summary.setText(
                    f"Queued mod check for {server.name}; finishing the current server check first."
                )
            return

        steam_context = self.mod_check_steam_context(install)
        if not workshop_dir:
            self.last_mod_result = None
            self.workshop_recovery_ids = ()
            self.mod_summary.setText(
                f"Workshop folder not detected for {steam_context or 'the current launch mode'}. "
                "Open Settings health to check the selected Steam install."
            )
            self.mods_table.setRowCount(0)
            if not silent:
                QMessageBox.warning(
                    self,
                    "Workshop folder not found",
                    "WolfLauncher could not find the DayZ Workshop folder for the current launch mode. Check Settings health.",
                )
            return

        self.mod_summary.setText(f"Checking required mods for {server.name}. {steam_context}.")
        self.workshop_recovery_ids = ()
        self.mods_table.setRowCount(0)
        self.active_mod_server_key = selected_key
        self.pending_mod_check_row = None
        self.pending_mod_server = None
        workshop_install = install if install and install.running else None
        self.mod_worker = ModWorker(
            server, workshop_dir, steam_context, workshop_install=workshop_install
        )
        self.mod_worker.mods_ready.connect(self.update_mods_table)
        self.mod_worker.finished.connect(self.handle_mod_worker_finished)
        self.mod_worker.start()

    def update_mods_table(self, result: ModCheckResult):
        self.active_mod_server_key = ""
        current_server = self.active_server_context()
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
        workshop_dir = install.workshop_dir if install else None
        if not current_server:
            return
        if not matching_mod_result(current_server, result, workshop_dir):
            self.pending_mod_server = current_server
            return

        self.last_mod_result = result
        self.update_discovered_required_mod_count(result)
        self.display_mods_result(result)
        self.update_workshop_recovery_state(result, install)

    def update_discovered_required_mod_count(self, result: ModCheckResult):
        cache_key = self.active_discovered_cache_key
        if not result.ok or not cache_key:
            return
        discovered = server_cache.get_server(self.server_cache, cache_key)
        if not discovered or server_key(result.server) != server_key(
            self.discovered_server_context(discovered)
        ):
            return
        count = len(result.required_mods)
        if discovered.required_mod_count == count:
            return
        server_cache.upsert_server(self.server_cache, replace(discovered, required_mod_count=count))
        self.refresh_server_browser()

    def handle_mod_worker_finished(self):
        self.mod_worker = None
        self._check_pending_server_mods()
        self.maybe_launch_after_workshop_download()

    def update_workshop_recovery_state(self, result: ModCheckResult, install: SteamInstall | None):
        missing_ids = [mod.workshop_id for mod in result.missing_mods] if result.ok else []
        recovery = workshop_recovery_state(install, missing_ids)
        self.workshop_recovery_ids = recovery.item_ids
        if recovery.active:
            count = len(recovery.item_ids)
            noun = "item" if count == 1 else "items"
            self.mod_readiness.setText(
                f"Steam may still be downloading {count} required "
                f"Workshop {noun} from an earlier session. Check Steam Downloads; WolfLauncher "
                "will recheck when you use Recheck mods."
            )

    def display_mods_result(self, result: ModCheckResult):
        self.mods_table.setSortingEnabled(False)
        self.mod_server_title.setText(mod_server_heading(result))
        self.mod_readiness.setText(mod_readiness_text(result))
        self.mod_summary.setText(mod_summary_text(result))
        self.mod_summary.setToolTip("")
        missing_count = len(result.missing_mods) if result.ok else 0
        self.subscribe_missing_button.setEnabled(missing_count > 0)
        self.subscribe_missing_button.setText(
            f"Resolve {missing_count} required mod{'s' if missing_count != 1 else ''}"
            if missing_count
            else "Install/update required mods"
        )
        self.force_update_button.setEnabled(False)
        if not result.ok:
            self.mods_table.setRowCount(0)
            self.mods_table.setSortingEnabled(True)
            return

        required = result.required_mods
        self.mods_table.setRowCount(len(required))
        for row, mod in enumerate(required):
            row_data = mod_row(mod)
            for column, value in enumerate(row_data.values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, row_data.workshop_id)
                if column in {2, 3}:
                    item.setFont(monospace_font())
                if column in {0, 2, 3}:
                    item.setTextAlignment(Qt.AlignCenter)
                if column == 0:
                    item.setForeground(QColor(row_data.status_colour))
                self.mods_table.setItem(row, column, item)
        self.mods_table.resizeColumnsToContents()
        self.mods_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.mods_table.setSortingEnabled(True)
        self.mods_table.sortItems(0, Qt.DescendingOrder)
        self.apply_mod_filter()
        if self.mods_table.rowCount() > 0:
            self.mods_table.selectRow(0)

    def selected_required_mod(self):
        result = self.last_mod_result
        if not result or not result.ok:
            return None
        row = self.mods_table.currentRow()
        workshop_id = self._mods_cell(row, 2) if row >= 0 else ""
        return next(
            (mod for mod in result.required_mods if mod.workshop_id == workshop_id),
            None,
        )

    def update_mod_detail_card(self):
        if not hasattr(self, "mod_detail_card"):
            return
        mod = self.selected_required_mod()
        if hasattr(self, "force_update_button"):
            self.force_update_button.setEnabled(mod is not None)
        if mod is None:
            self._set_mod_detail_status("warning")
            self.mod_detail_title.setText("Select a mod to see its Workshop details")
            self.mod_detail_description.setText(
                "Descriptions and preview images are supplied by the mod's Workshop page."
            )
            self.mod_detail_metadata.setText("")
            self.mod_detail_open_button.setEnabled(False)
            self.mod_detail_thumbnail.setPixmap(QPixmap())
            self.mod_detail_thumbnail.setText("No preview")
            self.mod_thumbnail_url = ""
            return
        self._set_mod_detail_status(mod_detail_status(mod))
        self.mod_detail_title.setText(mod.name or mod.installed_name or "Unknown mod")
        self.mod_detail_description.setText(mod_description_preview(mod, limit=900))
        self.mod_detail_description.setToolTip("")
        status = mod_row(mod).values[0].lstrip("✓✗!↻… ")
        self.mod_detail_metadata.setText(
            f"Workshop {mod.workshop_id}  ·  {mod_file_size(mod)}  ·  {status}"
        )
        self.mod_detail_open_button.setEnabled(bool(mod.workshop_url))
        self.load_mod_thumbnail(mod.workshop_preview_url)

    def _set_mod_detail_status(self, status: str):
        self.mod_detail_card.setProperty("modStatus", status)
        self.mod_detail_card.style().unpolish(self.mod_detail_card)
        self.mod_detail_card.style().polish(self.mod_detail_card)

    def load_mod_thumbnail(self, url: str):
        normalized_url = normalize_thumbnail_url(url)
        self.mod_thumbnail_url = normalized_url if is_safe_thumbnail_url(normalized_url) else ""
        self.mod_detail_thumbnail.setPixmap(QPixmap())
        if not self.mod_thumbnail_url:
            self.mod_detail_thumbnail.setText("No preview")
            return
        self.mod_detail_thumbnail.setText("Loading…")
        request = QNetworkRequest(QUrl(self.mod_thumbnail_url))
        reply = self.mod_thumbnail_manager.get(request)
        reply.downloadProgress.connect(
            lambda received, _total, active_reply=reply: self._abort_oversize_thumbnail(
                active_reply, received
            )
        )

    @staticmethod
    def _abort_oversize_thumbnail(reply: QNetworkReply, received: int) -> None:
        if received > MAX_THUMBNAIL_BYTES:
            reply.abort()

    def resize_mod_detail_card(self):
        if not hasattr(self, "mod_detail_card"):
            return
        panel_width = self.mod_detail_card.width()
        if panel_width < 100:
            panel_width = round(self.width() * 0.34)
        media_scale = mod_inspector_scale(self.height())
        type_scale = mod_inspector_type_scale(self.height())
        thumbnail_width = max(220, min(round(360 * media_scale), panel_width - 28))
        thumbnail_height = round(thumbnail_width * 9 / 16)
        self.mod_detail_thumbnail.setFixedSize(thumbnail_width, thumbnail_height)
        base_size = self.mod_detail_base_point_size
        for widget, multiplier in (
            (self.mod_detail_title, 1.12),
            (self.mod_detail_description, 1.0),
            (self.mod_detail_metadata, 0.95),
            (self.mod_detail_open_button, 1.0),
        ):
            font = widget.font()
            font.setPointSizeF(base_size * type_scale * multiplier)
            widget.setFont(font)

    def finish_mod_thumbnail_load(self, reply: QNetworkReply):
        try:
            if reply.url().toString() != self.mod_thumbnail_url:
                return
            pixmap = QPixmap()
            content_type = reply.header(QNetworkRequest.ContentTypeHeader) or ""
            payload = bytes(reply.readAll())
            if (
                reply.error() == QNetworkReply.NoError
                and len(payload) <= MAX_THUMBNAIL_BYTES
                and is_safe_thumbnail_content_type(str(content_type))
            ):
                pixmap.loadFromData(payload)
                if not is_safe_thumbnail_dimensions(pixmap.width(), pixmap.height()):
                    pixmap = QPixmap()
            if pixmap.isNull():
                self.mod_detail_thumbnail.setText("Preview unavailable")
                return
            self.mod_detail_thumbnail.setText("")
            self.mod_detail_thumbnail.setPixmap(
                pixmap.scaled(
                    self.mod_detail_thumbnail.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        finally:
            reply.deleteLater()

    def mod_check_steam_context(self, install: SteamInstall | None) -> str:
        if not install:
            return "Steam install not detected"
        if self.launch_engine_key() == "native":
            return f"Selected Steam install: {install_label(install)}"
        return f"Auto Steam install: {install_label(install)}"

    def _check_pending_server_mods(self):
        if self.mod_worker and self.mod_worker.isRunning():
            return
        pending_server = getattr(self, "pending_mod_server", None)
        if pending_server is not None:
            self.pending_mod_server = None
            self.check_server_mods(pending_server, silent=True)
            return
        if self.pending_mod_check_row is None:
            return
        row = self.pending_mod_check_row
        self.pending_mod_check_row = None
        self.check_server_mods_for_row(row, silent=True)

    def apply_mod_filter(self):
        mode = self.mod_filter.currentText() if hasattr(self, "mod_filter") else "All mods"
        for row in range(self.mods_table.rowCount()):
            status_item = self.mods_table.item(row, 0)
            status = status_item.text() if status_item else ""
            hide = False
            if mode == "Missing only":
                hide = "Missing" not in status
            elif mode == "Installed only":
                hide = "Installed" not in status
            self.mods_table.setRowHidden(row, hide)

    def handle_mod_double_clicked(self, row: int, column: int):
        self.open_workshop_page_for_mod_row(row)

    def open_workshop_page_for_mod_row(self, row: int):
        if row < 0:
            return
        mod = self.selected_required_mod()
        url = mod.workshop_url if mod else ""
        if not url:
            workshop_id = self._mods_cell(row, 2)
            if workshop_id:
                url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
        if not url:
            QMessageBox.warning(
                self, "No Workshop URL", "This mod row does not have a Workshop URL."
            )
            return
        QDesktopServices.openUrl(QUrl(url))

    def copy_mod_check_report(self):
        result = self._selected_mod_result()
        if not result:
            QMessageBox.information(
                self,
                "No mod check yet",
                "Check the selected server mods before copying its mod report.",
            )
            return
        self.copy_to_clipboard(format_mod_check_report(result), "Mod check report")

    def copy_missing_workshop_links(self):
        result = self._selected_mod_result(successful=True)
        if not result:
            QMessageBox.information(
                self,
                "No mod check yet",
                "Check the selected server mods successfully before copying missing Workshop links.",
            )
            return
        links = format_missing_workshop_links(result)
        if not links:
            QMessageBox.information(
                self,
                "No missing mods",
                "No missing Workshop links are available from the current mod check.",
            )
            return
        self.copy_to_clipboard(links, "Missing Workshop links")

    def show_mod_context_menu(self, pos: QPoint):
        row = self.mods_table.rowAt(pos.y())
        if row < 0:
            return
        self.mods_table.selectRow(row)
        menu = QMenu(self)
        open_action = QAction("Open Workshop page", self)
        copy_id_action = QAction("Copy Workshop ID", self)
        copy_name_action = QAction("Copy mod name", self)
        copy_url_action = QAction("Copy Workshop URL", self)
        check_update_action = QAction("Check/update this mod", self)
        force_update_action = QAction("Force Steam update", self)
        open_action.triggered.connect(lambda: self.open_workshop_page_for_mod_row(row))
        copy_id_action.triggered.connect(
            lambda: self.copy_to_clipboard(self._mods_cell(row, 2), "Workshop ID")
        )
        copy_name_action.triggered.connect(
            lambda: self.copy_to_clipboard(self._mods_cell(row, 1), "Mod name")
        )
        copy_url_action.triggered.connect(
            lambda: self.copy_to_clipboard(
                (self.selected_required_mod().workshop_url if self.selected_required_mod() else ""),
                "Workshop URL",
            )
        )
        check_update_action.triggered.connect(lambda: self.check_update_mod_row(row))
        force_update_action.triggered.connect(lambda: self.force_update_mod_row(row))
        menu.addAction(check_update_action)
        menu.addAction(force_update_action)
        menu.addSeparator()
        menu.addAction(open_action)
        menu.addAction(copy_id_action)
        menu.addAction(copy_name_action)
        menu.addAction(copy_url_action)
        menu.exec(self.mods_table.viewport().mapToGlobal(pos))

    def _mods_cell(self, row: int, column: int) -> str:
        item = self.mods_table.item(row, column)
        return item.text() if item else ""

    def open_selected_workshop_page(self):
        row = self.mods_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No mod selected", "Select a mod first.")
            return
        self.open_workshop_page_for_mod_row(row)

    def open_missing_workshop_pages(self):
        result = self._selected_mod_result(successful=True)
        if not result:
            QMessageBox.warning(
                self,
                "No mod check yet",
                "Check the selected server mods successfully before opening missing Workshop pages.",
            )
            return
        missing = result.missing_mods
        if not missing:
            QMessageBox.information(self, "Mods ready", "All required mods appear to be ready.")
            return
        if len(missing) > 10:
            reply = QMessageBox.question(
                self,
                "Open many tabs?",
                f"This will open {len(missing)} Workshop pages. Continue?",
            )
            if reply != QMessageBox.Yes:
                return
        for mod in missing:
            QDesktopServices.openUrl(QUrl(mod.workshop_url))

    def subscribe_missing_workshop_mods(self):
        self.workshop_resolution.subscribe_missing_mods()

    def check_update_mod_row(self, row: int):
        self.workshop_resolution.check_update_mod(row)

    def force_update_mod_row(self, row: int):
        self.workshop_resolution.force_update_mod(row)

    def force_update_selected_mod(self):
        row = self.mods_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No mod selected", "Select a mod to force its Steam update.")
            return
        self.force_update_mod_row(row)

    def start_workshop_resolution(self, mods, result, install):
        self.workshop_resolution.start_resolution(mods, result, install)

    def stop_workshop_subscription_monitoring(self):
        self.workshop_subscription_monitor_hidden = True
        if self.workshop_subscription_dialog:
            self.workshop_subscription_dialog.hide()
        self.statusBar().showMessage(
            "Workshop monitoring continues in the background; Steam downloads and launch "
            "readiness are unchanged.",
            8000,
        )

    def update_workshop_subscription_progress(self, snapshots):
        if hasattr(self, "update_mod_progress_rows"):
            self.update_mod_progress_rows(snapshots)
        dialog = self.workshop_subscription_dialog
        if not dialog or self.workshop_subscription_monitor_hidden or not snapshots:
            return
        installed = sum(1 for item in snapshots if item.installed)
        known = [item.percent for item in snapshots if item.percent is not None]
        progress = int(sum(known) / len(known)) if known else int(installed * 100 / len(snapshots))
        active = current_workshop_item(snapshots)
        detail = ""
        if active:
            item_name = self.workshop_subscription_names.get(active.workshop_id, active.workshop_id)
            detail = f" Current item: {item_name}"
            if active.percent is not None:
                detail += f" ({active.percent}%)"
        elif installed < len(snapshots):
            detail = " Waiting for Steam to start the next item."
        dialog.setLabelText(
            f"Steam has installed {installed} of {len(snapshots)} required item(s).{detail}"
        )
        dialog.setValue(progress)

    def update_mod_progress_rows(self, snapshots):
        result = self._selected_mod_result(successful=True)
        if not result:
            return
        apply_workshop_item_states(result, snapshots)
        mods = {mod.workshop_id: mod for mod in result.required_mods}
        for row in range(self.mods_table.rowCount()):
            id_item = self.mods_table.item(row, 2)
            workshop_id = id_item.data(Qt.UserRole) if id_item else ""
            mod = mods.get(str(workshop_id))
            if not mod:
                continue
            row_data = mod_row(mod)
            status_item = self.mods_table.item(row, 0)
            size_item = self.mods_table.item(row, 3)
            if status_item:
                status_item.setText(row_data.values[0])
                status_item.setForeground(QColor(row_data.status_colour))
            if size_item:
                size_item.setText(row_data.values[3])
            snapshot = next(
                (item for item in snapshots if item.workshop_id == mod.workshop_id),
                None,
            )
            percent = snapshot.percent if snapshot else None
            if (
                snapshot
                and snapshot.state & ITEM_STATE_DOWNLOADING
                and percent is not None
                and 0 <= percent < 100
            ):
                progress = self.mods_table.cellWidget(row, 0)
                if not isinstance(progress, QProgressBar):
                    progress = QProgressBar()
                    progress.setTextVisible(True)
                    self.mods_table.setCellWidget(row, 0, progress)
                progress.setValue(percent)
                progress.setFormat(f"Downloading {percent}%")
            else:
                self.mods_table.removeCellWidget(row, 0)

    def finish_workshop_subscription(self, result):
        if self.workshop_subscription_dialog:
            self.workshop_subscription_dialog.close()
            self.workshop_subscription_dialog = None
        self.workshop_subscription_monitor_hidden = False
        if result.ok:
            self.launch_button.setEnabled(False)
            installed_count = len(result.installed_ids)
            noun = "mod" if installed_count == 1 else "mods"
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Information)
            box.setWindowTitle("Mod download complete")
            box.setText(f"{installed_count} required {noun} downloaded successfully.")
            launch_button = box.addButton("Launch server", QMessageBox.ButtonRole.AcceptRole)
            set_ui_role(launch_button, "primary")
            box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(launch_button)
            box.exec()
            self.launch_after_workshop_download = box.clickedButton() == launch_button
        elif result.cancelled:
            self.statusBar().showMessage(
                "Stopped waiting for Steam; subscriptions and Steam downloads may continue.", 8000
            )
        else:
            QMessageBox.warning(
                self,
                "Steam Workshop incomplete",
                (result.error or "Steam did not install every requested Workshop item.")
                + "\n\nYou can still use the manual Workshop links.",
            )
        self.workshop_subscription_names = {}
        self.check_selected_server_mods(force=True)

    def clear_workshop_subscription_worker(self):
        self.workshop_subscription_worker = None
        self.launch_button.setEnabled(True)
        self.statusBar().showMessage("Steam Workshop helper finished; launch is available.", 5000)
        self.maybe_launch_after_workshop_download()

    def maybe_launch_after_workshop_download(self):
        if not self.launch_after_workshop_download:
            return
        workshop_worker = self.workshop_subscription_worker
        if workshop_worker and workshop_worker.isRunning():
            return
        if self.mod_worker and self.mod_worker.isRunning():
            return

        target_row = next(
            (
                row
                for row, server in enumerate(self.servers)
                if server_key(server) == self.workshop_subscription_server_key
            ),
            -1,
        )
        server = getattr(self, "workshop_subscription_server", None)
        if server is None:
            self.launch_after_workshop_download = False
            QMessageBox.warning(
                self,
                "Server unavailable",
                "The server selected for the Workshop download is no longer available.",
            )
            return

        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
        workshop_dir = install.workshop_dir if install else None
        result = usable_mod_result(server, self.last_mod_result, workshop_dir)
        if not result or not result.ok or result.missing_mods:
            self.launch_after_workshop_download = False
            QMessageBox.warning(
                self,
                "Mods not ready",
                "The post-download mod check did not confirm every required mod. "
                "Review the Mods tab before launching.",
            )
            return

        self.launch_after_workshop_download = False
        if target_row >= 0:
            self.table.selectRow(target_row)
        else:
            self.active_discovered_server = server
        QTimer.singleShot(0, self.launch_selected)

    def workshop_launch_block_reason(self) -> str:
        return launch_block_reason(
            self.workshop_subscription_worker,
            getattr(self, "workshop_state_worker", None),
            getattr(self, "workshop_recovery_ids", ()),
        )

    def _selected_mod_result(self, *, successful: bool = False) -> ModCheckResult | None:
        server = self.active_server_context()
        if not server:
            return None
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
        workshop_dir = install.workshop_dir if install else None
        result = matching_mod_result(server, self.last_mod_result, workshop_dir)
        if successful and result and not result.ok:
            return None
        return result
