#!/usr/bin/python3
"""Build deterministic source and scriptless Debian payloads without network access."""
import argparse
import gzip
import hashlib
from io import BytesIO
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from release_ops import VERSION

NAME = "alienware-battery-control-center"
EPOCH = 1795564800
PACKAGE_DEPS = {
    "backend": "python3 (>= 3.10), systemd, passwd",
    "dashboard": "python3 (>= 3.10), systemd, python3-gi, python3-cairo, gir1.2-gtk-3.0, gir1.2-gdkpixbuf-2.0",
}
PACKAGE_SUGGESTS = {
    "backend": "libnotify-bin",
    "dashboard": f"{NAME}-backend, gnome-shell",
}
RUNTIME = {
    "backend": ("deploy.py", "monitor.py", "alienware-battery-monitor.service",
                "alienware-battery-monitor-failure.service", "alienware-battery-monitor.timer",
                "alienware-battery-notify.service", "alienware-battery-notify.timer"),
    "dashboard": ("deploy.py", "widget.py", "widget.css", "chart.py", "telemetry.py", "probe.py",
                  "show.sh", "launcher.desktop", "bat07-widget.service", "extension.js", "metadata.json"),
}
EXECUTABLES = {"backend/deploy.py", "backend/monitor.py", "dashboard/deploy.py", "dashboard/widget.py",
               "dashboard/probe.py", "dashboard/show.sh", "tools/build.py", "tools/test-offline.sh",
               "tools/check-artifacts.py"}
DOCS = ("README.md", "LICENSE", "INSTALLATION.md", "ARCHITECTURE.md", "COMPATIBILITY.md",
        "TROUBLESHOOTING.md", "SECURITY.md", "DEPENDENCIES.md", "CHANGELOG.md")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def mode(name):
    return 0o755 if name in EXECUTABLES else 0o644


def payload(name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or str(relative) != name or ".." in relative.parts:
        raise ValueError(f"Unsafe source path: {name}")
    path = ROOT / name
    for parent in (path, *path.parents):
        if parent == ROOT:
            break
        if parent.is_symlink():
            raise ValueError(f"Symlink source: {name}")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"Source is not a regular file: {name}")
    return path.read_bytes()


def sources():
    manifest = payload("SOURCE.SHA256")
    files = {}
    for line in manifest.decode().splitlines():
        digest, name = line.split("  ", 1)
        data = payload(name)
        if name in files or name == "SOURCE.SHA256" or sha(data) != digest:
            raise ValueError(f"Invalid source checksum entry: {name}")
        files[name] = data
    files["SOURCE.SHA256"] = manifest
    return files


def source_archive(path, files):
    prefix = f"{NAME}-{VERSION}"
    directories = {prefix}
    for name in files:
        directories.update(str(PurePosixPath(prefix) / parent)
                           for parent in PurePosixPath(name).parents)
    with path.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=EPOCH) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name in sorted(directories):
                info = tarfile.TarInfo(name)
                info.type, info.mode, info.mtime = tarfile.DIRTYPE, 0o755, EPOCH
                archive.addfile(info)
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(f"{prefix}/{name}")
                info.mode, info.mtime, info.size = mode(name), EPOCH, len(data)
                archive.addfile(info, BytesIO(data))


def install_file(root, path, data, permissions=0o644):
    output = root / path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    output.chmod(permissions)


def deb_package(path, component, files, working):
    package = f"{NAME}-{component}"
    root = working / component
    share = f"usr/share/{package}"
    docs = f"usr/share/doc/{package}"
    for name in ("release_ops.py", *(f"{component}/{name}" for name in RUNTIME[component])):
        install_file(root, f"{share}/{name}", files[name], mode(name))
    for name in DOCS:
        install_file(root, f"{docs}/{name}", files[name])
    install_file(root, f"{docs}/copyright", files["LICENSE"])
    control = f"""Package: {package}
Version: {VERSION}
Section: utils
Priority: optional
Architecture: all
Maintainer: ABCC Release Preparation <release-preparation@users.noreply.invalid>
Depends: {PACKAGE_DEPS[component]}
Suggests: {PACKAGE_SUGGESTS[component]}
Description: Unofficial Alienware battery control center {component} payload
 Installs local program files only. Service activation is an explicit separate step.
"""
    install_file(root, "DEBIAN/control", control.encode())
    for entry in (root, *root.rglob("*")):
        if entry.is_dir():
            entry.chmod(0o755)
        os.utime(entry, (EPOCH, EPOCH))
    subprocess.run(["dpkg-deb", "--root-owner-group", "-Zxz", "-z6", "--build", str(root), str(path)],
                   check=True, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "SOURCE_DATE_EPOCH": str(EPOCH)})


def build(output, source_only):
    files = sources()
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".build-", dir=output) as directory:
        working = Path(directory)
        names = [f"{NAME}-{VERSION}.tar.gz"]
        source_archive(working / names[0], files)
        if not source_only:
            for component in RUNTIME:
                names.append(f"{NAME}-{component}_{VERSION}_all.deb")
                deb_package(working / names[-1], component, files, working)
        manifest = "".join(f"{sha((working / name).read_bytes())}  {name}\n" for name in names)
        for name in names:
            (working / name).replace(output / name)
        (working / "SHA256SUMS").write_text(manifest)
        (working / "SHA256SUMS").replace(output / "SHA256SUMS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    build(args.output.resolve(), args.source_only)
