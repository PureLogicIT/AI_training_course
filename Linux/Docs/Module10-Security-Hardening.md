# Module 10: Security Hardening for Production AI Servers
> Subject: Linux | Difficulty: Intermediate | Estimated Time: 300 minutes

## Objective

After completing this module, you will be able to harden a production Ubuntu/Debian Linux server that hosts AI inference services and exposes an internal API to authorized users. Specifically, you will configure `sshd_config` to eliminate root login, password authentication, and brute-force exposure; write sudoers rules that restrict each service account to precisely the commands it needs; install and configure `auditd` to log security-relevant events; create and apply an AppArmor profile that confines an AI service process; enable unattended security updates without disrupting long-running model inference; manage secrets on disk using restrictive file permissions and `.env` files instead of plaintext environment variables; isolate AI workloads in a network namespace; locate world-writable files and SUID binaries that attackers commonly exploit; run a Lynis audit and interpret its hardening index; and follow a practical incident response checklist when anomalies are detected. You will apply the relevant CIS Benchmark controls at each step so your configuration maps to an auditable standard.

## Prerequisites

- Completed Module 1 (if it exists in this subject) or equivalent: comfortable with the Linux filesystem hierarchy, basic shell commands, file permissions (`chmod`, `chown`), and package management (`apt`)
- Completed Module 2 or equivalent: understanding of Linux users, groups, and the `/etc/passwd` / `/etc/shadow` / `/etc/sudoers` structure
- Able to SSH into a test server — a local VM or cloud instance running Ubuntu 22.04 LTS or Ubuntu 24.04 LTS is strongly recommended (do **not** practice on a production host until you have rehearsed in a VM)
- Root or sudo access on the practice server
- Basic familiarity with `systemctl`, `journalctl`, and text editing via `vim` or `nano`
- Understanding of what an AI API service is: a process that listens on a TCP port, loads model weights, and serves inference requests to internal clients

## Key Concepts

### SSH Hardening

SSH is the primary administrative surface of any Linux server. Default OpenSSH installations are secure enough for casual use but ship with several settings that are unacceptable for a server handling sensitive data. Every setting change below must be made in `/etc/ssh/sshd_config` (or a drop-in file under `/etc/ssh/sshd_config.d/` — the drop-in directory is the preferred approach on Ubuntu 22.04+ because it survives package upgrades without clobbering your customizations).

**Disable root login.** The root account is a known target in every brute-force campaign. Even if root login requires a key, there is no audit trail separating individual operators. Set `PermitRootLogin no`. Operators must log in as a named user and escalate with `sudo`.

**Disable password authentication.** Passwords are guessable and phishable; SSH public keys are not. Set `PasswordAuthentication no` and `KbdInteractiveAuthentication no` (the latter replaces `ChallengeResponseAuthentication` in OpenSSH 8.7+). Ensure every authorized user has their public key in `~/.ssh/authorized_keys` before applying this change — locking yourself out is a common and painful mistake.

**Restrict which users may log in.** `AllowUsers` accepts a whitespace-separated list of usernames (optionally with `user@host` patterns). Only accounts explicitly listed can authenticate, even if they have valid keys. For an AI server, this list might be two or three named operators plus the service account used by your deployment pipeline.

**Reduce the attack window.** `MaxAuthTries 3` causes SSH to drop the connection after three failed authentication attempts per connection, limiting the value of automated key-guessing. `LoginGraceTime 30` drops unauthenticated connections after 30 seconds. `ClientAliveInterval 300` combined with `ClientAliveCountMax 2` terminates idle sessions after ~10 minutes, reducing the window for an unattended terminal to be hijacked.

**Change the listening port.** Moving SSH off port 22 is not a security control — it is noise reduction. It eliminates the constant automated scan traffic in your logs, making genuine intrusion attempts far easier to spot. A port in the range 1024–65535 that is not used by any other service is sufficient. Document the port in your infrastructure runbook.

A hardened drop-in file looks like this:

```
# /etc/ssh/sshd_config.d/99-hardening.conf
# Applied on top of the default /etc/ssh/sshd_config.
# Reload with: sudo systemctl reload ssh

Port 2222
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
AllowUsers alice bob deploy-bot
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
Banner /etc/ssh/banner.txt
```

After editing, validate syntax before reloading: `sudo sshd -t` exits with no output on success, or prints the error and line number on failure. Never run `systemctl restart ssh` without first running `sshd -t`.

### Sudo Hardening

`sudo` grants temporary privilege elevation. The default `%sudo ALL=(ALL:ALL) ALL` rule that Ubuntu ships means any member of the `sudo` group can run any command as root. That is appropriate for a developer workstation; it is not appropriate for a server where a compromised session could delete model weights, exfiltrate API keys, or pivot to other internal systems.

**Principle of least privilege for operators.** Replace broad `ALL` grants with explicit command allowlists using `Cmnd_Alias`. An AI-ops engineer who only needs to restart the inference service and read logs does not need the ability to run `bash`, `python`, or `chmod`.

**NOPASSWD only for automation.** `NOPASSWD` is justified when a non-interactive process (a systemd service, a CI runner, a deployment script) must run a privileged command without a TTY. It is not justified for human operators who are present at a terminal. If a human account has `NOPASSWD`, a stolen session token gives an attacker silent root escalation.

**Protect the sudoers file.** Always edit via `visudo` — it validates syntax before saving. A syntax error in `/etc/sudoers` can lock every user out of sudo. Drop-in files go in `/etc/sudoers.d/`; they must be owned by root and have mode `0440` or `sudo` will refuse to read them.

**Key global defaults to set:**

```
# /etc/sudoers.d/00-global-defaults
# visudo -f /etc/sudoers.d/00-global-defaults

Defaults env_reset
Defaults secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Defaults logfile="/var/log/sudo.log"
Defaults log_input, log_output
Defaults requiretty
Defaults timestamp_timeout=5
```

