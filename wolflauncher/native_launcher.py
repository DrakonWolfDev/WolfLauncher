import base64
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from .launcher import LaunchError, build_launch_command
from .models import Server
from .mods import RequiredMod, fetch_required_mods
from .platform_detection import FLATPAK_STEAM_ID, STEAM_APP_ID_DAYZ, SteamInstall, install_label
from .status import resolve_host


class NativeLaunchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str = "native launch",
        guidance: str = "",
        details: str = "",
    ):
        super().__init__(message)
        self.stage = stage
        self.guidance = guidance
        self.details = details

    def user_message(self) -> str:
        if not self.guidance:
            return str(self)
        return f"{self}\n\n{self.guidance}"

    def with_details(self, details: str) -> "NativeLaunchError":
        if not details:
            return self
        return NativeLaunchError(
            str(self),
            stage=self.stage,
            guidance=self.guidance,
            details=details,
        )


FLATPAK_STEAM_PARAMS = [
    "--branch=stable",
    "--arch=x86_64",
    "--command=/app/bin/steam-wrapper",
]
MOD_NAME_RE = re.compile(r'name\s*=\s*"([^"]+)"')


@dataclass
class PreparedNativeLaunch:
    command: list[str]
    mod_links: list[str] = field(default_factory=list)
    missing_mod_ids: list[str] = field(default_factory=list)
    prepared_mods: list["PreparedModLink"] = field(default_factory=list)


@dataclass
class PreparedModLink:
    workshop_id: str
    name: str
    source_path: Path
    link_path: Path
    link_name: str
    created: bool


@dataclass
class NativeModSetup:
    mod_links: list[str] = field(default_factory=list)
    prepared_mods: list[PreparedModLink] = field(default_factory=list)
    missing_mod_ids: list[str] = field(default_factory=list)


@dataclass
class NativeLaunchPreview:
    server: Server
    command: list[str]
    mod_setup: NativeModSetup

    @property
    def ready(self) -> bool:
        return not self.mod_setup.missing_mod_ids


@dataclass
class NativeLaunchParityReport:
    preview: NativeLaunchPreview
    install: SteamInstall
    required_mod_ids: list[str] = field(default_factory=list)
    required_mod_labels: list[str] = field(default_factory=list)
    missing_mod_labels: list[str] = field(default_factory=list)
    external_command: list[str] = field(default_factory=list)
    external_error: str = ""

    @property
    def resolved_connect(self) -> str:
        return f"{self.preview.server.host}:{self.preview.server.game_port}"

    @property
    def native_command_text(self) -> str:
        return shlex.join(self.preview.command) if self.preview.command else ""

    @property
    def external_command_text(self) -> str:
        return shlex.join(self.external_command) if self.external_command else ""


def compact_mod_link_name(workshop_id: str | int) -> str:
    """Return the legacy launcher's shortened @base64modid link name."""
    try:
        value = int(str(workshop_id).strip(), 10)
    except ValueError as exc:
        raise NativeLaunchError(
            f"Invalid Workshop mod ID: {workshop_id}",
            stage="mod setup",
            guidance="Recheck the server's required mod list before trying the native launcher again.",
        ) from exc
    if value < 0:
        raise NativeLaunchError(
            f"Invalid Workshop mod ID: {workshop_id}",
            stage="mod setup",
            guidance="Recheck the server's required mod list before trying the native launcher again.",
        )

    encoded = bytearray()
    while True:
        encoded.append(value & 0xFF)
        value >>= 8
        if value <= 0:
            break
    token = base64.b64encode(bytes(encoded)).decode("ascii")
    token = token.replace("/", "-").replace("+", "_").rstrip("=")
    return f"@{token}"


def build_steam_launch_command(
    install: SteamInstall,
    server: Server,
    player_name: str,
    mod_links: list[str],
    extra_params: list[str] | None = None,
) -> list[str]:
    safe_name = player_name.strip()
    command = _steam_command_prefix(install)
    command.extend(["-applaunch", str(STEAM_APP_ID_DAYZ)])

    if mod_links:
        command.append(f"-mod={';'.join(mod_links)}")
    command.extend([f"-connect={server.host}:{server.game_port}", "-nolauncher", "-world=empty"])
    if safe_name:
        command.append(f"-name={safe_name}")
    if extra_params:
        command.extend(extra_params)
    return command


