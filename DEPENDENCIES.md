# Dependencies and licensing

| Component | Required runtime components |
| --- | --- |
| Backend | Linux, Python 3.10+ with SQLite, systemd system manager, and the Debian `passwd` package's `groupadd`. DMI and battery sysfs are required for install preflight. |
| Dashboard | Linux, Python 3.10+, Python GObject introspection bindings, GTK 3/GDK/GdkPixbuf typelibs, PyCairo and a systemd user graphical session. GNOME Shell 50 and user extensions are required on Wayland. |
| Notifications | Optional `notify-send` (`libnotify-bin`), desktop session bus and a notification daemon. |
| Build and tests | Python 3.10+, system `dpkg-deb` and its xz compressor for Debian artifacts, a shell, and the dashboard runtime bindings for full tests. Core tests work without GTK. |

Direct packaging dependencies are declared in the generated Debian control files. No wheels, system libraries, GNOME code, fonts or icons are bundled. Chart marks and controls are drawn by the project's Cairo code. The launcher requests the standard `battery` theme icon at runtime.

The local licensing review used installed Debian copyright notices. PyGObject uses LGPL terms and includes Expat-licensed files. GTK and GdkPixbuf include LGPL and other component-specific notices. PyCairo is distributed under LGPL 2.1 or MPL 1.1 terms, and Cairo includes dual-licensed and other individually licensed files. The GNOME Shell and systemd packages contain GPL/LGPL and other separately licensed components. libnotify's library uses LGPL 2.1 or later. Python's standard library and SQLite come from system packages under their own terms. Consult the installed package copyright files for exact terms and attribution. The local build redistributes no dependency binaries or sources.

The project scripts, CSS, unit files and Shell extension came from the supplied BAT-05 and BAT-07 source trees. Andika Conoras confirmed the project copyright and authority to distribute under MIT, subject to applicable third-party licensing. The supplied trees contained no separate third-party attribution. The project license does not grant trademark rights.
