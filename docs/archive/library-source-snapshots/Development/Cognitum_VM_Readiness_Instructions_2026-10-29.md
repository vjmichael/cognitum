# Cognitum C15 T3 — Windows VM readiness check

Double-click **`Run-VM-Readiness-Check.cmd`** after extracting this package into a normal folder on your Windows PC. Run as a regular user; do **not** run as Administrator.

It checks your Windows edition, firmware virtualization status, CPU SLAT support, existing Hyper-V status, and whether VirtualBox or VMware executables are installed. It also reports available RAM and free disk space on the kit's volume.

**No software is installed**, no optional Windows features are enabled, no settings or firmware are changed, and there is no VM reboot, power operation, or snapshot action. Reports are written to a new `VM-Readiness-Report-*` subfolder of the kit. They do not include usernames, hostnames, serial numbers or installation paths, although they do contain the CPU model, OS version and resource totals.

Upload **`Cognitum_VM_Readiness.json`** from that folder to the ChatGPT conversation. The result will guide selection of Hyper-V (typically Windows Pro/Enterprise/Education), Oracle VirtualBox, or another existing virtualization platform.

## Important separation

Do **not** rerun the VM recovery/power-interruption harness on your physical host. Use a disposable Windows x86-64 **guest VM**. Keep the anti-rollback witness outside that VM and any guest snapshots. Guest snapshot rollback detection is **not** the same as tamper resistance against a compromised physical host. A genuine power-loss certification still requires separate, controlled storage testing.

Official guides:
- Microsoft Hyper-V: https://learn.microsoft.com/en-us/virtualization/hyper-v-on-windows/reference/hyper-v-requirements
- Oracle VirtualBox: https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/installation.html
- Firmware virtualization: https://support.microsoft.com/en-us/windows/experience/enable-virtualization-on-windows

This is a read-only preflight; **Windows execution has not yet been verified** by the authoring environment.