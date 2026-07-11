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
    return (
        f"{result.server.name}: Required {required_count} | "
        f"Installed {required_count - missing_count} | Missing {missing_count} | "
        f"Local Workshop mods found: {result.installed_count}{context}"
    )


def mod_row(mod: RequiredMod) -> ModRow:
    installed = mod.installed
    return ModRow(
        values=[
            "✓ Installed" if installed else "✗ Missing",
            mod.workshop_id,
            mod.name or "Unknown",
            mod.installed_name or "",
            mod.workshop_url,
            "Installed" if installed else "Missing - subscribe in Steam Workshop",
        ],
        workshop_id=mod.workshop_id,
        status_colour="#6ee16e" if installed else "#ff6b6b",
    )
