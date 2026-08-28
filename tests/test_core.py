import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


import xwallpaper_gui as app
from xwallpaper_gui import cli, system


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

    def test_settings_round_trip(self):
        expected = {"folder": "/pictures", "mode": "center", "recursive": False}
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
            app.save_settings(expected)
            self.assertEqual(app.load_settings(), expected)
            self.assertFalse(app.settings_path().with_suffix(".tmp").exists())


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

    def test_command_rejects_an_invalid_layout(self):
        with self.assertRaises(ValueError):
            app.wallpaper_command("/tmp/wallpaper.png", "focus", "All displays")

    def test_xinitrc_command_is_added_without_changing_existing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            xinitrc = Path(directory) / ".xinitrc"
            xinitrc.write_text("#!/bin/sh\nexec openbox-session\n", encoding="utf-8")
            app.save_xinitrc_command(
                ["xwallpaper", "--zoom", "/tmp/a wallpaper.png"], xinitrc
            )
            self.assertEqual(xinitrc.read_text(encoding="utf-8"),
                "#!/bin/sh\n\n"
                "# BEGIN xwallpaper-gui wallpaper\n"
                "xwallpaper --zoom '/tmp/a wallpaper.png'\n"
                "# END xwallpaper-gui wallpaper\n\n"
                "exec openbox-session\n")

    def test_xinitrc_command_is_replaced_instead_of_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            xinitrc = Path(directory) / ".xinitrc"
            app.save_xinitrc_command(["xwallpaper", "--zoom", "old.png"], xinitrc)
            app.save_xinitrc_command(["xwallpaper", "--tile", "new.png"], xinitrc)
            contents = xinitrc.read_text(encoding="utf-8")
            self.assertNotIn("old.png", contents)
            self.assertEqual(contents.count("# BEGIN xwallpaper-gui wallpaper"), 1)
            self.assertIn("xwallpaper --tile new.png", contents)

    def test_folder_scan_filters_and_sorts(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name in ("b.PNG", "a.jpg", "ignored.webp"):
                (folder / name).touch()
            paths, error = app.Window._find_paths(folder, False)
            self.assertIsNone(error)
            self.assertEqual([path.name for path in paths], ["a.jpg", "b.PNG"])

    def test_recursive_scan_includes_nested_images(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            nested = folder / "nested"
            nested.mkdir()
            (folder / "top.png").touch()
            (nested / "inside.jpg").touch()
            paths, error = app.Window._find_paths(folder, True)
            self.assertIsNone(error)
            self.assertEqual(
                {path.relative_to(folder).as_posix() for path in paths},
                {"top.png", "nested/inside.jpg"},
            )

    def test_folder_status_does_not_expose_the_absolute_path(self):
        window = mock.Mock(folder=Path("/private/location/Pictures"))
        self.assertEqual(app.Window._folder_name(window), "Pictures")

    @mock.patch.object(system.shutil, "which", return_value="/usr/bin/xrandr")
    @mock.patch.object(system.subprocess, "run")
    def test_output_detection_ignores_disconnected_outputs(self, run, _which):
        run.return_value = mock.Mock(
            returncode=0,
            stdout="DP-1 connected 1920x1080+0+0\nHDMI-1 disconnected\n",
        )
        with mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            self.assertEqual(app.outputs(), ["DP-1"])

    def test_restore_rejects_a_stale_display(self):
        with tempfile.NamedTemporaryFile(suffix=".png") as image, \
                mock.patch.object(cli, "load_settings", return_value={
                    "last_wallpaper": image.name,
                    "mode": "zoom",
                    "output": "DP-9",
                }), \
                mock.patch.object(cli.shutil, "which", return_value="/usr/bin/xwallpaper"), \
                mock.patch.object(cli, "outputs", return_value=["DP-1"]), \
                mock.patch.object(cli.subprocess, "run") as run, \
                mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            self.assertEqual(app.restore(), 1)
            run.assert_not_called()

    def test_restore_applies_a_valid_saved_wallpaper(self):
        with tempfile.NamedTemporaryFile(suffix=".png") as image, \
                mock.patch.object(cli, "load_settings", return_value={
                    "last_wallpaper": image.name,
                    "mode": "maximize",
                    "output": "All displays",
                }), \
                mock.patch.object(cli.shutil, "which", return_value="/usr/bin/xwallpaper"), \
                mock.patch.object(cli.subprocess, "run") as run, \
                mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            run.return_value.returncode = 0
            self.assertEqual(app.restore(), 0)
            run.assert_called_once_with(
                ["xwallpaper", "--maximize", image.name], timeout=10
            )


if __name__ == "__main__":
    unittest.main()
