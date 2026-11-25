# Alienware Battery Control Center

An unofficial Linux battery monitoring backend and desktop dashboard for compatible Alienware laptops. This independent project has no affiliation with or endorsement from Dell or Alienware. Device and brand names identify compatibility.

## Features

- A systemd sampler records battery measurements and alerts to local SQLite. The dashboard reads live sysfs values every two seconds and queries SQLite read-only.
- The GTK 3 dashboard shows SOH, charge, electrical readings, firmware-reported charging limits and real history samples with 24-hour, 7-day and 30-day views.
- The GNOME Shell extension places the Wayland dashboard at the upper right and keeps it above other windows. Drag the header to move it. Settings include opacity.
- Charge protection is observational. Firmware attributes are read only.

**Screenshot blocked.** No genuine dashboard capture was available in the release evidence.

## Verified performance

On an Alienware m15 R7 running Ubuntu 26.04.1, GNOME 50 and Wayland, the accepted BAT-07R7.2 widget used **0.899% of one logical core** and **67.66 MiB peak sampled RSS** over **60.1 seconds** visibly idle. The PID and service invocation stayed stable, automatic restarts were zero, and sysfs telemetry refreshed every two seconds. This evidence covers the tested widget process. Total compositor overhead and performance on other hardware were outside the measurement.

## Operations and privacy

See [installation and removal](INSTALLATION.md), [compatibility](COMPATIBILITY.md), [architecture](ARCHITECTURE.md), and [troubleshooting](TROUBLESHOOTING.md). The project writes battery history and alert transitions locally, with a 365-day retention window applied during sampling. There is no upload, analytics, telemetry endpoint or account integration. User-readable database access is controlled by a dedicated local group. History and group membership survive uninstall. The journal and optional desktop notification daemon apply their own retention settings. See [security](SECURITY.md) for sharing and reporting guidance.

The project uses the [MIT License](LICENSE). [Release review](RELEASE_REVIEW.md) records the blockers for publication.
