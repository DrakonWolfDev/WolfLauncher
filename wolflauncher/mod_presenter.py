from dataclasses import dataclass

from .mods import ModCheckResult, RequiredMod
from .theme import STATUS_COLOURS


@dataclass(frozen=True)
class ModRow:
    values: list[str]
    workshop_id: str
    status_colour: str


def format_byte_size(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return "Unavailable"


def mod_download_size(mod: RequiredMod) -> str:
    if mod.workshop_total > 0:
        return format_byte_size(max(0, mod.workshop_total - mod.workshop_downloaded))
    if mod.workshop_file_size > 0:
        return format_byte_size(mod.workshop_file_size)
    return "Unavailable"


def mod_file_size(mod: RequiredMod) -> str:
    """Return the full published size for table presentation when available."""
    size = mod.workshop_file_size or mod.workshop_total
    return format_byte_size(size) if size > 0 else "Unavailable"


def combined_download_estimate(mods: list[RequiredMod]) -> str:
    known = [
        mod for mod in mods
        if mod.workshop_total > 0 or mod.workshop_file_size > 0
    ]
    unknown = len(mods) - len(known)
    if not known:
        return f"Download size unavailable for all {len(mods)} item(s)."
    total = sum(
        max(0, mod.workshop_total - mod.workshop_downloaded)
        if mod.workshop_total > 0 else mod.workshop_file_size
        for mod in known
    )
    if unknown:
        return (
            f"Known remaining download: {format_byte_size(total)} across {len(known)} item(s); "
            f"size unavailable for {unknown} item(s)."
        )
    return f"Estimated remaining download: {format_byte_size(total)}."


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
        ITEM_STATE_INSTALLED,
        ITEM_STATE_NEEDS_UPDATE,
    )
    if mod.workshop_state is not None and mod.workshop_state & ITEM_STATE_DOWNLOADING:
        percent = (
            f" ({int(mod.workshop_downloaded * 100 / mod.workshop_total)}%)"
            if mod.workshop_total > 0 else ""
        )
        status = "↻ Downloading"
        status += percent
        colour = STATUS_COLOURS["warning"]
    elif mod.workshop_state is not None and mod.workshop_state & ITEM_STATE_DOWNLOAD_PENDING:
        status = "… Download pending"
        colour = STATUS_COLOURS["warning"]
    elif mod.workshop_state is not None and mod.workshop_state & ITEM_STATE_NEEDS_UPDATE:
        status = "! Update required"
        colour = STATUS_COLOURS["warning"]
    elif mod.workshop_state is not None and mod.workshop_state & ITEM_STATE_INSTALLED and not mod.installed:
        status = "… Verifying install"
        colour = STATUS_COLOURS["warning"]
    elif not mod.installed:
        status = "✗ Missing"
        colour = STATUS_COLOURS["negative"]
    else:
        status = "✓ Installed"
        colour = STATUS_COLOURS["positive"]
    return ModRow(
        values=[
            status,
            mod.name or mod.installed_name or "Unknown",
            mod.workshop_id,
            mod_file_size(mod),
            mod.workshop_url,
        ],
        workshop_id=mod.workshop_id,
        status_colour=colour,
    )
