import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import deploy


class BackendDeploymentTests(unittest.TestCase):
    def test_preflight_rejects_missing_dependency_and_unsupported_model(self):
        with patch("deploy.os.access", return_value=False), self.assertRaisesRegex(RuntimeError, "Missing required"):
            deploy.preflight()
        with TemporaryDirectory() as directory, patch.multiple(deploy, DMI=Path(directory), POWER=Path(directory)), \
                patch("deploy.os.access", return_value=True), patch("deploy.run") as command:
            with self.assertRaisesRegex(RuntimeError, "Unsupported hardware"):
                deploy.preflight()
            command.assert_not_called()
            (Path(directory) / "sys_vendor").write_text("Dell Inc.")
            (Path(directory) / "product_name").write_text("Alienware Synthetic")
            (Path(directory) / "BAT0").mkdir()
            deploy.preflight()
            command.assert_called_once_with("systemctl", "show", "--property=Version", "--value")

    def test_new_state_rejects_a_prepopulated_reader_group(self):
        with TemporaryDirectory() as directory, patch("deploy.STATE", Path(directory) / "missing"), \
                patch("deploy.grp.getgrnam", return_value=SimpleNamespace(gr_gid=1234, gr_mem=["fixture"])):
            with self.assertRaisesRegex(RuntimeError, "already grants"):
                deploy.state_group()

    def test_install_uninstall_upgrade_and_failure_keep_synthetic_history(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            program, state = root / "program", root / "state"
            unit = root / deploy.TIMER
            state.mkdir(mode=0o750)
            history = state / "monitor.sqlite3"
            with sqlite3.connect(history) as db:
                db.execute("CREATE TABLE samples (ts INTEGER)")
                db.execute("INSERT INTO samples VALUES (123)")
            history.chmod(0o640)
            original = history.read_bytes()
            payload = {"monitor.py": b"# synthetic v1", deploy.TIMER: b"timer"}
            result = SimpleNamespace(stdout="not-found\n", returncode=0)
            with patch.multiple(deploy, PROGRAM=program, STATE=state, ADMIN_UID=os.geteuid(),
                                OUTSIDE={unit: deploy.TIMER}), \
                    patch("deploy.preflight"), patch("deploy.run", return_value=result) as command, \
                    patch("deploy.grp.getgrnam", return_value=SimpleNamespace(gr_gid=os.getegid())), \
                    patch("deploy.source_bytes", side_effect=lambda name: payload[name]):
                unit.touch()
                with self.assertRaisesRegex(RuntimeError, "Existing installation path"):
                    deploy.install()
                command.assert_not_called()
                unit.unlink()
                with patch("deploy.start", side_effect=RuntimeError("synthetic failed activation")):
                    with self.assertRaisesRegex(RuntimeError, "failed activation"):
                        deploy.install()
                self.assertFalse(program.exists())
                self.assertFalse(unit.exists())
                self.assertEqual(history.read_bytes(), original)

                deploy.install()
                self.assertEqual((program / "monitor.py").read_bytes(), payload["monitor.py"])
                previous = program.with_name(program.name + ".previous")
                payload["monitor.py"] = b"# synthetic v2"
                with patch("deploy.start", side_effect=[RuntimeError("new failed"), None]):
                    with self.assertRaisesRegex(RuntimeError, "new failed"):
                        deploy.change("upgrade")
                self.assertEqual((program / "monitor.py").read_bytes(), b"# synthetic v1")
                self.assertFalse(previous.exists())
                deploy.change("upgrade")
                self.assertEqual((program / "monitor.py").read_bytes(), b"# synthetic v2")
                deploy.change("rollback")
                self.assertFalse(previous.exists())
                self.assertEqual((program / "monitor.py").read_bytes(), b"# synthetic v1")
                program.rename(previous)
                deploy.change("recover")
                self.assertFalse(previous.exists())
                self.assertEqual((program / "monitor.py").read_bytes(), b"# synthetic v1")
                deploy.change("upgrade")
                deploy.change("finalize")
                self.assertFalse(previous.exists())
                self.assertEqual((program / "monitor.py").read_bytes(), b"# synthetic v2")

                deploy.uninstall()
                self.assertFalse(program.exists())
                self.assertEqual(history.read_bytes(), original)
                deploy.install()
                self.assertEqual(history.read_bytes(), original)

                bogus = state / "monitoring.failed"
                bogus.symlink_to(history)
                with self.assertRaisesRegex(RuntimeError, "Unsafe retained state"):
                    deploy.validate_state(os.getegid())
                bogus.unlink()
                manifest = program / "manifest.json"
                data = json.loads(manifest.read_text())
                data["files"][str(root / "other")] = "x"
                manifest.write_text(json.dumps(data))
                with self.assertRaisesRegex(RuntimeError, "Manifest scope"):
                    deploy.uninstall()
                self.assertEqual(history.read_bytes(), original)
