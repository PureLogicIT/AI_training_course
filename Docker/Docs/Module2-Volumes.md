# Module 2: Volumes
> Subject: Docker | Difficulty: Intermediate | Estimated Time: 135 minutes

## Objective

After completing this module, you will be able to explain the three Docker storage mount types — named volumes, bind mounts, and tmpfs mounts — and select the appropriate type for a given scenario. You will create, inspect, list, and remove volumes using the full Docker volume CLI (`docker volume create`, `docker volume ls`, `docker volume inspect`, `docker volume rm`, `docker volume prune`). You will share a volume between multiple containers, resolve file permission and ownership mismatches caused by UID/GID differences between the host and container, back up and restore a named volume using a temporary container, and configure all three mount types in a `compose.yaml` file using both short and long syntax — including named volumes, external volumes, and bind mounts.

## Prerequisites

- Completed Module 1: Basics — you should be comfortable with `docker run`, `docker ps`, `docker exec`, and the concept of container lifecycle
- Docker Engine 27 or later installed (verify with `docker --version`; current stable release is Docker Engine 29.3.1)
- Basic familiarity with Linux file permissions (`chmod`, `chown`, UID/GID concepts)
- Ability to create and edit text files from the command line

## Key Concepts

### Why Containers Need External Storage

Every running container has a thin, writable layer on top of its read-only image layers. When the container process writes a file — saving a database record, generating a log, uploading a user file — that write lands in the writable layer. This layer is tied to the container's lifetime: the moment you run `docker rm`, the writable layer and everything in it is permanently deleted.

This is intentional design. Containers are meant to be ephemeral and replaceable. You should be able to stop a container, pull an updated image, and start a new container without any manual cleanup. But almost every real application has data that must outlive its container: database files, user uploads, configuration that changes at runtime, application logs that must be shipped to an aggregator.

Docker solves this with three distinct mount types that all inject external storage into a container at a specific path. The container process does not need to know where its data lives on the host — it just writes to `/var/lib/postgresql/data` or `/app/uploads` and the mount silently routes those writes to the appropriate location.

```
Without a mount:                 With a named volume:
┌───────────────────┐            ┌───────────────────┐
│    Container      │            │    Container      │
│  /var/lib/pg/data │            │  /var/lib/pg/data │◄──── pg-data volume
│  (writable layer) │            │                   │      (persists on host)
│  DELETED on rm    │            │  not in writable  │
└───────────────────┘            │  layer at all     │
                                 └───────────────────┘
```

### Named Volumes

A named volume is a storage unit managed entirely by Docker. You give it a name; Docker decides where to store it on the host filesystem (typically `/var/lib/docker/volumes/<name>/_data` on Linux). You never need to know or care about that path — Docker manages it.

Named volumes are the recommended storage type for almost all production data. They work identically on Linux, macOS, and Windows regardless of how Docker Desktop or Docker Engine handles the underlying storage. They can be backed up, inspected, and moved without touching the host filesystem directly. When you mount an empty named volume into a container directory that already has files in the image, Docker automatically seeds the volume with those files — a useful behaviour that bind mounts do not provide.

```bash
# Create a named volume explicitly
docker volume create app-data

# Mount it into a container at /app/data
docker run -d --name myapp \
  -v app-data:/app/data \
  myimage:1.0.0

# Equivalent using the preferred --mount syntax
docker run -d --name myapp \
  --mount type=volume,src=app-data,dst=/app/data \
  myimage:1.0.0
```

If you reference a volume name in `-v` that does not exist yet, Docker creates it automatically before starting the container. This implicit creation is convenient but can also silently create orphaned volumes if you mistype a volume name — prefer explicit `docker volume create` in production scripts.

### Bind Mounts

A bind mount takes a file or directory that already exists on the host and projects it into a container at a specified path. Unlike named volumes, bind mounts have no Docker-managed lifecycle — Docker simply exposes the host path you specify.

Bind mounts are the correct tool for development workflows where you want to edit source code on the host and have those changes reflected immediately inside the running container, without rebuilding the image. They are also appropriate for injecting read-only configuration files — such as Nginx configs or TLS certificates — into a container at runtime.

```bash
# Mount the current directory (source code) into the container for live editing
docker run -d --name dev-server \
  --mount type=bind,src="$(pwd)/src",dst=/app/src \
  myapp:dev

# Inject a read-only configuration file
docker run -d --name web \
  --mount type=bind,src="$(pwd)/nginx.conf",dst=/etc/nginx/nginx.conf,readonly \
  nginx:1.27-alpine

# Short -v syntax: host-path:container-path[:options]
docker run -d --name web \
  -v "$(pwd)/nginx.conf":/etc/nginx/nginx.conf:ro \
  nginx:1.27-alpine
```

The `--mount` flag is explicit about what type of mount is being created, which prevents a common mistake with `-v`: if the host path does not exist, `-v` silently creates a directory at that path (which is rarely what you want), while `--mount` returns an error and stops the container from starting.

Bind mounts make containers host-dependent: a `compose.yaml` that binds `/home/alice/project` to a container will fail on any machine where that path does not exist. They also expose the host filesystem to the container process, which has security implications — if the container is compromised, the attacker has write access to whatever the bound path contains.

### tmpfs Mounts

A tmpfs mount allocates storage from the host machine's RAM rather than its disk. Data written to a tmpfs mount is never persisted to any disk and disappears the moment the container stops. tmpfs mounts are only available on Linux; they are not supported on Docker Desktop for Mac or Windows.

