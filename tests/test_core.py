import json
import os
import struct
from pathlib import Path
import subprocess
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

    def test_unhashable_mode_values_are_discarded(self):
        for invalid_mode in ([], {}):
            with self.subTest(mode=invalid_mode), \
                    tempfile.TemporaryDirectory() as directory:
                config = Path(directory) / "xwallpaper-gui"
                config.mkdir()
                (config / "settings.json").write_text(
                    json.dumps({"mode": invalid_mode}), encoding="utf-8"
                )
                with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
                    self.assertEqual(app.load_settings(), {})

    def test_valid_fields_survive_sanitizing(self):
        expected = {
            "folder": "/pictures",
            "last_wallpaper": "/pictures/wall.png",
            "output": "DP-1",
            "mode": "zoom",
            "last_output": "HDMI-1",
            "last_mode": "tile",
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
            xinitrc.write_text("#!/bin/sh\nexec openbox-session\n", encoding="utf-8")
            app.save_xinitrc_command(["xwallpaper", "--zoom", "old.png"], xinitrc)
            app.save_xinitrc_command(["xwallpaper", "--tile", "new.png"], xinitrc)
            contents = xinitrc.read_text(encoding="utf-8")
            self.assertNotIn("old.png", contents)
            self.assertEqual(contents.count("# BEGIN xwallpaper-gui wallpaper"), 1)
            self.assertIn("xwallpaper --tile new.png", contents)

    def test_xinitrc_is_not_created_when_the_user_does_not_have_one(self):
        with tempfile.TemporaryDirectory() as directory:
            xinitrc = Path(directory) / ".xinitrc"
            reason = app.save_xinitrc_command(
                ["xwallpaper", "--zoom", "wall.png"], xinitrc)
            self.assertIn("does not exist", reason)
            self.assertFalse(xinitrc.exists())

    def test_a_sessionless_xinitrc_is_left_alone(self):
        """An xinitrc holding only our block would start no window manager."""
        with tempfile.TemporaryDirectory() as directory:
            xinitrc = Path(directory) / ".xinitrc"
            original = ("# BEGIN xwallpaper-gui wallpaper\n"
                        "xwallpaper --zoom old.png\n"
                        "# END xwallpaper-gui wallpaper\n")
            xinitrc.write_text(original, encoding="utf-8")
            reason = app.save_xinitrc_command(
                ["xwallpaper", "--tile", "new.png"], xinitrc)
            self.assertIn("starts no desktop session", reason)
            self.assertEqual(xinitrc.read_text(encoding="utf-8"), original)

    def test_a_real_xinitrc_is_still_updated(self):
        with tempfile.TemporaryDirectory() as directory:
            xinitrc = Path(directory) / ".xinitrc"
            xinitrc.write_text("#!/bin/sh\nexec dwm\n", encoding="utf-8")
            self.assertIsNone(app.save_xinitrc_command(
                ["xwallpaper", "--zoom", "wall.png"], xinitrc))
            self.assertIn("xwallpaper --zoom wall.png",
                          xinitrc.read_text(encoding="utf-8"))

    def test_xinitrc_command_is_not_inserted_inside_a_conditional(self):
        with tempfile.TemporaryDirectory() as directory:
            xinitrc = Path(directory) / ".xinitrc"
            xinitrc.write_text(
                "#!/bin/sh\nif false; then\n    exec unused-session\nfi\n"
                "exec openbox-session\n",
                encoding="utf-8",
            )
            app.save_xinitrc_command(
                ["xwallpaper", "--zoom", "wall.png"], xinitrc
            )
            contents = xinitrc.read_text(encoding="utf-8")
            self.assertLess(contents.index("xwallpaper --zoom"),
                            contents.index("if false; then"))

    def test_xinitrc_command_runs_even_when_an_early_exec_branch_is_false(self):
        with tempfile.TemporaryDirectory() as directory:
            xinitrc = Path(directory) / ".xinitrc"
            xinitrc.write_text(
                "#!/bin/sh\nif false; then\n    exec unused-session\nfi\n"
                "printf normal-session\n",
                encoding="utf-8",
            )
            app.save_xinitrc_command(["printf", "wallpaper-started"], xinitrc)
            result = subprocess.run(
                ["sh", str(xinitrc)], capture_output=True, text=True, check=True
            )
            self.assertEqual(result.stdout, "wallpaper-startednormal-session")

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

    def test_restore_uses_the_last_applied_options_not_browsing_controls(self):
        with tempfile.NamedTemporaryFile(suffix=".png") as image, \
                mock.patch.object(cli, "load_settings", return_value={
                    "last_wallpaper": image.name,
                    "mode": "tile",
                    "output": "DP-2",
                    "last_mode": "zoom",
                    "last_output": "DP-1",
                }), \
                mock.patch.object(cli.shutil, "which", return_value="/usr/bin/xwallpaper"), \
                mock.patch.object(cli, "outputs", return_value=["DP-1", "DP-2"]), \
                mock.patch.object(cli.subprocess, "run") as run, \
                mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            run.return_value.returncode = 0
            self.assertEqual(app.restore(), 0)
            run.assert_called_once_with(
                ["xwallpaper", "--output", "DP-1", "--zoom", image.name],
                timeout=10,
            )


class WindowControlTests(unittest.TestCase):
    def test_message_shows_the_bar_and_its_label(self):
        window = mock.Mock()
        app.Window.message(window, "something happened")
        window.info_label.set_text.assert_called_once_with("something happened")
        window.info_label.show.assert_called_once_with()
        window.info.show.assert_called_once_with()
        window.info.show_all.assert_not_called()

    def test_output_replacement_selects_a_connected_saved_display(self):
        window = mock.Mock(settings={"output": "DP-1"}, _updating_controls=False)
        app.Window._replace_outputs(window, ["DP-1", "HDMI-1"], "DP-1")
        window.output.set_active_id.assert_called_once_with("DP-1")

    def test_output_replacement_falls_back_without_forgetting_saved_display(self):
        settings = {"output": "DP-9"}
        window = mock.Mock(settings=settings, _updating_controls=False)
        app.Window._replace_outputs(window, ["DP-1"], "DP-9")
        window.output.set_active_id.assert_called_once_with("All displays")
        self.assertEqual(settings["output"], "DP-9")

    def test_display_refresh_starts_a_worker_instead_of_running_xrandr(self):
        window = mock.Mock(output_refresh_id=3)
        with mock.patch.object(window_module.threading, "Thread") as thread, \
                mock.patch.object(window_module, "outputs") as detect:
            app.Window._refresh_outputs(window)
        detect.assert_not_called()
        thread.assert_called_once_with(
            target=window._outputs_worker, args=(4,), daemon=True
        )
        thread.return_value.start.assert_called_once_with()

    def test_stale_display_refresh_is_ignored(self):
        window = mock.Mock(output_refresh_id=4)
        result = app.Window._outputs_ready(window, ["DP-1"], 3)
        window._replace_outputs.assert_not_called()
        self.assertEqual(result, window_module.GLib.SOURCE_REMOVE)

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
                           folder=Path("/pictures"), settings={}, applying=False)
        window.output.get_active_id.return_value = output
        window.mode.get_active_id.return_value = "zoom"
        window.recursive.get_active.return_value = False
        return window

    def test_apply_starts_a_worker_without_running_external_commands(self):
        window = self._apply_window("All displays")
        with mock.patch.object(window_module.shutil, "which", return_value="/bin/xwallpaper"), \
                mock.patch.object(window_module.threading, "Thread") as thread, \
                mock.patch.object(window_module, "outputs") as detect, \
                mock.patch.object(window_module.subprocess, "run") as run, \
                mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            app.Window.apply(window)
        detect.assert_not_called()
        run.assert_not_called()
        thread.assert_called_once_with(
            target=window._apply_worker,
            args=(Path("/pictures/wall.png"), Path("/pictures"), "zoom",
                  "All displays"),
            daemon=True,
        )
        thread.return_value.start.assert_called_once_with()

    def test_apply_does_not_start_an_overlapping_worker(self):
        window = self._apply_window("All displays")
        window.applying = True
        with mock.patch.object(window_module.threading, "Thread") as thread:
            app.Window.apply(window)
        thread.assert_not_called()

    def test_apply_worker_refuses_a_disconnected_display(self):
        window = self._apply_window("DP-9")
        with mock.patch.object(window_module, "outputs", return_value=["DP-1"]), \
                mock.patch.object(window_module.subprocess, "run") as run, \
                mock.patch.object(window_module.GLib, "idle_add") as idle_add:
            app.Window._apply_worker(
                window, Path("/pictures/wall.png"), Path("/pictures"),
                "zoom", "DP-9",
            )
        run.assert_not_called()
        self.assertIn("no longer connected", idle_add.call_args.args[-2])

    def test_successful_apply_worker_runs_command_and_updates_startup(self):
        window = self._apply_window("All displays")
        with mock.patch.object(window_module, "outputs", return_value=["DP-1"]), \
                mock.patch.object(window_module, "dwm_autostart_applies",
                                  return_value=True), \
                mock.patch.object(window_module.subprocess, "run") as run, \
                mock.patch.object(window_module, "save_xinitrc_command") as xinitrc, \
                mock.patch.object(window_module, "save_dwm_autostart_command") as autostart, \
                mock.patch.object(window_module.GLib, "idle_add") as idle_add:
            run.return_value.returncode = 0
            app.Window._apply_worker(
                window, Path("/pictures/wall.png"), Path("/pictures"),
                "zoom", "All displays",
            )
        run.assert_called_once_with(
            ["xwallpaper", "--zoom", "/pictures/wall.png"],
            capture_output=True, text=True, timeout=10,
        )
        xinitrc.assert_called_once()
        autostart.assert_called_once()
        idle_add.assert_called_once()

    def test_apply_completion_records_last_applied_options(self):
        window = self._apply_window("DP-1")
        window._replace_outputs = mock.Mock()
        window._set_apply_busy = mock.Mock()
        result = app.Window._apply_ready(
            window, Path("/pictures/wall.png"), Path("/pictures"), "zoom",
            "DP-1", ["DP-1"], None, [],
        )
        self.assertEqual(window.settings["last_mode"], "zoom")
        self.assertEqual(window.settings["last_output"], "DP-1")
        window.remember.assert_called_once_with()
        self.assertEqual(result, window_module.GLib.SOURCE_REMOVE)


