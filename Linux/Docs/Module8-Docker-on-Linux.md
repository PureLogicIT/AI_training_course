# Module 8: Docker on Linux
> Subject: Linux | Difficulty: Intermediate | Estimated Time: 285 minutes

## Objective

After completing this module, you will be able to install Docker Engine (not Docker Desktop) on Ubuntu or Debian using the official apt repository, manage containers with the core CLI commands (`docker run`, `pull`, `ps`, `stop`, `rm`, `images`), persist model data across container restarts using named volumes, configure bridge and host networking modes and understand when each is appropriate for GPU-accelerated workloads, pass environment variables into containers, install and configure the NVIDIA Container Toolkit so containers can access a host GPU, write a `compose.yaml` that brings up a full AI stack (Ollama LLM backend + Open WebUI + Nginx reverse proxy) with GPU passthrough and persistent storage, build custom Docker images with a Dockerfile, push and pull images from Docker Hub and a private registry, manage container logs, and apply resource limits (`--gpus`, `--memory`, `--cpus`) to prevent runaway containers from starving the host system.

## Prerequisites

- Completed Module 1: Introduction to Linux (comfortable with the terminal, `sudo`, and basic file navigation)
- Completed Module 5: Users, Groups, and Permissions (understanding of file ownership and the significance of adding users to groups)
- Completed Module 6: Services and systemd (familiarity with `systemctl enable/start/status` so that understanding Docker as a systemd service makes sense)
- Ubuntu 22.04 LTS or Ubuntu 24.04 LTS, or Debian 12 (Bookworm) — a fresh server or VM is strongly recommended
- For the GPU sections: an NVIDIA GPU with a driver already installed on the host (verify with `nvidia-smi`); CUDA drivers are managed by the host, not the container
- Root or `sudo` access on the server
- Conceptual familiarity with what a web server is (client sends request, server returns response)
- No prior Docker or container experience is assumed for the first half of this module

## Key Concepts

### Why Docker Engine Instead of Docker Desktop on a Linux Server

Docker Desktop is a graphical application designed for developer workstations. It bundles the Docker Engine inside a lightweight virtual machine so that containers run in an isolated Linux environment on macOS and Windows. On a Linux server you do not need that abstraction layer — Docker Engine runs containers directly on the host kernel without any VM in between. Docker Desktop on Linux also runs a VM by default, which wastes memory and CPU on a server that has no display attached and no reason for the GUI tooling.

Docker Engine is the production-grade runtime. It installs as a systemd service (`dockerd`), starts automatically on boot, and is what every cloud provider, CI system, and server deployment guide refers to when it says "Docker." The installation process adds two binaries that matter most: `dockerd` (the daemon that manages containers) and `docker` (the CLI client that talks to the daemon).

