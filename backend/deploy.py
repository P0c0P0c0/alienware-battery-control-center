#!/usr/bin/python3
"""Explicit system administrator actions for the BAT-05 monitoring backend."""
import sys
import os

if __name__ == "__main__" and os.geteuid() == 0 and not sys.flags.isolated:
    sys.exit("Invoke the administrator installer with /usr/bin/python3 -IB")

import argparse
import grp
from pathlib import Path
import pwd
import shutil
import sqlite3
import stat
import subprocess
from contextlib import closing

SOURCE = Path(__file__).absolute().parent
if __name__ == "__main__" and os.geteuid() == 0:
    for entry in (SOURCE / "deploy.py", SOURCE / "monitor.py", SOURCE.parent / "release_ops.py",
                  *SOURCE.parents, SOURCE):
        info = entry.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            sys.exit(f"Untrusted administrator source: {entry}")
sys.path[:0] = [str(SOURCE), str(SOURCE.parent)]
import monitor
from release_ops import (VERSION, absent, digest, finalize, lock, recover, require, safe_parent,
                         transition, verify_manifest, write_manifest, write_new)

NAME = "alienware-battery-monitor"
PROGRAM = Path("/opt") / NAME
STATE = monitor.STATE
DMI = Path("/sys/class/dmi/id")
POWER = monitor.POWER
SYSTEM = Path("/etc/systemd/system")
USER = Path("/etc/systemd/user")
TIMER = NAME + ".timer"
SERVICE = NAME + ".service"
FAILURE = NAME + "-failure.service"
OUTSIDE = {SYSTEM / name: name for name in (TIMER, SERVICE, FAILURE)}
OUTSIDE.update({USER / name: name for name in ("alienware-battery-notify.service", "alienware-battery-notify.timer")})
COMPONENT = "ABCC backend"
COMMANDS = {"systemctl": "/usr/bin/systemctl", "groupadd": "/usr/sbin/groupadd"}
STATE_NAMES = {"monitor.sqlite3", "monitor.sqlite3-journal", "monitor.sqlite3-wal",
               "monitor.sqlite3-shm", "monitoring.failed"}
ADMIN_UID = 0
LOCK = Path("/run/alienware-battery-control-center-backend.lock")


def run(command, *args, check=True):
    return subprocess.run([COMMANDS[command], *args], check=check, text=True,
                          capture_output=True, env={"PATH": "/usr/sbin:/usr/bin", "LC_ALL": "C"})


def source_bytes(name):
    path = SOURCE / name
    require(path.is_file() and not path.is_symlink(), f"Invalid payload: {name}")
    if os.geteuid() == 0:
        info = path.stat()
        require(info.st_uid == 0 and not info.st_mode & 0o022, f"Untrusted payload: {name}")
    return path.read_bytes()


def preflight():
    require(sys.platform.startswith("linux") and sys.version_info >= (3, 10),
            "Linux and Python 3.10 or later are required")
    for executable in COMMANDS.values():
        require(os.access(executable, os.X_OK), f"Missing required executable: {executable}")
    vendor = monitor.read(DMI / "sys_vendor") or ""
    product = monitor.read(DMI / "product_name") or ""
    require(("alienware" in vendor.casefold() or
             ("dell" in vendor.casefold() and "alienware" in product.casefold()))
            and (POWER / "BAT0").is_dir(), "Unsupported hardware: Alienware with BAT0 is required")
    run("systemctl", "show", "--property=Version", "--value")
    if monitor.sample(POWER)["firmware"] != monitor.EXPECTED:
        print("Firmware differs from the monitored 50–70% policy or is unavailable. Monitoring remains read-only.")


def state_group():
    try:
        group = grp.getgrnam(NAME)
    except KeyError:
        require(absent(STATE), "Existing retained state has no matching reader group")
        run("groupadd", "--system", NAME)
        return grp.getgrnam(NAME).gr_gid
    if absent(STATE):
        require(not group.gr_mem and not any(account.pw_gid == group.gr_gid for account in pwd.getpwall()),
                "An existing reader group already grants database access; review it before first install")
    return group.gr_gid


def validate_state(gid):
    safe_parent(STATE)
    info = STATE.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == ADMIN_UID and info.st_gid == gid
            and stat.S_IMODE(info.st_mode) == 0o750, "Unsafe backend state directory")
    for entry in STATE.iterdir():
        info = entry.lstat()
        require(entry.name in STATE_NAMES and stat.S_ISREG(info.st_mode) and info.st_uid == ADMIN_UID
                and info.st_gid == gid and stat.S_IMODE(info.st_mode) & 0o137 == 0
                and info.st_nlink == 1, f"Unsafe retained state entry: {entry.name}")


