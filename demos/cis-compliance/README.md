# CIS compliance break and restore demo

A pair of shell scripts that deliberately fail 11 of the 12 CIS
Ubuntu 24.04 policies in `gitops/default.yml`, then restore them.
Used for two things:

1. **Regression testing.** When a policy in `default.yml` changes,
   running `break.sh` on a test host and confirming the affected
   policies flip in the Fleet UI verifies the new query actually
   catches the violation it claims to.

2. **Live demonstration.** A compliant host next to a deliberately
   failing host in the same Fleet instance shows the compliance
   dashboard the way an operator actually uses it: mostly green,
   one host red, click in to see what's wrong.

## Test host requirements

A throwaway Ubuntu 24.04 VM enrolled in the same Fleet instance as
the compliant host. After `break.sh`, this VM has world-writable
`/etc/passwd`, world-readable `/etc/shadow`, a second UID-0
account, and a stopped cron daemon. Reversible via `restore.sh`,
but not safe to leave in this state for any real workload.

## Three-layer safety gate

`break.sh` and `restore.sh` both refuse to run unless all three are
true:

1. EUID is 0 (run with `sudo`)
2. The sentinel file `/etc/fleet-cis-demo/IAMATESTVM` exists on disk
3. `--confirm` is passed as the first argument

The sentinel is the deliberate barrier: it has to be created on the
target host manually, it isn't in the repo, and creating it is the
operator's "I know this is a throwaway VM" acknowledgment.

```bash
sudo mkdir -p /etc/fleet-cis-demo
sudo touch /etc/fleet-cis-demo/IAMATESTVM
sudo ./break.sh --confirm
# ... confirm Fleet dashboard goes red ...
sudo ./restore.sh --confirm
```

## What gets broken

| # | CIS control | Break action | Reversal |
|---|---|---|---|
| 1 | 1.1.1.1 cramfs module disabled | `modprobe cramfs` | `modprobe -r cramfs` |
| 2 | 1.4.1 grub.cfg perms | chmod 0644 /boot/grub/grub.cfg | chmod 0600 |
| 3 | 3.1.1 IPv4 forwarding disabled | sysctl net.ipv4.ip_forward=1 | sysctl net.ipv4.ip_forward=0 |
| 4 | 4.1.1.1 auditd installed | apt-get remove -y auditd | apt-get install -y auditd |
| 5 | 4.2.3 syslog perms | chmod 0644 /var/log/syslog | chmod 0640 |
| 6 | 5.1.1 cron active | systemctl stop cron | systemctl start cron |
| 7 | 5.2.1 sshd_config perms | chmod 0666 /etc/ssh/sshd_config | chmod 0600 |
| 8 | 5.2.2 SSH host key perms | chmod 0644 /etc/ssh/ssh_host_rsa_key | chmod 0600 |
| 9 | 6.1.2 /etc/passwd perms | chmod 0666 /etc/passwd | chmod 0644 |
| 10 | 6.1.5 /etc/shadow perms | chmod 0644 /etc/shadow | chmod 0640 |
| 11 | 6.2.5 only root has UID 0 | useradd -o -u 0 rootback | userdel rootback |

## Not broken on purpose

**CIS 3.5 host firewall module loaded** is intentionally skipped.
Unloading `nf_tables` or `iptable_filter` on a running system can
disrupt active firewall rules and in some cases break the network
mid-script. The script has no way to recover from a self-inflicted
network outage on the host it's running on. Better to leave that
control alone.

## Dangerous states the test host enters

After `break.sh`, the test host has:

- World-writable `/etc/passwd` (any user can add UID-0 accounts)
- World-readable `/etc/shadow` (every password hash exposed)
- World-writable `/etc/ssh/sshd_config` (any user can change SSH auth)
- World-readable SSH host private key (sshd may refuse to start on next reboot)
- A second UID-0 account named `rootback`
- A stopped cron daemon
- No auditd

All reversible via `restore.sh`. If the host reboots between break
and restore, sshd may fail to come up because of the loose key
perms; recover from the console.

## Action log

Both scripts append to `/var/log/fleet-cis-demo.log` with a
timestamp and the action taken. Useful for after-the-fact audit
("what did break.sh actually do on this host?") and for
troubleshooting if `restore.sh` finds something it didn't expect.