tmpfs mounts are appropriate for two scenarios. First, highly sensitive data — session tokens, decrypted secrets, one-time credentials — that must never touch disk. Second, scratch space for high-throughput applications that need fast temporary storage without the overhead of the container's overlay filesystem.

```bash
# Mount a 128 MB tmpfs at /tmp/scratch in the container
docker run -d --name fast-worker \
  --mount type=tmpfs,dst=/tmp/scratch,tmpfs-size=134217728 \
  myworker:1.0.0

# Using the --tmpfs flag shorthand (Linux-only, does not work for swarm services)
docker run -d --name fast-worker \
  --tmpfs /tmp/scratch:size=128m,mode=1777 \
  myworker:1.0.0
```

The `tmpfs-size` option is specified in bytes in `--mount` syntax. Setting `tmpfs-mode` lets you control file permissions on the mount (in octal); the default is `1777` (world-writable with sticky bit), which is correct for `/tmp`-style scratch space. Because tmpfs mounts cannot be shared between containers, they are only suitable for single-container temporary state.

### Volume CLI Commands

Docker provides a dedicated management group for volumes: `docker volume`. Every volume operation flows through these five subcommands.

```bash
# Create a volume with the default local driver
docker volume create my-volume

# Create a volume with a label for identification
docker volume create --label env=production --label app=api api-data

# Create a volume using the local driver with NFS backing
docker volume create \
  --driver local \
  --opt type=nfs \
  --opt o=addr=192.168.1.10,rw \
  --opt device=:/exports/shared \
  nfs-shared

# List all volumes
docker volume ls

# List only volumes with a specific label
docker volume ls --filter label=env=production

# Inspect a volume — returns JSON with driver, mount point, labels, and options
docker volume inspect my-volume

# Remove a specific volume (fails if any container is using it)
docker volume rm my-volume

# Remove multiple volumes at once
docker volume rm volume-a volume-b volume-c

# Remove all anonymous volumes not used by any container
docker volume prune

# Remove ALL unused volumes — named and anonymous — not used by any container
docker volume prune --all

# Skip the confirmation prompt in scripts
docker volume prune --all --force
```

The output of `docker volume inspect` is JSON and contains the host-side mount point, which is useful for direct inspection or backup operations:

```bash
docker volume inspect my-volume
```

```json
[
    {
        "CreatedAt": "2026-04-04T10:00:00Z",
        "Driver": "local",
        "Labels": {},
        "Mountpoint": "/var/lib/docker/volumes/my-volume/_data",
        "Name": "my-volume",
        "Options": {},
        "Scope": "local"
    }
]
```

A key distinction in `docker volume prune`: without `--all`, only **anonymous** volumes (those with no name, created automatically by `-v /container/path`) are removed. Named volumes you created explicitly are left alone. To remove all unused named volumes too, you must pass `--all`.

### Volume Drivers and Plugins

Every Docker volume is created by a volume driver. The built-in `local` driver stores volume data on the host's local filesystem. It also supports mounting network filesystems — NFS and CIFS/Samba — by passing driver options directly, without installing any additional plugin.

```bash
# NFS-backed named volume using the local driver (NFSv3)
docker volume create \
  --driver local \
  --opt type=nfs \
  --opt o=addr=10.0.0.10,rw,nfsvers=3 \
  --opt device=:/var/nfs/data \
  nfs-volume

# CIFS/Samba-backed named volume using the local driver
docker volume create \
  --driver local \
  --opt type=cifs \
  --opt device=//fileserver.local/share \
  --opt o=addr=fileserver.local,username=backupuser,password=secret,file_mode=0777,dir_mode=0777 \
  cifs-volume
```

For more advanced requirements — cloud block storage, distributed filesystems, encryption, snapshot management — third-party volume plugins extend Docker's capabilities. Plugins are installed via `docker plugin install` and then referenced by their driver name when creating a volume.

Notable third-party volume plugins include:

| Plugin | Storage Backend | Common Use Case |
|---|---|---|
| `rexray/ebs` | AWS EBS | Persistent volumes on EC2 instances |
| `rexray/gcepd` | Google Persistent Disk | Persistent volumes on GCE |
| `portworx` | Distributed block storage | Multi-host production clusters |
| `local` with NFS opts | NFS server | Shared volumes across multiple hosts |

```bash
# Install a volume plugin (example: DigitalOcean Block Storage)
docker plugin install digitalocean/do-block-storage \
  --alias do \
  DOCKER_HOST=<token>

# Create a volume using the installed plugin's driver name
docker volume create --driver do --name do-volume-1
```

For Docker Swarm and multi-host environments, the volume driver choice determines whether the same named volume is available on every Swarm node. The `local` driver creates a volume that only exists on the node where it was created; a distributed driver like Portworx creates a volume accessible from any node in the cluster.

### Sharing Volumes Between Containers

Multiple containers can be connected to the same named volume simultaneously. The containers share the same underlying directory, so writes from one are immediately visible to the other. This pattern is useful for sidecar containers — a pattern where a helper container reads log files that the main application writes, or a backup agent container that reads a database container's data directory.

