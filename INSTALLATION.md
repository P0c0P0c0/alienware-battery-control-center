# Installation and removal

Use a supported system and read [compatibility](COMPATIBILITY.md) first. Verify the downloaded file hashes against a trusted release manifest. This local v1.0.0 candidate awaits license confirmation and a clean-host smoke test before publication.

## Source or Debian payload

The source archive contains both components. For privileged operations, use the verified Debian backend payload or place the verified source in an administrator-owned directory with no group/world-writable or symlink ancestors. Invoke privileged Python in isolated mode (`-I`). Run commands from the appropriate admin or user terminal.

The two architecture-independent Debian packages carry source and documentation only. Installing a package through the normal system package manager does not install systemd units, change reader groups or start software. The command paths below refer to package payloads. When using source, substitute the corresponding `backend/deploy.py` or `dashboard/deploy.py` path.

### Backend

An administrator runs the read-only preflight, then separately consents to activating monitoring.

```sh
/usr/bin/python3 -IB /usr/share/alienware-battery-control-center-backend/backend/deploy.py preflight
/usr/bin/python3 -IB /usr/share/alienware-battery-control-center-backend/backend/deploy.py install --confirm
```

The installer refuses occupied program and unit paths. Retained state is accepted only with its original reader group, correct ownership and safe entries. Sampling stores health history and alerts but never changes firmware. An administrator can explicitly grant access to a trusted local desktop account using `gpasswd -a ACCOUNT alienware-battery-monitor` with the actual local account substituted. A fresh login is required. Membership grants access to all collected history.

Optional desktop notifications require the backend and a working `notify-send`. The desktop user explicitly opts in with `systemctl --user enable --now alienware-battery-notify.timer`.

### Dashboard

From the target user's GNOME or supported X11 desktop terminal:

```sh
/usr/bin/python3 -B /usr/share/alienware-battery-control-center-dashboard/dashboard/deploy.py preflight
/usr/bin/python3 -B /usr/share/alienware-battery-control-center-dashboard/dashboard/deploy.py install --confirm
```

On GNOME 50 Wayland, sign out and back in if Shell has not discovered the installed extension yet. Open **BAT-07 Alienware Battery** from the launcher. Run the same dashboard command with `verify` for the idle 60-second measurement and the BAT-05, extension and process checks.

## Upgrades, rollback and recovery

Use `upgrade --confirm` with the newly verified payload for the corresponding component. The installer requires a manifest from this release tooling and byte-identical managed units and integration files. One verified previous program is kept as a sibling ending in `.previous`. `rollback --confirm` restores it. If an interruption left the main program directory absent, `recover --confirm` restores the previous directory when that directory validates. An unresolved predecessor blocks a further upgrade and uninstall. Use the verified rollback, or explicitly discard the verified previous program with `finalize --confirm` once the new one is accepted. History is outside these swaps.

Legacy BAT-05/BAT-07 installs are treated as conflicts. There is no automatic legacy migration. Preserve the legacy SQLite state and reader group, resolve legacy program and unit paths through a separately reviewed, data-preserving procedure, and use preflight before activation. The legacy BAT-05 rollback can erase its database.

## Uninstall

Run the component's `uninstall --confirm` action before removing its Debian payload or source directory. Desktop removal disables its user unit and removes only its verified launcher, extension and program files. Disable optional notifications in every user session with `systemctl --user disable --now alienware-battery-notify.timer` before uninstalling the backend. Backend uninstall stops its units and removes its managed program and unit files. It retains `/var/lib/alienware-battery-monitor`, the reader group and its existing memberships. Administrators control any separate history deletion or membership removal.