`env_reset` strips the calling user's environment before executing the privileged command, preventing environment-variable injection attacks. `requiretty` prevents sudo from being invoked from a non-TTY context (such as a cron job or a web shell) unless explicitly overridden. `timestamp_timeout=5` means the sudo credential cache expires after 5 minutes.

**An allowlist rule for an AI-ops engineer:**

```
# /etc/sudoers.d/10-ai-ops
# visudo -f /etc/sudoers.d/10-ai-ops

Cmnd_Alias AI_SERVICE_CMDS = \
    /usr/bin/systemctl restart ai-inference, \
    /usr/bin/systemctl status ai-inference, \
    /usr/bin/systemctl stop ai-inference, \
    /usr/bin/journalctl -u ai-inference

# alice and bob may run these commands; password required each time
alice,bob ALL=(root) AI_SERVICE_CMDS

# deploy-bot runs systemctl reload only, no password (CI/CD pipeline)
deploy-bot ALL=(root) NOPASSWD: /usr/bin/systemctl reload ai-inference
```

### auditd — Kernel-Level Security Event Logging

`auditd` is the Linux kernel audit subsystem. Unlike `syslog` or `journald`, which log application-level events, `auditd` captures events at the syscall level: file opens, permission changes, privilege escalations, network socket creation, and more. Its records are tamper-evident — a process cannot silently suppress its own audit trail because the kernel writes directly to the audit ring buffer before the syscall completes.

Install and start it:

```bash
sudo apt install auditd audispd-plugins
sudo systemctl enable --now auditd
```

Audit rules are loaded from `/etc/audit/rules.d/*.rules` (files processed in alphabetical order) and compiled into `/etc/audit/audit.rules` by `augenrules`. Rules survive reboots when loaded this way.

**Key rule categories for an AI server:**

```bash
# /etc/audit/rules.d/50-ai-server.rules

# Log all authentication events
-w /etc/passwd -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/sudoers -p wa -k sudoers_changes
-w /etc/sudoers.d/ -p wa -k sudoers_changes

# Log SSH configuration changes
-w /etc/ssh/sshd_config -p wa -k sshd_config
-w /etc/ssh/sshd_config.d/ -p wa -k sshd_config

# Log privilege escalation
-a always,exit -F arch=b64 -S setuid -S setgid -k privilege_escalation
-a always,exit -F arch=b64 -S execve -F euid=0 -k root_commands

# Log access to model weights and API key directories
-w /opt/ai-models/ -p rwa -k model_access
-w /etc/ai-service/ -p rwa -k ai_service_config

# Log network socket creation by the inference process
-a always,exit -F arch=b64 -S socket -F exe=/usr/bin/python3 -k ai_socket

# Make rules immutable until next reboot (must be last rule)
-e 2
```

The `-e 2` flag at the end locks the rule set. An attacker who gains root cannot silently unload audit rules without rebooting the server (and a reboot is itself an auditable event).

Query audit logs with `ausearch`:

```bash
# Show all events tagged with the 'sudoers_changes' key
sudo ausearch -k sudoers_changes --interpret

# Show privilege escalation events in the last hour
sudo ausearch -k privilege_escalation --start recent --interpret

# Generate a summary report
sudo aureport --summary
```

### AppArmor Basics for AI Services

AppArmor is a Linux Security Module that enforces mandatory access control (MAC) using per-program profiles. A profile declares exactly which files, network resources, and capabilities a process may access. Any access attempt not listed in the profile is denied and logged. This means that even if your inference server process is compromised — for example, a prompt injection attack causes it to execute arbitrary code — AppArmor limits what damage that code can do.

AppArmor ships enabled by default on Ubuntu. Verify status:

```bash
sudo aa-status
# Expected output includes:
# apparmor module is loaded.
# N profiles are loaded.
# N profiles are in enforce mode.
```

AppArmor profiles live in `/etc/apparmor.d/`. Profile names conventionally mirror the full path to the binary they confine (e.g., `usr.bin.python3` for `/usr/bin/python3`).

