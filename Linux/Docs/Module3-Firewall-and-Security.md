# Module 3: Firewall and Security
> Subject: Linux | Difficulty: Intermediate | Estimated Time: 210 minutes

## Objective

After completing this module, you will be able to harden a Linux server that exposes AI inference endpoints to the network. You will configure `ufw` with explicit default policies, write allow and deny rules using ports, protocols, IP ranges, and named application profiles, and manage existing rules by number. You will understand enough `iptables` to read and interpret rules you encounter in production systems and documentation. You will install and configure `fail2ban` to automatically block brute-force attempts against SSH and HTTP/HTTPS services. You will apply a layered security model to a realistic scenario: an Ollama inference server on port 11434 that must be reachable only from a trusted internal subnet, behind an HTTPS API gateway that is open to the public. You will identify and disable unnecessary system services to reduce the attack surface, and you will understand the conceptual difference between trusted internal network zones and public-facing zones.

---

## Prerequisites

- **Completed Module 1: Linux Fundamentals** — comfort with the shell, file system navigation, reading man pages, and running commands with `sudo`
- **Completed Module 2: Users, Permissions, and SSH** — understanding of Linux user accounts, `sudo` configuration, SSH key authentication, and the principle of least privilege
- A Linux server or VM running Ubuntu 22.04 LTS or Ubuntu 24.04 LTS (commands are verified against these releases; most apply equally to Debian 12)
- Root or sudo access on that machine
- A second machine or a second terminal session on the same machine to test connectivity (useful for firewall verification steps)
- Basic understanding of TCP/IP: what a port is, what a subnet means (e.g., `10.0.0.0/24`), and what the difference between TCP and UDP is

---

## Key Concepts

### Why Firewalls Matter More for AI Servers

Running an AI inference service introduces an unusual threat model that many developers encounter for the first time. Tools like Ollama expose an HTTP API on a local port — port `11434` by default — that responds to natural language prompts, executes model inference, and can pull large model files from the internet. By design, the API has no built-in authentication in its default configuration. If port 11434 is reachable from the public internet, anyone who discovers it can:

- Run unlimited inference requests at your compute and electricity cost
- Extract any model you have pulled
- Potentially exfiltrate system information through carefully crafted prompts

The same risk applies to other common AI tooling ports: LM Studio on `1234`, vLLM on `8000`, OpenWebUI on `3000`, and similar services. A firewall is not optional for these workloads — it is the primary access control layer.

The broader principle is **defense in depth**: no single security control is sufficient. A firewall limits which traffic reaches your service. SSH key authentication prevents password brute-force. fail2ban backs up both by rate-limiting repeated failures. Disabled services shrink the total number of things that can be attacked. Together these layers mean that an attacker who defeats one control still faces several more.

```
Defense-in-Depth Model for an AI Server

  Internet
     │
     ▼
  ┌─────────────────────────────────────────────┐
  │  Layer 1: Firewall (ufw / iptables)         │
  │  — blocks all ports except 22, 80, 443      │
  │  — port 11434 allowed only from 10.0.0.0/8  │
  └─────────────────────────────────────────────┘
     │ (only allowed traffic passes)
     ▼
  ┌─────────────────────────────────────────────┐
  │  Layer 2: fail2ban                          │
  │  — bans IPs after N failed SSH/HTTP logins  │
  └─────────────────────────────────────────────┘
     │
     ▼
  ┌─────────────────────────────────────────────┐
  │  Layer 3: Service Authentication            │
  │  — SSH keys only, no password login         │
  │  — API gateway requires bearer tokens       │
  └─────────────────────────────────────────────┘
     │
     ▼
  ┌─────────────────────────────────────────────┐
  │  Layer 4: Minimal Attack Surface            │
  │  — only required services running           │
  │  — no unused daemons or open ports          │
  └─────────────────────────────────────────────┘
```

### ufw — The Uncomplicated Firewall

`ufw` (Uncomplicated Firewall) is the standard firewall management tool on Ubuntu and Debian. It is a frontend to `iptables` (and `nftables` on newer kernels), designed to make common firewall operations expressible in a single, readable command. ufw ships pre-installed on Ubuntu but is inactive by default. You must explicitly enable it.

**Checking status and enabling ufw:**

```bash
# Check whether ufw is active and what rules are loaded
sudo ufw status verbose

# Enable ufw — takes effect immediately; do NOT run this on a remote
# session unless you have already allowed SSH (port 22)
sudo ufw enable

# Disable ufw (removes all packet filtering, not just rules)
sudo ufw disable
```

**Default policies** control what happens to traffic that does not match any explicit rule. Setting the defaults before enabling ufw is the most important firewall configuration step. The security-correct defaults are:

```bash
# Deny all incoming connections by default
sudo ufw default deny incoming

# Allow all outgoing connections by default
# (servers need to initiate outbound DNS, apt updates, model pulls, etc.)
sudo ufw default allow outgoing

# Deny all forwarded traffic by default
# (this machine is not a router)
sudo ufw default deny routed
```

With `deny incoming` as the default, every inbound port is blocked unless you add an explicit allow rule. This is "default-deny" or "allowlist" policy — the correct posture for any server.

**Adding allow rules:**