```bash
# Start a primary container writing to a shared volume
docker run -d --name data-writer \
  -v shared-data:/data \
  busybox sh -c "while true; do date >> /data/log.txt; sleep 5; done"

# Start a second container reading from the same volume
docker run -d --name data-reader \
  -v shared-data:/data:ro \
  busybox sh -c "while true; do tail -5 /data/log.txt; sleep 5; done"
```

The `--volumes-from` flag is a shorthand that mounts all volumes from one container into another, using the same paths. It is most often used in backup patterns:

```bash
# Mount all volumes from the db container into a temporary backup container
docker run --rm \
  --volumes-from db \
  -v "$(pwd)/backups":/backup \
  alpine tar czf /backup/db-data.tar.gz /var/lib/postgresql/data
```

Important: when two containers write to the same volume path concurrently, they are sharing a raw filesystem with no built-in locking. Concurrent writes to the same files require the application to handle coordination — for example, a database that provides its own locking, or an application that uses a queue to serialize writes.

### Volume Permissions and Ownership

File permissions inside a volume follow standard Linux rules: every file has an owning UID and GID. The UID is a number — the kernel does not know or care about usernames. This becomes important with Docker because the username `postgres` inside a container (UID 999 by convention) and a user named `postgres` on the host are completely different users unless their UIDs happen to match.

The most common symptom is a `permission denied` error when a container process tries to write to a bind-mounted directory that the host created as root (UID 0). The container process runs as a non-root UID and has no write permission on the root-owned directory.

```bash
# On the host, you create a directory as your user (e.g., UID 1000)
mkdir ./app-data
# uid=1000(alice) gid=1000(alice)

# But the container runs its process as UID 999 (postgres)
docker run --rm \
  -v "$(pwd)/app-data":/var/lib/postgresql/data \
  postgres:16-alpine
# ERROR: initdb: error: could not change permissions of directory
# "/var/lib/postgresql/data": Operation not permitted
```

There are four practical approaches to resolving permission mismatches:

**1. Use named volumes instead of bind mounts for writable data.** Named volumes are owned and managed by Docker. When Docker creates a new named volume and mounts it into a container, the volume's root directory is pre-owned by root, but when data is seeded from the image, it preserves the image's ownership. Named volumes sidestep most host-UID-mismatch problems entirely.

**2. Pre-create the directory with the correct ownership.**
```bash
# Find the UID the container process will run as
# (check the image documentation or inspect with docker run --rm <image> id)
mkdir ./app-data
sudo chown 999:999 ./app-data
docker run -d \
  -v "$(pwd)/app-data":/var/lib/postgresql/data \
  postgres:16-alpine
```

**3. Use an entrypoint script to `chown` at container startup.**
```dockerfile
# In a Dockerfile for your own image
COPY docker-entrypoint.sh /usr/local/bin/
ENTRYPOINT ["docker-entrypoint.sh"]
```
```bash
# docker-entrypoint.sh
#!/bin/sh
chown -R appuser:appuser /app/data
exec su-exec appuser "$@"
```

**4. Match UIDs at build time using build arguments.**
```dockerfile
ARG UID=1000
ARG GID=1000
RUN addgroup -g "${GID}" appgroup && \
    adduser -u "${UID}" -G appgroup -s /bin/sh -D appuser
USER appuser
```
```bash
docker build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)" -t myapp:1.0.0 .
```

For named volumes, a common pattern is to let the container run as root initially to set up the directory, then switch users. Many official images (PostgreSQL, Redis, Nginx) already do this in their own entrypoint scripts, so you typically do not need to handle it yourself when using official images with named volumes.

### Backup and Restore Strategies

Because named volume data lives inside Docker's managed storage directory, you back it up by running a temporary container that has access to the volume and exports its contents. The container does the archiving, not the host — this keeps the process consistent across any OS and does not require root access to `/var/lib/docker`.

**The canonical backup pattern** uses a small Alpine or Busybox container, mounts the target volume read-only (to avoid writes during backup), and tars the contents into a bind-mounted host directory:

```bash
# Stop the container using the volume first to ensure a consistent snapshot
docker stop my-database

# Run a temporary container to back up the volume
docker run --rm \
  --mount type=volume,src=pg-data,dst=/data,readonly \
  -v "$(pwd)/backups":/backup \
  alpine tar czf /backup/pg-data-$(date +%Y%m%d%H%M%S).tar.gz -C /data .

# Restart the database
docker start my-database
```

The `-C /data .` argument to `tar` changes into the volume directory before archiving, so the tarball contains the volume contents at the root level (not a path like `/data/...`). This makes restoration simpler.

**The canonical restore pattern** creates a fresh volume, starts a temporary container, and extracts the archive into it:

```bash
# Create a fresh volume to restore into
docker volume create pg-data-restored

# Extract the backup into the new volume
docker run --rm \
  --mount type=volume,src=pg-data-restored,dst=/data \
  -v "$(pwd)/backups":/backup \
  alpine tar xzf /backup/pg-data-20260404120000.tar.gz -C /data
```

For databases, prefer native dump tools over filesystem snapshots where possible, because running `pg_dump` or `mysqldump` produces a consistent logical backup that survives PostgreSQL or MySQL version upgrades:

```bash
# Logical backup of a PostgreSQL database (consistent, version-portable)
docker exec my-database \
  pg_dump -U devuser devdb > backups/devdb-$(date +%Y%m%d).sql

# Restore a logical backup into a running container
docker exec -i my-database \
  psql -U devuser devdb < backups/devdb-20260404.sql
```

