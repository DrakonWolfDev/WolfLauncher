import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_root = Path(SPECPATH).parents[1]
node_executable = Path(os.environ["WOLFLAUNCHER_NODE_EXE"]).resolve()
node_modules = Path(os.environ["WOLFLAUNCHER_NODE_MODULES"]).resolve()
for required_path in (node_executable, node_modules):
    if not required_path.exists():
        raise SystemExit(f"Required AppImage packaging input is missing: {required_path}")

datas = collect_data_files("wolflauncher")
datas.extend(
    [
        (str(project_root / "example.servers.yaml"), "share/wolflauncher"),
        (
            str(project_root / "external/dayz-linux-cli-launcher/dayz-launcher.sh"),
            "share/wolflauncher/external",
        ),
        (str(node_executable), "node-runtime"),
        (str(node_modules), "node/node_modules"),
    ]
)

analysis = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("keyring.backends"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "packaging/linux/runtime_hook.py")],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="WolfLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

bundle = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="WolfLauncher",
)
