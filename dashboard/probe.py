#!/usr/bin/python3
"""Check the session compositor and optionally measure the real widget PID."""
import argparse
import os
from pathlib import Path
import sys
import time


def detect():
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk, Gdk

    print(f"Desktop={os.getenv('XDG_CURRENT_DESKTOP', '—')} sesi={os.getenv('XDG_SESSION_TYPE', '—')}")
    print(f"GTK tersedia={gi.Repository.get_default().enumerate_versions('Gtk')}")
    Gtk.init_check()
    display = Gdk.Display.get_default()
    if not display:
        print("FAIL · compositor tidak dapat diakses GTK")
        return 1
    kind = display.__gtype__.name
    print(f"Backend GTK={kind}")
    if "X11" in kind:
        gi.require_version("GdkX11", "3.0")
        from gi.repository import GdkX11
        screen = display.get_default_screen()
        supports = isinstance(screen, GdkX11.X11Screen) and screen.supports_net_wm_hint(
            Gdk.Atom.intern("_NET_WM_STATE_ABOVE", False))
        print(f"X11 _NET_WM_STATE_ABOVE={supports}")
        return 0 if supports else 1
    if "Wayland" in kind and "GNOME" in os.getenv("XDG_CURRENT_DESKTOP", "").upper():
        print("Wayland: always-on-top memerlukan ekstensi BAT-07 pada GNOME Shell 50")
        return 0
    print("FAIL · compositor tidak didukung untuk always-on-top")
    return 1


def process_sample(pid):
    root = Path("/proc") / str(pid)
    stat = (root / "stat").read_text().rsplit(")", 1)[1].split()
    pages = int((root / "statm").read_text().split()[1])
    return int(stat[19]), int(stat[11]) + int(stat[12]), pages * os.sysconf("SC_PAGE_SIZE") / 2**20


def measure(pid):
    start = time.monotonic()
    identity, ticks, rss = process_sample(pid)
    peak = rss
    for _ in range(60):
        time.sleep(1)
        current_identity, total, rss = process_sample(pid)
        if current_identity != identity:
            raise RuntimeError("PID berubah selama pengukuran")
        peak = max(peak, rss)
    elapsed = time.monotonic() - start
    cpu = 100 * (total - ticks) / os.sysconf("SC_CLK_TCK") / elapsed
    print(f"{elapsed:.1f} detik · CPU rata-rata {cpu:.3f}% satu core · RSS puncak {peak:.2f} MiB")
    return 0 if cpu < 2 and peak < 100 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int)
    arguments = parser.parse_args()
    try:
        sys.exit(measure(arguments.pid) if arguments.pid else detect())
    except (OSError, RuntimeError, ImportError, ValueError) as error:
        print(f"FAIL · {error}", file=sys.stderr)
        sys.exit(1)
