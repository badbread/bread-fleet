# demos/

Scripts that make this Fleet deployment demo-able. Each subdirectory
is a self-contained scenario with its own README, scripts, and
safety gates.

## Current scenarios

| Scenario | Purpose |
|---|---|
| [`cis-compliance/`](cis-compliance/) | Break CIS Ubuntu 24.04 policies on purpose, watch the Fleet UI turn red, then restore. For regression-testing that the policies catch real violations, and for live-demoing Fleet's compliance dashboard. |

## Safety philosophy

Every script in this directory that changes system state:

1. **Refuses to run as non-root.** If you forget `sudo`, the script
   exits immediately with a usage message.
2. **Requires a sentinel file on disk** acknowledging you know this
   is a disposable test host. The sentinel path is documented in each
   scenario's README.
3. **Requires an explicit `--confirm` argument.** Typos like `./break`
   without the flag print the warning banner and exit without doing
   anything.
4. **Logs every action to a scenario-specific log** so the matching
   restore script can reverse them and so you have an audit trail.

The goal is that nobody, including me months from now, can accidentally
apply these scripts to a host that matters. Three independent layers
of "yes I really mean it."

## Golden rule

**These scripts are for throwaway VMs. Never run them on a host you
care about.** Some of the CIS breaks in `cis-compliance/break.sh`
leave the system in a state where sshd may refuse to start on the
next restart, /etc/shadow may be world-readable, and a second UID-0
account may exist. All reversible via the matching `restore.sh`,
but all catastrophic if forgotten and the VM is then reused for
anything real.