Docker has three distribution channels: **Stable** (recommended for production), **Test** (release candidates), and **Nightly** (bleeding edge). This module uses the Stable channel exclusively. As of mid-2025 the stable release line is Docker Engine 27.x. Always verify the current version with `docker --version` after installation and compare against [https://docs.docker.com/engine/release-notes/](https://docs.docker.com/engine/release-notes/).

### Installing Docker Engine on Ubuntu and Debian

The distributions' built-in package repositories (`apt install docker.io`) ship old versions of Docker that are often one or two major versions behind. Always install from Docker's own apt repository to get the current stable release.

The installation has four phases: (1) remove any old conflicting packages, (2) add Docker's GPG key and apt repository, (3) install the packages, (4) run post-installation steps to make the daemon available without `sudo`.

**Phase 1 — Remove old packages**

```bash
# These package names conflict with the official Docker Engine packages.
# It is safe to run this even if none of them are installed.
for pkg in docker.io docker-doc docker-compose docker-compose-v2 \
           podman-docker containerd runc; do
  sudo apt-get remove -y "$pkg" 2>/dev/null || true
done
```

**Phase 2 — Add the apt repository**

```bash
# Install prerequisite tools
sudo apt-get update
sudo apt-get install -y ca-certificates curl

# Create the directory for apt keyrings if it doesn't exist
sudo install -m 0755 -d /etc/apt/keyrings

# Download Docker's official GPG key
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the stable Docker repository
# For Debian, replace "ubuntu" with "debian" in the URL
echo \
  "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
```

**Phase 3 — Install the packages**

```bash
sudo apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

The four packages serve distinct roles:
- `docker-ce` — the Docker Engine daemon
- `docker-ce-cli` — the `docker` command-line client
- `containerd.io` — the low-level container runtime Docker delegates to
- `docker-buildx-plugin` — extended image build capabilities
- `docker-compose-plugin` — adds the `docker compose` subcommand

**Phase 4 — Post-installation steps**

```bash
# Verify the daemon is running
sudo systemctl status docker

# Enable it to start at boot (usually already enabled after install)
sudo systemctl enable docker

# Add your user to the docker group so you can run docker without sudo.
# Log out and back in after this for the group change to take effect.
sudo usermod -aG docker "$USER"

# Verify the installation (run without sudo after re-logging in)
docker run hello-world
```

Expected output from `docker run hello-world`:

```
Hello from Docker!
This message shows that your installation appears to be working correctly.
...
```

### Core Container CLI Commands

Once Docker is installed these six commands form the foundation of daily container management. Understanding what each one does at the daemon level — not just the syntax — prevents confusion later.

**`docker pull`** fetches an image from a registry and stores it locally. Nothing runs yet.

```bash
# Pull the Ollama image (LLM runtime) from Docker Hub
docker pull ollama/ollama:latest

# Pull a specific digest-pinned version for reproducibility
docker pull ollama/ollama:0.3.12
```

**`docker run`** creates a container from an image and starts it. Common flags:

| Flag | Meaning |
|------|---------|
| `-d` | Detached — run in background, print container ID |
| `--name` | Give the container a human-readable name |
| `-p host:container` | Publish a container port to the host |
| `-v source:target` | Mount a volume or bind mount |
| `-e KEY=VALUE` | Set an environment variable |
| `--rm` | Delete the container automatically when it exits |
| `--restart unless-stopped` | Restart on crash or reboot, unless manually stopped |

```bash
# Run Nginx, expose port 8080 on the host, name the container "webserver"
docker run -d --name webserver -p 8080:80 --restart unless-stopped nginx:1.27-alpine
```

**`docker ps`** lists running containers. Add `-a` to include stopped containers.

```bash
docker ps
docker ps -a
```

Example output:
```
CONTAINER ID   IMAGE              COMMAND                  CREATED         STATUS         PORTS                  NAMES
3f2a1c8d9e01   nginx:1.27-alpine  "/docker-entrypoint.…"   2 minutes ago   Up 2 minutes   0.0.0.0:8080->80/tcp   webserver
```

**`docker stop`** sends SIGTERM to the main process, waits 10 seconds, then sends SIGKILL. This is a graceful shutdown.

```bash
docker stop webserver
```

**`docker rm`** removes a stopped container. The image remains on disk.

```bash
docker rm webserver
# Remove a running container forcefully (skips graceful shutdown)
docker rm -f webserver
```

**`docker images`** lists all locally stored images.

```bash
docker images
```

```
REPOSITORY       TAG           IMAGE ID       CREATED        SIZE
ollama/ollama    latest        a1b2c3d4e5f6   3 days ago     1.58GB
nginx            1.27-alpine   b2c3d4e5f6a7   2 weeks ago    43MB
hello-world      latest        c3d4e5f6a7b8   5 months ago   13.3kB
```

To remove an image: `docker rmi nginx:1.27-alpine`. Docker refuses to remove an image that has a running or stopped container using it — remove the container first.

### Volumes for Persistent Model Storage

By default a container's writable layer is deleted when the container is removed. For an LLM backend like Ollama this is catastrophic: a model such as Llama 3.1 70B can be 40+ GB. Re-downloading it every time a container is recreated is not acceptable.

Docker named volumes are the right solution. A named volume is a directory managed by Docker on the host filesystem (stored under `/var/lib/docker/volumes/`). It persists independently of any container lifecycle. You can stop, remove, and recreate the container and the volume — along with all the model files in it — remains untouched.

```bash
# Create a named volume explicitly
docker volume create ollama-models

# Mount it into a container at the path Ollama uses for models
docker run -d \
  --name ollama \
  -v ollama-models:/root/.ollama \
  -p 11434:11434 \
  ollama/ollama:latest

# Inspect the volume to see where Docker stores it on the host
docker volume inspect ollama-models
```

```json
[
    {
        "CreatedAt": "2025-09-01T14:22:10Z",
        "Driver": "local",
        "Mountpoint": "/var/lib/docker/volumes/ollama-models/_data",
        "Name": "ollama-models",
        "Scope": "local"
    }
]
```

**Bind mounts** are an alternative where you specify an exact host directory path. They are useful for configuration files and development code but less portable than named volumes for model storage.

```bash
# Bind mount: host path on left, container path on right
docker run -d \
  --name ollama \
  -v /data/ollama:/root/.ollama \
  -p 11434:11434 \
  ollama/ollama:latest
```

For AI workloads the recommendation is: use **named volumes** for large binary data (model weights), and **bind mounts** for configuration files you want to edit from the host.

### Networking: Bridge Mode vs. Host Mode

Docker containers are attached to virtual networks. The two modes that matter most for GPU AI stacks are bridge mode (the default) and host mode.

**Bridge mode** creates an internal virtual network. Each container on the same bridge network can reach other containers by their service name (Compose handles this automatically). Traffic from outside reaches containers only through explicitly published ports (`-p`). This is the correct default for most services including Open WebUI and Nginx.

```
Host OS
 └── Docker bridge network (172.17.0.0/16 default, or custom subnet)
      ├── ollama container (172.17.0.2)
      ├── open-webui container (172.17.0.3)
      └── nginx container (172.17.0.4) ← port 443 published to host
```

**Host mode** removes all network isolation between the container and the host. The container shares the host's network stack directly — it uses `localhost` to refer to the host and binds ports on the host interface without any translation. This has two important implications for GPU AI workloads:

1. **GPU performance:** Some CUDA and GPU-to-GPU communication paths (NCCL, NVLink) rely on low-level network primitives that do not cross the Docker bridge cleanly. Host networking eliminates the bridge layer entirely, reducing latency for high-throughput inference workloads.
2. **Port conflicts:** Because the container shares the host network, any port it binds competes directly with host processes. If something else is listening on 11434, Ollama will fail to start.

```bash
# Run Ollama in host network mode (no -p flag needed — it binds directly on the host)
docker run -d \
  --name ollama \
  --network host \
  -v ollama-models:/root/.ollama \
  ollama/ollama:latest
```

In a Compose file, a service uses host networking by setting `network_mode: host`. Note that host mode is only available on Linux; it is silently ignored on macOS and Windows Docker Desktop.

**Rule of thumb for a single-GPU AI server:** Run Ollama in host network mode. Run Open WebUI and Nginx in bridge mode. They communicate with Ollama via `http://localhost:11434` (host network), while the web UI and proxy remain isolated in their own bridge network.

### Environment Variables

Environment variables are the standard mechanism for configuring containers without baking values into the image. They control runtime behavior: API endpoints, authentication tokens, feature flags, and model parameters.

Pass a single variable with `-e`:

```bash
docker run -d \
  --name open-webui \
  -e OLLAMA_BASE_URL=http://localhost:11434 \
  -e WEBUI_AUTH=false \
  -p 3000:8080 \
  ghcr.io/open-webui/open-webui:main
```

Pass many variables from a file with `--env-file`. The file contains one `KEY=VALUE` per line and is never committed to source control:

```bash
# .env file
OLLAMA_BASE_URL=http://localhost:11434
WEBUI_AUTH=false
WEBUI_SECRET_KEY=changeme-use-a-real-secret

docker run -d --name open-webui --env-file .env -p 3000:8080 \
  ghcr.io/open-webui/open-webui:main
```

In `compose.yaml`, environment variables can be declared inline or by referencing a file:

```yaml
services:
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    env_file:
      - .env
    environment:
      - OLLAMA_BASE_URL=http://localhost:11434
```

Inline `environment` values take precedence over `env_file` values if the same key appears in both.

### NVIDIA Container Toolkit and GPU Passthrough

By default a Docker container has no access to the host's GPU. The NVIDIA Container Toolkit installs a container runtime hook (`nvidia-container-runtime`) that intercepts container creation, mounts the NVIDIA device files and shared libraries into the container, and injects the environment variables the CUDA runtime needs. The host only needs the NVIDIA drivers installed — the CUDA toolkit itself can live entirely inside the container image.

**Installation on Ubuntu/Debian**

```bash
# Add the NVIDIA Container Toolkit repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure the Docker daemon to use the NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker

# Restart the Docker daemon to pick up the new runtime configuration
sudo systemctl restart docker
```

The `nvidia-ctk runtime configure` command modifies `/etc/docker/daemon.json` to register the NVIDIA runtime. You can inspect the result:

```bash
cat /etc/docker/daemon.json
```

```json
{
    "runtimes": {
        "nvidia": {
            "args": [],
            "path": "nvidia-container-runtime"
        }
    }
}
```

**Granting GPU access to a container**

```bash
# Grant access to all GPUs
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

# Grant access to a specific GPU by index
docker run --rm --gpus '"device=0"' nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

# Grant access to a specific GPU by UUID
docker run --rm --gpus '"device=GPU-abc12345-1234-1234-1234-abcdef012345"' \
  nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

The `--gpus all` flag is shorthand for `--device /dev/nvidia0 --device /dev/nvidiactl --device /dev/nvidia-uvm` plus the shared library mounts. Without the toolkit you would have to enumerate all these manually. Verify GPU access is working by checking that `nvidia-smi` inside the container shows your GPU model and driver version.

**Why host network mode matters for GPU workloads**

When Ollama serves large models it uses CUDA's peer-to-peer memory operations and can use NCCL (NVIDIA Collective Communications Library) for multi-GPU inference. These communication paths work most reliably when the container shares the host network stack. For single-GPU setups the performance difference is small but host mode is still a common recommendation in the Ollama documentation because it eliminates one potential source of connectivity issues between the container and the GPU IPC (Inter-Process Communication) subsystem.

### Building Custom Images with a Dockerfile

The official images for Ollama and Open WebUI are suitable for most cases, but you will often need to customize: add a configuration file, install an extra Python package, or bake an API key check at startup.

A Dockerfile is a text file of instructions that Docker executes sequentially to build a new image layer by layer.

**Essential Dockerfile instructions**

| Instruction | Purpose |
|------------|---------|
| `FROM` | Base image to build on top of — every Dockerfile must start with this |
| `RUN` | Execute a shell command during the build; result is committed as a layer |
| `COPY` | Copy files from the build context (your local directory) into the image |
| `WORKDIR` | Set the working directory for subsequent `RUN`, `COPY`, `CMD` instructions |
| `ENV` | Set environment variables baked into the image |
| `EXPOSE` | Document which port the container listens on (does not actually publish it) |
| `CMD` | Default command to run when the container starts (can be overridden by `docker run`) |
| `ENTRYPOINT` | Fixed executable; `CMD` becomes arguments passed to it |

**Example: Custom Nginx image with an embedded configuration**

```dockerfile
# Dockerfile
FROM nginx:1.27-alpine

# Copy a custom nginx config from the build context into the image
COPY nginx.conf /etc/nginx/nginx.conf

# Copy static files for an error page
COPY html/ /usr/share/nginx/html/

# Expose the port Nginx listens on (documentation only)
EXPOSE 80 443

# Use the default CMD from the base image (starts nginx in foreground)
```

```bash
# Build the image, tagging it as "my-nginx:1.0"
# The dot (.) means "use the current directory as the build context"
docker build -t my-nginx:1.0 .

# Verify the new image appears locally
docker images my-nginx
```

**Multi-stage builds** keep production images small by separating build dependencies from runtime artifacts:

```dockerfile
# Stage 1: build
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: runtime (much smaller — no pip, no build tools)
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
CMD ["python", "server.py"]
```

### Registry Basics: Docker Hub and Private Registries

A registry is a server that stores and distributes Docker images. Docker Hub (`hub.docker.com`) is the default public registry. When you run `docker pull nginx`, Docker automatically expands this to `docker pull docker.io/library/nginx:latest`.

**Pushing to Docker Hub**

```bash
# Log in (prompts for username and password / access token)
docker login

# Tag your local image with your Docker Hub username and repository name
docker tag my-nginx:1.0 yourusername/my-nginx:1.0

# Push to Docker Hub
docker push yourusername/my-nginx:1.0
```

**Private registry** — for a GPU server you often want a self-hosted registry so model-augmented images stay on your infrastructure and are not bandwidth-limited by Docker Hub rate limits.

```bash
# Run a basic private registry on port 5000 of the host
docker run -d \
  --name registry \
  --restart unless-stopped \
  -p 5000:5000 \
  -v registry-data:/var/lib/registry \
  registry:2

# Tag an image for the private registry
docker tag my-nginx:1.0 localhost:5000/my-nginx:1.0

# Push to the private registry
docker push localhost:5000/my-nginx:1.0

# Pull from the private registry (from another machine, replace localhost with server IP)
docker pull 192.168.1.100:5000/my-nginx:1.0
```

For a private registry accessible from remote machines over HTTP (not HTTPS), add the server address to Docker's insecure registries list in `/etc/docker/daemon.json`:

```json
{
    "insecure-registries": ["192.168.1.100:5000"]
}
```

Then `sudo systemctl restart docker`.

### Log Management for Containers

Docker captures everything a container writes to stdout and stderr and stores it in a log file managed by the daemon. The default logging driver is `json-file`.

```bash
# View the last 50 lines of a container's logs
docker logs --tail 50 ollama

# Follow logs in real time (Ctrl+C to stop)
docker logs -f ollama

# Show logs with timestamps
docker logs -t --tail 100 open-webui

# View logs since a specific time
docker logs --since "2025-09-01T10:00:00" ollama
```

The `json-file` driver stores logs at `/var/lib/docker/containers/<container-id>/<container-id>-json.log`. These files grow unbounded by default and can fill up a disk on a busy inference server. Always configure log rotation in `/etc/docker/daemon.json`:

```json
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "50m",
        "max-file": "5"
    }
}
```

This keeps at most 5 log files of 50 MB each per container (250 MB maximum per container). Apply with `sudo systemctl restart docker`. Alternatively, configure log rotation per service in `compose.yaml`:

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    logging:
      driver: json-file
      options:
        max-size: "100m"
        max-file: "3"
```

