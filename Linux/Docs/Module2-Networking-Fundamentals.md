# Module 2: Networking Fundamentals
> Subject: Linux | Difficulty: Beginner-to-Intermediate | Estimated Time: 150 minutes

## Objective

After completing this module, you will be able to inspect and configure Linux network interfaces using `ip addr`, `ip link`, and `nmcli`; assign static IP addresses and understand when to use DHCP vs. static addressing; configure DNS resolution through `/etc/resolv.conf` and `systemd-resolved`; set up SSH with key-based authentication, write a productive `~/.ssh/config` file, and use SSH local and remote port forwarding to securely expose and reach AI services; identify the standard ports used by common AI and monitoring tools (Ollama, Jupyter, Grafana, and others); inspect active network connections with `ss` and the legacy `netstat`; and manage hostname and `/etc/hosts` entries so services are reachable by name rather than raw IP address.

All skills are framed around a concrete scenario you will encounter immediately: connecting to a remote Linux server that runs GPU-accelerated AI workloads, securely reaching its services from your laptop, and making those services addressable by meaningful names.

## Prerequisites

- Module 1 (Linux Basics) — familiarity with the shell, file permissions, text editors, and running commands as root with `sudo`
- A Linux machine or VM to practice on (Ubuntu 22.04 LTS or Ubuntu 24.04 LTS is assumed; commands work on Debian, Fedora, and RHEL-family systems with minor differences noted inline)
- Basic understanding of what a server and a client are at a conceptual level
- No prior networking knowledge beyond knowing that computers have IP addresses is assumed

## Key Concepts

### Why Networking Matters for AI Development

When you train a model or run inference on a remote GPU box, every interaction you have with that workload travels over a network. You SSH into the server to launch jobs, your Jupyter notebook is served over HTTP, Ollama exposes an API on port 11434, and Grafana shows GPU metrics on port 3000. None of that works — or works safely — without a solid grasp of how Linux handles network configuration.

This module teaches networking from the operational perspective: how to see what your server's network looks like, how to make it behave the way you need, and how to reach services securely without punching unnecessary holes in a firewall.

### The Network Interface: Linux's View of a NIC

Linux models every network connection — a physical Ethernet port, a Wi-Fi card, a virtual Ethernet adapter inside a VM, a loopback — as a **network interface**. Each interface has:

- A **name** (e.g., `eth0`, `ens3`, `enp3s0`, `wlan0`, `lo`). Modern systemd-based distributions use "predictable" names like `ens3` or `enp3s0` that encode the bus position of the hardware. Cloud VMs typically show `eth0` or `ens3`.
- A **MAC address** — a hardware-level 48-bit identifier unique to the physical (or virtual) NIC.
- One or more **IP addresses** with associated prefix lengths (e.g., `192.168.1.10/24`).
- A **state**: `UP` (active) or `DOWN` (inactive).

The loopback interface `lo` with address `127.0.0.1` is always present and always up. Traffic sent to `127.0.0.1` (also known as `localhost`) never leaves the machine — it loops back internally. This matters for AI development: when you run Ollama locally, it listens on `127.0.0.1:11434` by default, which means it is reachable only from processes on the same machine unless you explicitly bind it to a network-facing interface or create an SSH tunnel.

### IP Addressing: DHCP vs. Static

Every host on a network needs an IP address. There are two ways a Linux server gets one:

