# Module 3: Server Provisioning
> Subject: Ansible | Difficulty: Intermediate | Estimated Time: 210 minutes

## Objective

After completing this module, you will be able to write and run a single Ansible playbook that transforms a fresh Ubuntu 22.04 server into a baseline-ready AI workload host. Specifically, you will use the `apt` module to update packages and install a curated tool set, the `hostname` and `timezone` modules to configure system identity, the `user` and `authorized_key` modules to create hardened service accounts with SSH key authentication, the `lineinfile` and `blockinfile` modules to make precise edits to configuration files, the `mount` module to register additional storage in `/etc/fstab`, the `sysctl` module to tune kernel parameters for ML data pipelines (`vm.swappiness`, socket buffer sizes), and `chrony`/`systemd-timesyncd` for NTP synchronization. You will apply idempotency discipline throughout so the playbook is safe to re-run at any time without side effects.

## Prerequisites

- Completed **Module 1: Ansible Fundamentals** — you must be comfortable with inventory files, ad-hoc commands, playbook structure (`hosts`, `tasks`, `vars`), and running `ansible-playbook`
- Completed **Module 2: Roles and Variables** — you must understand variable precedence, `group_vars`/`host_vars`, Jinja2 templating, and the `ansible.cfg` configuration file
- Ansible 2.16 or later installed on the control node (`ansible --version`; current stable release is Ansible 2.17.x)
- A reachable Ubuntu 22.04 LTS target host (physical server, VM, or cloud instance) with Python 3 installed and a user that has `sudo` privileges
- SSH key-based access from your control node to the target host already established for the initial bootstrap user
- Basic familiarity with Linux system administration concepts: filesystem mounts, kernel parameters via `sysctl`, and SSH `authorized_keys`

## Key Concepts

### Idempotency — The Foundation of Safe Provisioning

Idempotency is the property that running a task once produces exactly the same end state as running it ten times. In Ansible, most built-in modules are idempotent by design: the `apt` module checks whether a package is already at the requested version before attempting installation, the `user` module checks whether the account exists and has the correct attributes before modifying anything, and the `mount` module checks `/etc/fstab` before adding an entry.

Idempotency matters in server provisioning because real-world playbooks are re-run frequently: after a failed first run, when you add a new task to an existing playbook, during a periodic compliance check, or when onboarding a new server into an existing cluster. A non-idempotent playbook that, for example, always appends a line to a config file without checking first, will corrupt configuration on the second run and break the server.

The Ansible `changed_when` and `failed_when` directives let you override the default change/failure detection logic for tasks that use the `command` or `shell` modules — the two modules that are not idempotent by default. Avoiding `command` and `shell` in favor of dedicated modules is the single highest-impact idempotency practice.

```yaml
# Non-idempotent — appends on every run
- name: Add sysctl line (WRONG)
  shell: echo "vm.swappiness=10" >> /etc/sysctl.conf

# Idempotent — checks before acting
- name: Set vm.swappiness (CORRECT)
  ansible.builtin.sysctl:
    name: vm.swappiness
    value: "10"
    state: present
    reload: true
```

The `state` parameter is the idempotency contract in most modules: `present` means "ensure this thing exists with these attributes," and `absent` means "ensure this thing does not exist." These are declarations about desired end state, not imperative commands.

### System Identity — Hostname, Timezone, and Locale

The first configuration a provisioning playbook should apply is system identity: the hostname, timezone, and locale. These settings affect log timestamps (critical for correlating events across a cluster), locale-sensitive package behavior, and how the server presents itself in DNS and monitoring systems.

The `ansible.builtin.hostname` module sets `/etc/hostname` and calls `hostnamectl` atomically. The `community.general.timezone` module sets the system timezone using `timedatectl` and restarts any affected services. For locale configuration on Ubuntu 22.04, the `command` module calling `locale-gen` is acceptable when guarded with `changed_when`, though a `lineinfile` approach targeting `/etc/locale.gen` is cleaner for repeated runs.

```yaml
- name: Set system hostname
  ansible.builtin.hostname:
    name: "{{ server_hostname }}"

- name: Set system timezone
  community.general.timezone:
    name: "{{ server_timezone | default('UTC') }}"

- name: Ensure locale is generated
  ansible.builtin.command:
    cmd: locale-gen en_US.UTF-8
  changed_when: false   # locale-gen is idempotent but has no meaningful return code change
```

Maintaining `/etc/hosts` across a cluster is a related concern. When you manage a set of servers that communicate with each other by hostname (common in distributed AI training workloads), you need every host to resolve every other host's name. The `blockinfile` module is the correct tool: it inserts a clearly delimited block that it can identify and update on subsequent runs.

```yaml
- name: Populate /etc/hosts with cluster members
  ansible.builtin.blockinfile:
    path: /etc/hosts
    marker: "# {mark} ANSIBLE MANAGED CLUSTER HOSTS"
    block: |
      {% for host in groups['ai_cluster'] %}
      {{ hostvars[host]['ansible_host'] }}  {{ host }}
      {% endfor %}
```

### User and SSH Key Management

AI workload servers typically require two categories of accounts: a named human operator account with `sudo` access, and one or more service accounts (e.g., `aiuser`, `mlops`) that own the workload processes and should not have interactive login or unnecessary privileges.

The `ansible.builtin.user` module manages local Unix accounts. Critical parameters for a hardened server include `shell` (set `/usr/sbin/nologin` for service accounts), `create_home` (set `false` for accounts that do not need home directories), `groups` (add operator accounts to `sudo`), and `password` (always supply a hashed value using Ansible Vault — never a plaintext string).