### Resource Limits

Without limits, a runaway container can consume all CPU, memory, or GPU on the host, making the server unresponsive. Docker resource limits are enforced by Linux cgroups (control groups) — they are not just advisory.

**Memory**

```bash
# Limit to 16 GB RAM; container is killed (OOMKilled) if it exceeds this
docker run -d --name ollama --memory 16g ollama/ollama:latest

# memory-swap is memory + swap combined.
# Setting it equal to --memory disables swap for the container.
docker run -d --name ollama --memory 16g --memory-swap 16g ollama/ollama:latest
```

**CPU**

```bash
# Limit to 4 CPU cores (fractional values allowed: 0.5 = half a core)
docker run -d --name ollama --cpus 4 ollama/ollama:latest
```

**GPU**

```bash
# Grant all GPUs with no limits
docker run -d --gpus all ollama/ollama:latest

# Grant a specific GPU
docker run -d --gpus '"device=0"' ollama/ollama:latest
```

In `compose.yaml`, resource limits go under `deploy.resources`:

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    deploy:
      resources:
        limits:
          memory: 16g
          cpus: "4"
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

The `deploy.resources.reservations.devices` block is the Compose-native way to request GPU access. It is equivalent to `--gpus all` on the command line.

## Best Practices

1. **Always install Docker Engine from the official Docker apt repository, not from `apt install docker.io`.** The distribution-packaged version lags months or years behind the stable release, missing security patches and Compose features your stack depends on.

