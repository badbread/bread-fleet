# macOS on Proxmox: the qm importdisk gotcha

Brief debugging note from setting up an OpenCore-based macOS VM on
Proxmox so I could exercise the macOS-side of Fleet (MDM enrollment,
osquery on darwin, CIS macOS controls). The VM build itself is
boilerplate and well-covered by the OSX-KVM project. This note
exists because of one Proxmox-specific behavior that cost me an
hour and isn't documented anywhere obvious.

## The setup that the gotcha is hiding inside

A Proxmox VM with OVMF UEFI, q35 chipset, an OpenCore boot ISO on
`ide0`, a blank target disk on `virtio0`, and a `BaseSystem.img`
(the macOS recovery installer, converted from `.dmg` via `dmg2img`)
that needs to be attached so OpenCore can find and boot it.

The intuitive thing to do, and the thing every guide tells you to
do, is to drop `BaseSystem.img` into `/var/lib/vz/template/iso/`
and attach it via `qm set`:

```bash
qm set <VMID> --sata0 /var/lib/vz/template/iso/BaseSystem.img,cache=unsafe
```

## What actually happens

Proxmox auto-flags any disk image attached from a path under
`/var/lib/vz/template/iso/` as `media=cdrom`, regardless of what the
image actually is. The resulting `qm config` looks like:

```
sata0: local:iso/BaseSystem.img,media=cdrom,cache=unsafe,size=3145616K
```

OpenCore's picker scans SATA hard disks for macOS boot candidates.
It does NOT treat SATA CDROMs the same way. `BaseSystem.img` is
visible to QEMU as an attached device, but invisible to OpenCore's
boot selection logic.

The symptom is the OC picker showing only the built-in tool entries
("Reset NVRAM", "Toggle SIP") and no macOS volume to install from.
Spending an hour adjusting OC config files looking for the missing
volume yields exactly nothing because the image is not the problem.

## The fix

Use `qm importdisk` instead of `qm set` directly. importdisk copies
the raw image into a real Proxmox storage pool (in this case the
local ZFS pool), where it gets registered as a VM disk rather than
a CDROM-implied iso template entry:

```bash
qm stop <VMID>
qm importdisk <VMID> /var/lib/vz/template/iso/BaseSystem.img local-zfs --format raw
# importdisk attaches it as 'unused0:'
qm set <VMID> --sata0 local-zfs:vm-<VMID>-disk-2,cache=unsafe
qm set <VMID> --boot 'order=ide0;sata0;virtio0'
qm start <VMID>
```

The `qm config` now shows `sata0: local-zfs:...,size=3G` with no
`media=cdrom`. OpenCore sees it. The picker shows the macOS Base
System entry. The install proceeds.

## Why this is documented here

Two reasons:

1. **Future-me will hit this again.** Every time I rebuild the
   macOS test VM I'm going to forget which detail mattered. Two
   sentences in this file save the next hour.

2. **It's a real example of the kind of thing that doesn't show up
   in the vendor docs.** The Proxmox docs explain `qm importdisk`
   and they explain `qm set`, but neither mentions the
   `media=cdrom` auto-flag for paths under iso storage. The OpenCore
   docs explain ScanPolicy and they explain how the picker works,
   but they don't say anything about Proxmox's storage type
   inference. The interaction between two correctly-documented
   pieces is where the bug lives, and it only surfaces when you've
   read both sets of docs and still can't see why your install
   image isn't appearing.

## Hardware identifiers and what's not in scope

This VM has fabricated hardware identifiers and will not function
for iCloud, FaceTime, iMessage, or anything that requires Apple's
server-side identity validation. That is fine for the work this
repo cares about: MDM, osquery, CIS benchmark evaluation, and
testing how Fleet responds to a macOS-class host.

In a real corporate deployment, Apple devices enroll via Apple
Business Manager and DEP, which assigns devices to an MDM server
automatically at first boot using a real hardware record. An
OpenCore VM cannot participate in ABM because it has no real
hardware identity to register. The contrast is
the entire point: this VM proves the Fleet-side of the macOS
pipeline (server, agent, policy evaluation, MDM profile delivery
when HTTPS is configured), while the ABM-side is a registration
workflow on the Apple side that requires real hardware and lives
in IT's corporate Apple developer account.
