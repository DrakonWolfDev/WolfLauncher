import base64
import os
import re
import shlex
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .launcher import DEFAULT_PLAYER_NAME, LaunchError, build_launch_command
from .models import Server
from .mods import RequiredMod, fetch_required_mods
from .platform_detection import (
    SteamInstall,
    install_label,
    proton_compatdata_detail,
    steam_command_detail,
    steam_mode_label,
)
from .platforms import current_platform
from .redaction import redact_support_text
from .status import resolve_host

# Flatpak Steam parameters (matching the external launcher)
FLATPAK_PARAMS = (
    "--branch=stable",
    "--arch=x86_64",
    "--command=/app/bin/steam-wrapper",
)


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
        if not details and not self.details:
            return self
        combined_details = self.details
        if details:
            combined_details = f"{combined_details}\n\n{details}" if combined_details else details
        return NativeLaunchError(
            str(self),
            stage=self.stage,
            guidance=self.guidance,
            details=combined_details,
        )


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
    selected_steam_mode: str = ""
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
    safe_name = player_name.strip() or DEFAULT_PLAYER_NAME
    command = _steam_command_prefix(install)
    command.extend(["-applaunch", str(install.product.client_app_id)])

    if mod_links:
        command.append(f"-mod={';'.join(mod_links)}")
    command.append(f"-connect={server.host}:{server.game_port}")
    # The official launcher normally starts BattlEye.  On Windows this direct
    # handoff skips that launcher, so request its supported equivalent.
    if Path(install.executable).suffix.lower() == ".exe":
        command.append("-useBE")
    command.extend(["-nolauncher", "-world=empty"])
    command.append(f"-name={safe_name}")
    if extra_params:
        command.extend(extra_params)
    return command


def build_steam_local_launch_command(
    install: SteamInstall,
    player_name: str,
    mod_links: list[str],
    extra_params: list[str] | None = None,
) -> list[str]:
    """Build a native DayZ handoff for an offline/local session.

    Local tools intentionally share the normal mod handling and Steam command
    prefix, but do not add a server ``-connect`` argument.
    """
    safe_name = player_name.strip() or DEFAULT_PLAYER_NAME
    command = _steam_command_prefix(install)
    command.extend(["-applaunch", str(install.product.client_app_id)])
    if mod_links:
        command.append(f"-mod={';'.join(mod_links)}")
    if Path(install.executable).suffix.lower() == ".exe":
        command.append("-useBE")
    command.extend(["-nolauncher", "-world=empty", f"-name={safe_name}"])
    if extra_params:
        command.extend(extra_params)
    return command


