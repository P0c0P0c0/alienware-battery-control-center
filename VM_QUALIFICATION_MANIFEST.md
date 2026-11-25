# Isolated VM qualification manifest

**Prepared only.** Scope is one disposable Ubuntu amd64 guest with GNOME Shell 50 and Wayland. Use Ubuntu 26.04.1 if available to match the accepted physical baseline. Ready for execution approval, with prerequisites still open in [host evidence](evidence/VM_HOST_READINESS.md).

## Approval gates and budget

1. **Host and VM creation.** Require separate approval, an authorized Ubuntu Desktop ISO with a trusted SHA256, a trusted offline dependency set or a pre-provisioned GNOME system, and working QEMU GTK display access. Reserve 4 vCPUs, 6 GiB guest RAM and at least 90 GiB host storage for the 40 GiB sparse base, disposable overlay and media. Leave at least 3 GiB RAM available to the host at launch. KVM requires read/write access to `/dev/kvm`. With approval, TCG may be used for functional checks only. Do not change device permissions, load host kernel modules or enable networking.
2. **Guest activation.** Require approval before installing packages, mounting fixtures or invoking authenticated administration in the guest. Use a dedicated user named `abcc-test` and a separate authorized guest administrator shell. No physical-device passthrough or host-directory sharing.
3. **Failure and cleanup.** Require approval before deliberately failing guest services, discarding the overlay, or promoting a new qualification image. The approved artifacts and base image remain outside destructive test steps.

## Host commands after approval

Run with Bash as the desktop user. Set the ISO path and trusted digests before running. The optional dependency bundle must be an offline directory of compatible DEBs and contain a trusted `SHA256SUMS`. Package payloads are exposed as a read-only ISO. The newly created VM directory must be unused.

```bash
set -euo pipefail
cd "$HOME/Projects/alienware-battery-control-center"
: "${UBUNTU_ISO:?Set absolute path to trusted Ubuntu Desktop ISO}"
: "${UBUNTU_SHA256:?Set trusted Ubuntu ISO SHA256}"
: "${OFFLINE_DEBS:?Set absolute path to the verified offline dependency bundle}"
: "${OFFLINE_MANIFEST_SHA256:?Set trusted SHA256 of the dependency bundle manifest}"
test -f "$UBUNTU_ISO"
test "$(nproc)" -ge 4
awk '/^MemAvailable:/ { exit !($2 >= 9437184) }' /proc/meminfo
df -PB1 "$HOME" | awk 'NR == 2 { exit !($4 >= 96636764160) }'
printf '%s  %s\n' "$UBUNTU_SHA256" "$UBUNTU_ISO" | sha256sum -c -
(cd "$OFFLINE_DEBS" &&
 printf '%s  %s\n' "$OFFLINE_MANIFEST_SHA256" SHA256SUMS | sha256sum -c - &&
 sha256sum --strict -c SHA256SUMS)
(cd dist && sha256sum --strict -c SHA256SUMS)
test -r /dev/kvm && test -w /dev/kvm
vm="$HOME/abcc-vm-qualification"
mkdir -m 700 "$vm"
mkdir -p "$vm/media/release" "$vm/media/dependencies"
cp -- dist/*.deb dist/SHA256SUMS dist/*.tar.gz "$vm/media/release/"
cp -- "$OFFLINE_DEBS/SHA256SUMS" "$vm/media/dependencies/"
while read -r digest filename; do
  filename="${filename#\*}"
  [[ "$digest" =~ ^[[:xdigit:]]{64}$ && "$filename" =~ ^[a-zA-Z0-9][a-zA-Z0-9._+~%-]*[.]deb$ ]]
  test -f "$OFFLINE_DEBS/$filename" && test ! -L "$OFFLINE_DEBS/$filename"
  cp -- "$OFFLINE_DEBS/$filename" "$vm/media/dependencies/"
done < "$OFFLINE_DEBS/SHA256SUMS"
xorriso -as mkisofs -R -V ABCC_FIXTURES -o "$vm/fixtures.iso" "$vm/media"
qemu-img create -f qcow2 "$vm/base.qcow2" 40G
qemu-system-x86_64 -name ABCC-Setup -machine q35 -accel kvm -cpu host \
  -smp 4 -m 6144 -nic none -display gtk,gl=off \
  -drive "file=$vm/base.qcow2,if=virtio,format=qcow2" \
  -drive "file=$UBUNTU_ISO,media=cdrom,readonly=on" -boot once=d
```

Complete Ubuntu installation offline. Create the dedicated guest account during setup and verify GNOME 50 Wayland. Power the guest off. Set the base file read-only with `chmod a-w "$vm/base.qcow2"`. Keep the base frozen and start a disposable overlay. If KVM is unavailable and TCG-only qualification was separately approved, replace `-accel kvm -cpu host` in both QEMU commands with `-accel tcg,thread=multi -cpu max` and omit the KVM access check. Record this difference.

