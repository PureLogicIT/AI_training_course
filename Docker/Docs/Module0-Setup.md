# Module 0: Setup
> Subject: Docker | Difficulty: Beginner | Estimated Time: 90 minutes

## Objective

After completing this module, you will be able to explain what Docker is at a conceptual level and why it differs from a virtual machine, install Docker Engine on Ubuntu/Debian, Fedora/RHEL, or Arch Linux using the official repositories, install the Docker Compose plugin and verify it is working, understand when Docker Desktop makes sense on Linux versus Engine-only, configure the Docker daemon using `/etc/docker/daemon.json` (logging driver, registry mirror, data-root), enable and understand rootless Docker mode, and verify a complete, working installation using `docker info`, `docker version`, `docker run hello-world`, and `docker compose version`. By the end of this module your Linux machine will be fully set up and ready for every subsequent module in this series.

## Prerequisites

- A Linux machine or VM running a modern distribution: Ubuntu 22.04 LTS / 24.04 LTS, Debian 12, Fedora 40+, RHEL/AlmaLinux/Rocky Linux 8 or 9, or Arch Linux. Most steps also work on Windows Subsystem for Linux 2 (WSL2).
- `sudo` (administrator) privileges on the machine
- A terminal emulator and basic comfort typing commands (navigating directories, editing text files with `nano` or `vim`)
- An internet connection for downloading packages
- No prior Docker or containerization knowledge is assumed

## Key Concepts

### What Docker Is (and Is Not)

Docker is an open platform for packaging and running applications in lightweight, isolated environments called **containers**. The core problem Docker solves is the classic "works on my machine" failure: software behaves differently in development, testing, and production because those environments have different OS versions, different runtime versions, and different system libraries. Docker fixes this by bundling the application together with every dependency it needs — the runtime, system libraries, configuration — into a single portable artifact called an **image**. That image runs identically on a developer's laptop, a CI server, and a production host.

Docker is **not** a virtual machine. Understanding the distinction is important:

```
Virtual Machine Stack              Docker Container Stack
──────────────────────             ──────────────────────
  App A     |  App B                 App A    |  App B
  Bins/Libs |  Bins/Libs             Bins/Libs  Bins/Libs
  Guest OS  |  Guest OS              ─────────────────────
  Hypervisor                         Docker Engine
  Host OS                            Host OS
  Hardware                           Hardware
```

A virtual machine emulates a complete hardware stack and runs a full guest operating system. That costs gigabytes of disk space and tens of seconds to boot. A Docker container shares the **host kernel** and isolates only the user-space filesystem and processes. Containers are therefore much smaller (often tens of megabytes) and start in under a second.

### Core Architecture: Daemon, CLI, and Registry

Docker operates on a **client-server** model with three main pieces:

- **Docker daemon (`dockerd`)** — a background service that does the real work: building images, starting containers, managing networks and volumes. It exposes a REST API, usually over a UNIX socket at `/var/run/docker.sock`.
- **Docker CLI (`docker`)** — the command-line tool you type commands into. It sends those commands to the daemon over the REST API and displays the results.
- **Docker registry** — a remote store for images. Docker Hub (`hub.docker.com`) is the default public registry. Private registries (self-hosted or cloud-managed) are common in organizations.

When you run `docker run nginx`, the CLI sends a request to the daemon, the daemon checks whether it has the `nginx` image locally, pulls it from Docker Hub if not, then creates and starts the container.

### Images, Containers, and the Daemon

- **Image** — a read-only, layered template that contains the filesystem and configuration for running a process. Built from a `Dockerfile`. Named as `repository:tag` (e.g., `ubuntu:24.04`, `nginx:1.27-alpine`).
- **Container** — a running instance of an image. Docker adds a thin, writable layer on top of the image's read-only layers. That writable layer is discarded when the container is removed. Multiple containers can run from the same image simultaneously.

These concepts are covered in much more depth in Module 1. For now, all you need to understand is what you are installing — the daemon that manages containers, and the CLI you use to talk to it.

---