```bash
# Allow SSH by service name (ufw reads /etc/services)
sudo ufw allow ssh

# Equivalent explicit form — allows TCP on port 22 from any source
sudo ufw allow 22/tcp

# Allow HTTPS only
sudo ufw allow 443/tcp

# Allow HTTP (needed for Let's Encrypt certificate renewal challenges)
sudo ufw allow 80/tcp

# Allow a port only from a specific IP address
sudo ufw allow from 203.0.113.45 to any port 22 proto tcp

# Allow a port only from a subnet — used for AI inference endpoints
# This allows Ollama's API to be reached only from the internal network
sudo ufw allow from 10.0.0.0/8 to any port 11434 proto tcp

# Allow a port range (e.g., for a pool of dynamic services)
sudo ufw allow 8000:8010/tcp
```

**Adding deny rules** — useful to explicitly block a source IP you know is malicious, regardless of other rules:

```bash
# Block all traffic from a specific IP
sudo ufw deny from 198.51.100.23

# Block a specific IP from reaching a specific port
sudo ufw deny from 198.51.100.23 to any port 443
```

ufw evaluates rules top-to-bottom and stops at the first match. A deny rule placed before a broader allow rule will shadow the allow. Numbered rules (covered below) let you inspect and control ordering.

### ufw Numbered Rules and Application Profiles

**Numbered rules** let you view, reorder, and delete rules precisely:

```bash
# List all rules with index numbers
sudo ufw status numbered

# Example output:
#      To                         Action      From
#      --                         ------      ----
# [ 1] 22/tcp                     ALLOW IN    Anywhere
# [ 2] 443/tcp                    ALLOW IN    Anywhere
# [ 3] 80/tcp                     ALLOW IN    Anywhere
# [ 4] 11434/tcp                  ALLOW IN    10.0.0.0/8
# [ 5] 22/tcp (v6)                ALLOW IN    Anywhere (v6)
# [ 6] 443/tcp (v6)               ALLOW IN    Anywhere (v6)
# [ 7] 80/tcp (v6)                ALLOW IN    Anywhere (v6)

# Delete rule number 3 (removes the HTTP allow rule)
sudo ufw delete 3

# After deletion, re-check numbering — indices shift after a deletion
sudo ufw status numbered
```

**Application profiles** are named rule sets stored in `/etc/ufw/applications.d/`. Many packages install their own profiles on installation. You can use profile names instead of port numbers, making rules more readable and resistant to port changes:

```bash
# List all available application profiles
sudo ufw app list

# Show the ports and protocol a profile covers
sudo ufw app info 'Nginx Full'
# Output:
# Profile: Nginx Full
# Title: Web Server (Nginx, HTTP + HTTPS)
# Description: This profile opens both 80 and 443.
# Ports: 80,443/tcp

# Allow the Nginx Full profile (opens 80 and 443 in one command)
sudo ufw allow 'Nginx Full'

# Allow only HTTPS via profile
sudo ufw allow 'Nginx HTTPS'
```

You can create your own application profile for Ollama. Create a file at `/etc/ufw/applications.d/ollama`:

```ini
[Ollama]
title=Ollama AI Inference API
description=Ollama local LLM inference server. Restrict to trusted sources only.
ports=11434/tcp
```

After creating the file, register it:

```bash
sudo ufw app update Ollama
sudo ufw app info Ollama
```

From this point you can write rules using the name `Ollama` instead of the port number.

### iptables Basics

`iptables` is the underlying Linux kernel packet filtering framework that both `ufw` and `firewalld` use as their backend on systems with kernels below 5.x (newer kernels use `nftables`, which `iptables` translates to via a compatibility layer). You will encounter `iptables` commands in older tutorials, in Docker documentation, and on CentOS/RHEL systems where `firewalld` manages it differently.

You do not need to manage `iptables` directly on Ubuntu if you use ufw — but you need to be able to read it.

**Core concepts:**
- **Tables**: `filter` (default, controls packet acceptance), `nat` (network address translation), `mangle` (packet modification)
- **Chains**: Within each table, rules are grouped into chains. The `filter` table has `INPUT` (inbound to this host), `OUTPUT` (outbound from this host), and `FORWARD` (routed through this host)
- **Targets**: What to do with a matching packet — `ACCEPT`, `DROP` (silently discard), `REJECT` (discard and send ICMP error), `LOG`, or a jump to a user-defined chain

```bash
# List all rules in the filter table with line numbers and no DNS resolution
sudo iptables -L -n -v --line-numbers

# List only the INPUT chain
sudo iptables -L INPUT -n -v --line-numbers

# Example output (abbreviated):
# Chain INPUT (policy DROP)
# num  pkts bytes target     prot opt in     out     source       destination
#   1     0     0 ACCEPT     all  --  lo     *       0.0.0.0/0    0.0.0.0/0
#   2  1234  89K ACCEPT     tcp  --  *      *       0.0.0.0/0    0.0.0.0/0    tcp dpt:22
#   3   892  67K ACCEPT     tcp  --  *      *       0.0.0.0/0    0.0.0.0/0    tcp dpt:443

# Show the raw iptables rules that ufw has installed
sudo iptables-save | grep -v "^#"
```

**Reading an iptables rule line:**

```
-A INPUT -s 10.0.0.0/8 -p tcp --dport 11434 -j ACCEPT
 │         │             │        │               │
 │         │             │        │               └─ Target: ACCEPT the packet
 │         │             │        └─ Destination port: 11434
 │         │             └─ Protocol: TCP
 │         └─ Source: only from 10.0.0.0/8
 └─ Append to INPUT chain
```