```bash
vm="$HOME/abcc-vm-qualification"
qemu-img create -f qcow2 -F qcow2 -b "$vm/base.qcow2" "$vm/qualification.qcow2"
qemu-system-x86_64 -name ABCC-Qualification -machine q35 -accel kvm -cpu host \
  -smp 4 -m 6144 -nic none -display gtk,gl=off \
  -drive "file=$vm/qualification.qcow2,if=virtio,format=qcow2" \
  -drive "file=$vm/fixtures.iso,media=cdrom,readonly=on"
```

## Guest-only installation and fixture commands

Run in the authorized **guest administrator** shell. The first checks guard the guest environment. Before mounting fixtures, run backend preflight and record the expected unsupported-hardware refusal on a VM without Dell sysfs. The approved offline bundle and APT's no-download mode prevent dependency fetching. Before explicit application activation, confirm both project units are absent or `not-found`.

```bash
set -euo pipefail
case "$(systemd-detect-virt)" in kvm|qemu) ;; *) exit 1 ;; esac
test "$(id -u)" -eq 0
id abcc-test
install -d -m 0755 /mnt/abcc-fixtures
mount -o ro,nosuid,nodev,noexec LABEL=ABCC_FIXTURES /mnt/abcc-fixtures
m=/mnt/abcc-fixtures
(cd "$m/release" && sha256sum --strict -c SHA256SUMS)
(cd "$m/dependencies" && sha256sum --strict -c SHA256SUMS)
apt-get --no-download --no-install-recommends install "$m"/dependencies/*.deb \
  "$m"/release/*-backend_1.0.0_all.deb "$m"/release/*-dashboard_1.0.0_all.deb
backend=/usr/share/alienware-battery-control-center-backend/backend/deploy.py
systemctl show -p LoadState alienware-battery-monitor.timer
if /usr/bin/python3 -IB "$backend" preflight; then
  printf '%s\n' 'Unexpected hardware preflight success without fixtures'; exit 1
fi

# Use guest bind mounts. No firmware attribute is written or emulated here.
f=/run/abcc-synthetic
install -d -m 0755 "$f/dmi" "$f/power/BAT0" "$f/power/AC"
printf '%s\n' 'Dell Inc.' > "$f/dmi/sys_vendor"
printf '%s\n' 'Alienware Synthetic VM' > "$f/dmi/product_name"
for kv in charge_full=6400000 charge_full_design=8000000 charge_now=4000000 \
  capacity=62 temp=335 voltage_now=11800000 current_now=1000 voltage_min_design=11400000 \
  status=Charging health=Good; do
  printf '%s\n' "${kv#*=}" > "$f/power/BAT0/${kv%%=*}"
done
printf '1\n' > "$f/power/AC/online"
mount --bind "$f/dmi" /sys/class/dmi/id
mount --bind "$f/power" /sys/class/power_supply
/usr/bin/python3 -IB "$backend" preflight
/usr/bin/python3 -IB "$backend" install --confirm
gpasswd -a abcc-test alienware-battery-monitor
systemctl is-active alienware-battery-monitor.timer
systemctl start alienware-battery-monitor.service
stat -c '%a %U %G %n' /var/lib/alienware-battery-monitor{,/monitor.sqlite3}
/usr/bin/python3 -IB /opt/alienware-battery-monitor/monitor.py status
```

Synthetic readings should show 80% SOH, 62% SOC and 33.5 °C. Firmware fields are deliberately unavailable. Record missing attribute alerts and an unavailable protection target. Do not use the simulated fixture to assess real Dell firmware compatibility. The installed backend preflight is expected to warn that the observed firmware policy is missing. Wait for samples at five-minute intervals for multiple chart points. Data belongs only to the disposable guest.

## Guest desktop, SQLite and performance

Sign in again to the GNOME Wayland session as `abcc-test` after granting group membership. Run from that user's terminal.

```bash
set -euo pipefail
test "$(id -un)" = abcc-test
test "$XDG_SESSION_TYPE" = wayland
gnome-shell --version | grep -E '(^|[[:space:]])50([.]|[[:space:]]|$)'
dashboard=/usr/share/alienware-battery-control-center-dashboard/dashboard/deploy.py
systemctl --user show -p LoadState bat07-widget.service
/usr/bin/python3 -B "$dashboard" preflight
/usr/bin/python3 -B - <<'PY'
import os, sqlite3
path = "/var/lib/alienware-battery-monitor/monitor.sqlite3"
assert os.access(path, os.R_OK) and not os.access(path, os.W_OK)
with sqlite3.connect("file:" + path + "?mode=ro", uri=True) as db:
    assert db.execute("PRAGMA quick_check").fetchone() == ("ok",)
    assert db.execute("SELECT count(*) FROM samples").fetchone()[0] >= 1
PY
/usr/bin/python3 -B "$dashboard" install --confirm
systemctl --user show bat07-widget.service -p ActiveState -p MainPID -p InvocationID -p NRestarts
gnome-extensions info bat07-widget@alienware.local
```

