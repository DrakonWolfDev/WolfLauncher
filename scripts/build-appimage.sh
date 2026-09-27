#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -n "${PYTHON:-}" ]]; then
  python_bin="$PYTHON"
elif [[ -x "$repo_root/venv/bin/python" ]]; then
  python_bin="$repo_root/venv/bin/python"
elif [[ -x "$repo_root/.venv/bin/python" ]]; then
  python_bin="$repo_root/.venv/bin/python"
else
  python_bin="$(command -v python3)"
fi

if ! "$python_bin" -c "import PyInstaller" 2>/dev/null; then
  echo "PyInstaller is missing. Install requirements-appimage.txt first." >&2
  exit 1
fi

version="$($python_bin -c 'from wolflauncher import __version__; print(__version__)')"
machine="$(uname -m)"
case "$machine" in
  x86_64)
    appimage_arch="x86_64"
    node_arch="x64"
    node_sha256="df770b2a6f130ed8627c9782c988fda9669fa23898329a61a871e32f965e007d"
    appimagetool_sha256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
    appimage_runtime_sha256="2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"
    ;;
  aarch64|arm64)
    echo "The aarch64 AppImage toolchain has not been checksum-pinned yet." >&2
    exit 1
    ;;
  *)
    echo "Unsupported AppImage architecture: $machine" >&2
    exit 1
    ;;
esac

node_version="20.20.2"
node_archive="$repo_root/dist/node-v${node_version}-linux-${node_arch}.tar.xz"
node_extract="$repo_root/build/node-v${node_version}-linux-${node_arch}"
appimagetool_version="1.9.1"
appimagetool="$repo_root/dist/appimagetool-${appimagetool_version}-${appimage_arch}.AppImage"
appimage_runtime_version="20251108"
appimage_runtime="$repo_root/dist/appimage-runtime-${appimage_runtime_version}-${appimage_arch}"
appdir="$repo_root/build/appimage/WolfLauncher.AppDir"
pyinstaller_dist="$repo_root/build/appimage/pyinstaller-dist"
pyinstaller_work="$repo_root/build/appimage/pyinstaller-work"
npm_root="$repo_root/build/appimage/npm"
artifact="$repo_root/dist/WolfLauncher-${version}-${appimage_arch}.AppImage"

mkdir -p "$repo_root/dist" "$repo_root/build"
if [[ ! -f "$node_archive" ]]; then
  curl -fsSL \
    "https://nodejs.org/dist/v${node_version}/node-v${node_version}-linux-${node_arch}.tar.xz" \
    -o "$node_archive"
fi
printf '%s  %s\n' "$node_sha256" "$node_archive" | sha256sum --check --status

if [[ ! -f "$appimagetool" ]]; then
  curl -fsSL \
    "https://github.com/AppImage/appimagetool/releases/download/${appimagetool_version}/appimagetool-${appimage_arch}.AppImage" \
    -o "$appimagetool"
fi
printf '%s  %s\n' "$appimagetool_sha256" "$appimagetool" | sha256sum --check --status
chmod 0755 "$appimagetool"

if [[ ! -f "$appimage_runtime" ]]; then
  curl -fsSL \
    "https://github.com/AppImage/type2-runtime/releases/download/${appimage_runtime_version}/runtime-${appimage_arch}" \
    -o "$appimage_runtime"
fi
printf '%s  %s\n' "$appimage_runtime_sha256" "$appimage_runtime" | \
  sha256sum --check --status

rm -rf "$repo_root/build/appimage" "$node_extract"
mkdir -p "$npm_root" "$appdir/usr/lib" "$appdir/usr/share/applications" \
  "$appdir/usr/share/icons/hicolor/scalable/apps"
tar -xJf "$node_archive" -C "$repo_root/build"
install -m 0644 packaging/npm/package.json packaging/npm/package-lock.json "$npm_root/"
PATH="$node_extract/bin:$PATH" "$node_extract/bin/npm" ci \
  --prefix "$npm_root" --omit=dev --ignore-scripts

export WOLFLAUNCHER_NODE_EXE="$node_extract/bin/node"
export WOLFLAUNCHER_NODE_MODULES="$npm_root/node_modules"
"$python_bin" -m PyInstaller --noconfirm --clean \
  --distpath "$pyinstaller_dist" \
  --workpath "$pyinstaller_work" \
  packaging/linux/WolfLauncher.spec

mv "$pyinstaller_dist/WolfLauncher" "$appdir/usr/lib/wolflauncher"
install -m 0644 packaging/linux/wolflauncher.desktop "$appdir/wolflauncher.desktop"
install -m 0644 packaging/linux/wolflauncher.desktop \
  "$appdir/usr/share/applications/wolflauncher.desktop"
install -m 0644 packaging/linux/wolflauncher.svg "$appdir/wolflauncher.svg"
install -m 0644 packaging/linux/wolflauncher.svg \
  "$appdir/usr/share/icons/hicolor/scalable/apps/wolflauncher.svg"
ln -s wolflauncher.svg "$appdir/.DirIcon"

cat > "$appdir/AppRun" <<'EOF'
#!/bin/sh
set -e
appdir="$(cd "$(dirname "$0")" && pwd)"
exec "$appdir/usr/lib/wolflauncher/WolfLauncher" "$@"
EOF
chmod 0755 "$appdir/AppRun"

rm -f "$artifact" "$artifact.sha256"
ARCH="$appimage_arch" VERSION="$version" \
  "$appimagetool" --appimage-extract-and-run \
  --runtime-file "$appimage_runtime" "$appdir" "$artifact"
chmod 0755 "$artifact"

smoke_root="$(mktemp -d)"
trap 'rm -rf "$smoke_root"' EXIT
XDG_CONFIG_HOME="$smoke_root/config" \
XDG_DATA_HOME="$smoke_root/data" \
QT_QPA_PLATFORM=offscreen \
WOLFLAUNCHER_SMOKE_TEST=1 \
  "$artifact" --appimage-extract-and-run

(cd "$repo_root/dist" && sha256sum "$(basename "$artifact")") > "$artifact.sha256"
chmod 0644 "$artifact.sha256"
printf '%s\n' "$artifact"
