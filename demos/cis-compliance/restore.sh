#!/usr/bin/env bash
# ============================================================================
# demos/cis-compliance/restore.sh
#
# Reverse the changes made by break.sh. Idempotent: running on a host
# that is already compliant is a no-op.
#
# Same three safety gates as break.sh (root, sentinel, --confirm). The
# sentinel requirement is kept even for the restore direction because
# this script still modifies system state and needs explicit operator
# intent, not a typo.
# ============================================================================

set -euo pipefail

SENTINEL=/etc/fleet-cis-demo/IAMATESTVM
LOGFILE=/var/log/fleet-cis-demo.log

banner() {
  cat <<'BANNER'
================================================================================
                    CIS COMPLIANCE RESTORE SCRIPT
================================================================================

Reverses the changes made by break.sh. Restores CIS-compliant state for the
11 controls that break.sh can modify. Idempotent.
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
  exit 3
fi

mkdir -p "$(dirname "$LOGFILE")"
touch "$LOGFILE"

log "=== RESTORE RUN STARTED ==="

# -- CIS 1.1.1.1: unload cramfs ---------------------------------------------
if lsmod | grep -q '^cramfs'; then
  log "restoring CIS 1.1.1.1: modprobe -r cramfs"
  modprobe -r cramfs 2>&1 | tee -a "$LOGFILE" || log "  (modprobe -r cramfs returned non-zero, module may be in use)"
else
  log "CIS 1.1.1.1 already compliant: cramfs not loaded"
fi

# -- CIS 1.4.1: restore grub.cfg perms --------------------------------------
if [[ -f /boot/grub/grub.cfg ]]; then
  log "restoring CIS 1.4.1: chown root:root /boot/grub/grub.cfg && chmod 0600"
  chown root:root /boot/grub/grub.cfg
  chmod 0600 /boot/grub/grub.cfg
fi

# -- CIS 3.1.1: disable IPv4 forwarding -------------------------------------
log "restoring CIS 3.1.1: sysctl -w net.ipv4.ip_forward=0"
sysctl -w net.ipv4.ip_forward=0 >/dev/null

# -- CIS 4.1.1.1: reinstall auditd ------------------------------------------
if ! dpkg -l auditd >/dev/null 2>&1; then
  log "restoring CIS 4.1.1.1: apt-get install -y auditd audispd-plugins"
  DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null 2>&1 || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y auditd audispd-plugins >/dev/null 2>&1 || log "  (auditd install returned non-zero, check apt logs)"
else
  log "CIS 4.1.1.1 already compliant: auditd installed"
fi

# -- CIS 4.2.3: restore syslog perms ----------------------------------------
if [[ -f /var/log/syslog ]]; then
  log "restoring CIS 4.2.3: chown root:adm /var/log/syslog && chmod 0640"
  chown root:adm /var/log/syslog 2>/dev/null || chown root:root /var/log/syslog
  chmod 0640 /var/log/syslog
fi

# -- CIS 5.1.1: start cron --------------------------------------------------
log "restoring CIS 5.1.1: systemctl start cron"
systemctl start cron 2>&1 | tee -a "$LOGFILE" || log "  (systemctl start cron returned non-zero)"

# -- CIS 5.2.1: restore sshd_config perms -----------------------------------
log "restoring CIS 5.2.1: chown root:root /etc/ssh/sshd_config && chmod 0600"
chown root:root /etc/ssh/sshd_config
chmod 0600 /etc/ssh/sshd_config

# -- CIS 5.2.2: restore SSH host key perms ----------------------------------
log "restoring CIS 5.2.2: chown root:root /etc/ssh/ssh_host_rsa_key && chmod 0600"
chown root:root /etc/ssh/ssh_host_rsa_key
chmod 0600 /etc/ssh/ssh_host_rsa_key

# -- CIS 6.1.2: restore /etc/passwd perms -----------------------------------
log "restoring CIS 6.1.2: chown root:root /etc/passwd && chmod 0644"
chown root:root /etc/passwd
chmod 0644 /etc/passwd

# -- CIS 6.1.5: restore /etc/shadow perms -----------------------------------
log "restoring CIS 6.1.5: chown root:shadow /etc/shadow && chmod 0640"
chown root:shadow /etc/shadow 2>/dev/null || chown root:root /etc/shadow
chmod 0640 /etc/shadow

# -- CIS 6.2.5: delete the rootback account ---------------------------------
if id rootback >/dev/null 2>&1; then
  log "restoring CIS 6.2.5: userdel rootback"
  userdel rootback 2>&1 | tee -a "$LOGFILE" || log "  (userdel rootback returned non-zero)"
else
  log "CIS 6.2.5 already compliant: rootback does not exist"
fi

log "=== RESTORE RUN COMPLETE ==="
echo
echo "Done. Wait one osquery distributed_interval and watch the Fleet UI flip"
echo "the affected policies back to passing."
