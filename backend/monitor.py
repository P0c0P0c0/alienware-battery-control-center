#!/usr/bin/python3
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from html import escape
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from tempfile import NamedTemporaryFile

STATE = Path("/var/lib/alienware-battery-monitor")
POWER = Path("/sys/class/power_supply")
FIRMWARE = Path("/sys/class/firmware-attributes/dell-wmi-sysman/attributes")
EXPECTED = dict(PrimaryBattChargeCfg="Custom", AdvBatteryChargeCfg="Disabled",
                CustomChargeStart="50", CustomChargeStop="70")
DAY = 86400
NUMERIC = ("charge_full", "charge_full_design", "charge_now", "capacity",
           "temp", "voltage_now", "current_now")


def read(path, convert=str):
    try:
        value = path.read_text().strip()
        return convert(value) if value else None
    except (OSError, ValueError):
        return None


def sample(power=POWER, firmware=FIRMWARE):
    battery = power / "BAT0"
    data = {key: read(battery / key, int) for key in NUMERIC}
    for key in ("status", "health"):
        data[key] = read(battery / key)
    data["ac_online"] = read(power / "AC/online", int)
    for key in ("charge_full", "charge_full_design", "charge_now", "voltage_now"):
        if data[key] is not None and data[key] < 0:
            data[key] = None
    if data["charge_full_design"] == 0:
        data["charge_full_design"] = None
    if data["capacity"] not in range(101):
        data["capacity"] = None
    if data["ac_online"] not in (0, 1):
        data["ac_online"] = None
    full, design = data["charge_full"], data["charge_full_design"]
    data["soh_pct"] = 100 * full / design if full is not None and design else None
    data["temp_c"] = data["temp"] / 10 if data["temp"] is not None else None
    data["firmware"] = {key: read(firmware / key / "current_value") for key in EXPECTED}
    return data


def emit(level, message):
    priorities = {"high": 3, "warning": 4, "recovered": 5, "info": 6}
    print(f"<{priorities[level]}>BAT-05 {level} {message}", flush=True)


def threshold(value, warning, high, lower=False):
    if value is None:
        return None
    if lower:
        return "high" if value <= high else "warning" if value <= warning else None
    return "high" if value >= high else "warning" if value >= warning else None


