#!/usr/bin/python3
"""Install and manage the current desktop user’s dashboard."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE.parent))
from release_ops import (VERSION, absent, digest, finalize, lock, recover, require, safe_parent,
                         transition, verify_manifest, write_manifest, write_new)
COMPONENT = "ABCC dashboard"
HOME = Path.home()
PROGRAM = HOME / ".local/share/bat07-widget"
def xdg_path(key, default):
    path = Path(os.environ.get(key, ""))
    return path if path.is_absolute() else default


CONFIG = xdg_path("XDG_CONFIG_HOME", HOME / ".config")
DATA = xdg_path("XDG_DATA_HOME", HOME / ".local/share")
UUID = "bat07-widget@alienware.local"
EXTENSION = DATA / "gnome-shell/extensions" / UUID
NAME = "bat07-widget.service"
UNIT = CONFIG / "systemd/user" / NAME
LINK = UNIT.parent / "graphical-session.target.wants" / NAME
MANIFEST = PROGRAM / "manifest.json"
PROGRAM_FILES = ("widget.py", "widget.css", "telemetry.py", "chart.py", "probe.py", "show.sh")
EXTENSION_FILES = {"extension.js": "extension.js", "metadata.json": "metadata.json"}
LAUNCHER = DATA / "applications" / "io.github.bat07.Widget.desktop"


def run(*command, check=True, capture=False):
    return subprocess.run(command, check=check, text=True, capture_output=capture)


def systemctl(*args, **kwargs):
    return run("systemctl", "--user", *args, **kwargs)


def settings():
    from gi.repository import Gio

    return Gio.Settings.new("org.gnome.shell")


def configure_extension(enabled):
    from gi.repository import Gio

    prefs = settings()
    entries = prefs.get_strv("enabled-extensions")
    if enabled and UUID not in entries:
        entries.append(UUID)
    if not enabled and UUID in entries:
        entries.remove(UUID)
    require(prefs.set_strv("enabled-extensions", entries), "Daftar ekstensi GNOME tidak dapat ditulis")
    Gio.Settings.sync()


def payloads(wayland):
    files = {PROGRAM / name: SOURCE / name for name in PROGRAM_FILES}
    files[UNIT] = SOURCE / NAME
    files[LAUNCHER] = SOURCE / "launcher.desktop"
    if wayland:
        files.update({EXTENSION / target: SOURCE / name for target, name in EXTENSION_FILES.items()})
    return files


def preflight():
    require(os.geteuid() != 0, "Run as the desktop user")
    require(sys.platform.startswith("linux") and sys.version_info >= (3, 10),
            "Linux and Python 3.10 or later are required")
    import widget
    require(widget.Gtk.get_major_version() == 3, "GTK 3 is required")
    run(sys.executable, "-B", str(SOURCE / "probe.py"))
    systemctl("is-active", "graphical-session.target")
    wayland = os.environ.get("XDG_SESSION_TYPE") == "wayland"
    if wayland:
        version = run("gnome-shell", "--version", capture=True).stdout
        require(re.search(r"\b50(?:\.|\b)", version), "GNOME Shell 50 is required on Wayland")
        require(not settings().get_boolean("disable-user-extensions"), "User extensions are disabled")
    return wayland


def install():
    wayland = preflight()
    if wayland:
        require(UUID not in settings().get_strv("enabled-extensions"), "Extension UUID is already enabled")
    files = payloads(wayland)
    directories = [PROGRAM, EXTENSION] if wayland else [PROGRAM]
    for path in (*directories, *files, LINK, PROGRAM.with_name(PROGRAM.name + ".previous")):
        safe_parent(path)
        require(absent(path), f"Existing installation path: {path}")
    state = systemctl("show", NAME, "-p", "LoadState", "--value", capture=True, check=False)
    require(state.stdout.strip() == "not-found", "An existing dashboard unit is loaded")
    hashes = {}
    created = []
    dirs = []
    extension_enabled = False
    unit_ready = False
    try:
        for directory in directories:
            directory.parent.mkdir(parents=True, exist_ok=True)
            directory.mkdir(mode=0o700)
            dirs.append(directory)
        for target, source in files.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            data = payload_bytes(target, source)
            write_new(target, data, 0o755 if target.name in ("widget.py", "show.sh") else 0o644)
            created.append(target)
            hashes[str(target)] = digest(data)
        write_manifest(MANIFEST, {"component": COMPONENT, "version": VERSION,
                                  "wayland": wayland, "files": hashes})
        created.append(MANIFEST)
        if wayland:
            extension_enabled = True
            configure_extension(True)
        unit_ready = True
        systemctl("daemon-reload")
        systemctl("enable", "--now", NAME)
        require_running()
        if wayland:
            print("Untuk memuat ekstensi baru, login ulang pada GNOME Wayland sebelum verifikasi.")
    except BaseException:
        if unit_ready:
            result = systemctl("disable", "--now", NAME, check=False)
            require(result.returncode == 0, "Could not stop dashboard. Installed files were kept.")
            if LINK.is_symlink() and LINK.resolve() == UNIT:
                LINK.unlink()
        if extension_enabled:
            configure_extension(False)
        for target in reversed(created):
            target.unlink()
        for directory in reversed(dirs):
            directory.rmdir()
        if unit_ready:
            systemctl("daemon-reload", check=False)
        raise


def payload_bytes(target, source):
    require(source.is_file() and not source.is_symlink(), f"Invalid payload: {source.name}")
    data = source.read_bytes()
    if target == LAUNCHER:
        path = str(PROGRAM / "show.sh")
        require(not any(ord(char) < 32 for char in path), "Invalid desktop launcher path")
        path = path.replace("\\", "\\\\").replace('"', '\\"')
        path = path.replace("$", "\\$").replace("`", "\\`").replace("%", "%%")
        data = data.decode().replace("@EXEC@", '"' + path.replace("\\", "\\\\") + '"').encode()
    return data


def verify_directory(directory):
    safe_parent(directory)
    path = directory / "manifest.json"
    require(directory.is_dir() and not directory.is_symlink() and path.is_file() and not path.is_symlink(),
            "Invalid dashboard manifest")
    raw = json.loads(path.read_text())
    require(type(raw.get("wayland")) is bool, "Invalid desktop type")
    outside = [path for path in payloads(raw["wayland"]) if path.parent != PROGRAM]
    data = verify_manifest(PROGRAM, directory, COMPONENT, PROGRAM_FILES, outside)
    if data["wayland"]:
        require(EXTENSION.is_dir() and not EXTENSION.is_symlink()
                and {item.name for item in EXTENSION.iterdir()} == set(EXTENSION_FILES),
                "Unexpected extension contents")
    require(absent(LINK) or (LINK.is_symlink() and LINK.resolve() == UNIT), "Unexpected autostart link")
    return data


def verify_files():
    data = verify_directory(PROGRAM)
    return data["wayland"], payloads(data["wayland"])


def uninstall():
    wayland, files = verify_files()
    require(absent(PROGRAM.with_name(PROGRAM.name + ".previous")), "Resolve the retained upgrade before uninstalling")
    systemctl("disable", "--now", NAME)
    if wayland:
        run("gnome-extensions", "disable", UUID, check=False)
        configure_extension(False)
    for path in files:
        path.unlink()
    MANIFEST.unlink()
    PROGRAM.rmdir()
    if wayland:
        EXTENSION.rmdir()
    systemctl("daemon-reload")


STARTUP_SECONDS = 10
STARTUP_PROPERTIES = ("ActiveState", "SubState", "MainPID", "NRestarts",
                      "InvocationID", "ExecMainStartTimestampMonotonic")


def startup_snapshot():
    properties = [f"--property={name}" for name in STARTUP_PROPERTIES]
    output = systemctl("show", NAME, *properties, capture=True).stdout
    values = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
    require(all(values.get(name) for name in STARTUP_PROPERTIES),
                   "BAT-07 startup status is incomplete")
    require(values["ActiveState"] == "active" and values["SubState"] == "running",
                   "BAT-07 left the active/running state during startup")
    require(values["MainPID"].isdecimal() and int(values["MainPID"]) > 0,
                   "BAT-07 did not acquire a main PID")
    require(values["NRestarts"] == "0", "BAT-07 restarted during startup")
    started = values["ExecMainStartTimestampMonotonic"]
    require(started.isdecimal() and int(started) > 0 and values["InvocationID"].strip("0"),
                   "BAT-07 start identity is unavailable")
    return tuple(values[name] for name in STARTUP_PROPERTIES)


def require_running():
    initial = startup_snapshot()
    deadline = time.monotonic() + STARTUP_SECONDS
    while (remaining := deadline - time.monotonic()) > 0:
        time.sleep(min(1, remaining))
        require(startup_snapshot() == initial, "BAT-07 process identity changed during startup")
    # Sample on or after the deadline as well, even if scheduling skipped the loop.
    require(startup_snapshot() == initial, "BAT-07 process identity changed during startup")



def change(action):
    wayland = preflight()

    def check(directory):
        manifest = verify_directory(directory)
        require(manifest["wayland"] == wayland, "Desktop type changed")
        return manifest

    def stop():
        systemctl("stop", NAME)

    def start():
        systemctl("start", NAME)
        require_running()

    if action == "finalize":
        finalize(PROGRAM, check, PROGRAM_FILES)
        return
    if action == "recover":
        recover(PROGRAM, check, stop, start)
        return
    files = payloads(wayland)
    for path, source in files.items():
        if path.parent != PROGRAM:
            require(path.is_file() and not path.is_symlink() and path.read_bytes() == payload_bytes(path, source),
                    f"Desktop integration migration requires separate review: {path.name}")
    was_active = systemctl("is-active", "--quiet", NAME, check=False).returncode == 0
    program = {path.name: (payload_bytes(path, source), 0o755 if path.name in ("widget.py", "show.sh") else 0o644)
               for path, source in files.items() if path.parent == PROGRAM}
    transition(PROGRAM, action, check, program, stop, start, start if was_active else lambda: None)


def measurement_identity():
    result = systemctl("show", NAME, "-p", "MainPID", "-p", "ActiveState",
                       "-p", "NRestarts", "-p", "InvocationID", capture=True)
    info = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    pid = info.get("MainPID", "")
    require(info.get("ActiveState") == "active" and pid.isdecimal() and int(pid) > 0,
            "Widget tidak memiliki PID aktif")
    require(info.get("NRestarts") == "0", "Widget telah restart otomatis atau status restart tidak tersedia")
    invocation = info.get("InvocationID", "")
    require(invocation.strip("0"), "Identitas service widget tidak tersedia")
    return pid, invocation


def verify():
    wayland, _files = verify_files()
    run(sys.executable, "-B", str(SOURCE / "probe.py"))
    systemctl("is-enabled", NAME)
    systemctl("is-active", NAME)
    timer = run("systemctl", "is-active", "alienware-battery-monitor.timer", check=False, capture=True)
    from telemetry import load_backend, freshness
    import time

    backend = load_backend()
    print(f"BAT-05 timer: {timer.stdout.strip() or 'tidak dapat diverifikasi'}")
    print(f"BAT-05 backend: {backend.status} · {freshness(backend.timestamp, time.time())}")
    if wayland:
        status = run("gnome-extensions", "info", UUID, capture=True)
        print(status.stdout, end="")
        require(re.search(r"(?m)^\s*State:\s+ACTIVE\s*$", status.stdout),
                "Ekstensi belum aktif. Login ulang lalu periksa kembali.")
    identity = measurement_identity()
    run(sys.executable, "-B", str(SOURCE / "probe.py"), "--pid", identity[0])
    require(measurement_identity() == identity, "Service widget berubah selama pengukuran")
    require(timer.returncode == 0, "Timer BAT-05 tidak terverifikasi aktif")
    require(backend.status == "DATABASE TERBACA" and backend.timestamp is not None
            and not freshness(backend.timestamp, time.time()).startswith("STALE"),
            "BAT-05 belum memberikan sampel terkini yang dapat dibaca")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "install", "verify", "uninstall", "upgrade", "rollback", "recover", "finalize"))
    parser.add_argument("--confirm", action="store_true", help="authorize this user installation change")
    args = parser.parse_args()
    os.environ["LC_ALL"] = "C.UTF-8"
    try:
        require(os.geteuid() != 0, "Run as the desktop user")
        if args.action in ("preflight", "verify"):
            {"preflight": preflight, "verify": verify}[args.action]()
        else:
            require(args.confirm, "Explicit --confirm is required")
            guard = PROGRAM.parent / ".alienware-battery-control-center.lock"
            safe_parent(guard)
            guard.parent.mkdir(parents=True, exist_ok=True)
            with lock(guard):
                if args.action in ("install", "uninstall"):
                    {"install": install, "uninstall": uninstall}[args.action]()
                else:
                    change(args.action)
    except (OSError, ValueError, KeyError, ImportError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Dashboard {args.action}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
