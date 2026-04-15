# Module 5: Dockerfile and Custom Containers
> Subject: Docker | Difficulty: Intermediate-Advanced | Estimated Time: 285 minutes

## Objective

After completing this module, you will be able to explain what a Dockerfile is and how `docker build` reads it to produce a layered image. You will write production-quality Dockerfiles using every commonly used instruction — `FROM`, `RUN`, `COPY`, `ADD`, `WORKDIR`, `ENV`, `ARG`, `EXPOSE`, `VOLUME`, `USER`, `ENTRYPOINT`, `CMD`, `HEALTHCHECK`, and `LABEL` — and understand the syntax, purpose, and tradeoffs of each. You will construct multi-stage builds that separate the build environment from the final runtime image, dramatically reducing image size and attack surface. You will apply caching strategies, `.dockerignore` patterns, and layer-ordering discipline to produce fast, reproducible builds. You will tag images with standard registry naming conventions, push to Docker Hub and a private registry, and inspect images with `docker inspect` and `docker history`. You will also scan images for vulnerabilities using `docker scout` and `trivy`.

## Prerequisites

- Completed Module 0: Setup — Docker Engine 27 or later installed and the Docker daemon running
- Completed Module 1: Basics — comfortable with `docker run`, `docker ps`, `docker exec`, port mapping, and pulling images from Docker Hub
- Completed Module 2: Volumes — understand named volumes and bind mounts
- Completed Module 3: Networking — familiar with user-defined bridge networks and port publishing
- Completed Module 4: Docker Compose — able to write `compose.yaml` files and use the Compose CLI
- Docker Engine 27 or later installed (verify with `docker --version`; current stable release is Docker Engine 29.3.1)
- Basic familiarity with at least one of: Python, Node.js, or Go

## Key Concepts

### What Is a Dockerfile?

A Dockerfile is a plain-text script that describes, step by step, how to assemble a Docker image. Each line is an instruction. When you run `docker build`, the Docker build system — backed by **BuildKit** (the default build engine since Docker Engine 23.0) — reads the Dockerfile from top to bottom and executes every instruction in sequence. The result is a read-only image that can be instantiated as one or many containers.

Every instruction that modifies the filesystem produces a new **layer**. Layers are stored as content-addressed diffs and are shared between images that have identical history up to a given point. This sharing is what makes pulling and storing many images efficient: two images based on `python:3.12-slim` share all the layers that precede your customizations.

```
Dockerfile                   Build layers (bottom = oldest)
──────────                   ──────────────────────────────
FROM python:3.12-slim    →   Layer 0: base OS + Python runtime
RUN pip install flask    →   Layer 1: Flask and its dependencies
COPY . /app              →   Layer 2: your application code
CMD ["python", "app.py"] →   Layer 3: metadata (no filesystem change)
```

### The Build Cache

BuildKit caches each layer keyed to the instruction content and all prior instructions. On subsequent builds, if an instruction and its context are identical to a previous build, BuildKit reuses the cached layer instead of re-executing the instruction. Cache hits make iterative development fast.

Cache is **invalidated** when:
- An instruction's text changes
- A file copied by `COPY` or `ADD` changes (BuildKit checksums files)
- Any earlier instruction's cache is invalidated (cache invalidation cascades downward)

This cascade behaviour has a direct implication for Dockerfile authoring: **place instructions that change rarely near the top, and instructions that change frequently near the bottom.** Dependencies typically change less often than source code, so install them before copying source.

---

## Dockerfile Instruction Reference

### Parser Directive

Place this as the very first line of every Dockerfile to opt in to the latest stable Dockerfile syntax and unlock all BuildKit features:

```dockerfile
# syntax=docker/dockerfile:1
```

This is a parser directive, not a comment. It must appear before any other content, including blank lines.

---

### FROM — Base Image Selection

```dockerfile
FROM [--platform=<platform>] <image>[:<tag>|@<digest>] [AS <name>]
```

`FROM` initializes a new build stage and declares the base image. Every Dockerfile must start with a `FROM` instruction (after any parser directives or `ARG` declarations).

**Always pin your base image tag.** Using `latest` means your build may silently change behaviour when the upstream image is updated.

```dockerfile
# Bad — unpinned
FROM python:latest

# Good — pinned to a minor version
FROM python:3.12-slim

# Best — pinned to a specific digest for supply-chain guarantees
FROM python:3.12-slim@sha256:a4e8b6e0d4f3c9b2a1f0e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6
```

**Scratch images** have no base at all — the image filesystem starts empty. They are used for statically compiled binaries (Go, Rust, C) that have no runtime dependencies:

```dockerfile
FROM scratch
COPY --from=build /bin/myapp /myapp
ENTRYPOINT ["/myapp"]
```

**Multi-stage syntax** adds `AS <name>` so later stages can reference this one:

```dockerfile
FROM node:22-alpine AS builder
```

> **Tip:** For Alpine-based images, always append the Alpine version (e.g., `node:22-alpine3.20`) rather than just `alpine`. The floating `alpine` tag can move to a new Alpine major version.

---

### RUN — Execute Build Commands

```dockerfile
RUN [OPTIONS] <command>                        # shell form
RUN [OPTIONS] ["<executable>", "<arg1>", ...]  # exec form
```