Do not mix `iptables` manual rules with `ufw` management on the same machine. ufw regenerates iptables rules on enable/disable and on reboot. Manual iptables rules added outside ufw will be lost. If you need both, add custom rules via ufw's `before.rules` or `after.rules` files in `/etc/ufw/`.

### fail2ban — Automatic Intrusion Throttling

`fail2ban` is a daemon that monitors log files for patterns indicating failed authentication or abuse (repeated 404s, login failures, etc.) and responds by temporarily blocking the offending IP address using the system firewall. It does not prevent a single targeted attack, but it makes broad automated brute-force attacks and credential-stuffing campaigns economically unattractive.

**Installing fail2ban:**

```bash
sudo apt update
sudo apt install fail2ban -y

# Check that the service is running
sudo systemctl status fail2ban
```

**Configuration architecture:**

fail2ban's configuration is layered:
- `/etc/fail2ban/fail2ban.conf` — global daemon settings (log level, socket path). Never edit this directly.
- `/etc/fail2ban/jail.conf` — default jail settings and all built-in jail definitions. Never edit this directly either.
- `/etc/fail2ban/jail.local` — your overrides. This file takes precedence. Create it from scratch or copy from `jail.conf`.
- `/etc/fail2ban/jail.d/*.conf` — per-jail override files; an alternative to `jail.local` for organizing rules by service.

The separation between `.conf` and `.local` means package upgrades can safely overwrite `.conf` files without destroying your configuration.

**A minimal `jail.local` configuration:**

```ini
# /etc/fail2ban/jail.local

[DEFAULT]
# Ban duration in seconds (3600 = 1 hour)
bantime  = 3600

# Window in which maxretry failures trigger a ban
findtime = 600

# Number of failures before banning
maxretry = 5

# Email alert destination (optional — requires a local MTA)
# destemail = admin@example.com
# action = %(action_mwl)s

# Use ufw as the ban action backend
banaction = ufw

[sshd]
enabled  = true
port     = ssh
logpath  = %(sshd_log)s
backend  = %(sshd_backend)s
maxretry = 3

[nginx-http-auth]
enabled  = true
port     = http,https
logpath  = /var/log/nginx/error.log
maxretry = 5

[nginx-limit-req]
enabled  = true
port     = http,https
logpath  = /var/log/nginx/error.log
maxretry = 10
```

After editing `jail.local`, restart fail2ban and verify:

```bash
sudo systemctl restart fail2ban

# Show the status of all active jails
sudo fail2ban-client status

# Show details for a specific jail, including currently banned IPs
sudo fail2ban-client status sshd

# Manually unban an IP address that was incorrectly banned
sudo fail2ban-client set sshd unbanip 203.0.113.42
```

**Verifying a ban is working:**

```bash
# Watch the fail2ban log in real time
sudo tail -f /var/log/fail2ban.log

# Example log lines showing a ban event:
# 2026-04-10 14:23:01,482 fail2ban.actions [1234]: NOTICE  [sshd] Ban 198.51.100.77
# 2026-04-10 15:23:01,502 fail2ban.actions [1234]: NOTICE  [sshd] Unban 198.51.100.77
```

### Securing AI Inference Ports — The Ollama Pattern

Ollama exposes a REST API on `http://localhost:11434` by default. When Ollama is installed as a systemd service, it binds to `127.0.0.1:11434`, meaning it is only reachable from the local machine. However, in multi-host or containerized deployments — and if Ollama is started with the `OLLAMA_HOST=0.0.0.0` environment variable — port 11434 becomes reachable on all network interfaces.

**The recommended pattern for AI inference port security:**

```
┌──────────────────────────────────────────────────────────────────┐
│  Public Internet (untrusted)                                     │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  API Gateway / Nginx (0.0.0.0:443)                       │   │
│  │  — TLS termination                                        │   │
│  │  — Bearer token authentication                            │   │
│  │  — Rate limiting                                          │   │
│  │  — Proxy to 127.0.0.1:11434                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │ (loopback only)                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Ollama (127.0.0.1:11434)                                │   │
│  │  — no direct external access                             │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

Firewall rules for this architecture:

```bash
# Start from a clean default-deny state
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (critical — do this before enabling ufw)
sudo ufw allow 22/tcp

# Allow public HTTPS for the API gateway
sudo ufw allow 443/tcp

# Allow HTTP only for Let's Encrypt ACME challenges
sudo ufw allow 80/tcp

# Ollama: allow ONLY from trusted internal subnet (e.g., your VPC or LAN)
# Replace 10.0.0.0/24 with your actual trusted network range
sudo ufw allow from 10.0.0.0/24 to any port 11434 proto tcp

# Explicitly deny port 11434 from everywhere else
# (redundant with default deny, but makes intent explicit in rule listings)
sudo ufw deny 11434/tcp

# Enable the firewall
sudo ufw enable

# Verify the final rule set
sudo ufw status numbered
```

Expected output after configuration:

```
Status: active

     To                         Action      From
     --                         ------      ----
