import os
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)


project_root = Path(SPECPATH).parents[1]
version_text = (project_root / "wolflauncher" / "__init__.py").read_text(encoding="utf-8")
version = re.search(r'__version__\s*=\s*"([^"]+)"', version_text).group(1)
numeric_version = [int(value) for value in re.findall(r"\d+", version)[:3]]
numeric_version.extend([0] * (4 - len(numeric_version)))
version_tuple = tuple(numeric_version[:4])

node_executable = Path(os.environ["WOLFLAUNCHER_NODE_EXE"]).resolve()
node_modules = Path(os.environ["WOLFLAUNCHER_NODE_MODULES"]).resolve()
icon_path = Path(os.environ["WOLFLAUNCHER_ICON_PATH"]).resolve()
for required_path in (node_executable, node_modules, icon_path):
    if not required_path.exists():
        raise SystemExit(f"Required Windows packaging input is missing: {required_path}")

version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=version_tuple,
        prodvers=version_tuple,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "WolfLauncher contributors"),
                        StringStruct("FileDescription", "WolfLauncher DayZ launcher"),
                        StringStruct("FileVersion", version),
                        StringStruct("InternalName", "WolfLauncher"),
                        StringStruct("OriginalFilename", "WolfLauncher.exe"),
                        StringStruct("ProductName", "WolfLauncher"),
                        StringStruct("ProductVersion", version),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

datas = collect_data_files("wolflauncher")
datas.extend(
    [
        (str(project_root / "example.servers.yaml"), "share/wolflauncher"),
        (str(node_executable), "node-runtime"),
        (str(node_modules), "node/node_modules"),
    ]
)

hiddenimports = collect_submodules("keyring.backends")
hiddenimports.extend(
    collect_submodules(
        "win32ctypes", filter=lambda name: not name.startswith("win32ctypes.tests")
    )
)

analysis = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "packaging/windows/runtime_hook.py")],
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
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path),
    version=version_info,
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