```yaml
- name: Create AI operator account
  ansible.builtin.user:
    name: "{{ operator_username }}"
    comment: "AI Workload Operator"
    groups: sudo
    append: true
    shell: /bin/bash
    create_home: true
    state: present

- name: Create AI service account
  ansible.builtin.user:
    name: aiuser
    comment: "AI Workload Service Account"
    shell: /usr/sbin/nologin
    create_home: false
    system: true
    state: present
```

The `ansible.posix.authorized_key` module manages entries in `~/.ssh/authorized_keys`. It reads the public key from a file on the control node (using the `lookup` plugin), inserts or removes it from the target user's authorized keys file, and sets correct file permissions. The `exclusive: true` parameter removes all keys not explicitly listed — use this carefully, only when you want Ansible to be the sole source of truth for who can log in.

```yaml
- name: Deploy operator SSH public key
  ansible.posix.authorized_key:
    user: "{{ operator_username }}"
    key: "{{ lookup('file', 'files/operator_id_ed25519.pub') }}"
    state: present
    exclusive: false   # do not remove keys added by other means

- name: Lock root SSH login
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#?PermitRootLogin'
    line: 'PermitRootLogin no'
    state: present
    validate: '/usr/sbin/sshd -t -f %s'
  notify: Restart sshd
```

### The lineinfile and blockinfile Modules

These two modules are the workhorses of configuration file editing when a template (`ansible.builtin.template`) is either impractical (the file is managed by another process and partially owned elsewhere) or overkill (you need to change one line in a large config).

`lineinfile` operates on a single line. It uses a `regexp` to find an existing line to replace, and `line` to specify what the line should contain after the task runs. If `regexp` matches nothing, the `line` is inserted (by default at the end of the file). The `insertafter` and `insertbefore` parameters control placement when inserting a new line.

```yaml
# Ensure PasswordAuthentication is explicitly disabled
- name: Disable SSH password authentication
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#?PasswordAuthentication'
    line: 'PasswordAuthentication no'
    state: present
    validate: '/usr/sbin/sshd -t -f %s'
  notify: Restart sshd

# Set the system-wide EDITOR preference
- name: Set default editor in environment
  ansible.builtin.lineinfile:
    path: /etc/environment
    regexp: '^EDITOR='
    line: 'EDITOR=vim'
    state: present
```

`blockinfile` inserts or replaces a multi-line block delimited by configurable marker comments. The markers are what make it idempotent: on subsequent runs, Ansible finds the existing markers and replaces the content between them, rather than appending a duplicate block. Always set a unique `marker` when you have more than one `blockinfile` task targeting the same file.

```yaml
- name: Configure limits for AI workload user
  ansible.builtin.blockinfile:
    path: /etc/security/limits.conf
    marker: "# {mark} ANSIBLE MANAGED - aiuser limits"
    block: |
      aiuser soft nofile 65536
      aiuser hard nofile 65536
      aiuser soft nproc  32768
      aiuser hard nproc  32768
```

The `{mark}` placeholder is expanded to `BEGIN` and `END` by Ansible, producing readable human-visible delimiters. The resulting file section looks like:

```
# BEGIN ANSIBLE MANAGED - aiuser limits
aiuser soft nofile 65536
aiuser hard nofile 65536
aiuser soft nproc  32768
aiuser hard nproc  32768
# END ANSIBLE MANAGED - aiuser limits
```

### The mount Module and Storage Provisioning

AI workloads — especially training runs — require significant storage: datasets, model checkpoints, logs, and scratch space. In a provisioned server, additional block devices (NVMe SSDs, attached volumes) must be formatted and mounted before any workload can use them. The `ansible.builtin.mount` module manages `/etc/fstab` entries and can also invoke `mount`/`umount` immediately.

The `state` parameter controls behavior:

| State | Effect |
|---|---|
| `mounted` | Adds the entry to `/etc/fstab` **and** mounts it immediately if not already mounted |
| `present` | Adds the entry to `/etc/fstab` but does **not** mount it (survives reboot only) |
| `unmounted` | Unmounts the filesystem but leaves the `/etc/fstab` entry intact |
| `absent` | Unmounts and removes the `/etc/fstab` entry |

Before mounting, you must ensure the filesystem exists. The `community.general.filesystem` module handles formatting in an idempotent way — it will not reformat a device that already has a filesystem of the correct type.

```yaml
- name: Ensure XFS filesystem on data volume
  community.general.filesystem:
    fstype: xfs
    dev: /dev/nvme1n1
    force: false   # never reformat if filesystem already exists

- name: Create mount point for AI data volume
  ansible.builtin.file:
    path: /mnt/aidata
    state: directory
    owner: aiuser
    group: aiuser
    mode: "0755"

- name: Mount AI data volume persistently
  ansible.builtin.mount:
    path: /mnt/aidata
    src: /dev/nvme1n1
    fstype: xfs
    opts: defaults,noatime,nodiratime
    state: mounted
```

The `noatime` and `nodiratime` mount options disable access-time updates — a meaningful throughput improvement for sequential read-heavy workloads like loading training datasets because they eliminate unnecessary metadata writes on every file read.

For cloud environments where device names are unstable across reboots, use the device's UUID or filesystem label instead of the block device path:

```yaml
- name: Mount by UUID (stable across reboots)
  ansible.builtin.mount:
    path: /mnt/aidata
    src: "UUID={{ data_volume_uuid }}"
    fstype: xfs
    opts: defaults,noatime,nodiratime
    state: mounted
```

### Swap Configuration

Swap is a nuanced topic for AI workloads. Model inference with large models (LLaMA 70B, for example) can benefit from swap when activations spill beyond GPU memory — but runaway swap usage on training nodes causes catastrophic slowdowns. The correct approach is: create a measured swap space, but tune `vm.swappiness` very low so the kernel only uses swap as a last resort.