**Creating a profile for an AI inference service.** The `aa-genprof` tool runs the application, watches what it does, and generates a draft profile. For a service that cannot be easily run interactively, start in `complain` mode (log violations but don't block), run representative workloads, then convert to `enforce` mode:

```bash
# Step 1: Generate an initial profile in complain mode
sudo aa-genprof /usr/local/bin/ai-inference-server

# Step 2: In a separate terminal, start the service and run test requests
sudo systemctl start ai-inference
curl http://localhost:8080/v1/health

# Step 3: Back in the aa-genprof terminal, press S to scan and F to finish
# Step 4: Review and load
sudo aa-enforce /etc/apparmor.d/usr.local.bin.ai-inference-server
sudo apparmor_parser -r /etc/apparmor.d/usr.local.bin.ai-inference-server
```

A hand-written minimal profile for an inference server that reads model weights and serves HTTP:

```
# /etc/apparmor.d/usr.local.bin.ai-inference-server

#include <tunables/global>

/usr/local/bin/ai-inference-server {
  #include <abstractions/base>
  #include <abstractions/python>

  # Allow reading model weights (read-only)
  /opt/ai-models/** r,

  # Allow reading its own config
  /etc/ai-service/config.yaml r,
  /etc/ai-service/.env r,

  # Allow writing to its log directory
  /var/log/ai-inference/** rw,

  # Allow binding to the inference port
  network tcp,

  # Deny everything else — no shell, no /etc/shadow, no /proc/*/mem
  deny /bin/sh x,
  deny /bin/bash x,
  deny /etc/shadow r,
  deny /proc/*/mem rw,
}
```

Switch between modes without losing the profile:

```bash
sudo aa-complain /etc/apparmor.d/usr.local.bin.ai-inference-server   # log but allow
sudo aa-enforce  /etc/apparmor.d/usr.local.bin.ai-inference-server   # block violations
```

### Automatic Security Updates with unattended-upgrades

A server that handles PII or proprietary model weights must receive security patches promptly. Manual update workflows fail silently during on-call weekends. `unattended-upgrades` applies security-only package updates automatically, leaving major version upgrades — which could break model dependencies — for a human to apply deliberately.

Install and configure:

```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
# Answer "Yes" to enable automatic updates
```

The configuration lives in `/etc/apt/apt.conf.d/50unattended-upgrades`. For an AI server, the critical adjustments are:

```
# /etc/apt/apt.conf.d/50unattended-upgrades (relevant sections)

Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    // Do NOT include -updates or -backports — those can change library ABIs
};

// Automatically remove unused packages after upgrade
Unattended-Upgrade::Remove-Unused-Dependencies "true";

// Reboot only during a maintenance window, not immediately
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Automatic-Reboot-Time "03:00";

// Email the ops team on failure
Unattended-Upgrade::Mail "ops@yourcompany.internal";
Unattended-Upgrade::MailReport "on-change";
```

Setting `Automatic-Reboot "false"` is deliberate: reboots interrupt inference workloads. Instead, monitor for the `/var/run/reboot-required` sentinel file in your monitoring stack and schedule reboots during planned maintenance windows.

Verify the timer is active and inspect what would be upgraded without actually applying it:

```bash
sudo systemctl status unattended-upgrades
sudo unattended-upgrade --dry-run --debug 2>&1 | grep -E "(Packages|error)"
```

### Secrets Management on Disk

An AI service needs credentials: database passwords, object storage keys, API tokens for upstream model providers. These secrets must never appear in:
- Environment variables set at shell login (they are visible in `/proc/<pid>/environ` to any user who can read that file)
- Docker Compose `environment:` blocks checked into version control
- Log files (log libraries often serialize entire configuration objects)
- Git history (a secret committed even once is compromised forever)

**The `.env` file pattern.** Store secrets in a file that is owned by the service account, readable only by that account, and never checked into version control:

```bash
# Create the secrets file
sudo install -o ai-service -g ai-service -m 600 /dev/null /etc/ai-service/.env

# Populate it — do this manually or via a secrets provisioning tool
sudo -u ai-service tee /etc/ai-service/.env > /dev/null << 'EOF'
DATABASE_URL=postgresql://ai_user:CHANGEME@db.internal:5432/ai_prod
OPENAI_API_KEY=sk-...
MODEL_SIGNING_SECRET=...
EOF

# Verify permissions
stat /etc/ai-service/.env
# Output should show: Access: (0600/-rw-------)  Uid: ( ai-service)
```

The systemd unit for the AI service loads the file via `EnvironmentFile=`:

```ini
# /etc/systemd/system/ai-inference.service (relevant section)
[Service]
User=ai-service
Group=ai-service
EnvironmentFile=/etc/ai-service/.env
ExecStart=/usr/local/bin/ai-inference-server --config /etc/ai-service/config.yaml
```

This pattern keeps secrets out of the process table's environment display (`ps e`) for other users, because systemd reads the file before exec and does not expose it via `/proc/<pid>/environ` in a way that is readable by other unprivileged users (the `/proc/<pid>/environ` file is owned by the process's UID and readable only by that UID and root).

**Never do this:**

```bash
# BAD: Secret visible to all users via `ps aux`
export DATABASE_URL="postgresql://user:password@host/db"
python ai_server.py

# BAD: Secret stored world-readable
chmod 644 /etc/ai-service/.env
```

**For higher security environments:** Consider `systemd-creds` (systemd 250+, Ubuntu 22.04+), which can encrypt credentials at rest using a machine-specific TPM key, or a secrets manager such as HashiCorp Vault, AWS Secrets Manager, or Azure Key Vault that delivers secrets at runtime via API rather than storing them in files at all.

### Finding World-Writable Files and SUID Binaries

World-writable files allow any user on the system to modify them. If an attacker gains access as any unprivileged user, they can overwrite world-writable scripts or configs that are later executed with elevated privileges. SUID (Set-UID) binaries run with the owner's UID (often root) regardless of who executes them — every unnecessary SUID binary is a potential privilege escalation vector.

**Find world-writable files:**

```bash
# Search the entire filesystem, excluding /proc and /sys (virtual filesystems)
sudo find / -xdev -type f -perm -o+w \
    ! -path "/proc/*" ! -path "/sys/*" ! -path "/dev/*" \
    2>/dev/null

# Expected benign results: files under /tmp with the sticky bit,
# named pipes in /run. Flag anything in /etc, /opt, /usr, /home, /var/log.
```

**Find SUID and SGID binaries:**

```bash
# SUID binaries (run as file owner)
sudo find / -xdev -type f \( -perm -4000 \) \
    ! -path "/proc/*" ! -path "/sys/*" \
    2>/dev/null | sort

# SGID binaries (run as file group)
sudo find / -xdev -type f \( -perm -2000 \) \
    ! -path "/proc/*" ! -path "/sys/*" \
    2>/dev/null | sort
```

Compare the output against a known-good baseline. Legitimate SUID binaries on a minimal Ubuntu server include `sudo`, `su`, `passwd`, `newgrp`, `chsh`, `chfn`, `mount`, `umount`, and `ssh-agent`. Any binary not in this list — especially shell interpreters, Python, or custom application binaries — should be investigated and removed if not required:

```bash
# Remove SUID bit from a binary that does not need it
sudo chmod u-s /usr/bin/at
```

**Automate baseline comparison.** Record the current state after initial hardening and check for drift:

```bash
# Record baseline
sudo find / -xdev -type f -perm -4000 2>/dev/null | sort > /root/suid_baseline.txt

# Check for new SUID files added since baseline
sudo find / -xdev -type f -perm -4000 2>/dev/null | sort > /tmp/suid_current.txt
diff /root/suid_baseline.txt /tmp/suid_current.txt
```

### Network Namespace Isolation

Linux network namespaces allow a process to have its own independent network stack — its own interfaces, routing tables, firewall rules, and port space. For an AI inference server, running the service in a network namespace means that even if the process is fully compromised, it cannot reach other internal services (your database, your internal orchestrator) unless you explicitly wire in those routes via a virtual ethernet pair (`veth`).

