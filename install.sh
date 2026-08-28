#!/usr/bin/env bash

set -eu

APP_NAME="xwallpaper-gui"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
APP_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/xwallpaper-gui"
INSTALL_PATH="$BIN_DIR/$APP_NAME"
DESKTOP_PATH="$APPLICATIONS_DIR/io.github.xwallpaper_gui.desktop"

usage() {
    printf 'Usage: %s [install|update|uninstall|check]\n' "$0"
}

dependency_status() {
    MISSING=""
    command -v python3 >/dev/null 2>&1 || MISSING="$MISSING python3"
    command -v xwallpaper >/dev/null 2>&1 || MISSING="$MISSING xwallpaper"
    command -v xrandr >/dev/null 2>&1 || MISSING="$MISSING xrandr"

    if command -v python3 >/dev/null 2>&1 &&
        ! python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" \
            >/dev/null 2>&1; then
        MISSING="$MISSING GTK/PyGObject"
    fi
}

dependency_command() {
    ID=""
    ID_LIKE=""
    if [ -r /etc/os-release ]; then
        # This system-owned file contains simple distribution identifiers.
        . /etc/os-release
    fi

    case " $ID $ID_LIKE " in
        *" arch "*)
            printf '%s' "sudo pacman -S --needed xwallpaper python-gobject gtk3 xorg-xrandr"
            ;;
        *" debian "*|*" ubuntu "*)
            printf '%s' "sudo apt-get install xwallpaper python3-gi gir1.2-gtk-3.0 x11-xserver-utils"
            ;;
        *)
            return 1
            ;;
    esac
}

check_dependencies() {
    dependency_status
    if [ -z "$MISSING" ]; then
        return 0
    fi

    printf 'Missing required components:%s\n' "$MISSING"
    if command=$(dependency_command); then
        printf '\nThese are system dependencies, not XWallpaper GUI itself.\n'
        printf 'Recommended command:\n  %s\n' "$command"
        if [ -t 0 ]; then
            printf '\nInstall these dependencies now? [y/N] '
            read -r answer
            case "$answer" in
                y|Y|yes|YES)
                    sh -c "$command"
                    dependency_status
                    ;;
            esac
        fi
    else
        printf '\nInstall Python 3, GTK 3 with PyGObject, xwallpaper, and xrandr\n'
        printf 'using your system package manager, then run this installer again.\n'
    fi

    if [ -n "$MISSING" ]; then
        printf '\nSetup stopped because the app would not be usable yet.\n' >&2
        return 1
    fi
}

refresh_menu() {
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
    fi
}

install_app() {
    check_dependencies

    install -d "$BIN_DIR" "$APPLICATIONS_DIR" "$APP_DATA_DIR/xwallpaper_gui"
    install -m 755 "$SCRIPT_DIR/xwallpaper-gui" "$INSTALL_PATH"
    for module in "$SCRIPT_DIR"/xwallpaper_gui/*.py; do
        install -m 644 "$module" "$APP_DATA_DIR/xwallpaper_gui/"
    done

    sed "s|@EXEC@|$INSTALL_PATH|g" \
        "$SCRIPT_DIR/io.github.xwallpaper_gui.desktop.in" > "$DESKTOP_PATH"
    chmod 644 "$DESKTOP_PATH"
    refresh_menu

    printf 'Installed XWallpaper GUI.\n'
    printf 'Open your application menu and search for “XWallpaper GUI”.\n'
}

update_app() {
    if ! command -v git >/dev/null 2>&1; then
        printf 'Git is required to update XWallpaper GUI.\n' >&2
        return 1
    fi
    if ! git -C "$SCRIPT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        printf 'This copy was not installed from a Git checkout.\n' >&2
        printf 'Download the latest release, then run its installer.\n' >&2
        return 1
    fi
    if [ -n "$(git -C "$SCRIPT_DIR" status --porcelain)" ]; then
        printf 'Update stopped because the source checkout has uncommitted changes:\n' >&2
        git -C "$SCRIPT_DIR" status --short >&2
        printf 'Commit or stash them, then run this command again.\n' >&2
        return 1
    fi

    printf 'Checking for XWallpaper GUI updates...\n'
    git -C "$SCRIPT_DIR" pull --ff-only
    install_app
}

uninstall_app() {
    rm -f "$INSTALL_PATH" "$DESKTOP_PATH"
    rm -rf "$APP_DATA_DIR"
    refresh_menu
    printf 'Uninstalled XWallpaper GUI.\n'
    printf 'Saved preferences were left in your configuration directory.\n'
}

case "${1:-install}" in
    install) install_app ;;
    update) update_app ;;
    uninstall) uninstall_app ;;
    check)
        dependency_status
        if [ -n "$MISSING" ]; then
            printf 'Missing:%s\n' "$MISSING"
            exit 1
        fi
        printf 'All required components are installed.\n'
        ;;
    -h|--help) usage ;;
    *) usage >&2; exit 2 ;;
esac
