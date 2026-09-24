# XWallpaper GUI

A lightweight Python/GTK wallpaper browser for Linux. Choose a folder, browse
its images in a thumbnail gallery, and apply one using `xwallpaper`.

![XWallpaper GUI browsing and applying a desktop wallpaper](screenshots/xwallpaper-gui.png)

## Features

- Remembers the chosen wallpaper folder.
- Shows PNG and JPEG files supported by `xwallpaper` in a responsive grid.
- Can include subfolders.
- Applies the selected thumbnail with a button or double-click.
- Supports all displays or one display detected through `xrandr`.
- Offers zoom, maximize, stretch, centre, and tile layouts.
- Saves the last wallpaper, layout, display, and folder.
- Adds the selected `xwallpaper` command to an existing `~/.xinitrc` so it is
  restored when an X11 session is started with `startx`.
- Adds the command to DWM's per-user autostart script, including when DWM is
  passed directly to `startx` and `~/.xinitrc` is bypassed.
- Supports non-interactive restoration with `--restore` for other startup systems.

The app does not copy, move, or modify wallpaper files.

## Install

In an **X11 session**, open a terminal and run:

```sh
git clone https://github.com/praisetux/xwallpaper-gui.git
cd xwallpaper-gui
./install.sh
```

Run `./install.sh` as your normal user, **without `sudo`**. It checks the
requirements and installs the app for your account. If dependencies are
missing, it offers to install them on Debian, Ubuntu, Linux Mint, and Arch-based
systems; this step may ask for your administrator password.

When you see **Ready!**, open **XWallpaper GUI** from your application menu,
or use the launch command printed by the installer.

If you don't have Git, download the repository using GitHub's **Code → Download
ZIP**, extract it, and run `./install.sh` from the extracted folder.

### Troubleshooting

- Run `./install.sh check` to see missing requirements and installation guidance.
- On other distributions, install the listed dependencies using your package manager.
- If the app hasn't appeared in your menu yet, use the printed launch command.
- XWallpaper GUI requires X11; it cannot set a Wayland desktop's wallpaper.

The app itself is installed from this repository, not a distribution package.
The executable is stored in `~/.local/bin`, and the modules and menu entry are
stored under `~/.local/share` (or your configured XDG locations).

### Update

From the cloned `xwallpaper-gui` folder, update the source and installed app
with one command:

```sh
./install.sh update
```

The updater fast-forwards the Git checkout and installs the refreshed files.
It stops without changing anything if the checkout contains uncommitted work.
If you downloaded a ZIP, download a fresh copy and run its `./install.sh` again.

### Requirements

- An X11 session (`xwallpaper` is an X11 application)
- Python 3, GTK 3, and PyGObject
- `xwallpaper`
- `xrandr`

To remove the executable and menu entry:

```sh
./install.sh uninstall
```

Uninstalling keeps saved wallpaper preferences.

Each successful Apply updates a marked block when `~/.xinitrc` already exists.
Existing content is preserved and repeated changes replace that block rather
than adding duplicate commands. The app deliberately does not create this file:
a wallpaper-only `~/.xinitrc` would override the system startup script and leave
`startx` without a desktop session to launch.

The same marked block is written to
`$XDG_DATA_HOME/dwm/autostart.sh` (normally
`~/.local/share/dwm/autostart.sh`) and the script is made executable. This is
used by DWM even when it is launched as an explicit `startx` client.

Desktop environments that do not read `~/.xinitrc` can instead run this command
from their own startup configuration:

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
- Very large or remote wallpaper collections may take time to scan, but scanning
  and thumbnail decoding run in the background so the interface stays usable.

## AI Notice

AI-assisted tools were used during the development of this project.