[ 1] 22/tcp                     ALLOW IN    Anywhere
[ 2] 443/tcp                    ALLOW IN    Anywhere
[ 3] 80/tcp                     ALLOW IN    Anywhere
[ 4] 11434/tcp                  ALLOW IN    10.0.0.0/24
[ 5] 11434/tcp                  DENY IN     Anywhere
[ 6] 22/tcp (v6)                ALLOW IN    Anywhere (v6)
[ 7] 443/tcp (v6)               ALLOW IN    Anywhere (v6)
[ 8] 80/tcp (v6)                ALLOW IN    Anywhere (v6)
```

To verify that the firewall is actually blocking access, from a machine **outside** the trusted subnet:

```bash
# This should time out or be refused — if it returns JSON, the port is open
curl --connect-timeout 5 http://<server-ip>:11434/api/tags
# Expected: curl: (28) Connection timed out after 5001 milliseconds
```

From a machine **inside** the trusted subnet:

```bash
# This should return the list of available models
curl http://<server-ip>:11434/api/tags
# Expected: {"models":[...]}
```

### Network Zones — Trusted vs Public Traffic

The concept of **network zones** classifies traffic sources by trust level before applying rules. This concept is formally implemented in `firewalld` (the default firewall manager on Fedora, CentOS, and RHEL), but the mental model applies to any firewall, including ufw.

In a typical AI deployment you have at least two zones:

| Zone | Examples | Trust Level | Typical Permissions |
|---|---|---|---|
| **loopback** | `127.0.0.0/8`, `::1` | Fully trusted | All traffic |
| **internal** | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` | Trusted | SSH, inference APIs, monitoring, management |
| **public** | Everything else | Untrusted | HTTPS (443), HTTP (80) only |
| **blocked** | Known bad IPs, ranges | No trust | Nothing |

Translating this to ufw rules means writing your most restrictive rules for public sources first (via the default deny policy), then carving out specific holes for trusted sources and specific public services:

```bash
# Zone: public — only HTTPS and HTTP allowed
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp

# Zone: internal — SSH management and inference API
sudo ufw allow from 10.0.0.0/8 to any port 22 proto tcp
sudo ufw allow from 10.0.0.0/8 to any port 11434 proto tcp

# Zone: blocked — explicit deny for a known bad actor network
sudo ufw deny from 198.51.100.0/24

# If SSH from public internet is required, restrict to a specific jump host IP
# sudo ufw allow from 203.0.113.10 to any port 22 proto tcp
```

On cloud platforms (AWS, GCP, Azure) you will also have a security group or VPC firewall layer above the OS-level firewall. Both layers should be configured consistently — never rely on only one.

### Disabling Unused Services

Every running service is a potential attack surface. A daemon that is not running cannot be exploited, even if a vulnerability is discovered in it tomorrow. The discipline of disabling unused services is called **reducing the attack surface**.

**Auditing running services:**

```bash
# List all active (running) services managed by systemd
sudo systemctl list-units --type=service --state=active

# List all enabled services (start on boot, whether currently running or not)
sudo systemctl list-unit-files --type=service --state=enabled

# List all open listening ports and the process behind each
sudo ss -tlnp
# or equivalently
sudo netstat -tlnp   # requires net-tools: sudo apt install net-tools

# Example ss output:
# Netid State  Recv-Q Send-Q Local Address:Port  Peer Address:Port  Process
# tcp   LISTEN 0      128    0.0.0.0:22           0.0.0.0:*          users:(("sshd",pid=1234))
# tcp   LISTEN 0      511    0.0.0.0:80           0.0.0.0:*          users:(("nginx",pid=5678))
# tcp   LISTEN 0      128    127.0.0.1:11434      0.0.0.0:*          users:(("ollama",pid=9012))
```

**Disabling and stopping a service:**

```bash
# Stop the service immediately
sudo systemctl stop <service-name>

# Disable it so it does not start on boot
sudo systemctl disable <service-name>

# Verify it is gone from the listening port list
sudo ss -tlnp | grep <port-number>
```

Common services to audit on a new server:

| Service | Default? | Keep if... | Disable if... |
|---|---|---|---|
| `sshd` | Yes | You need remote access | Never disable without a console fallback |
| `avahi-daemon` | Sometimes | Local mDNS discovery needed | Almost always safe to disable on servers |
| `cups` | Sometimes | Server is a print server | Always disable on headless servers |
| `bluetooth` | Sometimes | Bluetooth hardware present | Always disable in cloud/VM environments |
| `snapd` | Ubuntu only | You use snap packages | Safe to disable if you use only apt |
| `apache2` | Sometimes | You use Apache | Disable if you use Nginx exclusively |
| `postfix` | Sometimes | Server sends mail | Can be disabled if all mail is via external relay |

```bash
# A typical hardening sequence for a new AI inference server
sudo systemctl stop avahi-daemon cups bluetooth
sudo systemctl disable avahi-daemon cups bluetooth
sudo systemctl mask avahi-daemon cups bluetooth   # mask prevents re-enabling via dependencies
```

`systemctl mask` goes one step further than disable — it symlinks the unit file to `/dev/null`, making it impossible for any other service or script to start it as a dependency.

---

## Best Practices

1. **Set default policies before adding any allow rules.** Enabling ufw without first setting `default deny incoming` means the firewall starts with permissive defaults. One `sudo ufw default deny incoming` command before `sudo ufw enable` guarantees that only explicitly allowed traffic is accepted from the moment the firewall activates.

2. **Always allow SSH before enabling ufw on a remote session.** Running `sudo ufw enable` on a system where port 22 is not allowed will immediately terminate your SSH session and lock you out. Add `sudo ufw allow 22/tcp` first; verify it appears in `sudo ufw status`, then enable.