The standard method on Ubuntu 22.04 is a swap file rather than a dedicated partition, because it is resizable without repartitioning. Ansible does not have a dedicated swapfile module, so this requires a sequence of tasks with careful idempotency guards.

```yaml
- name: Check if swap file already exists
  ansible.builtin.stat:
    path: /swapfile
  register: swapfile_stat

- name: Create swap file (4GB)
  ansible.builtin.command:
    cmd: fallocate -l 4G /swapfile
  when: not swapfile_stat.stat.exists

- name: Set swap file permissions
  ansible.builtin.file:
    path: /swapfile
    owner: root
    group: root
    mode: "0600"

- name: Format swap file
  ansible.builtin.command:
    cmd: mkswap /swapfile
  when: not swapfile_stat.stat.exists

- name: Enable swap file
  ansible.builtin.command:
    cmd: swapon /swapfile
  when: not swapfile_stat.stat.exists

- name: Register swap file in /etc/fstab
  ansible.builtin.mount:
    path: none
    src: /swapfile
    fstype: swap
    opts: sw
    state: present
```

### The sysctl Module — Kernel Tuning for ML Pipelines

The Linux kernel's default parameters are tuned for generic workloads. AI training and inference workloads have specific characteristics that benefit from targeted tuning: large sequential I/O for dataset loading, high-throughput inter-node communication for distributed training (NCCL over InfiniBand or RDMA over Converged Ethernet), and memory pressure management during model loading.

The `ansible.builtin.sysctl` module writes to `/etc/sysctl.d/` (by default) and optionally applies the change immediately via `sysctl --system`. It is fully idempotent: it checks the current kernel value before writing.

```yaml
- name: Apply AI workload kernel tuning
  ansible.builtin.sysctl:
    name: "{{ item.name }}"
    value: "{{ item.value }}"
    state: present
    reload: true
    sysctl_file: /etc/sysctl.d/90-ai-workload.conf
  loop:
    # Memory management
    - { name: vm.swappiness,              value: "5"        }
    - { name: vm.dirty_ratio,             value: "15"       }
    - { name: vm.dirty_background_ratio,  value: "5"        }
    - { name: vm.overcommit_memory,       value: "1"        }
    # Network — large socket buffers for NCCL / distributed training
    - { name: net.core.rmem_max,          value: "134217728" }
    - { name: net.core.wmem_max,          value: "134217728" }
    - { name: net.core.rmem_default,      value: "67108864"  }
    - { name: net.core.wmem_default,      value: "67108864"  }
    - { name: net.ipv4.tcp_rmem,          value: "4096 87380 134217728" }
    - { name: net.ipv4.tcp_wmem,          value: "4096 65536 134217728" }
    - { name: net.core.netdev_max_backlog, value: "250000"   }
    - { name: net.ipv4.tcp_mtu_probing,   value: "1"        }
    # Transparent Huge Pages helper (actual THP is set via a separate task)
    - { name: vm.nr_hugepages,            value: "0"        }
```

The parameters explained:

- `vm.swappiness=5` — The kernel defers memory swapping aggressively. A value of 10 or below is typical for AI hosts; 0 disables swap entirely (not recommended — OOM killer risk).
- `vm.overcommit_memory=1` — Always allow memory overcommit. PyTorch and JAX allocate more virtual memory than they intend to use immediately, and a conservative kernel will kill processes that never actually consume the reserved memory.
- `net.core.rmem_max / wmem_max = 134217728` (128 MiB) — Maximum socket receive/send buffer size. NCCL and other MPI-based communication libraries negotiate large buffers during initialization; without this ceiling, buffer negotiation falls back to the 212 KiB default.
- `net.ipv4.tcp_mtu_probing=1` — Enables Path MTU Discovery probing. Useful when traversing infrastructure with jumbo frames (9000 MTU) where the path MTU is unknown.

### NTP Configuration with chrony

Clock synchronization is non-negotiable on a server cluster. Distributed training frameworks use timestamps for coordination, log correlation across machines depends on synchronized clocks, and SSL certificate validation will fail if clocks drift too far. Ubuntu 22.04 ships with `systemd-timesyncd` enabled by default, but for production server fleets, `chrony` is preferred: it converges faster on startup, handles leap seconds better, and provides a richer monitoring interface (`chronyc tracking`).

```yaml
- name: Install chrony
  ansible.builtin.apt:
    name: chrony
    state: present
    update_cache: false   # cache was updated earlier in the play

- name: Disable systemd-timesyncd (conflicts with chrony)
  ansible.builtin.systemd:
    name: systemd-timesyncd
    state: stopped
    enabled: false

- name: Configure chrony NTP servers
  ansible.builtin.blockinfile:
    path: /etc/chrony/chrony.conf
    marker: "# {mark} ANSIBLE MANAGED NTP SERVERS"
    insertafter: "^# pool"
    block: |
      pool {{ ntp_pool | default('pool.ntp.org') }} iburst maxsources 4
      makestep 1.0 3
      rtcsync
  notify: Restart chrony

- name: Ensure chrony is started and enabled
  ansible.builtin.systemd:
    name: chronyd
    state: started
    enabled: true
```

## Best Practices

1. **Run `apt: update_cache: true` exactly once at the top of the play, then set `update_cache: false` for all subsequent `apt` tasks.** Calling `update_cache` on every package task sends a redundant HTTP request to the mirror on each run; a single refresh at play start is sufficient and noticeably faster on servers with many packages to install.

2. **Use `validate` on every `lineinfile` or `template` task that modifies a daemon configuration file.** The `validate` parameter runs the specified command (e.g., `sshd -t -f %s`, `nginx -t`) on the staged file before writing it. This prevents playbook runs from breaking a running service by deploying a syntax error into its configuration.