2. **Pin image tags to specific versions in production (`ollama/ollama:0.3.12`, not `ollama/ollama:latest`).** The `latest` tag is a mutable pointer that can silently update to an incompatible version the next time `docker pull` runs, breaking your stack without a clear cause.

3. **Use named volumes for all large binary data (model weights, database files) and bind mounts only for configuration files you actively edit.** Named volumes survive `docker compose down -v` only if you omit `-v`; bind mounts tie your deployment to a specific host path that may not exist on a different server.

4. **Set `--restart unless-stopped` (or `restart: unless-stopped` in Compose) on every long-running service.** This ensures the AI stack comes back automatically after a server reboot without requiring a manual `docker compose up -d`.

5. **Always configure log rotation (`max-size` and `max-file`) in `daemon.json` or per-service in `compose.yaml` before deploying to production.** A model serving 100 requests per hour generates megabytes of logs daily; without rotation the disk fills silently.

6. **Run `sudo nvidia-ctk runtime configure --runtime=docker` and restart the daemon before testing GPU passthrough.** The most common GPU access failure is forgetting to configure the runtime after installing the toolkit — `--gpus all` silently fails or errors without it.

7. **Use host network mode (`network_mode: host`) for the Ollama service when CUDA IPC or NCCL communication is involved, and bridge mode for all other services.** This gives GPU workloads the best network path while keeping the web UI and proxy isolated.