For automated production backup, the `offen/docker-volume-backup` image provides an automated approach: deploy it as a sidecar service that runs on a cron schedule, uses `--volumes-from` to access target volumes, and ships archives to S3, SFTP, or a local path with configurable retention.

### Volumes in Docker Compose

Docker Compose manages volumes as a top-level resource alongside services and networks. Named volumes must be declared in the top-level `volumes:` section before they can be referenced by services. Bind mounts do not appear in the top-level `volumes:` section — they are defined inline in the service.

**Named volumes — short syntax:**
```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - pg-data:/var/lib/postgresql/data

volumes:
  pg-data:
```

**Named volumes — long syntax (explicit `type: volume`):**
```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - type: volume
        source: pg-data
        target: /var/lib/postgresql/data

volumes:
  pg-data:
```

**Bind mounts — long syntax:**
```yaml
services:
  web:
    image: nginx:1.27-alpine
    volumes:
      - type: bind
        source: ./nginx.conf
        target: /etc/nginx/nginx.conf
        read_only: true
```

**Bind mounts — short syntax:**
```yaml
services:
  web:
    image: nginx:1.27-alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
```

**External volumes** — volumes created outside of Compose (e.g., by a separate provisioning process or another Compose project) — are referenced with `external: true`. Compose will not create or delete these volumes; it will error out if they do not already exist when the stack starts:

```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - company-db-prod:/var/lib/postgresql/data

volumes:
  company-db-prod:
    external: true
```

**Volumes with driver options** (e.g., NFS-backed volume defined entirely in Compose):
```yaml
volumes:
  nfs-data:
    driver: local
    driver_opts:
      type: nfs
      o: "addr=10.0.0.10,rw,nfsvers=4"
      device: ":/exports/app-data"
```

**tmpfs mount in Compose:**
```yaml
services:
  worker:
    image: myworker:1.0.0
    tmpfs:
      - /tmp:size=128m,mode=1777
```

When you run `docker compose down`, named volumes are preserved by default. To also remove the volumes declared in the Compose file, pass `--volumes`:

```bash
# Tear down services and networks, but keep volumes (default)
docker compose down

# Tear down services, networks, AND all Compose-declared volumes
docker compose down --volumes
```

The `--volumes` flag only removes volumes declared in the Compose file's `volumes:` section — it does not remove external volumes.

## Best Practices

1. **Use named volumes for all writable production data, not bind mounts.** Named volumes are managed by Docker, are portable across host machines, and do not expose the host filesystem to the container — reducing both operational complexity and the blast radius of a compromised container.

2. **Always stop the container before taking a filesystem-level volume backup.** A database or any application with an open write-ahead log will produce a corrupt backup if you archive its data directory while writes are in flight. Stop the container or use the application's native backup tool (`pg_dump`, `mysqldump`) to get a consistent snapshot.

3. **Prefer `--mount` over `-v` for bind mounts in scripts and CI.** The `--mount` flag returns an error if the source path does not exist, while `-v` silently creates an empty directory — a subtle difference that causes hard-to-debug failures when a path is misspelled or the host environment changes.

4. **Never store sensitive ephemeral data (secrets, session tokens, decrypted credentials) in named volumes or bind mounts.** Use tmpfs mounts for data that must never touch disk. Combine this with `--read-only` on the root container filesystem to enforce that no writes go anywhere except explicitly mounted paths.

5. **Label your volumes for easier lifecycle management in production.** Labels make filtering with `docker volume ls --filter label=...` and targeted cleanup with `docker volume prune --filter label=...` practical. Adopt a consistent labeling convention across all services, such as `app=<name>`, `env=<production|staging>`, and `managed-by=compose`.

6. **Run `docker volume prune` in CI pipelines after each test run to prevent disk exhaustion.** Automated tests frequently spin up containers with anonymous volumes and never clean them up, silently consuming gigabytes of disk space on CI servers over time.

7. **Declare all volumes explicitly in `docker volume create` or in `compose.yaml` — do not rely on implicit auto-creation.** Implicit volume creation via `docker run -v myvolume:/data` will succeed even if you misspell `myvolume` as `myvloume`, silently creating a new, empty volume and leaving your application with no data.

8. **For bind mounts in development, mount only the directories that need to change, not the entire project root.** Mounting a large directory like `.` increases filesystem event overhead, can expose unintended files to the container, and can cause the container to pick up build artifacts or node_modules that differ from what is inside the image.

9. **Document required volumes in your README or `compose.yaml` comments, especially external volumes.** When a stack requires an external volume that must be provisioned before startup, operators will encounter an opaque error with no explanation unless the requirement is documented.

10. **Test that your backup archives restore correctly to a fresh volume before relying on them in production.** A backup that cannot be restored is not a backup. Schedule a monthly restore drill using the canonical tar-based restore pattern into a test environment.

## Use Cases

### Use Case 1: Database with Persistent Data That Survives Container Upgrades

A team runs PostgreSQL 15 in a container for a web application. A new PostgreSQL 16 minor release is available and they want to upgrade without losing any data.

- **Problem:** If the database data lives in the container's writable layer, upgrading means creating a new container from the new image, which starts with an empty database.
- **Concepts applied:** Named volume (`pg-data`) mounted at `/var/lib/postgresql/data`, `docker stop`, `docker rm`, `docker run` with the same `-v pg-data:/var/lib/postgresql/data` on the new image tag
- **Expected outcome:** The team stops the old container, removes it, and runs a new container from `postgres:16-alpine` with the same named volume. The data directory — including all tables, users, and configuration — is already present in the volume and the new container starts successfully against the existing data.