`RUN` executes a command inside the image during the build, creating a new layer. Every `RUN` instruction you add becomes a permanent part of the image history.

**Shell vs exec form:**
- Shell form runs the command through `/bin/sh -c` on Linux. It supports shell features like variable expansion, pipes, and globbing.
- Exec form runs the command directly without a shell. No shell substitution occurs. Required when the base image has no shell (e.g., `scratch` or `distroless`).

**Chain commands to minimize layers.** Each `RUN` creates one layer. If you install packages in multiple `RUN` instructions, intermediate layers accumulate package manager caches and metadata that are never cleaned up:

```dockerfile
# Bad — three layers, cache files baked in
RUN apt-get update
RUN apt-get install -y curl
RUN rm -rf /var/lib/apt/lists/*

# Good — one layer, cache wiped in the same step
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*
```

**`--mount=type=cache` for package manager caches (BuildKit):**

BuildKit can mount a persistent cache directory that survives between builds but is never baked into image layers. This is the best-of-both-worlds approach: the cache persists on the build host for speed, but the image stays small.

```dockerfile
# Python / pip
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --requirement requirements.txt

# Node.js / npm
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline

# APT (do NOT add rm -rf /var/lib/apt/lists/* when using cache mount)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends curl
```

> **Note:** `--mount=type=cache` requires BuildKit, which is the default engine since Docker Engine 23.0. If you are on an older installation, set `DOCKER_BUILDKIT=1` in your environment. Do not mix cache mounts with the `rm -rf /var/lib/apt/lists/*` cleanup pattern — the cache mount is detached after the `RUN` step completes and does not inflate the image layer.

**Catching pipe failures** — by default, the exit code of a pipe chain is the exit code of the last command. Use `set -o pipefail` to propagate failures from any command in the chain:

```dockerfile
RUN set -o pipefail && curl -fsSL https://example.com/install.sh | bash
```

---

### COPY vs ADD

```dockerfile
COPY [OPTIONS] <src> ... <dest>
ADD  [OPTIONS] <src> ... <dest>
```

Both instructions copy files into the image, but they have different capabilities:

| Feature | COPY | ADD |
|---|---|---|
| Copy files from build context | Yes | Yes |
| Copy from a previous build stage (`--from`) | Yes | No |
| Automatically extract local `.tar` archives | No | Yes |
| Fetch from a remote URL | No | Yes (use sparingly) |

**Use `COPY` by default.** Its behaviour is explicit and predictable. Use `ADD` only when you specifically need tar auto-extraction.

```dockerfile
# Copy a single file
COPY requirements.txt /app/requirements.txt

# Copy an entire directory
COPY src/ /app/src/

# Copy with explicit ownership (avoids a chown RUN step)
COPY --chown=appuser:appuser . /app

# Copy from a previous build stage
COPY --from=builder /app/dist /app/dist

# ADD for auto-extraction (legitimate use case)
ADD rootfs.tar.xz /
```

#### .dockerignore

The `.dockerignore` file controls which files from the build context directory are sent to the Docker daemon when you run `docker build`. Excluding unnecessary files reduces the build context size, speeds up transfers, and prevents cache invalidation from unrelated file changes.

Create `.dockerignore` at the project root alongside your Dockerfile:

```
# .dockerignore

# Version control
.git
.gitignore

# Python artifacts
__pycache__
*.pyc
*.pyo
.pytest_cache
.mypy_cache
*.egg-info
dist/
build/

# Node artifacts
node_modules
npm-debug.log

# Development and local config
.env
.env.local
*.env.*
.vscode
.idea

# Documentation
docs/
*.md

# Test output
coverage/
.nyc_output
```

> **Pitfall:** If you forget `.dockerignore`, your `node_modules` directory (often hundreds of megabytes) will be sent to the daemon on every build, even if you never `COPY` it.

---

### WORKDIR — Set the Working Directory

```dockerfile
WORKDIR /path/to/workdir
```

`WORKDIR` sets the working directory for all subsequent `RUN`, `CMD`, `ENTRYPOINT`, `COPY`, and `ADD` instructions. It creates the directory if it does not exist. Always use absolute paths.

```dockerfile
WORKDIR /app

# Subsequent COPY instructions are relative to /app
COPY requirements.txt .

# Subsequent RUN instructions execute in /app
RUN pip install -r requirements.txt
```

> **Pitfall:** Avoid `RUN cd /some/path && do-something`. The directory change in `RUN` does not persist to the next instruction. Use `WORKDIR` instead.

---

### ENV and ARG — Variables

#### ENV — Runtime Environment Variables

```dockerfile
ENV <key>=<value> [<key>=<value> ...]
```

`ENV` sets environment variables that are available during the build (in subsequent instructions) and persist into the running container. They appear in `docker inspect` output.

```dockerfile
ENV APP_PORT=8080 \
    APP_ENV=production \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
```

> **Security warning:** Do not store secrets in `ENV`. The values are baked into the image and visible to anyone who can pull the image or inspect its history. Pass secrets at runtime with `-e`, or use Docker secrets.

#### ARG — Build-time Arguments

```dockerfile
ARG <name>[=<default_value>]
```

`ARG` defines a variable that exists only during the build, passed in with `--build-arg`. Unlike `ENV`, `ARG` values do not persist in the final image.

