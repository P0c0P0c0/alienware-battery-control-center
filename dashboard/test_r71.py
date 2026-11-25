from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import chart
import widget


class ControlTests(unittest.TestCase):
    def test_cairo_symbols_are_distinct_transparent_raw_pixels(self):
        size = chart.SYMBOL_SIZE
        symbols = [chart.button_symbol(name) for name in ("hide", "settings", "exit")]
        self.assertEqual(len({bytes(pixels) for pixels in symbols}), 3)
        for pixels in symbols:
            self.assertEqual(len(pixels), size * size * 4)
            self.assertEqual(pixels[3], 0)
            self.assertGreater(max(pixels[3::4]), 0)

    def test_buttons_use_raw_pixbuf_and_accessible_actions(self):
        gtk = Mock()
        app = widget.Widget()
        action = Mock()
        with patch.object(widget, "Gtk", gtk):
            hide = app.symbol_button("hide", "Sembunyikan", action)
            settings = app.symbol_button("settings", "Pengaturan")
            app.symbol_button("exit", "Keluar", action)
        self.assertEqual(gtk.Button.call_count, 2)
        gtk.ToggleButton.assert_called_once_with()
        gtk.MenuButton.assert_not_called()
        gtk.Image.new_from_icon_name.assert_not_called()
        self.assertEqual(gtk.Image.new_from_pixbuf.call_count, 3)
        for call in gtk.Image.new_from_pixbuf.call_args_list:
            pixbuf = call.args[0]
            self.assertTrue(pixbuf.get_has_alpha())
            self.assertEqual(pixbuf.get_width(), chart.SYMBOL_SIZE)
        hide.connect.assert_called_with("clicked", action)
        settings.get_accessible().set_name.assert_called_once_with("Pengaturan")
        settings.set_tooltip_text.assert_called_once_with("Pengaturan")

    def test_popover_toggle_and_css(self):
        css = widget.Gtk.CssProvider()
        css.load_from_path(str(Path(widget.__file__).with_name("widget.css")))
        toggle, popover = Mock(), Mock()
        toggle.get_active.return_value = True
        widget.Widget.toggle_settings(toggle, popover)
        popover.popup.assert_called_once()
        toggle.get_active.return_value = False
        popover.get_visible.return_value = True
        widget.Widget.toggle_settings(toggle, popover)
        popover.popdown.assert_called_once()
        popover.get_visible.return_value = False
        widget.Widget.toggle_settings(toggle, popover)
        popover.popdown.assert_called_once()
