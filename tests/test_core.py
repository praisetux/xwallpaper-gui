import importlib.machinery
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
app = importlib.machinery.SourceFileLoader(
    "xwallpaper_gui", str(PROJECT_ROOT / "xwallpaper-gui")
).load_module()


class SettingsTests(unittest.TestCase):
    def test_invalid_field_types_are_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "xwallpaper-gui"
            config.mkdir()
            (config / "settings.json").write_text(json.dumps({
                "folder": 12,
                "last_wallpaper": None,
                "output": ["DP-1"],
                "mode": "not-a-mode",
                "recursive": "yes",
            }), encoding="utf-8")
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
                self.assertEqual(app.load_settings(), {})

    def test_valid_fields_survive_sanitizing(self):
        expected = {
            "folder": "/pictures",
            "last_wallpaper": "/pictures/wall.png",
            "output": "DP-1",
            "mode": "zoom",
            "recursive": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "xwallpaper-gui"
            config.mkdir()
            (config / "settings.json").write_text(
                json.dumps(expected), encoding="utf-8"
            )
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
                self.assertEqual(app.load_settings(), expected)

    def test_empty_xdg_config_home_uses_default_location(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}):
            self.assertEqual(
                app.settings_path(),
                Path.home() / ".config" / "xwallpaper-gui" / "settings.json",
            )


class WallpaperTests(unittest.TestCase):
    def test_only_xwallpaper_image_formats_are_listed(self):
        self.assertEqual(app.EXTENSIONS, {".jpg", ".jpeg", ".png"})

    def test_focus_mode_is_not_offered(self):
        self.assertNotIn("focus", {mode for mode, _label in app.MODES})

    def test_command_preserves_paths_with_spaces(self):
        self.assertEqual(
            app.wallpaper_command("/tmp/a wallpaper.png", "zoom", "DP-1"),
            ["xwallpaper", "--output", "DP-1", "--zoom", "/tmp/a wallpaper.png"],
        )

    def test_folder_scan_filters_and_sorts(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name in ("b.PNG", "a.jpg", "ignored.webp"):
                (folder / name).touch()
            paths, error = app.Window._find_paths(folder, False)
            self.assertIsNone(error)
            self.assertEqual([path.name for path in paths], ["a.jpg", "b.PNG"])

    @mock.patch.object(app.shutil, "which", return_value="/usr/bin/xrandr")
    @mock.patch.object(app.subprocess, "run")
    def test_output_detection_ignores_disconnected_outputs(self, run, _which):
        run.return_value = mock.Mock(
            returncode=0,
            stdout="DP-1 connected 1920x1080+0+0\nHDMI-1 disconnected\n",
        )
        with mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            self.assertEqual(app.outputs(), ["DP-1"])

    def test_restore_rejects_a_stale_display(self):
        with tempfile.NamedTemporaryFile(suffix=".png") as image, \
                mock.patch.object(app, "load_settings", return_value={
                    "last_wallpaper": image.name,
                    "mode": "zoom",
                    "output": "DP-9",
                }), \
                mock.patch.object(app.shutil, "which", return_value="/usr/bin/xwallpaper"), \
                mock.patch.object(app, "outputs", return_value=["DP-1"]), \
                mock.patch.object(app.subprocess, "run") as run, \
                mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            self.assertEqual(app.restore(), 1)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