```dockerfile
ARG NODE_VERSION=22
FROM node:${NODE_VERSION}-alpine

ARG BUILD_DATE
ARG GIT_COMMIT
LABEL org.opencontainers.image.created=${BUILD_DATE} \
      org.opencontainers.image.revision=${GIT_COMMIT}
```

**Scoping rules:** An `ARG` declared before `FROM` is only available in the `FROM` instruction. To use it after `FROM`, re-declare it (with no default, to inherit the outer value):

```dockerfile
ARG VERSION=1.0
FROM ubuntu:24.04

# VERSION is not available here yet
ARG VERSION        # re-declare to bring it back into scope
RUN echo "Building version ${VERSION}"
```

**`ARG` vs `ENV` — when to use which:**

| | `ARG` | `ENV` |
|---|---|---|
| Available during build | Yes | Yes |
| Available in running container | No | Yes |
| Visible in `docker inspect` | No (after build) | Yes |
| Override at runtime | No | Yes (`-e` flag) |
| Use for | Build customisation, CI metadata | Application config, runtime tuning |

---

### EXPOSE — Document Ports

```dockerfile
EXPOSE <port>[/<protocol>] [<port>[/<protocol>] ...]
```

`EXPOSE` is purely **documentation**. It records which ports the application listens on, but it does not publish them or create any firewall rules. Actual publishing still requires `-p` or `-P` at `docker run` time (or `ports:` in Compose).

```dockerfile
EXPOSE 8080
EXPOSE 5432/tcp
EXPOSE 53/udp
```

> **Note:** `docker run -P` (uppercase) automatically publishes all `EXPOSE`d ports to random host ports. This is useful for quick testing but should not be used in production.

---

### VOLUME — Declare Mount Points

```dockerfile
VOLUME ["/data"]
VOLUME /var/log /var/cache
```

`VOLUME` marks a path inside the container as a mount point. If no volume is provided at runtime, Docker automatically creates an anonymous volume at that path. Any data written to the path before the `VOLUME` instruction is preserved in the image; data written after (in subsequent build steps) is discarded.

```dockerfile
# Database data directory
VOLUME /var/lib/postgresql/data

# Application log directory
VOLUME /var/log/app
```

> **Tip:** `VOLUME` is most useful for documenting paths that should be externally managed. For production workloads, always supply an explicit named volume or bind mount at runtime rather than relying on anonymous volumes.

---

### USER — Drop Privileges

```dockerfile
USER <user>[:<group>]
USER <UID>[:<GID>]
```

By default, containers run as `root` (UID 0). Running as root inside a container is a security risk: if an attacker escapes the container namespace, they have root on the host. Use `USER` to run as a non-privileged user.

Create the user in a `RUN` instruction, then switch to it:

```dockerfile
# Create a dedicated user and group with no home directory and no login shell
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/false --no-create-home appuser

# Switch to the non-root user for all subsequent instructions
USER appuser
```

For Alpine-based images, use `addgroup`/`adduser`:

```dockerfile
RUN addgroup -S -g 1001 appgroup \
    && adduser -S -u 1001 -G appgroup -H -s /sbin/nologin appuser
USER appuser
```

> **Pitfall:** Files copied into the image before the `USER` instruction are owned by root. If your application needs to write to those files, either change ownership with `COPY --chown=appuser:appgroup` or `RUN chown` before switching users.

---

### ENTRYPOINT vs CMD — Container Startup

These two instructions define what runs when the container starts, and their interaction is one of the most frequently misunderstood aspects of Dockerfiles.

#### CMD

```dockerfile
CMD ["executable", "param1", "param2"]   # exec form (recommended)
CMD command param1 param2                 # shell form
CMD ["param1", "param2"]                 # default params for ENTRYPOINT
```

`CMD` sets the **default command** for the container. It can be completely overridden by supplying a command at `docker run` time:

```bash
# Uses the Dockerfile CMD
docker run myapp

# Overrides CMD entirely
docker run myapp python debug_script.py
```

Only the **last** `CMD` in a Dockerfile takes effect.

#### ENTRYPOINT

```dockerfile
ENTRYPOINT ["executable", "param1"]   # exec form (recommended)
ENTRYPOINT command param1              # shell form
```

`ENTRYPOINT` sets the container's main executable. Unlike `CMD`, it is not overridden by arguments to `docker run` — those arguments are **appended** to the `ENTRYPOINT` exec form:

```dockerfile
ENTRYPOINT ["python", "-m", "gunicorn"]
CMD ["--workers=4", "--bind=0.0.0.0:8080", "app:app"]
```

```bash
# Runs: python -m gunicorn --workers=4 --bind=0.0.0.0:8080 app:app
docker run myapp

# Runs: python -m gunicorn --workers=2 --bind=0.0.0.0:9090 app:app
docker run myapp --workers=2 --bind=0.0.0.0:9090 app:app

# To override ENTRYPOINT entirely:
docker run --entrypoint python myapp app.py
```

**Shell form disables signal forwarding.** If you write `ENTRYPOINT python app.py` (shell form), the process runs as a child of `/bin/sh -c`, not as PID 1. Signals like `SIGTERM` (from `docker stop`) are not forwarded to the Python process, causing the container to wait until the 10-second timeout before being killed. Always prefer exec form for `ENTRYPOINT`.

**Decision guide:**

