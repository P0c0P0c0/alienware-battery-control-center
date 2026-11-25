# v1.0.0 final release review

**Locally qualified — not published.** Accepted runtime baseline `8f2d3b1fb87407ae35614670992517c2ffca4855`. Runtime code and systemd units are byte-identical to that baseline.

| Gate | Result |
| --- | --- |
| GH-01 Source | PASS. Source provenance, accepted runtime and unit hardening preserved. |
| GH-02 Security, privacy and licensing | PASS for local preparation. Owner-approved MIT copyright, Debian maintainer metadata and private conduct intake are unchanged. GitHub Private Vulnerability Reporting remains pending activation. |
| GH-03 Packaging | PASS. Source archive and scriptless backend and dashboard DEBs built offline and reproduced byte-for-byte. In the user-reported guest run, a local-package APT error was worked around successfully with `dpkg`. |
| GH-04 Documentation | PASS. Genuine dashboard screenshot and sanitization retained. Hosted CI has not run. |
| GH-05 Qualification | PASS for the tested scope. The independent F001-R2 audit was **CONDITIONAL ACCEPT**. The reported clean VM run satisfied the live condition. Local tests remain 6/6 targeted and 41/41 offline. |

## Qualification and evidence boundary

The user reported Ubuntu 26.04.1, KVM, GNOME 50 Wayland and offline QXL/SPICE, ten-second stable autostart with zero restarts, and **0.483% CPU** of one logical core and **70.69 MiB peak sampled RSS** over **60.1 seconds** visibly idle. All six UI/UX checks passed. Backend and dashboard upgrade, exact rollback, injected startup failure, automatic recovery and uninstall passed. SQLite integrity, historical retention and synthetic fixture cleanup passed. [Qualification evidence](evidence/GH05_QUALIFICATION.md)

F001 initially retried native GTK readiness but still hit the cached PyGObject constructor guard. R2 separated native readiness from that guard and turned activation exceptions into process failure. The initial failing process environment remains unverified. [F001 and R2 investigation](F001.md)

## Security, privacy and remaining scope

The isolated backend writes only its managed SQLite state. Its firmware access is read-only. The unprivileged dashboard reads SQLite, and audited systemd hardening is unchanged. Installers retain explicit consent and verify scoped manifests. The documented Antigravity LOW finding remains. A failed initial backend install may retain an empty state directory and system reader group. No runtime patch was applied for that finding.

The accepted VM used synthetic hardware. One short widget-process benchmark does not establish long-run performance, whole-desktop overhead, or physical Dell firmware compatibility. Manual interrupted-swap recovery and optional notifications remain untested. Hosted CI, creation of the public repository, activation of GitHub Private Vulnerability Reporting and authorization to publish remain pending.

Release artifact contents, SHA256, privacy checks and reproducibility were independently checked in this workspace. The raw independent audit and guest logs were not supplied, so live outcomes are recorded as user-reported. This pass ran no installer, regression suite or VM. The [audit handoff](AUDIT.md) indexes the evidence.
