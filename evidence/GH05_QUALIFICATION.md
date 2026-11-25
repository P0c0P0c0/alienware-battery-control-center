# GH-05 v1.0.0 qualification evidence

Accepted runtime baseline: `8f2d3b1fb87407ae35614670992517c2ffca4855`.

## Independent and local evidence

The independent F001-R2 audit verdict was **CONDITIONAL ACCEPT**, as supplied for this consolidation. The raw audit report was not supplied in the release tree. Its outstanding live condition was subsequently satisfied by the user-reported VM run below.

The preserved [targeted run](F001_R2_TARGETED_TESTS.txt) records 6/6 passing tests. The preserved [offline regression run](F001_R2_OFFLINE_TESTS.txt) records 41/41. These tests were not rerun for the documentation-only release delta. Runtime identity, package contents, checksums and reproducibility are independently checked during final packaging.

## User-reported live VM evidence

Environment: Ubuntu Desktop 26.04.1 amd64, KVM, GNOME 50 Wayland, offline QXL/SPICE guest. Battery and Dell-facing sysfs inputs were synthetic. The report is a summary of supplied outcomes. It does not reproduce guest commands, raw logs, the exact APT diagnostic or UI checklist item names.

| Check | Reported result |
| --- | --- |
| F001-R2 live autostart | PASS, stable for 10 seconds, zero automatic restarts. |
| Visible-idle widget process | PASS, 60.1 s, 0.483% of one logical core, peak sampled RSS 70.69 MiB. |
| UI/UX | PASS, 6/6 checks confirmed by the user. |
| Clean-guest package staging | PASS via local `dpkg` workaround after an APT local-package error. |
| Backend and dashboard | PASS for normal upgrade, exact rollback, injected startup failure, automatic recovery and uninstall. |
| Data integrity and cleanup | PASS for SQLite integrity, historical data retention and synthetic fixture cleanup. |

The VM benchmark is one short, visible-idle widget process measurement. It does not establish compositor cost, long-run behavior, or results across hardware. This VM used synthetic telemetry and did not qualify physical Dell firmware compatibility. The separately reported m15 R7 result remains physical-widget evidence only.

## Remaining scope

Manual recovery after an interrupted directory swap was not tested. Optional desktop notifications are unverified. Hosted CI and activation of GitHub Private Vulnerability Reporting remain pending. Publication requires separate authorization.
