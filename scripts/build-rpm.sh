#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python_bin="${PYTHON:-python3}"
version="$("$python_bin" -c 'from wolflauncher import __version__; print(__version__)')"
[[ "$(uname -m)" == x86_64 ]] || { echo "RPM builds require x86_64" >&2; exit 1; }
# Reuse only when the caller built this AppDir from the same checkout in this job.
if [[ "${WOLFLAUNCHER_REUSE_APPDIR:-0}" != 1 ]]; then
  PYTHON="$python_bin" bash scripts/build-appimage.sh
fi
appdir="$repo_root/build/appimage/WolfLauncher.AppDir"
test -x "$appdir/usr/lib/wolflauncher/WolfLauncher"
top="$repo_root/build/rpm"
mkdir -p "$top"
cat > "$top/wolflauncher.spec" <<EOF
%global __os_install_post %{nil}
%global debug_package %{nil}
Name: wolflauncher
Version: $version
Release: 1
Summary: DayZ server launcher
License: AGPL-3.0-only
URL: https://github.com/DrakonWolfDev/WolfLauncher
BuildArch: x86_64
AutoReqProv: no
Requires: glibc >= 2.39
Requires: libglvnd-egl, libglvnd-glx, libglvnd-opengl, libxkbcommon, libxkbcommon-x11, libxcb, xcb-util-cursor, xcb-util-wm, xcb-util-keysyms, dbus-libs, fontconfig, freetype, glib2, libX11, libXext, libXrender, libXi, libSM, libICE

%description
Steam and Workshop-aware DayZ server launcher with bundled Python, Qt and Node.js.

%install
mkdir -p "%{buildroot}/usr"
cp -a "$appdir/usr/." "%{buildroot}/usr/"
install -Dm755 "$top/wolflauncher" "%{buildroot}/usr/bin/wolflauncher"
mkdir -p "%{buildroot}/usr/share/doc/wolflauncher"
cp "$repo_root/LICENSE" "$repo_root/COPYRIGHT" "$repo_root/THIRD_PARTY_NOTICES.md" "%{buildroot}/usr/share/doc/wolflauncher/"

%files
/usr/lib/wolflauncher
/usr/bin/wolflauncher
/usr/share/applications/wolflauncher.desktop
/usr/share/icons/hicolor/scalable/apps/wolflauncher.svg
/usr/share/doc/wolflauncher
EOF
cat > "$top/wolflauncher" <<'EOF'
#!/bin/sh
exec /usr/lib/wolflauncher/WolfLauncher "$@"
EOF
rpmbuild -bb --define "_topdir $top" "$top/wolflauncher.spec"
artifact="$repo_root/dist/wolflauncher-${version}-1.x86_64.rpm"
cp "$top/RPMS/x86_64/wolflauncher-${version}-1.x86_64.rpm" "$artifact"
rpm -qip "$artifact"
(cd "$repo_root/dist" && sha256sum "$(basename "$artifact")") > "$artifact.sha256"
printf '%s\n' "$artifact"
