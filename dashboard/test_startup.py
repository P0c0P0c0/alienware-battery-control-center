from contextlib import redirect_stderr
from io import StringIO
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import widget


class DisplayReadinessTests(unittest.TestCase):
    def start(self, gtk_checks, displays, session="wayland"):
        now = 0
        sleeps = []

        def sleep(seconds):
            nonlocal now
            sleeps.append(seconds)
            now += seconds

        with patch.dict(os.environ, {"XDG_SESSION_TYPE": session}), \
                patch("widget.time.monotonic", side_effect=lambda: now), \
                patch("widget.time.sleep", side_effect=sleep), \
                patch("widget.GLib.set_prgname"), \
                patch("widget.Gtk.init_check", side_effect=((value, []) for value in gtk_checks)) as init, \
                patch("widget.Gdk.Display.get_default", side_effect=displays), \
                patch("widget.Widget") as application, redirect_stderr(StringIO()) as errors:
            application.return_value.activation_failed = False
            application.return_value.run.return_value = 0
            result = widget.main()
        return result, sleeps, init.call_count, application.call_count, errors.getvalue()

    def test_ready_immediately(self):
        self.assertEqual(self.start([True], [object()]), (0, [], 1, 1, ""))

    def test_retries_until_wayland_connects(self):
        for session in ("wayland", ""):
            with self.subTest(session=session):
                self.assertEqual(self.start([False, False, True], [object()], session),
                                 (0, [0.25, 0.25], 3, 1, ""))

    def test_false_readiness_does_not_start_widget(self):
        # A display alone or an init_check success without a default display is insufficient.
        with patch("widget.Gdk.Display.get_default", return_value=object()) as display, \
                patch("widget.Gtk.init_check", return_value=(False, [])), \
                patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}):
            self.assertFalse(widget.wait_for_display())
            display.assert_not_called()
        self.assertEqual(self.start([True, True], [None, object()]), (0, [0.25], 2, 1, ""))

    def test_timeout_fails_without_creating_widget(self):
        probes = 1 + int(widget.DISPLAY_READY_TIMEOUT / widget.DISPLAY_READY_INTERVAL)
        code, sleeps, checks, applications, errors = self.start([False] * probes, [])
        self.assertEqual((code, applications), (1, 0))
        self.assertEqual(sum(sleeps), widget.DISPLAY_READY_TIMEOUT)
        self.assertEqual(checks, probes)
        self.assertIn("compositor GTK", errors)

    def test_explicit_x11_failure_is_immediate(self):
        code, sleeps, checks, applications, _ = self.start([False], [], "x11")
        self.assertEqual((code, sleeps, checks, applications), (1, [], 1, 0))

    def test_activation_exception_fails_application_and_command_line(self):
        app = widget.Widget()
        command = SimpleNamespace(get_arguments=lambda: ["widget.py", "show"])

        def run(_args):
            self.assertEqual(app.do_command_line(command), 1)
            return 0  # An ordinary GApplication run status must not hide a callback failure.

        with patch.object(app, "run", side_effect=run), \
                patch.object(app, "activate", side_effect=app.do_activate), \
                patch.object(app, "create_window", side_effect=RuntimeError("window creation failed")), \
                patch.object(app, "quit") as quit_app, \
                patch("widget.GLib.set_prgname"), patch("widget.Widget", return_value=app), \
                patch("widget.wait_for_display", return_value=True), redirect_stderr(StringIO()) as errors:
            self.assertEqual(widget.main(), 1)
        quit_app.assert_called_once_with()
        self.assertIn("window creation failed", errors.getvalue())
