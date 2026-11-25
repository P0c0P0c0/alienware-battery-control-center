"""Read-only data access for BAT-07."""
from contextlib import closing
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sqlite3
import time

POWER = Path("/sys/class/power_supply")
DATABASE = Path("/var/lib/alienware-battery-monitor/monitor.sqlite3")
PERIODS = {"24 jam": 86400, "7 hari": 604800, "30 hari": 2592000}
STALE_SECONDS = 900


def read(path, convert=str, minimum=None, maximum=None):
    try:
        value = convert(path.read_text().strip())
        if value == "" or (minimum is not None and value < minimum):
            return None
        return None if maximum is not None and value > maximum else value
    except (OSError, ValueError):
        return None


def live(power=POWER):
    battery = power / "BAT0"
    full = read(battery / "charge_full", int, 0)
    design = read(battery / "charge_full_design", int, 1)
    reference_uv = read(battery / "voltage_min_design", int, 1)
    energy = read(battery / "energy_full", int, 0)
    energy_design = read(battery / "energy_full_design", int, 1)
    temperature = read(battery / "temp", int)
    voltage = read(battery / "voltage_now", int, 1)
    current = read(battery / "current_now", int)
    return {
        "timestamp": time.time(), "soh": 100 * full / design if full is not None and design else None,
        "charge": read(battery / "capacity", int, 0, 100),
        "temperature": temperature / 10 if temperature is not None else None,
        "capacity": energy / 1e6 if energy is not None else
        full * reference_uv / 1e12 if full is not None and reference_uv else None,
        "design": energy_design / 1e6 if energy_design is not None else
        design * reference_uv / 1e12 if design and reference_uv else None,
        "estimated_wh": (energy is None and full is not None and reference_uv is not None)
        or (energy_design is None and design is not None and reference_uv is not None),
        "voltage": voltage / 1e6 if voltage is not None else None,
        "current": current / 1e6 if current is not None else None,
        "ac": read(power / "AC/online", int, 0, 1),
        "status": read(battery / "status"),
        "health": read(battery / "health"),
    }


@dataclass
class Backend:
    status: str
    timestamp: int | None = None
    firmware: dict = field(default_factory=dict)
    alerts: list = field(default_factory=list)
    history: dict = field(default_factory=dict)


def database_signature(database):
    signature = []
    for suffix in ("", "-wal", "-journal"):
        path = database.with_name(database.name + suffix)
        try:
            info = path.stat()
        except FileNotFoundError:
            if not suffix:
                raise
            signature.append(None)
        else:
            signature.append((info.st_dev, info.st_ino, info.st_size,
                              info.st_mtime_ns, info.st_ctime_ns))
    return tuple(signature)


class BackendCache:
    """Reuse a read-only snapshot until the database or required range changes."""

    def __init__(self, database=DATABASE):
        self.database = database
        self.signature = None
        self.loaded_at = None
        self.samples = []

    def load(self, now):
        database = self.database
        try:
            signature = database_signature(database)
            if not os.access(database, os.R_OK):
                raise PermissionError(database)
            if signature != self.signature or now < self.loaded_at:
                with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True,
                                             timeout=0.2)) as db:
                    db.execute("BEGIN")
                    latest = db.execute("SELECT ts, data FROM samples ORDER BY ts DESC LIMIT 1").fetchone()
                    if latest is None:
                        firmware, alerts, samples = {}, [], []
                    else:
                        firmware = json.loads(latest[1]).get("firmware") or {}
                        alerts = db.execute("SELECT key, level, detail FROM active ORDER BY level, key").fetchall()
                        samples = db.execute(
                            "SELECT ts, soh FROM samples WHERE ts >= ? AND soh IS NOT NULL ORDER BY ts",
                            (now - max(PERIODS.values()),)).fetchall()
                self.latest = latest
                self.firmware, self.alerts, self.samples = firmware, alerts, samples
                self.loaded_at = now
                self.signature = signature
            if self.latest is None:
                return Backend("BELUM ADA SAMPEL")
            failed = database.with_name("monitoring.failed").exists()
            alerts = self.alerts
            if failed:
                alerts = [("monitoring", "high", "Sampling gagal"), *alerts]
            status = "GAGAL SAMPLING" if failed else "DATABASE TERBACA"
            return Backend(status, self.latest[0], self.firmware, alerts)
        except (OSError, sqlite3.Error, ValueError, AttributeError) as error:
            self.signature = None
            self.samples = []
            if isinstance(error, PermissionError):
                return Backend("AKSES DITOLAK · login ulang jika baru bergabung ke grup BAT-05")
            if isinstance(error, FileNotFoundError):
                return Backend("DATABASE BELUM TERSEDIA")
            return Backend("DATABASE TAK DAPAT DIBACA")

    def history(self, now, seconds):
        start = now - seconds
        width = max(300, seconds // 300)
        buckets = {}
        for ts, soh in self.samples:
            if ts > now:
                break
            if ts >= start:
                buckets[(ts - start) // width] = (ts, soh)
        return list(buckets.values())


def load_backend(database=DATABASE, now=None):
    now = int(time.time()) if now is None else now
    cache = BackendCache(database)
    backend = cache.load(now)
    if backend.timestamp is not None:
        backend.history = {label: cache.history(now, span) for label, span in PERIODS.items()}
    return backend


def freshness(timestamp, now):
    if timestamp is None:
        return "usia —"
    if timestamp > now:
        return "STALE · jam sistem berubah"
    seconds = int(now - timestamp)
    return f"{'STALE · ' if seconds >= STALE_SECONDS else ''}usia {seconds // 60}m {seconds % 60:02d}d"
