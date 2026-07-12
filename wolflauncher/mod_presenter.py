from dataclasses import dataclass

from .mods import ModCheckResult, RequiredMod


@dataclass(frozen=True)
class ModRow:
    values: list[str]
    workshop_id: str
    status_colour: str


def mod_result_context(result: ModCheckResult) -> str:
    parts = []
    if result.steam_context:
        parts.append(result.steam_context)
    if result.workshop_dir:
        parts.append(f"Workshop: {result.workshop_dir}")
    return f" ({'; '.join(parts)})" if parts else ""


def mod_summary_text(result: ModCheckResult) -> str:
    context = mod_result_context(result)
    if not result.ok:
        return f"Could not check mods for {result.server.name}: {result.error}{context}"

    required_count = len(result.required_mods)
    if required_count == 0:
        return (
            f"{result.server.name}: no required mods reported by the server API. "
            f"Installed Workshop mods found locally: {result.installed_count}.{context}"
        )

    missing_count = len(result.missing_mods)
    summary = (
        f"{result.server.name}: Required {required_count} | "
        f"Ready {required_count - missing_count} | Missing {len(result.absent_mods)} | "
        f"Update/pending {len(result.update_mods)} | "
        f"Local Workshop mods found: {result.installed_count}{context}"
    )
    if result.workshop_state_error:
        summary += f" Steam item state unavailable: {result.workshop_state_error}"
    return summary


def mod_row(mod: RequiredMod) -> ModRow:
    from .workshop_subscription import (
        ITEM_STATE_DOWNLOADING,
        ITEM_STATE_DOWNLOAD_PENDING,
        ITEM_STATE_NEEDS_UPDATE,
    )
    installed = mod.ready
    if not mod.installed:
        status = "✗ Missing"
        detail = "Missing - subscribe in Steam Workshop"
        colour = "#ff6b6b"
    elif mod.workshop_state is not None and mod.workshop_state & ITEM_STATE_DOWNLOADING:
        percent = (
            f" ({int(mod.workshop_downloaded * 100 / mod.workshop_total)}%)"
            if mod.workshop_total > 0 else ""
        )
        status = "↻ Downloading"
        detail = f"Downloading update{percent}"
        colour = "#f6c453"
    elif mod.workshop_state is not None and mod.workshop_state & ITEM_STATE_DOWNLOAD_PENDING:
        status = "… Download pending"
        detail = "Steam has queued this item"
        colour = "#f6c453"
    elif mod.workshop_state is not None and mod.workshop_state & ITEM_STATE_NEEDS_UPDATE:
        status = "! Update required"
        detail = "Installed directory is outdated"
        colour = "#f6c453"
    else:
        status = "✓ Installed"
        detail = "Installed"
        colour = "#6ee16e"
    return ModRow(
        values=[
            status,
            mod.workshop_id,
            mod.name or "Unknown",
            mod.installed_name or "",
            mod.workshop_url,
            detail,
        ],
        workshop_id=mod.workshop_id,
        status_colour=colour,
    )
