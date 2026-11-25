# Ubuntu VM media and offline dependencies

Official sources are the [26.04.1 release directory](https://releases.ubuntu.com/26.04.1/), [published checksums](https://releases.ubuntu.com/26.04.1/SHA256SUMS), [Ubuntu verification instructions](https://ubuntu.com/tutorials/how-to-verify-ubuntu) and [Resolute archive metadata](https://archive.ubuntu.com/ubuntu/dists/resolute/InRelease).

## Executed guest workflow

The later user-reported qualification used Ubuntu Desktop 26.04.1 on an offline KVM guest with QXL/SPICE and GNOME 50 Wayland. The exact media acquisition record, checksum signature output, and guest dependency resolution trace were not supplied. The prior preparation shell could read the official listings but could not download media through its DNS configuration. The published ISO SHA256 and the commands below document verification for a repeat run, without claiming that this release pass independently checked the guest's ISO.

APT rejected a local-package installation attempt in the offline guest. The operator reported successful installation with local `dpkg`. The raw APT diagnostic, exact command and dependency bundle inventory were not supplied. Passing service activation validates the tested guest, not dependency closure for a different baseline.

For an authorized repeat run, verify the local package hashes and satisfy dependencies from the authenticated offline bundle before the fallback. From the guest administrator shell only, stage the two verified release packages with `dpkg`, then check their configuration and dependency state before explicit activation:

```bash
case "$(systemd-detect-virt)" in kvm|qemu) ;; *) exit 1 ;; esac
test "${ABCC_APPROVE_GUEST_ACTIVATION:-}" = YES && test "$(id -u)" -eq 0 || exit 1
release=/mnt/abcc-fixtures/release
(cd "$release" && sha256sum --strict -c SHA256SUMS) || exit 1
backend=alienware-battery-control-center-backend
dashboard=alienware-battery-control-center-dashboard
dpkg -i "$release/${backend}_1.0.0_all.deb" "$release/${dashboard}_1.0.0_all.deb" || exit 1
audit=$(dpkg --audit) || exit 1
test -z "$audit" || exit 1
for package in "$backend" "$dashboard"; do
  test "$(dpkg-query -W -f='${Status}' "$package")" = 'install ok installed' || exit 1
done
```

Stop if dependencies are unresolved. Do not fetch packages inside the offline guest or force an incomplete install. See the [qualification record](evidence/GH05_QUALIFICATION.md). The following preparation commands are a repeat-run recipe.

## Download and authenticate the ISO

Run in an Ubuntu-network-enabled, unprivileged Bash terminal. Supply a trusted local Ubuntu CD-image signing keyring. Authenticate the key fingerprint independently via the official verification instructions before use. A cached ISO can be copied to the media directory first and reused after verification.

```bash
must() { "$@" || exit 1; }
test "$(id -u)" -ne 0 || exit 1
media="$HOME/abcc-vm-media"
: "${CD_IMAGE_KEYRING:?Specify a pretrusted local Ubuntu CD-image keyring}"
: "${CD_IMAGE_SIGNER:?Specify the full trusted Ubuntu CD-image signer fingerprint}"
test -r "$CD_IMAGE_KEYRING" || exit 1
must install -d -m 0700 "$media" "$media/iso" "$media/gnupg"
must cd "$media/iso"
origin=https://releases.ubuntu.com/26.04.1
iso=ubuntu-26.04.1-desktop-amd64.iso
must curl --disable --fail --silent --show-error --proto '=https' --output SHA256SUMS.ubuntu "$origin/SHA256SUMS"
must curl --disable --fail --silent --show-error --proto '=https' --output SHA256SUMS.ubuntu.gpg "$origin/SHA256SUMS.gpg"
must gpgv --homedir "$media/gnupg" --keyring "$CD_IMAGE_KEYRING" --status-fd 1 \
  SHA256SUMS.ubuntu.gpg SHA256SUMS.ubuntu > SHA256SUMS.ubuntu.status || exit 1
awk -v f="$CD_IMAGE_SIGNER" '$2=="VALIDSIG" && ($3==f || $NF==f) {ok=1} END {exit !ok}' \
  SHA256SUMS.ubuntu.status || exit 1
awk -v n="$iso" 'length($1)==64 && ($2=="*"n || $2==n) {print $1 "  " n; ++c} END {exit c!=1}' \
  SHA256SUMS.ubuntu > SHA256SUMS || exit 1
if ! test -f "$iso"; then
  must curl --disable --fail --silent --show-error --proto '=https' --output "$iso.part" "$origin/$iso"
  expected=$(awk '{print $1}' SHA256SUMS) || exit 1
  printf '%s  %s\n' "$expected" "$iso.part" | sha256sum --strict -c - || exit 1
  must mv -- "$iso.part" "$iso"
fi
must sha256sum --strict -c SHA256SUMS
must stat -c '%n %s bytes' "$iso"
```

## Resolve and download dependencies without touching host APT

Use the **exact unmodified, post-install guest dpkg status file** for the chosen ISO installation profile. The [VM manifest](VM_QUALIFICATION_MANIFEST.md) exports it before any release packages are installed. ISO live package lists and host dpkg state do not establish installed guest closure. If the exact guest status is unavailable, mark all closure requirements unresolved. Direct requirements include `python3 (>= 3.10)`, `systemd`, `passwd`, `python3-gi`, `python3-cairo`, GTK 3 and GdkPixbuf typelibs. This scenario additionally requires GNOME Shell 50 with a working Wayland session. Optional notification packages are excluded.

The isolated APT commands below read only the supplied status file, use Ubuntu Resolute's signed release pocket for a reproducible baseline, and fail if the versioned dependency plan requires removals, unavailable versions or archive entries outside that pocket. The host APT configuration and package state are outside this operation. Make a fresh `apt-sandbox` per baseline.

```bash
must() { "$@" || exit 1; }
test "$(id -u)" -ne 0 || exit 1
media="$HOME/abcc-vm-media"
release="$HOME/Projects/alienware-battery-control-center/dist"
: "${GUEST_DPKG_STATUS:?Specify exact post-install baseline dpkg status file}"
test -s "$GUEST_DPKG_STATUS" || exit 1
test -r /usr/share/keyrings/ubuntu-archive-keyring.gpg || exit 1
(cd "$release" && sha256sum --strict -c SHA256SUMS) || exit 1
work="$media/apt-sandbox"
bundle="$media/dependencies"
test ! -e "$work" && test ! -L "$work" && test ! -e "$bundle" && test ! -L "$bundle" || exit 1
must install -d -m 0700 "$work" "$work/lists/partial" "$work/archives/partial" "$bundle"
must cp -- "$GUEST_DPKG_STATUS" "$work/status"
printf '%s\n' 'deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://archive.ubuntu.com/ubuntu/ resolute main restricted universe multiverse' > "$work/sources.list" || exit 1
cat > "$work/apt.conf" <<CONF || exit 1
Dir::Etc::parts "-";
Dir::Etc::main "-";
Dir::Etc::sourcelist "$work/sources.list";
Dir::Etc::sourceparts "-";
Dir::Etc::preferences "-";
Dir::Etc::preferencesparts "-";
Dir::State "$work";
Dir::State::status "$work/status";
Dir::State::lists "$work/lists";
Dir::Cache "$work";
Dir::Cache::archives "$work/archives";
Dir::Log "$work";
APT::Architecture "amd64";
Acquire::Languages "none";
Acquire::https::AllowRedirect "false";
Acquire::AllowInsecureRepositories "false";
APT::Get::AllowUnauthenticated "false";
CONF
packages=("$release/alienware-battery-control-center-backend_1.0.0_all.deb"
          "$release/alienware-battery-control-center-dashboard_1.0.0_all.deb")
must env APT_CONFIG="$work/apt.conf" apt-get -o APT::Update::Error-Mode=any update
must env APT_CONFIG="$work/apt.conf" apt-get -s --no-install-recommends --no-remove install "${packages[@]}" > "$work/closure.txt" || exit 1
must env APT_CONFIG="$work/apt.conf" apt-get -y --download-only --no-install-recommends --no-remove install "${packages[@]}"
for package in "$work"/archives/*.deb; do
  if test -f "$package"; then must cp -- "$package" "$bundle/"; fi
done
must cp -- "$work/closure.txt" "$bundle/CLOSURE.txt"
(cd "$work" && sha256sum status) > "$bundle/BASELINE.SHA256" || exit 1
(
  must cd "$bundle"
  files=(CLOSURE.txt BASELINE.SHA256)
  for package in ./*.deb; do
    if test -f "$package"; then files+=("$package"); fi
  done
  must sha256sum -- "${files[@]}" > SHA256SUMS || exit 1
  must sha256sum --strict -c SHA256SUMS
) || exit 1
must sha256sum "$bundle/SHA256SUMS"
```

APT authenticates InRelease and package index digests and checks package object hashes during download. Keep signed indexes, resolver output, exact dpkg-status digest and raw package checksums as preparation evidence. A zero-DEB closure is valid only if the exact baseline simulation succeeded. Guest activation is gated on the separate no-download simulation with the actual bundle. If either simulation fails, capture the reported dependency constraints and stop. Do not substitute host packages or use unauthenticated repositories. If the release pocket cannot supply the ISO's point-release versions, an explicitly approved, authenticated matching Ubuntu pocket or snapshot is a prerequisite. Do not widen the source list implicitly.

## Historical non-boot preparation checks

QEMU reported the GTK display backend and GTK libraries were installed. GTK initialization could not connect to a display in this execution context. The host operator reported accessible KVM; this execution context has no `/dev/kvm`, so the launch guard must be rechecked from the approved desktop terminal. The synthetic fixture was read successfully by unchanged backend and dashboard code in a temporary directory, including exact readings, missing firmware handling and an in-memory SQLite sample. The preparation shell did not exercise the service namespace gate. The later VM report records successful guest backend and dashboard operation and fixture cleanup.