## Section 1: Installing Docker Engine on Linux

> **Important:** Always install Docker Engine from the **official Docker repository**, not from your distribution's default package manager. Distro-packaged versions (e.g., `apt install docker.io` on Ubuntu) are often several major releases behind. The snap package on Ubuntu is also not recommended — it has known permission and volume-mount limitations.

Before starting, check your distribution:

```bash
cat /etc/os-release
```

Look at the `ID` or `ID_LIKE` field to identify your distro family.

---

### 1.1 Ubuntu and Debian (apt)

These steps apply to **Ubuntu 22.04, 24.04** and **Debian 11, 12**. The procedure is identical — only the repository URL differs (`ubuntu` vs `debian`).

**Step 1: Install prerequisite packages**

```bash
sudo apt update
sudo apt install ca-certificates curl
```

**Step 2: Add Docker's official GPG key**

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

> For Debian, replace `ubuntu` in the URL with `debian`:
> `https://download.docker.com/linux/debian/gpg`

**Step 3: Add the Docker apt repository**

```bash
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

> For Debian, replace `https://download.docker.com/linux/ubuntu` with `https://download.docker.com/linux/debian`.

**Step 4: Update the package list and install Docker Engine**

```bash
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

This installs five packages:
- `docker-ce` — the Docker Engine daemon
- `docker-ce-cli` — the `docker` command-line client
- `containerd.io` — the container runtime Docker Engine uses internally
- `docker-buildx-plugin` — the BuildKit-powered build plugin
- `docker-compose-plugin` — the `docker compose` plugin (covered in Section 3)

**Step 5: Verify Docker started automatically**

On Ubuntu and Debian, `dockerd` starts automatically after installation. Confirm it is running:

```bash
sudo systemctl status docker
```

You should see `Active: active (running)` in the output. If it is not running, start it manually:

```bash
sudo systemctl start docker
```

---

### 1.2 Fedora (dnf)

These steps apply to **Fedora 40 and later**.

**Step 1: Add the Docker dnf repository**

```bash
sudo dnf config-manager addrepo \
  --from-repofile https://download.docker.com/linux/fedora/docker-ce.repo
```

**Step 2: Install Docker Engine**

```bash
sudo dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

When prompted, review and accept the Docker GPG key. Verify that its fingerprint matches:
```
060A 61C5 1B55 8A7F 742B 77AA C52F EB6B 621E 9F35
```

**Step 3: Enable and start the Docker service**

Unlike Ubuntu/Debian, Fedora does not start Docker automatically. You must enable and start it explicitly:

```bash
sudo systemctl enable --now docker
```

The `--now` flag combines `enable` (start on boot) and `start` (start immediately) into one command.

---

### 1.3 RHEL, AlmaLinux, and Rocky Linux (dnf)

These steps apply to **RHEL 8, 9, 10** and their community equivalents (AlmaLinux, Rocky Linux).

> **Note for RHEL users:** RHEL ships with Podman as its default container runtime, which may conflict with Docker. The first step removes any pre-installed conflicting packages.

**Step 1: Remove conflicting packages**

```bash
sudo dnf remove docker \
  docker-client \
  docker-client-latest \
  docker-common \
  docker-latest \
  docker-latest-logrotate \
  docker-logrotate \
  docker-engine \
  podman \
  runc
```

It is safe to run this even if none of these packages are installed — `dnf` will simply report that nothing was removed.

**Step 2: Add the Docker repository**

```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
```

**Step 3: Install Docker Engine**