### Use Case 2: Live Code Reloading During Development

A developer is building a Node.js Express API and wants to see code changes reflected in the running container immediately without rebuilding the image on every save.

- **Problem:** Rebuilding the Docker image on every code change takes 20–60 seconds and breaks the flow of development.
- **Concepts applied:** Bind mount of the host `src/` directory into the container, container running a file-watching process like `nodemon`, read-only mount for `package.json` to prevent accidental writes
- **Expected outcome:** The developer runs `docker run -v "$(pwd)/src":/app/src -v "$(pwd)/package.json":/app/package.json:ro myapp:dev`. Every time they save a file in `src/`, the bind mount makes the new file immediately visible inside the container, and `nodemon` restarts the server — all without a rebuild.

### Use Case 3: Sidecar Backup Agent for a Production Database

A production PostgreSQL database runs in Docker. The team needs automated nightly backups that are uploaded to S3 without any manual intervention or modifications to the database container.

- **Problem:** The database container should be a single-purpose service with no backup logic built in. A separate backup process is needed that can access the database's data without modifying the primary container.
- **Concepts applied:** Shared named volume between the `db` container and a `backup-agent` sidecar container, `--volumes-from` or a shared volume mount in `compose.yaml`, `offen/docker-volume-backup` or a custom backup script with `pg_dump`
- **Expected outcome:** A `backup-agent` container declared in `compose.yaml` runs `pg_dump` nightly via a cron schedule, writing the output to a bind-mounted host path or pushing directly to S3. The database container has no knowledge of this process.

### Use Case 4: Secrets That Must Never Touch Disk

An application decrypts a license key at startup and holds the plaintext in memory for the lifetime of the process. For compliance reasons, the plaintext key must never be written to any disk — including Docker volume storage.

- **Problem:** Writing the decrypted key to any named volume or bind mount leaves a plaintext artifact on disk, violating the compliance requirement.
- **Concepts applied:** tmpfs mount at the path where the decrypted key is written (`/run/secrets`), container started with `--read-only` so all other writes are rejected, tmpfs provides a RAM-backed writable escape hatch
- **Expected outcome:** `docker run --read-only --mount type=tmpfs,dst=/run/secrets,tmpfs-size=1048576 myapp:1.0.0`. The decrypted key is written to `/run/secrets/license.key`, which lives entirely in RAM and is destroyed the instant the container stops.

### Use Case 5: Migrating Data Between Environments

A staging database volume must be copied to a production host to seed the production environment with the latest staging data before a major release.

- **Problem:** The volume's data lives inside Docker's storage directory at a path that is opaque and host-specific; there is no built-in `docker volume copy` command.
- **Concepts applied:** Tar-based volume backup using a temporary Alpine container, transferring the archive file to the production host with `scp` or `rsync`, tar-based restore into a fresh named volume on the production host
- **Expected outcome:** The operator runs the canonical backup pattern on the staging host to produce `staging-db.tar.gz`, copies it to the production host, creates a new named volume on production, and runs the restore pattern. The production database starts with an exact copy of the staging data.

## Hands-on Examples

### Example 1: Create, Inspect, and Manage Named Volumes with the CLI

You will practice the complete volume lifecycle: create a named volume, attach it to a container, write data to it, remove the container, and confirm the data persists by attaching the volume to a second container.

1. Create a named volume called `demo-vol`.

```bash
docker volume create demo-vol
```

Expected output:
```
demo-vol
```

2. Inspect the volume to see where Docker is storing its data.

```bash
docker volume inspect demo-vol
```

Expected output:
```json
[
    {
        "CreatedAt": "2026-04-04T10:00:00Z",
        "Driver": "local",
        "Labels": {},
        "Mountpoint": "/var/lib/docker/volumes/demo-vol/_data",
        "Name": "demo-vol",
        "Options": {},
        "Scope": "local"
    }
]
```

3. Start a Busybox container, mount the volume at `/data`, and write a file into it.

```bash
docker run --rm \
  --mount type=volume,src=demo-vol,dst=/data \
  busybox sh -c "echo 'hello from volume' > /data/hello.txt && cat /data/hello.txt"
```

Expected output:
```
hello from volume
```

The container exits and is removed (`--rm`), but the volume remains.

4. Confirm the volume still exists after the container was removed.

```bash
docker volume ls
```

Expected output:
```
DRIVER    VOLUME NAME
local     demo-vol
```

5. Start a second, completely independent container and verify the file is still there.

```bash
docker run --rm \
  --mount type=volume,src=demo-vol,dst=/data \
  busybox cat /data/hello.txt
```

Expected output:
```
hello from volume
```

6. Remove the volume.

```bash
docker volume rm demo-vol
```

Expected output:
```
demo-vol
```

7. Verify it is gone.

```bash
docker volume ls
```

Expected output:
```
DRIVER    VOLUME NAME
(empty — no volumes listed)
```

---

### Example 2: Bind Mount for Live Development Reload

You will simulate a live-reload development workflow: run a container that serves a static file, modify the file on the host, and observe the change immediately inside the container — no image rebuild required.

1. Create a working directory and a starter HTML file.

```bash
mkdir live-demo
cd live-demo
echo "<h1>Version 1</h1>" > index.html
```