This is a lower-level, more surgical tool than Docker networking (which uses namespaces under the hood). It is most useful when running a bare-metal inference service that you cannot containerize easily due to hardware access requirements (GPU drivers, RDMA adapters).

**Creating an isolated namespace for AI inference:**

```bash
# Create a persistent network namespace
sudo ip netns add ai-inference-ns

# Create a veth pair: one end in root ns, one end in the new ns
sudo ip link add veth-host type veth peer name veth-ai

# Move the ai-side interface into the namespace
sudo ip link set veth-ai netns ai-inference-ns

# Assign IPs
sudo ip addr add 10.99.0.1/30 dev veth-host
sudo ip netns exec ai-inference-ns ip addr add 10.99.0.2/30 dev veth-ai

# Bring up both interfaces
sudo ip link set veth-host up
sudo ip netns exec ai-inference-ns ip link set veth-ai up
sudo ip netns exec ai-inference-ns ip link set lo up

# Add a default route in the namespace pointing to the host
sudo ip netns exec ai-inference-ns ip route add default via 10.99.0.1

# Run the inference service inside the namespace
sudo ip netns exec ai-inference-ns \
    sudo -u ai-service /usr/local/bin/ai-inference-server
```

Add `iptables` rules on the host to control what the namespace can reach:

```bash
# Allow inference clients on the internal network to reach the service port
sudo iptables -I FORWARD -i veth-host -p tcp --dport 8080 -j ACCEPT

# Block the inference ns from initiating connections to the database directly
# (it must go through the application layer, not raw TCP)
sudo iptables -I FORWARD -i veth-host -d 10.0.1.5 -j DROP
```

Make the namespace and `iptables` rules persistent across reboots by encoding them in a systemd unit or using `ip-netns` with a configuration management tool.

### Vulnerability Scanning with Lynis

Lynis is an open-source security auditing tool that runs locally on the server, performs hundreds of checks across every hardening domain covered in this module, and produces a scored report with specific remediation suggestions. It is CIS-Benchmark-aware, mapping its findings to relevant controls.

Install and run:

```bash
sudo apt install lynis

# Run a full system audit as root
sudo lynis audit system 2>&1 | tee /var/log/lynis-$(date +%Y%m%d).log
```

Lynis produces a **Hardening Index** score between 0 and 100. A freshly installed Ubuntu server typically scores in the 55–65 range. After applying the controls in this module, scores of 75–85 are achievable. CIS Level 1 compliance typically aligns with scores above 70; Level 2 above 80.

Key sections of the Lynis report to focus on for an AI server:

```
[+] SSH and authentication
[+] File permissions
[+] Software: file integrity
[+] Kernel hardening
[+] Logging and auditing
[+] Networking
```

At the bottom of the report, Lynis prints `Suggestions` and `Warnings`. Warnings are items with known active risk; Suggestions are improvements that reduce attack surface. Address all Warnings before production deployment.

```bash
# Show only the actionable findings
sudo lynis audit system 2>/dev/null | grep -E "^\[WARNING\]|^\[SUGGESTION\]"

# Run just one test category during iterative hardening
sudo lynis audit system --tests-category "authentication"
```

### CIS Benchmark Overview

The Center for Internet Security (CIS) publishes Benchmarks — detailed, peer-reviewed hardening guides for every major operating system. The CIS Ubuntu Linux 22.04 LTS Benchmark and the CIS Ubuntu Linux 24.04 LTS Benchmark are the authoritative references for the controls in this module.

CIS Benchmarks define two profiles:

| Profile | Description |
|---|---|
| Level 1 | Practical, low-disruption hardening. All controls can be applied to most production servers without breaking standard functionality. This is the minimum for a server handling sensitive data. |
| Level 2 | Stricter controls that may impact usability or require significant operational adaptation. Appropriate for servers handling regulated data (PHI, PCI, classified information). |

Each control in the benchmark includes a rationale, an audit procedure (how to verify the current state), and a remediation procedure (how to fix it). The controls map directly to the topics in this module:

- **CIS 1.x** — Filesystem configuration (mount options, SUID, world-writable files)
- **CIS 4.x** — Logging and auditing (`auditd` rules, log file permissions)
- **CIS 5.x** — Access, authentication, and authorization (SSH, sudo, PAM)
- **CIS 6.x** — System maintenance (file permissions, unowned files)

For an AI server not subject to formal compliance audits, treat CIS Level 1 as a floor rather than a ceiling. The controls in this module exceed CIS Level 1 in several areas (network namespaces, AppArmor profiles for custom services) because the threat model — a process that executes arbitrary user-supplied text — is more specific than the benchmark assumes.

The full PDF benchmarks are available free of charge at `https://www.cisecurity.org/cis-benchmarks` after free registration. The `cis-cat-lite` tool can run automated CIS assessment against a running system.

### Incident Response Basics

Incident response (IR) for an internal AI server is not about fighting nation-state actors; it is about detecting anomalies early, containing their impact, and restoring service from a known-good state. The following checklist covers the most likely scenarios: a compromised service account, an exfiltrated `.env` file, and an unauthorized model weight access.

**Immediate containment (first 15 minutes):**

1. Do not reboot the server — volatile memory contains evidence. If the intrusion is ongoing, isolate the host at the network layer first:
   ```bash
   # Block all inbound connections except your admin SSH session
   sudo iptables -I INPUT 1 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
   sudo iptables -I INPUT 2 -s YOUR_ADMIN_IP/32 -p tcp --dport 2222 -j ACCEPT
   sudo iptables -A INPUT -j DROP
   ```

2. Preserve current state before any remediation:
   ```bash
   # Capture running processes, network connections, logged-in users
   ps auxf > /tmp/ir-processes.txt
   ss -tulnp > /tmp/ir-network.txt
   who > /tmp/ir-who.txt
   last -20 > /tmp/ir-last.txt
   sudo ausearch --start today > /tmp/ir-audit.txt
   ```