3. **Always use `notify` + handlers for service restarts, never `systemd: state: restarted` directly in a task.** A `notify` only triggers the handler once at the end of the play, even if five tasks all notify the same handler. Putting `state: restarted` directly in a task restarts the service every time the playbook runs, whether or not anything changed.

4. **Store secrets in Ansible Vault, never in plain-text variable files.** Passwords, private keys, and API tokens must be encrypted with `ansible-vault encrypt_string` or in a vault-encrypted variable file. A plaintext password in a `vars` file committed to source control is a permanent credential leak.

5. **Use `become: true` at the play level, not on individual tasks, for a provisioning playbook that is inherently root-level work.** Toggling `become` per task increases visual noise and makes it easy to accidentally leave a task without privilege escalation. If a specific task must run as a non-root user, override with `become: false` at the task level.

6. **Use `sysctl_file` to write kernel parameters to a dedicated file under `/etc/sysctl.d/` rather than editing `/etc/sysctl.conf`.** A named file like `/etc/sysctl.d/90-ai-workload.conf` makes the configuration's origin obvious, survives OS upgrades cleanly, and can be removed as a unit when decommissioning the tuning.

7. **Gate swap-creation tasks with `ansible.builtin.stat` checks rather than `creates:` on the `command` module.** Registering the `stat` result and using `when: not swapfile_stat.stat.exists` is more readable and composable than `creates:`, and it lets you reuse the registered variable in multiple dependent tasks (format, enable, register) without repeating the check.

8. **Pin base package versions in your package list variable when building reproducible AI infrastructure.** Using `state: latest` on packages like CUDA drivers or Python installs can silently break model compatibility across provisioning runs. Either pin to a version (`cuda-toolkit-12-3`) or accept that `state: latest` is a deliberate "always upgrade" policy.

9. **Set `ansible_python_interpreter: /usr/bin/python3` explicitly in your inventory or `group_vars`.** Ubuntu 22.04 does not have a `python` (Python 2) binary. Without this setting, older Ansible versions may auto-discover the wrong interpreter or emit deprecation warnings that clutter output.

10. **Validate the complete playbook with `ansible-playbook --check --diff` against a staging host before running against production.** Check mode simulates execution and `--diff` shows the exact line-level changes that `lineinfile`, `blockinfile`, and `template` tasks would make, giving a human-readable change preview.

## Use Cases

### AI Training Cluster Node Onboarding

**Problem:** A team managing a GPU cluster must bring a new bare-metal node into compliance with the cluster baseline — same users, same kernel parameters, same NFS mounts — within minutes of OS installation, without manual steps that introduce human error.

**Concepts applied:** `user` and `authorized_key` for uniform account creation, `sysctl` for NCCL-optimized network buffers, `mount` for shared NFS storage, `blockinfile` for adding the new node's IP to `/etc/hosts` on all other nodes via a separate play in the same playbook.

**Expected outcome:** The new node passes a compliance check playbook immediately after provisioning, all cluster members can resolve the new node's hostname, and NCCL benchmark throughput matches existing nodes from the first distributed test run.

### Cloud VM Hardening After Launch

**Problem:** A data engineering team launches Ubuntu 22.04 cloud VMs using an infrastructure-as-code tool (Terraform, Pulumi) but the VM images are vanilla OS installs. A follow-on Ansible playbook must harden each VM — disable root SSH, enforce key-only authentication, configure a firewall baseline — before it is handed off to application teams.

**Concepts applied:** `lineinfile` for `sshd_config` hardening, `authorized_key` with `exclusive: true` to remove the cloud provider's default key, `apt` for unattended-upgrades configuration, `sysctl` for network hardening parameters (`net.ipv4.conf.all.rp_filter=1`).

**Expected outcome:** The VM fails a scan for common SSH misconfigurations, has no root key authorized, and the only interactive user is the named operator account with a verified public key.

### Reproducible Development Environment Provisioning

**Problem:** A small ML research team of five needs each member's dedicated server to have identical Python versions, system libraries, user accounts, and mount points so that "works on my machine" debugging is eliminated when sharing experiment code.

**Concepts applied:** `apt` to pin Python 3.11 and build-essential libraries, `user` to create a shared `researcher` account, `mount` for a common NFS home directory mount, `blockinfile` to set environment variables in `/etc/environment`, and `timezone` to synchronize to a single reference timezone for log correlation.

**Expected outcome:** Any team member can run the same experiment script on any team server without environment-related failures, and experiment logs are timestamp-comparable without timezone offset arithmetic.

### Post-Incident Compliance Re-Attestation

**Problem:** After a security incident involving a compromised SSH key, the security team must rotate authorized keys on 40 servers simultaneously and verify that no unauthorized keys remain.

**Concepts applied:** `authorized_key` with `exclusive: true` to replace the entire `authorized_keys` file from a single canonical source in version control, a trailing `command` task using `wc -l` on the `authorized_keys` file to assert the expected key count, and `lineinfile` to force `sshd_config` audit settings if they were changed.

**Expected outcome:** All 40 servers have only the post-rotation key set within one playbook run, and the playbook's idempotency means re-running it the next day as a compliance check produces zero `changed` results.

## Hands-on Examples

### Example 1: Bootstrap a Fresh Ubuntu 22.04 Server End-to-End

This example walks through the complete "zero to AI-ready" playbook — all the pieces assembled in order. You need one fresh Ubuntu 22.04 server reachable by SSH, an inventory file pointing to it, and an ed25519 SSH public key in `files/operator_id_ed25519.pub` relative to the playbook directory.

**Step 1 — Create the directory structure:**

```bash
mkdir -p ai-baseline/{files,group_vars}
cd ai-baseline
ssh-keygen -t ed25519 -f files/operator_id_ed25519 -N "" -C "ansible-operator"
```

