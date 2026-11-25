from contextlib import closing
from pathlib import Path
import json
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import deploy
import telemetry


class TelemetryTests(unittest.TestCase):
    def test_live_sysfs_has_unit_conversions_and_missing(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            battery = root / "BAT0"
            battery.mkdir()
            (root / "AC").mkdir()
            (root / "AC/online").write_text("1")
            for key, raw in {"charge_full": "4000000", "charge_full_design": "8000000",
                             "voltage_min_design": "12000000", "capacity": "92", "temp": "351",
                             "voltage_now": "11701000", "current_now": "-1000",
                             "status": "Not charging"}.items():
                (battery / key).write_text(raw)
            sample = telemetry.live(root)
            self.assertAlmostEqual(sample["soh"], 50.0)
            self.assertAlmostEqual(sample["capacity"], 48.0)
            self.assertAlmostEqual(sample["design"], 96.0)
            self.assertAlmostEqual(sample["voltage"], 11.701)
            self.assertEqual((sample["current"], sample["temperature"], sample["ac"]), (-0.001, 35.1, 1))
            self.assertTrue(sample["estimated_wh"])
            (battery / "charge_full_design").write_text("0")
            self.assertIsNone(telemetry.live(root)["soh"])

    def test_backend_latest_history_staleness_and_no_writes(self):
        now = 3_000_000
        with TemporaryDirectory() as directory:
            database = Path(directory) / "monitor.sqlite3"
            firmware = {"CustomChargeStart": "50", "CustomChargeStop": "70"}
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("CREATE TABLE samples(ts INTEGER PRIMARY KEY, soh REAL, data TEXT)")
                db.execute("CREATE TABLE active(key TEXT, level TEXT, detail TEXT)")
                db.execute("INSERT INTO active VALUES (?, ?, ?)", ("temperature", "high", "synthetic"))
                db.executemany("INSERT INTO samples VALUES (?, ?, ?)",
                               [(now - age, soh, json.dumps({"firmware": firmware}))
                                for age, soh in [(900, 44.75), (86401, 44.80), (700000, 44.91),
                                                 (2800000, 46), (-10, 12)]])
                db.execute("DELETE FROM samples WHERE ts > ?", (now,))
            before = database.read_bytes()
            status = telemetry.load_backend(database, now)
            self.assertEqual(status.firmware, firmware)
            self.assertIn("STALE", telemetry.freshness(status.timestamp, now))
            self.assertNotIn("STALE", telemetry.freshness(now - 899, now))
            self.assertEqual(status.alerts[0][:2], ("temperature", "high"))
            for label, count in (("24 jam", 1), ("7 hari", 2), ("30 hari", 3)):
                self.assertEqual(len(status.history[label]), count)
            self.assertEqual(database.read_bytes(), before)
            self.assertEqual(list(database.parent.iterdir()), [database])

    def test_permission_errors_and_absent_backend(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "missing.db"
            self.assertIn("BELUM TERSEDIA", telemetry.load_backend(path).status)
            path.touch()
            with patch("telemetry.os.access", return_value=False):
                self.assertIn("login ulang", telemetry.load_backend(path).status)
            self.assertEqual(telemetry.freshness(200, 100), "STALE · jam sistem berubah")

class DeployTests(unittest.TestCase):
    def test_failed_install_and_scoped_rollback(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            program = root / "local/program"
            unit = root / "systemd" / deploy.NAME
            link = unit.parent / "graphical-session.target.wants" / unit.name
            launcher = root / "applications" / "app.desktop"
            manifest = program / "manifest.json"
            unrelated = root / "unrelated"
            unrelated.write_text("preserve")
            with patch.multiple(deploy, PROGRAM=program, UNIT=unit, LINK=link,
                                LAUNCHER=launcher, MANIFEST=manifest), \
                    patch.dict(deploy.os.environ, {"XDG_SESSION_TYPE": "x11"}), \
                    patch.object(deploy.os, "geteuid", return_value=1000), \
                    patch.object(deploy, "run"), patch.object(deploy, "require_running"), \
                    patch.object(deploy, "systemctl") as control:
                unit.parent.mkdir()
                unit.write_text("existing")
                with self.assertRaisesRegex(RuntimeError, "Existing installation path"):
                    deploy.install()
                self.assertEqual(unit.read_text(), "existing")
                unit.unlink()

                def fail(*args, **kwargs):
                    if args[:2] == ("enable", "--now"):
                        link.parent.mkdir()
                        link.symlink_to(unit)
                        raise subprocess.CalledProcessError(1, args)
                    return control.return_value

                control.return_value.returncode = 0
                control.return_value.stdout = "not-found\n"
                control.side_effect = fail
                with self.assertRaises(subprocess.CalledProcessError):
                    deploy.install()
                self.assertFalse(program.exists())
                self.assertFalse(link.is_symlink())
                self.assertFalse(unit.exists())

                control.side_effect = None
                deploy.install()
                (program / "unrelated").touch()
                with self.assertRaisesRegex(RuntimeError, "Unexpected contents"):
                    deploy.uninstall()
                (program / "unrelated").unlink()
                deploy.uninstall()
                self.assertFalse(program.exists())
                self.assertFalse(unit.exists())
                self.assertEqual(unrelated.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