```bash
sudo dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Accept the GPG key when prompted (fingerprint: `060A 61C5 1B55 8A7F 742B 77AA C52F EB6B 621E 9F35`).

**Step 4: Enable and start the Docker service**

```bash
sudo systemctl enable --now docker
```

---

### 1.4 Arch Linux (pacman)

Arch Linux carries Docker in its official community repositories, making installation straightforward.

**Step 1: Install Docker**

```bash
sudo pacman -S docker
```

This installs the `docker` package, which includes the Docker Engine daemon and the `docker` CLI. If you want the older standalone Compose binary as well (optional — see Section 3), you can install `docker-compose` here:

```bash
sudo pacman -S docker docker-compose
```

**Step 2: Enable and start the Docker service**

```bash
sudo systemctl enable --now docker
```

**Step 3: Verify the service is running**

```bash
sudo systemctl status docker
```

> **Arch note:** The Arch package tracks the upstream Docker release closely, so you will typically have a very recent version. Run `sudo pacman -Syu` to keep it updated along with the rest of your system.

---

### 1.5 Post-Installation Steps (All Distributions)

These steps apply regardless of which distribution you used above.

#### Add Your User to the `docker` Group

By default, the Docker socket is only accessible by `root`. Running `docker` commands requires `sudo` unless you add your user to the `docker` group.

```bash
# Create the docker group (it may already exist — that's fine)
sudo groupadd docker

# Add your current user to the group
sudo usermod -aG docker $USER

# Activate the group membership in the current shell session
newgrp docker
```

> **Security note:** Membership in the `docker` group is equivalent to root-level access on the host. Any user in this group can mount host paths into containers and escape normal file permission restrictions. On shared machines or servers, consider using rootless Docker instead (Section 5.2). On a personal development machine this trade-off is usually acceptable.

For the change to take full effect in all terminal sessions, log out and log back in (or reboot).

#### Verify the Installation with hello-world

Run the canonical Docker verification image:

```bash
docker run hello-world
```

Expected output (abbreviated):

```
Unable to find image 'hello-world:latest' locally
latest: Pulling from library/hello-world
...
Status: Downloaded newer image for hello-world:latest

Hello from Docker!
This message shows that your installation appears to be working correctly.

To generate this message, Docker took the following steps:
 1. The Docker client contacted the Docker daemon.
 2. The Docker daemon pulled the "hello-world" image from the Docker Hub.
 3. The Docker daemon created a new container from that image which runs the
    executable that produces the output you are currently reading.
 4. The Docker daemon streamed that output to the Docker client, which sent it
    to your terminal.
