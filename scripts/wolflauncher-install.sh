#!/usr/bin/env bash
# WolfLauncher user-level installer (Linux, distro-neutral)
#
# Installs WolfLauncher into ~/.local so it works on every distro without
# touching system packages. Detects the distro family only to print helpful
# guidance about native Steam and optional system helpers.
#
# Usage:
#   ./wolflauncher-install.sh                # install (or update) from local checkout
#   Unpack the complete installer source archive before running this script.
#
# Environment overrides:
#   WOLFLAUNCHER_PREFIX       install prefix (default: $XDG_DATA_HOME/wolflauncher/runtime)
#   WOLFLAUNCHER_BIN_DIR      bin dir (default: $XDG_BIN_HOME or ~/.local/bin)
#   WOLFLAUNCHER_REPO         source dir override (default: script-adjacent checkout)
#   WOLFLAUNCHER_VERSION      force a version string in the launcher script
#   WOLFLAUNCHER_SKIP_SYSTEM  skip suggestions for apt/dnf/pacman/etc.
#   WOLFLAUNCHER_ASSUME_YES   assume yes for optional helpers
#
# Exit codes:
#   0 success, 1 user error, 2 missing dependency, 3 download failure
#
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

if [[ -t 1 ]]; then
  readonly C_RESET=$'\033[0m'
  readonly C_BOLD=$'\033[1m'
  readonly C_DIM=$'\033[2m'
  readonly C_RED=$'\033[31m'
  readonly C_GREEN=$'\033[32m'
  readonly C_YELLOW=$'\033[33m'
  readonly C_BLUE=$'\033[34m'
else
  readonly C_RESET="" C_BOLD="" C_DIM="" C_RED="" C_GREEN="" C_YELLOW="" C_BLUE=""
fi