The installer must pass its ten-second gate. If necessary, sign out and back in for extension discovery. Follow the [GNOME checklist](CLEAN_HOST_TEST_PLAN.md), including the two-second SYSFS display, chart periods, menu actions and hide/show behavior. Command the launcher to show the dashboard if it is hidden. Measure only after it is visible and idle, with the extension active.

```bash
/usr/bin/python3 -B /usr/share/alienware-battery-control-center-dashboard/dashboard/deploy.py verify
```

Apply CPU **<2% of one logical core**, peak sampled RSS **<100 MiB**, 60 seconds, stable PID and invocation identity, and zero restarts. Record VM accelerator and rendering backend. TCG output is diagnostic only. A KVM pass qualifies only this guest widget scenario with synthetic sysfs. The accepted physical result is separately documented in [README](README.md) and does not establish VM performance. The VM verifies neither Dell firmware access nor physical charging behavior.

## Guest upgrade, failure recovery and cleanup

Proceed only after approval of the guest failure fixtures. Preserve integration files and create a versioned test copy. Use the documented component commands on disposable guest state. The following verifies normal changes and a deliberate start failure. A Python comment changes the payload digest without changing behavior.

```bash
# Guest administrator only
case "$(systemd-detect-virt)" in kvm|qemu) ;; *) exit 1 ;; esac
test "$(id -u)" -eq 0
install -d -m 0700 /root/abcc-fixtures
cp -a /usr/share/alienware-battery-control-center-backend /root/abcc-fixtures/backend
b=/root/abcc-fixtures/backend/backend
sha256sum /opt/alienware-battery-monitor/monitor.py > /run/abcc-backend-before.sha256
printf '\n# qualification upgrade fixture\n' >> "$b/monitor.py"
/usr/bin/python3 -IB "$b/deploy.py" upgrade --confirm
/usr/bin/python3 -IB "$b/deploy.py" rollback --confirm
sha256sum -c /run/abcc-backend-before.sha256
sed -i '2i raise SystemExit(1)' "$b/monitor.py"
if /usr/bin/python3 -IB "$b/deploy.py" upgrade --confirm; then exit 1; fi
sha256sum -c /run/abcc-backend-before.sha256
systemctl is-active alienware-battery-monitor.timer
```

```bash
# GNOME test user only
test "$(id -un)" = abcc-test
install -d -m 0700 "$HOME/abcc-fixtures"
cp -a /usr/share/alienware-battery-control-center-dashboard "$HOME/abcc-fixtures/dashboard"
chmod -R u+w "$HOME/abcc-fixtures/dashboard"
d="$HOME/abcc-fixtures/dashboard/dashboard"
sha256sum "$HOME/.local/share/bat07-widget/widget.py" > "$HOME/abcc-fixtures/widget-before.sha256"
printf '\n# qualification upgrade fixture\n' >> "$d/widget.py"
/usr/bin/python3 -B "$d/deploy.py" upgrade --confirm
/usr/bin/python3 -B "$d/deploy.py" rollback --confirm
sha256sum -c "$HOME/abcc-fixtures/widget-before.sha256"
sed -i '2i raise SystemExit(1)' "$d/widget.py"
if /usr/bin/python3 -B "$d/deploy.py" upgrade --confirm; then exit 1; fi
sha256sum -c "$HOME/abcc-fixtures/widget-before.sha256"
systemctl --user is-active bat07-widget.service
/usr/bin/python3 -B /usr/share/alienware-battery-control-center-dashboard/dashboard/deploy.py uninstall --confirm
```

As guest administrator, record retained SQLite history across each stage, check that the dashboard and backend files are removed by their uninstallers, then shut down.

```bash
case "$(systemd-detect-virt)" in kvm|qemu) ;; *) exit 1 ;; esac
test "$(id -u)" -eq 0
/usr/bin/python3 -IB /usr/share/alienware-battery-control-center-backend/backend/deploy.py uninstall --confirm
test -s /var/lib/alienware-battery-monitor/monitor.sqlite3
getent group alienware-battery-monitor
apt-get --no-download remove alienware-battery-control-center-backend alienware-battery-control-center-dashboard
umount /sys/class/power_supply
umount /sys/class/dmi/id
umount /mnt/abcc-fixtures
systemctl poweroff
```

After the guest exits, export only sanitized evidence through a separately approved method. Leave the offline base untouched. With cleanup approval, discard only the named overlay, then restore the clean snapshot by recreating an empty overlay from the frozen base for any subsequent run. A completed qualification overlay may instead be retained under the approved evidence policy.

```bash
vm="$HOME/abcc-vm-qualification"
test -f "$vm/base.qcow2" && test -f "$vm/qualification.qcow2"
rm -- "$vm/qualification.qcow2"
# For a new approved run only:
qemu-img create -f qcow2 -F qcow2 -b "$vm/base.qcow2" "$vm/qualification.qcow2"
```
