import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


import xwallpaper_gui as app
from xwallpaper_gui import cli, system, window as window_module


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

    def test_dwm_autostart_is_created_and_made_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            autostart = Path(directory) / "dwm" / "autostart.sh"
            app.save_dwm_autostart_command(
                ["xwallpaper", "--zoom", "/tmp/a wallpaper.png"], autostart
            )
            self.assertEqual(autostart.read_text(encoding="utf-8"),
                "#!/bin/sh\n\n"
                "# BEGIN xwallpaper-gui wallpaper\n"
                "xwallpaper --zoom '/tmp/a wallpaper.png'\n"
                "# END xwallpaper-gui wallpaper\n")
            self.assertTrue(autostart.stat().st_mode & 0o100)

    def test_dwm_autostart_preserves_existing_commands_and_replaces_ours(self):
        with tempfile.TemporaryDirectory() as directory:
            autostart = Path(directory) / "autostart.sh"
            autostart.write_text("#!/bin/sh\npicom &\n", encoding="utf-8")
            app.save_dwm_autostart_command(
                ["xwallpaper", "--zoom", "old.png"], autostart
            )
            app.save_dwm_autostart_command(
                ["xwallpaper", "--tile", "new.png"], autostart
            )
            contents = autostart.read_text(encoding="utf-8")
            self.assertIn("picom &", contents)
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

    def test_repeated_xinitrc_updates_do_not_accumulate_blank_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            xinitrc = Path(directory) / ".xinitrc"
            xinitrc.write_text("#!/bin/sh\nexec openbox-session\n", encoding="utf-8")
            app.save_xinitrc_command(["xwallpaper", "--zoom", "one.png"], xinitrc)
            first = xinitrc.read_text(encoding="utf-8")
            for name in ("two.png", "three.png", "four.png"):
                app.save_xinitrc_command(["xwallpaper", "--zoom", name], xinitrc)
            self.assertEqual(xinitrc.read_text(encoding="utf-8"),
                             first.replace("one.png", "four.png"))

    def test_repeated_dwm_updates_do_not_accumulate_blank_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            autostart = Path(directory) / "autostart.sh"
            autostart.write_text("#!/bin/sh\npicom &\n", encoding="utf-8")
            app.save_dwm_autostart_command(["xwallpaper", "--zoom", "one.png"], autostart)
            first = autostart.read_text(encoding="utf-8")
            for name in ("two.png", "three.png"):
                app.save_dwm_autostart_command(["xwallpaper", "--zoom", name], autostart)
            self.assertEqual(autostart.read_text(encoding="utf-8"),
                             first.replace("one.png", "three.png"))

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


class WindowControlTests(unittest.TestCase):
    def test_message_shows_the_bar_and_its_label(self):
        window = mock.Mock()
        app.Window.message(window, "something happened")
        window.info_label.set_text.assert_called_once_with("something happened")
        window.info_label.show.assert_called_once_with()
        window.info.show.assert_called_once_with()
        window.info.show_all.assert_not_called()

    def test_refresh_selects_a_connected_saved_display(self):
        window = mock.Mock(settings={"output": "DP-1"}, _updating_controls=False)
        with mock.patch.object(window_module, "outputs", return_value=["DP-1", "HDMI-1"]):
            self.assertEqual(app.Window._refresh_outputs(window), ["DP-1", "HDMI-1"])
        window.output.set_active_id.assert_called_once_with("DP-1")

    def test_refresh_falls_back_without_forgetting_the_saved_display(self):
        settings = {"output": "DP-9"}
        window = mock.Mock(settings=settings, _updating_controls=False)
        with mock.patch.object(window_module, "outputs", return_value=["DP-1"]):
            app.Window._refresh_outputs(window)
        window.output.set_active_id.assert_called_once_with("All displays")
        self.assertEqual(settings["output"], "DP-9")

    def test_programmatic_control_updates_are_not_persisted(self):
        settings = {"mode": "tile", "output": "DP-9", "recursive": True}
        window = mock.Mock(settings=settings, _updating_controls=True)
        app.Window._mode_changed(window, None)
        app.Window._output_changed(window, None)
        app.Window._recursive_changed(window, mock.Mock())
        window.remember.assert_not_called()
        self.assertEqual(settings, {"mode": "tile", "output": "DP-9", "recursive": True})

    def test_a_chosen_display_is_persisted(self):
        settings = {}
        window = mock.Mock(settings=settings, _updating_controls=False)
        window.output.get_active_id.return_value = "HDMI-1"
        app.Window._output_changed(window, None)
        self.assertEqual(settings["output"], "HDMI-1")
        window.remember.assert_called_once_with()

    @staticmethod
    def _apply_window(output):
        window = mock.Mock(selected=Path("/pictures/wall.png"),
                           folder=Path("/pictures"), settings={})
        window.output.get_active_id.return_value = output
        window.mode.get_active_id.return_value = "zoom"
        window.recursive.get_active.return_value = False
        window._refresh_outputs.return_value = ["DP-1"]
        return window

    def test_apply_refreshes_displays_even_for_all_displays(self):
        window = self._apply_window("All displays")
        with mock.patch.object(window_module.shutil, "which", return_value="/bin/xwallpaper"), \
                mock.patch.object(window_module.subprocess, "run") as run, \
                mock.patch.object(window_module, "save_xinitrc_command") as xinitrc, \
                mock.patch.object(window_module, "save_dwm_autostart_command") as autostart, \
                mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            run.return_value.returncode = 0
            app.Window.apply(window)
        window._refresh_outputs.assert_called_once_with()
        self.assertEqual(run.call_args[0][0],
                         ["xwallpaper", "--zoom", "/pictures/wall.png"])
        xinitrc.assert_called_once()
        autostart.assert_called_once()

    def test_apply_refuses_a_disconnected_display(self):
        window = self._apply_window("DP-9")
        with mock.patch.object(window_module.shutil, "which", return_value="/bin/xwallpaper"), \
                mock.patch.object(window_module.subprocess, "run") as run, \
                mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            app.Window.apply(window)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
