# Security Policy

## Scope

This repository contains tooling, configuration, and architectural
decision records for an enterprise Fleet Device Management
deployment. The configurations, osquery queries, CIS benchmark
policies, and demo scripts here are designed to be read for
understanding and adapted for production use, not deployed verbatim.

If you are looking for Fleet itself, see
[fleetdm/fleet](https://github.com/fleetdm/fleet) and their
[security policy](https://github.com/fleetdm/fleet/security).

## Reporting issues

### Credential or secret accidentally committed

If you find a real credential or secret in this repo (an `.env`
file with real values, an API token, a private key, a cert, etc.),
please open a [private security advisory](https://github.com/badbread/bread-fleet/security/advisories/new)
rather than a public issue. Direct attention reduces the time
between disclosure and rotation.

### Vulnerability in custom code

The Compliance Troubleshooter, the Zero-Day Pipeline, the demo
scripts under `demos/`, and `gitops/apply.sh` are the executable
code in this repo. Bugs in how they parse external input, handle
authentication, or interact with Fleet's API are in scope. Open an
issue with the `security` label.

### CIS benchmark policy mistakes

If a policy under `gitops/default.yml` misattributes a CIS section
number, has a query that produces false positives or false
negatives, or doesn't match the control text, open an issue with
the `cis-benchmark` label and link the specific CIS document
section. Getting these right matters because the policies are the
substrate the rest of the tooling depends on.

## Out of scope

- The `.env.example` placeholder values, which are clearly not
  real credentials
- RFC1918 internal IP addresses in documentation, which are not
  routable from the internet
- Documented design tradeoffs in the ADRs, which are explicit
  decisions and not accidents
- Pinned dependency versions, which are updated on a deliberate
  cadence rather than automatically
- Missing enterprise ingress controls (WAF, rate limiting,
  enterprise SSO) that would exist in a production deployment
  but are out of scope for the demonstration shape