def prepare_native_launch(
    install: SteamInstall,
    server: Server,
    player_name: str,
    required_mods: list[RequiredMod] | None = None,
    extra_params: list[str] | None = None,
) -> PreparedNativeLaunch:
    """Prepare DayZ mod symlinks and build the Steam launch command.

    This mirrors the vendored shell launcher core while staying behind a Python
    interface. Callers can pass already-fetched mods to keep GUI preflight and
    native preparation in sync; otherwise the DayZSA API is queried here.
    """
    dayz_dir = _require_dir(install.dayz_dir, "DayZ install")
    workshop_dir = _require_dir(install.workshop_dir, "DayZ Workshop")
    launch_server = _resolved_server(server)
    mods = required_mods if required_mods is not None else fetch_required_mods(launch_server)

    mod_setup = prepare_mod_links(dayz_dir, workshop_dir, mods)

    if mod_setup.missing_mod_ids:
        raise NativeLaunchError(
            "Missing mod directories for: " + ", ".join(_missing_mod_labels(mods, mod_setup.missing_mod_ids)),
            stage="mod setup",
            guidance=(
                "Open the missing Workshop pages from the Mods tab, let Steam finish downloading them, "
                "then run the mod check again."
            ),
        )

    return PreparedNativeLaunch(
        command=build_steam_launch_command(install, launch_server, player_name, mod_setup.mod_links, extra_params),
        mod_links=mod_setup.mod_links,
        missing_mod_ids=mod_setup.missing_mod_ids,
        prepared_mods=mod_setup.prepared_mods,
    )


def prepare_native_launch_preview(
    install: SteamInstall,
    server: Server,
    player_name: str,
    required_mods: list[RequiredMod],
    extra_params: list[str] | None = None,
) -> NativeLaunchPreview:
    """Prepare installed mod links and return a non-executing launch preview."""
    dayz_dir = _require_dir(install.dayz_dir, "DayZ install")
    workshop_dir = _require_dir(install.workshop_dir, "DayZ Workshop")
    launch_server = _resolved_server(server)
    mod_setup = prepare_mod_links(dayz_dir, workshop_dir, required_mods)
    command = []
    if not mod_setup.missing_mod_ids:
        command = build_steam_launch_command(install, launch_server, player_name, mod_setup.mod_links, extra_params)
    return NativeLaunchPreview(server=launch_server, command=command, mod_setup=mod_setup)


def prepare_native_launch_parity_report(
    install: SteamInstall,
    launcher_path: str,
    server: Server,
    player_name: str,
    required_mods: list[RequiredMod],
    extra_params: list[str] | None = None,
) -> NativeLaunchParityReport:
    """Prepare a non-launching native preview and compare it with external handoff."""
    preview = prepare_native_launch_preview(
        install,
        server,
        player_name,
        required_mods,
        extra_params,
    )
    try:
        external_command = build_launch_command(launcher_path, player_name, server)
        external_error = ""
    except LaunchError as exc:
        external_command = []
        external_error = str(exc)
    return NativeLaunchParityReport(
        preview=preview,
        install=install,
        required_mod_ids=[str(mod.workshop_id).strip() for mod in required_mods],
        required_mod_labels=_mod_labels(required_mods),
        missing_mod_labels=_missing_mod_labels(required_mods, preview.mod_setup.missing_mod_ids),
        external_command=external_command,
        external_error=external_error,
    )


