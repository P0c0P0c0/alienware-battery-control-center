# Independent audit handoff

**v1.0.0 locally qualified — not published**

The independent F001-R2 audit was reported as **CONDITIONAL ACCEPT**. The user subsequently reported passing its live condition on Ubuntu 26.04.1, KVM and GNOME 50 Wayland. The audit and guest summaries were supplied to this release pass. Preserved local test outputs and newly verified release hashes are separate evidence.

| Audit item | Evidence |
| --- | --- |
| Accepted runtime identity | Compare runtime and units with `8f2d3b1fb87407ae35614670992517c2ffca4855`. Final changes are documentation and the source manifest. |
| F001 and R2 | [Root cause and fix](F001.md). [Targeted 6/6](evidence/F001_R2_TARGETED_TESTS.txt) and [offline 41/41](evidence/F001_R2_OFFLINE_TESTS.txt) from the accepted baseline. |
| Live evidence and coverage | [Qualification summary](evidence/GH05_QUALIFICATION.md) and [VM runbook](VM_QUALIFICATION_MANIFEST.md). The successful `dpkg` workaround is described in [media preparation](VM_MEDIA_PREPARATION.md). |
| Ownership, privacy and reporting | [MIT](LICENSE), [dependency licenses](DEPENDENCIES.md), [security](SECURITY.md) and [conduct](CODE_OF_CONDUCT.md). |
| Artifact verification | Run `sha256sum -c SOURCE.SHA256`, `(cd dist && sha256sum -c SHA256SUMS)` and `/usr/bin/python3 -B tools/check-artifacts.py dist`. The source archive and both packages were rebuilt independently from the extracted archive. |

Remaining scope includes manual interrupted-swap recovery, optional notifications, hosted CI and activation of GitHub Private Vulnerability Reporting. No new deployment or regression run was performed during this consolidation.