**Step 2 — Create the inventory file at `ai-baseline/inventory.ini`:**

```ini
[ai_servers]
ai-node-01 ansible_host=192.168.1.100 ansible_user=ubuntu

[ai_servers:vars]
ansible_python_interpreter=/usr/bin/python3
```

**Step 3 — Create variable defaults at `ai-baseline/group_vars/ai_servers.yml`:**

```yaml
server_hostname: ai-node-01
server_timezone: UTC
operator_username: aiops
ntp_pool: pool.ntp.org

base_packages:
  - curl
  - wget
  - git
  - vim
  - htop
  - iotop
  - nvme-cli
  - net-tools
  - lsof
  - strace
  - python3-pip
  - python3-venv
  - build-essential
  - cmake
  - pkg-config
  - libssl-dev
  - unattended-upgrades

data_volume_device: /dev/sdb   # adjust to your block device
data_volume_uuid: ""           # fill with `blkid` output after first format
```

**Step 4 — Create the playbook at `ai-baseline/site.yml`:**

```yaml
---
- name: AI Server Baseline Provisioning
  hosts: ai_servers
  become: true

  handlers:
    - name: Restart sshd
      ansible.builtin.systemd:
        name: ssh
        state: restarted

    - name: Restart chrony
      ansible.builtin.systemd:
        name: chronyd
        state: restarted

  tasks:

    # ── System Updates ────────────────────────────────────────────────────────
    - name: Update apt cache and upgrade all packages
      ansible.builtin.apt:
        update_cache: true
        upgrade: dist
        cache_valid_time: 3600

    - name: Install base packages
      ansible.builtin.apt:
        name: "{{ base_packages }}"
        state: present
        update_cache: false

    # ── System Identity ───────────────────────────────────────────────────────
    - name: Set hostname
      ansible.builtin.hostname:
        name: "{{ server_hostname }}"

    - name: Set timezone
      community.general.timezone:
        name: "{{ server_timezone }}"

    - name: Set locale
      ansible.builtin.lineinfile:
        path: /etc/locale.gen
        regexp: '^#?\s*en_US.UTF-8'
        line: 'en_US.UTF-8 UTF-8'
        state: present

    - name: Generate locale
      ansible.builtin.command:
        cmd: locale-gen
      changed_when: false

    - name: Set /etc/hosts entry for this server
      ansible.builtin.lineinfile:
        path: /etc/hosts
        regexp: "^127\\.0\\.1\\.1"
        line: "127.0.1.1  {{ server_hostname }}"
        state: present

    # ── Users and SSH Keys ────────────────────────────────────────────────────
    - name: Create AI operator user
      ansible.builtin.user:
        name: "{{ operator_username }}"
        comment: AI Workload Operator
        groups: sudo
        append: true
        shell: /bin/bash
        create_home: true
        state: present

    - name: Create AI service account
      ansible.builtin.user:
        name: aiuser
        comment: AI Workload Service Account
        shell: /usr/sbin/nologin
        create_home: false
        system: true
        state: present

    - name: Deploy operator SSH public key
      ansible.posix.authorized_key:
        user: "{{ operator_username }}"
        key: "{{ lookup('file', 'files/operator_id_ed25519.pub') }}"
        state: present
        exclusive: false

    - name: Harden SSH — disable root login
      ansible.builtin.lineinfile:
        path: /etc/ssh/sshd_config
        regexp: '^#?PermitRootLogin'
        line: 'PermitRootLogin no'
        state: present
        validate: '/usr/sbin/sshd -t -f %s'
      notify: Restart sshd

    - name: Harden SSH — disable password authentication
      ansible.builtin.lineinfile:
        path: /etc/ssh/sshd_config
        regexp: '^#?PasswordAuthentication'
        line: 'PasswordAuthentication no'
        state: present
        validate: '/usr/sbin/sshd -t -f %s'
      notify: Restart sshd

    - name: Harden SSH — set MaxAuthTries
      ansible.builtin.lineinfile:
        path: /etc/ssh/sshd_config
        regexp: '^#?MaxAuthTries'
        line: 'MaxAuthTries 3'
        state: present
        validate: '/usr/sbin/sshd -t -f %s'
      notify: Restart sshd

    # ── Swap ──────────────────────────────────────────────────────────────────
    - name: Check if swap file exists
      ansible.builtin.stat:
        path: /swapfile
      register: swapfile_stat

    - name: Allocate swap file
      ansible.builtin.command:
        cmd: fallocate -l 4G /swapfile
      when: not swapfile_stat.stat.exists

    - name: Set swap file permissions
      ansible.builtin.file:
        path: /swapfile
        owner: root
        group: root
        mode: "0600"

    - name: Format swap file
      ansible.builtin.command:
        cmd: mkswap /swapfile
      when: not swapfile_stat.stat.exists

    - name: Enable swap file
      ansible.builtin.command:
        cmd: swapon /swapfile
      when: not swapfile_stat.stat.exists

    - name: Persist swap in /etc/fstab
      ansible.builtin.mount:
        path: none
        src: /swapfile
        fstype: swap
        opts: sw
        state: present

    # ── Storage ───────────────────────────────────────────────────────────────
    - name: Ensure XFS filesystem on data volume
      community.general.filesystem:
        fstype: xfs
        dev: "{{ data_volume_device }}"
        force: false
      when: data_volume_device is defined and data_volume_device | length > 0

    - name: Create AI data mount point
      ansible.builtin.file:
        path: /mnt/aidata
        state: directory
        owner: aiuser
        group: aiuser
        mode: "0755"

    - name: Mount AI data volume persistently
      ansible.builtin.mount:
        path: /mnt/aidata
        src: "{{ data_volume_device }}"
        fstype: xfs
        opts: defaults,noatime,nodiratime
        state: mounted
      when: data_volume_device is defined and data_volume_device | length > 0

    # ── Kernel Tuning ─────────────────────────────────────────────────────────
    - name: Apply AI workload kernel parameters
      ansible.builtin.sysctl:
        name: "{{ item.name }}"
        value: "{{ item.value }}"
        state: present
        reload: true
        sysctl_file: /etc/sysctl.d/90-ai-workload.conf
      loop:
        - { name: vm.swappiness,               value: "5"          }
        - { name: vm.dirty_ratio,              value: "15"         }
        - { name: vm.dirty_background_ratio,   value: "5"          }
        - { name: vm.overcommit_memory,        value: "1"          }
        - { name: net.core.rmem_max,           value: "134217728"  }
        - { name: net.core.wmem_max,           value: "134217728"  }
        - { name: net.core.rmem_default,       value: "67108864"   }
        - { name: net.core.wmem_default,       value: "67108864"   }
        - { name: net.ipv4.tcp_rmem,           value: "4096 87380 134217728" }
        - { name: net.ipv4.tcp_wmem,           value: "4096 65536 134217728" }
        - { name: net.core.netdev_max_backlog, value: "250000"     }
        - { name: net.ipv4.tcp_mtu_probing,    value: "1"          }

    - name: Set ulimits for AI workload service account
      ansible.builtin.blockinfile:
        path: /etc/security/limits.conf
        marker: "# {mark} ANSIBLE MANAGED - aiuser limits"
        block: |
          aiuser soft nofile 65536
          aiuser hard nofile 65536
          aiuser soft nproc  32768
          aiuser hard nproc  32768

    # ── NTP ───────────────────────────────────────────────────────────────────
    - name: Install chrony
      ansible.builtin.apt:
        name: chrony
        state: present
        update_cache: false

    - name: Stop and disable systemd-timesyncd
      ansible.builtin.systemd:
        name: systemd-timesyncd
        state: stopped
        enabled: false

    - name: Configure chrony NTP pool
      ansible.builtin.blockinfile:
        path: /etc/chrony/chrony.conf
        marker: "# {mark} ANSIBLE MANAGED NTP SERVERS"
        block: |
          pool {{ ntp_pool }} iburst maxsources 4
          makestep 1.0 3
          rtcsync
      notify: Restart chrony

    - name: Enable and start chrony
      ansible.builtin.systemd:
        name: chronyd
        state: started
        enabled: true
```

