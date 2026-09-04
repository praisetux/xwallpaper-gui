"""Integration with xrandr and xwallpaper."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess

from .constants import MODES


def outputs():
    if not shutil.which("xrandr") or not os.environ.get("DISPLAY"):
        return []
    try:
        result = subprocess.run(
            ["xrandr", "--query"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode:
        return []
    return [
        line.split()[0]
        for line in result.stdout.splitlines()
        if len(line.split()) > 1 and line.split()[1] == "connected"
    ]


def wallpaper_command(image, mode, output):
    if mode not in {item[0] for item in MODES}:
        raise ValueError("Invalid wallpaper layout")
    command = ["xwallpaper"]
    if output != "All displays":
        command += ["--output", output]
    return command + [f"--{mode}", str(image)]


XINIT_BEGIN = "# BEGIN xwallpaper-gui wallpaper"
XINIT_END = "# END xwallpaper-gui wallpaper"


def _remove_managed_block(lines):
    """Drop our block and the blank lines that separated it from its neighbours."""
    try:
        begin = lines.index(XINIT_BEGIN)
        end = lines.index(XINIT_END, begin + 1)
    except ValueError:
        return
    del lines[begin:end + 1]
    while begin < len(lines) and not lines[begin]:
        del lines[begin]
    while begin and not lines[begin - 1]:
        del lines[begin - 1]
        begin -= 1


def save_xinitrc_command(command, path=None):
    """Add or replace the wallpaper command managed by this application."""
    target = Path(path) if path is not None else Path.home() / ".xinitrc"
    try:
        existing = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = ""

    lines = existing.splitlines()
    _remove_managed_block(lines)

    while lines and not lines[-1]:
        lines.pop()
    block = [XINIT_BEGIN, shlex.join([str(item) for item in command]), XINIT_END]
    insertion = next(
        (index for index, line in enumerate(lines)
         if line.lstrip().startswith("exec ")),
        len(lines),
    )
    if insertion and lines[insertion - 1]:
        block.insert(0, "")
    if insertion < len(lines) and lines[insertion]:
        block.append("")
    lines[insertion:insertion] = block

    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def dwm_autostart_path():
    """Return the per-user autostart script used by current DWM releases."""
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return base / "dwm" / "autostart.sh"


def save_dwm_autostart_command(command, path=None):
    """Add or replace our command in DWM's non-blocking autostart script."""
    target = Path(path) if path is not None else dwm_autostart_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = "#!/bin/sh\n"

    lines = existing.splitlines()
    _remove_managed_block(lines)

    while lines and not lines[-1]:
        lines.pop()
    if lines:
        lines.append("")
    lines.extend([
        XINIT_BEGIN,
        shlex.join([str(item) for item in command]),
        XINIT_END,
    ])
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    target.chmod(target.stat().st_mode | 0o100)
