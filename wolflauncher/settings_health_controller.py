"""Qt coordination for the Settings health snapshot and table."""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidgetItem

from .platform_detection import detect_steam
from .settings_health import build_settings_health_snapshot
from .theme import STATUS_COLOURS


class SettingsHealthCoordinator:
    """Refresh the settings-health model and apply it to the owned widgets."""

    def __init__(self, window):
        self.window = window

    def refresh(self):
        window = self.window
        if not hasattr(window, "health_table"):
            return
        install_rows = detect_steam()
        window.detected_steam_installs = install_rows
        provider_status, provider_detail = self._provider_health()
        snapshot = build_settings_health_snapshot(
            window.launcher_path.text(),
            window.launch_engine_key(),
            window.native_steam_mode_key(),
            provider_status,
            provider_detail,
            install_rows,
        )
        window.system_summary.setText(snapshot.summary)
        rows = snapshot.rows
        window.health_table.setRowCount(len(rows))
        for row, (name, status, details) in enumerate(rows):
            self._set_item(row, 0, name)
            self._set_item(row, 1, status, self.colour(status))
            self._set_item(row, 2, details)
        window.health_table.resizeColumnsToContents()
        window.update_settings_health_groups(rows)

    def _provider_health(self) -> tuple[str, str]:
        window = self.window
        provider = window.discovery_provider_key()
        detail = window.discovery_provider.currentText()
        if provider == "steam_web_api":
            status = "OK" if window.steam_web_api_key.text().strip() else "MISSING"
            detail = "Steam Web API key saved" if status == "OK" else "Steam Web API key required"
            return status, detail
        if provider == "steam_master":
            try:
                addresses = window.steam_master_addresses()
            except (OSError, ValueError) as exc:
                return "WARN", str(exc)
            detail = ", ".join(address.address for address in addresses)
            return "OK", detail or "Default Steam masters"
        details = {
            "wolfapi_v1": "WolfAPI server discovery",
            "wolfapi": "WolfAPI legacy hosted cache fallback",
            "battlemetrics": "BattleMetrics public API",
            "disabled": "Database refresh is disabled",
        }
        return ("WARN" if provider == "disabled" else "OK"), details.get(provider, detail)

    @staticmethod
    def colour(status: str) -> str:
        if status == "OK":
            return STATUS_COLOURS["positive"]
        if status == "WARN":
            return STATUS_COLOURS["warning"]
        return STATUS_COLOURS["negative"]

    def _set_item(self, row: int, column: int, text: str, colour: str | None = None):
        item = QTableWidgetItem(text)
        if colour:
            item.setForeground(QColor(colour))
        self.window.health_table.setItem(row, column, item)