| Goal | Use |
|---|---|
| Simple image with a fixed default command | `CMD` only |
| Container behaves like an executable (e.g., a CLI tool) | `ENTRYPOINT` (exec form) + optional `CMD` defaults |
| Wrapper script that sets up the environment, then exec's the command | `ENTRYPOINT ["./entrypoint.sh"]` + `CMD` |

---

### HEALTHCHECK — Container Health

```dockerfile
HEALTHCHECK [OPTIONS] CMD <command>
HEALTHCHECK NONE  # disable any inherited health check
```

`HEALTHCHECK` defines a command Docker runs periodically inside the container to determine if it is healthy. The result appears in `docker ps` as `healthy`, `unhealthy`, or `starting`.

Options:

| Option | Default | Description |
|---|---|---|
| `--interval` | `30s` | How often to run the check |
| `--timeout` | `30s` | How long to wait for the command to complete |
| `--start-period` | `0s` | Grace period after startup before failing checks count |
| `--start-interval` | `5s` | Interval during the start period |
| `--retries` | `3` | Consecutive failures before marking unhealthy |

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1
```

For images without `curl`, use `wget`:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:8080/health || exit 1
```

> **Note:** Docker Compose and Kubernetes both read the `HEALTHCHECK` instruction. In Compose, a service with a health check marked as `unhealthy` can block dependent services when `depends_on: condition: service_healthy` is used (as covered in Module 4).

---

### LABEL — Image Metadata

```dockerfile
LABEL <key>=<value> [<key>=<value> ...]
```

