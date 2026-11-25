"""Manifest verification and one-generation program swaps for trusted installers."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory

VERSION = "1.0.0"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def absent(path):
    return not os.path.lexists(path)


def safe_parent(path):
    for parent in path.parents:
        require(not parent.is_symlink(), f"Symlink parent: {parent}")
        if os.geteuid() == 0 and parent.exists():
            info = parent.stat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
                    f"Untrusted administrator path: {parent}")


def write_new(path, data, mode):
    safe_parent(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink()
        raise


def write_manifest(path, manifest):
    write_new(path, (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(), 0o600)


def owned_path(path, kind):
    info = path.lstat()
    require(kind(info.st_mode) and info.st_uid == os.geteuid() and not info.st_mode & 0o022,
            f"Unexpected ownership or permissions: {path}")
    if stat.S_ISREG(info.st_mode):
        require(info.st_nlink == 1, f"Unexpected hard link: {path}")


def verify_manifest(program, directory, component, program_names, outside):
    safe_parent(directory)
    owned_path(directory, stat.S_ISDIR)
    require({p.name for p in directory.iterdir()} == {*program_names, "manifest.json"},
            f"Unexpected contents: {directory}")
    manifest = directory / "manifest.json"
    owned_path(manifest, stat.S_ISREG)
    data = json.loads(manifest.read_text())
    require(data.get("component") == component and isinstance(data.get("version"), str),
            "Installation was not created by this release installer")
    mapping = {str(program / name): directory / name for name in program_names}
    mapping.update({str(path): path for path in outside})
    hashes = data.get("files")
    require(isinstance(hashes, dict) and set(hashes) == set(mapping), "Manifest scope mismatch")
    for name, path in mapping.items():
        safe_parent(path)
        owned_path(path, stat.S_ISREG)
        require(digest(path.read_bytes()) == hashes[name], f"Installed file differs: {path}")
    return data


@contextmanager
def lock(path):
    safe_parent(path)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                and not info.st_mode & 0o077 and info.st_nlink == 1, "Unsafe installer lock")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def swap(program, candidate, displaced, stop, start, restore):
    """Replace a verified directory, restoring its predecessor on startup failure."""
    stop()
    moved = activated = False
    try:
        program.rename(displaced)
        moved = True
        candidate.rename(program)
        activated = True
        start()
    except BaseException:
        if activated:
            stop()
            program.rename(candidate)
        if moved:
            displaced.rename(program)
        restore()
        raise


def transition(program, action, verify, payloads, stop, start, restore):
    previous = program.with_name(program.name + ".previous")
    current = verify(program)
    with TemporaryDirectory(prefix=".release-", dir=program.parent) as working:
        candidate = Path(working) / "program"
        if action == "rollback":
            verify(previous)
            swap(program, previous, candidate, stop, start, restore)
            return
        require(absent(previous), f"Previous version already retained at {previous}")
        require(set(payloads) <= {Path(path).name for path in current["files"]}, "Unexpected upgrade scope")
        candidate.mkdir(mode=stat.S_IMODE(program.stat().st_mode))
        updated = {**current, "version": VERSION, "files": dict(current["files"])}
        for name, (data, mode) in payloads.items():
            write_new(candidate / name, data, mode)
            updated["files"][str(program / name)] = digest(data)
        require(updated != current, "The installed program is already current")
        write_manifest(candidate / "manifest.json", updated)
        verify(candidate)
        swap(program, candidate, previous, stop, start, restore)


def recover(program, verify, stop, start):
    previous = program.with_name(program.name + ".previous")
    require(absent(program), "Recovery requires the installed program directory to be absent")
    verify(previous)
    stop()
    previous.rename(program)
    start()


def finalize(program, verify, program_names):
    previous = program.with_name(program.name + ".previous")
    verify(program)
    verify(previous)
    for name in (*program_names, "manifest.json"):
        (previous / name).unlink()
    previous.rmdir()