8. **Store secrets (API keys, registry credentials, `WEBUI_SECRET_KEY`) in a `.env` file that is listed in `.gitignore`, not hardcoded in `compose.yaml`.** A `compose.yaml` is typically committed to version control; a `.env` file is not.

9. **Use multi-stage Dockerfile builds for any custom image that involves a compilation or dependency installation step.** A Python application built in one stage and copied into a clean runtime stage can be 5–10x smaller than an image that installs build tools and keeps them.

10. **Test GPU access with `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` immediately after toolkit installation.** If this command shows your GPU, the entire stack will have GPU access. If it errors, diagnose here before writing a single line of `compose.yaml`.

## Use Cases

### Single-GPU Home Lab AI Server

**Problem:** A developer has a workstation with an NVIDIA GPU running Ubuntu 24.04 and wants to run a local LLM accessible from other devices on the home network, with a web chat interface and all services starting automatically on boot.

**Concepts applied:** Docker Engine installation, NVIDIA Container Toolkit, Ollama container with `--gpus all` and a named volume for model persistence, Open WebUI container connected to Ollama via host networking, `restart: unless-stopped` for automatic startup, Nginx as a reverse proxy on port 80.

**Outcome:** After `docker compose up -d`, the user accesses the chat interface at `http://server-ip` from any device on the network, models persist across restarts, and the full stack restores automatically after a power cycle.

### Reproducible AI Development Environment for a Team

**Problem:** A machine learning team has three engineers working on a RAG pipeline. Each engineer runs slightly different versions of Python packages, leading to "works on my machine" failures. The team wants a containerized environment that produces identical results across all three machines.

**Concepts applied:** Custom Dockerfile with pinned base image and pinned `requirements.txt`, multi-stage build to keep the image small, Docker Hub push/pull for distribution, environment variables for API keys passed via `--env-file`.

**Outcome:** Any team member runs `docker pull teamorg/rag-dev:1.4.2 && docker run --gpus all --env-file .env teamorg/rag-dev:1.4.2` and has an identical, reproducible runtime without installing Python, pip packages, or CUDA libraries directly on their workstation.

### Production AI Stack with Monitoring

**Problem:** A small company deploys an internal LLM-powered document assistant on a dedicated GPU server. They need the stack to recover from crashes, rotate logs so the disk does not fill, and limit Ollama's RAM usage so the system remains responsive for SSH and other admin tasks.

**Concepts applied:** `compose.yaml` with `restart: unless-stopped`, log rotation via the `logging` block per service, `--memory` limit on Ollama to reserve headroom for the OS, named volume for model persistence, Nginx on port 443 with TLS termination as the only publicly exposed port.

**Outcome:** The stack self-heals on container crashes and server reboots, logs cap at 500 MB total, Ollama cannot exceed 32 GB RAM even if a large model request leaks memory, and all user traffic is encrypted.

### Air-Gapped Deployment

**Problem:** A government contractor must deploy an LLM stack on a server with no internet access. Images must be preloaded and a private registry must serve as the source of truth.

**Concepts applied:** `docker save` to export images to tar archives on an internet-connected machine, physical transfer to the air-gapped host, `docker load` to import them, private registry container for internal distribution, `compose.yaml` pointing to `localhost:5000/...` image references.

**Outcome:** The stack runs entirely from locally available images with no outbound internet connections, satisfying network security requirements.

## Hands-on Examples

### Example 1: Installing Docker Engine and Verifying the Installation

You are setting up a freshly provisioned Ubuntu 24.04 server and need Docker Engine installed and verified before deploying any services.

