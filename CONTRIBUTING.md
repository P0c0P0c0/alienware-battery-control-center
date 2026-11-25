# Contributing

Run `./tools/test-offline.sh` from a checkout with the listed system dependencies. Use `--core-only` where GTK is unavailable. New tests should use temporary directories, synthetic SQLite and synthetic sysfs. Keep firmware, platform settings and running installations outside test actions.

Describe what changed and why, report checks actually run, and indicate which behaviors still require a live GNOME session. Keep dependency changes explicit. For UI changes, include sanitized before/after images when available. For packaging changes, verify clean builds and inspect the resulting package before requesting review. See the [code of conduct](CODE_OF_CONDUCT.md) and [security instructions](SECURITY.md).


Build the source archive and Debian payloads from a verified release tree with
`/usr/bin/python3 -B tools/build.py`. Inspect the outputs using
`/usr/bin/python3 -B tools/check-artifacts.py dist`. The build reads the source
file manifest and writes artifact hashes to `dist/SHA256SUMS`.
