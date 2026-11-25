import contextlib
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import chart
import probe
import telemetry
import widget


class DrawingTests(unittest.TestCase):
    def test_gauges_and_protection_use_actual_readings(self):
        self.assertEqual(chart.gauge_reading(45.125, "SOH", "Good"),
                         ("45.12%", "Perlu perhatian", "danger", 0.4512))
        self.assertEqual(chart.gauge_reading(92, "SOC"), ("92%", "Terisi", "good", 0.92))
        self.assertEqual(chart.gauge_reading(None, "SOC")[2:], ("muted", None))
        self.assertEqual(chart.gauge_reading(89, "SOH", "Unknown")[2], "warning")
        firmware = {"CustomChargeStart": "50", "CustomChargeStop": "70"}
        for soc, text, tone in ((49, "1 poin di bawah", "warning"), (50, "Dalam target", "good"),
                                (70, "Dalam target", "good"), (92, "22 poin di atas", "warning"),
                                (None, "Deviasi —", "muted")):
            self.assertEqual(chart.charge_target(firmware, soc), ((50, 70), "Target 50–70%", text, tone))
        self.assertIsNone(chart.charge_target({"CustomChargeStart": "75", "CustomChargeStop": "70"}, 60)[0])
        self.assertIsNone(chart.charge_target({}, 60)[0])

    def test_history_coordinates_skip_missing_samples_and_break_gaps(self):
        now = 3_000_000
        for span in telemetry.PERIODS.values():
            samples = [(now - span - 1, 90), (now - span, 44), (now - span + 10, 45),
                       (now - 10, 43), (now, float("inf")), (now + 1, 99)]
            drawing = chart.history_layout(samples, now, span)
            points, levels, times = drawing
            self.assertEqual([connected for _, _, connected in points], [False, True, False])
            self.assertEqual((len(levels), len(times)), (3, 3))
            self.assertTrue(all(51 <= x <= chart.WIDTH - 13 and 12 <= y <= 92 for x, y, _ in points))
            pixels = chart.raster(chart.WIDTH, chart.HEIGHT, chart.paint_history, points, levels, chart.HISTORY_DIVISIONS)
            self.assertEqual(len(pixels), chart.WIDTH * chart.HEIGHT * 3)
            self.assertEqual(pixels[:3], bytes(chart.PANEL_RGB))
            self.assertNotEqual(pixels, bytes(chart.PANEL_RGB) * (chart.WIDTH * chart.HEIGHT))
            self.assertEqual(chart.history_layout([], now, span)[:2], ((), ()))

    def test_css_loads_and_rasters_upload_only_on_visual_changes(self):
        css = widget.Gtk.CssProvider()
        css.load_from_path(str(Path(widget.__file__).with_name("widget.css")))
        app = widget.Widget()
        image = Mock()
        args = (chart.GAUGE_SIZE, chart.GAUGE_SIZE, chart.paint_gauge)
        app.set_image("SOC", image, *args, 0.92, "good")
        app.set_image("SOC", image, *args, 0.92, "good")
        image.set_from_pixbuf.assert_called_once()
        pixbuf = image.set_from_pixbuf.call_args.args[0]
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (chart.GAUGE_SIZE,) * 2)
        app.set_image("SOC", image, *args, 0.70, "good")
        self.assertEqual(image.set_from_pixbuf.call_count, 2)

    def test_unchanged_labels_and_style_are_not_written(self):
        app = widget.Widget()
        field = Mock()
        field.get_text.return_value = "92%"
        app.set_text(field, "92%")
        field.set_text.assert_not_called()
        app.set_text(field, "91%")
        field.set_text.assert_called_once_with("91%")
        app.set_tone(field, "good")
        app.set_tone(field, "good")
        style = field.get_style_context.return_value
        style.add_class.assert_called_once_with("good")
        app.set_tone(field, "warning")
        style.remove_class.assert_called_once_with("good")

    def test_live_refresh_and_period_change_use_existing_cache(self):
        app = widget.Widget()
        app.backend_cache = Mock()
        app.backend_cache.load.return_value = telemetry.Backend("DATABASE TERBACA")
        app.update_live = Mock()
        app.update_protection = Mock()
        app.update_footer = Mock()
        app.graph = Mock()
        app.set_image = Mock()
        app.backend_cache.history.return_value = []
        ticks = ({"timestamp": now, "charge": 60} for now in range(100, 132, 2))
        with patch("widget.live", side_effect=ticks) as live:
            for _ in range(16):
                app.refresh()
        self.assertEqual(live.call_count, 16)
        self.assertEqual(app.backend_cache.load.call_count, 2)
        self.assertEqual(app.update_footer.call_count, 16)
        for period in telemetry.PERIODS:
            app.change_period(SimpleNamespace(get_active=lambda: True), period)
            app.backend_cache.history.assert_called_with(130, telemetry.PERIODS[period])
        self.assertEqual(app.backend_cache.load.call_count, 2)


class VerifierTests(unittest.TestCase):
    def test_strict_cpu_and_rss_limits(self):
        for ticks, peak, result in ((119, 99, 0), (120, 99, 1), (119, 100, 1)):
            readings = [(1, 0, 50)] + [(1, ticks, peak)] * 60
            with patch("probe.time.sleep"), patch("probe.time.monotonic", side_effect=(0, 60)), \
                    patch("probe.os.sysconf", return_value=100), \
                    patch("probe.process_sample", side_effect=readings), \
                    contextlib.redirect_stdout(StringIO()):
                self.assertEqual(probe.measure(1000), result)

    def test_pid_change_still_fails(self):
        with patch("probe.time.sleep"), patch("probe.process_sample", side_effect=((1, 0, 50), (2, 0, 50))):
            with self.assertRaisesRegex(RuntimeError, "PID berubah"):
                probe.measure(1000)
