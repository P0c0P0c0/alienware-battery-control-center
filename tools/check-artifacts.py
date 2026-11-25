#!/usr/bin/python3
"""Inspect built archives without executing package scripts or extracting to the host."""
from io import BytesIO
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tarfile

from build import EPOCH, NAME, RUNTIME, VERSION, mode, sha, sources

output = Path(sys.argv[1])
files = sources()
archive = f"{NAME}-{VERSION}.tar.gz"
expected = {archive, *(f"{NAME}-{key}_{VERSION}_all.deb" for key in RUNTIME)}
verified = set()
for line in (output / "SHA256SUMS").read_text().splitlines():
    digest, filename = line.split("  ", 1)
    assert filename in expected and filename not in verified
    assert sha((output / filename).read_bytes()) == digest
    verified.add(filename)
assert verified == expected

prefix = f"{NAME}-{VERSION}/"
with tarfile.open(output / archive) as source:
    names = set()
    for item in source:
        assert item.name == prefix[:-1] or item.name.startswith(prefix)
        assert ".." not in PurePosixPath(item.name).parts
        assert (item.uid, item.gid, item.mtime) == (0, 0, EPOCH)
        if item.isdir():
            assert item.mode == 0o755
            continue
        name = item.name.removeprefix(prefix)
        assert item.isfile() and item.mode == mode(name)
        assert name in files and name not in names
        assert source.extractfile(item).read() == files[name]
        names.add(name)
    assert names == set(files)

for component in RUNTIME:
    package = f"{NAME}-{component}"
    deb = output / f"{package}_{VERSION}_all.deb"
    control = subprocess.check_output(["dpkg-deb", "--ctrl-tarfile", str(deb)])
    with tarfile.open(fileobj=BytesIO(control)) as contents:
        assert {item.name for item in contents if item.isfile()} == {"./control"}
        fields = contents.extractfile("./control").read().decode()
        assert f"Package: {package}\n" in fields and f"Version: {VERSION}\n" in fields
        assert "Architecture: all\n" in fields
    data = subprocess.check_output(["dpkg-deb", "--fsys-tarfile", str(deb)])
    allowed_source = {f"./usr/share/{package}/{name}": name
                      for name in ("release_ops.py", *(f"{component}/{name}" for name in RUNTIME[component]))}
    seen = set()
    with tarfile.open(fileobj=BytesIO(data)) as contents:
        for item in contents:
            assert ".." not in PurePosixPath(item.name).parts and (item.uid, item.gid) == (0, 0)
            if item.isdir():
                assert item.mode == 0o755
                continue
            assert item.isfile() and not item.mode & (stat.S_ISUID | stat.S_ISGID)
            blob = contents.extractfile(item).read()
            if item.name in allowed_source:
                name = allowed_source[item.name]
                assert blob == files[name] and item.mode == mode(name)
                seen.add(item.name)
            else:
                assert item.name.startswith(f"./usr/share/doc/{package}/") and item.mode == 0o644
                name = item.name.rsplit("/", 1)[-1]
                assert blob == files["LICENSE" if name == "copyright" else name]
        assert seen == set(allowed_source)
print("Source and Debian archives match checksums, allowed payloads, ownership and modes. No maintainer scripts.")