`LABEL` attaches arbitrary key-value metadata to an image. Labels are queryable with `docker inspect` and searchable in registries. The [OCI Image Spec](https://specs.opencontainers.org/image-spec/annotations/) defines a standard set of annotation keys under the `org.opencontainers.image.*` namespace.

```dockerfile
LABEL org.opencontainers.image.title="My Application" \
      org.opencontainers.image.description="A production-ready Flask API" \
      org.opencontainers.image.version="2.1.0" \
      org.opencontainers.image.authors="team@example.com" \
      org.opencontainers.image.source="https://github.com/example/myapp" \
      org.opencontainers.image.licenses="MIT"
```

> **Note:** The `MAINTAINER` instruction is deprecated. Use `LABEL org.opencontainers.image.authors=` instead.

---

## Building Images

### The `docker build` Command

```bash
docker build [OPTIONS] <build-context>
```

The **build context** is the directory whose contents are sent to the Docker daemon. It is almost always `.` (the current directory). Keep your build context lean — use `.dockerignore` aggressively.

**Common flags:**

| Flag | Purpose | Example |
|---|---|---|
| `-t`, `--tag` | Name and optionally tag the image | `-t myapp:1.0.0` |
| `-f`, `--file` | Path to a Dockerfile (default: `./Dockerfile`) | `-f docker/Dockerfile.prod` |
| `--build-arg` | Set a build-time `ARG` variable | `--build-arg NODE_ENV=production` |
| `--no-cache` | Disable the build cache (all layers rebuilt) | `--no-cache` |
| `--target` | Stop at a specific named stage | `--target builder` |
| `--platform` | Target architecture (cross-compilation) | `--platform linux/arm64` |
| `--pull` | Always pull the latest base image | `--pull` |
| `--progress` | Build output format (`auto`, `plain`, `tty`) | `--progress=plain` |

**Example build commands:**

```bash
# Standard build with a tag
docker build -t myapp:1.0.0 .

# Build with a non-default Dockerfile path
docker build -f deploy/Dockerfile.prod -t myapp:1.0.0 .

# Build with build arguments
docker build \
  --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) \
  -t myapp:1.0.0 .

# Force a completely fresh build (no cache, fresh base image)
docker build --no-cache --pull -t myapp:1.0.0 .

# Build only up to the "test" stage in a multi-stage Dockerfile
docker build --target test -t myapp:test .
```

---

## Multi-Stage Builds

### Why Multi-Stage Builds?

Compiling a Go binary, transpiling TypeScript, or bundling a React app all require build tools — compilers, bundlers, dev dependencies — that have no place in a production image. Before multi-stage builds, teams either shipped bloated images containing build tools or maintained two separate Dockerfiles and a build script to orchestrate them.

Multi-stage builds solve this in a single Dockerfile: you define multiple `FROM` stages, each potentially using a different base image. The final stage selectively copies only the artifacts it needs from earlier stages using `COPY --from=<stage-name>`. Build tools are left behind in intermediate stages that are never exported as the final image.

**Impact on image size (typical Node.js application):**

| Approach | Image Size |
|---|---|
| Single stage (all tools included) | ~1.1 GB |
| Multi-stage (runtime only) | ~120 MB |
| Multi-stage with Alpine | ~85 MB |

### COPY --from Syntax

```dockerfile
# Copy from a named stage
COPY --from=builder /app/dist /app/dist

# Copy from a stage by index (0-based; fragile, prefer names)
COPY --from=0 /bin/hello /bin/hello

# Copy from an external image (not a stage in this Dockerfile)
COPY --from=nginx:1.27-alpine /etc/nginx/nginx.conf /etc/nginx/nginx.conf
```

### Building Intermediate Stages with --target

During development, you may want to build and inspect an intermediate stage — for example, running your test suite inside the build environment:

```bash
# Build only up to the "test" stage
docker build --target test -t myapp:test .

# Run the tests
docker run --rm myapp:test
```

BuildKit is smart about `--target`: it only executes the stages that the target stage depends on, skipping unrelated branches.

---

## Best Practices

### 1. Order Instructions by Change Frequency

The most impactful caching optimisation. Layers near the top of the Dockerfile rarely change (OS packages, runtime installation). Layers near the bottom change frequently (your source code). Place them accordingly:

```
1. FROM (base image)
2. Install OS packages (changes rarely)
3. Install language runtime or framework (changes occasionally)
4. Copy dependency manifests (package.json, requirements.txt)
5. Install application dependencies (changes when manifest changes)
6. Copy source code (changes constantly)
7. Build/compile (if needed)
8. Configure USER, EXPOSE, HEALTHCHECK, CMD
```

### 2. Use Specific Tags, Never `latest`

```dockerfile
# Bad
FROM node:latest

# Good
FROM node:22.3.0-alpine3.20
```

### 3. Run as Non-Root

Create a dedicated user and switch to it before the final `CMD`. The earlier you create the user in the file, the more instructions benefit from the principle of least privilege.

### 4. Keep Images Small

- Use Alpine or distroless base images
- Install only `--no-install-recommends` packages
- Clean up package manager caches in the same `RUN` step (or use `--mount=type=cache`)
- Use multi-stage builds to exclude build tools from the final image
- Use `.dockerignore` to exclude test fixtures, documentation, and dev configs

### 5. Scan Images for Vulnerabilities

Integrate image scanning into your build pipeline. Two popular tools:

**Docker Scout** (built into the Docker CLI):

```bash
# Quick vulnerability overview
docker scout quickview myapp:1.0.0

# Detailed CVE list
docker scout cves myapp:1.0.0

# Show only fixable critical and high CVEs
docker scout cves --only-fixed --only-severity critical,high myapp:1.0.0

# Compare two image versions
docker scout compare myapp:1.0.0 myapp:1.1.0
```

**Trivy** (open-source, no daemon required):

```bash
# Install trivy (Linux)
# See https://trivy.dev for platform-specific install instructions

# Scan a local image
trivy image myapp:1.0.0

# Scan with severity filter
trivy image --severity HIGH,CRITICAL myapp:1.0.0

# Run trivy as a container (no local install required)
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image myapp:1.0.0
```

### 6. One Process Per Container

Design each image to run a single process as PID 1. Use Compose or an orchestrator (Kubernetes) to wire together multiple containers. Do not run a web server, a database, and a cron daemon inside one image.

### 7. Make the Entrypoint Executable

If you use a shell script as an entrypoint, ensure it is executable and starts with a proper shebang, and that it `exec`s its arguments so the process becomes PID 1:

```bash
#!/bin/sh
set -e

# Perform initialisation (e.g., run database migrations)
python manage.py migrate

# exec replaces the shell process with the application,
# making it PID 1 and ensuring it receives signals correctly
exec "$@"
```

```dockerfile
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "gunicorn", "app:app"]
```

---

## Working with Custom Containers

### Tagging Conventions

Image names follow the format:

```
[registry/][namespace/]repository[:tag]
```

| Component | Description | Example |
|---|---|---|
| `registry` | Registry hostname and optional port (omit for Docker Hub) | `ghcr.io`, `registry.example.com:5000` |
| `namespace` | Username or organisation | `myusername`, `mycompany` |
| `repository` | Image name | `myapp`, `api-server` |
| `tag` | Version label (default: `latest`) | `1.0.0`, `v2.3.1-alpine`, `20260413` |

```bash
# Docker Hub (registry omitted, defaults to docker.io)
myusername/myapp:1.0.0

# GitHub Container Registry
ghcr.io/myorg/myapp:1.0.0

# Private registry
registry.example.com:5000/myteam/myapp:1.0.0
```

**Versioning strategies:**

- **Semantic versions** (`1.0.0`, `2.3.1`) for release artefacts
- **Git SHA tags** (`myapp:abc1234`) for CI/CD traceability
- **Date tags** (`myapp:20260413`) for nightly builds
- **Floating convenience tags** (`myapp:latest`, `myapp:1`) that point to the most recent release — update these alongside the pinned tag but never rely on them in production

### docker tag

`docker tag` creates an additional name (tag) pointing to an existing image. No new image is created; it is a pointer update:

```bash
# Tag a locally built image for Docker Hub
docker tag myapp:1.0.0 myusername/myapp:1.0.0

# Add a floating latest tag pointing to the same image
docker tag myapp:1.0.0 myusername/myapp:latest

# Tag for a private registry
docker tag myapp:1.0.0 registry.example.com:5000/myteam/myapp:1.0.0
```

### docker push and docker pull

```bash
# Log in to Docker Hub
docker login

# Log in to a private registry
docker login registry.example.com:5000

# Push to Docker Hub
docker push myusername/myapp:1.0.0
docker push myusername/myapp:latest

# Push to a private registry
docker push registry.example.com:5000/myteam/myapp:1.0.0

# Pull from Docker Hub
docker pull myusername/myapp:1.0.0

# Pull from a private registry
docker pull registry.example.com:5000/myteam/myapp:1.0.0

# Push all local tags for a repository at once
docker push --all-tags myusername/myapp
```

> **Pitfall:** Docker Hub rate-limits unauthenticated pulls (100 pulls per 6 hours per IP for anonymous users). Always `docker login` in CI/CD environments that pull frequently.

### Inspecting Images

```bash
# Full JSON metadata: layers, environment variables, entrypoint, labels, etc.
docker inspect myapp:1.0.0

# Extract a specific field with --format
docker inspect --format='{{.Config.Cmd}}' myapp:1.0.0
docker inspect --format='{{json .Config.Labels}}' myapp:1.0.0 | python3 -m json.tool

# View layer history — shows each instruction and its size contribution
docker history myapp:1.0.0

# Show layer sizes in a human-readable table
docker history --human myapp:1.0.0

# View the full, untruncated command for each layer
docker history --no-trunc myapp:1.0.0
```

---

## Hands-On Examples

### Example 1 — Python Flask Application

This example containerises a minimal Flask application from scratch, demonstrating dependency caching, non-root execution, and a health check.

**Project structure:**

```
flask-app/
├── Dockerfile
├── .dockerignore
├── requirements.txt
└── app.py
```

**`app.py`:**

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({"message": "Hello from Docker!", "status": "ok"})

@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

**`requirements.txt`:**

```
flask==3.1.0
gunicorn==23.0.0
```

**`.dockerignore`:**

```
__pycache__
*.pyc
*.pyo
.pytest_cache
.env
.git
```

**`Dockerfile`:**

```dockerfile
# syntax=docker/dockerfile:1

# ── Base stage ─────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# Prevents Python from writing .pyc files and buffers stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── Dependencies stage ─────────────────────────────────────────────────────────
FROM base AS deps

# Copy only the requirements file first to leverage the build cache.
# This layer is only rebuilt when requirements.txt changes.
COPY requirements.txt .

# Use BuildKit cache mount to avoid re-downloading packages on every build.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --require-hashes --no-deps -r requirements.txt || \
    pip install -r requirements.txt

# ── Final production stage ─────────────────────────────────────────────────────
FROM base AS final

# Create a non-root user
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/false --no-create-home appuser

# Copy installed packages from the deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Copy application source code, owned by the non-root user
COPY --chown=appuser:appgroup . .

# Switch to non-root user
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

LABEL org.opencontainers.image.title="Flask Demo App" \
      org.opencontainers.image.version="1.0.0"

ENTRYPOINT ["gunicorn"]
CMD ["--workers=2", "--bind=0.0.0.0:8080", "app:app"]
```

**Build and run:**

```bash
cd flask-app

# Build the image
docker build -t flask-demo:1.0.0 .

# Run the container
docker run -d --name flask-demo -p 8080:8080 flask-demo:1.0.0

# Test the endpoints
curl http://localhost:8080/
curl http://localhost:8080/health

# Check health status
docker ps   # look for "healthy" in the STATUS column

# View image layers
docker history flask-demo:1.0.0

# Clean up
docker stop flask-demo && docker rm flask-demo
```

> **Tip:** On the second build (after any requirements.txt change), notice how the `pip install` step uses the BuildKit cache and completes significantly faster.

---

### Example 2 — Node.js Application with Multi-Stage Build

This example builds a Node.js application that has a separate build step (TypeScript compilation), demonstrating a true multi-stage pipeline where build dependencies never reach the final image.

**Project structure:**

```
node-app/
├── Dockerfile
├── .dockerignore
├── package.json
├── package-lock.json
├── tsconfig.json
└── src/
    └── index.ts
```

**`src/index.ts`:**

```typescript
import http from "http";

const PORT = parseInt(process.env.PORT || "3000", 10);

const server = http.createServer((req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "healthy" }));
    return;
  }
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ message: "Hello from Node.js on Docker!", status: "ok" }));
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Server running on port ${PORT}`);
});
```

**`package.json`:**

```json
{
  "name": "node-demo",
  "version": "1.0.0",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js"
  },
  "dependencies": {},
  "devDependencies": {
    "typescript": "^5.4.5",
    "@types/node": "^22.0.0"
  }
}
```

**`tsconfig.json`:**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "outDir": "./dist",
    "strict": true,
    "esModuleInterop": true
  },
  "include": ["src"]
}
```