3. **Bind AI inference services to loopback or a specific interface, not `0.0.0.0`.** A service bound to `127.0.0.1` is unreachable from outside the machine regardless of firewall configuration. This is a deeper, more reliable control than a firewall rule alone. Configure Ollama with `OLLAMA_HOST=127.0.0.1:11434` unless multi-host access is genuinely required.

4. **Use subnet-scoped rules instead of single-IP rules for internal services.** Internal IPs can change, rotate in autoscaling groups, or be reassigned. A rule allowing `10.0.0.0/24` requires no maintenance when individual host IPs change; a rule for `10.0.0.42` breaks the moment that host is replaced.

5. **Never open a range of ports when you can open a specific one.** `sudo ufw allow 8000:9000/tcp` opens one thousand ports. Determine the exact port your service uses and allow only that. Port ranges are appropriate only for explicitly port-range-based protocols (e.g., passive FTP data channels).

6. **Configure fail2ban with `banaction = ufw` so bans integrate with your existing ruleset.** The default fail2ban action uses iptables directly, which can interact unpredictably with ufw. Setting `banaction = ufw` in `jail.local` ensures fail2ban inserts rules through ufw's interface and they survive `sudo ufw reload`.

7. **Set a `maxretry` of 3 for SSH, not the default 5.** Three failed attempts is enough to accommodate genuine typos. Any legitimate user will contact an administrator after three failures rather than continuing to guess — five or more retries benefit only automated attacks.

8. **Test your firewall from the outside after every change.** It is trivially easy to write a rule that looks correct but is shadowed by an earlier rule. From a second machine or a cloud shell, run `curl --connect-timeout 5 http://<server-ip>:<port>` and `nmap -p <port> <server-ip>` to confirm that blocked ports are actually blocked.

9. **Audit open ports after installing any new software.** Many packages open listening ports on installation without asking. Run `sudo ss -tlnp` after every `apt install` of a server-class package and add or deny ufw rules accordingly.

10. **Mask, do not merely disable, services you will never need.** `systemctl disable` prevents autostart but allows other services to start the unit as a dependency. `systemctl mask` makes the unit completely inert — it cannot be started by any mechanism until explicitly unmasked.

---

## Use Cases

### Use Case 1: Internal-Only Ollama Server Behind an HTTPS Gateway

**Problem:** A team runs Ollama on a GPU server for AI-powered code review. The server must be reachable by CI/CD pipeline workers on the same VPC (`172.31.0.0/20`) and by a public-facing API gateway over HTTPS. Direct access to Ollama from the internet must be impossible.

**Concepts applied:** Default deny incoming, subnet-scoped allow rule for port 11434, public allow rules for 443 and 80, application binding to loopback, fail2ban for the API gateway's Nginx logs.

**Outcome:** CI/CD workers can call `http://172.31.x.x:11434/api/generate` directly. External users authenticate against the Nginx HTTPS gateway, which proxies to Ollama on localhost. Any IP not in `172.31.0.0/20` that probes port 11434 receives no response (connection timeout).

### Use Case 2: Hardening a New Cloud VM Before Deploying an AI Service

**Problem:** A developer spins up a fresh Ubuntu 24.04 instance on a cloud provider. Before installing Ollama, they want to verify the baseline security posture, enable a firewall, and install fail2ban so the machine is hardened before it is ever reachable.

**Concepts applied:** Auditing running services with `ss -tlnp`, setting ufw defaults, allowing only SSH initially, disabling unused daemons (avahi, cups), installing fail2ban before Ollama is installed so brute-force protection is active from the start.

**Outcome:** The machine boots with a minimal attack surface. Only port 22 is open. fail2ban is monitoring SSH logs. Later, when Ollama is installed and port 11434 needs to be accessed from an orchestration node, a single targeted `ufw allow from <node-ip> to any port 11434 proto tcp` opens exactly the required path.

### Use Case 3: Blocking a Malicious Scanner

**Problem:** A server hosting a public AI API gateway is being actively scanned by a botnet. `sudo fail2ban-client status nginx-limit-req` shows that a single IP block (`203.0.113.0/24`) is responsible for thousands of requests per minute. fail2ban's per-IP ban is insufficient because the botnet rotates through the entire `/24`.

**Concepts applied:** Manual subnet-level deny rule in ufw, prioritization of deny rules relative to allow rules, verification with `ufw status numbered`.

**Outcome:** `sudo ufw insert 1 deny from 203.0.113.0/24` inserts a deny rule at position 1, before any allow rules. All traffic from that subnet is dropped before it reaches Nginx. The AI API continues serving legitimate users without interruption.

### Use Case 4: Migrating from Default SSH Port to Reduce Noise

**Problem:** Server logs show thousands of SSH scan attempts per day against port 22. The team wants to move SSH to a non-standard port (e.g., `2222`) to reduce automated noise, and update the firewall rules atomically without locking themselves out.

**Concepts applied:** Adding a new allow rule before removing the old one, verifying both rules are present with `ufw status numbered`, testing the new port from a second session before deleting the old rule, updating fail2ban's `[sshd]` jail `port` setting.

**Outcome:** SSH on port 2222 is confirmed working before port 22 is closed. fail2ban's `[sshd]` jail is updated to `port = 2222`. Automated SSH scanners hitting port 22 receive no response.

---

## Hands-on Examples

### Example 1: Configuring ufw for an AI Inference Server from Scratch

