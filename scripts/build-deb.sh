#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python_bin="${PYTHON:-$repo_root/.venv/bin/python}"
version="$($python_bin -c 'from wolflauncher import __version__; print(__version__)')"
debian_version="${version/.dev0/~dev0}"
architecture="$(dpkg --print-architecture)"
package_root="$repo_root/build/deb/wolflauncher_${debian_version}_${architecture}"
python_root="$package_root/usr/lib/wolflauncher/python"
node_root="$package_root/usr/lib/wolflauncher/node"

rm -rf "$repo_root/build/deb"
mkdir -p \
  "$package_root/DEBIAN" \
  "$package_root/usr/bin" \
  "$python_root" \
  "$node_root" \
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

install -m 0644 packaging/npm/package.json packaging/npm/package-lock.json "$node_root/"
npm ci --prefix "$node_root" --omit=dev --ignore-scripts

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
export PATH="/usr/lib/wolflauncher/node/node_modules/.bin:$PATH"
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
Depends: python3 (>= 3.10), nodejs (>= 18)
Installed-Size: $installed_size
Maintainer: WolfLauncher contributors
Homepage: https://github.com/DrakonWolfDev/WolfLauncher
Description: Linux-first DayZ launcher
 Native Steam and Workshop-aware DayZ server launcher for Linux.
EOF

mkdir -p "$repo_root/dist"
artifact="$repo_root/dist/wolflauncher_${debian_version}_${architecture}.deb"
dpkg-deb --root-owner-group --build "$package_root" "$artifact"
sha256sum "$artifact" > "$artifact.sha256"
printf '%s\n' "$artifact"