**`.dockerignore`:**

```
node_modules
dist
npm-debug.log
.git
*.md
```

**`Dockerfile`:**

```dockerfile
# syntax=docker/dockerfile:1

# ── Builder stage ──────────────────────────────────────────────────────────────
# Uses the full Node.js image which includes npm and build tools
FROM node:22-alpine3.20 AS builder

WORKDIR /build

# Copy dependency manifests first to take advantage of layer caching.
# npm ci is only re-run when package-lock.json changes.
COPY package.json package-lock.json ./

# Install ALL dependencies including devDependencies (TypeScript, type defs)
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Copy the source code and compile TypeScript → JavaScript
COPY tsconfig.json .
COPY src/ ./src/
RUN npm run build

# ── Production stage ───────────────────────────────────────────────────────────
# Uses a minimal Node.js image — no TypeScript compiler, no devDependencies
FROM node:22-alpine3.20 AS final

WORKDIR /app

# Install only production dependencies from scratch
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --omit=dev

# Copy only the compiled JavaScript output from the builder stage
COPY --from=builder /build/dist ./dist

# Create and use a non-root user
RUN addgroup -S -g 1001 appgroup \
    && adduser -S -u 1001 -G appgroup -H -s /sbin/nologin appuser
USER appuser

ENV PORT=3000
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:3000/health || exit 1

LABEL org.opencontainers.image.title="Node.js Demo App" \
      org.opencontainers.image.version="1.0.0"

CMD ["node", "dist/index.js"]
```