2. Run an Nginx container with a bind mount projecting the current directory into the default Nginx web root. Use the absolute path for the bind mount source.

```bash
docker run -d --name live-nginx \
  --mount type=bind,src="$(pwd)",dst=/usr/share/nginx/html,readonly \
  -p 8080:80 \
  nginx:1.27-alpine
```

3. Verify the container is serving `Version 1`.

```bash
curl http://localhost:8080
```

Expected output:
```html
<h1>Version 1</h1>
```

4. On the host, update the HTML file — do not touch the container.

```bash
echo "<h1>Version 2 - live updated!</h1>" > index.html
```

5. Request the page again from the same running container.

```bash
curl http://localhost:8080
```

Expected output:
```html
<h1>Version 2 - live updated!</h1>
```

The file changed inside the container because the bind mount exposes the host directory directly — Nginx is reading `index.html` directly from your host. No restart, no rebuild.

6. Clean up.

```bash
docker stop live-nginx
docker rm live-nginx
cd ..
rm -rf live-demo
```

---

### Example 3: Back Up and Restore a Named Volume

You will create a named volume with data in it, produce a compressed tar archive backup, delete the volume, create a fresh volume, and restore the backup into it — verifying the data came back intact.

1. Create a volume and populate it with some files.

```bash
docker volume create source-data

docker run --rm \
  --mount type=volume,src=source-data,dst=/data \
  busybox sh -c "mkdir -p /data/records && \
    echo 'record 1' > /data/records/r1.txt && \
    echo 'record 2' > /data/records/r2.txt && \
    echo 'record 3' > /data/records/r3.txt"
```

2. Create a local directory to hold the backup archive.

```bash
mkdir ./vol-backups
```

3. Run a temporary Alpine container to create a compressed tar archive of the volume contents.

```bash
docker run --rm \
  --mount type=volume,src=source-data,dst=/data,readonly \
  -v "$(pwd)/vol-backups":/backup \
  alpine tar czf /backup/source-data-backup.tar.gz -C /data .
```

4. Confirm the backup file was created on the host.

```bash
ls -lh ./vol-backups/
```

Expected output:
```
-rw-r--r-- 1 user user  312 Apr  4 10:00 source-data-backup.tar.gz
```

5. Simulate a disaster: delete the original volume.

```bash
docker volume rm source-data
```

6. Create a new, empty volume to restore into.

```bash
docker volume create restored-data
```

7. Run a temporary Alpine container to extract the archive into the new volume.

```bash
docker run --rm \
  --mount type=volume,src=restored-data,dst=/data \
  -v "$(pwd)/vol-backups":/backup \
  alpine tar xzf /backup/source-data-backup.tar.gz -C /data
```

8. Verify all three files came back.

```bash
docker run --rm \
  --mount type=volume,src=restored-data,dst=/data \
  busybox find /data -type f -exec cat {} \;
```

Expected output:
```
record 1
record 2
record 3
```

9. Clean up.

```bash
docker volume rm restored-data
rm -rf ./vol-backups
```

---

### Example 4: Volumes and Bind Mounts in Docker Compose

You will write a `compose.yaml` that uses all three mount mechanisms: a named volume for database persistence, a bind mount for injecting a configuration file, and a tmpfs mount for a worker service's scratch space.

1. Create a project directory.

```bash
mkdir compose-volumes-demo
cd compose-volumes-demo
```

2. Create a custom Nginx configuration file on the host.

```bash
cat > custom-nginx.conf << 'EOF'
server {
    listen 80;
    location / {
        return 200 'Hello from custom nginx config\n';
        add_header Content-Type text/plain;
    }
    location /health {
        return 200 'OK\n';
        add_header Content-Type text/plain;
    }
}
EOF
```

3. Create the `compose.yaml`.

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: appsecret
      POSTGRES_DB: appdb
    volumes:
      - type: volume
        source: pg-data
        target: /var/lib/postgresql/data

  web:
    image: nginx:1.27-alpine
    ports:
      - "8080:80"
    volumes:
      - type: bind
        source: ./custom-nginx.conf
        target: /etc/nginx/conf.d/default.conf
        read_only: true

  worker:
    image: busybox
    command: sh -c "echo 'Writing to tmpfs...' && dd if=/dev/zero of=/tmp/scratch bs=1M count=10 && echo 'Done' && sleep 3600"
    tmpfs:
      - /tmp:size=64m,mode=1777

volumes:
  pg-data:
```

4. Start the stack.

```bash
docker compose up -d
```

Expected output:
```
[+] Running 4/4
 ✔ Network compose-volumes-demo_default  Created
 ✔ Container compose-volumes-demo-db-1    Started
 ✔ Container compose-volumes-demo-web-1   Started
 ✔ Container compose-volumes-demo-worker-1 Started