def verify_program(directory):
    return verify_manifest(PROGRAM, directory, COMPONENT, ("monitor.py",), OUTSIDE)


def check_database():
    validate_state(grp.getgrnam(NAME).gr_gid)
    database = STATE / "monitor.sqlite3"
    require(database.is_file(), "The sampling service has not created its database")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
        require(db.execute("PRAGMA quick_check").fetchone() == ("ok",), "SQLite integrity check failed")
        require(db.execute("SELECT 1 FROM samples LIMIT 1").fetchone() is not None,
                "The sampling service has no samples")


def start():
    run("systemctl", "start", SERVICE)
    check_database()
    run("systemctl", "start", TIMER)
    run("systemctl", "is-active", TIMER)


def stop():
    run("systemctl", "stop", TIMER, SERVICE, FAILURE)


def install():
    preflight()
    for path in (PROGRAM, PROGRAM.with_name(PROGRAM.name + ".previous"), *OUTSIDE):
        safe_parent(path)
        require(absent(path), f"Existing installation path: {path}")
    for unit in (TIMER, SERVICE, FAILURE):
        result = run("systemctl", "show", "-p", "LoadState", "--value", unit, check=False)
        require(result.stdout.strip() == "not-found", f"Existing or unavailable unit: {unit}")
    payloads = {PROGRAM / "monitor.py": (source_bytes("monitor.py"), 0o755),
                **{path: (source_bytes(name), 0o644) for path, name in OUTSIDE.items()}}
    gid = state_group()
    safe_parent(STATE)
    if absent(STATE):
        STATE.mkdir(mode=0o750)
        os.chown(STATE, ADMIN_UID, gid)
        STATE.chmod(0o750)
    validate_state(gid)
    PROGRAM.mkdir(mode=0o755)
    PROGRAM.chmod(0o755)
    created = []
    loaded = False
    try:
        for path, (content, mode) in payloads.items():
            write_new(path, content, mode)
            created.append(path)
        write_manifest(PROGRAM / "manifest.json", {"version": VERSION, "component": COMPONENT,
                       "files": {str(path): digest(data) for path, (data, _) in payloads.items()}})
        created.append(PROGRAM / "manifest.json")
        loaded = True
        run("systemctl", "daemon-reload")
        start()
        run("systemctl", "enable", TIMER)
    except BaseException:
        if loaded:
            stopped = run("systemctl", "stop", TIMER, SERVICE, FAILURE, check=False)
            require(stopped.returncode == 0, "Could not stop services. Installed files and retained state were kept.")
            run("systemctl", "disable", TIMER, check=False)
        for path in reversed(created):
            path.unlink()
        PROGRAM.rmdir()
        if loaded:
            run("systemctl", "daemon-reload")
        raise


def uninstall():
    verify_program(PROGRAM)
    require(absent(PROGRAM.with_name(PROGRAM.name + ".previous")), "Resolve the retained upgrade before uninstalling")
    stop()
    run("systemctl", "disable", TIMER)
    for path in OUTSIDE:
        path.unlink()
    (PROGRAM / "manifest.json").unlink()
    (PROGRAM / "monitor.py").unlink()
    PROGRAM.rmdir()
    run("systemctl", "daemon-reload")


def change(action):
    preflight()
    validate_state(grp.getgrnam(NAME).gr_gid)
    if action == "finalize":
        finalize(PROGRAM, verify_program, ("monitor.py",))
        return
    if action == "recover":
        recover(PROGRAM, verify_program, stop, start)
        return
    for path, name in OUTSIDE.items():
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == source_bytes(name),
                f"Unit migration requires separate review: {name}")
    was_active = run("systemctl", "is-active", TIMER, check=False).returncode == 0
    transition(PROGRAM, action, verify_program, {"monitor.py": (source_bytes("monitor.py"), 0o755)},
               stop, start, start if was_active else lambda: None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "install", "uninstall", "upgrade", "rollback", "recover", "finalize"))
    parser.add_argument("--confirm", action="store_true", help="authorize this system change")
    args = parser.parse_args()
    try:
        if args.action == "preflight":
            preflight()
            return 0
        require(args.confirm and os.geteuid() == 0, "Explicit --confirm and a system administrator shell are required")
        with lock(LOCK):
            if args.action == "install":
                install()
            elif args.action == "uninstall":
                uninstall()
            else:
                change(args.action)
    except (OSError, RuntimeError, ValueError, KeyError, sqlite3.Error, subprocess.SubprocessError) as error:
        print(f"Backend {args.action}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
