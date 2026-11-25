from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import chart
import deploy
import telemetry
import widget


class RedrawTests(unittest.TestCase):
    def test_cairo_buffers_use_glib_fast_bytes_path(self):
        symbol = chart.button_symbol("settings")
        plot = chart.raster(chart.WIDTH, chart.HEIGHT, chart.paint_history, (), (), chart.HISTORY_DIVISIONS)
        self.assertIs(type(symbol), bytes)
        self.assertIs(type(plot), bytes)
        self.assertEqual(widget.GLib.Bytes.new(plot).get_data(), plot)

    def test_footer_changes_one_fixed_row_and_keeps_stale_color(self):
        app = widget.Widget()
        app.labels = {key: Mock() for key in ("backend", "alert")}
        app.clock_store = widget.Gtk.ListStore(str, str, str)
        app.clock_row = app.clock_store.append(("", "", ""))
        changes = []
        app.clock_store.connect("row-changed", lambda *_: changes.append(tuple(app.clock_store[0])))
        app.backend = telemetry.Backend("DATABASE TERBACA", 100)
        app.update_footer(998)
        app.update_footer(998)
        app.update_footer(1000)
        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[0], ("usia 14m 58d", f"SYSFS {widget.stamp(998)}", "#a8b7c5"))
        self.assertEqual(changes[1], ("STALE · usia 15m 00d", f"SYSFS {widget.stamp(1000)}", "#ffbf71"))

    def test_axis_change_leaves_plot_and_repeated_selection_reuses_history(self):
        app = widget.Widget()
        app.graph = Mock()
        app.backend_at = 3_000_000
        app.backend_cache = Mock()
        app.backend_cache.history.return_value = [(app.backend_at - 3600, 45)]
        app.draw()
        app.draw()
        app.graph.set_from_pixbuf.assert_called_once()
        app.backend_cache.history.assert_called_once()

        plot_before = app.history_rasters["plot"][1]
        axis_before = app.history_rasters["axis"][1]
        app.backend_at += 60
        app.history_layouts.clear()
        app.draw()
        self.assertEqual(app.graph.set_from_pixbuf.call_count, 2)
        self.assertIs(app.history_rasters["plot"][1], plot_before)
        self.assertNotEqual(app.history_rasters["axis"][1], axis_before)
        self.assertEqual(app.backend_cache.history.call_count, 2)


class MeasurementTests(unittest.TestCase):
    def test_verifier_detects_changed_invocation_and_nonzero_restart(self):
        template = "MainPID=123\nActiveState=active\nNRestarts={}\nInvocationID={}\n"
        first = SimpleNamespace(stdout=template.format(0, "one"))
        timer = SimpleNamespace(stdout="active\n", returncode=0)
        backend = telemetry.Backend("DATABASE TERBACA", 100)
        for last, error in ((template.format(0, "two"), "berubah"),
                            (template.format(1, "one"), "restart")):
            second = SimpleNamespace(stdout=last)
            with self.subTest(last=last), \
                    patch("deploy.verify_files", return_value=(False, {})), \
                    patch("deploy.run", return_value=timer) as run, \
                    patch("deploy.systemctl", side_effect=[None, None, first, second]), \
                    patch("telemetry.load_backend", return_value=backend), \
                    patch("sys.stdout", new_callable=StringIO), \
                    self.assertRaisesRegex(RuntimeError, error):
                deploy.verify()
            self.assertEqual(run.call_args.args[-2:], ("--pid", "123"))