**Step 5 — Verify syntax, then run in check mode:**

```bash
ansible-playbook -i inventory.ini site.yml --syntax-check
ansible-playbook -i inventory.ini site.yml --check --diff
```

Expected output (check mode, no actual changes made):

```
PLAY [AI Server Baseline Provisioning] *******************************

TASK [Gathering Facts] ***********************************************
ok: [ai-node-01]

TASK [Update apt cache and upgrade all packages] *********************
changed: [ai-node-01]

...

PLAY RECAP ***********************************************************
ai-node-01  : ok=28  changed=14  unreachable=0  failed=0  skipped=2
```

**Step 6 — Run the playbook for real:**

```bash
ansible-playbook -i inventory.ini site.yml
```

**Step 7 — Verify the result on the target server:**

```bash
# SSH in as the operator user (not ubuntu) to confirm key and user worked
ssh -i files/operator_id_ed25519 aiops@192.168.1.100

# On the target — check kernel parameters
sysctl vm.swappiness net.core.rmem_max

# Check swap
swapon --show

# Check NTP sync
chronyc tracking

# Check mount
df -h /mnt/aidata
```

Expected verification output:

```
vm.swappiness = 5
net.core.rmem_max = 134217728

NAME      TYPE SIZE USED PRIO
/swapfile file   4G   0B   -2

Reference ID    : A29FC801 (time.cloudflare.com)
Stratum         : 3
System time     : 0.000012345 seconds fast of NTP time
Last offset     : +0.000008123 seconds
RMS offset      : 0.000015678 seconds
Frequency       : 2.345 ppm fast
Residual freq   : -0.001 ppm
Skew            : 0.089 ppm
Root delay      : 0.012345678 seconds
Root dispersion : 0.000456789 seconds
Update interval : 64.0 seconds
Leap status     : Normal

Filesystem      Size  Used Avail Use% Mounted on
/dev/sdb        100G  748M   99G   1% /mnt/aidata
```

### Example 2: Managing /etc/hosts Across a Multi-Node Cluster

This example demonstrates using a single playbook run to keep `/etc/hosts` synchronized across all nodes in an AI cluster, so that every node can resolve every other node by hostname without a DNS server.

**Setup:** An inventory with three nodes in the `ai_cluster` group. Each has an `ansible_host` variable set to its management IP.

```ini
[ai_cluster]
ai-node-01 ansible_host=10.0.0.11
ai-node-02 ansible_host=10.0.0.12
ai-node-03 ansible_host=10.0.0.13

[ai_cluster:vars]
ansible_user=aiops
ansible_python_interpreter=/usr/bin/python3
```

**The play — run this against `ai_cluster` as a whole:**

```yaml
---
- name: Synchronize /etc/hosts across AI cluster
  hosts: ai_cluster
  become: true

  tasks:
    - name: Populate /etc/hosts with all cluster member entries
      ansible.builtin.blockinfile:
        path: /etc/hosts
        marker: "# {mark} ANSIBLE MANAGED CLUSTER MEMBERS"
        block: |
          {% for host in groups['ai_cluster'] %}
          {{ hostvars[host]['ansible_host'] }}  {{ host }}
          {% endfor %}
```

**Run it:**

```bash
ansible-playbook -i inventory.ini cluster-hosts.yml
```

