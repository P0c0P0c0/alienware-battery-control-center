# Isolated VM qualification manifest

## Executed qualification

The later user-reported run used Ubuntu Desktop 26.04.1, KVM, GNOME 50 Wayland and an offline QXL/SPICE guest with synthetic battery inputs. The independent F001-R2 audit's live condition was satisfied. Autostart held for ten seconds with zero restarts, and the widget measured 0.483% CPU and 70.69 MiB peak sampled RSS over 60.1 seconds. UI/UX passed 6/6. Both components passed upgrade, exact rollback, injected startup failure, automatic recovery and uninstall. SQLite integrity, retained history and fixture cleanup passed. [GH-05 qualification evidence](evidence/GH05_QUALIFICATION.md)

APT rejected a local-package attempt. The operator staged the release packages successfully with local `dpkg` and activated the components separately. See [the offline workaround](VM_MEDIA_PREPARATION.md#executed-guest-workflow). The exact QEMU command line, APT error and guest logs were not supplied. The host-side commands below are a repeat-run recipe using a GTK viewer, not a reconstruction of the QXL/SPICE launch. Capture future launch and dependency details with the test record. Manual interrupted-swap recovery and optional notifications were outside the reported run.

## Repeat-run scope

Obtain approval for base creation, guest activation, fault injection and cleanup. Use clean Ubuntu Desktop 26.04.1 amd64 with GNOME 50 Wayland, 4 vCPUs, 6 GiB guest RAM, at least 9 GiB host available RAM and 90 GiB free storage. Use no NIC, device passthrough or host-directory sharing. The test account is `abcc-test`. Run each Bash block in a fresh shell for its stated role. See [media preparation](VM_MEDIA_PREPARATION.md).

## A. Create and freeze the baseline after approval

Host desktop user. A verified ISO and usable QEMU GTK session are required. Confirm administrator access can be arranged in the disposable guest without any host privilege. Use KVM for the benchmark. For separately approved functional-only TCG use, omit the KVM check and replace `-accel kvm -cpu host` in both commands with `-accel tcg,thread=multi -cpu max`.

```bash
must() { "$@" || exit 1; }
test "${ABCC_APPROVE_BASE_VM:-}" = YES && test "$(id -u)" -ne 0 || exit 1
test "$(nproc)" -ge 4 && test -r /dev/kvm && test -w /dev/kvm || exit 1
awk '/^MemAvailable:/ {ok=($2>=9437184)} END {exit !ok}' /proc/meminfo || exit 1
df -PB1 "$HOME" | awk 'NR==2 {ok=($4>=96636764160)} END {exit !ok}' || exit 1
qemu-system-x86_64 -display help | grep -Eq '^[[:space:]]*gtk$' || exit 1
must /usr/bin/python3 -B -c 'import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk; raise SystemExit(0 if Gtk.init_check()[0] else 1)'
media="$HOME/abcc-vm-media"
vm="$HOME/abcc-vm-qualification"
iso="$media/iso/ubuntu-26.04.1-desktop-amd64.iso"
: "${CD_IMAGE_KEYRING:?Specify the trusted Ubuntu CD-image keyring used for media preparation}"
: "${CD_IMAGE_SIGNER:?Specify its full independently confirmed signer fingerprint}"
test -r "$CD_IMAGE_KEYRING" || exit 1
signature=$(gpgv --homedir "$media/gnupg" --keyring "$CD_IMAGE_KEYRING" --status-fd 1 \
  "$media/iso/SHA256SUMS.ubuntu.gpg" "$media/iso/SHA256SUMS.ubuntu") || exit 1
printf '%s\n' "$signature" | awk -v f="$CD_IMAGE_SIGNER"   '$2=="VALIDSIG" && ($3==f || $NF==f) {ok=1} END {exit !ok}' || exit 1
expected=601e30fbf5d97759367c632e2c33630665039b7e2158fd068403da3ccf1bda1f
grep -Fx "$expected *ubuntu-26.04.1-desktop-amd64.iso" "$media/iso/SHA256SUMS.ubuntu" >/dev/null || exit 1
printf '%s  %s\n' "$expected" "$iso" | sha256sum --strict -c - || exit 1
test ! -e "$vm" && test ! -L "$vm" || exit 1
must mkdir -m 700 "$vm"
must qemu-img create -f qcow2 "$vm/base.qcow2" 40G
must qemu-system-x86_64 -name ABCC-Setup -machine q35 -accel kvm -cpu host \
  -smp 4 -m 6144 -nic none -display gtk,gl=off \
  -serial none -serial "file:$vm/guest-status.serial" \
  -drive "file=$vm/base.qcow2,if=virtio,format=qcow2" \
  -drive "file=$iso,media=cdrom,readonly=on" -boot once=d
```

Install Ubuntu offline, create the test user, and confirm GNOME 50 Wayland. Before adding packages, export the actual installed baseline from the guest administrator shell via the second virtual serial port.

```bash
case "$(systemd-detect-virt)" in kvm|qemu) ;; *) exit 1 ;; esac
test "${ABCC_APPROVE_BASELINE_EXPORT:-}" = YES && test "$(id -u)" -eq 0 && test -c /dev/ttyS1 || exit 1
{ printf 'ABCC-DPKG-BEGIN\n' && base64 -w0 /var/lib/dpkg/status && printf '\nABCC-DPKG-END\n'; } > /dev/ttyS1 || exit 1
systemctl poweroff || exit 1
```

After QEMU exits, extract and freeze the baseline, then run the dependency procedure in [media preparation](VM_MEDIA_PREPARATION.md) with the resulting `GUEST_DPKG_STATUS`.

```bash
vm="$HOME/abcc-vm-qualification"
media="$HOME/abcc-vm-media"
test -f "$vm/base.qcow2" && test -s "$vm/guest-status.serial" || exit 1
/usr/bin/python3 -B - "$vm/guest-status.serial" "$media/guest-dpkg-status" <<'PY' || exit 1
import base64, pathlib, re, sys
serial, output = map(pathlib.Path, sys.argv[1:])
matches = re.findall(rb"^ABCC-DPKG-BEGIN\n([A-Za-z0-9+/=]+)\nABCC-DPKG-END$",
                     serial.read_bytes().replace(b"\r\n", b"\n"), re.M)
if len(matches) != 1:
    raise SystemExit("Missing or ambiguous status")
data = base64.b64decode(matches[0], validate=True)
if b"Status: install ok installed" not in data or b"Package: gnome-shell\n" not in data:
    raise SystemExit("Incomplete baseline")
with output.open("xb") as handle:
    handle.write(data)
PY
chmod a-w "$vm/base.qcow2" || exit 1
```

## B. Boot an offline test overlay after approval

The authorized host user runs these commands after dependency resolution. Only allowlisted files from the checked manifest enter the read-only media.

```bash
must() { "$@" || exit 1; }
test "${ABCC_APPROVE_TEST_VM:-}" = YES && test "$(id -u)" -ne 0 || exit 1
test -r /dev/kvm && test -w /dev/kvm || exit 1
must /usr/bin/python3 -B -c 'import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk; raise SystemExit(0 if Gtk.init_check()[0] else 1)'
vm="$HOME/abcc-vm-qualification"
media="$HOME/abcc-vm-media"
release="$HOME/Projects/alienware-battery-control-center/dist"
bundle="$media/dependencies"
: "${OFFLINE_MANIFEST_SHA256:?Use the verified local dependency manifest digest}"
(cd "$bundle" &&
  printf '%s  %s\n' "$OFFLINE_MANIFEST_SHA256" SHA256SUMS | sha256sum --strict -c - &&
  sha256sum --strict -c SHA256SUMS) || exit 1
expected=$(awk '$2=="status" {print $1}' "$bundle/BASELINE.SHA256") || exit 1
printf '%s  %s\n' "$expected" "$media/guest-dpkg-status" | sha256sum --strict -c - || exit 1
(cd "$release" && sha256sum --strict -c SHA256SUMS) || exit 1
test -f "$vm/base.qcow2" && test ! -w "$vm/base.qcow2" || exit 1
for path in "$vm/media" "$vm/fixtures.iso" "$vm/qualification.qcow2"; do
  test ! -e "$path" && test ! -L "$path" || exit 1
done
must mkdir -p "$vm/media/release" "$vm/media/dependencies"
must cp -- "$release"/*.deb "$release/SHA256SUMS" "$release"/*.tar.gz "$vm/media/release/"
must cp -- "$bundle/SHA256SUMS" "$vm/media/dependencies/"
while read -r digest name; do
  name="${name#\*}"
  name="${name#./}"
  [[ "$digest" =~ ^[[:xdigit:]]{64}$ && "$name" =~ ^([a-zA-Z0-9][a-zA-Z0-9._+~%:-]*[.]deb|CLOSURE[.]txt|BASELINE[.]SHA256)$ ]] || exit 1
  test -f "$bundle/$name" && test ! -L "$bundle/$name" || exit 1
  must cp -- "$bundle/$name" "$vm/media/dependencies/"
done < "$bundle/SHA256SUMS"
must xorriso -as mkisofs -R -V ABCC_FIXTURES -o "$vm/fixtures.iso" "$vm/media"
must qemu-img create -f qcow2 -F qcow2 -b "$vm/base.qcow2" "$vm/qualification.qcow2"
must qemu-system-x86_64 -name ABCC-Qualification -machine q35 -accel kvm -cpu host \
  -smp 4 -m 6144 -nic none -display gtk,gl=off \
  -drive "file=$vm/qualification.qcow2,if=virtio,format=qcow2" \
  -drive "file=$vm/fixtures.iso,media=cdrom,readonly=on"
```

## C. Simulated hardware and unchanged hardening

Authorized **guest administrator** only. Test closure against the exact fresh guest status and the supplied files. No package fetch or removal is permitted during this test. The APT commands below describe the intended path. If APT specifically rejects local package handling, use the verified dpkg fallback documented in the media guide. Dependency failures still stop qualification. Before activation, confirm the project service is absent and check that backend preflight fails specifically for unsupported hardware without the fixture.

```bash
must() { "$@" || exit 1; }
case "$(systemd-detect-virt)" in kvm|qemu) ;; *) exit 1 ;; esac
test "${ABCC_APPROVE_GUEST_ACTIVATION:-}" = YES && test "$(id -u)" -eq 0 || exit 1
must id abcc-test
m=/mnt/abcc-fixtures
must install -d -m 0755 "$m"
must mount -o ro,nosuid,nodev,noexec LABEL=ABCC_FIXTURES "$m"
(cd "$m/release" && sha256sum --strict -c SHA256SUMS) || exit 1
(cd "$m/dependencies" && sha256sum --strict -c SHA256SUMS) || exit 1
expected=$(awk '$2=="status" {print $1}' "$m/dependencies/BASELINE.SHA256") || exit 1
printf '%s  %s\n' "$expected" /var/lib/dpkg/status | sha256sum --strict -c - || exit 1
debs=("$m"/release/*-backend_1.0.0_all.deb "$m"/release/*-dashboard_1.0.0_all.deb)
for package in "$m"/dependencies/*.deb; do
  if test -f "$package"; then debs+=("$package"); fi
done
must apt-get -s --no-download --no-remove --no-install-recommends install "${debs[@]}"
must apt-get --no-download --no-remove --no-install-recommends install "${debs[@]}"
backend=/usr/share/alienware-battery-control-center-backend/backend/deploy.py
test "$(systemctl show -p LoadState --value alienware-battery-monitor.timer)" = not-found || exit 1
if result=$(/usr/bin/python3 -IB "$backend" preflight 2>&1); then exit 1; fi
printf '%s\n' "$result" | grep -F 'Unsupported hardware:' || exit 1

f=/run/abcc-synthetic
test ! -e "$f" && test ! -L "$f" || exit 1
must install -d -m 0755 "$f/dmi" "$f/power/BAT0" "$f/power/AC"
printf '%s\n' 'Dell Inc.' > "$f/dmi/sys_vendor" || exit 1
printf '%s\n' 'Alienware Synthetic VM' > "$f/dmi/product_name" || exit 1
for kv in charge_full=6400000 charge_full_design=8000000 charge_now=4000000 \
  capacity=62 temp=335 voltage_now=11800000 current_now=1000 voltage_min_design=11400000 \
  status=Charging health=Good; do
  printf '%s\n' "${kv#*=}" > "$f/power/BAT0/${kv%%=*}" || exit 1
done
printf '1\n' > "$f/power/AC/online" || exit 1
(cd "$f" && find dmi power -type f -print0 > file-list &&
 sort -z -o file-list file-list && xargs -0 -r sha256sum < file-list > SHA256SUMS &&
 test -s SHA256SUMS && sha256sum --strict -c SHA256SUMS) || exit 1
dmi=$(readlink -f /sys/class/dmi/id) || exit 1
test -d "$dmi" && test -d /sys/class/power_supply || exit 1
must mount --bind "$f/dmi" "$dmi"
must mount -o remount,bind,ro "$dmi"
must mount --bind "$f/power" /sys/class/power_supply
must mount -o remount,bind,ro /sys/class/power_supply
must /usr/bin/python3 -IB "$backend" preflight
must /usr/bin/python3 -IB "$backend" install --confirm
must gpasswd -a abcc-test alienware-battery-monitor
must systemctl is-active alienware-battery-monitor.timer
for unit in alienware-battery-monitor.service alienware-battery-monitor-failure.service alienware-battery-monitor.timer; do
  must cmp "/etc/systemd/system/$unit" "/usr/share/alienware-battery-control-center-backend/backend/$unit"
  dropins=$(systemctl show "$unit" -p DropInPaths --value) || exit 1
  test -z "$dropins" || exit 1
done
must systemctl start alienware-battery-monitor.service
must stat -c '%a %U %G %n' /var/lib/alienware-battery-monitor{,/monitor.sqlite3}
must /usr/bin/python3 -IB /opt/alienware-battery-monitor/monitor.py status > /run/abcc-sampled-status.json || exit 1
/usr/bin/python3 -B - /run/abcc-sampled-status.json <<'PY' || exit 1
import json, sys
from datetime import datetime, timezone
with open(sys.argv[1]) as f:
    sample = json.load(f)["latest"]
assert (sample["soh_pct"], sample["capacity"], sample["temp_c"], sample["ac_online"]) == (80, 62, 33.5, 1)
age = (datetime.now(timezone.utc) - datetime.fromisoformat(sample["timestamp"])).total_seconds()
assert 0 <= age < 120
PY
```

Compatibility is demonstrated only if the **real unchanged hardened unit** persists the expected fresh fixture values. The read-only bind is consistent with the source's sysfs reads; runtime visibility has not been verified. On a mismatch stop and capture logs, with no unit override or hardening change. Verify the state directory and DB are 0750 and 0640, respectively. Firmware attributes remain unavailable by design. Wait for additional real sampling intervals for multiple chart points.

Sign back into GNOME Wayland as `abcc-test`. Verify read-only SQLite access and widget activation. The installer enforces the ten-second stable PID and zero-restart gate.

```bash
must() { "$@" || exit 1; }
case "$(systemd-detect-virt)" in kvm|qemu) ;; *) exit 1 ;; esac
test "${ABCC_APPROVE_GUEST_ACTIVATION:-}" = YES && test "$(id -un)" = abcc-test || exit 1
test "${XDG_SESSION_TYPE:-}" = wayland || exit 1
gnome-shell --version | grep -E '(^|[[:space:]])50([.]|[[:space:]]|$)' || exit 1
dashboard=/usr/share/alienware-battery-control-center-dashboard/dashboard/deploy.py
test "$(systemctl --user show -p LoadState --value bat07-widget.service)" = not-found || exit 1
must /usr/bin/python3 -B "$dashboard" preflight
/usr/bin/python3 -B - <<'PY' || exit 1
import os, sqlite3
p="/var/lib/alienware-battery-monitor/monitor.sqlite3"
assert os.access(p, os.R_OK) and not os.access(p, os.W_OK)
with sqlite3.connect("file:" + p + "?mode=ro", uri=True) as db:
    assert db.execute("PRAGMA quick_check").fetchone()==("ok",)
PY
must /usr/bin/python3 -B "$dashboard" install --confirm
must systemctl --user show bat07-widget.service -p ActiveState -p MainPID -p InvocationID -p NRestarts
gnome-extensions info bat07-widget@alienware.local || exit 1
```

If needed log in again for extension discovery. Check visibility, all controls, always-on-top, two-second updates, data unavailability and history per [clean-host plan](CLEAN_HOST_TEST_PLAN.md). With the extension active and widget visible and idle, run `/usr/bin/python3 -B /usr/share/alienware-battery-control-center-dashboard/dashboard/deploy.py verify`. Pass requires 60 seconds, CPU **<2%** of one logical core, sampled RSS **<100 MiB**, stable PID and invocation identity, and zero automatic restarts. TCG is diagnostic only. KVM results apply to this VM and synthetic readings. Physical Alienware and firmware evidence remains separate.

## D. Approved upgrade, rollback and recovery fixtures

Run the next block separately using the exact role variable `ABCC_COMPONENT=backend` in the guest administrator shell or `ABCC_COMPONENT=dashboard` as the desktop test user. For each component, snapshot installed program hashes and retain the verified integration baseline, recalculate the fixture manifest after each intentional content change, and verify it before activation. The installers independently regenerate the installed manifest during a successful upgrade. Report a pass only if normal rollback and automatic failure recovery each restore the exact program, remove the transient predecessor, restore the active service, and leave the group and SQLite history intact. Compare existing rows while allowing new scheduled samples.

```bash
must() { "$@" || exit 1; }
case "$(systemd-detect-virt)" in kvm|qemu) ;; *) exit 1 ;; esac
test "${ABCC_APPROVE_GUEST_FAILURES:-}" = YES && test -n "${ABCC_COMPONENT:-}" || exit 1
case "$ABCC_COMPONENT" in
  backend)
    test "$(id -u)" -eq 0 || exit 1
    parent=/root/abcc-qualification-backend; program=/opt/alienware-battery-monitor
    script=monitor.py; py=/usr/bin/python3; opts=-IB
    service=(systemctl is-active alienware-battery-monitor.timer)
    ;;
  dashboard)
    test "$(id -un)" = abcc-test || exit 1
    parent="$HOME/abcc-qualification-dashboard"; program="$HOME/.local/share/bat07-widget"
    script=widget.py; py=/usr/bin/python3; opts=-B
    service=(systemctl --user is-active bat07-widget.service)
    ;;
  *) exit 1 ;;
esac
src="/usr/share/alienware-battery-control-center-$ABCC_COMPONENT"
test ! -e "$parent" && test ! -L "$parent" || exit 1
test ! -e "$program.previous" && test ! -L "$program.previous" || exit 1
must mkdir -m 700 "$parent"
must cp -R "$src" "$parent/candidate"
must chmod -R u+w "$parent/candidate"
candidate="$parent/candidate/$ABCC_COMPONENT"
hash_tree() {
  directory="$1"; manifest="$2"
  (cd "$directory" && find . -type f -print0 > "$parent/file-list" &&
    sort -z -o "$parent/file-list" "$parent/file-list" &&
    xargs -0 -r sha256sum < "$parent/file-list" > "$manifest" &&
    test -s "$manifest" && sha256sum --strict -c "$manifest") || exit 1
}
hash_tree "$program" "$parent/program-before.sha256"
refresh_fixture() {
  hash_tree "$parent/candidate" "$parent/$1.sha256"
}
printf '\n# qualification upgrade fixture\n' >> "$candidate/$script" || exit 1
refresh_fixture normal
must "$py" "$opts" "$candidate/deploy.py" upgrade --confirm
test -f "$program.previous/manifest.json" || exit 1
must cmp "$candidate/$script" "$program/$script"
must "$py" "$opts" "$candidate/deploy.py" rollback --confirm
(cd "$program" && sha256sum --strict -c "$parent/program-before.sha256") || exit 1
test ! -e "$program.previous" && test ! -L "$program.previous" || exit 1
must "${service[@]}"
must sed -i '2i raise SystemExit(1)' "$candidate/$script"
refresh_fixture failure
if "$py" "$opts" "$candidate/deploy.py" upgrade --confirm; then exit 1; fi
(cd "$program" && sha256sum --strict -c "$parent/program-before.sha256") || exit 1
test ! -e "$program.previous" && test ! -L "$program.previous" || exit 1
must "${service[@]}"
```

Check the desktop service again after ten seconds, with active state, stable PID/invocation and zero restarts. An early refusal to process the fixture does not demonstrate recovery. Require service evidence of the deliberately failing invocation followed by a healthy restored invocation. The installed units and managed integrations must still match their originals. Review these files separately against the verified package or the dashboard's initial manifest. For additional interrupted-swap testing, use a separate disposable overlay and approved fault injection. `recover --confirm` qualifies only when the current directory is absent, the verified predecessor is restored byte-for-byte, the service passes startup and historical rows remain.

## E. Uninstall and clean up after approval

Guest test user runs the dashboard uninstaller with `--confirm` after checking the guest identity; guest administrator then removes backend and payloads. Skip optional notifications unless separately approved; if enabled, disable them in the test session first.

```bash
case "$(systemd-detect-virt)" in kvm|qemu) ;; *) exit 1 ;; esac
test "${ABCC_APPROVE_GUEST_CLEANUP:-}" = YES && test "$(id -un)" = abcc-test || exit 1
/usr/bin/python3 -B /usr/share/alienware-battery-control-center-dashboard/dashboard/deploy.py uninstall --confirm || exit 1
test ! -e "$HOME/.local/share/bat07-widget" || exit 1
```

```bash
must() { "$@" || exit 1; }
case "$(systemd-detect-virt)" in kvm|qemu) ;; *) exit 1 ;; esac
test "${ABCC_APPROVE_GUEST_CLEANUP:-}" = YES && test "$(id -u)" -eq 0 || exit 1
must /usr/bin/python3 -IB /usr/share/alienware-battery-control-center-backend/backend/deploy.py uninstall --confirm
test ! -e /opt/alienware-battery-monitor && test -s /var/lib/alienware-battery-monitor/monitor.sqlite3 || exit 1
must getent group alienware-battery-monitor
must apt-get --no-download remove alienware-battery-control-center-backend alienware-battery-control-center-dashboard
must umount /sys/class/power_supply
dmi=$(readlink -f /sys/class/dmi/id) || exit 1
must umount "$dmi"
must umount /mnt/abcc-fixtures
must systemctl poweroff
```

The host user waits for the QEMU process to exit. Preserve sanitized evidence only via a separately approved transfer. Retain the frozen base. With explicit disposal approval, delete only the named overlay. Recreating it from the frozen base restores a clean test snapshot for a new approved run.

```bash
test "${ABCC_APPROVE_OVERLAY_DISPOSAL:-}" = YES || exit 1
vm="$HOME/abcc-vm-qualification"
test -f "$vm/base.qcow2" && test ! -w "$vm/base.qcow2" || exit 1
test -f "$vm/qualification.qcow2" && test ! -L "$vm/qualification.qcow2" || exit 1
rm -- "$vm/qualification.qcow2" || exit 1
# A subsequent approved run creates a fresh overlay from the frozen base.
```