```

If you see this output, Docker Engine is correctly installed and your user can talk to the daemon without `sudo`.

---

## Section 2: Installing Docker Compose

### 2.1 Understanding v1 vs v2

There are two generations of Docker Compose that you will encounter in the wild:

| Feature | Docker Compose v1 (`docker-compose`) | Docker Compose v2 (`docker compose`) |
|---|---|---|
| Command | `docker-compose up` (hyphen) | `docker compose up` (space) |
| Implementation | Standalone Python binary, installed separately | Go plugin, integrated into the Docker CLI |
| Installation | `pip install docker-compose` or separate binary | Installed as `docker-compose-plugin` package |
| Maintenance | **Deprecated in 2023, no longer maintained** | Actively maintained, the only supported version |
| YAML files | `docker-compose.yml` | `compose.yaml` (also reads `docker-compose.yml`) |

**You should use v2 exclusively.** If you encounter a tutorial or codebase that uses `docker-compose` (with a hyphen), simply replace the hyphen with a space — v2 is backward-compatible with v1 YAML files in almost all cases.

### 2.2 Installing the Compose Plugin

If you followed the installation steps in Section 1, the `docker-compose-plugin` package was installed as part of the same `apt install` or `dnf install` command. The Compose plugin requires no additional installation steps on Ubuntu, Debian, Fedora, and RHEL.

**On Arch Linux**, the Compose plugin is included in the `docker` package from the official repositories. Run:

```bash
sudo pacman -S docker-compose
```

This installs both the standalone v1 binary and provides v2 functionality. On Arch, the preferred v2 invocation is `docker compose` (space), which maps to the CLI plugin.

### 2.3 Verifying Docker Compose

```bash
docker compose version
```

Expected output:

```
Docker Compose version v2.29.x
```

The exact patch version will vary. As long as you see `v2.x.x`, you have the modern plugin installed. If the command is not found, ensure the `docker-compose-plugin` package is installed and your Docker Engine installation is complete.

> **Tip:** If you see an error like `docker: 'compose' is not a docker command`, the plugin package was not installed. Re-run the `apt install` or `dnf install` command from Section 1 and make sure `docker-compose-plugin` is included.

---

## Section 3: Docker Desktop on Linux (Optional)

Docker Desktop is a GUI application that bundles Docker Engine, Docker Compose, Docker Scout, and an integrated Kubernetes cluster behind a graphical interface. It was originally available only on macOS and Windows, but Docker has offered a Linux version (DEB and RPM packages) since 2022.

### When Docker Desktop Makes Sense on Linux

| Scenario | Recommendation |
|---|---|
| Personal development workstation with a desktop environment | Docker Desktop is a reasonable choice — it provides a visual dashboard for containers, images, and volumes |
| Headless server, VM, or CI environment | Docker Engine only — Desktop requires a desktop environment (GNOME, KDE, etc.) and adds memory overhead |
| Learning Docker fundamentals | Either works; this training series uses the Engine CLI so all commands apply to both |
| You need integrated Kubernetes for local testing | Docker Desktop includes a single-node Kubernetes cluster you can enable with one click |

### How Docker Desktop Differs from Engine-Only on Linux

Unlike macOS and Windows (where Docker Desktop runs a Linux VM internally), Docker Desktop for Linux still runs containers directly on the host kernel — but it wraps the daemon in its own isolated context. This means Docker Desktop and a bare Docker Engine installation store their containers and images separately; a container started in one will not appear in the other.

### Where to Get It

Docker Desktop for Linux is distributed as `.deb` (Ubuntu/Debian) and `.rpm` (Fedora/RHEL) packages. The download page and installation instructions are maintained at:

**[https://docs.docker.com/desktop/setup/install/linux/](https://docs.docker.com/desktop/setup/install/linux/)**

This training series focuses exclusively on Docker Engine and the CLI — all commands in subsequent modules work identically with or without Desktop installed.

---

## Section 4: Basic Post-Install Configuration

### 4.1 The Daemon Configuration File

The Docker daemon reads its configuration from `/etc/docker/daemon.json` at startup. This file does not exist by default — you create it. It uses standard JSON syntax.

After editing `daemon.json`, you must reload the daemon to apply the changes:

```bash
sudo systemctl reload docker
# If reload is not supported, restart instead:
sudo systemctl restart docker
```

> **Tip:** Validate your JSON before restarting — a syntax error in `daemon.json` will prevent the daemon from starting. Use `python3 -m json.tool /etc/docker/daemon.json` to check syntax.

#### Setting the Default Logging Driver

By default, Docker uses the `json-file` logging driver, which writes container output to JSON files on disk. This is fine for development but can consume significant disk space in long-running environments if log rotation is not configured. A minimal but sensible configuration caps log file size and count:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

This configuration caps each log file at 10 MB and retains at most 3 rotated files per container (30 MB total per container).

Alternative drivers include `journald` (integrates with systemd's journal, useful on Fedora/RHEL) and `local` (a compact binary format with built-in rotation). For most beginners, `json-file` with rotation configured is the right starting point.

#### Configuring a Registry Mirror

If you frequently pull images from Docker Hub and want to reduce bandwidth usage or improve pull speeds, you can configure a registry mirror. Organizations often run an internal mirror (e.g., using Harbor or a cloud registry) so that frequently-used base images are cached locally.

```json
{
  "registry-mirrors": ["https://your-mirror-host.example.com"]
}
```

Replace `https://your-mirror-host.example.com` with the URL of your mirror. If you do not have a mirror set up, omit this key entirely.

#### Changing the Data Root Directory

By default, Docker stores all of its data — images, containers, volumes, build cache — in `/var/lib/docker`. If your root partition is small, you can move this to a larger disk:

```json
{
  "data-root": "/mnt/large-disk/docker"
}
```

Ensure the target directory exists before restarting the daemon:

```bash
sudo mkdir -p /mnt/large-disk/docker
```

