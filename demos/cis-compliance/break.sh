#!/usr/bin/env bash
# ============================================================================
# demos/cis-compliance/break.sh
#
# Deliberately fail 11 of the 12 CIS Ubuntu 24.04 policies defined in
# gitops/default.yml. For the Fleet compliance-dashboard demo.
#
# Refuses to run unless ALL THREE of these are satisfied:
#   1. EUID == 0 (run with sudo)
#   2. The sentinel file /etc/fleet-cis-demo/IAMATESTVM exists
#   3. --confirm is passed as the first argument
#
# See README.md in this directory for the full safety discussion and
# exactly what the script does.
# ============================================================================

set -euo pipefail

SENTINEL=/etc/fleet-cis-demo/IAMATESTVM
LOGFILE=/var/log/fleet-cis-demo.log

banner() {
  cat <<'BANNER'
================================================================================
                     CIS COMPLIANCE BREAK SCRIPT (DANGER)
================================================================================

This script deliberately loosens or removes security controls on this host
for the purpose of demonstrating Fleet's compliance dashboard.

AFTER RUNNING:
  - /etc/shadow will be world-readable
  - /etc/passwd will be world-writable
  - /etc/ssh/sshd_config will be world-writable
  - /etc/ssh/ssh_host_rsa_key will be world-readable
  - auditd will be uninstalled
  - cron will be stopped
  - A second UID-0 account named 'rootback' will exist
  - sshd may refuse to start on the next reboot due to loose key perms

THIS IS FOR THROWAWAY TEST VMS ONLY.

Running this script on any host you care about is a bad day. Use restore.sh
to reverse the breaks.
================================================================================
BANNER
}

log() {
  local msg="$1"
  echo "[$(date -Iseconds)] $msg" | tee -a "$LOGFILE"
}

# -- Safety gates ------------------------------------------------------------

banner

if [[ "${1:-}" != "--confirm" ]]; then
  echo "ABORTED: --confirm flag not passed. See README.md."
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "ABORTED: must run as root (use sudo)."
  exit 2
fi

if [[ ! -f "$SENTINEL" ]]; then
  echo "ABORTED: sentinel file $SENTINEL not present."
  echo "If this really is a throwaway test VM, create it with:"
  echo "  sudo mkdir -p /etc/fleet-cis-demo && sudo touch $SENTINEL"
  exit 3
fi

# Make sure the log file is writable
mkdir -p "$(dirname "$LOGFILE")"
touch "$LOGFILE"

log "=== BREAK RUN STARTED ==="

# -- CIS 1.1.1.1: load the cramfs module ------------------------------------
log "breaking CIS 1.1.1.1: modprobe cramfs"
modprobe cramfs 2>&1 | tee -a "$LOGFILE" || log "  (modprobe cramfs returned non-zero, module may not be available on this kernel)"

# -- CIS 1.4.1: loosen grub.cfg perms ---------------------------------------
if [[ -f /boot/grub/grub.cfg ]]; then
  log "breaking CIS 1.4.1: chmod 0644 /boot/grub/grub.cfg"
  chmod 0644 /boot/grub/grub.cfg
else
  log "CIS 1.4.1 skipped: /boot/grub/grub.cfg does not exist on this host"
fi

# -- CIS 3.1.1: enable IPv4 forwarding --------------------------------------
log "breaking CIS 3.1.1: sysctl -w net.ipv4.ip_forward=1"
sysctl -w net.ipv4.ip_forward=1 >/dev/null

# -- CIS 4.1.1.1: remove auditd ---------------------------------------------
if dpkg -l auditd >/dev/null 2>&1; then
  log "breaking CIS 4.1.1.1: apt-get remove -y auditd"
  DEBIAN_FRONTEND=noninteractive apt-get remove -y auditd >/dev/null 2>&1 || log "  (auditd removal returned non-zero)"
else
  log "CIS 4.1.1.1 note: auditd not installed, control is already failing"
fi

# -- CIS 4.2.3: widen syslog perms ------------------------------------------
if [[ -f /var/log/syslog ]]; then
  log "breaking CIS 4.2.3: chmod 0644 /var/log/syslog"
  chmod 0644 /var/log/syslog
else
  log "CIS 4.2.3 skipped: /var/log/syslog does not exist"
fi

# -- CIS 5.1.1: stop cron ---------------------------------------------------
log "breaking CIS 5.1.1: systemctl stop cron"
systemctl stop cron 2>&1 | tee -a "$LOGFILE" || log "  (systemctl stop cron returned non-zero)"

# -- CIS 5.2.1: world-writable sshd_config ----------------------------------
log "breaking CIS 5.2.1: chmod 0666 /etc/ssh/sshd_config"
chmod 0666 /etc/ssh/sshd_config

# -- CIS 5.2.2: world-readable SSH host key ---------------------------------
log "breaking CIS 5.2.2: chmod 0644 /etc/ssh/ssh_host_rsa_key"
chmod 0644 /etc/ssh/ssh_host_rsa_key

# -- CIS 6.1.2: world-writable /etc/passwd ----------------------------------
log "breaking CIS 6.1.2: chmod 0666 /etc/passwd"
chmod 0666 /etc/passwd

# -- CIS 6.1.5: world-readable /etc/shadow ----------------------------------
log "breaking CIS 6.1.5: chmod 0644 /etc/shadow"
chmod 0644 /etc/shadow

# -- CIS 6.2.5: create a second UID-0 account -------------------------------
if ! id rootback >/dev/null 2>&1; then
  log "breaking CIS 6.2.5: useradd -o -u 0 -g 0 -M -s /bin/bash rootback"
  useradd -o -u 0 -g 0 -M -s /bin/bash rootback
else
  log "CIS 6.2.5 note: rootback user already exists"
fi

log "=== BREAK RUN COMPLETE ==="
echo
echo "Done. Wait one osquery distributed_interval (default 10s) and watch the"
echo "Fleet UI at Policies for this host to flip to failing on the broken"
echo "controls. Run restore.sh --confirm to reverse the changes."
