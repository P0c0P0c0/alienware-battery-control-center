from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import os
import sys
import unittest
from unittest.mock import patch

import deploy


class DesktopReleaseTests(unittest.TestCase):
    def test_missing_bindings_and_unsupported_desktop(self):
        with patch("deploy.os.geteuid", return_value=1000), patch.dict(sys.modules, {"widget": None}):
            with self.assertRaises(ModuleNotFoundError):
                deploy.preflight()
        with patch("deploy.os.geteuid", return_value=1000), \
                patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}), \
                patch("deploy.run", return_value=SimpleNamespace(stdout="GNOME Shell 49.0")), \
                patch("deploy.systemctl"):
            with self.assertRaisesRegex(RuntimeError, "GNOME Shell 50"):
                deploy.preflight()

    def test_unconfirmed_cli_does_not_dispatch(self):
        with patch("deploy.os.geteuid", return_value=1000), patch.object(sys, "argv", ["deploy", "install"]), \
                patch("deploy.install") as install, patch("sys.stderr", new_callable=StringIO):
            self.assertEqual(deploy.main(), 1)
            install.assert_not_called()

    def test_desktop_upgrade_and_rollback_in_temporary_home(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            program = root / "program"
            unit = root / deploy.NAME
            launcher = root / "launcher.desktop"
            helper = deploy.payload_bytes

            def changed(target, source):
                data = helper(target, source)
                return data + b"\n# synthetic upgrade\n" if target == program / "widget.py" else data

            with patch.multiple(deploy, PROGRAM=program, UNIT=unit, LINK=root / "link",
                                LAUNCHER=launcher, MANIFEST=program / "manifest.json"), \
                    patch("deploy.preflight", return_value=False), patch("deploy.require_running"), \
                    patch("deploy.systemctl", return_value=SimpleNamespace(returncode=0, stdout="not-found\n")):
                deploy.install()
                original = (program / "widget.py").read_bytes()
                with patch("deploy.payload_bytes", side_effect=changed):
                    deploy.change("upgrade")
                    self.assertEqual((program / "widget.py").read_bytes(), original + b"\n# synthetic upgrade\n")
                    deploy.change("rollback")
                self.assertEqual((program / "widget.py").read_bytes(), original)
                deploy.uninstall()
                self.assertFalse(program.exists())