def prepare_native_local_launch(
    install: SteamInstall,
    player_name: str,
    required_mods: list[RequiredMod],
    extra_params: list[str] | None = None,
) -> PreparedNativeLaunch:
    """Prepare a native offline/local DayZ launch from an explicit mod set."""
    dayz_dir = _require_dir(install.dayz_dir, "DayZ install")
    workshop_dir = _require_dir(install.workshop_dir, "DayZ Workshop")
    mod_setup = prepare_mod_links(dayz_dir, workshop_dir, required_mods)
    if mod_setup.missing_mod_ids:
        raise NativeLaunchError(
            "Missing mod directories for: "
            + ", ".join(_missing_mod_labels(required_mods, mod_setup.missing_mod_ids)),
            stage="local mod setup",
            guidance=(
                "Open the missing Workshop pages, let Steam finish downloading them, "
                "then verify the local profile again."
            ),
        )
    return PreparedNativeLaunch(
        command=build_steam_local_launch_command(
            install, player_name, mod_setup.mod_links, extra_params
        ),
        mod_links=mod_setup.mod_links,
        missing_mod_ids=mod_setup.missing_mod_ids,
        prepared_mods=mod_setup.prepared_mods,
    )


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
    native preparation in sync; otherwise the server's DayZ A2S_RULES manifest
    is queried directly here.
    """
    dayz_dir = _require_dir(install.dayz_dir, "DayZ install")
    workshop_dir = _require_dir(install.workshop_dir, "DayZ Workshop")
    launch_server = _resolved_server(server)
    if required_mods is None:
        try:
            mods = fetch_required_mods(launch_server)
        except Exception as exc:
            raise NativeLaunchError(
                f"Could not fetch required mods: {exc}",
                stage="mod lookup",
                guidance=(
                    "Check the network connection and server availability, then run the mod check again. "
                    "The external launcher remains available as a fallback."
                ),
            ) from exc
    else:
        mods = required_mods

    if install.product.experimental and current_platform().capabilities.platform_id != "linux":
        return _prepare_experimental_native_launch(install, launch_server, mods, extra_params)

    mod_setup = prepare_mod_links(dayz_dir, workshop_dir, mods)

    if mod_setup.missing_mod_ids:
        raise NativeLaunchError(
            "Missing mod directories for: "
            + ", ".join(_missing_mod_labels(mods, mod_setup.missing_mod_ids)),
            stage="mod setup",
            guidance=(
                "Open the missing Workshop pages from the Mods tab, let Steam finish downloading them, "
                "then run the mod check again."
            ),
        )

    return PreparedNativeLaunch(
        command=build_steam_launch_command(
            install, launch_server, player_name, mod_setup.mod_links, extra_params
        ),
        mod_links=mod_setup.mod_links,
        missing_mod_ids=mod_setup.missing_mod_ids,
        prepared_mods=mod_setup.prepared_mods,
    )


def _prepare_experimental_native_launch(
    install: SteamInstall,
    server: Server,
    mods: list[RequiredMod],
    extra_params: list[str] | None,
) -> PreparedNativeLaunch:
    """Build the observed Windows DayZ Experimental BattlEye handoff.

    Experimental has no Workshop app. Its official launcher uses local paths,
    commonly the Stable launcher's ``DayZ/!Workshop`` junction collection.
    WolfLauncher only reads those locations; it does not copy, subscribe, or
    mutate Workshop content.
    """
    if current_platform().capabilities.platform_id != "windows":
        raise NativeLaunchError(
            "DayZ Experimental native launch is not validated on this platform yet",
            stage="Experimental launch",
            guidance="Use Steam's DayZ Experimental launcher until the Linux Experimental handoff is verified.",
        )
    dayz_dir = _require_dir(install.dayz_dir, "DayZ Experimental install")
    executable = dayz_dir / "DayZ_BE.exe"
    if not executable.is_file():
        raise NativeLaunchError(
            "DayZ Experimental BattlEye launcher was not detected",
            stage="Experimental launch",
            guidance="Launch DayZ Experimental once through Steam and complete BattlEye setup, then retry.",
        )
    workshop_dir = _require_dir(install.workshop_dir, "Stable DayZ Workshop")
    local_paths = _experimental_mod_paths(dayz_dir, workshop_dir, mods)
    missing = [str(mod.workshop_id) for mod, path in zip(mods, local_paths) if not path.is_dir()]
    if missing:
        raise NativeLaunchError(
            "Missing local mod directories for: " + ", ".join(_missing_mod_labels(mods, missing)),
            stage="Experimental local mods",
            guidance="Add the Stable DayZ !Workshop folder as an Experimental local-mod source, then retry.",
        )
    links = [str(path) for path in local_paths]
    command = [str(executable), "0", "1", "1", "-exe", "DayZ_x64.exe"]
    if links:
        command.append(f"-mod={';'.join(links)}")
    command.append(f"-connect={server.host}:{server.game_port}:{server.query_port}")
    if extra_params:
        command.extend(extra_params)
    return PreparedNativeLaunch(command=command, mod_links=links)


def _experimental_mod_paths(
    dayz_dir: Path, workshop_dir: Path, mods: list[RequiredMod]
) -> list[Path]:
    """Prefer the official launcher-compatible Stable ``!Workshop`` junction names."""
    by_id: dict[str, Path] = {}
    local_source = dayz_dir.parent / "DayZ" / "!Workshop"
    if local_source.is_dir():
        for child in local_source.iterdir():
            try:
                target = child.resolve()
                if target.is_dir() and target.name.isdigit():
                    by_id[target.name] = child
            except OSError:
                continue
    return [by_id.get(str(mod.workshop_id), workshop_dir / str(mod.workshop_id)) for mod in mods]


def prepare_native_launch_preview(
    install: SteamInstall,
    server: Server,
    player_name: str,
    required_mods: list[RequiredMod],
    extra_params: list[str] | None = None,
) -> NativeLaunchPreview:
    """Prepare installed mod links and return a non-executing launch preview."""
    launch_server = _resolved_server(server)
    if install.product.experimental and current_platform().capabilities.platform_id != "linux":
        prepared = _prepare_experimental_native_launch(
            install, launch_server, required_mods, extra_params
        )
        return NativeLaunchPreview(
            server=launch_server,
            command=prepared.command,
            mod_setup=NativeModSetup(mod_links=prepared.mod_links),
        )
    dayz_dir = _require_dir(install.dayz_dir, "DayZ install")
    workshop_dir = _require_dir(install.workshop_dir, "DayZ Workshop")
    mod_setup = prepare_mod_links(dayz_dir, workshop_dir, required_mods)
    command = []
    if not mod_setup.missing_mod_ids:
        command = build_steam_launch_command(
            install, launch_server, player_name, mod_setup.mod_links, extra_params
        )
    return NativeLaunchPreview(server=launch_server, command=command, mod_setup=mod_setup)


def prepare_native_launch_parity_report(
    install: SteamInstall,
    launcher_path: str,
    server: Server,
    player_name: str,
    required_mods: list[RequiredMod],
    extra_params: list[str] | None = None,
    selected_steam_mode: str = "",
) -> NativeLaunchParityReport:
    """Prepare a non-launching native preview and compare it with external handoff."""
    preview = prepare_native_launch_preview(
        install,
        server,
        player_name,
        required_mods,
        extra_params,
    )
    if current_platform().capabilities.supports_external_launcher:
        try:
            external_command = build_launch_command(launcher_path, player_name, preview.server)
            external_error = ""
        except LaunchError as exc:
            external_command = []
            external_error = str(exc)
    else:
        external_command = []
        external_error = "External launcher fallback is not supported on this platform"
    return NativeLaunchParityReport(
        preview=preview,
        install=install,
        selected_steam_mode=selected_steam_mode,
        required_mod_ids=[str(mod.workshop_id).strip() for mod in required_mods],
        required_mod_labels=_mod_labels(required_mods),
        missing_mod_labels=_missing_mod_labels(required_mods, preview.mod_setup.missing_mod_ids),
        external_command=external_command,
        external_error=external_error,
    )


def format_native_launch_parity_report(
    report: NativeLaunchParityReport,
    generated_at: datetime | None = None,
) -> str:
    """Return a copyable native-launch parity report for testing and bug reports."""
    if not current_platform().capabilities.supports_external_launcher:
        return _format_native_launch_preview_report(report, generated_at)

    preview = report.preview
    install = report.install
    install_detail = install_label(install)
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    lines = [
        "Native launch parity report",
        f"Generated at: {timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat()}",
        "",
        "This compares the configured external launcher fallback with the native path.",
        "It did not launch Steam or DayZ.",
        "",
        "Validation checklist:",
        f"- Steam install setting: {_selected_steam_mode_label(report.selected_steam_mode)}",
        f"- Steam mode: {install_detail}",
        f"- Steam command: {steam_command_detail(install)}",
        f"- Steam running: {'yes' if install.running else 'no'}",
        f"- Steam root: {_path_text(install.root)}",
        f"- Steam library: {_path_text(install.steamapps)}",
        f"- Proton compatdata: {proton_compatdata_detail(install)}",
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
        "Readiness comparison:",
        f"- External launcher: {_external_readiness_text(report)}",
        f"- Native launcher: {_native_readiness_text(report)}",
        f"- Connect target: {report.resolved_connect}",
        f"- Query port: {preview.server.query_port}",
        f"- Required mods from current check: {len(report.required_mod_ids)}",
        "- External mod source: external launcher refetches server requirements at launch",
        "- Native mod source: current WolfLauncher mod check and prepared local Workshop links",
        "",
        "External launcher handoff:",
    ]

    if report.external_command:
        lines.extend(
            [
                "- Ready: yes",
                f"- Command: {report.external_command_text}",
                f"- Server argument: {report.resolved_connect}",
                f"- Query port: {preview.server.query_port}",
            ]
        )
    else:
        lines.extend(
            [
                "- Ready: no",
                "- Command: not available",
                f"- Reason: {report.external_error or 'external launcher command could not be built'}",
            ]
        )

    lines.extend(
        [
            "",
            "Native launcher candidate:",
            f"- Ready: {'yes' if preview.ready else 'no'}",
            f"- Connect argument: {report.resolved_connect}",
            "",
        ]
    )

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
                f"- {prepared.name} ({prepared.workshop_id}) -> {prepared.link_name} [{state}]"
            )
            lines.append(f"  source: {prepared.source_path}")
            lines.append(f"  link: {prepared.link_path}")
    else:
        lines.append("Native prepared mod links: none")

    if preview.mod_setup.missing_mod_ids:
        lines.extend(
            [
                "",
                "Missing Workshop mod directories:",
                *[f"- {label}" for label in report.missing_mod_labels],
                "",
                "Native Steam command: not ready until all required mods are installed.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Native Steam command:",
                report.native_command_text,
            ]
        )
    return redact_support_text("\n".join(lines))


def _format_native_launch_preview_report(
    report: NativeLaunchParityReport,
    generated_at: datetime | None = None,
) -> str:
    preview = report.preview
    install = report.install
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    lines = [
        "Native launch preview report",
        f"Generated at: {timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat()}",
        "",
        "This preview did not launch Steam or DayZ.",
        "",
        "Validation checklist:",
        f"- Steam install setting: {_selected_steam_mode_label(report.selected_steam_mode)}",
        f"- Steam mode: {install_label(install)}",
        f"- Steam command: {steam_command_detail(install)}",
        f"- Steam running: {'yes' if install.running else 'no'}",
        f"- Steam root: {_path_text(install.root)}",
        f"- Steam library: {_path_text(install.steamapps)}",
        f"- DayZ path: {_path_text(install.dayz_dir)}",
        f"- Workshop path: {_path_text(install.workshop_dir)}",
        f"- Server: {preview.server.name}",
        f"- Resolved connect: {report.resolved_connect}",
        f"- Query port: {preview.server.query_port}",
        f"- Required mod count: {len(report.required_mod_ids)}",
        f"- Prepared Workshop paths: {len(preview.mod_setup.prepared_mods)}",
        f"- Missing Workshop directories: {len(preview.mod_setup.missing_mod_ids)}",
        f"- Native ready: {'yes' if preview.ready else 'no'}",
        "",
    ]
    if report.required_mod_ids:
        lines.append("Required Workshop mods:")
        lines.extend(f"- {label}" for label in report.required_mod_labels)
    else:
        lines.append("Required Workshop mods: none")
    lines.append("")
    if preview.mod_setup.prepared_mods:
        lines.append("Native Workshop paths:")
        for prepared in preview.mod_setup.prepared_mods:
            lines.append(f"- {prepared.name} ({prepared.workshop_id}) -> {prepared.link_name}")
    else:
        lines.append("Native Workshop paths: none")
    if preview.mod_setup.missing_mod_ids:
        lines.extend(
            [
                "",
                "Missing Workshop mod directories:",
                *[f"- {label}" for label in report.missing_mod_labels],
                "",
                "Native Steam command: not ready until all required mods are installed.",
            ]
        )
    else:
        lines.extend(["", "Native Steam command:", report.native_command_text])
    return redact_support_text("\n".join(lines))


def format_native_launch_unavailable_context(
    install: SteamInstall,
    server: Server,
    player_name: str,
    selected_steam_mode: str,
) -> str:
    """Return copyable context when a full native parity report cannot be built."""
    return redact_support_text(
        "\n".join(
            [
                "Selected native launch context:",
                f"- Steam install setting: {steam_mode_label(selected_steam_mode)}",
                f"- Detected Steam install: {install_label(install)}",
                f"- Steam command: {steam_command_detail(install)}",
                f"- Steam running: {'yes' if install.running else 'no'}",
                f"- DayZ path: {_path_text(install.dayz_dir)}",
                f"- Workshop path: {_path_text(install.workshop_dir)}",
                f"- Server: {server.name}",
                f"- Connect target: {server.host}:{server.game_port}",
                f"- Query port: {server.query_port}",
                f"- Player name: {player_name}",
            ]
        )
    )


def native_launch_failure_details(
    install: SteamInstall,
    launcher_path: str,
    server: Server,
    player_name: str,
    required_mods: list[RequiredMod] | None,
    selected_steam_mode: str,
) -> str:
    """Build the best copyable diagnostic context available after native preflight fails."""
    if required_mods is None:
        return (
            "Native launch parity report unavailable.\n\n"
            f"{format_native_launch_unavailable_context(install, server, player_name, selected_steam_mode)}\n\n"
            "Run Check selected server mods successfully before launching to include required Workshop IDs "
            "and prepared mod-link details in launch failure reports."
        )
    try:
        report = prepare_native_launch_parity_report(
            install,
            launcher_path,
            server,
            player_name,
            required_mods,
            selected_steam_mode=selected_steam_mode,
        )
    except NativeLaunchError as detail_error:
        text = (
            "Native launch parity report unavailable.\n\n"
            f"Report generation failed during {detail_error.stage}: {detail_error.user_message()}"
        )
        if detail_error.details:
            text = f"{text}\n\n{detail_error.details}"
        return text
    return format_native_launch_parity_report(report)


def prepare_mod_links(
    dayz_dir: Path, workshop_dir: Path, required_mods: list[RequiredMod]
) -> NativeModSetup:
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
        strategy = current_platform().capabilities.mod_link_strategy
        if strategy == "relative_symlink":
            created = _ensure_relative_symlink(mod_path, link_path)
            launch_reference = compact_name
        elif strategy == "absolute_path":
            created = False
            link_path = mod_path
            launch_reference = str(mod_path)
        else:
            raise NativeLaunchError(
                f"Unsupported mod launch strategy: {strategy}",
                stage="mod setup",
                guidance="Use a supported WolfLauncher platform backend.",
            )
        setup.mod_links.append(launch_reference)
        setup.prepared_mods.append(
            PreparedModLink(
                workshop_id=workshop_id,
                name=mod_name,
                source_path=mod_path,
                link_path=link_path,
                link_name=launch_reference,
                created=created,
            )
        )

    return setup


def _steam_command_prefix(install: SteamInstall) -> list[str]:
        if not install.executable:
            if install.mode == "STEAM_ROOT env":
                guidance = (
                    "STEAM_ROOT points WolfLauncher at a Steam library, but the native Steam executable "
                    "was not found. Install native Steam or make the steam command available on PATH."
                )
            else:
                guidance = (
                    "Install native Steam, make the steam command available on PATH, "
                    "then select Auto, Flatpak Steam, or Snap Steam."
                )
            raise NativeLaunchError(
                f"{install.mode} Steam executable not detected",
                stage="Steam detection",
                guidance=guidance,
            )
        
        # Handle flatpak steam
        if install.executable == "flatpak":
            return ["flatpak", "run", *FLATPAK_PARAMS, "com.valvesoftware.Steam"]
        
        return [install.executable]


def _require_dir(path: Path | None, label: str) -> Path:
    if not path or not path.is_dir():
        if label == "DayZ install":
            guidance = (
                "Check Settings health and confirm DayZ is installed in the selected Steam library."
            )
        elif label == "DayZ Workshop":
            guidance = (
                "Check Settings health and confirm the DayZ Workshop folder is visible for the selected Steam library. "
                "If DayZ is installed but no Workshop folder appears, subscribe to at least one DayZ Workshop item "
                "and let Steam finish downloading it."
            )
        else:
            guidance = (
                "Check Settings health and confirm the selected Steam library paths are detected."
            )
        raise NativeLaunchError(
            f"{label} directory not detected",
            stage="Steam library detection",
            guidance=guidance,
        )
    return path


def _path_text(path: Path | None) -> str:
    return str(path) if path else "not detected"


def _selected_steam_mode_label(selected_steam_mode: str) -> str:
    labels = {
        "auto": "Auto",
        "native": "Native Steam",
        "STEAM_ROOT env": "STEAM_ROOT Steam library",
        "steam_root": "STEAM_ROOT Steam library",
    }
    return labels.get(selected_steam_mode, "not recorded")


def _created_mod_link_count(mod_setup: NativeModSetup) -> int:
    return sum(1 for prepared in mod_setup.prepared_mods if prepared.created)


def _reused_mod_link_count(mod_setup: NativeModSetup) -> int:
    return sum(1 for prepared in mod_setup.prepared_mods if not prepared.created)


def _parity_result_text(report: NativeLaunchParityReport) -> str:
    preview = report.preview
    external_note = ""
    if report.external_error:
        external_note = f" External launcher comparison is unavailable: {report.external_error}"
    if preview.ready:
        return (
            f"Native command is ready for {report.resolved_connect} with "
            f"{len(preview.mod_setup.prepared_mods)} prepared mod link(s)."
            f"{external_note}"
        )
    return (
        "Native command is not ready because "
        f"{len(preview.mod_setup.missing_mod_ids)} Workshop director"
        f"{'y is' if len(preview.mod_setup.missing_mod_ids) == 1 else 'ies are'} missing."
        f"{external_note}"
    )


def _external_readiness_text(report: NativeLaunchParityReport) -> str:
    if report.external_command:
        return "ready; command can be handed to the configured external launcher"
    return f"unavailable; {report.external_error or 'external launcher command could not be built'}"


def _native_readiness_text(report: NativeLaunchParityReport) -> str:
    preview = report.preview
    if preview.ready:
        return f"ready; {len(preview.mod_setup.prepared_mods)} local Workshop link(s) prepared"
    return (
        "blocked; "
        f"{len(preview.mod_setup.missing_mod_ids)} required Workshop director"
        f"{'y is' if len(preview.mod_setup.missing_mod_ids) == 1 else 'ies are'} missing"
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
    return {
        str(mod.workshop_id).strip(): mod.name.strip() for mod in required_mods if mod.name.strip()
    }


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
        actual_target_text = os.readlink(link_path)
        actual_target = Path(actual_target_text)
        expected_target_text = os.path.relpath(target, start=link_path.parent)
        expected_target = Path(expected_target_text)
        actual_resolved = link_path.resolve(strict=False)
        expected_resolved = target.resolve(strict=False)
        if actual_target == expected_target or actual_resolved == expected_resolved:
            return False
        raise NativeLaunchError(
            f"Mod link path already exists but points somewhere else: {link_path}",
            stage="mod setup",
            guidance=(
                "Remove the stale @mod symlink from the DayZ install directory, then prepare the native launch again."
            ),
            details="\n".join(
                [
                    "Stale @mod symlink conflict:",
                    f"- Link: {link_path}",
                    f"- Expected target: {expected_target_text}",
                    f"- Actual target: {actual_target_text}",
                    f"- Expected resolved path: {expected_resolved}",
                    f"- Actual resolved path: {actual_resolved}",
                ]
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