1. Connect to the server via SSH and update the package index:
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   ```

2. Remove any conflicting legacy packages:
   ```bash
   for pkg in docker.io docker-doc docker-compose docker-compose-v2 \
              podman-docker containerd runc; do
     sudo apt-get remove -y "$pkg" 2>/dev/null || true
   done
   ```

3. Install prerequisites and add Docker's GPG key:
   ```bash
   sudo apt-get install -y ca-certificates curl
   sudo install -m 0755 -d /etc/apt/keyrings
   sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
     -o /etc/apt/keyrings/docker.asc
   sudo chmod a+r /etc/apt/keyrings/docker.asc
   ```

4. Add the Docker apt repository:
   ```bash
   echo \
     "deb [arch=$(dpkg --print-architecture) \
     signed-by=/etc/apt/keyrings/docker.asc] \
     https://download.docker.com/linux/ubuntu \
     $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
     sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt-get update
   ```

5. Install Docker Engine and the Compose plugin:
   ```bash
   sudo apt-get install -y \
     docker-ce docker-ce-cli containerd.io \
     docker-buildx-plugin docker-compose-plugin
   ```

6. Add your user to the docker group:
   ```bash
   sudo usermod -aG docker "$USER"
   newgrp docker
   ```

7. Verify the installation:
   ```bash
   docker run hello-world
   docker --version
   docker compose version
   ```

   Expected output includes:
   ```
   Hello from Docker!
   This message shows that your installation appears to be working correctly.
   ```
   ```
   Docker version 27.x.x, build ...
   Docker Compose version v2.x.x
   ```

### Example 2: Testing GPU Access Inside a Container

Your GPU server has the NVIDIA driver installed. You will install the NVIDIA Container Toolkit, configure Docker, and verify GPU access from inside a container.

1. Confirm the host driver is working:
   ```bash
   nvidia-smi
   ```
   This should print your GPU model, driver version, and CUDA version. If it fails, install NVIDIA drivers on the host first — this is a prerequisite the toolkit cannot fix.

2. Add the NVIDIA Container Toolkit repository and install:
   ```bash
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
     sudo gpg --dearmor \
     -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

   curl -s -L \
     https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
     sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
     sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

   sudo apt-get update
   sudo apt-get install -y nvidia-container-toolkit
   ```

3. Configure the Docker runtime and restart the daemon:
   ```bash
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```

4. Run the GPU test container:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
   ```

   Expected output: the same `nvidia-smi` table you saw on the host, printed from inside the container. You will see lines like:
   ```
   +-----------------------------------------------------------------------------------------+
   | NVIDIA-SMI 550.xx.xx    Driver Version: 550.xx.xx    CUDA Version: 12.4               |
   |-------------------------------+----------------------+----------------------+
   | GPU  Name                     Pers-M | Bus-Id         Disp.A | Volatile Uncorr. ECC |
   |   0  NVIDIA GeForce RTX 4090  Off   | 00000000:01:00.0  Off |                  N/A |
   +-------------------------------+----------------------+----------------------+
   ```

5. Pull the Ollama image and verify it can see the GPU:
   ```bash
   docker run --rm --gpus all --network host \
     -v ollama-models:/root/.ollama \
     ollama/ollama:latest ollama list
   ```

   This starts Ollama, lists downloaded models (empty on first run), and exits cleanly — confirming GPU access and volume mounting work together.

### Example 3: Full AI Stack with docker-compose

You will deploy a complete AI stack: Ollama (LLM backend with GPU access and host networking), Open WebUI (chat interface), and Nginx (reverse proxy). All services restart automatically and models persist across restarts.

1. Create a project directory and navigate into it:
   ```bash
   mkdir ~/ai-stack && cd ~/ai-stack
   ```

2. Create the Nginx configuration file:
   ```bash
   mkdir nginx
   cat > nginx/nginx.conf << 'EOF'
   events {
       worker_connections 1024;
   }

   http {
       upstream open_webui {
           server open-webui:8080;
       }

       server {
           listen 80;
           server_name _;

           client_max_body_size 100M;

           location / {
               proxy_pass http://open_webui;
               proxy_set_header Host $host;
               proxy_set_header X-Real-IP $remote_addr;
               proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
               proxy_set_header X-Forwarded-Proto $scheme;

               # Required for Open WebUI's streaming responses
               proxy_buffering off;
               proxy_read_timeout 300s;
           }
       }
   }
   EOF
   ```

3. Create the `.env` file for secrets (not committed to version control):
   ```bash
   cat > .env << 'EOF'
   WEBUI_SECRET_KEY=replace-this-with-a-long-random-string
   WEBUI_AUTH=false
   EOF
   ```

4. Create the `compose.yaml` file:
   ```yaml
   # compose.yaml
   # Full AI stack: Ollama + Open WebUI + Nginx
   # Requires NVIDIA Container Toolkit installed on the host.

   services:

     ollama:
       image: ollama/ollama:latest
       container_name: ollama
       # Host network mode: Ollama binds directly on the host at port 11434.
       # Open WebUI reaches it at http://localhost:11434.
       network_mode: host
       volumes:
         - ollama-models:/root/.ollama
       deploy:
         resources:
           reservations:
             devices:
               - driver: nvidia
                 count: 1
                 capabilities: [gpu]
       restart: unless-stopped
       logging:
         driver: json-file
         options:
           max-size: "100m"
           max-file: "3"

     open-webui:
       image: ghcr.io/open-webui/open-webui:main
       container_name: open-webui
       depends_on:
         - ollama
       networks:
         - ai-net
       env_file:
         - .env
       environment:
         # localhost here refers to the host (Ollama runs in host network mode)
         - OLLAMA_BASE_URL=http://localhost:11434
       volumes:
         - webui-data:/app/backend/data
       restart: unless-stopped
       logging:
         driver: json-file
         options:
           max-size: "50m"
           max-file: "3"

     nginx:
       image: nginx:1.27-alpine
       container_name: nginx
       depends_on:
         - open-webui
       networks:
         - ai-net
       ports:
         - "80:80"
       volumes:
         - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
       restart: unless-stopped
       logging:
         driver: json-file
         options:
           max-size: "20m"
           max-file: "3"

   volumes:
     ollama-models:
       driver: local
     webui-data:
       driver: local

   networks:
     ai-net:
       driver: bridge
   ```

5. Start the stack:
   ```bash
   docker compose up -d
   ```

6. Verify all three containers are running:
   ```bash
   docker compose ps
   ```
   Expected output:
   ```
   NAME           IMAGE                                 COMMAND               SERVICE      CREATED        STATUS        PORTS
   nginx          nginx:1.27-alpine                     "/docker-entrypoint…" nginx        5 seconds ago  Up 4 seconds  0.0.0.0:80->80/tcp
   ollama         ollama/ollama:latest                  "/bin/ollama serve"   ollama       5 seconds ago  Up 4 seconds
   open-webui     ghcr.io/open-webui/open-webui:main    "bash start.sh"       open-webui   5 seconds ago  Up 4 seconds
   ```

