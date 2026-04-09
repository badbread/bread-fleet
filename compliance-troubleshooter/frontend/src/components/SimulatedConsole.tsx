// Simulated terminal window showing a remediation script running.
// Lines appear one by one with a typing delay to mimic real execution.
// Ends with a disclaimer explaining the simulation.

import { useState, useEffect, useRef } from "react";

interface Props {
  remediationId: string;
  hostname: string;
  onComplete: () => void;
}

// Simulated output per remediation type.
const SCRIPTS: Record<string, string[]> = {
  cramfs_disable: [
    "$ sudo modprobe -r cramfs",
    "$ echo 'install cramfs /bin/true' | sudo tee /etc/modprobe.d/cramfs.conf",
    "install cramfs /bin/true",
    "$ lsmod | grep cramfs",
    "(no output — module unloaded)",
    "",
    "✓ cramfs kernel module disabled successfully.",
  ],
  bootloader_perms: [
    "$ sudo chmod 600 /boot/grub/grub.cfg",
    "$ sudo chown root:root /boot/grub/grub.cfg",
    "$ stat -c '%a %U:%G' /boot/grub/grub.cfg",
    "600 root:root",
    "",
    "✓ Bootloader config permissions tightened to owner-only.",
  ],
  ipv4_forward_disable: [
    "$ sudo sysctl -w net.ipv4.ip_forward=0",
    "net.ipv4.ip_forward = 0",
    "$ echo 'net.ipv4.ip_forward = 0' | sudo tee /etc/sysctl.d/99-no-forward.conf",
    "net.ipv4.ip_forward = 0",
    "$ sysctl net.ipv4.ip_forward",
    "net.ipv4.ip_forward = 0",
    "",
    "✓ IPv4 packet forwarding disabled.",
  ],
  auditd_install: [
    "$ sudo apt-get update -qq",
    "Fetched 2,847 kB in 1s (2,847 kB/s)",
    "$ sudo apt-get install -y auditd audispd-plugins",
    "Reading package lists...",
    "Setting up auditd (1:3.1.2-2.1) ...",
    "Setting up audispd-plugins (1:3.1.2-2.1) ...",
    "$ sudo systemctl enable --now auditd",
    "Created symlink /etc/systemd/system/multi-user.target.wants/auditd.service",
    "",
    "✓ auditd installed and running.",
  ],
};

const DEFAULT_SCRIPT = [
  "$ sudo /opt/fleet/remediate.sh",
  "Running automated fix...",
  "",
  "✓ Remediation applied.",
];

export default function SimulatedConsole({ remediationId, hostname, onComplete }: Props) {
  const [lines, setLines] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const script = SCRIPTS[remediationId] || DEFAULT_SCRIPT;

  useEffect(() => {
    let i = 0;
    const timer = setInterval(() => {
      if (i < script.length) {
        setLines((prev) => [...prev, script[i]]);
        i++;
      } else {
        clearInterval(timer);
        setDone(true);
      }
    }, 400);
    return () => clearInterval(timer);
  }, [script]);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [lines]);

  return (
    <div className="mt-4 rounded-lg overflow-hidden border border-neutral-200">
      {/* Title bar */}
      <div className="bg-neutral-800 px-4 py-2 flex items-center gap-2">
        <span className="w-3 h-3 rounded-full bg-[#E03E3E]" />
        <span className="w-3 h-3 rounded-full bg-[#CB912F]" />
        <span className="w-3 h-3 rounded-full bg-[#0F7B6C]" />
        <span className="ml-3 text-[12px] text-neutral-300 font-mono">
          {hostname} — remediation
        </span>
      </div>

      {/* Console output */}
      <div
        ref={scrollRef}
        className="bg-neutral-900 px-4 py-3 font-mono text-[12px] leading-relaxed max-h-[200px] overflow-y-auto"
      >
        {lines.map((line, i) => (
          <div
            key={i}
            className={
              line.startsWith("$")
                ? "text-[#6CB6FF]"
                : line.startsWith("✓")
                  ? "text-[#3FB950]"
                  : "text-neutral-400"
            }
          >
            {line || "\u00A0"}
          </div>
        ))}
        {!done && (
          <span className="text-neutral-400 animate-pulse">▊</span>
        )}
      </div>

      {/* Disclaimer */}
      {done && (
        <div className="bg-neutral-50 border-t border-neutral-200 px-4 py-3">
          <p className="text-[12px] text-neutral-500 leading-relaxed">
            <span className="font-semibold text-neutral-700">Simulated execution.</span>{" "}
            Fleet Free does not expose the script execution API to service accounts.
            In production (Fleet Premium), this runs as a real shell script dispatched
            through Fleet's agent and the output streams back live. The remediation
            registry and API architecture are identical — only the dispatch layer changes.
          </p>
          <button
            onClick={onComplete}
            className="mt-2 text-[12px] text-accent hover:underline font-medium"
          >
            Re-check compliance →
          </button>
        </div>
      )}
    </div>
  );
}