```

5. Test the web server is using the custom configuration.

```bash
curl http://localhost:8080
curl http://localhost:8080/health
```

Expected output:
```
Hello from custom nginx config
OK
```

6. Verify the named volume was created for PostgreSQL.

```bash
docker volume ls
```

Expected output:
```
DRIVER    VOLUME NAME
local     compose-volumes-demo_pg-data
```

Note: Compose prefixes the volume name with the project name (`compose-volumes-demo_`).

7. Inspect the pg-data volume to confirm it points to the database container.

```bash
docker volume inspect compose-volumes-demo_pg-data
```

8. Tear down the stack, keeping the database volume intact.

```bash
docker compose down
```

9. Confirm the volume persisted after `down` (no `--volumes` flag was passed).

```bash
docker volume ls
```

Expected output:
```
DRIVER    VOLUME NAME
local     compose-volumes-demo_pg-data
```

10. Clean up everything including the volume.

```bash
docker compose down --volumes
docker volume prune --force
cd ..
rm -rf compose-volumes-demo
```

## Common Pitfalls

### Pitfall 1: Pruning Named Volumes by Accident with `docker volume prune --all`

**Description:** Running `docker volume prune --all` removes every named volume that is not currently attached to a running container — including volumes for stopped database containers that contain months of production data.

**Why it happens:** Developers learn that `prune` cleans up unused resources and run it without realising that `--all` extends beyond anonymous volumes to named volumes as well. A database container that was stopped for maintenance looks "unused" to Docker.

**Incorrect pattern:**
```bash
# Intended: clean up disk space before a deployment
# Actual: destroys the stopped database volume
docker volume prune --all --force
```

**Correct pattern:**
```bash
# Only remove anonymous volumes, leave named volumes alone
docker volume prune --force

# Or prune only volumes with a specific label you use for disposable data
docker volume prune --filter label=disposable=true --force
```

---

### Pitfall 2: Bind Mounting a Non-Existent Host Path with `-v`

**Description:** When you use `-v /host/path/that/does/not/exist:/container/path`, Docker silently creates an empty directory at the host path and mounts it into the container. The application inside the container finds an empty directory where it expected data, and fails silently or with a confusing error.

**Why it happens:** The auto-creation behaviour of `-v` is a convenience for named volumes but a footgun for bind mounts. The path appears to work — `docker ps` shows the container running — until you investigate why no data is being loaded.

**Incorrect pattern:**
```bash
# Typo: /home/alice/proejct instead of /home/alice/project
docker run -v /home/alice/proejct:/app/src myapp:dev
# Docker creates /home/alice/proejct/ silently; container starts with an empty /app/src
```

**Correct pattern:**
```bash
# Use --mount: returns an error if the source path does not exist
docker run --mount type=bind,src=/home/alice/project,dst=/app/src myapp:dev
# Error response: invalid mount config for type "bind": bind source path does not exist
```

---

### Pitfall 3: Expecting Data Persistence from a Container's Writable Layer

**Description:** A developer stores data at a path inside the container that is not mounted to a volume, assuming `docker stop` followed by `docker start` will bring the data back. Data from the writable layer does survive `stop`/`start`, but it is permanently deleted by `docker rm`, which is almost always the next step in any deployment or cleanup workflow.

**Why it happens:** `docker stop` + `docker start` does preserve the writable layer, so the mistake is not caught until the container is removed — which can be weeks later, after a deployment or a `docker compose down`.

**Incorrect pattern:**
```bash
docker run -d --name mydb postgres:16-alpine
# (months of use and data accumulation)
docker compose down   # Removes the container — writable layer is gone
docker compose up -d  # New container, empty database
```

**Correct pattern:**
```bash
docker run -d --name mydb \
  -v mydb-data:/var/lib/postgresql/data \
  postgres:16-alpine
docker compose down   # Volume persists
docker compose up -d  # New container finds existing data in the volume
```

---

### Pitfall 4: UID/GID Mismatch Causing Permission Denied on Bind Mounts

**Description:** A container process that runs as a non-root UID (e.g., UID 999 for the `postgres` user) cannot write to a host directory that is owned by a different user (e.g., UID 1000, your laptop user), resulting in `permission denied` errors that are difficult to diagnose.

**Why it happens:** Linux permissions are enforced by UID number, not username. The name `postgres` inside the container and the name `alice` on the host have different UIDs that the kernel treats as completely separate identities.

**Incorrect pattern:**
```bash
mkdir ./pg-data          # Created as UID 1000 on the host
docker run -d \
  -v "$(pwd)/pg-data":/var/lib/postgresql/data \
  postgres:16-alpine
# Error: could not change permissions of directory: Operation not permitted
```

**Correct pattern:**
```bash
# Option A: use a named volume instead (Docker manages ownership)
docker run -d -v pg-data:/var/lib/postgresql/data postgres:16-alpine

# Option B: pre-set ownership to match the container's UID
mkdir ./pg-data
sudo chown 999:999 ./pg-data
docker run -d \
  -v "$(pwd)/pg-data":/var/lib/postgresql/data \
  postgres:16-alpine
```

---

### Pitfall 5: Using Relative Paths in `-v` with Docker Run

**Description:** Docker run does not accept relative paths in `-v` for bind mounts. Writing `-v ./data:/app/data` fails with a confusing error about the volume path being invalid.

**Why it happens:** The `-v` flag was designed to accept either a volume name (no path separator) or an absolute host path. Relative paths are only supported in Docker Compose, not in `docker run`.

**Incorrect pattern:**
```bash
docker run -v ./data:/app/data myapp:1.0.0
# Error: invalid mount config for type "bind": invalid mount path: './data' mount path must be absolute
```

**Correct pattern:**
```bash
# Use an absolute path with $(pwd) for the current directory
docker run -v "$(pwd)/data":/app/data myapp:1.0.0