7. Pull a model into Ollama (this downloads the model weights into the named volume):
   ```bash
   docker exec ollama ollama pull llama3.2:3b
   ```

8. Open a browser and navigate to `http://<your-server-ip>`. The Open WebUI chat interface should appear, connected to Ollama.

9. View logs for a specific service:
   ```bash
   docker compose logs -f ollama
   ```

10. Stop the stack without deleting volumes:
    ```bash
    docker compose down
    # To also delete the named volumes (DELETES ALL DOWNLOADED MODELS):
    # docker compose down -v
    ```

### Example 4: Building and Pushing a Custom Nginx Image

You need a custom Nginx image that includes your organization's Nginx configuration baked in, so any team member can pull it and get the correct reverse proxy setup without managing external config files.

1. Ensure you are in the `~/ai-stack` directory with the `nginx/nginx.conf` file from Example 3.

2. Create a `Dockerfile` in the `nginx/` directory:
   ```bash
   cat > nginx/Dockerfile << 'EOF'
   FROM nginx:1.27-alpine

   # Remove the default Nginx config
   RUN rm /etc/nginx/conf.d/default.conf

   # Copy our custom config into the image
   COPY nginx.conf /etc/nginx/nginx.conf

   # Document the port
   EXPOSE 80

   # Inherit CMD from base image: nginx -g "daemon off;"
   EOF
   ```

3. Build the image from the `nginx/` directory:
   ```bash
   docker build -t myorg/ai-nginx:1.0 nginx/
   ```

4. Test the image locally by replacing the nginx service temporarily:
   ```bash
   docker run --rm -d --name test-nginx \
     --network ai-stack_ai-net \
     -p 80:80 \
     myorg/ai-nginx:1.0
   docker logs test-nginx
   docker stop test-nginx
   ```

5. Log in to Docker Hub and push the image:
   ```bash
   docker login
   docker push myorg/ai-nginx:1.0
   ```

6. Update `compose.yaml` to use the custom image:
   ```yaml
   nginx:
     image: myorg/ai-nginx:1.0
     # Remove the volumes.nginx.conf bind mount — config is now in the image
     container_name: nginx
     depends_on:
       - open-webui
     networks:
       - ai-net
     ports:
       - "80:80"
     restart: unless-stopped
   ```

7. Redeploy the nginx service with the new image:
   ```bash
   docker compose up -d --no-deps nginx
   ```

   The `--no-deps` flag restarts only `nginx` without touching `ollama` or `open-webui`.

## Common Pitfalls

### 1. Installing Docker from the Ubuntu Snap or apt default repository

**Why it happens:** Running `sudo apt install docker.io` or `sudo snap install docker` feels like the right way to install software on Ubuntu, and it works — but it installs a version that may be years old.

**Incorrect:**
```bash
sudo apt install docker.io
```

**Correct:** Follow the official repository method described in the installation section. Verify with `apt-cache policy docker-ce` that the candidate version comes from `download.docker.com` before installing.

---

### 2. Forgetting to log out and back in after `usermod -aG docker`

**Why it happens:** Group membership is read at login time. Adding your user to the `docker` group with `usermod` does not take effect in the current terminal session.

**Incorrect pattern (still requires sudo, despite the usermod):**
```bash
sudo usermod -aG docker "$USER"
docker ps   # Error: permission denied while connecting to the Docker daemon socket
```

**Correct:** Either run `newgrp docker` to start a new shell with the group active, or log out completely and log back in. Verify with `groups` that `docker` appears in the output.

---

### 3. Using `-v` with `docker compose down` and accidentally deleting model volumes

**Why it happens:** The Docker docs show `docker compose down -v` to fully clean up. The `-v` flag deletes all named volumes declared in the `compose.yaml`, which includes `ollama-models`. A 40 GB model download is destroyed silently.

**Incorrect:**
```bash
docker compose down -v   # Deletes ollama-models and webui-data
```

**Correct:**
```bash
docker compose down      # Stops and removes containers; volumes survive
# Only add -v when you explicitly want to wipe all data (fresh start)
```

---

### 4. Expecting `--gpus` to work without the NVIDIA Container Toolkit configured

**Why it happens:** The `--gpus` flag is part of Docker's CLI, but the actual GPU injection requires the runtime hook installed by `nvidia-ctk runtime configure`. Without it, Docker either returns an error or the container starts but sees no GPU.

**Incorrect:** Running `docker run --gpus all ...` immediately after installing Docker, without installing and configuring the toolkit.

**Correct:**
```bash
# Confirm toolkit is installed
nvidia-ctk --version

# Confirm runtime is configured in daemon.json
cat /etc/docker/daemon.json | grep -A3 '"nvidia"'

# Test
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

---

### 5. Using bridge network mode for Ollama when it needs GPU IPC

**Why it happens:** Bridge mode is the default and works for most services. Developers apply it uniformly without considering the CUDA IPC path.

**Incorrect `compose.yaml` snippet:**
```yaml
ollama:
  image: ollama/ollama:latest
  networks:
    - ai-net     # Bridge network — may interfere with CUDA IPC
  ports:
    - "11434:11434"