You have a fresh Ubuntu 24.04 server. You want to install and configure ufw so that: SSH is accessible from anywhere, HTTPS is open publicly, and Ollama on port 11434 is accessible only from a trusted subnet `10.10.0.0/24`.

**Step 1: Verify current firewall state and open ports.**

```bash
sudo ufw status
# Expected: Status: inactive

sudo ss -tlnp
# Note which ports are already listening before you change anything
```

**Step 2: Set default policies.**

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw default deny routed
```

**Step 3: Add allow rules for required services.**

```bash
sudo ufw allow 22/tcp
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp
sudo ufw allow from 10.10.0.0/24 to any port 11434 proto tcp
```

**Step 4: Enable the firewall.**

```bash
sudo ufw enable
# Prompted: Command may disrupt existing ssh connections. Proceed with operation (y|n)? y
# Expected: Firewall is active and enabled on system startup
```

**Step 5: Verify the rule set.**

```bash
sudo ufw status numbered
```

Expected output:

```
Status: active

     To                         Action      From
     --                         ------      ----
[ 1] 22/tcp                     ALLOW IN    Anywhere
[ 2] 443/tcp                    ALLOW IN    Anywhere
[ 3] 80/tcp                     ALLOW IN    Anywhere
[ 4] 11434/tcp                  ALLOW IN    10.10.0.0/24
[ 5] 22/tcp (v6)                ALLOW IN    Anywhere (v6)
[ 6] 443/tcp (v6)               ALLOW IN    Anywhere (v6)
[ 7] 80/tcp (v6)                ALLOW IN    Anywhere (v6)
```

**Step 6: Test connectivity from an external machine.**

```bash
# From a machine NOT in 10.10.0.0/24:
curl --connect-timeout 5 http://<server-ip>:11434/api/tags
# Expected: curl: (28) Connection timed out after 5001 milliseconds

# From a machine IN 10.10.0.0/24 (or from localhost using 127.0.0.1):
curl http://127.0.0.1:11434/api/tags
# Expected (if Ollama is running): {"models":[...]}
```

---

### Example 2: Installing and Configuring fail2ban for SSH and Nginx

You want fail2ban to ban any IP that fails SSH authentication three times within ten minutes, and to ban any IP that triggers Nginx's HTTP auth failure five times within ten minutes.

**Step 1: Install fail2ban.**

```bash
sudo apt update && sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

**Step 2: Create the local configuration file.**

```bash
sudo nano /etc/fail2ban/jail.local
```

Paste the following content:

```ini
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5
banaction = ufw

[sshd]
enabled  = true
port     = ssh
logpath  = %(sshd_log)s
backend  = %(sshd_backend)s
maxretry = 3

[nginx-http-auth]
enabled  = true
port     = http,https
logpath  = /var/log/nginx/error.log
maxretry = 5
```

Save and close (`Ctrl+O`, `Enter`, `Ctrl+X` in nano).

**Step 3: Restart fail2ban and verify jails are active.**

```bash
sudo systemctl restart fail2ban

sudo fail2ban-client status
```

Expected output:

```
Status
|- Number of jail:      2
`- Jail list:   nginx-http-auth, sshd
```

**Step 4: Verify the sshd jail configuration.**

```bash
sudo fail2ban-client status sshd
```

Expected output (no bans yet on a fresh install):

```
Status for the jail: sshd
|- Filter
|  |- Currently failed: 0
|  |- Total failed:     0
|  `- File list:        /var/log/auth.log
`- Actions
   |- Currently banned: 0
   |- Total banned:     0
   `- Banned IP list:
```

**Step 5: Monitor the log for ban events.**

```bash
sudo tail -f /var/log/fail2ban.log
```

Leave this running in one terminal. In a second terminal, simulate checking whether the ufw ban action is wired correctly:

```bash
# Manually trigger a test ban (use an IP you can unban safely)
sudo fail2ban-client set sshd banip 192.0.2.1

# Check that ufw now lists a deny rule for that IP
sudo ufw status | grep 192.0.2.1
# Expected: Anywhere                   DENY IN     192.0.2.1

# Unban the test IP
sudo fail2ban-client set sshd unbanip 192.0.2.1

# Verify the ufw rule is removed
sudo ufw status | grep 192.0.2.1
# Expected: (no output)
```

---

### Example 3: Auditing and Disabling Unused Services

You have just provisioned a new Ubuntu 22.04 server. Before deploying anything, you want to identify and disable services that have no role on a headless AI server.

**Step 1: List all currently listening ports.**

```bash
sudo ss -tlnp
```

**Step 2: List all enabled services.**

```bash
sudo systemctl list-unit-files --type=service --state=enabled
```

**Step 3: Identify and disable services with no role on this server.**

```bash
# Check if avahi-daemon is running (mDNS — not needed on a server)
sudo systemctl status avahi-daemon

# Stop and mask it
sudo systemctl stop avahi-daemon
sudo systemctl mask avahi-daemon

# Check if cups is running (printing — never needed on a headless server)
sudo systemctl status cups 2>/dev/null || echo "cups not installed"

# If present:
sudo systemctl stop cups
sudo systemctl mask cups
```

**Step 4: Confirm the ports are no longer listening.**

```bash
sudo ss -tlnp
# Verify that ports associated with disabled services (e.g., 631 for cups, 5353 for avahi) are gone
```

**Step 5: Document your changes.**

```bash
# Record what is running for future reference
sudo systemctl list-units --type=service --state=active > ~/active-services-$(date +%F).txt
sudo ss -tlnp > ~/open-ports-$(date +%F).txt
```

