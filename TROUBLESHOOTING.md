# Troubleshooting

- **BAT-05 access denied.** Check reader-group membership and sign in again after an administrator changes it. Keep the database and directory permissions intact.
- **Missing telemetry or stale history.** Confirm `BAT0` exists and inspect `systemctl status alienware-battery-monitor.timer` and the relevant system journal locally. The UI can still present live sysfs values if history is unavailable.
- **Always-on-top absent on Wayland.** Check `gnome-extensions info bat07-widget@alienware.local` and whether GNOME Shell 50 is running. A fresh GNOME login can be needed to discover the extension.
- **Dashboard startup fails.** Inspect the user service with `systemctl --user status bat07-widget.service`. Upgrade failures are checked by a ten-second stability gate. If recovery reports a manifest conflict, retain the files and review the hashes before trying again.
- **Firmware warning.** Compare the reported attributes with the intended firmware configuration. The project takes no corrective firmware action.
- **Slow or high-memory widget.** Keep it visible and idle and run `dashboard/deploy.py verify` with the system Python. Note measured duration, CPU/RSS, hardware and desktop version. Inspect and redact any service output before sharing it.
