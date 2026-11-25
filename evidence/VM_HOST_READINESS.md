# Read-only VM host qualification

| Prerequisite | Observed |
| --- | --- |
| Virtualization tools | QEMU x86_64 and qemu-img 10.2.1, QEMU GTK GUI package, and xorriso 1.5.6 available. No libvirt or VirtualBox executable found in PATH. |
| Acceleration | CPU flags expose VMX. `/dev/kvm` was unavailable in the current execution context. Its availability to a separately approved host session is unverified. |
| Capacity | 20 logical CPUs reported, roughly 14.8 GiB RAM total and 9.6 GiB available at inspection. The workspace filesystem reported about 715 GiB available. Recheck immediately before an approved run. |
| Media | No Ubuntu ISO found in the workspace, Downloads, or the inspected common ISO and mounted-media locations. Offline dependencies and a verified guest image remain to be supplied. |
| Readiness | Documentation is ready. Execution is blocked on verified offline Ubuntu media and an approval. A KVM-backed benchmark also requires an accessible KVM device. |

No VM or disk image was created. No VM process was started.