**Verify on ai-node-01:**

```bash
ssh aiops@10.0.0.11 "cat /etc/hosts | grep -A5 'ANSIBLE MANAGED'"
```

Expected output on each node:

```
# BEGIN ANSIBLE MANAGED CLUSTER MEMBERS
10.0.0.11  ai-node-01
10.0.0.12  ai-node-02
10.0.0.13  ai-node-03
# END ANSIBLE MANAGED CLUSTER MEMBERS
```

**Verify hostname resolution works:**

```bash
ssh aiops@10.0.0.11 "ping -c 1 ai-node-03"
```

```
PING ai-node-03 (10.0.0.13) 56(84) bytes of data.
64 bytes from ai-node-03 (10.0.0.13): icmp_seq=1 ttl=64 time=0.412 ms
```

When you add a fourth node to the inventory, re-running the playbook updates all three existing nodes' `/etc/hosts` files automatically, replacing the managed block with the new four-entry block.

### Example 3: Verifying Idempotency

A critical habit when writing provisioning playbooks is confirming that a second run produces zero `changed` results. This example shows how to test idempotency by running the playbook twice and inspecting the recap.

**First run (establishes baseline):**

```bash
ansible-playbook -i inventory.ini site.yml 2>&1 | tail -5
```

```
PLAY RECAP ***********************************************************
ai-node-01  : ok=32  changed=28  unreachable=0  failed=0  skipped=2
```

**Immediately run again without changing anything:**

```bash
ansible-playbook -i inventory.ini site.yml 2>&1 | tail -5
```

```
PLAY RECAP ***********************************************************
ai-node-01  : ok=32  changed=0  unreachable=0  failed=0  skipped=2
```

A `changed=0` result on the second run confirms every task in the playbook is idempotent. If `changed` is nonzero on the second run, identify the offending task by running with `-v` and looking for yellow `changed` output, then fix it with a `when` guard, `changed_when: false`, or by replacing the `command`/`shell` task with a purpose-built module.

## Common Pitfalls

### 1. Using `shell` or `command` Without Idempotency Guards

**Description:** Using `shell` or `command` for operations that have a dedicated Ansible module, or using them without `when`, `creates`, or `changed_when` guards.

**Why it happens:** The `command` module is flexible and familiar to system administrators who know shell commands, making it a tempting shortcut.

**Incorrect pattern:**

```yaml
- name: Set swappiness
  ansible.builtin.shell: echo 10 > /proc/sys/vm/swappiness
```

**Correct pattern:**

```yaml
- name: Set swappiness
  ansible.builtin.sysctl:
    name: vm.swappiness
    value: "10"
    state: present
    reload: true
```

### 2. Forgetting `validate` on sshd_config Changes

**Description:** Modifying `/etc/ssh/sshd_config` with `lineinfile` and notifying a handler to restart `sshd`, without validating the config syntax first. A syntax error locks you out of the server permanently.

**Why it happens:** The `validate` parameter is easy to overlook because it is not required for the task to succeed.

**Incorrect pattern:**

```yaml
- name: Disable root login
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#?PermitRootLogin'
    line: 'PermitRootLogin no'
  notify: Restart sshd
  # No validate — a typo in 'line' deploys broken sshd_config, handler restarts
  # sshd, sshd refuses to start with bad config, you are locked out
```

**Correct pattern:**

```yaml
- name: Disable root login
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#?PermitRootLogin'
    line: 'PermitRootLogin no'
    validate: '/usr/sbin/sshd -t -f %s'
  notify: Restart sshd
```

### 3. Restarting Services Directly Instead of Using Handlers

**Description:** Using `ansible.builtin.systemd: state: restarted` directly in a task, which restarts the service every single playbook run regardless of whether any configuration changed.

**Why it happens:** Handlers require an extra block in the playbook and a `notify` directive, which seems like more work than a direct task.

**Incorrect pattern:**

```yaml
- name: Disable password auth
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#?PasswordAuthentication'
    line: 'PasswordAuthentication no'

- name: Restart sshd  # Runs EVERY time — breaks idempotency
  ansible.builtin.systemd:
    name: ssh
    state: restarted
```

**Correct pattern:**

```yaml
- name: Disable password auth
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#?PasswordAuthentication'
    line: 'PasswordAuthentication no'
    validate: '/usr/sbin/sshd -t -f %s'
  notify: Restart sshd

handlers:
  - name: Restart sshd
    ansible.builtin.systemd:
      name: ssh
      state: restarted
```

### 4. Using `append: false` (the default) When Adding a User to a Group

**Description:** The `user` module's `groups` parameter replaces the user's supplementary groups by default when `append` is not set to `true`. This silently removes the user from all other groups, including `sudo`.

**Why it happens:** The parameter name `append` is not obvious — the natural reading of `groups: sudo` is "give this user the sudo group," not "replace this user's groups with only sudo."

**Incorrect pattern:**

```yaml
- name: Create operator user
  ansible.builtin.user:
    name: aiops
    groups: sudo   # append defaults to false — removes all OTHER groups
```

**Correct pattern:**

```yaml
- name: Create operator user
  ansible.builtin.user:
    name: aiops
    groups: sudo
    append: true   # add sudo to existing groups without removing others
```

### 5. Storing Public Key Files in the Wrong Path for the `lookup` Plugin

**Description:** Using `lookup('file', 'operator_id_ed25519.pub')` without specifying a path relative to the playbook directory, causing Ansible to look relative to the working directory the `ansible-playbook` command is invoked from.

**Why it happens:** The `lookup` plugin resolves file paths relative to the playbook file's directory on the control node, which is intuitive when you run `ansible-playbook` from the playbook directory but breaks in CI pipelines or when using `ansible-playbook /absolute/path/to/site.yml` from a different directory.