# Or use --mount which accepts relative paths (. expands to current directory)
docker run --mount type=bind,src=./data,dst=/app/data myapp:1.0.0
```

---

### Pitfall 6: Forgetting to Declare Volumes in the Top-Level `volumes:` Section in Compose

**Description:** Referencing a named volume in a service's `volumes:` list without declaring it in the top-level `volumes:` section causes `docker compose up` to fail immediately with an error stating the volume is not declared.

**Why it happens:** Compose requires every named volume to be explicitly declared so that Compose can manage its lifecycle (creation, deletion with `--volumes`). Bind mounts do not need top-level declarations, so developers familiar only with bind mounts miss this requirement.

**Incorrect pattern:**
```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - pg-data:/var/lib/postgresql/data
# Missing top-level volumes: section
```

**Correct pattern:**
```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - pg-data:/var/lib/postgresql/data

volumes:
  pg-data:   # Must be declared here
```

---

### Pitfall 7: Taking a Filesystem Backup of a Running Database Volume

**Description:** Archiving a PostgreSQL or MySQL data directory while the database process is actively writing to it produces a corrupt backup. The archive will contain partially written pages and a write-ahead log that is ahead of the data files, which cannot be replayed into a consistent state.

**Why it happens:** Filesystem-level backup tools (tar, rsync) do not know about database transaction boundaries. They copy whatever bytes are on disk at the moment they read each file, which can be mid-transaction.

**Incorrect pattern:**
```bash
# Database is still running while this backup runs — corruption risk
docker run --rm \
  --mount type=volume,src=pg-data,dst=/data,readonly \
  -v "$(pwd)/backups":/backup \
  alpine tar czf /backup/pg-live.tar.gz -C /data .
```

**Correct pattern:**
```bash
# Option A: stop the database first for a consistent filesystem snapshot
docker stop my-database
docker run --rm \
  --mount type=volume,src=pg-data,dst=/data,readonly \
  -v "$(pwd)/backups":/backup \
  alpine tar czf /backup/pg-stopped.tar.gz -C /data .
docker start my-database

# Option B: use pg_dump for a logical backup without stopping the database
docker exec my-database \
  pg_dump -U devuser devdb > backups/devdb-$(date +%Y%m%d).sql
```

## Summary

- Docker provides three mount types for injecting storage into containers: named volumes (Docker-managed, portable, recommended for production data), bind mounts (host-path projection, ideal for development and config injection), and tmpfs mounts (RAM-backed, ephemeral, Linux-only, suited for sensitive transient data).
- The `docker volume` CLI subcommands — `create`, `ls`, `inspect`, `rm`, and `prune` — provide full lifecycle management for named volumes; `prune --all` is destructive and should only be used deliberately, as it removes all unused named volumes.
- Named volumes survive container removal and can be shared between containers simultaneously; when sharing writable volumes, the application is responsible for coordinating concurrent writes because Docker provides no built-in locking.
- Volume permission issues are almost always caused by UID/GID mismatches between the host and the container process; named volumes sidestep most of these issues compared to bind mounts, and the recommended fix for bind mounts is to match ownership explicitly using `chown` or build-time UID arguments.
- Docker Compose manages named volumes as top-level resources that must be declared in the `volumes:` section; external volumes require `external: true` and must be pre-created; `docker compose down --volumes` is the only way to remove Compose-declared volumes as a group.

## Further Reading

- [Docker Engine Storage: Volumes — Official Docs](https://docs.docker.com/engine/storage/volumes/) — The authoritative reference for named volumes: CLI usage, driver options, backup/restore patterns, and Compose configuration with complete examples for every scenario covered in this module.
- [Docker Engine Storage: Bind Mounts — Official Docs](https://docs.docker.com/engine/storage/bind-mounts/) — Complete reference for bind mount syntax, all `--mount` and `-v` options, SELinux labels, bind propagation modes, and security considerations; essential reading before using bind mounts in any production workflow.
- [Docker Engine Storage: tmpfs Mounts — Official Docs](https://docs.docker.com/engine/storage/tmpfs/) — Covers tmpfs syntax, size and mode options, Linux-only restrictions, and the specific scenarios where in-memory storage is the correct choice over disk-backed mounts.
- [Docker Compose File Reference: Volumes — Official Docs](https://docs.docker.com/reference/compose-file/volumes/) — The complete Compose Specification for top-level volume declarations, driver options, external volumes, labels, and custom naming — the definitive reference for every volume attribute available in `compose.yaml`.
- [Docker Storage Overview — Official Docs](https://docs.docker.com/engine/storage/) — A concise comparison of all three mount types with a decision guide for when to use each; the right first page to re-read when choosing between storage options.
- [Handling Permissions with Docker Volumes — Deni Bertovic](https://denibertovic.com/posts/handling-permissions-with-docker-volumes/) — A practitioner deep-dive into the UID/GID mismatch problem with bind mounts, covering the entrypoint script approach to dynamic ownership correction; one of the most referenced articles on this topic.
- [docker-volume-backup — offen/docker-volume-backup on GitHub](https://github.com/offen/docker-volume-backup) — An open-source sidecar container that automates Docker volume backups on a cron schedule with support for S3, SFTP, and local storage, encryption, and retention policies; the recommended starting point for production backup automation.
- [Docker Engine 29 Release Notes — Official Docs](https://docs.docker.com/engine/release-notes/29/) — Release notes for Docker Engine v29 (current stable as of 2026), noting the containerd image store as the new default and nftables firewall backend changes that can affect volume mount behaviour in hardened environments.