log()   { printf '%s==>%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
ok()    { printf '%s  ✓%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn()  { printf '%s  !%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
err()   { printf '%s  ✗%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; }
hdr()   { printf '\n%s%s%s\n' "$C_BOLD" "$*" "$C_RESET"; }

die() {
  local code=$1; shift
  err "$*"
  exit "$code"
}

# ---------------------------------------------------------------------------
# Locate repo
# ---------------------------------------------------------------------------
script_path="${BASH_SOURCE[0]:-$0}"
if [[ "$script_path" = /* ]]; then
  script_dir="$(cd "$(dirname "$script_path")" && pwd)"
else
  script_dir="$(cd "$(pwd)/$(dirname "$script_path")" && pwd)"
fi

if [[ -n "${WOLFLAUNCHER_REPO:-}" ]]; then
  repo_dir="$WOLFLAUNCHER_REPO"
elif [[ -f "$script_dir/pyproject.toml" && -f "$script_dir/main.py" ]]; then
  repo_dir="$script_dir"
elif [[ -f "$script_dir/../pyproject.toml" && -f "$script_dir/../main.py" ]]; then
  repo_dir="$(cd "$script_dir/.." && pwd)"
else
  die 1 "Could not locate WolfLauncher checkout. Set WOLFLAUNCHER_REPO."
fi

[[ -f "$repo_dir/pyproject.toml" ]] || die 1 "pyproject.toml missing in $repo_dir"
[[ -f "$repo_dir/main.py" ]]        || die 1 "main.py missing in $repo_dir"

# ---------------------------------------------------------------------------
# Paths (XDG-aware, all user-local)
# ---------------------------------------------------------------------------
: "${XDG_DATA_HOME:=$HOME/.local/share}"
: "${XDG_BIN_HOME:=$HOME/.local/bin}"
: "${XDG_CONFIG_HOME:=$HOME/.config}"

prefix="${WOLFLAUNCHER_PREFIX:-$XDG_DATA_HOME/wolflauncher/runtime}"
bin_dir="${WOLFLAUNCHER_BIN_DIR:-$XDG_BIN_HOME}"
python_dir="$prefix/python"
node_dir="$prefix/node"
node_runtime_dir="$prefix/node-runtime"
app_dir="$prefix/app"
share_dir="$prefix/share"
log_dir="$prefix/log"

mkdir -p "$bin_dir" "$python_dir" "$node_dir" "$node_runtime_dir/bin" \
         "$app_dir" "$share_dir" "$log_dir" \
         "$XDG_DATA_HOME/applications" \
         "$XDG_DATA_HOME/icons/hicolor/scalable/apps" \
         "$XDG_CONFIG_HOME/wolflauncher"

# ---------------------------------------------------------------------------
# Distro detection (advisory only — never blocks install)
# ---------------------------------------------------------------------------
detect_distro() {
  local id="" like=""
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    id="${ID:-unknown}"
    like="${ID_LIKE:-}"
  fi
  case "$id:$like" in
    debian:*|ubuntu:*|*debian*)         echo "debian" ;;
    fedora:*|*rhel*|*fedora*)           echo "rhel"   ;;
    arch:*|*arch*)                      echo "arch"   ;;
    opensuse-*|sles:*|*suse*)           echo "suse"   ;;
    nixos:*|*nixos*)                    echo "nix"    ;;
    alpine:*|*alpine*)                  echo "alpine" ;;
    *)                                  echo "unknown" ;;
  esac
}

distro="$(detect_distro)"
python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die 2 "Required command '$1' not found. $2"
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

confirm() {
  local prompt="$1" default="${2:-N}"
  if [[ "${WOLFLAUNCHER_ASSUME_YES:-}" =~ ^[Yy] ]]; then return 0; fi
  local yn
  if [[ "$default" = "Y" ]]; then
    read -r -p "$prompt [Y/n] " yn || return 1
    [[ -z "$yn" || "$yn" =~ ^[Yy] ]]
  else
    read -r -p "$prompt [y/N] " yn || return 1
    [[ "$yn" =~ ^[Yy] ]]
  fi
}

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------
hdr "Checking prerequisites"
need_cmd python3 "Install Python 3.10+ from your distribution or https://python.org."

if [[ -z "$python_version" ]]; then
  die 2 "python3 is not usable."
fi

# Python >= 3.10
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
  die 2 "Python 3.10 or newer is required (found $python_version)."
fi
ok "python3 $python_version"

# Verify Qt platform deps via a dry-run of PySide6's loader only if available.
# We don't import PySide6 here — that happens later. We just record what we
# expect so we can warn about missing system libs.
case "$distro" in
  debian) qt_pkg_hint="libegl1 libxcb-cursor0 libxkbcommon0 libdbus-1-3" ;;
  rhel)   qt_pkg_hint="mesa-libEGL libxkbcommon dbus-libs" ;;
  arch)   qt_pkg_hint="libegl libxkbcommon libxcursor dbus" ;;
  suse)   qt_pkg_hint="libEGL1 libxkbcommon0 libdbus-1-3" ;;
  alpine) qt_pkg_hint="mesa-egl libxkbcommon dbus-libs" ;;
  *)      qt_pkg_hint="" ;;
esac
if [[ -n "$qt_pkg_hint" ]]; then
  printf '  %snote:%s Qt dependencies vary by distro. If the GUI fails to start,\n' "$C_DIM" "$C_RESET"
  printf '        install these via your package manager: %s\n' "$qt_pkg_hint"
fi

# ---------------------------------------------------------------------------
# Find or fetch a working pip
# ---------------------------------------------------------------------------
ensure_pip() {
  if python3 -m pip --version >/dev/null 2>&1; then
    return 0
  fi
  warn "python3 -m pip missing; bootstrapping pip via ensurepip"
  if ! python3 -m ensurepip --upgrade >/dev/null 2>&1; then
    case "$distro" in
      debian|rhel|arch|suse|alpine)
        warn "ensurepip is disabled. Install python3-pip / python3-pipx from your package manager."
        ;;
      *)
        warn "ensurepip is disabled on this Python build. Install pip system-wide and re-run."
        ;;
    esac
    return 1
  fi
}

# ---------------------------------------------------------------------------
# Install Python deps into prefix/python
# ---------------------------------------------------------------------------
hdr "Installing Python runtime"
ensure_pip || die 2 "pip is not available."

# Allow transitive deps (PySide6_Essentials / Addons) to be resolved and
# downloaded. `--no-deps` is dropped here on purpose; subsequent install
# passes re-pin the runtime set without recompiling bytecode in place.
python3 -m pip install \
  --disable-pip-version-check \
  --no-compile \
  --upgrade \
  --target "$python_dir" \
  -r "$repo_dir/requirements.txt"

# Build a wheel from the local checkout, then install it into the target dir.
# This mirrors scripts/build-deb.sh and avoids `pip install <dir>` running
# setuptools under PEP 668 / PEP 639 isolation, which rejects the project
# metadata on newer setuptools.
if ! python3 -m build --help >/dev/null 2>&1; then
  log "Bootstrapping build toolchain into $python_dir"
  python3 -m pip install --disable-pip-version-check --no-compile \
    --target "$python_dir" \
    "build" "setuptools>=80" "wheel>=0.46" "pyproject_hooks" "packaging" \
    2>/dev/null \
    || warn "Could not bootstrap build toolchain; wheel build may error out."
fi
log "Building wheel from $repo_dir"
wheel_dir="$(mktemp -d)"
trap 'rm -rf "$wheel_dir"' EXIT
PYTHONPATH="$python_dir${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m build --wheel --no-isolation --outdir "$wheel_dir" "$repo_dir"
shopt -s nullglob
wheel_files=("$wheel_dir"/*.whl)
shopt -u nullglob
if [[ ${#wheel_files[@]} -eq 0 ]]; then
  die 2 "Build did not produce a wheel in $wheel_dir"
fi
wheel_path="${wheel_files[0]}"

python3 -m pip install \
  --disable-pip-version-check \
  --no-compile \
  --upgrade \
  --target "$python_dir" \
  "$wheel_path"

ok "Python runtime installed at $python_dir"

# ---------------------------------------------------------------------------
# Install bundled Node + GameDig so status checks work even without npm
# ---------------------------------------------------------------------------
hdr "Installing Node.js runtime and GameDig"

node_version="20.20.2"
node_arch=""
node_sha=""
case "$(uname -m)" in
  x86_64|amd64)  node_arch="x64";   node_sha="df770b2a6f130ed8627c9782c988fda9669fa23898329a61a871e32f965e007d" ;;
  aarch64|arm64) node_arch="arm64"; node_sha="73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71" ;;
  *)
  warn "Unknown CPU architecture $(uname -m). Falling back to system node if available."
  ;;
esac

if [[ -n "$node_arch" && -z "${WOLFLAUNCHER_SKIP_NODE:-}" ]]; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$wheel_dir" "$tmp"' EXIT
  archive="$tmp/node-v${node_version}-linux-${node_arch}.tar.xz"
  url="https://nodejs.org/dist/v${node_version}/node-v${node_version}-linux-${node_arch}.tar.xz"

  log "Downloading Node.js $node_version ($node_arch)"
  if command -v curl >/dev/null 2>&1; then
    if ! curl -fsSL --retry 3 -o "$archive" "$url"; then
      warn "Failed to download $url. Falling back to system node if available."
      archive=""
    fi
  elif command -v wget >/dev/null 2>&1; then
    if ! wget -q -O "$archive" "$url"; then
      warn "Failed to download $url. Falling back to system node if available."
      archive=""
    fi
  else
    die 2 "Either curl or wget is required."
  fi

  if [[ -n "$archive" && -s "$archive" ]]; then
    if printf '%s  %s\n' "$node_sha" "$archive" | sha256sum --check --status; then
      tar -xJf "$archive" -C "$tmp"
      cp -R "$tmp/node-v${node_version}-linux-${node_arch}/." "$node_runtime_dir/"
      export PATH="$node_runtime_dir/bin:$PATH"
      ok "Node.js installed at $node_runtime_dir/bin/node"
    else
      warn "Node.js archive hash mismatch — refusing to use it. Falling back to system node."
    fi
  fi
elif [[ -n "$node_arch" && -n "${WOLFLAUNCHER_SKIP_NODE:-}" ]]; then
  log "Skipping Node.js download (WOLFLAUNCHER_SKIP_NODE=1)"
fi

if have_cmd node; then
  ok "node available: $(command -v node)"
elif [[ ! -x "$node_runtime_dir/bin/node" ]]; then
  warn "node was not found. Install nodejs via your package manager; the launcher will still run but live server status checks will be disabled."
fi

# Install the pinned GameDig node modules
if [[ -f "$repo_dir/packaging/npm/package.json" ]]; then
  install -m 0644 "$repo_dir/packaging/npm/package.json" "$node_dir/"
  install -m 0644 "$repo_dir/packaging/npm/package-lock.json" "$node_dir/"

  if [[ -n "${WOLFLAUNCHER_SKIP_GAMEDIG:-}" ]]; then
    log "Skipping GameDig installation (WOLFLAUNCHER_SKIP_GAMEDIG=1)"
  elif have_cmd npm; then
    log "Installing GameDig via npm (lockfile-pinned)"
    (cd "$node_dir" && npm ci --omit=dev --ignore-scripts --no-audit --no-fund --silent)
    ok "GameDig installed"
  else
    warn "npm unavailable; install Node.js and npm, then rerun to enable live status checks."
  fi
else
  warn "Repo is missing packaging/npm/package.json — skipping GameDig."
fi

# ---------------------------------------------------------------------------
# Vendored external dayz-launcher.sh (Linux fallback)
# ---------------------------------------------------------------------------
hdr "Vendoring external launcher fallback"
if [[ -f "$repo_dir/external/dayz-linux-cli-launcher/dayz-launcher.sh" ]]; then
  install -m 0755 -d "$share_dir/external"
  install -m 0755 "$repo_dir/external/dayz-linux-cli-launcher/dayz-launcher.sh" \
                 "$share_dir/external/dayz-launcher.sh"
  ok "External dayz-launcher.sh vendored"
else
  warn "external/dayz-linux-cli-launcher/dayz-launcher.sh missing — external launcher fallback will be unavailable."
fi

if [[ -f "$repo_dir/example.servers.yaml" ]]; then
  install -m 0644 "$repo_dir/example.servers.yaml" "$share_dir/"
fi

# ---------------------------------------------------------------------------
# Desktop entry + icon
# ---------------------------------------------------------------------------
hdr "Installing desktop entry"
if [[ -f "$repo_dir/packaging/linux/wolflauncher.desktop" ]]; then
  install -m 0644 "$repo_dir/packaging/linux/wolflauncher.desktop" \
                 "$XDG_DATA_HOME/applications/wolflauncher.desktop"
fi
if [[ -f "$repo_dir/packaging/linux/wolflauncher.svg" ]]; then
  install -m 0644 "$repo_dir/packaging/linux/wolflauncher.svg" \
                 "$XDG_DATA_HOME/icons/hicolor/scalable/apps/wolflauncher.svg"
fi
ok "Desktop entry installed (refresh icon cache or re-login if needed)"

# ---------------------------------------------------------------------------
# Launcher wrapper
# ---------------------------------------------------------------------------
hdr "Creating launcher command"
wrapper="$bin_dir/wolflauncher"
version="${WOLFLAUNCHER_VERSION:-$(python3 - <<PY
import sys, importlib.util
sys.path.insert(0, "$python_dir")
try:
    import wolflauncher as _wl
    print(_wl.__version__)
except Exception:
    spec = importlib.util.find_spec("wolflauncher")
    print(getattr(spec, "name", "0.0.0") if spec else "0.0.0")
PY
)}"
cat > "$wrapper" <<EOF
#!/usr/bin/env bash
# WolfLauncher $version (user install)
export WOLFLAUNCHER_SHARE_ROOT="$share_dir"
export PYTHONPATH="$python_dir\${PYTHONPATH:+:\$PYTHONPATH}"
export PATH="$node_runtime_dir/bin:$node_dir/node_modules/.bin:\${PATH:+\$PATH:}"
exec python3 -m wolflauncher "\$@"
EOF
chmod 0755 "$wrapper"
ok "Launcher created at $wrapper"

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
hdr "Verifying installation"
if [[ -n "${WOLFLAUNCHER_SKIP_VERIFY:-}" ]]; then
  log "Skipping launcher verify (WOLFLAUNCHER_SKIP_VERIFY=1)"
elif timeout 2 "$wrapper" --help >/dev/null 2>&1 || timeout 2 "$wrapper" --version >/dev/null 2>&1; then
  ok "Launcher responds"
elif timeout 2 "$wrapper" >/dev/null 2>&1 &
  then sleep 1; kill %1 2>/dev/null || true; ok "Launcher started"
else
  warn "Launcher did not respond to a quick smoke test. Run '$wrapper' to see the error."
fi

# ---------------------------------------------------------------------------
# Distro-specific follow-ups (advisory)
# ---------------------------------------------------------------------------
hdr "Distro-specific suggestions ($distro)"
case "$distro" in
  debian)
    cat <<D
  - Steam: install with 'sudo apt install steam' (enable the non-free/multiverse
    repo if needed) or use Flatpak ('flatpak install flathub com.valvesoftware.Steam').
  - Qt libs (sudo apt install): $qt_pkg_hint
D
    ;;
  rhel)
    cat <<D
  - Steam: enable RPM Fusion nonfree and 'sudo dnf install steam', or use Flatpak.
  - Qt libs (sudo dnf install): $qt_pkg_hint
D
    ;;
  arch)
    cat <<D
  - Steam: 'sudo pacman -S steam' or use Flatpak.
  - Qt libs (sudo pacman -S): $qt_pkg_hint
  - AUR users: a 'wolflauncher' AUR package can wrap this installer.
D
    ;;
  suse)
    cat <<D
  - Steam: 'sudo zypper install steam' (Packman/Education repos may be required),
    or use Flatpak.
  - Qt libs (sudo zypper install): $qt_pkg_hint
D
    ;;
  nix)
    cat <<D
  - Steam: enable 'programs.steam' in configuration.nix or use Flatpak.
  - Qt libs come from your system profile automatically.
D
    ;;
  alpine)
    cat <<D
  - Steam: not officially supported on Alpine; Flatpak may work in a non-musl chroot.
  - Qt libs (sudo apk add): $qt_pkg_hint
D
    ;;
  *)
    cat <<D
  - Install Steam via your distribution's package manager or Flatpak.
  - If the GUI fails to start, install: $qt_pkg_hint
D
    ;;
esac

cat <<D

Installation complete.

  Launch:      $wrapper
  Data dir:    $prefix
  Config dir:  $XDG_CONFIG_HOME/wolflauncher
  Uninstall:   ./scripts/wolflauncher-uninstall.sh

Make sure '$bin_dir' is on your PATH (most distros add ~/.local/bin automatically).
D
