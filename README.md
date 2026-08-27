# XWallpaper GUI

A lightweight Python/GTK wallpaper browser for Linux. Choose a folder, browse
its images in a thumbnail gallery, and apply one using `xwallpaper`.

## Features

- Remembers the chosen wallpaper folder.
- Shows JPG, PNG, WebP, BMP, GIF, and TIFF files in a responsive grid.
- Can include subfolders.
- Applies the selected thumbnail with a button or double-click.
- Supports all displays or one display detected through `xrandr`.
- Offers zoom, maximize, stretch, centre, tile, and focus layouts.
- Saves the last wallpaper, layout, display, and folder.
- Supports non-interactive restoration with `--restore`.

The app does not copy, move, or modify wallpaper files.

## Requirements

- An X11 session (`xwallpaper` is an X11 application)
- Python 3, GTK 3, and PyGObject
- `xwallpaper`
- `xrandr` (optional; used to target one display)

Example installations:

```sh
# Debian or Ubuntu
sudo apt install xwallpaper python3-gi gir1.2-gtk-3.0 x11-xserver-utils

# Arch Linux
sudo pacman -S xwallpaper python-gobject gtk3 xorg-xrandr

# Fedora (package availability may vary)
sudo dnf install xwallpaper python3-gobject gtk3 xrandr
```

## Install and open from the application menu

```sh
./install.sh
```

Then open the desktop application menu and search for **XWallpaper GUI**. The
installer is user-local, does not use `sudo`, and installs:

- The executable at `~/.local/bin/xwallpaper-gui`.
- The menu launcher at
  `~/.local/share/applications/io.github.xwallpaper_gui.desktop`.

Some application menus take a few seconds to notice a newly installed launcher.
Log out and back in only if it still does not appear.

To remove the executable and menu entry:

```sh
./install.sh uninstall
```

Uninstalling keeps the saved wallpaper preferences. This machine already has
GTK and PyGObject, but `xwallpaper` is not currently installed. The gallery will
open, but applying requires that package.

To restore the most recently applied wallpaper at X11 login, add this command to
the desktop or window manager's startup configuration:

```sh
/absolute/path/to/xwallpaper-gui --restore
```

Settings are stored in
`$XDG_CONFIG_HOME/xwallpaper-gui/settings.json`, or
`~/.config/xwallpaper-gui/settings.json` when that variable is unset.

## Limitations

- X11 only.
- Different images can be applied to displays one at a time; there is no
  multi-display arrangement editor yet.
- A very large image or remote folder can briefly pause while one thumbnail is
  decoded, though thumbnails are loaded incrementally to keep the GUI updating.