3. Check for unexpected accounts and recently modified files:
   ```bash
   # Accounts with UID 0 (other than root)
   awk -F: '($3 == 0) { print $1 }' /etc/passwd

   # Files modified in the last 24 hours under sensitive directories
   sudo find /etc /opt /usr/local/bin -mtime -1 -type f 2>/dev/null
   ```

**Rotation of all secrets (within the hour):**
Any incident that involves a potentially compromised process, file system access, or account must trigger immediate rotation of all credentials in `/etc/ai-service/.env`. Treat all secrets as compromised until proven otherwise. Rotate API keys, database passwords, and signing secrets from a separate, unaffected machine.

**Post-incident:**
- Preserve audit logs off-host (`auditd` + a remote syslog destination, configured via `audisp-remote`)
- File an internal incident report documenting timeline, blast radius, and lessons learned
- Run Lynis again to verify the hardening state has not degraded
- Update your threat model: which control prevented escalation, and which control was bypassed?

## Best Practices

1. **Apply the principle of least privilege to every account, every service, and every process.** Granting broad permissions "just in case" is how a compromised AI service becomes a full server compromise. Every `ALL` in a sudoers file, every world-readable secrets file, and every unnecessary SUID binary is a potential pivot point.

2. **Always validate `sshd_config` syntax with `sudo sshd -t` before reloading the SSH daemon.** A syntax error in a drop-in file will prevent the daemon from reloading and, on some configurations, may lock you out on the next restart — even if your current session stays alive.

3. **Put AppArmor profiles in `complain` mode during staging, then convert to `enforce` in production.** Running immediately in enforce mode without profiling real workloads causes legitimate inference requests to be denied without warning; complain mode gives you a week of real-traffic data to build an accurate profile.

4. **Never store secrets in environment variables that are set at shell login.** `EnvironmentFile=` in a systemd unit, with the file owned by the service account and mode `600`, keeps secrets out of `/proc/<pid>/environ` for unprivileged users and out of `ps` output.

5. **Record a SUID baseline immediately after initial hardening and diff against it weekly.** Package installations, especially Python packages that install helper binaries, can introduce new SUID files without any explicit administrator action.

6. **Set `Automatic-Reboot "false"` in `unattended-upgrades` and monitor for `/var/run/reboot-required`.** Uncontrolled reboots interrupt multi-hour inference jobs and can surprise on-call engineers; planned maintenance windows preserve service SLAs while still applying kernel security patches promptly.

7. **Use `auditd` rule immutability (`-e 2`) in production.** An attacker with root access cannot silently disable audit logging at runtime; the only way to change rules is to reboot, which is itself logged by the kernel and by your monitoring infrastructure.

8. **Rotate all secrets on every security incident, even if the scope appears limited.** The cost of rotation is measured in minutes; the cost of a missed credential rotation is measured in days of breach exposure plus notification obligations if PII was accessed.

9. **Run Lynis before and after major configuration changes, not just during initial hardening.** Package upgrades, new service deployments, and configuration drift can silently reduce your hardening score; scheduled monthly Lynis runs catch regressions before they are exploited.

10. **Keep AppArmor, `auditd`, and SSH configurations in version control.** Treating your hardening configuration as code means changes are reviewed, reversible, and auditable — the same discipline applied to application code.

## Use Cases

### Protecting Proprietary Model Weights from Exfiltration

A company fine-tunes a proprietary LLM on internal business data. The weights represent months of compute budget and contain learned patterns of sensitive business information. The weights are stored under `/opt/ai-models/` on the inference server.

The relevant controls from this module are: AppArmor profile restricting the inference process to read-only access of `/opt/ai-models/` and no write access to network sockets outside the inference port; `auditd` rules on `/opt/ai-models/` logging every read access with the accessing process's UID, PID, and executable path; file ownership set to `ai-service:ai-service` with mode `750` so that no other user can even list the directory contents.

Expected outcome: any exfiltration attempt — whether by a compromised service process, a curious employee with a shell session, or a supply-chain attack in a Python dependency — produces an audit trail that triggers an alert within minutes, and the AppArmor profile prevents the compromised process from opening an outbound connection to exfiltrate data.

### Containing a Compromised Inference Process

A researcher discovers that a particular prompt causes the inference server to call `subprocess.run()` and execute shell commands (a prompt injection vulnerability in the application layer). Without hardening, this means the attacker has a shell running as `ai-service`.

With the controls from this module applied: the AppArmor profile denies `exec` of shell binaries (`/bin/sh`, `/bin/bash`); the network namespace means the shell cannot reach the database or other internal services; the `ai-service` account has no sudo rights; and the `auditd` rules capture the `execve` syscalls, alerting the ops team within seconds.

Expected outcome: the prompt injection achieves code execution but cannot escalate, pivot, or exfiltrate data. The `auditd` alert fires and the ops team isolates the server before any data leaves.

### Meeting an Internal Security Audit

The company's internal security team runs a quarterly audit of infrastructure handling PII. They use the CIS Ubuntu 22.04 Benchmark Level 1 as their baseline and run `cis-cat-lite` against the server. Before this module's controls are applied, the server scores 48% compliance. After applying SSH hardening, sudo restrictions, `auditd` rules, file permission fixes, and SUID cleanup, the same assessment scores 82%.

The relevant controls are: all of them, but specifically the SSH, sudo, auditd, world-writable file, and SUID sections map directly to CIS sections 5.x, 4.x, and 1.x respectively.

Expected outcome: a documented, reproducible hardening configuration that satisfies the audit requirements, with each CIS control traceable to a specific configuration file under version control.

### Segmenting an AI API from Internal Databases

An AI inference server needs to call an embedding database (pgvector) for RAG lookups, but should not be able to reach the HR database, the finance system, or other internal services that happen to be on the same VLAN. A network namespace with explicit `iptables` rules on the host implements this segmentation without requiring VLAN changes or a separate physical network.

The relevant controls are the network namespace section, combined with `auditd` socket monitoring rules to detect if the inference process attempts connections to unauthorized destinations.

Expected outcome: the inference service can reach only the embedding database and the inference port; any attempt to connect elsewhere is blocked at the `FORWARD` chain and logged by `auditd`.

