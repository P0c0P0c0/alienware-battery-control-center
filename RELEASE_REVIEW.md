# v1.0.0 release review

**READY FOR GPT RELEASE REVIEW — NOT PUBLISHED**

This is a locally built review candidate. Keep it local until the release owner confirms the copyright and reporting contact and approves a clean-host test and publication.

| Gate | Status | Evidence and exceptions |
| --- | --- | --- |
| GH-01 Source consolidation | PASS | BAT-05 and installed BAT-07R7.2 managed file hashes matched their installed manifests. The original source checksums verified. The dashboard rendering, Cairo controls, R7.2 chart caches, two-second cadence and Shell integration retain their accepted source. Systemd unit hardening is byte-identical to the input. See [provenance](PROVENANCE.md) and [baseline evidence](evidence/BASELINE.txt). |
| GH-02 Security, privacy and licensing | BLOCKED | MIT text is drafted. The copyright holder and authority to license the supplied code must be confirmed. A public security and conduct reporting contact also needs confirmation. No bundled third-party source or dependency binary was identified. See [dependency licensing](DEPENDENCIES.md) and the review below. |
| GH-03 Packaging | PASS | Deterministic source archive and separately installable, architecture-independent Debian payloads build offline using the installed Python and dpkg-deb. The packages contain no lifecycle scripts and activate no services. Live package activation awaits a clean host. |
| GH-04 Documentation | PASS | English documentation, privacy guidance, GitHub templates and offline regression command are included. Screenshot pending. The GitHub workflow has not run remotely. |
| GH-05 Qualification | BLOCKED | Offline regression and artifact verification passed. Live clean-host package activation, systemd wiring, GNOME behavior and a sanitized screenshot remain unverified. The active installation was not touched. |

## Security and privacy review

- **Privilege and execution.** Backend activation is administrator-only and requires explicit consent, a trusted administrator-owned source path, and isolated Python as documented. Administrative subprocesses use fixed executable paths, argument arrays and a limited environment. The dashboard installer refuses root and activates only a user service. Optional notification delivery is unprivileged and uses fixed program paths and escaped message bodies.
- **Files and state.** Managed writes use exclusive creation, symlink checks and mode enforcement. Manifest verification checks scope, hashes, ownership and hard links. Fixed system paths and trusted ancestors protect administrative operations. SQLite state uses an administrator-owned 0750 directory and service umask 0027. A retained or malformed state layout fails validation. Backend uninstall retains history and the reader group. Dashboard and reporting open SQLite read-only. The reader group can read all local history and should contain only explicitly trusted users.
- **Upgrade and recovery.** Explicit operations lock per component and use same-filesystem swaps with validated predecessor manifests, startup checks and rollback. Desktop startup preserves the ten-second active/zero-restart gate. Legacy installs and unit/launcher schema changes are excluded from in-place upgrade. A process kill between renames can require the documented `recover` action. Live privileged recovery has not been exercised.
- **Firmware and system policy.** All firmware paths in release code are reads. The preflight flags mismatched or missing values without changing them. The backend units retain private network/devices, read-only system paths and their state directory scope. The current desktop and backend units retain all original sandbox controls.
- **Privacy.** Reviewed text and artifact inventories for secrets, token patterns, SSH material, identity-bearing paths and private data. The old device-specific BAT-05 reference was removed from the status report. Unit names, application IDs and system paths are product-wide identifiers. The source archive and Debian payloads contain no personal database, recovery archive, machine manifest, private log or device serial. Tests use synthetic inputs.
- **Licensing.** The supplied source does not state an existing project license or author identity. Dependency licensing was inventoried from installed package notices. No contributor identity or external attribution was fabricated. Confirm title, permission and any required attribution before public publication.

## Test and compatibility evidence

[evidence/OFFLINE_TESTS.txt](evidence/OFFLINE_TESTS.txt) records offline tests using synthetic sysfs and SQLite, isolated temporary program paths and simulated service management. Coverage includes missing dependencies, unsupported hardware and desktop, inaccessible database, symlink/collision refusal, failure recovery, retained data on uninstall, upgrades and rollback, strict CPU/RSS limits and process invocation/restart checks. Artifact checks validate bytes, paths, ownership and modes, and two builds are compared bit for bit. Package activation and a GitHub-hosted run were outside the available environment.

Accepted process evidence supplied for BAT-07R7.2 on Alienware m15 R7, Ubuntu 26.04.1 and GNOME 50 Wayland was 0.899% of one logical core and 67.66 MiB peak sampled RSS over 60.1 seconds visibly idle. PID and invocation identity remained stable, restarts were zero and telemetry refreshed every two seconds. This evidence does not measure the complete desktop or compositor and does not establish performance on other hardware. The consolidated candidate was not benchmarked live.

The release repository has no configured remotes. No installer was run on the active host. No package was installed and no publication occurred.