> **Warning:** Changing `data-root` on an existing installation does not automatically migrate existing images and containers. You will need to manually copy data or accept starting fresh. Plan this before you have significant data in Docker.

#### A Complete Example `daemon.json`

The following combines all three options. You would only include the keys you actually need — this is shown together for illustration:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "registry-mirrors": ["https://your-mirror-host.example.com"],
  "data-root": "/mnt/large-disk/docker"
}
```

Create or edit the file:

```bash
sudo nano /etc/docker/daemon.json
```

Then apply the configuration:

```bash
sudo systemctl restart docker
```

---

### 4.2 Rootless Docker Mode

#### What It Is

Rootless mode lets the Docker daemon and all containers run as a regular (non-root) user rather than as root. Because the daemon itself never runs as root, a compromised daemon or container cannot directly affect root-owned resources on the host. This provides a significantly stronger security boundary than the standard installation, where the daemon runs as root and `docker` group membership gives users effective root access.

#### When to Use Rootless Mode

| Use rootless if... | Use standard (root daemon) if... |
|---|---|
| You are on a multi-user machine where security matters | You are on a single-user personal development machine |
| Your organization requires non-root container execution | You need full feature compatibility (some edge-case features are unavailable in rootless mode) |
| You are not the sole administrator of the machine | Performance on the host network is critical (rootless uses a user-space network stack) |

For most beginners setting up a personal development environment, the standard installation from Section 1 with the docker group is appropriate. Rootless mode is worth learning once you have more experience with Docker.

#### Prerequisites

Install the required packages before running the setup tool:

```bash
# Ubuntu / Debian
sudo apt install uidmap dbus-user-session

# Fedora / RHEL
sudo dnf install shadow-utils dbus-daemon

# Arch Linux
sudo pacman -S shadow
```

Your user also needs entries in `/etc/subuid` and `/etc/subgid`. Check:

```bash
grep $USER /etc/subuid
grep $USER /etc/subgid
```

Each line should contain at least 65,536 subordinate IDs (e.g., `youruser:100000:65536`). If neither file has an entry for your user, add one:

```bash
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER
```

#### Enabling Rootless Mode

If you already have a system-wide Docker daemon running, disable it first to avoid conflicts:

```bash
sudo systemctl disable --now docker
```

Then run the rootless setup tool, which is installed alongside Docker Engine:

```bash
dockerd-rootless-setuptool.sh install
```

The tool configures a systemd user service and prints the environment variables you need to add to your shell profile (e.g., `~/.bashrc`):

```bash
export PATH=/usr/bin:$PATH
export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock
```

Add these lines to your `~/.bashrc` or `~/.bash_profile`, then reload:

```bash
source ~/.bashrc
```

Manage the rootless daemon with `systemctl --user`:

```bash
# Start the rootless daemon
systemctl --user start docker

# Enable it to start automatically on login
systemctl --user enable docker

# To keep it running after logout (requires lingering):
sudo loginctl enable-linger $USER
```

Verify rootless mode is active:

```bash
docker info | grep rootless
# Should output: rootless: true
```

---

## Section 5: Verifying the Installation

Once Docker Engine is installed, run these four checks. Each command tells you something specific about your setup.

### 5.1 `docker version`

```bash
docker version
```

Sample output:

```
Client: Docker Engine - Community
 Version:           29.0.3
 API version:       1.48
 Go version:        go1.22.10
 Git commit:        b17ef9d
 Built:             Thu Jan 30 12:34:56 2025
 OS/Arch:           linux/amd64
 Context:           default

Server: Docker Engine - Community
 Engine:
  Version:          29.0.3
  API version:      1.48 (minimum version 1.24)
  Go version:       go1.22.10
  Git commit:       a41ad02
  Built:            Thu Jan 30 12:34:56 2025
  OS/Arch:          linux/amd64
  Experimental:     false
 containerd:
  Version:          1.7.22
  GitCommit:        7f7fdf...
 runc:
  Version:          1.1.15
  GitCommit:        v1.1.15-0-g9dde...
