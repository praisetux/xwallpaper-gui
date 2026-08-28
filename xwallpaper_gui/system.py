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


def save_xinitrc_command(command, path=None):
    """Add or replace the wallpaper command managed by this application."""
    target = Path(path) if path is not None else Path.home() / ".xinitrc"
    try:
        existing = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = ""

    lines = existing.splitlines()
    try:
        begin = lines.index(XINIT_BEGIN)
        end = lines.index(XINIT_END, begin + 1)
    except ValueError:
        pass
    else:
        del lines[begin:end + 1]

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
