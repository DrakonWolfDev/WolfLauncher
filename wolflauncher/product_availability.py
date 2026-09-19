"""Product-specific installation snapshots. Detection never starts Steam or DayZ."""

from dataclasses import dataclass

from .dayz_product import EXPERIMENTAL, STABLE, DayZProduct
from .platform_detection import (
    SteamInstall,
    detect_steam,
    parse_appmanifest_installdir,
    select_steam_install,
)

EXPERIMENTAL_SETUP = (
    "Install DayZ Experimental from your Steam Library. Launch it through Steam once "
    "to complete initial and BattlEye setup, close the game, then Rescan installations. "
    "Finding the installation does not verify that first-run setup is complete."
)


@dataclass(frozen=True)
class ProductAvailability:
    product: DayZProduct
    state: str
    detail: str
    install: SteamInstall | None
    candidates: tuple[SteamInstall, ...] = ()

    @property
    def detected(self) -> bool:
        return self.state == "detected"


def inspect_install(install: SteamInstall | None, product: DayZProduct) -> ProductAvailability:
    if install is None or not (install.root or install.executable):
        return ProductAvailability(product, "steam_missing", "Steam was not detected.", install)
    if install.product != product:
        return ProductAvailability(
            product, "error", "Installation belongs to another edition.", install
        )
    try:
        if not install.dayz_dir:
            return ProductAvailability(
                product, "missing", f"{product.label} is not installed.", install
            )
        folder = install.dayz_dir
        folder.stat()  # distinguish missing/inaccessible paths
        manifest = folder.parent.parent / f"appmanifest_{product.client_app_id}.acf"
        text = manifest.read_text(encoding="utf-8")
        install_name = parse_appmanifest_installdir(text)
        if (
            not install_name
            or (manifest.parent / "common" / install_name).resolve() != folder.resolve()
        ):
            return ProductAvailability(
                product, "incomplete", "Steam manifest does not match the game directory.", install
            )
        for name in ("DayZ_x64.exe", "DayZ_BE.exe"):
            executable = folder / name
            if not executable.is_file():
                return ProductAvailability(
                    product,
                    "incomplete",
                    f"Missing {name}. Complete or verify the installation in Steam.",
                    install,
                )
        return ProductAvailability(
            product, "detected", f"Detected at {folder}. First-run setup is not verified.", install
        )
    except FileNotFoundError:
        return ProductAvailability(
            product,
            "incomplete",
            "Game files or the Steam manifest are missing. Complete installation in Steam.",
            install,
        )
    except OSError as exc:
        return ProductAvailability(
            product, "error", f"Could not inspect the installation: {exc}", install
        )


def scan_availability(mode: str, detector=None) -> dict[str, ProductAvailability]:
    detector = detector or detect_steam
    result = {}
    for product in (STABLE, EXPERIMENTAL):
        try:
            candidates = detector(product)
            selected = select_steam_install(mode, candidates)
            state = inspect_install(selected, product)
            result[product.key] = ProductAvailability(
                product, state.state, state.detail, selected, tuple(candidates)
            )
        except (OSError, ValueError) as exc:
            result[product.key] = ProductAvailability(product, "error", str(exc), None)
    return result


def installation_key(install: SteamInstall) -> tuple:
    return (
        install.product.key,
        install.mode,
        str(install.root),
        str(install.dayz_dir),
        str(install.workshop_dir),
    )


def installation_still_present(install: SteamInstall) -> bool:
    return inspect_install(install, install.product).detected


def setup_message(product: DayZProduct, detail: str = "") -> str:
    instructions = (
        EXPERIMENTAL_SETUP
        if product.experimental
        else (
            "Install DayZ from your Steam Library, launch it through Steam once, close it, then Rescan installations."
        )
    )
    return f"{detail}\n\n{instructions}".strip()
