"""GTK application lifecycle."""

from .constants import APP_ID
from .gtk import Gio, Gtk
from .window import Window


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        window = self.get_active_window() or Window(self)
        window.show_all()
        if not window.info_label.get_text():
            window.info.hide()
        window.present()
