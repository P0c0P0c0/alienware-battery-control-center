# Compatibility

| Environment | Status |
| --- | --- |
| Alienware m15 R7, Ubuntu 26.04.1, GNOME 50 Wayland | Accepted R7.2 widget benchmark. BAT-05 and GNOME integration were active in the supplied evidence. |
| v1.0.0 on Ubuntu 26.04.1, KVM, GNOME 50 Wayland, offline QXL/SPICE | User-reported qualification passed with synthetic battery inputs. See [GH-05 evidence](evidence/GH05_QUALIFICATION.md). |
| Other supported Debian/Ubuntu releases with Python 3.10+, systemd and GTK 3 | Packages build locally. Runtime behavior needs separate validation. Wayland integration requires GNOME Shell 50 and user extensions. |
| X11 with EWMH above-window support | An explicit preflight checks the hint. Live X11 coverage is pending. |
| Other Wayland compositors, unsupported GNOME versions, missing BAT0 | Outside the documented installation target. |

The code expects the battery device at `BAT0`. AC state expects an `AC/online` attribute. Dell WMI firmware attributes may be inaccessible or missing. The dashboard reports unavailable data and stale samples rather than inventing values. Watt-hours are labeled as estimated when calculated from charge and design voltage. Some machines expose energy-only attributes and cannot provide the project's charge-based SOH. Firmware limits outside the observed 50–70% policy can trigger an alert. These limits do not gate installation and the software never changes them.
