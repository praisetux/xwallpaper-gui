#!/usr/bin/env bash

set -eu

APP_NAME="xwallpaper-gui"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
INSTALL_PATH="$BIN_DIR/$APP_NAME"
DESKTOP_PATH="$APPLICATIONS_DIR/io.github.xwallpaper_gui.desktop"

usage() {
    printf 'Usage: %s [install|uninstall]\n' "$0"
}

refresh_menu() {
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
    fi
}

install_app() {
    if ! command -v python3 >/dev/null 2>&1; then
        printf 'Error: Python 3 is required.\n' >&2
        exit 1
    fi

    if ! python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" \
        >/dev/null 2>&1; then
        printf 'Error: GTK 3 and the Python PyGObject bindings are required.\n' >&2
        exit 1
    fi

    install -d "$BIN_DIR" "$APPLICATIONS_DIR"
    install -m 755 "$SCRIPT_DIR/xwallpaper-gui" "$INSTALL_PATH"

    sed "s|@EXEC@|$INSTALL_PATH|g" \
        "$SCRIPT_DIR/io.github.xwallpaper_gui.desktop.in" > "$DESKTOP_PATH"
    chmod 644 "$DESKTOP_PATH"
    refresh_menu

    printf 'Installed XWallpaper GUI.\n'
    printf 'Open your application menu and search for “XWallpaper GUI”.\n'
    if ! command -v xwallpaper >/dev/null 2>&1; then
        printf '\nNote: xwallpaper is not installed yet. The gallery will open, but\n'
        printf 'wallpapers cannot be applied until xwallpaper is installed.\n'
    fi
}

uninstall_app() {
    rm -f "$INSTALL_PATH" "$DESKTOP_PATH"
    refresh_menu
    printf 'Uninstalled XWallpaper GUI.\n'
    printf 'Saved preferences were left in your configuration directory.\n'
}

case "${1:-install}" in
    install) install_app ;;
    uninstall) uninstall_app ;;
    -h|--help) usage ;;
    *) usage >&2; exit 2 ;;
esac
