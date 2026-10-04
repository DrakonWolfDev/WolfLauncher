#!/usr/bin/env bash
# WolfLauncher user-level uninstaller (Linux)
#
# Removes the user-local installation created by wolflauncher-install.sh.
# Does NOT touch the user's settings, favourites or cached servers under
# ~/.config/wolflauncher unless --purge is passed.
#
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

: "${XDG_DATA_HOME:=$HOME/.local/share}"
: "${XDG_BIN_HOME:=$HOME/.local/bin}"
: "${XDG_CONFIG_HOME:=$HOME/.config}"

prefix="${WOLFLAUNCHER_PREFIX:-$XDG_DATA_HOME/wolflauncher/runtime}"
bin_dir="${WOLFLAUNCHER_BIN_DIR:-$XDG_BIN_HOME}"

PURGE=0
for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=1 ;;
    -h|--help)
      cat <<H
Usage: wolflauncher-uninstall.sh [--purge]

  --purge   also delete ~/.config/wolflauncher (settings, favourites, curated list)
H
      exit 0
      ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

if [[ -t 1 ]]; then
  readonly C_YELLOW=$'\033[33m' C_BLUE=$'\033[34m' C_RESET=$'\033[0m'
else
  readonly C_YELLOW="" C_BLUE="" C_RESET=""
fi
log()  { printf '%s==>%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
warn() { printf '%s  !%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }

removed_any=0

if [[ -e "$bin_dir/wolflauncher" ]]; then
  log "Removing launcher $bin_dir/wolflauncher"
  rm -f "$bin_dir/wolflauncher"
  removed_any=1
fi

if [[ -e "$bin_dir/wolflauncher-uninstall" ]]; then
  log "Removing uninstaller $bin_dir/wolflauncher-uninstall"
  rm -f "$bin_dir/wolflauncher-uninstall"
  removed_any=1
fi

if [[ -e "$prefix" ]]; then
  log "Removing installation at $prefix"
  rm -rf "$prefix"
  removed_any=1
fi

for f in "$XDG_DATA_HOME/applications/wolflauncher.desktop" \
         "$XDG_DATA_HOME/icons/hicolor/scalable/apps/wolflauncher.svg"; do
  if [[ -e "$f" ]]; then
    log "Removing $f"
    rm -f "$f"
  fi
done

if (( PURGE )); then
  cfg="$XDG_CONFIG_HOME/wolflauncher"
  if [[ -d "$cfg" ]]; then
    log "Purging $cfg (--purge)"
    rm -rf "$cfg"
  else
    warn "No config dir at $cfg"
  fi
else
  cat <<P
Preserving config at $XDG_CONFIG_HOME/wolflauncher (settings, favourites, curated list).
Re-run with --purge to remove them.
P
fi

if (( removed_any )); then
  log "Done."
else
  warn "No WolfLauncher installation was found."
fi
