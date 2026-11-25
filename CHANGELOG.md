# Changelog

## 1.0.0 — qualified local release
- F001 adds a bounded Wayland display-readiness check before dashboard startup.
- F001-R2 separates explicit GTK readiness from import-time PyGObject state and makes activation exceptions fail the process.

- Reported clean-VM acceptance closed the independent audit’s live condition. Autostart, performance, UI and recovery checks passed.
- Consolidated BAT-05 and the accepted BAT-07R7.2 dashboard.
- Retained the two-second live display, read-only SQLite cache, Cairo controls, separately cached chart rasters, fixed-height footer and GNOME 50 integration.
- Added explicit split deployment, collision checks, manifest verification and verified program swaps. Backend uninstall retains database history by default.
- Removed the machine-specific BAT-05 reference capacity and status baseline from distribution.
- Added reproducible source and Debian payload builds, offline regression coverage and security documentation.