**DHCP (Dynamic Host Configuration Protocol)** — A DHCP server (usually your router or a cloud provider's infrastructure) automatically assigns an IP address, subnet mask, default gateway, and DNS server addresses when the interface comes up. The lease expires after a set time and the address may change on renewal. DHCP is the default in most Linux desktop and cloud installations and is suitable for:
- Development laptops and workstations
- Cloud instances that manage addressing through their own infrastructure (AWS, GCP, Azure all use DHCP internally)
- Any machine where you do not need to predict the address in advance

**Static (manual) addressing** — You permanently assign a specific IP address that never changes unless you reconfigure it. Static addressing is appropriate for:
- On-premises GPU servers that other machines need to reach by a predictable address
- DNS servers, NFS servers, and anything that acts as infrastructure
- Machines where you want hostnames in `/etc/hosts` or DNS to remain permanently correct

In practice, cloud providers handle addressing for you through DHCP with stable leases, and you rarely need to set a static IP on a cloud VM. The skill matters most for bare-metal on-premises servers and local lab environments.

### The `ip` Command Suite

The `ip` command (part of the `iproute2` package, installed by default on all major Linux distributions) is the modern, authoritative tool for inspecting and modifying the network stack. It replaces the older `ifconfig` and `route` commands, which are still present on many systems but are considered deprecated.

The general structure is:

```
ip [OPTIONS] OBJECT { COMMAND | help }
```

The objects you will use most often are `addr` (IP addresses), `link` (network interfaces), and `route` (routing table).

#### `ip addr` — View and Manage IP Addresses

```bash
# Show all interfaces and their IP addresses
ip addr show

# Short form (identical output)
ip addr

# Show only a specific interface
ip addr show dev ens3

# Add an IP address to an interface (requires root)
sudo ip addr add 192.168.1.50/24 dev ens3

# Remove an IP address from an interface
sudo ip addr del 192.168.1.50/24 dev ens3
```

Sample output of `ip addr show` on a typical cloud VM:

```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host
       valid_lft forever preferred_lft forever
2: ens3: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP
    link/ether fa:16:3e:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 10.0.0.5/24 brd 10.0.0.255 scope global dynamic ens3
       valid_lft 85942sec preferred_lft 85942sec
    inet6 fe80::f816:3eff:feab:cdef/64 scope link
       valid_lft forever preferred_lft forever
```

Key fields to read:
- `state UP` — the interface is active
- `inet 10.0.0.5/24` — the IPv4 address and prefix (24 = 255.255.255.0 subnet mask)
- `dynamic` — address was assigned by DHCP
- `valid_lft 85942sec` — seconds until the DHCP lease expires
- `inet6 fe80::...` — a link-local IPv6 address, auto-assigned and not routable beyond the local segment

#### `ip link` — View and Control Interface State

```bash
# Show all interfaces (link layer info, no IP addresses)
ip link show

# Show a specific interface
ip link show dev ens3

# Bring an interface up
sudo ip link set ens3 up

# Bring an interface down
sudo ip link set ens3 down
```

`ip link` shows the same interfaces as `ip addr` but without IP address information. It is most useful when you need to bring an interface up or down, change its MTU, or check its MAC address.

#### `ip route` — View and Manage the Routing Table

```bash
# Show the routing table
ip route show

# Show which interface and gateway a packet to a specific host would use
ip route get 8.8.8.8

# Add a default gateway
sudo ip route add default via 10.0.0.1 dev ens3

# Add a static route to a specific subnet
sudo ip route add 172.16.0.0/16 via 10.0.0.254 dev ens3

# Delete a route
sudo ip route del 172.16.0.0/16
```

Sample `ip route show` output:

```
default via 10.0.0.1 dev ens3 proto dhcp src 10.0.0.5 metric 100
10.0.0.0/24 dev ens3 proto kernel scope link src 10.0.0.5
```

The `default` line is the **default gateway** — the router that handles all traffic not destined for a locally connected subnet.

### NetworkManager and `nmcli`

On Ubuntu Desktop, Fedora, and RHEL/CentOS systems, **NetworkManager** manages network connections persistently — meaning configuration survives reboots. `nmcli` is its command-line interface. On Ubuntu Server 22.04 and later, **Netplan** (backed by either NetworkManager or `networkd`) is the default.

`nmcli` is most useful when:
- You are on a NetworkManager-managed system and want changes to persist without editing YAML files
- You need to create, modify, or delete connection profiles
- You want to connect to Wi-Fi from the terminal

```bash
# Show all connections (both active and inactive)
nmcli connection show

# Show only active connections
nmcli connection show --active

# Show detailed info about a specific connection
nmcli connection show "Wired connection 1"

# Show device status (maps interface names to their connection profiles)
nmcli device status

# Show brief device and IP info
nmcli device show ens3

# Bring a connection up by its profile name
sudo nmcli connection up "Wired connection 1"

# Bring a connection down
sudo nmcli connection down "Wired connection 1"

# Create a new static IP connection profile
sudo nmcli connection add \
  type ethernet \
  con-name "gpu-server-static" \
  ifname ens3 \
  ipv4.method manual \
  ipv4.addresses 192.168.1.100/24 \
  ipv4.gateway 192.168.1.1 \
  ipv4.dns "1.1.1.1 8.8.8.8"

# Apply the new profile
sudo nmcli connection up "gpu-server-static"

# Modify an existing connection (e.g., change DNS)
sudo nmcli connection modify "gpu-server-static" ipv4.dns "1.1.1.1"
sudo nmcli connection up "gpu-server-static"
```

On Ubuntu Server with Netplan, persistent configuration lives in `/etc/netplan/*.yaml`. A minimal static IP configuration looks like:

```yaml
# /etc/netplan/00-installer-config.yaml
network:
  version: 2
  ethernets:
    ens3:
      dhcp4: false
      addresses:
        - 192.168.1.100/24
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses:
          - 1.1.1.1
          - 8.8.8.8
```

Apply Netplan changes with:

```bash
sudo netplan apply
```

Note: `netplan try` applies the configuration with a 120-second timeout — if you do not confirm, it rolls back automatically. Use this on remote servers to avoid locking yourself out.

### DNS Configuration

DNS (Domain Name System) translates human-readable names like `gpu-box.internal` into IP addresses. On a Linux server, name resolution goes through several layers:

1. `/etc/hosts` — checked first; static local overrides (covered in the next section)
2. `/etc/resolv.conf` — specifies DNS nameserver addresses
3. `systemd-resolved` — a local caching DNS stub resolver used on systemd-based distributions

#### `/etc/resolv.conf`

On systems **without** `systemd-resolved`, `/etc/resolv.conf` is the primary DNS configuration file:

```
# /etc/resolv.conf
nameserver 1.1.1.1
nameserver 8.8.8.8
search internal.company.com
```

- `nameserver` — the IP address of a DNS server to query (up to three entries, queried in order)
- `search` — a domain suffix appended when you query a short name. With `search internal.company.com`, querying `gpu-box` automatically tries `gpu-box.internal.company.com`

#### `systemd-resolved`

On Ubuntu 20.04 and later, `/etc/resolv.conf` is typically a **symlink** to a stub file managed by `systemd-resolved`:

```bash
ls -la /etc/resolv.conf
# /etc/resolv.conf -> ../run/systemd/resolve/stub-resolv.conf
```

`systemd-resolved` runs as a local service on `127.0.0.53:53`. All DNS queries go to this stub, which caches results and forwards upstream. Key commands:

```bash
# Show current DNS server configuration per interface
resolvectl status

# Look up a hostname (uses systemd-resolved, more informative than nslookup)
resolvectl query gpu-box.internal

# Show DNS cache statistics
resolvectl statistics

# Flush the DNS cache
sudo resolvectl flush-caches

# Show which DNS server resolved a specific name
resolvectl query --legend=yes github.com
```

To set a per-interface DNS server using `systemd-resolved` on a Netplan system, add it to the Netplan YAML (shown above). To set it for the entire system without Netplan, edit `/etc/systemd/resolved.conf`:

```ini
# /etc/systemd/resolved.conf
[Resolve]
DNS=1.1.1.1 8.8.8.8
FallbackDNS=9.9.9.9
Domains=~internal.company.com
```

Then restart the service:

```bash
sudo systemctl restart systemd-resolved
```

### SSH: Secure Shell

SSH is how you interact with remote Linux servers. For AI development, SSH is not just a login tool — it is a secure tunnel that lets you run Jupyter notebooks, forward Ollama API calls, and access monitoring dashboards without exposing those services to the public internet.

#### Installing and Starting the SSH Server

```bash
# Install OpenSSH server (Ubuntu/Debian)
sudo apt update && sudo apt install -y openssh-server

# Check if it is running
sudo systemctl status ssh

# Enable it to start on boot and start it now
sudo systemctl enable --now ssh
```

On Fedora/RHEL, the service is named `sshd`:

```bash
sudo dnf install -y openssh-server
sudo systemctl enable --now sshd
```

#### Key-Based Authentication

Password authentication over SSH is vulnerable to brute-force attacks. Key-based authentication is strongly preferred for any server exposed to the internet or hosting production workloads.

The mechanism:
1. You generate an **ED25519 key pair** on your local machine — a private key (never leaves your machine) and a public key (safe to share)
2. You copy the public key to the remote server's `~/.ssh/authorized_keys`
3. When you SSH in, the server challenges you using your public key and your local machine proves identity by signing the challenge with your private key — no password ever crosses the network

```bash
# Step 1: Generate an ED25519 key pair on your LOCAL machine
# -C adds a comment (your email helps identify the key later)
ssh-keygen -t ed25519 -C "you@yourdomain.com"
# Accept the default path (~/.ssh/id_ed25519) or specify one
# Set a passphrase to encrypt the private key at rest (strongly recommended)
```

This creates two files:
- `~/.ssh/id_ed25519` — your private key (permissions must be `600`)
- `~/.ssh/id_ed25519.pub` — your public key (safe to copy anywhere)

```bash
# Step 2: Copy the public key to the remote server
# ssh-copy-id handles creating ~/.ssh and authorized_keys with correct permissions
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@192.168.1.100

# If ssh-copy-id is not available, do it manually:
cat ~/.ssh/id_ed25519.pub | ssh user@192.168.1.100 \
  "mkdir -p ~/.ssh && chmod 700 ~/.ssh && \
   cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

```bash
# Step 3: Test key-based login
ssh user@192.168.1.100
# You should be prompted for your key passphrase (if set), not a server password
```

Once key-based auth works, disable password authentication on the server for security:

```bash
# On the SERVER: edit /etc/ssh/sshd_config
sudo nano /etc/ssh/sshd_config
```

Set or confirm these lines:

```
PasswordAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
PermitRootLogin no
```

Restart the SSH daemon to apply:

```bash
sudo systemctl restart ssh
```

**Important:** Before disabling password auth, confirm you can log in with your key in a separate terminal session. Locking yourself out of a remote server is a serious mistake.

#### The SSH Client Config File (`~/.ssh/config`)

Typing `ssh user@192.168.1.100 -p 2222 -i ~/.ssh/gpu_key` every time is tedious and error-prone. The `~/.ssh/config` file lets you define named host profiles with all parameters pre-set.

```
# ~/.ssh/config

# A remote GPU training server
Host gpu-box
    HostName 203.0.113.45
    User ubuntu
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3

# A second server accessed through a jump host
Host private-gpu
    HostName 10.10.0.5
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
    ProxyJump bastion

Host bastion
    HostName 203.0.113.10
    User ec2-user
    IdentityFile ~/.ssh/bastion_key
    Port 22
```

With this config, `ssh gpu-box` replaces the full command. The most useful options:

| Option | Purpose |
|---|---|
| `Host` | The alias you type on the command line |
| `HostName` | The real IP address or DNS name |
| `User` | The remote username |
| `Port` | SSH port (default 22; change if server uses a non-standard port) |
| `IdentityFile` | Path to the private key for this host |
| `ServerAliveInterval` | Seconds between keepalive packets (prevents idle disconnects) |
| `ServerAliveCountMax` | How many missed keepalives before disconnecting |
| `ProxyJump` | Hop through another SSH host to reach this one (jump host / bastion) |
| `ForwardAgent` | Forward your local SSH agent so you can SSH further from the remote host |
| `LocalForward` | Create a local port forward (see next section) |

Set restrictive permissions on the config file:

```bash
chmod 600 ~/.ssh/config
```

#### SSH Port Forwarding: Reaching AI Services Securely

Port forwarding lets you route traffic through an encrypted SSH tunnel. This is how you safely access a Jupyter notebook, Ollama API, or Grafana dashboard running on a remote server that has no public-facing port open for those services — only port 22.

**Local port forwarding** (`-L`) — binds a port on your **local machine** and forwards traffic through SSH to a port on the **remote server** (or a host reachable from the remote server). This is the most common case: you want to reach a service running on the remote server from your laptop.

```bash
# Syntax: ssh -L [local_addr:]local_port:remote_addr:remote_port user@ssh_host

# Forward local port 11434 to Ollama running on the remote server's loopback
ssh -L 11434:localhost:11434 ubuntu@gpu-box

# Now, from your laptop:
curl http://localhost:11434/api/tags
# This request travels through the SSH tunnel to Ollama on gpu-box

# Forward local 8888 to Jupyter on the remote server
ssh -L 8888:localhost:8888 ubuntu@gpu-box
# Open http://localhost:8888 in your browser to access the remote Jupyter

# Forward local 3000 to Grafana on the remote server
ssh -L 3000:localhost:3000 ubuntu@gpu-box
# Open http://localhost:3000 to access the remote Grafana dashboard

# Run in background (-N = no command, -f = background)
ssh -N -f -L 11434:localhost:11434 ubuntu@gpu-box
```

You can combine multiple forwards in one session or define them in `~/.ssh/config`:

```
Host gpu-box
    HostName 203.0.113.45
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
    LocalForward 11434 localhost:11434
    LocalForward 8888 localhost:8888
    LocalForward 3000 localhost:3000
```

With this config, every `ssh gpu-box` session automatically opens all three tunnels.

**Remote port forwarding** (`-R`) — binds a port on the **remote server** and forwards traffic back through SSH to a port on your **local machine**. Less common, but useful when you want to temporarily expose a service running on your laptop to the remote server.

```bash
# Syntax: ssh -R [remote_addr:]remote_port:local_addr:local_port user@ssh_host

# Expose local port 5000 (a dev Flask app) as port 5000 on the remote server
ssh -R 5000:localhost:5000 ubuntu@gpu-box
```

**Dynamic port forwarding** (`-D`) — creates a SOCKS proxy on a local port. All traffic routed through that proxy is forwarded through the SSH tunnel, letting you browse as if you were on the remote network.

```bash
# Create a SOCKS5 proxy on local port 1080
ssh -D 1080 -N -f ubuntu@gpu-box
# Configure your browser to use SOCKS5 proxy at 127.0.0.1:1080
```

### Common Ports for AI Services

Understanding which service lives on which port lets you write correct firewall rules, configure port forwards, and diagnose connection problems quickly.

| Port | Protocol | Service | Notes |
|---|---|---|---|
| 22 | TCP | SSH | Default; change to a non-standard port to reduce scan noise |
| 80 | TCP | HTTP | Unencrypted web traffic; redirect to 443 in production |
| 443 | TCP | HTTPS | Encrypted web traffic; use for any public-facing service |
| 8080 | TCP | HTTP alt / Jupyter alt | Common alternative HTTP port; also used by many web apps |
| 8443 | TCP | HTTPS alt | Alternative HTTPS port; used by some management interfaces |
| 8888 | TCP | Jupyter Notebook/Lab | Default Jupyter port |
| 11434 | TCP | Ollama | Local LLM inference API; listens on `127.0.0.1` by default |
| 3000 | TCP | Grafana | Metrics and monitoring dashboards |
| 9090 | TCP | Prometheus | Metrics collection and alerting |
| 6006 | TCP | TensorBoard | Training visualization |
| 7860 | TCP | Gradio | ML demo web UIs |
| 7777 | TCP | vLLM (common config) | High-performance LLM inference server |
| 5000 | TCP | Flask dev server | Python web app development |
| 8501 | TCP | Streamlit | ML app framework |
| 5432 | TCP | PostgreSQL | Relational database; used by vector DBs like pgvector |
| 6379 | TCP | Redis | Cache / message broker; used by task queues |
| 19530 | TCP | Milvus | Vector database |

A key design principle: services like Ollama and Jupyter that are intended for local development bind to `127.0.0.1` (loopback only) by default for security. To reach them from your laptop, use an SSH tunnel rather than binding them to `0.0.0.0` (all interfaces) and opening a firewall port.

### Inspecting Connections with `ss` and `netstat`

Before you can forward a port or open a firewall rule, you need to know which ports services are actually listening on.

#### `ss` — Socket Statistics (Modern)

`ss` is the modern replacement for `netstat`, included in the `iproute2` package. It is faster and provides more detail.

```bash
# Show all listening TCP sockets
ss -tlnp

# Show all listening UDP sockets
ss -ulnp

# Show all listening TCP and UDP sockets
ss -tlnpu

# Show all established TCP connections
ss -tnp state established

# Show all sockets (listening and established)
ss -anp

# Filter by port number
ss -tnp 'sport = :11434'

# Filter by process name
ss -tnp | grep ollama
```

Flag reference for `ss`:

| Flag | Meaning |
|---|---|
| `-t` | Show TCP sockets |
| `-u` | Show UDP sockets |
| `-l` | Show only listening sockets |
| `-n` | Show numeric addresses (do not resolve names) |
| `-p` | Show the process that owns each socket |
| `-a` | Show all sockets (listening + established) |

Sample output of `ss -tlnp`:

```
State   Recv-Q  Send-Q  Local Address:Port  Peer Address:Port  Process
LISTEN  0       128     0.0.0.0:22          0.0.0.0:*          users:(("sshd",pid=987,fd=3))
LISTEN  0       4096    127.0.0.1:11434     0.0.0.0:*          users:(("ollama",pid=2341,fd=7))
LISTEN  0       128     127.0.0.1:8888      0.0.0.0:*          users:(("jupyter",pid=3102,fd=9))
```

This output tells you:
- SSH is listening on all interfaces (`0.0.0.0:22`) — reachable externally
- Ollama is listening on loopback only (`127.0.0.1:11434`) — not reachable externally without a tunnel
- Jupyter is on loopback only (`127.0.0.1:8888`) — same

#### `netstat` (Legacy)

`netstat` is still present on most systems (from the `net-tools` package, which may need to be installed separately on minimal systems). Its flags are nearly equivalent:

```bash
# Install on Ubuntu/Debian if missing
sudo apt install -y net-tools

# Show all listening TCP ports with process names
netstat -tlnp

# Show all connections
netstat -anp

# Show network interface statistics
netstat -i

# Show the routing table
netstat -r
```

On modern systems, prefer `ss` — it is faster, always available, and better maintained.

### Hostname Configuration

The **hostname** is the name the server identifies itself by. It appears in your shell prompt, in SSH banners, in logs, and in service discovery. Consistent, meaningful hostnames eliminate the "which server am I on?" confusion when managing multiple GPU boxes.

```bash
# Show the current hostname
hostname

# Show the full hostname including domain (FQDN)
hostname -f

# Show the system hostname as known to systemd
hostnamectl status

# Change the hostname permanently (survives reboot)
sudo hostnamectl set-hostname gpu-box-01

# The new hostname is immediately active; verify it
hostnamectl status
```

`hostnamectl status` sample output:

```
 Static hostname: gpu-box-01
       Icon name: computer-vm
         Chassis: vm
      Machine ID: a1b2c3d4e5f6...
         Boot ID: f6e5d4c3b2a1...
  Virtualization: kvm
Operating System: Ubuntu 24.04.1 LTS
          Kernel: Linux 6.8.0-48-generic
    Architecture: x86-64
```

On Ubuntu, the hostname is stored in `/etc/hostname`:

```bash
cat /etc/hostname
# gpu-box-01
```

### `/etc/hosts` — Local Name Resolution

`/etc/hosts` is a plain text file that maps hostnames to IP addresses. It is checked before DNS and has no expiry — entries are permanent until you edit the file. It is the simplest way to make a server addressable by name on your local network or within a team, without setting up a DNS server.

```
# /etc/hosts format: IP_ADDRESS  HOSTNAME  [ALIASES...]

127.0.0.1   localhost
127.0.1.1   gpu-box-01

# On-premises GPU servers
10.10.0.10  gpu-box-01  gpu1
10.10.0.11  gpu-box-02  gpu2
10.10.0.12  storage-01

# AI services accessible by tunnel
127.0.0.1   ollama.local
127.0.0.1   jupyter.local
```

With these entries, you can type `ssh gpu1` or `curl http://ollama.local:11434/api/tags` instead of remembering raw IPs.

Edit `/etc/hosts` as root:

```bash
sudo nano /etc/hosts
```

Changes take effect immediately — no restart or reload is needed. Verify resolution with:

```bash
# Resolve a hostname using the system resolver (checks /etc/hosts first)
getent hosts gpu-box-01

# Also works
ping -c 1 gpu-box-01
```

The order of hostname resolution is controlled by `/etc/nsswitch.conf`:

```bash
grep hosts /etc/nsswitch.conf
# hosts: files dns
```

`files` means `/etc/hosts` is checked first; `dns` means the configured DNS server is checked if `/etc/hosts` has no match.

## Best Practices

1. **Never bind AI inference services directly to `0.0.0.0` on a publicly routable interface without authentication.** Ollama, Jupyter, and most ML tools have no authentication by default. Use SSH port forwarding instead of opening firewall ports — you get encryption and authentication for free.

2. **Use ED25519 keys, not RSA, for new SSH key pairs.** ED25519 keys are shorter, faster, and considered more secure than RSA-2048. Generate them with `ssh-keygen -t ed25519`. If you must interoperate with legacy systems, RSA-4096 is an acceptable fallback.

3. **Always set a passphrase on your SSH private key.** A passphrase encrypts the key at rest; without one, anyone who copies the file has full access to every server it is authorized on. Use `ssh-agent` to avoid typing the passphrase on every connection.

4. **Always run `netplan try` instead of `netplan apply` when reconfiguring network interfaces on a remote server.** `netplan try` automatically rolls back if you do not confirm within 120 seconds, preventing you from locking yourself out due to a misconfiguration.

5. **Define all SSH connections in `~/.ssh/config` rather than remembering long command-line flags.** A well-maintained config file is self-documenting, reduces typos, and makes scripts and tools that call SSH (such as `scp`, `rsync`, and `git`) automatically use the correct key and port.

6. **Assign static IPs or stable DHCP reservations to on-premises GPU servers.** Entries in `/etc/hosts` and SSH config break silently if the server's IP changes after a DHCP renewal. Most routers and DHCP servers support reserving a fixed IP for a known MAC address.

7. **Run `ss -tlnp` before and after starting any service to confirm it is listening on the expected address and port.** It is common to start a service only to find it bound to `127.0.0.1` when you intended `0.0.0.0`, or to the wrong port entirely.

8. **Keep `/etc/hosts` synchronized across servers that need to address each other by name.** If `gpu-box-01` and `gpu-box-02` both need to communicate, put entries for both in each server's `/etc/hosts`. For larger fleets, graduate to an internal DNS server.

9. **Disable password authentication on SSH after confirming key-based auth works.** Test from a separate terminal session before setting `PasswordAuthentication no` in `sshd_config`. Always keep a console access method (cloud provider console, IPMI, or physical access) available as a recovery path.

10. **Use `resolvectl query` instead of `nslookup` or `dig` on systemd-resolved systems.** It queries through the same resolver path your applications use, so results reflect the actual resolution behavior including search domains and per-interface DNS settings.

## Use Cases

### Use Case 1: Reaching Ollama on a Remote GPU Box via SSH Tunnel

A data scientist has an on-premises server with an NVIDIA GPU running Ollama. Ollama is bound to `127.0.0.1:11434` (its default). The server has only port 22 open externally.

- **Problem:** The scientist wants to query the Ollama API from their laptop (e.g., using the OpenAI-compatible endpoint) without exposing port 11434 to the internet.
- **Concepts applied:** SSH config file, local port forwarding (`-L`), `ss -tlnp` to confirm Ollama is listening, `/etc/hosts` to make `ollama.local` resolve to `127.0.0.1`
- **Expected outcome:** `ssh gpu-box` opens the tunnel automatically via `LocalForward 11434 localhost:11434` in the SSH config; `curl http://localhost:11434/api/tags` on the laptop returns the list of loaded models.

### Use Case 2: Giving a GPU Server a Persistent Address and Name

A small team shares an on-premises GPU server. Its IP changes on every reboot because it is on DHCP, causing all SSH configs and `/etc/hosts` entries to break.

- **Problem:** The dynamic IP creates broken connections and wastes debugging time after reboots.
- **Concepts applied:** Netplan YAML for static IP assignment (`dhcp4: false`, `addresses`), `hostnamectl set-hostname`, `/etc/hosts` entries on team members' laptops
- **Expected outcome:** The server always boots with IP `192.168.1.100`, and team members `ssh gpu-server` without thinking about its address.

### Use Case 3: Accessing a Jupyter Notebook and Grafana Simultaneously

A researcher has Jupyter Lab on port 8888 and Grafana on port 3000 on a remote training server. They want to access both from their browser at the same time.

- **Problem:** Two services, two ports, one SSH session — they need both forwarded simultaneously without running two separate SSH commands.
- **Concepts applied:** Multiple `LocalForward` directives in `~/.ssh/config`, understanding of loopback-bound services
- **Expected outcome:** A single `ssh gpu-box` opens both tunnels; `http://localhost:8888` shows Jupyter Lab and `http://localhost:3000` shows Grafana.

### Use Case 4: Diagnosing "Connection Refused" on Port 11434

A developer installs Ollama on a new server and immediately tries to hit its API from another machine, getting `Connection refused`.

- **Problem:** They do not know whether Ollama failed to start, is on the wrong port, or is bound only to loopback.
- **Concepts applied:** `ss -tlnp` to see what is listening and on which address, `systemctl status ollama` to check service health, understanding of `0.0.0.0` vs `127.0.0.1` binding
- **Expected outcome:** `ss -tlnp | grep 11434` reveals Ollama is listening on `127.0.0.1:11434`, confirming it is loopback-only. The developer sets up an SSH tunnel instead of misconfiguring the bind address.

### Use Case 5: Setting Up DNS So Services Are Reachable by Name

An ML platform team runs several services on the same server and wants them reachable by name (`ollama.internal`, `jupyter.internal`) from all machines on their internal network, without a full DNS server.

- **Problem:** Raw IP addresses with port numbers are hard to remember, hard to share, and break when the server's address changes.
- **Concepts applied:** `/etc/hosts` on each client machine mapping names to the server's IP, `search` directive in `/etc/resolv.conf`, `getent hosts` to verify resolution
- **Expected outcome:** Team members type `curl http://ollama.internal:11434` and get a response; when the server IP changes, only the `/etc/hosts` files need updating.

## Hands-on Examples

### Example 1: Inspect Your Network Interfaces and Routing Table

You will use `ip addr`, `ip link`, and `ip route` to build a complete picture of your server's network configuration before making any changes.

1. Show all interfaces with their IP addresses.

```bash
ip addr show
```

Expected output (on a typical Ubuntu Server VM — interface names vary):

```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
2: ens3: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether fa:16:3e:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 10.0.0.5/24 brd 10.0.0.255 scope global dynamic ens3
       valid_lft 82341sec preferred_lft 82341sec
```

2. Identify your primary interface (the one with your server's IP), your IP address, prefix length, and DHCP lease time.

3. Show only the link-layer (MAC address) view:

```bash
ip link show
```

4. Show the routing table:

```bash
ip route show
```

Expected output:

```
default via 10.0.0.1 dev ens3 proto dhcp src 10.0.0.5 metric 100
10.0.0.0/24 dev ens3 proto kernel scope link src 10.0.0.5
```

5. Trace how a packet to `8.8.8.8` would be routed:

```bash
ip route get 8.8.8.8
```

Expected output:

```
8.8.8.8 via 10.0.0.1 dev ens3 src 10.0.0.5 uid 1000
    cache
```

This confirms packets to the internet leave via `ens3` through gateway `10.0.0.1`.

6. Confirm DNS is working:

```bash
resolvectl status
```

Look for `Current DNS Server` and `DNS Servers` lines for your primary interface.

---

### Example 2: Generate an SSH Key Pair and Set Up Key-Based Login

You will generate a new ED25519 key pair on your local machine and authorize it on a remote server. Substitute `YOUR_USER` and `SERVER_IP` with your own values.

1. On your **local machine**, generate the key pair. Accept the default file path and enter a passphrase when prompted.

```bash
ssh-keygen -t ed25519 -C "ai-dev-key"
```

Expected output:

```
Generating public/private ed25519 key pair.
Enter file in which to save the key (/home/user/.ssh/id_ed25519):
Enter passphrase (empty for no passphrase): [type a passphrase]
Enter same passphrase again: [repeat passphrase]
Your identification has been saved in /home/user/.ssh/id_ed25519
Your public key has been saved in /home/user/.ssh/id_ed25519.pub
The key fingerprint is:
SHA256:AbCdEfGhIjKlMnOpQrStUvWxYz1234567890abcdef ai-dev-key
```

2. View the public key (safe to share):

```bash
cat ~/.ssh/id_ed25519.pub
```

Expected output (one long line):

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... ai-dev-key
```

3. Copy the public key to the remote server. Enter the server password when prompted (this is the last time you will need it):

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub YOUR_USER@SERVER_IP
```

Expected output:

```
/usr/bin/ssh-copy-id: INFO: Source of key(s) to be installed: "/home/user/.ssh/id_ed25519.pub"
/usr/bin/ssh-copy-id: INFO: attempting to log in with the new key(s)
Number of key(s) added: 1

Now try logging into the machine, with:   "ssh 'YOUR_USER@SERVER_IP'"
and check to make sure that only the key(s) you wanted were added.
```

4. Test key-based login:

```bash
ssh YOUR_USER@SERVER_IP
```

You should be prompted for your key passphrase (not the server password) and then get a shell.

5. Verify the authorized key was added correctly on the remote server:

```bash
cat ~/.ssh/authorized_keys
```

Expected output contains your public key on one line.

6. Set correct permissions (these are required for SSH to accept the key):

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

---

### Example 3: Write an SSH Config File with Port Forwarding

You will create a `~/.ssh/config` entry for a GPU server that automatically opens tunnels to Ollama, Jupyter, and Grafana when you connect.

1. On your **local machine**, open (or create) the SSH config file:

```bash
nano ~/.ssh/config
```

2. Add the following block. Replace `203.0.113.45` with your server's actual IP and `ubuntu` with your username.

```
Host gpu-box
    HostName 203.0.113.45
    User ubuntu
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
    LocalForward 11434 localhost:11434
    LocalForward 8888 localhost:8888
    LocalForward 3000 localhost:3000
```

3. Set restrictive permissions on the config file:

```bash
chmod 600 ~/.ssh/config
```

4. Connect using the alias:

```bash
ssh gpu-box
```

This connects to `203.0.113.45` as `ubuntu` using your ED25519 key, and simultaneously opens three local port forwards. You will see something like:

```
Welcome to Ubuntu 24.04.1 LTS (GNU/Linux 6.8.0-48-generic x86_64)
ubuntu@gpu-box-01:~$
```

5. While the SSH session is open, open a **new terminal on your local machine** and test the Ollama tunnel:

```bash
curl http://localhost:11434/api/tags
```

If Ollama is running on the server, you will see a JSON response listing available models. If Ollama is not running, you will see `curl: (7) Failed to connect to localhost port 11434: Connection refused` — the tunnel is working but the service is not running on the remote end.

6. To run the tunnel in the background (so you do not need to keep a terminal open):

```bash
ssh -N -f gpu-box
```

To find and kill the background process:

```bash
# Find the ssh process
ps aux | grep 'ssh -N'
# Kill it by PID
kill <PID>
```

---

### Example 4: Inspect Services with `ss` and Add a Hosts Entry

You will check which services are listening on a server, then make one reachable by name on your local machine.

1. On the **remote server**, show all listening TCP sockets with process names:

```bash
ss -tlnp
```

Expected output showing a typical AI dev server:

```
State   Recv-Q  Send-Q  Local Address:Port  Peer Address:Port  Process
LISTEN  0       128     0.0.0.0:22          0.0.0.0:*          users:(("sshd",pid=987,fd=3))
LISTEN  0       4096    127.0.0.1:11434     0.0.0.0:*          users:(("ollama",pid=2341,fd=7))
LISTEN  0       128     127.0.0.1:8888      0.0.0.0:*          users:(("jupyter-lab",pid=3102,fd=9))
LISTEN  0       128     0.0.0.0:3000        0.0.0.0:*          users:(("grafana",pid=1854,fd=12))
```

Note: Grafana in this example is listening on `0.0.0.0:3000` (all interfaces) while Ollama and Jupyter are on loopback only.

2. Confirm which processes are using specific ports:

```bash
ss -tlnp | grep ':11434'
ss -tlnp | grep ':8888'
```

3. Check established connections (to see who is currently connected over SSH):

```bash
ss -tnp state established
```

4. Now, on your **local machine**, add hosts entries so you can reach the forwarded services by name. Open `/etc/hosts` as root:

```bash
sudo nano /etc/hosts
```

Add these lines:

```
127.0.0.1   ollama.local
127.0.0.1   jupyter.local
127.0.0.1   grafana.local
```

5. Verify the entries resolve:

```bash
getent hosts ollama.local
```

Expected output:

```
127.0.0.1       ollama.local
```

6. With the SSH tunnel open (from Example 3), test by name:

```bash
curl http://ollama.local:11434/api/tags
```

This routes `ollama.local` to `127.0.0.1` via `/etc/hosts`, which is the local end of your SSH tunnel, which connects to Ollama on the remote server.

---

### Example 5: Configure DNS Resolution and Verify It

You will inspect your current DNS configuration, test name resolution, and flush the DNS cache.

1. Check whether your system uses `systemd-resolved`:

```bash
ls -la /etc/resolv.conf
```

If it is a symlink to a `systemd` path, `systemd-resolved` is active.

2. Show DNS resolver status:

```bash
resolvectl status
```

Note the `DNS Servers` and `DNS Domain` lines for each interface.

3. Query a hostname and see which DNS server answered:

```bash
resolvectl query github.com
```

Expected output:

```
github.com: 140.82.114.3
            -- Information acquired via protocol DNS in 32.4ms.
            -- Data is authenticated: no; Data was acquired via local or logical transport: no
            -- Data origin: network, interface: ens3
```

4. Flush the DNS cache (useful when DNS records have changed and you want fresh results):

```bash
sudo resolvectl flush-caches
```

5. Confirm the cache is cleared:

```bash
resolvectl statistics
```

The `Current Cache Size` should be 0 or very low immediately after flushing.

6. Look up a hostname you added to `/etc/hosts` and confirm it does not go to DNS:

```bash
getent hosts ollama.local
resolvectl query ollama.local
```

`getent` will return the `/etc/hosts` entry. `resolvectl query` may show an error or return `127.0.0.1` depending on your `nsswitch.conf` configuration — the key point is that `/etc/hosts` is authoritative and checked first.

## Common Pitfalls

### Pitfall 1: Binding AI Services to `0.0.0.0` Instead of Using SSH Tunneling

**Description:** A developer wants to reach Ollama from their laptop and, rather than setting up an SSH tunnel, changes Ollama's bind address to `0.0.0.0` so it is reachable on the public interface. The service is now accessible to anyone who can reach the server's IP on port 11434.

**Why it happens:** SSH tunnels feel like extra setup; binding to `0.0.0.0` feels simpler and more direct.

**Incorrect pattern:**
```bash
# Setting OLLAMA_HOST=0.0.0.0 on the server exposes it to the internet
export OLLAMA_HOST=0.0.0.0:11434
ollama serve
# Now anyone can query your model, download your models, and run inference at your expense
```

**Correct pattern:**
```bash
# Leave Ollama on 127.0.0.1 (its default)
# Create an SSH tunnel from your laptop instead
ssh -L 11434:localhost:11434 ubuntu@your-gpu-server
# Query Ollama securely from your laptop
curl http://localhost:11434/api/tags
```

---

### Pitfall 2: Locking Yourself Out by Disabling Password Auth Before Testing Key Auth

**Description:** A developer sets `PasswordAuthentication no` in `sshd_config` and restarts SSH — but the public key was not correctly copied to `authorized_keys`. They are now locked out of the server.

**Why it happens:** The steps feel sequential; it is easy to skip the "test in a separate terminal" step.

**Incorrect pattern:**
```bash
# Edit sshd_config and disable password auth
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
# Close the terminal and try to SSH in
# LOCKED OUT if the key was not correctly installed
```

**Correct pattern:**
```bash
# Step 1: Copy your key first
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@SERVER_IP

# Step 2: Open a NEW terminal and confirm key login works BEFORE changing sshd_config
ssh user@SERVER_IP
# Confirm you get a shell using the key

# Step 3: Only now edit sshd_config and restart
sudo nano /etc/ssh/sshd_config  # set PasswordAuthentication no
sudo systemctl restart ssh

# Step 4: Test login again in yet another new terminal to confirm
```

---

### Pitfall 3: Confusing `ip addr add` with a Persistent Network Change

**Description:** A developer uses `ip addr add` to assign a static IP and it works perfectly — until the next reboot, when the address is gone. `ip` commands modify the running kernel state only; they do not write to any configuration file.

**Why it happens:** The command works immediately and produces no warning that the change is not persistent.

**Incorrect pattern:**
```bash
# This sets the IP right now, but it will be gone after reboot
sudo ip addr add 192.168.1.100/24 dev ens3
sudo ip route add default via 192.168.1.1
```

**Correct pattern (Ubuntu with Netplan):**
```bash
# Edit /etc/netplan/00-installer-config.yaml to set dhcp4: false and add addresses
sudo nano /etc/netplan/00-installer-config.yaml
# Then apply safely
sudo netplan try
# Press ENTER to confirm the configuration within 120 seconds
sudo netplan apply
```

---

### Pitfall 4: Using `nslookup` or `dig` When the System Uses `systemd-resolved`

**Description:** A developer uses `nslookup gpu-box.internal` and gets `NXDOMAIN` (name not found). They conclude DNS is broken — but `ssh gpu-box` works fine. The issue is that `nslookup` and `dig` bypass `systemd-resolved` and `/etc/hosts` entirely, querying DNS directly. `resolvectl` uses the full resolution stack.

**Why it happens:** `nslookup` and `dig` are familiar tools taught in general networking; learners do not realize they bypass the local resolver.

**Incorrect pattern:**
```bash
nslookup gpu-box.internal
# Server:  127.0.0.53
# ** server can't find gpu-box.internal: NXDOMAIN
# Conclusion: "DNS is broken" — but it is not
```

**Correct pattern:**
```bash
# Use getent (checks /etc/hosts + full NSS stack)
getent hosts gpu-box.internal

# Use resolvectl (queries via systemd-resolved, same path as applications)
resolvectl query gpu-box.internal

# nslookup and dig are still useful for querying a specific upstream DNS server
# but are not representative of what your applications see
```

---

### Pitfall 5: Forgetting That Port Forwards Close When the SSH Session Ends

**Description:** A developer sets up SSH port forwarding in a terminal, starts using the tunneled services, then closes the terminal. All forwarded services immediately become unreachable.

**Why it happens:** The forward is tied to the SSH session process; closing the terminal sends SIGHUP and kills the process.

**Incorrect pattern:**
```bash
ssh -L 11434:localhost:11434 ubuntu@gpu-box
# Use tunnel from another terminal...
# Close the terminal
# All tunnels are now dead
```

**Correct pattern:**
```bash
# Run the tunnel in the background with -N (no remote command) and -f (fork to background)
ssh -N -f -L 11434:localhost:11434 ubuntu@gpu-box

# Or, define the tunnel in ~/.ssh/config with LocalForward
# and use autossh to automatically restart it if the connection drops:
sudo apt install -y autossh
autossh -M 0 -N -f gpu-box
```

---

### Pitfall 6: Editing `/etc/resolv.conf` Directly on a `systemd-resolved` System

**Description:** A developer edits `/etc/resolv.conf` to change DNS servers, and the changes work immediately — but are silently overwritten the next time `systemd-resolved` or the network manager restarts.

**Why it happens:** `/etc/resolv.conf` looks like an ordinary config file and editing it directly is deeply familiar. The symlink nature is easy to miss.

**Incorrect pattern:**
```bash
# On a systemd-resolved system, this file is a managed symlink
sudo nano /etc/resolv.conf
# Adds nameserver 1.1.1.1
# Works until next network restart, then reverts
```

**Correct pattern (Netplan + systemd-resolved):**
```bash
# Add DNS servers in the Netplan config
sudo nano /etc/netplan/00-installer-config.yaml
# Set: nameservers: addresses: [1.1.1.1, 8.8.8.8]
sudo netplan apply

# Or edit /etc/systemd/resolved.conf for global DNS settings
sudo nano /etc/systemd/resolved.conf
# Set: DNS=1.1.1.1 8.8.8.8
sudo systemctl restart systemd-resolved
```

---

### Pitfall 7: SSH Tunnel to a Port Already in Use Locally

**Description:** A developer runs `ssh -L 8888:localhost:8888 ubuntu@gpu-box` but they already have a local Jupyter instance running on port 8888. The tunnel bind fails silently or with a cryptic error, and they cannot figure out why the remote Jupyter is not accessible.

**Why it happens:** The error message (`bind: Address already in use`) can scroll by quickly at connection time and is easy to miss.

**Incorrect pattern:**
```bash
# Local Jupyter already running on 8888
ssh -L 8888:localhost:8888 ubuntu@gpu-box
# Warning: remote port forwarding failed for listen port 8888
# Connection established but no tunnel
```

**Correct pattern:**
```bash
# Check if the local port is already in use before binding
ss -tlnp | grep ':8888'
# If in use, pick a different local port (e.g., 18888)
ssh -L 18888:localhost:8888 ubuntu@gpu-box
# Access the remote Jupyter at http://localhost:18888
```

## Summary

- Linux represents every network connection as a **network interface**, inspected with `ip addr` (for IP addresses and state) and `ip link` (for link-layer and MAC information). `ip route` shows how the kernel decides where to send each packet.
- **DHCP** assigns addresses automatically and suits cloud VMs and development machines; **static addressing** (configured via Netplan on Ubuntu Server) is essential for on-premises servers that other machines need to reach by a predictable address. Always use `netplan try` on remote servers to guard against misconfiguration.
- **DNS** resolves names to IPs. On modern Ubuntu, `systemd-resolved` provides a local caching stub at `127.0.0.53`; `resolvectl` is the correct tool to inspect and test it. `/etc/hosts` provides static, instant overrides that are checked before DNS and require no service restarts.
- **SSH key-based authentication** with ED25519 keys is the secure baseline for all server access. The `~/.ssh/config` file reduces every server connection to a short alias and can define persistent port forwards that activate automatically on connect.
- **SSH port forwarding** (`-L`) is the correct way to reach AI services like Ollama (11434), Jupyter (8888), and Grafana (3000) that are intentionally bound to `127.0.0.1`. It provides encryption and authentication without exposing ports to the public internet.
- `ss -tlnp` is the definitive tool for confirming which services are listening, on which address, and which process owns them — the first command to run when debugging any "connection refused" error.
- **Hostname** (`hostnamectl set-hostname`) and `/etc/hosts` work together to make servers addressable by meaningful names, eliminating the need to remember raw IP addresses across SSH configs, API calls, and terminal prompts.

## Further Reading

- [iproute2 — ip(8) Manual Page (man7.org)](https://man7.org/linux/man-pages/man8/ip.8.html) — The authoritative Unix manual page for the `ip` command covering every subcommand (`addr`, `link`, `route`, `neigh`, `rule`) with full option descriptions; the definitive reference when a flag's behavior is unclear.
- [OpenSSH Manual Pages — ssh(1) and ssh_config(5)](https://www.openssh.com/manual.html) — Official OpenSSH documentation for the client (`ssh`) and client configuration file (`ssh_config`); lists every directive available in `~/.ssh/config` with precise semantics and examples.
- [Ubuntu Server Guide: Networking (Canonical)](https://ubuntu.com/server/docs/network-configuration) — The canonical documentation for Ubuntu Server networking, covering Netplan YAML syntax, static IP configuration, and NetworkManager integration for Ubuntu 22.04 and 24.04 specifically.
- [systemd-resolved Documentation (systemd.io)](https://www.freedesktop.org/software/systemd/man/latest/systemd-resolved.service.html) — Complete reference for `systemd-resolved` including `resolved.conf` options, the stub resolver, LLMNR, and mDNS; essential reading for understanding name resolution behavior on modern Ubuntu systems.
- [SSH Tunneling / Port Forwarding Explained — SSH Academy](https://www.ssh.com/academy/ssh/tunneling/example) — A clear, diagram-heavy walkthrough of local, remote, and dynamic SSH port forwarding with real-world use cases; the best standalone reference for this module's forwarding section.
- [Ollama FAQ: How to expose Ollama on a network (Ollama GitHub)](https://github.com/ollama/ollama/blob/main/docs/faq.md) — Official Ollama documentation on `OLLAMA_HOST` configuration, including the security implications of binding to non-loopback addresses; directly relevant to the pitfalls in this module.
- [The Linux Command Line, Chapter 9: Networking (William Shotts, No Starch Press)](https://linuxcommand.org/tlcl.php) — A freely available chapter from a highly regarded Linux primer covering `ping`, `traceroute`, `ss`, `wget`, and fundamental networking concepts from first principles; excellent supplementary reading for the tools introduced here.
- [Netplan Reference Documentation (netplan.io)](https://netplan.readthedocs.io/en/stable/reference/) — Complete YAML key reference for Netplan configuration files, covering `ethernets`, `wifis`, `vlans`, `routes`, `nameservers`, and renderer-specific options; required reading before writing production Netplan configs.