---

### Example 4: Reading and Interpreting iptables Rules Generated by ufw

After configuring ufw, you want to understand what iptables rules it has actually created in the kernel.

**Step 1: Dump all active iptables rules.**

```bash
sudo iptables-save
```

**Step 2: Filter to show only the rules ufw created for port 11434.**

```bash
sudo iptables-save | grep 11434
```

Expected output (will vary slightly by system):

```
-A ufw-user-input -s 10.10.0.0/24 -p tcp -m tcp --dport 11434 -j ACCEPT
-A ufw-user-input -p tcp -m tcp --dport 11434 -j DROP
```

This confirms that ufw translated your `allow from 10.10.0.0/24 to any port 11434` and `deny 11434` rules into exact iptables commands:
- The first line accepts TCP to port 11434 when the source is in `10.10.0.0/24`
- The second line drops everything else hitting port 11434

**Step 3: Check the IPv6 equivalent.**

```bash
sudo ip6tables-save | grep 11434
```

If you only added an IPv4 rule (e.g., `from 10.10.0.0/24`), the IPv6 table may have a permissive rule for port 11434. Explicitly deny the IPv6 port unless you have an IPv6 use case:

```bash
sudo ufw deny in on all to ::0/0 port 11434 proto tcp
# Simpler approach: deny the port without specifying source (covers IPv4 and IPv6)
sudo ufw deny 11434/tcp
sudo ufw status numbered
# Rule 5 from Example 1 already does this — verify it covers IPv6
```

---

## Common Pitfalls

### Pitfall 1: Enabling ufw Without an SSH Allow Rule

**Description:** Running `sudo ufw enable` from a remote SSH session without first allowing port 22 immediately terminates the session and locks you out of the server.

**Why it happens:** The default policy after enabling is `deny incoming`, and ufw applies it instantly. There is no grace period.

**Incorrect pattern:**
```bash
sudo ufw default deny incoming
sudo ufw enable   # <-- locks you out if SSH is not already allowed
```

**Correct pattern:**
```bash
sudo ufw default deny incoming
sudo ufw allow 22/tcp   # <-- allow SSH FIRST
sudo ufw status         # <-- confirm the rule is listed before enabling
sudo ufw enable
```

---

### Pitfall 2: Confusing Rule Ordering — Allow After Deny

**Description:** A specific allow rule added after a broad deny rule has no effect, because ufw evaluates rules top-to-bottom and stops at the first match.

**Why it happens:** Developers familiar with other firewalls (e.g., AWS Security Groups, which have no ordering) expect that `allow` rules override `deny` rules regardless of position.

**Incorrect pattern:**
```bash
sudo ufw deny 11434/tcp
sudo ufw allow from 10.0.0.0/24 to any port 11434 proto tcp
# The allow rule will never be reached because deny is evaluated first
```

**Correct pattern:**
```bash
# Add the specific allow rule first
sudo ufw allow from 10.0.0.0/24 to any port 11434 proto tcp
# Then add the broad deny for everything else
sudo ufw deny 11434/tcp
# Verify order with numbered output
sudo ufw status numbered
```

---

### Pitfall 3: Forgetting That ufw Manages Both IPv4 and IPv6

**Description:** A rule written as `sudo ufw allow from 10.0.0.0/24 to any port 11434` applies only to IPv4. If your server has an IPv6 address and an attacker connects over IPv6, they bypass the rule.

**Why it happens:** ufw handles IPv4 and IPv6 as separate rule sets. Rules with explicit IPv4 source addresses do not apply to IPv6 traffic.

**Incorrect assumption:** Writing an IPv4 source-restricted rule and assuming port 11434 is completely protected.

**Correct pattern:**
```bash
# Add both an IPv4-scoped allow (for your internal subnet)
sudo ufw allow from 10.0.0.0/24 to any port 11434 proto tcp
# AND a universal deny that covers both IPv4 and IPv6
sudo ufw deny 11434/tcp
# The deny with no source qualifier applies to both protocol families
sudo ufw status numbered
```

---

### Pitfall 4: Editing `jail.conf` Instead of `jail.local`

**Description:** Modifying `/etc/fail2ban/jail.conf` directly causes your configuration to be overwritten the next time the `fail2ban` package is upgraded.

**Why it happens:** The file is well-organized and tempting to edit in place. There is no warning when you open it.

**Incorrect pattern:**
```bash
sudo nano /etc/fail2ban/jail.conf   # direct edit — will be lost on upgrade
```

**Correct pattern:**
```bash
# Create or edit jail.local — this file is never touched by apt upgrades
sudo nano /etc/fail2ban/jail.local
# Only put the sections and settings you want to override
```

---

### Pitfall 5: Setting `banaction` to the Default iptables Action When Using ufw

**Description:** fail2ban's default `banaction` is `iptables-multiport`, which inserts rules directly into iptables. On a ufw-managed system, these rules are erased whenever `sudo ufw reload` or `sudo systemctl restart ufw` is run.

**Why it happens:** fail2ban's upstream default does not assume ufw is present. New installs inherit the default.

**Incorrect pattern (`jail.local` without banaction override):**
```ini
[DEFAULT]
# banaction not set — uses iptables-multiport by default
```

**Correct pattern:**
```ini
[DEFAULT]
banaction = ufw
```

---

### Pitfall 6: Assuming `systemctl disable` Prevents a Service from Starting

