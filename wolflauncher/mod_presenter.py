import re
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


def mod_description_preview(mod: RequiredMod, limit: int = 120) -> str:
    text = re.sub(r"\[/?[^\]]+\]", "", mod.workshop_description)
    text = re.sub(r"https?://\S+", "", text)
    text = " ".join(text.split())
    if not text:
        return "No Workshop description supplied."
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def mod_inspector_scale(window_height: int) -> float:
    """Scale inspector media from the established 720p baseline."""
    return max(1.0, min(1.4, max(0, window_height) / 720))


def mod_inspector_type_scale(window_height: int) -> float:
    """Grow inspector type more gently than its preview image."""
    growth = (max(0, window_height) - 720) / 1800
    return max(1.0, min(1.22, 1.0 + growth))


def mod_detail_status(mod: RequiredMod) -> str:
    if mod.ready:
        return "ready"
    if not mod.installed:
        return "missing"
    return "warning"


def mod_default_sort_key(mod: RequiredMod) -> tuple[int, str, str]:
    """Keep actionable required mods at the top of the initial table view."""
    from .workshop_subscription import (
        ITEM_STATE_DOWNLOAD_PENDING,
        ITEM_STATE_DOWNLOADING,
        ITEM_STATE_NEEDS_UPDATE,
    )

    state = mod.workshop_state or 0
    needs_update = mod.remote_update_available or bool(
        state & (ITEM_STATE_NEEDS_UPDATE | ITEM_STATE_DOWNLOADING | ITEM_STATE_DOWNLOAD_PENDING)
    )
    priority = 0 if needs_update else 1 if not mod.installed else 2
    return (priority, (mod.name or mod.installed_name).casefold(), mod.workshop_id)


def mods_needing_workshop_update(mods: list[RequiredMod]) -> list[RequiredMod]:
    """Return only installed items Steam or revision metadata says need attention."""
    return [mod for mod in mods if mod.installed and not mod.ready]


def combined_download_estimate(mods: list[RequiredMod]) -> str:
    known = [mod for mod in mods if mod.workshop_total > 0 or mod.workshop_file_size > 0]
    unknown = len(mods) - len(known)
    if not known:
        return f"Download size unavailable for all {len(mods)} item(s)."
    total = sum(
        max(0, mod.workshop_total - mod.workshop_downloaded)
        if mod.workshop_total > 0
        else mod.workshop_file_size
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
    if not result.ok:
        return f"Check failed: {result.error}"

    required_count = len(result.required_mods)
    if required_count == 0:
        return "Required 0  ·  Ready 0  ·  Missing 0  ·  Update/pending 0"

    missing_count = len(result.missing_mods)
    summary = (
        f"Required {required_count}  ·  Ready {required_count - missing_count}  ·  "
        f"Missing {len(result.absent_mods)}  ·  "
        f"Update/pending {len(result.update_mods)}"
    )
    if result.workshop_state_error:
        summary += f" Steam item state unavailable: {result.workshop_state_error}"
    unavailable = [mod for mod in result.absent_mods if mod.workshop_metadata_result == 9]
    if unavailable:
        labels = ", ".join(
            f"{mod.name or mod.installed_name or 'Workshop item'} ({mod.workshop_id})"
            for mod in unavailable
        )
        summary += (
            f"\nSteam's public Workshop service could not find: {labels}. "
            "Open the Workshop links while signed into Steam and check whether you can "
            "subscribe and download. If unavailable, contact the server administrator; "
            "the item may need to be restored or replaced on the server. "
            "Keep any working installed copies."
        )
    return summary


def mod_server_heading(result: ModCheckResult) -> str:
    """Return the stable selected-server identity above volatile check details."""
    return f"Required mods for {result.server.name}  ·  {result.server.connect_target}"


def mod_readiness_text(result: ModCheckResult) -> str:
    if not result.ok:
        return "Mod readiness could not be confirmed. Recheck before launching."
    missing_count = len(result.missing_mods)
    if missing_count:
        noun = "item" if missing_count == 1 else "items"
        return f"Action required: resolve {missing_count} Workshop {noun} before launching."
    if not result.required_mods:
        return "Ready to launch: this server reports no required mods."
    return f"Ready to launch: all {len(result.required_mods)} required mods are installed."


def mod_row(mod: RequiredMod) -> ModRow:
    from .workshop_subscription import (
        ITEM_STATE_DOWNLOAD_PENDING,
        ITEM_STATE_DOWNLOADING,
        ITEM_STATE_INSTALLED,
        ITEM_STATE_NEEDS_UPDATE,
    )

    if mod.workshop_state is not None and mod.workshop_state & ITEM_STATE_DOWNLOADING:
        percent = (
            f" ({int(mod.workshop_downloaded * 100 / mod.workshop_total)}%)"
            if mod.workshop_total > 0
            else ""
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
    elif mod.remote_update_available:
        status = "! Workshop update available"
        colour = STATUS_COLOURS["warning"]
    elif (
        mod.workshop_state is not None
        and mod.workshop_state & ITEM_STATE_INSTALLED
        and not mod.installed
    ):
        status = "… Verifying install"
        colour = STATUS_COLOURS["warning"]
    elif not mod.installed:
        status = (
            "✗ Missing; Steam item not found" if mod.workshop_metadata_result == 9 else "✗ Missing"
        )
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
        ],
        workshop_id=mod.workshop_id,
        status_colour=colour,
    )