class StartupTargetTests(unittest.TestCase):
    def test_dwm_autostart_is_skipped_without_dwm(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(system.shutil, "which", return_value=None), \
                mock.patch.dict(os.environ, {"XDG_DATA_HOME": directory}):
            self.assertFalse(app.dwm_autostart_applies())

    def test_dwm_autostart_applies_when_dwm_is_installed(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(system.shutil, "which",
                                  return_value="/usr/bin/dwm"), \
                mock.patch.dict(os.environ, {"XDG_DATA_HOME": directory}):
            self.assertTrue(app.dwm_autostart_applies())

    def test_dwm_autostart_applies_when_the_script_already_exists(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(system.shutil, "which", return_value=None), \
                mock.patch.dict(os.environ, {"XDG_DATA_HOME": directory}):
            script = Path(directory) / "dwm" / "autostart.sh"
            script.parent.mkdir(parents=True)
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            self.assertTrue(app.dwm_autostart_applies())

    def test_apply_reports_when_no_startup_file_could_be_updated(self):
        window = mock.Mock(selected=Path("/pictures/wall.png"),
                           folder=Path("/pictures"), settings={}, applying=False)
        with mock.patch.object(window_module, "outputs", return_value=["DP-1"]), \
                mock.patch.object(window_module, "dwm_autostart_applies",
                                  return_value=False), \
                mock.patch.object(window_module, "save_xinitrc_command",
                                  return_value="no xinitrc here"), \
                mock.patch.object(window_module.subprocess, "run") as run, \
                mock.patch.object(window_module.GLib, "idle_add") as idle_add:
            run.return_value.returncode = 0
            app.Window._apply_worker(
                window, Path("/pictures/wall.png"), Path("/pictures"),
                "zoom", "All displays")
        self.assertIsNone(idle_add.call_args.args[-2])
        self.assertEqual(idle_add.call_args.args[-1], ["no xinitrc here"])

    def test_apply_stays_quiet_when_one_destination_succeeds(self):
        window = mock.Mock(selected=Path("/pictures/wall.png"),
                           folder=Path("/pictures"), settings={}, applying=False)
        with mock.patch.object(window_module, "outputs", return_value=["DP-1"]), \
                mock.patch.object(window_module, "dwm_autostart_applies",
                                  return_value=False), \
                mock.patch.object(window_module, "save_xinitrc_command",
                                  return_value=None), \
                mock.patch.object(window_module.subprocess, "run") as run, \
                mock.patch.object(window_module.GLib, "idle_add") as idle_add:
            run.return_value.returncode = 0
            app.Window._apply_worker(
                window, Path("/pictures/wall.png"), Path("/pictures"),
                "zoom", "All displays")
        self.assertEqual(idle_add.call_args.args[-1], [])


class ScanErrorTests(unittest.TestCase):
    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_recursive_scan_reports_an_unreadable_subfolder(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "top.png").touch()
            locked = folder / "locked"
            locked.mkdir()
            (locked / "hidden.png").touch()
            locked.chmod(0o000)
            try:
                paths, error = app.Window._find_paths(folder, True)
            finally:
                locked.chmod(0o755)
            self.assertEqual([path.name for path in paths], ["top.png"])
            self.assertIsNotNone(error)
            self.assertIn("Permission denied", error)

    def test_a_readable_recursive_scan_reports_no_error(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            nested = folder / "nested"
            nested.mkdir()
            (folder / "top.png").touch()
            (nested / "inside.jpg").touch()
            paths, error = app.Window._find_paths(folder, True)
            self.assertIsNone(error)
            self.assertEqual(len(paths), 2)

    def test_a_folder_of_undecodable_images_shows_the_empty_state(self):
        window = mock.Mock(scan_id=4, loaded=0)
        app.Window._finish_thumbnails(window, 4)
        window._show_empty.assert_called_once()
        self.assertIn("could be opened", window._show_empty.call_args.args[0])

    def test_a_folder_with_thumbnails_keeps_the_gallery(self):
        window = mock.Mock(scan_id=4, loaded=3)
        app.Window._finish_thumbnails(window, 4)
        window._show_empty.assert_not_called()

class ThumbnailTests(unittest.TestCase):
    @staticmethod
    def _write_jpeg(path, width, height, orientation=None):
        """Write a solid JPEG, optionally tagged with an EXIF orientation."""
        pixbuf = window_module.GdkPixbuf.Pixbuf.new(
            window_module.GdkPixbuf.Colorspace.RGB, False, 8, width, height)
        pixbuf.fill(0x3366CCFF)
        _, data = pixbuf.save_to_bufferv("jpeg", [], [])
        if orientation is not None:
            tiff = (b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", 1)
                    + struct.pack("<HHI", 0x0112, 3, 1)
                    + struct.pack("<HH", orientation, 0) + struct.pack("<I", 0))
            payload = b"Exif\x00\x00" + tiff
            app1 = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
            data = data[:2] + app1 + data[2:]
        Path(path).write_bytes(data)

    def test_quarter_turn_orientation_still_fits_the_tile_box(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "rotated.jpg"
            self._write_jpeg(image, 400, 300, orientation=6)
            thumbnail = app.Window._thumbnail(image)
            self.assertLessEqual(thumbnail.get_width(), 200)
            self.assertLessEqual(thumbnail.get_height(), 125)
            self.assertGreater(thumbnail.get_height(), thumbnail.get_width())

    def test_upright_image_keeps_its_aspect_ratio(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "wide.jpg"
            self._write_jpeg(image, 400, 300)
            thumbnail = app.Window._thumbnail(image)
            self.assertEqual((thumbnail.get_width(), thumbnail.get_height()),
                             (167, 125))

    def test_a_panorama_is_bounded_by_the_tile_width(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "panorama.jpg"
            self._write_jpeg(image, 2560, 800)
            thumbnail = app.Window._thumbnail(image)
            self.assertEqual(thumbnail.get_width(), 200)
            self.assertLessEqual(thumbnail.get_height(), 125)

    def test_an_undecodable_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "broken.png"
            broken.write_bytes(b"not an image")
            self.assertIsNone(app.Window._thumbnail(broken))


if __name__ == "__main__":
    unittest.main()
