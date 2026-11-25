from contextlib import redirect_stderr
from io import StringIO
import os
import unittest
from unittest.mock import patch

import widget


class DisplayReadinessTests(unittest.TestCase):
    def start(self, checks, session="wayland"):
        now = 0
        sleeps = []

        def sleep(seconds):
            nonlocal now
            sleeps.append(seconds)
            now += seconds

        connected = object()

        def get_display():
            return connected if now >= checks else None

        with patch.dict(os.environ, {"XDG_SESSION_TYPE": session}), \
                patch("widget.time.monotonic", side_effect=lambda: now), \
                patch("widget.time.sleep", side_effect=sleep), \
                patch("widget.GLib.set_prgname"), \
                patch("widget.Gtk.init_check") as gtk_init, \
                patch("widget.Gdk.Display.get_default", side_effect=get_display), \
                patch("widget.Widget") as application, redirect_stderr(StringIO()) as errors:
            application.return_value.run.return_value = 0
            result = widget.main()
        return result, sleeps, gtk_init.call_count, application.call_count, errors.getvalue()

    def test_ready_immediately(self):
        self.assertEqual(self.start(0), (0, [], 1, 1, ""))

    def test_retries_until_wayland_connects(self):
        for session in ("wayland", ""):
            with self.subTest(session=session):
                self.assertEqual(self.start(0.5, session), (0, [0.25, 0.25], 3, 1, ""))

    def test_timeout_fails_without_creating_widget(self):
        code, sleeps, checks, applications, errors = self.start(float("inf"))
        self.assertEqual((code, applications), (1, 0))
        self.assertEqual(sum(sleeps), widget.DISPLAY_READY_TIMEOUT)
        self.assertEqual(checks, 1 + len(sleeps))
        self.assertIn("compositor GTK", errors)

    def test_explicit_x11_failure_is_immediate(self):
        code, sleeps, checks, applications, _ = self.start(float("inf"), "x11")
        self.assertEqual((code, sleeps, checks, applications), (1, [], 1, 0))
