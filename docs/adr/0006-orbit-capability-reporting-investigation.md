# ADR-0006: Orbit capability reporting limits automated remediation

## Status

Accepted

## Context

The Compliance Troubleshooter (ADR-0005) includes a remediation
registry that maps specific failing policies to automated fixes via
Fleet's `/api/latest/fleet/scripts/run/sync` endpoint. The first
automated remediation in scope was `auditd_install`, which runs
`apt-get install -y auditd` on a Linux host by dispatching a shell
script through Fleet.

Fleet's script execution API enforces two preconditions on the
server side:

1. `scripts_disabled: false` in Fleet's server config (which the
   GitOps-applied `default.yml` sets).
2. The target host's orbit agent must have reported that it
   supports script execution via the `scripts_enabled` capability.
   Fleet stores this in the host record.

Condition 1 is satisfied globally. Condition 2 is per-host and
depends on orbit talking to Fleet via the orbit-specific API
endpoints (`/api/fleet/orbit/config`, `/api/fleet/orbit/enroll`,
etc.). orbit reports its capabilities through headers on those
calls.

When the troubleshooter first tried to invoke the remediation
against a test host, Fleet returned:

```
422 Unprocessable Entity
{
  "errors": [{
    "name": "base",
    "reason": "Couldn't run script. To run a script, deploy the fleetd agent with --enable-scripts."
  }]
}
```

The message is misleading. The fleetd agent WAS deployed with
`--enable-scripts` (via `fleetctl package --enable-scripts`). The
actual failure is that Fleet has never learned the host supports
scripts because orbit's capability-reporting path is broken.

## Investigation summary

The full debugging sequence, captured here so the next person
doesn't repeat it:

1. **Verified orbit was running and osquery was reporting.** Host
   status `online`, osquery version populated, policies evaluating.
   Only the orbit-specific fields (`orbit_version`, `scripts_enabled`,
   `last_mdm_enrolled_at`) were `None`.

2. **Confirmed the .deb was built with `--enable-scripts`.** Running
   `fleetctl package --enable-scripts` produced a package containing
   `/etc/default/orbit` with `ORBIT_ENABLE_SCRIPTS=true`. Verified
   the file was installed correctly on the host.

3. **Traced the root cause to orbit's HTTPS requirement.** orbit's
   own backend calls (for capability reporting) hardcode HTTPS for
   their URL scheme, regardless of the scheme in `ORBIT_FLEET_URL`.
   Fleet was running on plain HTTP per ADR-0003. orbit's initial
   enroll call to `/api/fleet/orbit/config` failed with a bare
   `https:///api/fleet/orbit/config` request (no host because
   orbit's URL builder used an empty FLEET_URL) and then later
   with TLS handshake errors against an HTTP server.

4. **Switched Fleet to a self-signed cert on the LAN.** Generated a
   self-signed cert valid for `fleet.lan`, `localhost`, and a few
   DNS aliases. Mounted it into the Fleet container and set
   `FLEET_SERVER_TLS=true`, `FLEET_SERVER_CERT`, `FLEET_SERVER_KEY`
   via environment variables. Fleet now serves HTTPS on port 8080
   with the self-signed cert. Verified with
   `curl -k https://fleet.lan:8080/healthz`.

5. **Updated orbit environment on both test hosts to use HTTPS.**
   Changed `ORBIT_FLEET_URL` from `http://fleet.lan:8080` to
   `https://fleet.lan:8080`. Initially set `ORBIT_INSECURE=true`
   to bypass cert verification, which orbit rejected with
   `"insecure and fleet-certificate may not be specified together"`.
   Removed `ORBIT_INSECURE` and instead set
   `ORBIT_FLEET_CERTIFICATE=/etc/fleet.crt`, pinning orbit's trust
   to the self-signed cert directly.

6. **orbit restarted cleanly** with the pinned cert. Logs showed
   osqueryd connecting directly to `https://fleet.lan:8080` using
   `--tls_server_certs /etc/fleet.crt`. No more fallback TLS
   proxy. No TLS errors.

7. **Deleted the stale orbit node key** (`/opt/orbit/secret-orbit-node-key.txt`)
   to force a fresh enrollment. orbit re-enrolled successfully and
   wrote a new 32-byte node key. Fleet's access log confirmed:

   ```
   POST /api/fleet/orbit/enroll
   host_id=2 identifier=51335dcf-... hostname=lab-linux-02
   ```

   Response: 200, 14.7ms. Fleet logged a warn about overwriting the
   existing host record for the same UUID (expected, because the
   host was previously enrolled through a different code path).

8. **After successful enrollment, orbit stopped calling Fleet's
   orbit-specific endpoints entirely.** No `POST /api/fleet/orbit/config`,
   no capability headers, no subsequent orbit traffic visible in
   Fleet's logs over multiple minutes. osquery kept working (policies
   evaluated, distributed queries responded), but orbit's internal
   `capabilities checker` goroutine never made a single observable
   HTTP call after enrollment.

9. **Fleet's host record never updated.** `orbit_version`,
   `scripts_enabled`, `last_mdm_checked_in_at`, and
   `fleet_desktop_version` all remained `None` even though the
   enrollment clearly succeeded.

10. **Script execution API continued to return the "deploy with
    --enable-scripts" error** because Fleet's check is against the
    host record's `scripts_enabled` column, which was never
    populated.