## Hands-on Examples

### Example 1: Hardening SSH on a Fresh Server

You have just provisioned a Ubuntu 22.04 LTS VM and need to lock down SSH before placing the server on the internal network. You already have a key-based SSH session open as a non-root user with sudo access.

1. Confirm your public key is present and SSH is functional before making any changes:
   ```bash
   cat ~/.ssh/authorized_keys
   # Should show your public key — do not proceed if this is empty
   ```

2. Create the drop-in directory if it does not exist:
   ```bash
   sudo mkdir -p /etc/ssh/sshd_config.d
   ```

3. Write the hardening drop-in file:
   ```bash
   sudo tee /etc/ssh/sshd_config.d/99-hardening.conf > /dev/null << 'EOF'
   Port 2222
   PermitRootLogin no
   PasswordAuthentication no
   KbdInteractiveAuthentication no
   PermitEmptyPasswords no
   AllowUsers YOUR_USERNAME
   MaxAuthTries 3
   LoginGraceTime 30
   ClientAliveInterval 300
   ClientAliveCountMax 2
   X11Forwarding no
   AllowAgentForwarding no
   AllowTcpForwarding no
   EOF
   ```
   Replace `YOUR_USERNAME` with your actual non-root username.

4. Validate syntax:
   ```bash
   sudo sshd -t
   # No output means success. Any error output means do NOT proceed — fix it first.
   ```

5. Reload the daemon (not restart — reload keeps existing sessions alive):
   ```bash
   sudo systemctl reload ssh
   ```

6. **Without closing your current session**, open a second terminal and test that the new configuration works:
   ```bash
   ssh -p 2222 YOUR_USERNAME@YOUR_SERVER_IP
   # Expected: successful login with your key
   ```

7. Confirm that root login is rejected:
   ```bash
   ssh -p 2222 root@YOUR_SERVER_IP
   # Expected: "Permission denied (publickey)" — root has no authorized key,
   # and even if it did, PermitRootLogin no blocks it
   ```

Expected result: you are logged in on port 2222, root login is blocked, and password authentication is unavailable.

---

### Example 2: Writing and Testing a Sudoers Allowlist

You are creating a `deploy-bot` service account used by your CI/CD pipeline to reload the AI inference service after a new model is deployed. The account should be able to run exactly one command as root with no password prompt: `systemctl reload ai-inference`.

1. Create the service account (no login shell, no home directory needed):
   ```bash
   sudo useradd --system --no-create-home --shell /usr/sbin/nologin deploy-bot
   ```

2. Write the sudoers drop-in file using `visudo` with an explicit filename:
   ```bash
   sudo visudo -f /etc/sudoers.d/20-deploy-bot
   ```
   Enter the following content in the editor:
   ```
   # deploy-bot: CI/CD pipeline account
   # May only reload the AI inference service; no password required
   deploy-bot ALL=(root) NOPASSWD: /usr/bin/systemctl reload ai-inference
   ```
   Save and exit. `visudo` validates syntax on exit and refuses to save a malformed file.

3. Verify the file permissions (sudo refuses to read sudoers files with wrong permissions):
   ```bash
   ls -l /etc/sudoers.d/20-deploy-bot
   # Expected: -r--r----- 1 root root ... /etc/sudoers.d/20-deploy-bot
   # (visudo sets 0440 automatically)
   ```

4. Test the permission as the deploy-bot user:
   ```bash
   sudo -u deploy-bot sudo /usr/bin/systemctl reload ai-inference
   # Expected: command runs without a password prompt
   ```

5. Confirm that any other command is refused:
   ```bash
   sudo -u deploy-bot sudo /usr/bin/systemctl restart ai-inference
   # Expected: "Sorry, user deploy-bot is not allowed to execute
   # '/usr/bin/systemctl restart ai-inference' as root on ..."
   ```

Expected result: `deploy-bot` can reload (but not restart, stop, or start) the inference service without a password, and any other elevated command is denied.

---

### Example 3: Installing auditd and Writing Rules for an AI Server

You want to ensure that any access to your model weights directory and any change to sudo configuration is logged with a named key that your SIEM or log-shipping agent can filter on.

1. Install `auditd`:
   ```bash
   sudo apt install auditd audispd-plugins
   sudo systemctl enable --now auditd
   ```

2. Confirm it is running:
   ```bash
   sudo systemctl status auditd
   # Expected: active (running)
   auditctl -l
   # Expected: lists current rules (may be empty on a fresh install)
   ```

3. Write a rules file:
   ```bash
   sudo tee /etc/audit/rules.d/50-ai-server.rules > /dev/null << 'EOF'
   # Sudoers changes
   -w /etc/sudoers -p wa -k sudoers_changes
   -w /etc/sudoers.d/ -p wa -k sudoers_changes

   # SSH config changes
   -w /etc/ssh/sshd_config -p wa -k sshd_config
   -w /etc/ssh/sshd_config.d/ -p wa -k sshd_config

   # Model weight access (adjust path to match your deployment)
   -w /opt/ai-models/ -p rwa -k model_access

   # AI service config and secrets
   -w /etc/ai-service/ -p rwa -k ai_service_config

   # Privilege escalation (64-bit)
   -a always,exit -F arch=b64 -S execve -F euid=0 -k root_commands

   # Immutable rule set
   -e 2
   EOF
   ```

4. Reload the rules:
   ```bash
   sudo augenrules --load
   # Expected: ends with "Success"
   sudo auditctl -l | tail -5
   # Expected: shows your new rules, last line shows "-e 2"
   ```

5. Trigger a test event:
   ```bash
   sudo touch /etc/sudoers.d/test-trigger
   sudo rm /etc/sudoers.d/test-trigger
   ```

6. Query for the event:
   ```bash
   sudo ausearch -k sudoers_changes --interpret
   # Expected: one or more records showing the touch and rm operations,
   # with the calling user's name, UID, and process name
   ```

Expected result: `ausearch` returns records identifying who touched the sudoers directory, from which terminal, at what timestamp.