def format_native_launch_parity_report(report: NativeLaunchParityReport) -> str:
    """Return a copyable native-launch parity report for testing and bug reports."""
    preview = report.preview
    install = report.install
    install_detail = install_label(install)
    lines = [
        "Native launch parity report",
        "",
        "This compares the configured external launcher handoff with the experimental native path.",
        "It did not launch Steam or DayZ.",
        "",
        "Validation checklist:",
        f"- Steam mode: {install_detail}",
        f"- Steam command: {install.executable or 'not detected'}",
        f"- Steam running: {'yes' if install.running else 'no'}",
        f"- Steam root: {_path_text(install.root)}",
        f"- Steam library: {_path_text(install.steamapps)}",
        f"- Proton compatdata: {_path_text(install.compatdata_dir)}",
        f"- DayZ path: {_path_text(install.dayz_dir)}",
        f"- Workshop path: {_path_text(install.workshop_dir)}",
        f"- Server: {preview.server.name}",
        f"- Resolved connect: {report.resolved_connect}",
        f"- Query port: {preview.server.query_port}",
        f"- Required mod count: {len(report.required_mod_ids)}",
        f"- Prepared native mod links: {len(preview.mod_setup.prepared_mods)}",
        f"- Created native mod links: {_created_mod_link_count(preview.mod_setup)}",
        f"- Reused native mod links: {_reused_mod_link_count(preview.mod_setup)}",
        f"- Missing Workshop directories: {len(preview.mod_setup.missing_mod_ids)}",
        f"- Native ready: {'yes' if preview.ready else 'no'}",
        "",
        "Result:",
        _parity_result_text(report),
        "",
        "External launcher handoff:",
    ]

    if report.external_command:
        lines.extend([
            f"- Command: {report.external_command_text}",
            f"- Server argument: {report.resolved_connect}",
            f"- Query port: {preview.server.query_port}",
        ])
    else:
        lines.extend([
            "- Command: not available",
            f"- Reason: {report.external_error or 'external launcher command could not be built'}",
        ])

    lines.extend([
        "",
        "Native launcher candidate:",
        f"- Ready: {'yes' if preview.ready else 'no'}",
        f"- Connect argument: {report.resolved_connect}",
        "",
    ])

    if report.required_mod_ids:
        lines.append("Required Workshop mods:")
        lines.extend(f"- {label}" for label in report.required_mod_labels)
    else:
        lines.append("Required Workshop mods: none")
    lines.append("")

    if preview.mod_setup.prepared_mods:
        lines.append("Native prepared mod links:")
        for prepared in preview.mod_setup.prepared_mods:
            state = "created" if prepared.created else "already existed"
            lines.append(
                f"- {prepared.name} ({prepared.workshop_id}) -> "
                f"{prepared.link_name} [{state}]"
            )
            lines.append(f"  source: {prepared.source_path}")
            lines.append(f"  link: {prepared.link_path}")
    else:
        lines.append("Native prepared mod links: none")

    if preview.mod_setup.missing_mod_ids:
        lines.extend([
            "",
            "Missing Workshop mod directories:",
            *[f"- {label}" for label in report.missing_mod_labels],
            "",
            "Native Steam command: not ready until all required mods are installed.",
        ])
    else:
        lines.extend([
            "",
            "Native Steam command:",
            report.native_command_text,
        ])
    return "\n".join(lines)


def prepare_mod_links(dayz_dir: Path, workshop_dir: Path, required_mods: list[RequiredMod]) -> NativeModSetup:
    """Prepare the legacy-compatible DayZ @mod symlinks for installed mods."""
    setup = NativeModSetup()

    for mod in required_mods:
        workshop_id = str(mod.workshop_id).strip()
        compact_name = compact_mod_link_name(workshop_id)
        mod_path = workshop_dir / workshop_id
        if not mod_path.is_dir():
            setup.missing_mod_ids.append(workshop_id)
            continue

        if not (mod_path / "meta.cpp").is_file():
            raise NativeLaunchError(
                f"Missing mod metadata for: {workshop_id}",
                stage="mod setup",
                guidance="Let Steam verify or redownload the Workshop item, then recheck mods.",
            )
        mod_name = mod.name.strip() or _read_mod_name(mod_path / "meta.cpp")
        if not mod_name:
            raise NativeLaunchError(
                f"Missing mod name for: {workshop_id}",
                stage="mod setup",
                guidance="Let Steam verify or redownload the Workshop item, then recheck mods.",
            )

        link_path = dayz_dir / compact_name
        created = _ensure_relative_symlink(mod_path, link_path)
        setup.mod_links.append(compact_name)
        setup.prepared_mods.append(
            PreparedModLink(
                workshop_id=workshop_id,
                name=mod_name,
                source_path=mod_path,
                link_path=link_path,
                link_name=compact_name,
                created=created,
            )
        )

    return setup


def _steam_command_prefix(install: SteamInstall) -> list[str]:
    if install.mode == "flatpak":
        if not install.executable:
            raise NativeLaunchError(
                "Flatpak Steam command not detected",
                stage="Steam detection",
                guidance=(
                    "Install Flatpak Steam, confirm the flatpak command is available, "
                    "or switch to a detected native Steam installation."
                ),
            )
        return ["flatpak", "run", *FLATPAK_STEAM_PARAMS, FLATPAK_STEAM_ID]

    if not install.executable:
        if install.mode == "STEAM_ROOT env":
            guidance = (
                "STEAM_ROOT points WolfLauncher at a Steam library, but the native Steam executable "
                "was not found. Install native Steam or make the steam command available on PATH."
            )
        else:
            guidance = (
                "Install native Steam, make the steam command available on PATH, "
                "or switch to a detected Flatpak Steam installation."
            )
        raise NativeLaunchError(
            f"{install.mode} Steam executable not detected",
            stage="Steam detection",
            guidance=guidance,
        )
    return [install.executable]


