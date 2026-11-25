# Independent audit handoff

**READY FOR INDEPENDENT AUDIT — NOT PUBLISHED**

Review delta from `5f07ff3`. Runtime source, unit files, UI and benchmark evidence should match that baseline. The delta is limited to approved release metadata, documentation, qualification evidence and checksums.

| Audit item | Evidence |
| --- | --- |
| Ownership and terms | [MIT notice](LICENSE), [Debian metadata](tools/build.py), [dependency license review](DEPENDENCIES.md). Owner-approved maintainer email is intentional release metadata. |
| Reporting | [Security](SECURITY.md) and [conduct](CODE_OF_CONDUCT.md). Private vulnerability reporting is approved and awaits activation. Conduct intake has no approved contact. |
| Reproduction and contents | Run `sha256sum -c SOURCE.SHA256` from the release tree, `(cd dist && sha256sum -c SHA256SUMS)`, and `/usr/bin/python3 -B tools/check-artifacts.py dist`. Rebuild from the extracted source and compare artifact bytes. See [artifact evidence](evidence/ARTIFACTS.txt). |
| Regression | See the [single offline run](evidence/OFFLINE_TESTS.txt). Runtime and systemd hardening were kept byte-identical to the baseline. |
| Outstanding live evidence | [Clean-host plan](CLEAN_HOST_TEST_PLAN.md) and [release review](RELEASE_REVIEW.md). No genuine screenshot was available. The accepted R7.2 benchmark is prior evidence for the unchanged dashboard process. |
