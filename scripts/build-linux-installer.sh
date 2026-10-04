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

version="$($python_bin -c 'from wolflauncher import __version__; print(__version__)')"
case "$(uname -m)" in
  x86_64|amd64) architecture="x86_64" ;;
  aarch64|arm64) architecture="aarch64" ;;
  *) echo "Unsupported Linux installer architecture: $(uname -m)" >&2; exit 1 ;;
esac

appimage="${WOLFLAUNCHER_APPIMAGE_PATH:-$repo_root/dist/WolfLauncher-${version}-${architecture}.AppImage}"
if [[ ! -f "$appimage" ]]; then
  "$repo_root/scripts/build-appimage.sh"
fi
[[ -f "$appimage" ]] || { echo "AppImage was not produced: $appimage" >&2; exit 1; }

bundle_name="WolfLauncher-${version}-linux-${architecture}"
stage_root="$repo_root/build/linux-installer"
bundle_root="$stage_root/$bundle_name"
archive="$repo_root/dist/${bundle_name}-installer.tar.gz"

rm -rf "$stage_root"
mkdir -p "$bundle_root" "$repo_root/dist"
install -m 0755 "$appimage" "$bundle_root/$(basename "$appimage")"
install -m 0755 scripts/wolflauncher-install.sh "$bundle_root/install.sh"
install -m 0755 scripts/wolflauncher-uninstall.sh "$bundle_root/uninstall.sh"
install -m 0644 packaging/linux/wolflauncher.desktop "$bundle_root/wolflauncher.desktop"
install -m 0644 packaging/linux/wolflauncher.svg "$bundle_root/wolflauncher.svg"
install -m 0644 docs/INSTALL_LINUX.md "$bundle_root/INSTALL.md"
install -m 0644 LICENSE COPYRIGHT THIRD_PARTY_NOTICES.md "$bundle_root/"

rm -f "$archive" "$archive.sha256"
tar -czf "$archive" -C "$stage_root" "$bundle_name"
(cd "$repo_root/dist" && sha256sum "$(basename "$archive")") > "$archive.sha256"
printf '%s\n' "$archive"
