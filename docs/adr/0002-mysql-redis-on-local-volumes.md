# ADR-0002: MySQL and Redis on local Docker volumes, not NFS bind mounts

## Status

Accepted (supersedes the data-storage section of ADR-0001)

## Context

ADR-0001 originally called for the entire Fleet stack, including
MySQL and Redis state, to live on a NAS-mounted bind path under the
runtime directory. The rationale was the disposable-host property:
rebuild the Docker host, `docker compose up -d`, done.

When the stack was first brought up against a Synology NAS export,
both MySQL and Redis entered immediate restart loops with:

```
chown: changing ownership of '/var/lib/mysql': Operation not permitted
chown: .: Operation not permitted
```

Root cause: the Synology NFS share is exported with `root_squash`
(the DSM default and the right default for almost any shared
storage). The MySQL 8.0 image's entrypoint runs as root inside the
container and tries to `chown 999:999 /var/lib/mysql` so the
in-container `mysql` user can read its own data directory. NFS
squashes that root request to `nobody`, the chown fails, the
entrypoint aborts, the container exits, Compose marks it unhealthy,
and the restart loop begins. Redis on Alpine has the same behavior.

## Decision

Move MySQL, Redis, and Fleet's vulnerability feed cache onto **named
Docker volumes** that live on the Docker host's local disk at
`/var/lib/docker/volumes/`. Do not bind-mount any of them from the
NFS-mounted runtime directory.

The compose file declares the volumes explicitly so they appear in
`docker volume ls` with predictable names:

```yaml
volumes:
  fleet-mysql-data:
    name: fleet-mysql-data
  fleet-redis-data:
    name: fleet-redis-data
  fleet-vulndbs:
    name: fleet-vulndbs
```

The compose file itself, `.env.example`, and the runtime `.env` all
still live on NAS-mounted storage. Only the persistent database and
cache state moves off NAS.

## Alternatives Considered

1. **Disable `root_squash` on the NAS export.** Solves the chown
   error but is a blanket relaxation of NFS security for the entire
   share. Every other container workload on the same share would
   then run effectively as host root over NFS. Wrong tradeoff: a
   single container's quirky entrypoint should not weaken
   authentication for a shared storage layer that backs other
   workloads.

2. **Set `user: "<uid>:<gid>"` in the compose service.** Skips the
   entrypoint chown by running the container as a UID that already
   owns the data directory. Works for some images but is fragile
   for MySQL 8.0 in particular: the official entrypoint script has
   multiple chown sites and assumes root context. Maintenance burden
   each time the image bumps majors.

3. **Run MySQL and Redis as native services on the host.** Move them
   out of Compose entirely. Rejected because it splits the stack
   across two management planes and makes the disposable-host
   property even harder to maintain.

4. **A separate NFS export with different mount options.** Add a
   second share specifically for container databases with looser
   squash rules. Possible, but adds another moving piece, still
   leaves the database I/O performance concerns of NFS unaddressed,
   and creates a confusing "which share for which container?"
   problem the next time someone reads the layout.

## Tradeoffs

- **The disposable-host property is now partial.** Rebuilding the
  Docker host loses the MySQL database unless it was backed up
  first. The compose file and the gitignored `.env` still live on
  NAS and survive, so the *config* is portable. The *data* is not.
- **An explicit backup requirement now exists.** Without local
  volumes living on NAS, scheduled `mysqldump` to off-host storage
  is no longer optional. It is the only path back from a host
  failure. The current state of this requirement is "documented as
  pending, not implemented."
- **Named volumes are less discoverable than bind mounts.** Someone
  reading the runtime directory layout will not see where the data
  lives. Documented in compose comments and in this ADR to
  partially compensate.
- **Local-disk I/O is faster than NFS for MySQL.** Not a tradeoff so
  much as an upside the NFS approach was costing us anyway.

## At Enterprise Scale

The Compose-volume model does not exist in a real production
deployment. The decisions look like:

- **Managed database service.** RDS for MySQL or equivalent. Backups
  are automatic, point-in-time recovery is automatic, multi-AZ
  failover is automatic, the disposable-host question becomes "stand
  up a new Fleet container, point it at the same RDS endpoint."
- **Managed cache.** Elasticache or MemoryDB for Redis. Fleet treats
  Redis as ephemeral, so failover semantics are forgiving and a
  cluster mode replica is enough.
- **NFS is not in the picture at all.** Container databases live on
  managed storage; container config lives in object storage or in
  the Helm chart values. The "NFS root_squash vs container chown"
  problem this ADR exists to document is a single-host trap that
  goes away when the topology is right.
- **Backups are tested, not just configured.** Automated quarterly
  restore drills against a staging Fleet, with the restore time
  measured against an SLO. Confidence that backups work matters
  more than confidence that backups exist.