```

**What to look for:**
- `Client` and `Server` both have version numbers — if only Client is shown, the daemon is not running or your user cannot reach the socket.
- `API version` on the client and server should match (or the server's minimum should be below the client's version).
- `OS/Arch` confirms you installed the right build for your platform.

### 5.2 `docker info`

```bash
docker info
```

Sample output (abbreviated):

```
Client:
 Version:    29.0.3
 Context:    default
 ...

Server:
 Containers: 0
  Running: 0
  Paused: 0
  Stopped: 0
 Images: 0
 Server Version: 29.0.3
 Storage Driver: overlay2
 Logging Driver: json-file
 Cgroup Driver: systemd
 ...
 Docker Root Dir: /var/lib/docker
 ...
 Kernel Version: 6.8.0-51-generic
 Operating System: Ubuntu 24.04.1 LTS
 OSType: linux
 Architecture: x86_64
 Total Memory: 15.59GiB
 ...
```

**What to look for:**
- `Containers: 0` and `Images: 0` are expected on a fresh install.
- `Storage Driver: overlay2` — this is the modern default and correct for most Linux kernels.
- `Logging Driver: json-file` — reflects your `daemon.json` configuration (or the default if you have not created that file yet).
- `Docker Root Dir` — confirms the data directory; should reflect your `data-root` if you changed it.
- `Cgroup Driver: systemd` — Docker should use `systemd` as the cgroup driver on systemd-based distributions. If it shows `cgroupfs`, this is a known compatibility issue; consult the Docker documentation for your distro.

### 5.3 `docker run hello-world`

You ran this in Section 1 as part of post-install verification. Run it again now to confirm everything is still working after any daemon configuration changes:

```bash
docker run hello-world
```

You should see the "Hello from Docker!" message. If you do not, check `docker info` for errors and confirm the daemon is running with `sudo systemctl status docker`.

### 5.4 `docker compose version`

```bash
docker compose version
```

Expected output:

```
Docker Compose version v2.29.x
```

Any `v2.x.x` output confirms the Compose plugin is correctly installed. If you see `command not found` or `'compose' is not a docker command`, the `docker-compose-plugin` package needs to be reinstalled.

---

## Best Practices

1. **Always use the official Docker repository, never the distro-default package.** Distribution packages like Ubuntu's `docker.io` can be several major versions behind. Sticking with `download.docker.com` ensures you have security patches and current feature support.

2. **Configure log rotation in `daemon.json` before running any long-lived containers.** Without it, log files for busy containers can fill your disk over days or weeks. The `max-size` and `max-file` options in Section 4.1 are a sensible starting point.

3. **Understand the security implications of the `docker` group before adding users to it.** On a personal development machine, adding yourself to the `docker` group is a convenient and reasonable choice. On a multi-user server, use rootless mode or `sudo` instead.

4. **Pin Docker Engine versions in automated setup scripts.** The `apt install docker-ce` and `dnf install docker-ce` commands install the latest available version, which can change. For reproducible server provisioning, pin a specific version using `apt install docker-ce=5:29.x.x-1~ubuntu.24.04~noble` or the dnf equivalent.

5. **Use `docker compose` (v2, no hyphen) for all new work.** If you encounter old documentation or scripts using `docker-compose` (with a hyphen), that is the deprecated v1 Python binary. The syntax is nearly identical — just replace the hyphen with a space.

6. **Validate `daemon.json` before restarting the daemon.** A JSON syntax error will prevent `dockerd` from starting, leaving you without Docker until the error is fixed. Run `python3 -m json.tool /etc/docker/daemon.json` as a quick check.

7. **Enable the Docker service at boot if you want it available automatically.** `sudo systemctl enable docker` ensures Docker starts when the machine reboots, which matters for servers and development machines where you expect Docker to always be present.

---

## Hands-on Examples

### Example 1: Complete Install from Scratch and Verify (Ubuntu 24.04)

This example walks through the entire installation sequence end-to-end on a fresh Ubuntu 24.04 machine and verifies each step.

1. Update the package list and install prerequisites.

```bash
sudo apt update
sudo apt install ca-certificates curl
```

2. Create the keyring directory and download Docker's GPG key.

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

3. Add the Docker apt repository.

```bash
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
```

4. Install Docker Engine and the Compose plugin.

```bash
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