**Build and run:**

```bash
cd node-app

# Build the final production image
docker build -t node-demo:1.0.0 .

# Build only the builder stage (useful for debugging build failures)
docker build --target builder -t node-demo:builder .

# Compare image sizes
docker images node-demo

# Run the production image
docker run -d --name node-demo -p 3000:3000 node-demo:1.0.0

# Test the app
curl http://localhost:3000/
curl http://localhost:3000/health

# Verify TypeScript source and devDependencies are NOT in the image
docker run --rm node-demo:1.0.0 ls /app

# Clean up
docker stop node-demo && docker rm node-demo
```

**Expected output from `docker images node-demo`:**

```
REPOSITORY   TAG       IMAGE ID       CREATED         SIZE
node-demo    1.0.0     a1b2c3d4e5f6   1 minute ago    ~120 MB
node-demo    builder   f6e5d4c3b2a1   1 minute ago    ~470 MB
```

> **Tip:** The `COPY --from=builder /build/dist ./dist` line is the heart of multi-stage: it copies only the compiled JavaScript from the builder stage. Everything else in the builder stage — the TypeScript compiler, `node_modules` with devDependencies, intermediate files — stays in the builder layer, which is never shipped.

---

### Example 3 — Custom Base Image with Non-Root User and Health Check

This example builds a reusable hardened base image for Python microservices. Other teams can use it as their `FROM` and inherit the non-root user, health check framework, and standard labels.

**`Dockerfile`:**

```dockerfile
# syntax=docker/dockerfile:1

FROM python:3.12-slim AS hardened-base

# ── Metadata ───────────────────────────────────────────────────────────────────
LABEL org.opencontainers.image.title="Hardened Python Base" \
      org.opencontainers.image.description="Minimal Python 3.12 base with non-root user and health endpoint" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.authors="platform-team@example.com"

# ── System packages ────────────────────────────────────────────────────────────
# curl is included for health checks; pinned to avoid surprise upgrades
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Environment ────────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    APP_PORT=8080

WORKDIR ${APP_HOME}

# ── Non-root user ──────────────────────────────────────────────────────────────
ARG APP_UID=1001
ARG APP_GID=1001

RUN groupadd --gid ${APP_GID} appgroup \
    && useradd \
        --uid ${APP_UID} \
        --gid appgroup \
        --shell /bin/false \
        --no-create-home \
        appuser \
    && chown -R appuser:appgroup ${APP_HOME}

# ── Health check ───────────────────────────────────────────────────────────────
# Child images should expose a /health endpoint on APP_PORT
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${APP_PORT}/health || exit 1

EXPOSE ${APP_PORT}

# Switch to non-root user (child images inherit this unless they reset it)
USER appuser
```

**Building and using the custom base:**

```bash
# Build the hardened base image
docker build -t myorg/python-base:3.12-v1 .

# Override the UID/GID at build time if needed
docker build --build-arg APP_UID=2000 --build-arg APP_GID=2000 \
  -t myorg/python-base:3.12-v1 .

# Inspect the resulting configuration
docker inspect --format='{{json .Config.User}}' myorg/python-base:3.12-v1
docker inspect --format='{{json .Config.Healthcheck}}' myorg/python-base:3.12-v1

# View the full layer history
docker history myorg/python-base:3.12-v1
```

**A downstream service Dockerfile using the custom base:**

```dockerfile
# syntax=docker/dockerfile:1

# Inherit all the hardening: non-root user, health check, env vars
FROM myorg/python-base:3.12-v1

# Copy and install app-specific dependencies
COPY --chown=appuser:appgroup requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy application source
COPY --chown=appuser:appgroup . .

CMD ["gunicorn", "--workers=2", "--bind=0.0.0.0:8080", "app:app"]
```

```bash
# Build the downstream service
docker build -t myorg/my-service:1.0.0 -f Dockerfile.service .

# Verify the user is still non-root
docker run --rm myorg/my-service:1.0.0 id

# Run and verify health check kicks in
docker run -d --name my-service -p 8080:8080 myorg/my-service:1.0.0
sleep 15
docker ps   # should show "healthy"

# Clean up
docker stop my-service && docker rm my-service
```

---

## Common Pitfalls

**Pitfall 1 — `apt-get update` on its own line**
Splitting `apt-get update` and `apt-get install` into separate `RUN` instructions causes the `update` to be cached and never refreshed. When the package list is stale, `apt-get install` may fail or install outdated versions. Always combine them in one `RUN` step.

**Pitfall 2 — Copying secrets into the image**
`COPY .env /app/.env` bakes your credentials into the image layer. Even a subsequent `RUN rm /app/.env` does not remove the data — it remains in the previous layer. Use Docker secrets, environment variables at runtime, or secret mounts:
```dockerfile
RUN --mount=type=secret,id=mysecret,target=/run/secrets/mysecret \
    cat /run/secrets/mysecret
```