---

### Example 4: Running Lynis and Interpreting the Report

You have applied the SSH, sudo, and auditd changes from this module and want to measure your current hardening posture and identify the highest-priority remaining gaps.

1. Install Lynis:
   ```bash
   sudo apt install lynis
   lynis show version
   # Expected output: lynis 3.x.x (verify this is current at https://cisofy.com/lynis/)
   ```

2. Run a full audit and capture the output:
   ```bash
   sudo lynis audit system 2>&1 | tee /var/log/lynis-$(date +%Y%m%d).log
   # This takes 2–5 minutes on a typical server
   ```

3. Find the hardening index:
   ```bash
   grep "Hardening index" /var/log/lynis-$(date +%Y%m%d).log
   # Expected: Hardening index : 72 [##############      ]
   # (Your actual score depends on what is already configured)
   ```

4. Show all warnings (items requiring immediate attention):
   ```bash
   grep "\[WARNING\]" /var/log/lynis-$(date +%Y%m%d).log
   ```

5. Show all suggestions (improvements that reduce attack surface):
   ```bash
   grep "\[suggestion\]" /var/log/lynis-$(date +%Y%m%d).log -i
   ```

6. Pick one Warning or Suggestion and apply the fix. For example, if Lynis warns that core dumps are enabled:
   ```bash
   # Lynis warning: KRNL-5820 - Harden kernel - suggestion to disable core dumps
   # Fix: add to /etc/security/limits.conf
   echo "* hard core 0" | sudo tee -a /etc/security/limits.conf

   # And in /etc/sysctl.d/
   echo "fs.suid_dumpable = 0" | sudo tee /etc/sysctl.d/99-no-core-dumps.conf
   sudo sysctl --system
   ```

7. Re-run Lynis and confirm the score improved:
   ```bash
   sudo lynis audit system 2>&1 | grep "Hardening index"
   # Expected: score increased by 1–3 points per fixed item
   ```

Expected result: a hardening index score, a prioritized list of remaining gaps, and at least one gap remediated with a measurable score improvement.

## Common Pitfalls

### Pitfall 1: Locking Yourself Out of SSH

**What happens:** You disable password authentication or change the SSH port without first verifying that key-based login works on the new port.

**Why it happens:** The change is made in one terminal session; the operator assumes it will work and closes the session without testing from a second window.

**Incorrect pattern:**
```bash
# Changes the port, immediately restarts the daemon, closes terminal
sudo sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config
sudo systemctl restart ssh
exit
# Now you cannot SSH in — your firewall still only allows port 22
```

**Correct pattern:**
```bash
# 1. Make the change in a drop-in file
# 2. Run sudo sshd -t to validate syntax
# 3. Run sudo systemctl reload ssh (keeps your existing session alive)
# 4. Open a SECOND terminal and confirm login works on the new port
# 5. Update your firewall rules to allow the new port
# 6. Only then close the original session
```

---

### Pitfall 2: Sudoers File Syntax Error Locking Out All Sudo Access

**What happens:** A typo in `/etc/sudoers` or a file in `/etc/sudoers.d/` causes `sudo` to refuse to run anything, including `sudo visudo` to fix the error.

**Why it happens:** Editing `/etc/sudoers` directly with a text editor instead of `visudo`. `visudo` validates syntax before saving and refuses to write a broken file.

**Incorrect pattern:**
```bash
sudo nano /etc/sudoers
# Makes a typo: "alice ALL=(ALL:ALL ALL" (missing closing parenthesis)
# Saves. Now sudo is broken for everyone.
```

**Correct pattern:**
```bash
sudo visudo
# visudo catches the syntax error and shows: ">>> sudoers file: syntax error, line 28 <<<"
# Does not save; returns you to the editor to fix it.

# For drop-in files:
sudo visudo -f /etc/sudoers.d/10-ai-ops
```

---

### Pitfall 3: AppArmor Profile Breaks Inference at 2 AM

**What happens:** An AppArmor profile written in `enforce` mode blocks a file access pattern that only occurs during model loading or a specific inference path, causing the service to crash silently at runtime.

**Why it happens:** The profile was written based on one test run that did not exercise all code paths. Model loading, logging initialization, and tokenizer cache creation often access paths not covered by a basic smoke test.

**Incorrect pattern:**
```bash
# Write a profile based on one test run, immediately enforce it in production
sudo aa-enforce /etc/apparmor.d/usr.local.bin.ai-inference-server
sudo systemctl restart ai-inference
# Works fine in testing; crashes at 2 AM when a new model variant is loaded
```

**Correct pattern:**
```bash
# Step 1: Deploy in complain mode
sudo aa-complain /etc/apparmor.d/usr.local.bin.ai-inference-server
# Step 2: Run the service for at least 24–48 hours under realistic load
# Step 3: Review complain-mode denials
sudo journalctl | grep "apparmor" | grep "ALLOWED"
# Step 4: Add missing paths to the profile
# Step 5: Only then switch to enforce mode
sudo aa-enforce /etc/apparmor.d/usr.local.bin.ai-inference-server
```

---

### Pitfall 4: `.env` File Readable by Other Users

**What happens:** A secrets file is created with default permissions (`644`) or by a user with a permissive `umask`, making it world-readable.

**Why it happens:** Using `echo` or a text editor to create the file, which inherits the user's `umask` (commonly `022`, producing `644` files).

**Incorrect pattern:**
```bash
echo "OPENAI_API_KEY=sk-..." > /etc/ai-service/.env
# File mode is 644 — any user on the system can read the API key
ls -l /etc/ai-service/.env
# -rw-r--r-- 1 root root 30 ... .env
```

**Correct pattern:**
```bash
# Create with correct permissions atomically
sudo install -o ai-service -g ai-service -m 600 /dev/null /etc/ai-service/.env
sudo -u ai-service tee /etc/ai-service/.env > /dev/null << 'EOF'
OPENAI_API_KEY=sk-...
EOF
# Verify
stat /etc/ai-service/.env | grep Access
# Access: (0600/-rw-------)  Uid: (ai-service)
```

