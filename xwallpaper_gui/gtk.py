"""Central GTK imports and version declarations."""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk  # noqa: E402

__all__ = ["Gdk", "GdkPixbuf", "Gio", "GLib", "Gtk"]
