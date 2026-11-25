# Architecture

The BAT-05 system timer runs a Python sampler about every five minutes. The oneshot service runs with root ownership, the reader group, an empty capability bounding set, restricted address families, an isolated network, private devices and a read-only system tree except for its state directory. The service reads battery and Dell firmware attributes and records a transactional SQLite sample, retained alert events and active alerts. The data directory is mode 0750 and the service uses umask 0027. The read-only CLI uses a SQLite URI with `mode=ro`.

The dashboard is a separate unprivileged GTK 3 application with a two-second sysfs refresh. It checks for database changes at its existing backend interval, reuses the R6 read-only snapshot and processes only the selected history range. Cairo draws the controls, chart and gauges into raw RGB/RGBA pixbufs. R7.2 caches chart layers and uses one fixed-height footer row update. The window service retains its original systemd hardening. Wayland placement is delegated to the GNOME 50 Shell extension. X11 uses the window manager's above-window hint.

The launcher talks to the existing user process or asks the user service manager to start it. Optional notifications read the same database as the desktop user and keep an atomic cursor under that user's private runtime directory. BAT-05 and the dashboard require no network service.

Install manifests are generated locally. Their paths and hashes allow installers to refuse foreign, modified and out-of-scope files. System and desktop upgrade actions use locked same-filesystem directory swaps. Database history and optional desktop notification state are outside program replacement.
