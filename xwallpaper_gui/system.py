"""Integration with xrandr and xwallpaper."""

import os
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
