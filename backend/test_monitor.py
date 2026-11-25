from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import monitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.now = 400 * monitor.DAY
        self.data = dict.fromkeys(monitor.NUMERIC, 1)
        self.data.update(soh_pct=87.25, temp_c=35.2, status="Not charging",
                         health="Good", ac_online=1, firmware=monitor.EXPECTED.copy())

    def collect(self, offset=0, **updates):
        return [(level, message.split(":")[0]) for level, message in
                monitor.record(self.db, self.now + offset, self.data | updates)]

    def test_temperature_and_soh_boundaries_and_dedup(self):
        self.assertEqual(self.collect(temp_c=40, soh_pct=42),
                         [("warning", "temperature"), ("warning", "soh")])
        self.assertEqual(self.collect(300, temp_c=45, soh_pct=40),
                         [("high", "temperature"), ("high", "soh")])
        self.assertEqual(self.collect(600, temp_c=46, soh_pct=39), [])
        self.assertEqual(self.collect(900), [("recovered", "temperature"), ("recovered", "soh")])

    def test_soh_drop_needs_actual_history(self):
        self.assertEqual(self.collect(soh_pct=47), [])
        self.assertEqual(self.collect(6 * monitor.DAY), [])
        self.assertEqual(self.collect(7 * monitor.DAY, soh_pct=46), [("warning", "soh_drop")])
        self.assertEqual(self.collect(7 * monitor.DAY + 300, soh_pct=45), [("high", "soh_drop")])
        self.assertEqual(self.collect(7 * monitor.DAY + 600, soh_pct=47), [("recovered", "soh_drop")])

    def test_missing_does_not_clear_active_temperature(self):
        self.collect(temp_c=45)
        self.assertEqual(self.collect(300, temp_c=None), [("warning", "missing")])
        self.assertEqual(self.collect(600, temp_c=None), [])
        self.assertEqual(self.collect(900), [("recovered", "temperature"), ("recovered", "missing")])

    def test_firmware_and_health_changes(self):
        key = "firmware.CustomChargeStop"
        self.assertEqual(self.collect(health="Dead", firmware=monitor.EXPECTED | {"CustomChargeStop": "80"}),
                         [("warning", "health"), ("warning", key)])
        self.assertEqual(self.collect(300, health="Dead", firmware=monitor.EXPECTED | {"CustomChargeStop": "90"}),
                         [("warning", key)])
        self.assertEqual(self.collect(600), [("recovered", "health"), ("recovered", key)])

    def test_retention_and_reports(self):
        self.collect(-365 * monitor.DAY - 1, temp_c=45)
        self.collect(-365 * monitor.DAY)
        self.collect()
        self.assertEqual(self.db.execute("SELECT count(*) FROM samples").fetchone()[0], 2)
        self.assertEqual(self.db.execute("SELECT level FROM events").fetchall(), [("recovered",)])
        for name in ("daily", "weekly", "monthly"):
            self.assertEqual(monitor.report(self.db, name, self.now)["samples"], 1)
        self.assertEqual(monitor.report(self.db, "status", self.now)["latest"]["soh_pct"], 87.25)
        self.assertEqual(len(monitor.report(self.db, "alerts", self.now)["events"]), 1)

    def test_atomic_transaction(self):
        self.collect()
        self.db.execute("""CREATE TRIGGER reject_sample BEFORE INSERT ON samples
                           BEGIN SELECT RAISE(ABORT, 'synthetic'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.collect(301, temp_c=45)
        self.assertEqual(self.db.execute("SELECT count(*) FROM events").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM active").fetchone()[0], 0)

    def test_failure_dedup_and_recovery(self):
        with TemporaryDirectory() as directory, patch.object(monitor, "STATE", Path(directory)), \
                patch.object(monitor, "emit") as emit, patch.object(monitor, "sample", return_value=self.data):
            monitor.failure()
            monitor.failure()
            monitor.collect()
            monitor.collect()
            self.assertEqual([call.args[0] for call in emit.call_args_list],
                             ["high", "recovered", "info", "info"])
            with closing(sqlite3.connect(Path(directory) / "monitor.sqlite3")) as database:
                self.assertIsNotNone(database.execute("SELECT ts FROM samples").fetchone())

    def test_read_validation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            battery = root / "BAT0"
            battery.mkdir()
            (battery / "charge_full").write_text("300")
            for invalid in ("0", "-1", "bad", ""):
                (battery / "charge_full_design").write_text(invalid)
                result = monitor.sample(root, root / "firmware")
                self.assertIsNone(result["soh_pct"])
                self.assertIsNone(result["charge_full_design"])
                self.assertIsNone(result["capacity"])
            (battery / "charge_full_design").write_text("600")
            self.assertEqual(monitor.sample(root, root / "firmware")["soh_pct"], 50)


if __name__ == "__main__":
    unittest.main()
