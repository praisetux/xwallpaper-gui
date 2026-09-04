"""Main GTK window and wallpaper gallery."""

import os
from pathlib import Path
import shutil
import subprocess
import threading

from .constants import EXTENSIONS, MODES
from .gtk import Gdk, GdkPixbuf, GLib, Gtk
from .settings import load_settings, save_settings
from .system import (
    outputs, save_dwm_autostart_command, save_xinitrc_command,
    wallpaper_command,
)


class Window(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="XWallpaper GUI")
        self.set_default_size(900, 620)
        self.set_size_request(520, 360)
        self.settings = load_settings()
        self.folder = None
        self.selected = None
        self.scan_id = 0
        self.loaded = 0
        self.dependency_warning = not shutil.which("xwallpaper")
        self._updating_controls = False
        self._build()
        self._restore_controls()
        GLib.idle_add(self._startup)

    def _build(self):
        self._load_styles()

        header = Gtk.HeaderBar(title="Wallpapers", show_close_button=True)
        header.set_subtitle("Browse and apply desktop backgrounds")
        self.set_titlebar(header)
        self.folder_button = Gtk.Button(label="Choose Folder…")
        self.folder_button.set_tooltip_text("Choose a wallpaper folder")
        self.folder_button.connect("clicked", self._choose_folder)
        header.pack_start(self.folder_button)
        refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        refresh.set_tooltip_text("Rescan the folder and connected displays")
        refresh.connect("clicked", lambda _button: self._refresh())
        header.pack_start(refresh)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        self.info = Gtk.InfoBar()
        self.info.set_no_show_all(True)
        self.info.set_show_close_button(True)
        self.info.connect("response", lambda bar, _response: bar.hide())
        self.info_label = Gtk.Label(xalign=0)
        self.info_label.set_line_wrap(True)
        self.info.get_content_area().add(self.info_label)
        root.pack_start(self.info, False, False, 0)

        workspace = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        workspace.set_position(230)
        workspace.set_wide_handle(True)
        root.pack_start(workspace, True, True, 0)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        sidebar.set_size_request(210, -1)
        sidebar.set_border_width(18)
        sidebar.get_style_context().add_class("settings-sidebar")
        workspace.pack1(sidebar, resize=False, shrink=False)

        settings_title = Gtk.Label(label="Wallpaper settings", xalign=0)
        settings_title.get_style_context().add_class("section-title")
        sidebar.pack_start(settings_title, False, False, 0)

        layout_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sidebar.pack_start(layout_group, False, False, 0)
        layout_group.pack_start(self._field_label("LAYOUT"), False, False, 0)
        self.mode = Gtk.ComboBoxText()
        for key, label in MODES:
            self.mode.append(key, label)
        self.mode.connect("changed", self._mode_changed)
        layout_group.pack_start(self.mode, False, False, 0)

        display_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sidebar.pack_start(display_group, False, False, 0)
        display_group.pack_start(self._field_label("DISPLAY"), False, False, 0)
        self.output = Gtk.ComboBoxText()
        self.output.connect("changed", self._output_changed)
        display_group.pack_start(self.output, False, False, 0)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sidebar.pack_start(separator, False, False, 0)
        self.recursive = Gtk.CheckButton(label="Include subfolders")
        self.recursive.set_tooltip_text("Show images from folders inside the selected folder")
        self.recursive.connect("toggled", self._recursive_changed)
        sidebar.pack_start(self.recursive, False, False, 0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        workspace.pack2(content, resize=True, shrink=False)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        content.pack_start(self.stack, True, True, 0)
        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                        valign=Gtk.Align.CENTER)
        empty.pack_start(Gtk.Image.new_from_icon_name(
            "image-x-generic-symbolic", Gtk.IconSize.DIALOG), False, False, 0)
        self.empty_title = Gtk.Label()
        self.empty_title.set_markup("<big><b>Choose a wallpaper folder</b></big>")
        self.empty_detail = Gtk.Label(label="Its images will appear here.")
        empty.pack_start(self.empty_title, False, False, 0)
        empty.pack_start(self.empty_detail, False, False, 0)
        self.stack.add_named(empty, "empty")

        scroll = Gtk.ScrolledWindow()
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE,
                                column_spacing=12, row_spacing=12,
                                min_children_per_line=1, max_children_per_line=20)
        self.flow.set_border_width(12)
        self.flow.connect("selected-children-changed", self._selection_changed)
        self.flow.connect("child-activated", lambda *_args: self.apply())
        scroll.add(self.flow)
        self.stack.add_named(scroll, "gallery")
        self.stack.set_visible_child_name("empty")

        bar = Gtk.ActionBar()
        bar.get_style_context().add_class("gallery-footer")
        content.pack_end(bar, False, False, 0)
        self.status = Gtk.Label(label="No folder selected", xalign=0)
        self.status.set_ellipsize(3)
        bar.pack_start(self.status)
        self.apply_button = Gtk.Button(label="Apply", sensitive=False)
        self.apply_button.set_tooltip_text("Apply the selected wallpaper")
        self.apply_button.get_style_context().add_class(Gtk.STYLE_CLASS_SUGGESTED_ACTION)
        self.apply_button.connect("clicked", lambda _button: self.apply())
        bar.pack_end(self.apply_button)

    @staticmethod
    def _field_label(text):
        label = Gtk.Label(label=text, xalign=0)
        label.get_style_context().add_class("field-label")
        return label

    @staticmethod
    def _load_styles():
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            .settings-sidebar {
                background-color: alpha(@theme_fg_color, 0.035);
                border-right: 1px solid alpha(@theme_fg_color, 0.12);
            }
            .section-title {
                font-size: 1.15em;
                font-weight: bold;
            }
            .field-label {
                color: alpha(@theme_fg_color, 0.65);
                font-size: 0.82em;
                font-weight: bold;
            }
            .gallery-footer {
                border-top: 1px solid alpha(@theme_fg_color, 0.12);
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _startup(self):
        if self.dependency_warning:
            self.message("xwallpaper is not installed. Browsing works, but applying requires it.")
        folder = self.settings.get("folder")
        if folder and Path(folder).is_dir():
            self.folder = Path(folder)
            self.scan()
        return GLib.SOURCE_REMOVE

    def _folder_name(self):
        return self.folder.name or "Selected folder"

    def _restore_controls(self):
        self._updating_controls = True
        try:
            mode = self.settings.get("mode", "zoom")
            self.mode.set_active_id(
                mode if mode in {item[0] for item in MODES} else "zoom")
            self.recursive.set_active(bool(self.settings.get("recursive")))
        finally:
            self._updating_controls = False
        self._refresh_outputs()

    def _refresh_outputs(self):
        """Rebuild the display list, keeping the saved preference if it is connected."""
        preferred = self.settings.get("output", "All displays")
        available = outputs()
        self._updating_controls = True
        try:
            self.output.remove_all()
            self.output.append("All displays", "All displays")
            for name in available:
                self.output.append(name, name)
            self.output.set_active_id(
                preferred if preferred in available else "All displays")
        finally:
            self._updating_controls = False
        return available

    def _refresh(self):
        self._refresh_outputs()
        self.scan()

    def message(self, text, kind=Gtk.MessageType.WARNING):
        self.info.set_message_type(kind)
        self.info_label.set_text(text)
        self.info_label.show()
        self.info.show()

    def remember(self):
        try:
            save_settings(self.settings)
        except OSError as error:
            self.message(f"Could not save settings: {error}")

    def _mode_changed(self, _widget):
        if self._updating_controls:
            return
        self.settings["mode"] = self.mode.get_active_id() or "zoom"
        self.remember()

    def _output_changed(self, _widget):
        if self._updating_controls:
            return
        self.settings["output"] = self.output.get_active_id() or "All displays"
        self.remember()

    def _recursive_changed(self, widget):
        if self._updating_controls:
            return
        self.settings["recursive"] = widget.get_active()
        self.remember()
        if self.folder:
            self.scan()

    def _choose_folder(self, _button):
        dialog = Gtk.FileChooserDialog("Choose a wallpaper folder", self,
            Gtk.FileChooserAction.SELECT_FOLDER,
            ("Cancel", Gtk.ResponseType.CANCEL, "Choose", Gtk.ResponseType.ACCEPT))
        if self.folder:
            dialog.set_current_folder(str(self.folder))
        elif (Path.home() / "Pictures").is_dir():
            dialog.set_current_folder(str(Path.home() / "Pictures"))
        response = dialog.run()
        chosen = dialog.get_filename() if response == Gtk.ResponseType.ACCEPT else None
        dialog.destroy()
        if chosen:
            self.folder = Path(chosen)
            self.settings["folder"] = chosen
            self.remember()
            self.scan()

    @staticmethod
    def _find_paths(folder, recursive):
        iterator = folder.rglob("*") if recursive else folder.iterdir()
        try:
            paths = sorted((path for path in iterator
                            if path.is_file() and path.suffix.lower() in EXTENSIONS),
                           key=lambda path: str(path).casefold())
            return paths, None
        except OSError as error:
            return [], str(error)

    def scan(self):
        if not self.folder:
            return
        self.scan_id += 1
        scan_id = self.scan_id
        self.loaded = 0
        self.selected = None
        self.apply_button.set_sensitive(False)
        for child in self.flow.get_children():
            self.flow.remove(child)
        self.folder_button.set_label(self.folder.name or str(self.folder))
        self.folder_button.set_tooltip_text(str(self.folder))
        self.stack.set_visible_child_name("gallery")
        self.status.set_text(f"Scanning {self._folder_name()}…")
        threading.Thread(
            target=self._scan_worker,
            args=(self.folder, self.recursive.get_active(), scan_id),
            daemon=True,
        ).start()

    def _scan_worker(self, folder, recursive, scan_id):
        paths, error = self._find_paths(folder, recursive)
        GLib.idle_add(self._scan_ready, paths, error, scan_id)

    def _scan_ready(self, paths, error, scan_id):
        if scan_id != self.scan_id:
            return GLib.SOURCE_REMOVE
        if error:
            self.message(f"Could not completely scan the folder: {error}")
        if not paths:
            self.empty_title.set_markup("<big><b>No wallpaper images found</b></big>")
            self.empty_detail.set_text("Choose another folder or include subfolders.")
            self.stack.set_visible_child_name("empty")
            self.status.set_text(f"0 images in {self._folder_name()}")
            return GLib.SOURCE_REMOVE
        self.stack.set_visible_child_name("gallery")
        self.status.set_text(f"Loading {len(paths)} images…")
        threading.Thread(
            target=self._thumbnail_worker, args=(paths, scan_id), daemon=True
        ).start()
        return GLib.SOURCE_REMOVE

    def _thumbnail_worker(self, paths, scan_id):
        for path in paths:
            if scan_id != self.scan_id:
                return
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(path), 200, 125, True
                ).apply_embedded_orientation()
            except GLib.Error:
                continue
            GLib.idle_add(self._add_thumbnail, path, pixbuf, scan_id)
        GLib.idle_add(self._finish_thumbnails, scan_id)

    def _add_thumbnail(self, path, pixbuf, scan_id):
        if scan_id == self.scan_id:
            tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            tile.set_size_request(200, -1)
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.set_size_request(200, 125)
            tile.pack_start(image, False, False, 0)
            label = Gtk.Label(label=path.name, ellipsize=3, max_width_chars=25)
            label.set_tooltip_text(str(path))
            tile.pack_start(label, False, False, 0)
            child = Gtk.FlowBoxChild()
            child.wallpaper_path = path
            child.add(tile)
            self.flow.add(child)
            child.show_all()
            self.loaded += 1
        return GLib.SOURCE_REMOVE

    def _finish_thumbnails(self, scan_id):
        if scan_id == self.scan_id:
            noun = "image" if self.loaded == 1 else "images"
            self.status.set_text(
                f"{self.loaded} {noun} in {self._folder_name()}"
            )
        return GLib.SOURCE_REMOVE

    def _selection_changed(self, flow):
        children = flow.get_selected_children()
        self.selected = children[0].wallpaper_path if children else None
        self.apply_button.set_sensitive(self.selected is not None)
        if self.selected:
            self.status.set_text(self.selected.name)

    def apply(self):
        if not self.selected:
            return
        if not shutil.which("xwallpaper"):
            self.message("Install xwallpaper with your distribution's package manager first.")
            return
        if not os.environ.get("DISPLAY"):
            self.message("No X11 display was detected; xwallpaper requires X11.")
            return
        output = self.output.get_active_id() or "All displays"
        available = self._refresh_outputs()
        if output != "All displays" and output not in available:
            self.message(f"Display {output} is no longer connected. Choose another display.")
            return
        command = wallpaper_command(
            self.selected, self.mode.get_active_id() or "zoom", output)
        try:
            result = subprocess.run(command,
                capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as error:
            self.message(f"Could not run xwallpaper: {error}")
            return
        if result.returncode:
            self.message("Could not apply wallpaper: " +
                         (result.stderr.strip() or "unknown xwallpaper error"))
            return
        self.settings.update(folder=str(self.folder), last_wallpaper=str(self.selected),
            mode=self.mode.get_active_id(), output=output,
            recursive=self.recursive.get_active())
        self.remember()
        persistence_errors = []
        for destination, save_command in (
            ("~/.xinitrc", save_xinitrc_command),
            ("DWM autostart", save_dwm_autostart_command),
        ):
            try:
                save_command(command)
            except OSError as error:
                persistence_errors.append(f"{destination}: {error}")
        if persistence_errors:
            self.message("Wallpaper applied, but startup could not be updated: " +
                         "; ".join(persistence_errors))
            return
        self.message(f"Applied {self.selected.name}", Gtk.MessageType.INFO)
