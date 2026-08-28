"""Command-line entry point and non-interactive wallpaper restoration."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .application import Application
from .settings import load_settings
from .system import outputs, wallpaper_command


def restore():
    settings = load_settings()
    image = Path(settings.get("last_wallpaper", ""))
    if not shutil.which("xwallpaper"):
        print("xwallpaper is not installed", file=sys.stderr)
        return 1
    if not os.environ.get("DISPLAY"):
        print("no X11 display was detected", file=sys.stderr)
        return 1
    if not image.is_file():
        print("the saved wallpaper no longer exists", file=sys.stderr)
        return 1
    output = settings.get("output", "All displays")
    if output != "All displays" and output not in outputs():
        print(f"the saved display is no longer connected: {output}", file=sys.stderr)
        return 1
    try:
        return subprocess.run(
            wallpaper_command(image, settings.get("mode", "zoom"), output),
            timeout=10,
        ).returncode
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(error, file=sys.stderr)
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Browse a folder of images and apply one using xwallpaper."
    )
    parser.add_argument(
        "--restore", action="store_true",
        help="apply the last wallpaper without opening the GUI",
    )
    args = parser.parse_args(argv)
    return restore() if args.restore else Application().run([])