---

### Pitfall 5: `AllowUsers` Blocking a Needed Deployment Account

**What happens:** `AllowUsers` is set to only the names of human operators. The CI/CD deployment pipeline's SSH key — used by a service account — stops working, causing deployment failures.

**Why it happens:** `AllowUsers` affects all SSH logins, including those used by automation. Operators list human accounts and forget about non-interactive service accounts.

**Incorrect pattern:**
```
AllowUsers alice bob
# deploy-bot and github-actions cannot SSH in anymore
```

**Correct pattern:**
```
AllowUsers alice bob deploy-bot
# All accounts that legitimately need SSH access are explicitly listed
# Document each entry: why it exists, what key it uses, when it was added
```

---

### Pitfall 6: `unattended-upgrades` Restarting the Inference Service Mid-Job

**What happens:** `unattended-upgrades` installs a libssl update and automatically restarts dependent services, including the inference server, killing a running inference job.

**Why it happens:** Some packages register post-install hooks (via `needrestart`) that restart services using updated libraries. `unattended-upgrades` with `Automatic-Reboot "false"` does not prevent service restarts triggered by `needrestart`.

**Incorrect pattern:**
```
# Only setting Automatic-Reboot to false, not configuring needrestart
Unattended-Upgrade::Automatic-Reboot "false";
# needrestart still restarts ai-inference when libssl is updated
```

**Correct pattern:**
```bash
# Configure needrestart to list services needing restart but not auto-restart them
sudo sed -i 's/#$nrconf{restart} = .*/\$nrconf{restart} = '\''l'\'';/' \
    /etc/needrestart/needrestart.conf
# 'l' means "list only" — operators see what needs a restart at next login
# Apply restarts during the next scheduled maintenance window
```

---

### Pitfall 7: auditd `-e 2` Set Before Testing Rules

**What happens:** The audit rules file has `-e 2` (immutable mode) at the end and also contains a syntax error in a preceding rule. The rules load partially, and because of `-e 2`, you cannot fix them without rebooting.

**Why it happens:** `-e 2` is added as a security measure but is applied before validating that all rules load correctly.

**Correct pattern:**
```bash
# Test rules without -e 2 first
sudo auditctl -R /etc/audit/rules.d/50-ai-server.rules
sudo auditctl -l   # verify all rules are present
# Only after confirming rules load correctly, add -e 2 to the file
# and reload with augenrules --load
```

## Summary

- SSH hardening eliminates the most common remote attack vectors by disabling root login, enforcing key-only authentication, restricting login to named accounts with `AllowUsers`, and reducing the brute-force window with `MaxAuthTries` and `LoginGraceTime`.
- Sudoers allowlists implement least-privilege privilege escalation by replacing broad `ALL` grants with explicit `Cmnd_Alias` blocks, reserving `NOPASSWD` only for non-interactive automation accounts.
- `auditd` provides tamper-evident kernel-level logging of file access, privilege escalation, and configuration changes; immutable rules (`-e 2`) prevent an attacker with root access from silently disabling the audit trail.
- AppArmor profiles confine service processes to precisely the filesystem and network access they need, limiting the blast radius of a compromised inference process to what the profile permits.
- Secrets management, world-writable file elimination, SUID binary auditing, network namespace isolation, `unattended-upgrades` configuration, and regular Lynis scans together form a defense-in-depth posture aligned with CIS Benchmark Level 1 and appropriate for a server handling PII and proprietary model weights.

## Further Reading

- [OpenSSH Manual Pages — sshd_config(5)](https://man.openbsd.org/sshd_config) — The authoritative reference for every `sshd_config` directive, including accepted values, defaults, and version notes; cross-check any directive in this module against the version of OpenSSH installed on your server with `ssh -V`.
- [CIS Benchmarks — Ubuntu Linux](https://www.cisecurity.org/cis-benchmarks) — Free-to-download PDF guides covering every hardening control for Ubuntu 20.04, 22.04, and 24.04 LTS at Level 1 and Level 2; each control includes a rationale, audit procedure, and remediation step that maps directly to the configurations shown in this module.
- [Lynis Documentation and Hardening Guide](https://cisofy.com/documentation/lynis/) — Official documentation for Lynis covering installation, scan profiles, custom tests, CI integration, and interpretation of the hardening index; essential for turning Lynis output into a remediation backlog.
- [AppArmor Wiki — Ubuntu Community Help](https://help.ubuntu.com/community/AppArmor) — Ubuntu-specific AppArmor documentation covering profile syntax, the `aa-genprof`/`aa-logprof` workflow, abstractions, and how to debug denials using `dmesg` and `journalctl`; includes worked examples for common service types.
- [Linux Audit Documentation — audit.rules(7)](https://man7.org/linux/man-pages/man7/audit.rules.7.html) — The Linux man page for audit rule syntax, covering all rule types (`-w` filesystem watches, `-a` syscall rules), filter fields, and the `-e` flag; the canonical reference when writing custom `auditd` rules beyond the examples in this module.
- [The Linux Command Line — William Shotts (Chapter on Permissions)](https://linuxcommand.org/tlcl.php) — A freely available book that provides deep grounding in Unix permission bits, SUID/SGID semantics, `umask`, and file ownership; essential background for anyone who finds the permissions sections of this module moving too quickly.
- [Ubuntu Security Team — unattended-upgrades](https://help.ubuntu.com/community/AutomaticSecurityUpdates) — Ubuntu's official guide to configuring `unattended-upgrades`, covering origin patterns, email notifications, bandwidth throttling, and integration with `needrestart`; the reference for production-grade automatic update configuration.
- [NIST SP 800-123 — Guide to General Server Security](https://csrc.nist.gov/publications/detail/sp/800-123/final) — A foundational NIST publication covering the full lifecycle of server hardening, from initial installation through ongoing maintenance; provides the policy rationale behind many of the technical controls in this module and is useful when justifying security decisions to non-technical stakeholders.
