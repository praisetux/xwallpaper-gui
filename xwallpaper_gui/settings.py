"""Load and persist user preferences."""

import json
import os
from pathlib import Path

from .constants import MODES


def settings_path():
    configured = os.environ.get("XDG_CONFIG_HOME")
    base = Path(configured) if configured else Path.home() / ".config"
    return base / "xwallpaper-gui" / "settings.json"


def load_settings():
    try:
        value = json.loads(settings_path().read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return {}
        clean = {}
        for key in ("folder", "last_wallpaper", "output"):
            if isinstance(value.get(key), str):
                clean[key] = value[key]
        if value.get("mode") in {item[0] for item in MODES}:
            clean["mode"] = value["mode"]
        if isinstance(value.get("recursive"), bool):
            clean["recursive"] = value["recursive"]
        return clean
    except (OSError, ValueError):
        return {}


def save_settings(value):
    target = settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