The investigation ran ~90 minutes. I stopped at step 10 because
the next diagnostic step would require reading orbit's Go source
to understand why the `capabilities checker` goroutine was silent.
That investment is disproportionate to the value of getting one
button working in a demo, and the workaround (manual remediation
path) preserves the demo's core value.

## Decision

**Mark the `auditd_install` remediation in the Compliance
Troubleshooter as manual-only** by setting
`automated_remediation_id: None` in the translator's static
fallback for `CIS 4.1.1.1 auditd package installed`. The UI shows
manual fix steps that a support person can walk the user through
instead of a Fix button.

The remediation registry in `backend/src/remediation.py` still
contains the `_auditd_install` handler. The entry stays in the
registry as a **proof-of-concept** and as the implementation that
will be re-enabled the moment orbit's capability reporting is
fixed. The code path is live, just not linked from the UI.

Every other part of the Compliance Troubleshooter is unaffected.

## Alternatives Considered

1. **Read orbit's Go source and find the bug.** High time cost,
   uncertain outcome, specific to a version of orbit that the
   project will replace eventually. Rejected as not worth the
   investment for a demo deployment.

2. **Upgrade Fleet and orbit to the latest version.** Might include
   a fix for this path. Risk of introducing new issues mid-demo.
   Deferred as "try later if the demo needs the live remediation."

3. **Use Cloudflare Tunnel for Fleet so orbit talks to a
   certificate signed by a public CA.** Works around the self-
   signed cert question entirely but pushes Fleet's agent surface
   onto the public internet, which the operator explicitly did not
   want. Rejected per the ingress decision.

4. **Run a local reverse proxy (Caddy, nginx) with a self-signed
   cert in front of Fleet instead of Fleet's native TLS.** Same end
   result from orbit's perspective because orbit still trusts the
   self-signed cert. Does not address the deeper issue that orbit's
   capability reporting goroutine is silent. Would have hit the
   same dead end.

5. **Use Fleet's web UI manually to verify the host supports
   scripts.** There is no such UI affordance; Fleet derives
   `scripts_enabled` from what orbit reports. Nothing manual to
   check here.

6. **Accept the script execution API failure and ship a broken
   Fix button.** The button would show the literal "deploy with
   --enable-scripts" error to support staff, which is both wrong
   and confusing. Rejected because it presents a worse UX than
   manual-only.

## Tradeoffs

- **The Compliance Troubleshooter's headline "one-click fix"
  feature is reduced to manual fix steps.** The demo story becomes
  "plain English translation + severity scoring + escalation
  routing + manual fix instructions + audit log" instead of "one
  click fixes a device in front of you." Still strong, not as
  strong.

- **The remediation registry is now a stub for one entry.** The
  `auditd_install` handler exists but is unreferenced from the
  live translator path. Adds a small amount of dead code that
  proves the architecture and will come back to life later.

- **Debugging time lost.** ~90 minutes on an issue that is a
  specific quirk of orbit 1.54.0 with self-signed certs and the
  particular enroll-then-silent failure mode. Time I could have
  spent on the Zero-Day Pipeline or the Security Posture
  Dashboard. Recording it here at least means the time produces
  documentary value.

- **The Fleet server is now TLS-terminated on the LAN** even
  though the original orbit fix it enabled never worked. Not a
  regression: self-signed HTTPS on the LAN is marginally more
  secure than plain HTTP (prevents passive ARP-layer observers
  from reading admin session cookies) and costs nothing.

## At Enterprise Scale

This specific bug would never hit a production deployment for
three reasons:

1. **Production Fleet runs behind real TLS from a real CA.** Either
   a Cloudflare tunnel with Cloudflare-managed certs, a Let's
   Encrypt cert on a reverse proxy, or an internal CA the orbit
   agents trust. Self-signed cert + agent trust-pinning is a
   homelab-only pattern.

2. **Production orbit packages are built for that specific Fleet
   deployment** via the same CI pipeline that generates the Fleet
   instance. The `fleetctl package` flags are part of the
   deployment spec. If capability reporting breaks, it's caught in
   a CI smoke test before the package ships.

3. **Production Fleet typically has the full MDM stack enabled**,
   which orbit needs to report capabilities for anyway. The
   orbit-config endpoint is exercised on every deployment. A
   silent-failure-after-enrollment bug would show up within
   minutes of the first host rolling out, not hours into a
   debugging session.

The Compliance Troubleshooter's automated remediation path in
production would:

- Use Fleet's script execution API (same endpoint), but pre-flight
  check `scripts_enabled` on the host record before showing the Fix
  button. If `scripts_enabled != true`, the button is hidden and
  the card shows manual steps automatically.
- Gate the automated fix behind a per-tier approval workflow
  (tier-1 support can click single-host fixes, bulk fixes require
  tier-2 sign-off).
- Log every remediation attempt to the audit stream in real time,
  not just the JSONL file used in the MVP.
- Have an eval suite that tests each registered remediation against
  a staging Fleet with a known-good set of hosts, so a broken
  remediation path is caught before it reaches support.

Those are out of scope for the MVP but they're what closes the
loop between "I built the thing" and "the thing is production-
ready." Captured here so there's a trail back to what would need
to happen at real scale.
