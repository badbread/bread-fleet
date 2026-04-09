# ADR-0003: LAN-only ingress with documented at-scale tunnel design

## Status

Accepted (supersedes the ingress section of ADR-0001)

## Context

ADR-0001 called for Cloudflare Tunnel as the ingress path for Fleet
with two stated goals: a public HTTPS endpoint with a real cert so
devices could enroll from anywhere, and "no published ports" as a
zero-trust principle.

The `cloudflared` sidecar was scaffolded and the tunnel creation
flow was started. At that point the design hit two real problems
worth examining instead of just powering through.

**First**, every test device in this deployment lives on the same
trusted network as the Docker host. The Linux test VM, the OpenCore
macOS test VM, and the operator workstation are all behind the same
perimeter firewall. There is no remote-enrollment scenario in scope.
The tunnel was solving a problem the deployment did not have.

**Second**, Fleet serves its entire HTTP surface on a single port.
The admin web UI, the REST API, the osquery TLS plugin endpoints,
and the MDM endpoints all share `:8080`. Exposing the tunnel
without path restriction would put the admin UI on the public
internet. Fixing that requires either path-restricted public
hostnames in the Cloudflare dashboard (which works but is fiddly)
or a Cloudflare Access policy on admin paths (which requires SSO
configuration). Both are real work, and both exist to mitigate a
problem that does not exist on a trusted network.

The "no published ports" line from ADR-0001 was a dogmatic read of
the zero-trust playbook. The perimeter firewall already blocks
inbound from WAN. The threat model for a single-tenant deployment
on a trusted network does not benefit from forcing all admin
traffic through an outbound tunnel versus binding to `0.0.0.0:8080`
locally.

## Decision

Drop Cloudflare Tunnel from the default deployment. Fleet binds
`0.0.0.0:8080` on the Docker host and is reachable on the trusted
network at `http://<docker-host-ip>:8080`.

The `cloudflared` sidecar stays in the compose file behind a
`tunnel` profile (`profiles: ["tunnel"]`), so a plain
`docker compose up -d` does not start it but `docker compose --profile tunnel up -d`
does. The runtime `.env` documents the `CLOUDFLARED_TOKEN` variable
as optional. The path-restricted hostname design is documented in
this ADR so anyone enabling the profile knows what dashboard
configuration to add.

## Alternatives Considered

1. **Keep the Cloudflare Tunnel as the default ingress.** Original
   plan from ADR-0001. Rejected because of the two problems above:
   it solves a remote-access problem the deployment doesn't have,
   and it forces an immediate decision about admin-UI exposure that
   was not in the critical path.

2. **Self-signed certificate via reverse proxy.** Caddy or Traefik
   in front of Fleet, terminating TLS with a self-signed cert.
   Acceptable, but the self-signed CA has to be installed on every
   client device that would connect. For Linux hosts using
   `--insecure` flag at the agent level this is OK, for macOS MDM
   it does not work because Apple's MDM client refuses self-signed
   profile delivery URLs. Defers the same decision and adds an
   extra moving piece.

3. **Local CA via mkcert or similar.** Generate a private CA, sign
   a cert for `fleet.example.local`, install the root CA on every
   test host. Solves the reverse-proxy fragility but adds a CA
   lifecycle to manage. Worth doing if there were many devices,
   not worth doing for two test VMs.

4. **HTTP only, no tunnel, no TLS at all.** What the deployment
   actually does today. Acceptable for the trusted-network scope,
   blocked for macOS MDM enrollment which strictly requires HTTPS.
   The "macOS MDM is blocked" item is a known constraint, not a
   surprise.

## Tradeoffs

- **macOS MDM enrollment is blocked.** Apple's MDM protocol
  requires HTTPS for the profile delivery URL. The current LAN HTTP
  setup cannot deliver MDM profiles to macOS or iOS devices. The
  Fleet stack, the GitOps flow, and the osquery + CIS policy work
  all proceed without HTTPS, but the MDM-specific work is parked
  until an HTTPS strategy is chosen.
- **No remote-enrollment story today.** A device that leaves the
  trusted network cannot reach Fleet to check in until it returns.
  For a deployment where every device is always on the trusted
  network this is fine; for a real fleet with traveling laptops it
  is not.
- **The admin UI is on the trusted network, not behind any auth
  layer beyond Fleet's own login.** A misconfigured Wi-Fi guest
  network with the wrong VLAN could expose it. The mitigation is
  network segmentation done correctly, which is upstream of this
  decision.

## At Enterprise Scale

The default ingress at production scale is the path-restricted
Cloudflare Tunnel design that this ADR exists to document. The
shape:

In the Cloudflare Zero Trust dashboard, register multiple public
hostnames against the same tunnel, each with a path regex, all
pointing at `http://fleet:8080` on the `fleet-net` bridge:

```
fleet.example.com  ^/api/osquery/        -> http://fleet:8080
fleet.example.com  ^/api/fleet/orbit/    -> http://fleet:8080
fleet.example.com  ^/api/fleet/device/   -> http://fleet:8080
fleet.example.com  ^/mdm/apple/          -> http://fleet:8080
fleet.example.com  ^/api/mdm/apple/      -> http://fleet:8080
fleet.example.com  ^/mdm/microsoft/      -> http://fleet:8080
fleet.example.com  ^/api/mdm/microsoft/  -> http://fleet:8080
```

Anything not matching any rule is rejected at the Cloudflare edge
with a 404. The admin UI at `/`, the admin REST API at
`/api/latest/fleet/*`, and the login page are never publicly
reachable through this hostname.

For belt-and-suspenders protection, a separate hostname like
`fleet-admin.example.com` is created **without** path restriction
and gated by a Cloudflare Access policy requiring SSO. Engineers
who need the admin UI hit that hostname; agents and MDM clients
hit the path-restricted public hostname.

mTLS is the next layer: the agent endpoints can require client
certificates issued by an internal CA, so even if a path
allowlist had a hole, only devices with a valid client cert can
talk to Fleet at all. Cloudflare supports this natively.

The path allowlist has to be re-verified against each Fleet major
release because new endpoints get added (Fleet Desktop, the orbit
updater, Windows MDM, future Apple MDM features). A monthly
verification job that diffs the live Fleet routes against the
allowlist is a small piece of automation worth writing.