5. Add your user to the `docker` group and activate it.

```bash
sudo usermod -aG docker $USER
newgrp docker
```

6. Run all four verification commands.

```bash
docker version
docker info
docker run hello-world
docker compose version
```

Expected final output from `docker run hello-world`:

```
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

---

### Example 2: Configure the Daemon with Log Rotation

In this example you will create a `daemon.json` configuration file that enables log rotation and restart the daemon to apply it.

1. Check that no `daemon.json` exists yet (expected on a fresh install).

```bash
sudo cat /etc/docker/daemon.json
```

Expected output:

```
cat: /etc/docker/daemon.json: No such file or directory
```

2. Create the configuration file.

```bash
sudo tee /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
```

3. Validate the JSON syntax.

```bash
python3 -m json.tool /etc/docker/daemon.json
```

Expected output:

```json
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    }
}
```

If you see a `json.decoder.JSONDecodeError`, there is a syntax error — fix it before proceeding.

4. Restart the Docker daemon to apply the change.

```bash
sudo systemctl restart docker
```

5. Confirm the new logging driver is active.

```bash
docker info | grep "Logging Driver"
```

Expected output:

```
 Logging Driver: json-file
```

6. Run a test container and verify its log configuration.

```bash
docker run -d --name log-test nginx:alpine
docker inspect log-test --format '{{.HostConfig.LogConfig}}'
```

Expected output (reflects the daemon default you set):

```
{json-file map[max-file:3 max-size:10m]}
```

7. Clean up.

```bash
docker stop log-test
docker rm log-test
docker rmi nginx:alpine
```

---

## Common Pitfalls

### Pitfall 1: Installing from the Distro Repository Instead of Docker's Official Repository

**Description:** Running `sudo apt install docker.io` or `sudo apt install docker` installs the distribution-maintained package, which may be several major versions behind the current Docker Engine release.

**Why it happens:** It is faster to type, and the distro package is right there in the default repository. Beginners often do not realize there is a meaningful difference.

**Incorrect pattern:**
```bash
sudo apt install docker.io
# Or on Ubuntu, installing the snap:
sudo snap install docker
```

**Correct pattern:**
```bash
# Follow the official repository setup in Section 1.1
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

---

### Pitfall 2: Forgetting to Run `newgrp docker` After Adding Yourself to the Group

**Description:** After running `sudo usermod -aG docker $USER`, the group membership is not active in the current shell session. Running `docker run hello-world` still fails with a permissions error.

**Why it happens:** Unix group changes take effect only for new login sessions. The current shell was started before the group change, so it does not see it yet.

**Symptom:**
```
permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock
```

**Correct pattern:**
```bash
# Option A: Activate in the current shell immediately
newgrp docker

# Option B: Log out and log back in completely
exit
# (re-open terminal)
```

---

### Pitfall 3: JSON Syntax Error in `daemon.json` Prevents the Daemon from Starting

**Description:** A missing comma, trailing comma, or mismatched brace in `/etc/docker/daemon.json` causes `dockerd` to fail to start after a restart. All Docker commands stop working.

**Why it happens:** JSON is strict about commas and structure. Trailing commas (valid in JavaScript) are not valid in JSON. This is an easy mistake when editing the file manually.

**Symptom:**
```
$ docker info
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

**Incorrect `daemon.json`:**
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3",
  },
}
```
(Trailing commas after `"3"` and after the `log-opts` block are invalid JSON.)

**Correct pattern — validate before restarting:**
```bash
python3 -m json.tool /etc/docker/daemon.json && sudo systemctl restart docker
```

---

### Pitfall 4: Using `docker-compose` (Hyphen) When Only v2 Is Installed

**Description:** Following an older tutorial that uses `docker-compose up` on a system where only the v2 plugin is installed results in a `command not found` error.