def _require_dir(path: Path | None, label: str) -> Path:
    if not path or not path.is_dir():
        if label == "DayZ install":
            guidance = "Check Settings health and confirm DayZ is installed in the selected Steam library."
        elif label == "DayZ Workshop":
            guidance = (
                "Check Settings health and confirm the DayZ Workshop folder is visible for the selected Steam library. "
                "If DayZ is installed but no Workshop folder appears, subscribe to at least one DayZ Workshop item "
                "and let Steam finish downloading it."
            )
        else:
            guidance = "Check Settings health and confirm the selected Steam library paths are detected."
        raise NativeLaunchError(
            f"{label} directory not detected",
            stage="Steam library detection",
            guidance=guidance,
        )
    return path


def _path_text(path: Path | None) -> str:
    return str(path) if path else "not detected"


def _created_mod_link_count(mod_setup: NativeModSetup) -> int:
    return sum(1 for prepared in mod_setup.prepared_mods if prepared.created)


def _reused_mod_link_count(mod_setup: NativeModSetup) -> int:
    return sum(1 for prepared in mod_setup.prepared_mods if not prepared.created)


def _parity_result_text(report: NativeLaunchParityReport) -> str:
    preview = report.preview
    if preview.ready:
        return (
            f"Native command is ready for {report.resolved_connect} with "
            f"{len(preview.mod_setup.prepared_mods)} prepared mod link(s)."
        )
    return (
        "Native command is not ready because "
        f"{len(preview.mod_setup.missing_mod_ids)} Workshop director"
        f"{'y is' if len(preview.mod_setup.missing_mod_ids) == 1 else 'ies are'} missing."
    )


def _missing_mod_labels(required_mods: list[RequiredMod], missing_mod_ids: list[str]) -> list[str]:
    names_by_id = _mod_names_by_id(required_mods)
    labels = []
    for workshop_id in missing_mod_ids:
        name = names_by_id.get(workshop_id)
        labels.append(f"{name} ({workshop_id})" if name else workshop_id)
    return labels


def _mod_labels(required_mods: list[RequiredMod]) -> list[str]:
    labels = []
    for mod in required_mods:
        workshop_id = str(mod.workshop_id).strip()
        name = mod.name.strip()
        labels.append(f"{name} ({workshop_id})" if name else workshop_id)
    return labels


def _mod_names_by_id(required_mods: list[RequiredMod]) -> dict[str, str]:
    return {str(mod.workshop_id).strip(): mod.name.strip() for mod in required_mods if mod.name.strip()}


def _resolved_server(server: Server) -> Server:
    try:
        host = resolve_host(server.host)
    except OSError as exc:
        raise NativeLaunchError(
            f"Could not resolve server host {server.host}: {exc}",
            stage="server DNS",
            guidance="Check the server address, network connection and DNS before launching.",
        ) from exc
    return Server(
        name=server.name,
        group=server.group,
        host=host,
        game_port=server.game_port,
        query_port=server.query_port,
        favourite=server.favourite,
    )


def _read_mod_name(meta_path: Path) -> str:
    if not meta_path.is_file():
        return ""
    try:
        text = meta_path.read_text(errors="ignore")
    except OSError:
        return ""
    match = MOD_NAME_RE.search(text)
    return match.group(1).strip() if match else ""


def _ensure_relative_symlink(target: Path, link_path: Path) -> bool:
    if link_path.is_symlink():
        existing_target = Path(os.readlink(link_path))
        expected_target = Path(os.path.relpath(target, start=link_path.parent))
        if existing_target == expected_target or link_path.resolve(strict=False) == target.resolve(strict=False):
            return False
        raise NativeLaunchError(
            f"Mod link path already exists but points somewhere else: {link_path}",
            stage="mod setup",
            guidance=(
                "Remove the stale @mod symlink from the DayZ install directory, then prepare the native launch again."
            ),
        )
    if link_path.exists():
        raise NativeLaunchError(
            f"Mod link path already exists and is not a symlink: {link_path}",
            stage="mod setup",
            guidance="Move or remove the conflicting path in the DayZ install directory before retrying.",
        )

    relative_target = os.path.relpath(target, start=link_path.parent)
    try:
        link_path.symlink_to(relative_target)
        return True
    except OSError as exc:
        raise NativeLaunchError(
            f"Could not create mod symlink {link_path}: {exc}",
            stage="mod setup",
            guidance="Check write permissions on the DayZ install directory.",
        ) from exc