**Incorrect pattern:**

```yaml
key: "{{ lookup('file', '~/.ssh/operator.pub') }}"  # ~ expands on control node, brittle in CI
```

**Correct pattern:**

```yaml
# Store key in files/ subdirectory next to the playbook
# Use a path relative to the playbook — Ansible resolves it correctly
key: "{{ lookup('file', 'files/operator_id_ed25519.pub') }}"
```

### 6. Using `state: latest` for APT Packages in a Provisioning Playbook

**Description:** Using `state: latest` for packages that have AI/ML version dependencies (Python, CUDA components, build tools) causes the installed version to drift whenever the apt mirror updates, breaking reproducibility.

**Why it happens:** `state: latest` feels like good hygiene, and it is appropriate for security tools like `ufw` or `fail2ban`, but not for packages that are part of a versioned software stack.

**Incorrect pattern:**

```yaml
- name: Install Python
  ansible.builtin.apt:
    name: python3
    state: latest   # Will install whatever is current, may break pinned deps
```

**Correct pattern:**

```yaml
- name: Install specific Python version
  ansible.builtin.apt:
    name: python3.11
    state: present   # Idempotent: install if absent, do not upgrade if present
```

### 7. Omitting `become: true` Without a Clear Reason

**Description:** Forgetting `become: true` on a play or task that requires root privileges causes the task to fail with a permission error, but only if the connecting user is not root — which is correct practice on hardened servers.

**Why it happens:** During development, playbooks are often tested as root over a direct connection where `become` is not needed, then fail when run under a normal operator account.

**Incorrect pattern:**

```yaml
- name: AI Server Provisioning
  hosts: ai_servers
  # Missing become: true — all privileged tasks will fail as the operator user

  tasks:
    - name: Install packages
      ansible.builtin.apt:
        name: curl
        state: present   # Will fail: "Permission denied" writing to /var/lib/apt
```

**Correct pattern:**

```yaml
- name: AI Server Provisioning
  hosts: ai_servers
  become: true   # All tasks in this play run as root via sudo

  tasks:
    - name: Install packages
      ansible.builtin.apt:
        name: curl
        state: present
```

## Summary

- A single Ansible playbook can transform a fresh Ubuntu 22.04 server into a baseline AI-ready host by combining the `apt`, `hostname`, `timezone`, `user`, `authorized_key`, `lineinfile`, `blockinfile`, `mount`, and `sysctl` modules in a logical sequence — from system identity and user creation through storage mounting and kernel tuning.
- Idempotency is not automatic with `command` and `shell` — it must be enforced explicitly using `when` guards, the `stat` module for existence checks, `changed_when`, or by replacing shell commands with purpose-built Ansible modules whenever one exists.
- The `lineinfile` module handles single-line configuration changes with regex targeting, while `blockinfile` manages multi-line sections using delimited markers, making both safe for repeated runs against files partially managed by other tools.
- Kernel tuning parameters written via the `sysctl` module to a file under `/etc/sysctl.d/` are applied immediately and persist across reboots, and the critical AI-workload parameters (`vm.swappiness=5`, `vm.overcommit_memory=1`, large socket buffers) are safe defaults that improve performance without introducing instability.
- Handlers, the `validate` parameter, `become: true` at the play level, and Ansible Vault for secrets are the four structural practices that separate a production-grade provisioning playbook from a one-time shell script.

## Further Reading

- [Ansible Built-In Module Index](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/index.html) — The authoritative reference for every parameter of every module covered in this module, including `lineinfile`, `blockinfile`, `sysctl`, `mount`, `user`, and `authorized_key`; essential when debugging unexpected task behavior.
- [ansible.posix.authorized_key module documentation](https://docs.ansible.com/ansible/latest/collections/ansible/posix/authorized_key_module.html) — Full parameter reference for the `authorized_key` module, including the `exclusive` parameter behavior and key format requirements for different key types (RSA, ed25519, ECDSA).
- [Chrony Documentation — Configuration Reference](https://chrony-project.org/doc/4.5/chrony.conf.html) — Complete reference for `chrony.conf` directives including `pool`, `makestep`, `rtcsync`, and monitoring configuration; required reading before customizing NTP behavior beyond the basics in this module.
- [Linux kernel sysctl documentation — vm/ namespace](https://www.kernel.org/doc/html/latest/admin-guide/sysctl/vm.html) — Official kernel documentation for every `vm.*` sysctl parameter including `swappiness`, `overcommit_memory`, `dirty_ratio`, and `dirty_background_ratio`, with precise descriptions of what each value means and its effect on memory management behavior.
- [NCCL Performance Tuning Guide — System Configuration](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/env.html) — NVIDIA's official guidance on OS-level configuration for high-performance collective communications, covering socket buffer sizes, MTU settings, and other network parameters that directly correspond to the sysctl values set in this module.
- [Ansible Best Practices — Playbook Tips](https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html) — Ansible's official tips document covering directory layout, variable organization, handler patterns, and the use of `--check` and `--diff`; a concise reference for the structural practices emphasized in this module.
- [Ubuntu 22.04 Server Guide — Storage Configuration](https://ubuntu.com/server/docs/storage-introduction) — Ubuntu's official storage documentation covering filesystem creation, `/etc/fstab` syntax, UUID-based mounts, and mount options including `noatime`; provides the Ubuntu-specific context for the storage provisioning tasks in this module.
- [Ansible Vault documentation](https://docs.ansible.com/ansible/latest/vault_guide/index.html) — Complete guide to encrypting secrets in Ansible, including `ansible-vault encrypt_string` for inline secrets, vault-encrypted variable files, and using vault passwords in CI/CD pipelines; mandatory reading before storing any credential in a playbook variable.