**Why it happens:** The v1 standalone binary is a separate package from the v2 plugin. Many tutorials written before 2023 use the v1 syntax.

**Symptom:**
```
bash: docker-compose: command not found
```

**Correct pattern:**
```bash
# Replace the hyphen with a space in every command
docker compose up -d
docker compose down
docker compose logs -f
```

---

### Pitfall 5: The Docker Service Is Not Enabled at Boot (Fedora / RHEL / Arch)

**Description:** Docker works fine right after installation, but stops working after a reboot because the service was started but not enabled.

**Why it happens:** On Fedora, RHEL, and Arch Linux, `systemctl start docker` starts the service for the current session only. `systemctl enable docker` is required to make it persist across reboots. Ubuntu and Debian enable the service automatically on package install.

**Symptom:**
```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```
(Appears only after a reboot)

**Correct pattern:**
```bash
# Enable AND start in one command
sudo systemctl enable --now docker
```

---

## Summary

- Docker packages applications and their dependencies into lightweight containers that share the host kernel, making them far smaller and faster than virtual machines.
- Docker Engine consists of the daemon (`dockerd`), the CLI (`docker`), and communicates with registries like Docker Hub to pull images.
- Always install Docker Engine from Docker's official repository (`download.docker.com`), not from your distribution's default packages, to get the current stable release.
- The `docker-compose-plugin` package provides the modern `docker compose` (v2) command, which replaces the deprecated standalone `docker-compose` (v1) Python binary.
- Post-install, add your user to the `docker` group (and understand the security trade-off), enable the `docker` systemd service at boot, and confirm the installation with `docker run hello-world`.
- The daemon configuration file `/etc/docker/daemon.json` controls the logging driver, registry mirrors, and data directory; always validate JSON syntax before restarting the daemon.
- Rootless Docker mode runs the entire daemon as a non-root user, providing a stronger security posture for multi-user machines — worth considering once you are comfortable with the standard setup.

## Further Reading

- [Install Docker Engine — Official Docs](https://docs.docker.com/engine/install/) — The top-level installation landing page for all supported Linux distributions, Windows, and macOS; the authoritative starting point and the first place to check if installation steps have changed.
- [Linux Post-Installation Steps — Official Docs](https://docs.docker.com/engine/install/linux-postinstall/) — The official guide to the docker group, systemd service configuration, and other recommended steps after installing Docker Engine; covers the security implications of docker group membership in detail.
- [Docker Daemon Configuration Overview — Official Docs](https://docs.docker.com/engine/daemon/) — The authoritative reference for `daemon.json`, covering every configuration option available to the daemon including logging, storage drivers, networking, and TLS settings.
- [Configure Logging Drivers — Official Docs](https://docs.docker.com/engine/logging/configure/) — Explains every logging driver available in Docker (json-file, journald, local, syslog, and more), their options, and when to prefer one over another; essential reading before deploying anything long-lived.
- [Rootless Mode — Official Docs](https://docs.docker.com/engine/security/rootless/) — The complete guide to running Docker without root privileges, including prerequisites, installation, known limitations, and how to manage the rootless daemon with systemd user services.
- [Install Docker Desktop on Linux — Official Docs](https://docs.docker.com/desktop/setup/install/linux/) — Distribution-specific download and installation instructions for Docker Desktop on Linux; covers Ubuntu, Debian, Fedora, and Arch-based distributions.
- [History and Development of Docker Compose — Official Docs](https://docs.docker.com/compose/intro/history/) — Explains how Docker Compose evolved from the standalone v1 Python tool to the v2 Go plugin, why v1 was deprecated, and what changed between versions; useful context for understanding why the hyphen-vs-space distinction matters.
- [Docker Engine v29 Release Notes — Official Docs](https://docs.docker.com/engine/release-notes/29/) — Release notes for the Docker Engine v29 series (current stable as of 2025–2026); covers the nftables firewall backend, containerd image store changes, and security updates relevant to fresh installations.