def record(db, now, data):
    db.execute("CREATE TABLE IF NOT EXISTS samples (ts INTEGER PRIMARY KEY, soh REAL, data TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS active (key TEXT PRIMARY KEY, level TEXT, detail TEXT)")
    db.execute("""CREATE TABLE IF NOT EXISTS events
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, key TEXT, level TEXT, detail TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS events_ts ON events(ts)")
    changes = []
    with db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM samples WHERE ts < ?", (now - 365 * DAY,))
        db.execute("DELETE FROM events WHERE ts < ?", (now - 365 * DAY,))
        old = db.execute("""SELECT soh FROM samples WHERE ts BETWEEN ? AND ?
                            AND soh IS NOT NULL ORDER BY ts DESC LIMIT 1""",
                         (now - 7 * DAY - 600, now - 7 * DAY)).fetchone()
        soh = data["soh_pct"]
        drop = round(old[0] - soh, 10) if old and soh is not None else None
        faults = {}

        def check(key, level, detail, available=True, track_detail=False):
            if not available:
                return
            prior = db.execute("SELECT level, detail FROM active WHERE key = ?", (key,)).fetchone()
            if level:
                if prior and prior[0] == level and (not track_detail or prior[1] == detail):
                    return
                db.execute("INSERT OR REPLACE INTO active VALUES (?, ?, ?)", (key, level, detail))
            elif prior:
                level, detail = "recovered", prior[1]
                db.execute("DELETE FROM active WHERE key = ?", (key,))
            else:
                return
            db.execute("INSERT INTO events(ts,key,level,detail) VALUES (?,?,?,?)",
                       (now, key, level, detail))
            changes.append((level, f"{key}: {detail}"))

        temp = data["temp_c"]
        check("temperature", threshold(temp, 40, 45), f"{temp} °C", temp is not None)
        check("soh", threshold(soh, 42, 40, lower=True), f"{soh} %", soh is not None)
        check("soh_drop", threshold(drop, 1, 2), f"{drop} percentage points in 7 days", drop is not None)
        health = data["health"]
        check("health", "warning" if health != "Good" else None, str(health), health is not None, True)
        for key, expected in EXPECTED.items():
            value = data["firmware"][key]
            check(f"firmware.{key}", "warning" if value != expected else None,
                  f"{value} (expected {expected})", value is not None, True)
        faults.update({key: value for key, value in data.items() if key != "firmware"})
        faults.update({f"firmware.{key}": value for key, value in data["firmware"].items()})
        missing = ", ".join(sorted(key for key, value in faults.items() if value is None))
        check("missing", "warning" if missing else None, missing, track_detail=True)
        db.execute("INSERT OR REPLACE INTO samples VALUES (?, ?, ?)", (now, soh, json.dumps(data)))
    return changes


def failure():
    marker = STATE / "monitoring.failed"
    try:
        with marker.open("x"):
            pass
    except FileExistsError:
        return
    emit("high", "monitoring failed; inspect alienware-battery-monitor.service")


def collect():
    now = int(time.time())
    data = sample()
    with closing(sqlite3.connect(STATE / "monitor.sqlite3", timeout=10)) as db:
        changes = record(db, now, data)
    for level, message in changes:
        emit(level, message)
    marker = STATE / "monitoring.failed"
    if marker.exists():
        marker.unlink()
        emit("recovered", "monitoring resumed")
    emit("info", f"sample persisted at {stamp(now)}")


def stamp(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def report(db, command, now):
    if command == "status":
        row = db.execute("SELECT ts, data FROM samples ORDER BY ts DESC LIMIT 1").fetchone()
        return {"latest": {"timestamp": stamp(row[0]), **json.loads(row[1])}
                if row else None}
    if command == "alerts":
        return {"active": list(db.execute("SELECT key,level,detail FROM active ORDER BY key")),
                "events": [[stamp(ts), key, level, detail] for ts, key, level, detail in db.execute(
                    "SELECT ts,key,level,detail FROM events ORDER BY id DESC LIMIT 100")],
                "monitoring_failed": (STATE / "monitoring.failed").exists()}
    days = {"daily": 1, "weekly": 7, "monthly": 30}[command]
    rows = db.execute("SELECT ts,soh,data FROM samples WHERE ts BETWEEN ? AND ? ORDER BY ts",
                      (now - days * DAY, now)).fetchall()
    values = [soh for _, soh, _ in rows if soh is not None]
    temps = [data["temp_c"] for _, _, raw in rows if (data := json.loads(raw))["temp_c"] is not None]
    return {"days": days, "samples": len(rows), "valid_soh": len(values),
            "first": stamp(rows[0][0]) if rows else None, "last": stamp(rows[-1][0]) if rows else None,
            "soh_mean_pct": sum(values) / len(values) if values else None,
            "soh_first_pct": values[0] if values else None, "soh_last_pct": values[-1] if values else None,
            "max_temp_c": max(temps, default=None)}


def notify():
    # The graphical user's service owns the session bus and its own cursor.
    client = Path("/usr/bin/notify-send")
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if os.geteuid() == 0 or not runtime or not client.is_file() or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return
    runtime = Path(runtime)
    info = runtime.lstat()
    if not runtime.is_absolute() or runtime.is_symlink() or not runtime.is_dir() or (
            info.st_uid != os.geteuid() or info.st_mode & 0o077):
        raise OSError("Notification runtime directory is not private")
    database = STATE / "monitor.sqlite3"
    if not os.access(database, os.R_OK):
        return
    cursor = runtime / "alienware-battery-notify.json"
    if cursor.is_symlink():
        raise OSError("Notification cursor must not be a symlink")
    saved = read(cursor, json.loads)
    if not isinstance(saved, dict):
        saved = {}
    event_id = saved.get("id", 0)
    if type(event_id) is not int or not 0 <= event_id <= 2**63 - 1:
        event_id = 0
    identity = database.stat().st_ino
    if saved.get("database") != identity:
        event_id = 0
    now = int(time.time())
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
        events = db.execute("""SELECT id, key, level, detail FROM events WHERE id > ? AND ts >= ?
                               ORDER BY id LIMIT 100""", (event_id, now - 600)).fetchall()
    marker = STATE / "monitoring.failed"
    failed = marker.exists()
    messages = []
    if failed != saved.get("failed", False):
        messages.append(("monitoring", "high" if failed else "recovered",
                         "Monitoring failed" if failed else "Monitoring resumed"))
    messages.extend((key, level, detail) for _, key, level, detail in events)
    if messages:
        urgency = "critical" if any(level == "high" for _, level, _ in messages) else "normal"
        body = "\n".join(escape(f"{key} ({level}): {detail}") for key, level, detail in messages)
        subprocess.run([str(client), "--urgency=" + urgency, "--", "BAT-05", body],
                       check=True, timeout=10)
    with NamedTemporaryFile(mode="w", dir=runtime, prefix=".alienware-battery-", delete=False) as file:
        pending = Path(file.name)
        try:
            json.dump({"id": events[-1][0] if events else event_id,
                       "database": identity, "failed": failed}, file)
            file.flush()
            pending.replace(cursor)
        finally:
            pending.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("status", "daily", "weekly", "monthly", "alerts",
                                           "sample", "failure", "notify"))
    command = parser.parse_args().command
    try:
        if command == "sample":
            collect()
        elif command == "failure":
            failure()
        elif command == "notify":
            notify()
        else:
            with closing(sqlite3.connect((STATE / "monitor.sqlite3").as_uri() + "?mode=ro",
                                         uri=True, timeout=10)) as db:
                print(json.dumps(report(db, command, int(time.time())), indent=2))
    except (OSError, sqlite3.Error, subprocess.SubprocessError) as error:
        if command in ("sample", "failure"):
            emit("high", str(error))
        else:
            print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
