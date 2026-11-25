from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import telemetry


class SnapshotTests(unittest.TestCase):
    def test_read_only_cache_invalidation_and_rolling_buckets(self):
        now = 3_000_000
        with TemporaryDirectory() as directory:
            path = Path(directory) / "monitor.sqlite3"
            with closing(sqlite3.connect(path)) as writer:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute("PRAGMA wal_autocheckpoint=0")
                with writer:
                    writer.execute("CREATE TABLE samples(ts INTEGER PRIMARY KEY, soh REAL, data TEXT)")
                    writer.execute("CREATE TABLE active(key, level, detail)")
                    writer.executemany("INSERT INTO samples VALUES (?, ?, '{}')",
                                       [(now - 2592001, 41), (now - 86400, 42),
                                        (now - 86100, 43), (now + 10, 45), (now - 1, None)])
                cache = telemetry.BackendCache(path)
                with patch("telemetry.sqlite3.connect", wraps=sqlite3.connect) as connect:
                    cache.load(now)
                    self.assertEqual(cache.history(now, 86400), [(now - 86400, 42), (now - 86100, 43)])
                    self.assertEqual(cache.history(now + 10, 86400), [(now - 86100, 43), (now + 10, 45)])
                    marker = path.with_name("monitoring.failed")
                    marker.touch()
                    self.assertEqual(cache.load(now + 10).alerts[0][0], "monitoring")
                    self.assertEqual(connect.call_count, 1)
                    marker.unlink()
                    with writer:
                        writer.execute("UPDATE samples SET soh=46 WHERE ts=?", (now + 10,))
                        writer.execute("INSERT INTO active VALUES ('a', 'high', 'details')")
                    self.assertEqual(cache.load(now + 11).alerts, [("a", "high", "details")])
                    self.assertEqual(cache.history(now + 11, 86400)[-1], (now + 10, 46))
                    self.assertEqual(connect.call_count, 2)
                    cache.load(now - 1)
                    self.assertEqual(cache.history(now - 1, 2592000)[0], (now - 2592001, 41))
                    self.assertEqual(connect.call_count, 3)
                    with patch("telemetry.os.access", return_value=False):
                        self.assertIn("AKSES DITOLAK", cache.load(now).status)
                        self.assertEqual(cache.history(now, 86400), [])
                    self.assertEqual(cache.load(now).status, "DATABASE TERBACA")

    def test_database_replacement_and_disappearance(self):
        now = 3_000_000
        with TemporaryDirectory() as directory:
            path = Path(directory) / "monitor.sqlite3"
            replacement = path.with_name("replacement")
            for database, soh in ((path, 40), (replacement, 50)):
                with closing(sqlite3.connect(database)) as db, db:
                    db.execute("CREATE TABLE samples(ts INTEGER PRIMARY KEY, soh REAL, data TEXT)")
                    db.execute("CREATE TABLE active(key, level, detail)")
                    db.execute("INSERT INTO samples VALUES (?, ?, '{}')", (now, soh))
            cache = telemetry.BackendCache(path)
            cache.load(now)
            replacement.replace(path)
            cache.load(now + 1)
            self.assertEqual(cache.history(now + 1, 86400), [(now, 50)])
            path.unlink()
            self.assertEqual(cache.load(now + 2).status, "DATABASE BELUM TERSEDIA")
            self.assertEqual(cache.history(now + 2, 86400), [])
