#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -n "${PYTHON:-}" ]]; then
  python_bin="$PYTHON"
elif [[ -x "$repo_root/.venv/bin/python" ]]; then
  python_bin="$repo_root/.venv/bin/python"
else
  python_bin="$(command -v python3)"
fi
version="$($python_bin -c 'from wolflauncher import __version__; print(__version__)')"
debian_version="${version/.dev0/~dev0}"
architecture="$(dpkg --print-architecture)"
python_version="$($python_bin -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
python_next_minor="$($python_bin -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor + 1}")')"
artifact_label="${WOLFLAUNCHER_ARTIFACT_LABEL:-$architecture}"
package_root="$repo_root/build/deb/wolflauncher_${debian_version}_${architecture}"
python_root="$package_root/usr/lib/wolflauncher/python"
node_root="$package_root/usr/lib/wolflauncher/node"
node_runtime="$package_root/usr/lib/wolflauncher/node-runtime"

node_version="20.20.2"
case "$architecture" in
  amd64)
    node_arch="x64"
    node_sha256="df770b2a6f130ed8627c9782c988fda9669fa23898329a61a871e32f965e007d"
    ;;
  arm64)
    node_arch="arm64"
    node_sha256="73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71"
    ;;
  *)
    echo "Unsupported Node.js package architecture: $architecture" >&2
    exit 1
    ;;
esac
node_archive="$repo_root/dist/node-v${node_version}-linux-${node_arch}.tar.xz"

rm -rf "$repo_root/build/deb"
mkdir -p \
  "$package_root/DEBIAN" \
  "$package_root/usr/bin" \
  "$python_root" \
  "$node_root" \
  "$node_runtime/bin" \
  "$package_root/usr/share/applications" \
  "$package_root/usr/share/icons/hicolor/scalable/apps" \
  "$package_root/usr/share/wolflauncher/external" \
  "$package_root/usr/share/doc/wolflauncher"

"$python_bin" -m build --wheel --no-isolation
wheel_path="$repo_root/dist/wolflauncher-${version}-py3-none-any.whl"
"$python_bin" -m pip install \
  --disable-pip-version-check \
  --no-compile \
  --no-deps \
  --requirement "$repo_root/requirements-release.txt" \
  --target "$python_root"
"$python_bin" -m pip install \
  --disable-pip-version-check \
  --no-compile \
  --no-deps \
  --target "$python_root" \
  "$wheel_path"

mkdir -p "$repo_root/dist"
if [[ ! -f "$node_archive" ]]; then
  curl -fsSL \
    "https://nodejs.org/dist/v${node_version}/node-v${node_version}-linux-${node_arch}.tar.xz" \
    -o "$node_archive"
fi
printf '%s  %s\n' "$node_sha256" "$node_archive" | sha256sum --check --status
node_extract="$repo_root/build/node-v${node_version}-linux-${node_arch}"
tar -xJf "$node_archive" -C "$repo_root/build"
install -m 0755 "$node_extract/bin/node" "$node_runtime/bin/node"

install -m 0644 packaging/npm/package.json packaging/npm/package-lock.json "$node_root/"
PATH="$node_extract/bin:$PATH" "$node_extract/bin/npm" ci \
  --prefix "$node_root" --omit=dev --ignore-scripts

install -m 0644 packaging/linux/wolflauncher.desktop "$package_root/usr/share/applications/"
install -m 0644 packaging/linux/wolflauncher.svg \
  "$package_root/usr/share/icons/hicolor/scalable/apps/"
install -m 0644 example.servers.yaml "$package_root/usr/share/wolflauncher/"
install -m 0755 external/dayz-linux-cli-launcher/dayz-launcher.sh \
  "$package_root/usr/share/wolflauncher/external/"
install -m 0644 LICENSE THIRD_PARTY_NOTICES.md "$package_root/usr/share/doc/wolflauncher/"

cat > "$package_root/usr/bin/wolflauncher" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH="/usr/lib/wolflauncher/python${PYTHONPATH:+:$PYTHONPATH}"
export PATH="/usr/lib/wolflauncher/node-runtime/bin:/usr/lib/wolflauncher/node/node_modules/.bin:$PATH"
exec python3 -m wolflauncher "$@"
EOF
chmod 0755 "$package_root/usr/bin/wolflauncher"

# Package payloads must not inherit a developer's group-writable umask.
find "$package_root" -type d -exec chmod 0755 {} +
find "$package_root" -type f -exec chmod go-w {} +

installed_size="$(du -sk "$package_root/usr" | cut -f1)"
cat > "$package_root/DEBIAN/control" <<EOF
Package: wolflauncher
Version: $debian_version
Section: games
Priority: optional
Architecture: $architecture
Depends: python3 (>= $python_version), python3 (<< $python_next_minor)
Installed-Size: $installed_size
Maintainer: WolfLauncher contributors
Homepage: https://github.com/DrakonWolfDev/WolfLauncher
Description: Linux-first DayZ launcher
 Native Steam and Workshop-aware DayZ server launcher for Linux.
EOF

artifact="$repo_root/dist/wolflauncher_${debian_version}_${artifact_label}_${architecture}.deb"
dpkg-deb --root-owner-group --build "$package_root" "$artifact"
(cd "$repo_root/dist" && sha256sum "$(basename "$artifact")") > "$artifact.sha256"
printf '%s\n' "$artifact"