```

**Correct:**
```yaml
ollama:
  image: ollama/ollama:latest
  network_mode: host   # Bypasses bridge for GPU communication
  # Remove ports: section — not applicable in host mode
```

---

### 6. No log rotation configured, disk fills silently

**Why it happens:** Docker's default `json-file` logging driver appends indefinitely. A busy Ollama instance can write hundreds of megabytes per day. Operators notice only when the server becomes unresponsive because `/var/lib/docker` has consumed all disk space.

**Incorrect:** Starting the stack without any `logging` configuration in `compose.yaml` or `daemon.json`.

**Correct:**
```yaml
logging:
  driver: json-file
  options:
    max-size: "100m"
    max-file: "3"
```
Add this block to every service in `compose.yaml`, or configure it globally in `/etc/docker/daemon.json`.

---

### 7. Hardcoding secrets in `compose.yaml`

**Why it happens:** It is convenient to put `WEBUI_SECRET_KEY=abc123` directly in the YAML file. The problem surfaces when the file is pushed to a public or shared Git repository.

**Incorrect:**
```yaml
environment:
  - WEBUI_SECRET_KEY=mysupersecretkey123
```

**Correct:** Use an `env_file` pointing to a `.env` file that is listed in `.gitignore`:
```yaml
env_file:
  - .env
```
```bash
echo ".env" >> .gitignore
```

---

### 8. Pulling models before the Ollama container is fully started

**Why it happens:** `docker compose up -d` returns immediately after starting containers. Ollama takes a few seconds to initialize its HTTP server. Running `docker exec ollama ollama pull ...` immediately after `up` may hit the server before it is ready.

**Incorrect:**
```bash
docker compose up -d
docker exec ollama ollama pull llama3.2:3b   # May fail: connection refused
```

**Correct:** Wait for Ollama to report healthy, either by checking logs or using a small wait loop:
```bash
docker compose up -d
until docker exec ollama ollama list 2>/dev/null; do
  echo "Waiting for Ollama to start..."
  sleep 2
done
docker exec ollama ollama pull llama3.2:3b
```

## Summary

- Docker Engine is installed on Ubuntu and Debian via Docker's official apt repository, not the distribution's built-in packages; the post-installation step of adding your user to the `docker` group removes the need for `sudo` on every command.
- The core container lifecycle commands (`pull`, `run`, `ps`, `stop`, `rm`, `images`) manage the full lifetime of containers, while named volumes decouple persistent data (model weights, application databases) from the container lifecycle so data survives container recreation.
- The NVIDIA Container Toolkit adds a runtime hook that injects NVIDIA device files and CUDA libraries into containers at start time; after running `nvidia-ctk runtime configure --runtime=docker` and restarting the daemon, the `--gpus` flag and the `deploy.resources.reservations.devices` Compose block grant containers GPU access.
- A `compose.yaml` declaratively defines the entire AI stack — Ollama in host network mode for GPU IPC, Open WebUI and Nginx in a shared bridge network, named volumes for persistence, per-service log rotation, and `restart: unless-stopped` for automatic recovery — and the whole stack is managed with `docker compose up -d` and `docker compose down`.
- Custom images are built with a Dockerfile, tagged, and pushed to Docker Hub or a private registry, making the entire stack portable across machines and team members without manual environment setup.

## Further Reading

- [Install Docker Engine on Ubuntu — Docker Official Docs](https://docs.docker.com/engine/install/ubuntu/) — The canonical, step-by-step guide for installing Docker Engine from Docker's apt repository on Ubuntu; always check here before installing to ensure the commands match the current release.
- [NVIDIA Container Toolkit Installation Guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) — Official NVIDIA documentation for installing and configuring the container toolkit, including the `nvidia-ctk runtime configure` command and verification steps for all supported distributions.
- [Ollama Docker Hub and GitHub Documentation](https://github.com/ollama/ollama/blob/main/docs/docker.md) — Ollama's own Docker usage guide, covering GPU flags, volume mount paths, environment variables, and multi-GPU configuration specific to Ollama's runtime.
- [Open WebUI Documentation](https://docs.openwebui.com/) — Comprehensive reference for Open WebUI's environment variables, authentication configuration, and deployment options, essential for customizing the chat interface in the Compose stack.
- [Docker Compose Specification — deploy key](https://docs.docker.com/compose/compose-file/deploy/) — Reference for the `deploy` key in `compose.yaml`, covering `resources.limits`, `resources.reservations`, and the `devices` block used to request GPU access declaratively.
- [Docker Logging Drivers](https://docs.docker.com/config/containers/logging/configure/) — Full reference for Docker's logging subsystem, including all available drivers (`json-file`, `syslog`, `journald`, `loki`) and the configuration options for rotation and forwarding to external log aggregators.
- [Dockerfile Reference](https://docs.docker.com/reference/dockerfile/) — The authoritative reference for every Dockerfile instruction, including `RUN`, `COPY`, `ARG`, `ENV`, multi-stage `FROM`, and `HEALTHCHECK`; bookmark this when writing custom images.
- [Post-installation steps for Docker Engine on Linux](https://docs.docker.com/engine/install/linux-postinstall/) — Covers the `docker` group setup, configuring Docker to start on boot with systemd, and the `daemon.json` options for log rotation and insecure registries.