**Pitfall 3 — Shell form ENTRYPOINT breaks signal handling**
`ENTRYPOINT python app.py` runs Python as a child of `/bin/sh`. `docker stop` sends `SIGTERM` to `/bin/sh`, which does not forward it to Python. The container hangs for 10 seconds (the default stop grace period) before being killed. Use exec form: `ENTRYPOINT ["python", "app.py"]`.

**Pitfall 4 — Forgetting .dockerignore**
Without `.dockerignore`, the entire build context (including `node_modules`, `.git`, test fixtures) is sent to the daemon on every build. A `node_modules` directory can be hundreds of megabytes, causing multi-second build context transfers even when nothing changed.

**Pitfall 5 — `COPY . .` before installing dependencies**
Copying source code before installing dependencies means any source file change invalidates the dependency installation cache. Copy dependency manifests first, install, then copy source.

**Pitfall 6 — Using `ADD` for local file copies**
`ADD` has hidden magic (tar extraction, URL fetching) that can produce surprising results. Use `COPY` for all local file operations. Reserve `ADD` for its specific capabilities when you explicitly need them.

**Pitfall 7 — Not running as non-root**
Containers running as root are a significant security risk. If the application process is compromised and the container breaks out of its namespace, the attacker has root on the host. Always create a dedicated user with a fixed UID and switch to it with `USER`.

---

## Summary

| Instruction | Key Takeaway |
|---|---|
| `FROM` | Pin to a specific tag or digest; use `AS name` for multi-stage |
| `RUN` | Chain commands with `&&`; use `--mount=type=cache` for package managers |
| `COPY` | Prefer over `ADD`; use `--chown` to set ownership |
| `ADD` | Use only for tar extraction or URL fetching |
| `WORKDIR` | Always use absolute paths; avoid `RUN cd` |
| `ENV` | For runtime configuration; never for secrets |
| `ARG` | For build-time customisation; does not persist in the image |
| `EXPOSE` | Documentation only; does not publish ports |
| `VOLUME` | Declares mount points; always supply explicit volumes at runtime |
| `USER` | Switch to a non-root user before `CMD`/`ENTRYPOINT` |
| `ENTRYPOINT` | Use exec form; defines the container's main executable |
| `CMD` | Provides default arguments; overridable at runtime |
| `HEALTHCHECK` | Define meaningful health checks; use `--start-period` for slow startup |
| `LABEL` | Use OCI standard keys for metadata |

---

## Further Reading

- [Dockerfile Reference — Docker Docs](https://docs.docker.com/reference/dockerfile/) — The authoritative, exhaustive reference for every Dockerfile instruction, parser directive, and option flag. Bookmark this; you will return to it often.
- [Best Practices for Writing Dockerfiles — Docker Docs](https://docs.docker.com/build/building/best-practices/) — Docker's official guidance on layer caching, image size, security, and maintainability, with concrete before/after examples.
- [Multi-Stage Builds — Docker Docs](https://docs.docker.com/build/building/multi-stage/) — In-depth documentation on multi-stage builds, `COPY --from`, `--target` flag usage, and BuildKit behaviour when building intermediate stages.
- [Optimize Build Cache — Docker Docs](https://docs.docker.com/build/cache/optimize/) — Explains how BuildKit validates cache, how to use `--mount=type=cache` for package managers, and strategies for cache export and import in CI/CD environments.
- [Docker Scout Quickstart — Docker Docs](https://docs.docker.com/scout/quickstart/) — Getting started guide for Docker Scout vulnerability scanning, including CLI commands, CVE filtering, and comparison workflows.
- [Trivy Documentation — trivy.dev](https://trivy.dev/docs/latest/guide/target/container_image/) — Complete reference for scanning container images with Trivy, including severity filters, output formats (JSON, SARIF, CycloneDX), and CI/CD integration patterns.
- [Top 21 Dockerfile Best Practices for Container Security — Sysdig](https://www.sysdig.com/learn-cloud-native/dockerfile-best-practices/) — Practitioner-focused security checklist covering non-root users, secret handling, image signing, distroless images, and CI/CD scanning integration.

---

Sources:
- [Dockerfile reference | Docker Docs](https://docs.docker.com/reference/dockerfile/)
- [Best practices | Docker Docs](https://docs.docker.com/build/building/best-practices/)
- [Multi-stage | Docker Docs](https://docs.docker.com/build/building/multi-stage/)
- [Optimize cache usage in builds | Docker Docs](https://docs.docker.com/build/cache/optimize/)
- [Docker Scout Quickstart | Docker Docs](https://docs.docker.com/scout/quickstart/)
- [Trivy - Container Image | trivy.dev](https://trivy.dev/docs/latest/guide/target/container_image/)
- [Top 21 Dockerfile best practices for container security | Sysdig](https://www.sysdig.com/learn-cloud-native/dockerfile-best-practices)
- [How to Use Multi-Stage Docker Builds | OneUptime](https://oneuptime.com/blog/post/2026-02-02-docker-multi-stage-builds/view)
- [How to Use RUN --mount=type=cache | OneUptime](https://oneuptime.com/blog/post/2026-02-08-how-to-use-run-mounttypecache-for-package-manager-caching/view)
- [docker image tag | Docker Docs](https://docs.docker.com/reference/cli/docker/image/tag/)
- [docker image push | Docker Docs](https://docs.docker.com/reference/cli/docker/image/push/)