**Description:** `systemctl disable` removes the service from the boot-time autostart list, but another service that lists the disabled service as a dependency can still start it. `systemctl mask` is the only reliable way to prevent a service from ever starting.

**Why it happens:** The distinction between disabled and masked is easy to overlook in documentation.

**Incorrect pattern (for services you want completely inert):**
```bash
sudo systemctl disable avahi-daemon
# avahi-daemon can still be started by nss-mdns or similar dependencies
```

**Correct pattern:**
```bash
sudo systemctl stop avahi-daemon
sudo systemctl mask avahi-daemon
# Masking creates a symlink to /dev/null — no process can start it
```

---

### Pitfall 7: Exposing Ollama by Setting `OLLAMA_HOST=0.0.0.0` Without a Firewall Rule

**Description:** The `OLLAMA_HOST` environment variable is commonly set to `0.0.0.0` in tutorials so that Docker containers or remote hosts can reach Ollama. If this is done on a cloud VM before firewall rules are in place, port 11434 becomes publicly accessible with no authentication.

**Why it happens:** Tutorials prioritize getting things working quickly and omit security context. The step "set `OLLAMA_HOST=0.0.0.0`" precedes "configure your firewall" in many guides.

**Incorrect pattern (on a cloud VM):**
```bash
export OLLAMA_HOST=0.0.0.0
ollama serve   # port 11434 is now publicly exposed, no authentication
```

**Correct pattern:**
```bash
# Step 1: configure the firewall FIRST
sudo ufw allow from 10.0.0.0/24 to any port 11434 proto tcp
sudo ufw deny 11434/tcp
# Step 2: verify rules are active
sudo ufw status numbered
# Step 3: only then set OLLAMA_HOST and start the service
export OLLAMA_HOST=0.0.0.0
ollama serve
```

---

## Summary

- `ufw` provides an accessible command-line interface to Linux packet filtering. Correct use requires setting `default deny incoming` before enabling, always allowing SSH before activation, and writing subnet-scoped allow rules for AI inference ports like Ollama's 11434 so that only trusted internal traffic can reach them.
- Rule ordering in ufw is significant: the firewall evaluates rules top-to-bottom and stops at the first match, so specific allow rules must precede broad deny rules; use `ufw status numbered` and `ufw delete <n>` to audit and correct ordering.
- `iptables` is the kernel-level framework underlying ufw; reading `iptables-save` output lets you verify that the rules you wrote in ufw are correctly translated, catch IPv6 gaps, and interpret existing configurations on systems that do not use ufw.
- `fail2ban` monitors log files and automatically issues time-limited bans for IPs that exhibit brute-force patterns; configuring it with `banaction = ufw` in `jail.local` integrates bans with the ufw rule set and ensures they survive firewall reloads.
- Minimizing the attack surface — by binding services to loopback where possible, disabling unneeded daemons with `systemctl mask`, and auditing open ports with `ss -tlnp` after every new installation — is as important as any firewall rule, because a service that is not running or not reachable cannot be exploited.

---

## Further Reading

- [Ubuntu UFW Documentation](https://help.ubuntu.com/community/UFW) — The official Ubuntu community guide covering all ufw commands, default policies, application profiles, and logging configuration; the authoritative first reference for Ubuntu/Debian deployments.

- [ufw man page (manpages.ubuntu.com)](https://manpages.ubuntu.com/manpages/noble/man8/ufw.8.html) — The full manual page for ufw on Ubuntu 24.04 (Noble); covers every flag, rule syntax, and configuration file location with precise technical detail.

- [fail2ban Official Documentation](https://www.fail2ban.org/wiki/index.php/Main_Page) — The fail2ban project wiki with complete coverage of jail configuration, filter regex syntax, action scripts, and integration with multiple firewall backends including ufw.

- [Ollama FAQ — Network Binding and Security](https://github.com/ollama/ollama/blob/main/docs/faq.md) — Ollama's official FAQ covering `OLLAMA_HOST` configuration, how to bind to specific interfaces, and security considerations for exposing the API; essential reading before deploying Ollama beyond a local workstation.

- [DigitalOcean: How To Set Up a Firewall with UFW on Ubuntu](https://www.digitalocean.com/community/tutorials/how-to-set-up-a-firewall-with-ufw-on-ubuntu) — A comprehensive practical tutorial covering ufw setup, rule management, logging, and IPv6 considerations, with clear step-by-step examples suitable for server hardening walkthroughs.

- [DigitalOcean: How To Protect SSH with Fail2Ban on Ubuntu](https://www.digitalocean.com/community/tutorials/how-to-protect-ssh-with-fail2ban-on-ubuntu) — Detailed walkthrough of fail2ban installation, jail configuration for SSH, testing bans, and integrating with ufw; mirrors real-world server hardening practice closely.

- [Linux iptables: A Beginner's Guide (Red Hat)](https://www.redhat.com/en/blog/iptables-beginners-guide) — Red Hat's introduction to iptables concepts, chains, targets, and rule syntax; useful for understanding what ufw generates under the hood and for reading iptables configurations on RHEL/CentOS systems.

- [NIST SP 800-123: Guide to General Server Security](https://csrc.nist.gov/publications/detail/sp/800-123/final) — The US National Institute of Standards and Technology's server security baseline guide; covers patch management, account controls, network service minimization, and firewall policy in a framework-neutral way applicable to any Linux server deployment.
