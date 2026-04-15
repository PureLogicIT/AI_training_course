# Module 0: Setup
> Subject: Ansible | Difficulty: Beginner | Estimated Time: 105 minutes

## Objective

After completing this module, you will be able to explain what Ansible is, why its agentless architecture makes it different from other automation tools, and what role each machine plays in an Ansible setup. You will install Ansible on a Linux control node using the method appropriate for your distribution (Ubuntu/Debian PPA, Fedora/RHEL dnf, Arch pacman, or pip in a virtualenv), verify the installation with `ansible --version` and understand every line of its output, lay out a standard Ansible project directory with `ansible.cfg`, an inventory file in both INI and YAML formats, and SSH key authentication configured for a dedicated service account on your managed nodes. By the end of this module your control node will be ready to run ad-hoc commands, and you will have confirmed live connectivity to at least one managed node with `ansible all -m ping`.

## Prerequisites

- A Linux machine or VM that will act as the **control node** — Ubuntu 22.04 LTS / 24.04 LTS, Debian 12, Fedora 40+, RHEL 9 / AlmaLinux 9 / Rocky Linux 9, or Arch Linux. Most steps also work on macOS with Homebrew.
- `sudo` (administrator) privileges on the control node.
- At least one additional Linux host (VM, cloud instance, or physical machine) to act as a **managed node** — any modern distribution with Python 3 and an SSH server will work.
- Basic Linux command-line comfort: navigating the filesystem, editing files with `nano` or `vim`, and understanding file permissions (`chmod`, `chown`).
- A working knowledge of SSH — you should know what a key pair is and how `ssh user@host` works. You do not need to be an SSH expert.
- No prior Ansible or infrastructure automation experience is assumed.

## Key Concepts

### What Ansible Is — The Big Picture

Ansible is an open-source IT automation platform that lets you describe the desired state of your infrastructure in plain YAML files called *playbooks* and then apply those descriptions across any number of remote machines simultaneously. Rather than SSH-ing into each server by hand and running commands one at a time, you write down what should be true — "the `nginx` package should be installed," "the firewall should allow port 443," "the `deploy` user should exist with these SSH keys" — and Ansible makes it so on every host in your inventory.

The name matters: Ansible is the fictional faster-than-light communication device from Ursula K. Le Guin's science fiction novels. The software borrows that name to describe the idea of sending instructions to many distant systems instantly.

At its core, Ansible has three main pieces:

- **Control node** — the machine you run Ansible on. This is your laptop, a CI/CD server, or a dedicated jump host. Ansible itself is installed only here.
- **Managed nodes** — the servers, VMs, or cloud instances Ansible configures. No Ansible software is installed on them.
- **Inventory** — a file (or directory of files) that tells Ansible which hosts exist and how to reach them.

```
Your Laptop / CI Server          Production Servers
─────────────────────            ────────────────────────────────
  [CONTROL NODE]                 [MANAGED NODES]
  ansible installed        SSH   ┌─────────────────────────────┐
  playbooks/            ──────►  │  web-01  web-02  db-01      │
  inventory/                     │  No Ansible agent installed │
  ansible.cfg                    │  Only needs: sshd + python3 │
                                 └─────────────────────────────┘
```

### Agentless Architecture and the Push Model

The defining characteristic of Ansible is that it is **agentless**: there is no daemon, no background process, and no Ansible software permanently installed on the machines it manages. This stands in contrast to tools like Puppet or Chef, which require an agent process running on every managed node — a process that must itself be bootstrapped, secured, updated, and monitored.

When Ansible runs a task, it:
1. Opens an SSH connection to the target host.
2. Copies a small, self-contained Python script to a temporary directory on the remote host.
3. Executes that script and collects the JSON result.
4. Deletes the temporary file and closes the connection.

The entire operation leaves no persistent footprint. The only hard requirements on a managed node are a running SSH server and Python 3 — both of which ship by default on every modern Linux distribution.

Ansible also follows a **push model**: changes originate on the control node and are pushed outward to managed nodes on demand. You run `ansible-playbook` and Ansible immediately connects to every host in the inventory and applies changes. There is no polling loop, no check-in interval, and no waiting. When the command finishes, every host is in the desired state (or Ansible has clearly reported which hosts failed and why).

```
Push model (Ansible)                Pull model (Puppet/Chef)
────────────────────                ────────────────────────
You run: ansible-playbook           Agent on each node polls
         site.yml                   a central server every
              │                     30 minutes and applies
              ▼                     whatever catalog it finds
        Ansible connects
        to each host NOW
        Changes applied
        immediately
```

### YAML, Playbooks, and Modules

Ansible's automation language is **YAML** — a human-readable data format that uses indentation to express structure. Every playbook is a YAML file. The learning curve is gentle: if you can read a bullet-pointed list, you can read a playbook.

A **playbook** contains one or more *plays*. Each play targets a group of hosts from your inventory and runs a list of *tasks*. Each task calls an Ansible **module** — a built-in unit of work that knows how to accomplish one specific thing safely and idempotently.

```yaml
# A minimal playbook — site.yml
- name: Configure web servers
  hosts: webservers
  become: true          # run tasks as root (via sudo)

  tasks:
    - name: Ensure nginx is installed
      ansible.builtin.apt:
        name: nginx
        state: present

    - name: Ensure nginx is started and enabled
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true
```

Modules are **idempotent**: running the same task twice produces the same result as running it once. If `nginx` is already installed, the `apt` module reports `ok` rather than reinstalling it. This makes Ansible safe to run repeatedly without side effects.

The `ansible` package on PyPI ships with hundreds of built-in modules covering package management, file operations, user accounts, systemd services, network configuration, cloud APIs, and more. Modules not included in the base package are distributed as **collections** via Ansible Galaxy.

### Inventory — Telling Ansible About Your Hosts

The inventory is the list of machines Ansible manages. At its simplest it is a single text file; in larger projects it becomes a directory of files with per-group and per-host variable overrides.

Inventory files support two formats — INI and YAML. Both express the same information; choose whichever your team prefers.

**INI format** (`inventory/hosts.ini`):

```ini
# Ungrouped hosts
bastion.example.com

[webservers]
web-01.example.com
web-02.example.com ansible_port=2222

[databases]
db-01.example.com ansible_user=dbadmin

[production:children]
webservers
databases
```

**YAML format** (`inventory/hosts.yml`):

```yaml
all:
  children:
    webservers:
      hosts:
        web-01.example.com:
        web-02.example.com:
          ansible_port: 2222
    databases:
      hosts:
        db-01.example.com:
          ansible_user: dbadmin
    production:
      children:
        webservers:
        databases:
```

Every host always belongs to two built-in groups: `all` (every host in the inventory) and `ungrouped` (hosts not assigned to any explicit group). Group names like `webservers` and `databases` are yours to define.

---

## Section 1: Installing Ansible on the Control Node

The current stable versions (as of April 2026) are:
- **ansible 13.x** (the community package — includes ansible-core plus a curated set of collections)
- **ansible-core 2.20.x** (the engine only — you add collections separately)

For beginners, the `ansible` package is almost always the right choice because it includes the module collections you will use immediately. The `ansible-core`-only approach is for production environments where you want to manage collection versions explicitly.

> **Note:** Ansible runs only on the **control node**. Do not install Ansible on your managed nodes.

---

### 1.1 Ubuntu and Debian (apt + official PPA)

The Ubuntu/Debian package repositories carry Ansible, but the version in the default repos often lags behind the current stable release. The official **`ppa:ansible/ansible`** maintained by the Ansible project gives you a more up-to-date package.

**Step 1 — Install prerequisite packages:**

```bash
sudo apt update
sudo apt install software-properties-common -y
```

**Step 2 — Add the official Ansible PPA:**

```bash
sudo add-apt-repository --yes --update ppa:ansible/ansible
```

The `--yes` flag accepts the repository addition without a prompt. `--update` refreshes the package index immediately so you do not need a separate `apt update`.

**Step 3 — Install Ansible:**

```bash
sudo apt install ansible -y
```

**Step 4 — Verify the installation:**

```bash
ansible --version
```

Expected output (version numbers will differ slightly based on release):

```
ansible [core 2.20.4]
  config file = None
  configured module search path = ['/home/youruser/.ansible/plugins/modules', '/usr/share/ansible/plugins/modules']
  ansible python module location = /usr/lib/python3/dist-packages/ansible
  ansible collection location = /home/youruser/.ansible/collections:/usr/share/ansible/collections
  executable location = /usr/bin/ansible
  python version = 3.12.3 (main, ...) [GCC 13.2.0]
  jinja version = 3.1.4
  libyaml = True
```

The most important lines are:
- `ansible [core 2.20.4]` — the ansible-core version actually installed.
- `config file = None` — no `ansible.cfg` found yet; we will create one in Section 3.
- `python version` — the Python interpreter Ansible is using.
- `libyaml = True` — the fast C-based YAML parser is available (good for performance).

---

### 1.2 Fedora (dnf)

Fedora's default repositories include Ansible. Install directly:

```bash
sudo dnf install ansible -y
ansible --version
```

---

### 1.3 RHEL 9, AlmaLinux 9, Rocky Linux 9, CentOS Stream 9 (dnf + EPEL)

On RHEL-based systems there are two separate packages:

| Package | What it contains | When to use it |
|---|---|---|
| `ansible-core` | The automation engine only (~70 built-in modules) | Production: pin your own collections |
| `ansible` | ansible-core + community collections (~3,000+ modules) | Development / learning |

**`ansible-core` is in the AppStream repository** and requires no extra setup:

```bash
sudo dnf install ansible-core -y
```

**`ansible` (full package) is in EPEL.** Enable EPEL first:

```bash
# Enable EPEL
sudo dnf install epel-release -y

# Install the full Ansible package
sudo dnf install ansible -y
```

> **RHEL 9 note:** On a registered RHEL 9 system without EPEL, `ansible-core` from AppStream is the recommended path. The `ansible` community package from EPEL is appropriate for learning and lab environments.

Verify after either installation:

```bash
ansible --version
```

---

### 1.4 Arch Linux (pacman)

The Arch Linux community repositories include both packages:

```bash
# Full package with collections (recommended for learning)
sudo pacman -S ansible

# Core only
sudo pacman -S ansible-core
```

Verify:

```bash
ansible --version
```

---

### 1.5 pip in a Virtual Environment (any distro)

The pip approach installs the very latest release from PyPI and isolates Ansible from your system Python. Use this when:
- Your distro packages a version that is too old.
- You need multiple Ansible versions side by side.
- You are on macOS or a distro not covered above.
- You are running Ansible inside a CI/CD container.

**Step 1 — Ensure Python 3.12+ and pip are available:**

```bash
python3 --version      # must be 3.12 or later
python3 -m pip --version
```

**Step 2 — Create and activate a virtual environment:**

```bash
python3 -m venv ~/.venv/ansible
source ~/.venv/ansible/bin/activate
```

Your shell prompt will change to show `(ansible)` at the start. All subsequent `pip` and `ansible` commands use this isolated environment.

**Step 3 — Install Ansible:**

```bash
pip install --upgrade pip
pip install ansible
```

**Step 4 — Verify:**

```bash
ansible --version
```

**Step 5 — Make the environment persistent:**

Add the activation line to your shell's startup file so you do not have to re-activate after logging out:

```bash
echo 'source ~/.venv/ansible/bin/activate' >> ~/.bashrc
source ~/.bashrc
```

> **Tip:** If you use a virtualenv, always activate it before running any `ansible` or `ansible-playbook` command. A common pitfall is running commands in a shell where the environment is not active and getting a "command not found" error even though Ansible is installed.

---

## Section 2: Standard Ansible Project Structure

A well-organized project directory prevents confusion as your automation grows. The layout below follows the structure recommended by the Ansible project and is used throughout every subsequent module in this series.

```
my-ansible-project/
├── ansible.cfg               # Project-wide configuration
├── inventory/
│   ├── hosts.ini             # Static inventory (INI format)
│   ├── group_vars/
│   │   ├── all.yml           # Variables for every host
│   │   └── webservers.yml    # Variables for the webservers group
│   └── host_vars/
│       └── web-01.yml        # Variables for one specific host
├── playbooks/
│   ├── site.yml              # Master playbook (runs everything)
│   ├── webservers.yml        # Playbook for the webservers group
│   └── databases.yml
└── roles/                    # Covered in Module 2
    └── nginx/
        ├── tasks/
        │   └── main.yml
        └── handlers/
            └── main.yml
```

Create the skeleton for a new project:

```bash
mkdir -p my-ansible-project/{inventory/{group_vars,host_vars},playbooks,roles}
cd my-ansible-project
```

### 2.1 ansible.cfg — The Configuration File

`ansible.cfg` is an INI-format file that sets project-wide defaults. Ansible searches for it in this order (first match wins):

1. Path in the `ANSIBLE_CONFIG` environment variable.
2. `./ansible.cfg` — the current working directory (**recommended**).
3. `~/.ansible.cfg` — your home directory.
4. `/etc/ansible/ansible.cfg` — the system-wide default.

**Always keep `ansible.cfg` in the root of your project directory** alongside your `inventory/` and `playbooks/` directories. This ensures Ansible uses the project's settings regardless of where on the system the project lives, and the file travels with your repository when you check it into version control.

A starter `ansible.cfg` for a new project:

```ini
[defaults]
# Where to find the inventory
inventory = inventory/hosts.ini

# The SSH user Ansible will connect as (override per-host in inventory)
remote_user = ansible

# Path to the SSH private key for authentication
private_key_file = ~/.ssh/ansible_ed25519

# Disable interactive SSH host key prompts in lab environments
# WARNING: set this to True in production for security
host_key_checking = False

# Show a summary of changed/ok/failed hosts after each run
stdout_callback = yaml

[privilege_escalation]
# Allow Ansible to use sudo for tasks that require root
become = true
become_method = sudo
become_user = root
```

Key settings explained:

| Setting | What it does |
|---|---|
| `inventory` | Relative or absolute path to the inventory file or directory. |
| `remote_user` | The SSH username Ansible logs in as. Overridden per-host by `ansible_user` in inventory. |
| `private_key_file` | Path to the SSH private key. Overridden per-host by `ansible_ssh_private_key_file` in inventory. |
| `host_key_checking` | When `False`, Ansible does not prompt you to confirm new SSH host keys. Useful in labs; keep `True` in production. |
| `become` | When `True`, all tasks run with `sudo` by default. |

### 2.2 Inventory — Static and Dynamic

**Static inventory** is a file (or directory of files) you maintain by hand. This is the right starting point for most projects.

An INI inventory with two groups:

```ini
# inventory/hosts.ini

[webservers]
web-01.example.com
web-02.example.com

[databases]
db-01.example.com

# Group of groups — targets all webservers AND databases
[production:children]
webservers
databases

# Variables applied to every host in [webservers]
[webservers:vars]
http_port=80
```

**Group variables** and **host variables** go in separate YAML files, not in the INI file itself (keeping the inventory clean):

```yaml
# inventory/group_vars/all.yml
# Applied to every host
ansible_user: ansible
ansible_ssh_private_key_file: ~/.ssh/ansible_ed25519
```

```yaml
# inventory/group_vars/webservers.yml
# Applied only to hosts in [webservers]
nginx_worker_processes: 4
```

```yaml
# inventory/host_vars/web-01.yml
# Applied only to web-01.example.com
ansible_port: 2222   # this host uses a non-standard SSH port
```

**Dynamic inventory** is covered in a later module. In brief: instead of a static file, you point Ansible at a script or plugin that queries a cloud API (AWS, GCP, Azure, etc.) at runtime and returns the current list of hosts. The same group variables and host variables concepts apply.

### 2.3 Playbooks and Roles

Keep playbooks in `playbooks/`. A typical layout has a `site.yml` that imports the others:

```yaml
# playbooks/site.yml
- import_playbook: webservers.yml
- import_playbook: databases.yml
```

`roles/` holds reusable, self-contained units of automation. Roles are covered in detail in Module 2. For now, just know the directory belongs there.

---

## Section 3: Configuring SSH for Ansible

Ansible connects to managed nodes over SSH. The setup involves three steps: generating a dedicated key pair, copying the public key to each managed node, and optionally configuring `~/.ssh/config` so the connection details are tidy.

### 3.1 Generate a Dedicated SSH Key Pair

Create a key pair specifically for Ansible rather than reusing your personal key. This lets you rotate or revoke Ansible's access independently.

```bash
ssh-keygen -t ed25519 -C "ansible-control-key" -f ~/.ssh/ansible_ed25519
```

- `-t ed25519` — the Ed25519 algorithm is modern, fast, and generates smaller keys than RSA.
- `-C "ansible-control-key"` — a comment to identify this key's purpose in `authorized_keys` files.
- `-f ~/.ssh/ansible_ed25519` — the output path. This creates two files:
  - `~/.ssh/ansible_ed25519` — the **private key** (never share or copy this).
  - `~/.ssh/ansible_ed25519.pub` — the **public key** (this goes on every managed node).

When prompted for a passphrase, press Enter twice to leave it empty. Ansible runs unattended; a passphrase would require human input at runtime unless you configure an SSH agent. For lab environments, no passphrase is standard practice. In production, use `ssh-agent` or a secrets manager.

### 3.2 Copy the Public Key to Managed Nodes

Use `ssh-copy-id` to append your public key to the `authorized_keys` file on each managed node. You will need password-based SSH access for this one-time step:

```bash
ssh-copy-id -i ~/.ssh/ansible_ed25519.pub ansible@web-01.example.com
ssh-copy-id -i ~/.ssh/ansible_ed25519.pub ansible@web-02.example.com
ssh-copy-id -i ~/.ssh/ansible_ed25519.pub ansible@db-01.example.com
```

If `ssh-copy-id` is not available on your system, use the manual equivalent:

```bash
cat ~/.ssh/ansible_ed25519.pub | ssh ansible@web-01.example.com \
  "mkdir -p ~/.ssh && chmod 700 ~/.ssh && \
   cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

### 3.3 Test SSH Connectivity Manually

Before involving Ansible at all, confirm that plain SSH works:

```bash
ssh -i ~/.ssh/ansible_ed25519 ansible@web-01.example.com
```

You should get a shell prompt on the remote host without being asked for a password. If you are prompted for a password, the key was not copied correctly — re-run `ssh-copy-id`.

### 3.4 Configure ~/.ssh/config (Optional but Recommended)

An SSH config file makes connections cleaner and avoids having to specify the key and username on every command:

```
# ~/.ssh/config

Host web-01.example.com
    User ansible
    IdentityFile ~/.ssh/ansible_ed25519
    StrictHostKeyChecking no

Host web-02.example.com
    User ansible
    IdentityFile ~/.ssh/ansible_ed25519
    StrictHostKeyChecking no

Host db-01.example.com
    User ansible
    IdentityFile ~/.ssh/ansible_ed25519
    StrictHostKeyChecking no
```

Set the correct permissions on the config file:

```bash
chmod 600 ~/.ssh/config
```

> **Note on `StrictHostKeyChecking no`:** This setting is appropriate for lab environments where you frequently rebuild VMs with new SSH host keys. In production, leave it at the default (`yes`) and manage host keys explicitly via your `known_hosts` file. The `ansible.cfg` setting `host_key_checking = False` achieves the same effect at the Ansible level.

---

## Section 4: Setting Up Managed Nodes

Ansible's requirements on a managed node are deliberately minimal:

1. **An SSH server (`sshd`) must be running.** It is enabled by default on most server-oriented Linux distributions. Verify with `sudo systemctl status sshd`.
2. **Python 3 must be available.** Ansible uploads small Python scripts and executes them remotely. Modern Ubuntu, Debian, Fedora, and RHEL all ship with Python 3. Verify with `python3 --version`.
3. **A user account that can connect via SSH.** Ideally a dedicated service account with passwordless sudo.

### 4.1 Create a Dedicated `ansible` Service Account

Run these commands **on each managed node** (not the control node). You can do this over a regular SSH session before Ansible is set up:

```bash
# Create the ansible user (no interactive login shell needed in production,
# but /bin/bash is easier during initial setup)
sudo useradd -m -s /bin/bash ansible

# Grant passwordless sudo to the ansible user
# This creates a dedicated sudoers drop-in file (safer than editing /etc/sudoers directly)
echo "ansible ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/ansible

# Restrict permissions on the sudoers file (required — sudo ignores files with loose permissions)
sudo chmod 440 /etc/sudoers.d/ansible
```

Create the `.ssh` directory for the ansible user:

```bash
sudo mkdir -p /home/ansible/.ssh
sudo chmod 700 /home/ansible/.ssh
sudo chown ansible:ansible /home/ansible/.ssh
```

Now paste in the **public key** from your control node (`~/.ssh/ansible_ed25519.pub`):

```bash
# On the managed node — paste the content of your ansible_ed25519.pub file here
echo "ssh-ed25519 AAAA...your-public-key-here... ansible-control-key" \
  | sudo tee /home/ansible/.ssh/authorized_keys

sudo chmod 600 /home/ansible/.ssh/authorized_keys
sudo chown ansible:ansible /home/ansible/.ssh/authorized_keys
```

### 4.2 Verify Python Is Available

```bash
# On the managed node
python3 --version
```

If Python 3 is not installed (rare on modern systems), install it:

```bash
# Ubuntu/Debian
sudo apt install python3 -y

# RHEL/Fedora/AlmaLinux
sudo dnf install python3 -y

# Arch Linux
sudo pacman -S python
```

### 4.3 Windows Managed Nodes (Brief Mention)

Ansible can manage Windows hosts using **WinRM** (Windows Remote Management) or **SSH** (available on Windows 10/Server 2019 and later). The setup is more involved — you need to enable the WinRM listener, configure authentication, and install the `pywinrm` Python library on the control node. Windows management is out of scope for this module but is well-documented in the official Ansible Windows guide (see Further Reading).

---

## Section 5: Testing the Connection

With Ansible installed, `ansible.cfg` configured, an inventory file in place, and SSH keys deployed, you are ready to verify end-to-end connectivity.

### 5.1 Check Your Inventory

Before running any Ansible command, verify Ansible can parse your inventory correctly:

```bash
# From your project directory (where ansible.cfg lives)
cd ~/my-ansible-project

# List all hosts in JSON format
ansible-inventory --list

# Show a visual tree of groups and hosts
ansible-inventory --graph
```

Expected `--graph` output:

```
@all:
  |--@ungrouped:
  |--@webservers:
  |  |--web-01.example.com
  |  |--web-02.example.com
  |--@databases:
  |  |--db-01.example.com
  |--@production:
  |  |--@webservers:
  |  |--@databases:
```

If a host is missing or in the wrong group, fix `inventory/hosts.ini` before continuing.

### 5.2 The Ping Module

The `ansible` command runs **ad-hoc commands** — one-off tasks without a playbook. The `ping` module is the standard connectivity check:

```bash
ansible all -m ping
```

The `ping` module does not send an ICMP ping. It opens an SSH connection, verifies that Python is available on the remote host, and returns `pong`. Success output looks like:

```
web-01.example.com | SUCCESS => {
    "ansible_facts": {
        "discovered_interpreter_python": "/usr/bin/python3"
    },
    "changed": false,
    "ping": "pong"
}
web-02.example.com | SUCCESS => {
    "ansible_facts": {
        "discovered_interpreter_python": "/usr/bin/python3"
    },
    "changed": false,
    "ping": "pong"
}
db-01.example.com | SUCCESS => {
    "ansible_facts": {
        "discovered_interpreter_python": "/usr/bin/python3"
    },
    "changed": false,
    "ping": "pong"
}
```

An unreachable host looks like:

```
web-02.example.com | UNREACHABLE! => {
    "changed": false,
    "msg": "Failed to connect to the host via ssh: Permission denied (publickey).",
    "unreachable": true
}
```

Common causes of failure: wrong SSH user, key not deployed, `sshd` not running on the managed node, or a firewall blocking port 22. Add `-vvv` to the command for verbose SSH debugging output.

### 5.3 Gather Facts

The `setup` module (also available as `gather_facts`) collects detailed information about each managed node — OS, kernel version, IP addresses, CPU count, memory, disk partitions, and much more. Running it ad-hoc is useful for verifying what Ansible can see:

```bash
ansible all -m setup
```

The output is verbose. Filter to a specific fact with `--filter`:

```bash
ansible all -m setup --args "filter=ansible_distribution*"
```

Example output:

```
web-01.example.com | SUCCESS => {
    "ansible_facts": {
        "ansible_distribution": "Ubuntu",
        "ansible_distribution_major_version": "24",
        "ansible_distribution_release": "noble",
        "ansible_distribution_version": "24.04"
    },
    "changed": false
}
```

### 5.4 Ad-Hoc Commands with -m command and -m shell

The `command` module runs a command directly — no shell features (no pipes, no redirects, no environment variable expansion):

```bash
ansible all -m command -a "uptime"
```

The `shell` module runs the command through `/bin/sh`, enabling shell features:

```bash
ansible all -m shell -a "echo $HOSTNAME && uptime"
```

Target a specific group instead of `all`:

```bash
ansible webservers -m command -a "df -h /"
```

Run as root using `--become`:

```bash
ansible all -m command -a "id" --become
```

---

## Best Practices

1. **Keep `ansible.cfg` in the project root and commit it to version control.** Ansible picks up the file in the current directory, so your settings travel with the project and every team member uses identical configuration without any extra setup steps.

2. **Use Ed25519 keys for Ansible SSH authentication, not RSA.** Ed25519 keys are shorter, faster to verify, and considered more secure than 2048-bit RSA. They are supported by all OpenSSH versions you are likely to encounter.

3. **Create a dedicated `ansible` service account on every managed node, separate from your personal user.** This makes it straightforward to audit which changes were made by automation versus a human operator, and lets you rotate Ansible's credentials independently.

4. **Never store SSH private keys or passwords directly in inventory files or playbooks.** Use `group_vars` files with appropriate filesystem permissions (`chmod 600`), and for secrets that must be checked into version control, use Ansible Vault (covered in Module 7).

5. **Use `ansible-inventory --graph` to validate inventory before running any playbook.** A typo in a group name or an indentation error in YAML can silently exclude hosts; the graph view makes the actual grouping visible at a glance.

6. **Disable `host_key_checking` only in controlled lab environments, never in production.** In production, manage `known_hosts` explicitly or use `StrictHostKeyChecking=accept-new` in your SSH config — this accepts new keys automatically but still alerts you if a known host's key changes (a potential sign of a man-in-the-middle attack).

7. **Prefer `ansible.builtin.command` over `ansible.builtin.shell` when you do not need shell features.** The `command` module does not invoke a shell, which avoids injection risks if any part of the argument string comes from a variable.

8. **Set `stdout_callback = yaml` in `ansible.cfg` for human-readable output.** The default output format can be hard to read on long runs; the `yaml` callback formats results cleanly and is easier to scan for failures.

9. **Always test `ansible all -m ping` after any infrastructure change** — adding a new host, rotating SSH keys, changing firewall rules — before assuming connectivity is intact. A minute of pinging saves hours of debugging mid-playbook.

10. **Run Ansible from a virtualenv in CI/CD pipelines.** Pinning the Ansible version in `requirements.txt` (`ansible==13.5.0`) ensures every pipeline run uses identical software, eliminating "it worked on my machine" version drift.

## Use Cases

**Scenario 1 — Rapidly provisioning identical lab VMs**
A developer creates five Ubuntu VMs for load testing and needs each one configured identically: same user accounts, same packages, same sysctl settings. Manually SSH-ing to five VMs and running the same sequence of commands is tedious and error-prone. After completing this module's setup — SSH keys deployed, `ansible.cfg` configured, inventory listing all five VMs — the developer can run `ansible all -m command -a "uname -r"` to verify all five are running the expected kernel in under five seconds, then proceed to write a playbook that applies the full configuration in a single command.

**Scenario 2 — Auditing the state of a fleet before a change window**
A sysadmin needs to know which servers in a 20-node inventory are running Ubuntu 22.04 versus 24.04 before scheduling OS upgrades. Rather than logging into each host, they run `ansible all -m setup --args "filter=ansible_distribution_version"` from the control node. Within seconds they have a per-host breakdown of OS versions without touching a single managed node manually.

**Scenario 3 — Onboarding a new team member's workstation as the control node**
A new engineer joins the infrastructure team. They need their laptop configured as an Ansible control node so they can run the team's playbooks. The team's project is already in a Git repository. The engineer clones the repo, installs Ansible via the PPA, generates an Ed25519 key pair, has the team lead add their public key to the managed nodes, and within 20 minutes they are running `ansible all -m ping` and seeing green. The fact that `ansible.cfg` and the inventory live in the repository means the engineer does not have to manually re-discover configuration choices.

**Scenario 4 — Verifying SSH connectivity after a cloud firewall rule change**
A platform engineer updates a security group rule in AWS to restrict SSH access to a new CIDR range. After applying the change, they want to immediately confirm which hosts Ansible can still reach and which are now unreachable. Running `ansible all -m ping` gives a clear per-host SUCCESS or UNREACHABLE result in seconds, faster and more comprehensive than spot-checking a sample of hosts manually.

## Hands-on Examples

### Example 1: Installing Ansible on Ubuntu 24.04 and Verifying the Installation

You have a fresh Ubuntu 24.04 VM and want to set it up as an Ansible control node.

1. Update the package index and install the prerequisites:

```bash
sudo apt update
sudo apt install software-properties-common -y
```

2. Add the official Ansible PPA:

```bash
sudo add-apt-repository --yes --update ppa:ansible/ansible
```

3. Install Ansible:

```bash
sudo apt install ansible -y
```

4. Verify the installation and review the output:

```bash
ansible --version
```

Expected output:

```
ansible [core 2.20.4]
  config file = None
  configured module search path = ['/home/ubuntu/.ansible/plugins/modules', '/usr/share/ansible/plugins/modules']
  ansible python module location = /usr/lib/python3/dist-packages/ansible
  ansible collection location = /home/ubuntu/.ansible/collections:/usr/share/ansible/collections
  executable location = /usr/bin/ansible
  python version = 3.12.3 (main, Apr  2 2024, 05:51:12) [GCC 13.2.0]
  jinja version = 3.1.4
  libyaml = True
```

5. Confirm `config file = None`. This tells you Ansible has not yet found a project-specific `ansible.cfg`. That is expected — you have not created one yet.

6. Check the executable path:

```bash
which ansible
# /usr/bin/ansible
```

---

### Example 2: Setting Up a Minimal Working Project with SSH Key Auth and a Successful Ping

You have Ansible installed on the control node and a second Linux VM (`192.168.1.50`) available as a managed node. Your goal is a clean project layout, SSH key auth, and a verified `ansible all -m ping`.

**On the control node:**

1. Generate the Ansible SSH key pair (press Enter twice when prompted for a passphrase):

```bash
ssh-keygen -t ed25519 -C "ansible-control-key" -f ~/.ssh/ansible_ed25519
```

2. Create the project directory structure:

```bash
mkdir -p ~/my-ansible-project/inventory/group_vars
cd ~/my-ansible-project
```

3. Create `ansible.cfg`:

```bash
cat > ansible.cfg << 'EOF'
[defaults]
inventory = inventory/hosts.ini
remote_user = ansible
private_key_file = ~/.ssh/ansible_ed25519
host_key_checking = False
stdout_callback = yaml

[privilege_escalation]
become = true
become_method = sudo
become_user = root
EOF
```

4. Create the inventory file with two groups:

```bash
cat > inventory/hosts.ini << 'EOF'
[webservers]
web-01 ansible_host=192.168.1.50

[databases]
db-01 ansible_host=192.168.1.51

[lab:children]
webservers
databases
EOF
```

**On each managed node** (log in via SSH with your regular credentials):

5. Create the `ansible` service account and configure passwordless sudo:

```bash
sudo useradd -m -s /bin/bash ansible
echo "ansible ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/ansible
sudo chmod 440 /etc/sudoers.d/ansible
sudo mkdir -p /home/ansible/.ssh
sudo chmod 700 /home/ansible/.ssh
sudo chown ansible:ansible /home/ansible/.ssh
```

6. Copy your public key to the managed node. Back on the **control node**:

```bash
ssh-copy-id -i ~/.ssh/ansible_ed25519.pub ansible@192.168.1.50
ssh-copy-id -i ~/.ssh/ansible_ed25519.pub ansible@192.168.1.51
```

**Back on the control node, from the project directory:**

7. Verify the inventory is parsed correctly:

```bash
ansible-inventory --graph
```

Expected output:

```
@all:
  |--@ungrouped:
  |--@webservers:
  |  |--web-01
  |--@databases:
  |  |--db-01
  |--@lab:
  |  |--@webservers:
  |  |--@databases:
```

8. Run the ping check:

```bash
ansible all -m ping
```

Expected output:

```
web-01 | SUCCESS => {
    "ansible_facts": {
        "discovered_interpreter_python": "/usr/bin/python3"
    },
    "changed": false,
    "ping": "pong"
}
db-01 | SUCCESS => {
    "ansible_facts": {
        "discovered_interpreter_python": "/usr/bin/python3"
    },
    "changed": false,
    "ping": "pong"
}
```

Both hosts return `pong`. Your control node is fully configured.

---

### Example 3: Running a First Ad-Hoc Command to Install a Package on a Managed Node

With connectivity confirmed, you want to install `htop` on all web servers without writing a playbook yet.

1. First confirm the package is not installed (the `command` module does not use sudo by default — add `--become` for root actions):

```bash
ansible webservers -m command -a "which htop"
```

Expected output (package not found):

```
web-01 | FAILED! => {
    "changed": false,
    "cmd": ["which", "htop"],
    "rc": 1,
    "stderr": "",
    "stdout": "",
    "stdout_lines": []
}
```

A non-zero return code means `which htop` found nothing — the package is not installed, which is what we expected.

2. Install `htop` using the `ansible.builtin.apt` module with `--become` for privilege escalation:

```bash
ansible webservers -m ansible.builtin.apt -a "name=htop state=present" --become
```

Expected output (first run — package installed):

```
web-01 | CHANGED => {
    "ansible_facts": {
        "discovered_interpreter_python": "/usr/bin/python3"
    },
    "cache_update_time": 1712345678,
    "cache_updated": false,
    "changed": true,
    ...
}
```

3. Run the same command again to see idempotency in action:

```bash
ansible webservers -m ansible.builtin.apt -a "name=htop state=present" --become
```

Expected output (second run — already installed, no change):

```
web-01 | SUCCESS => {
    "ansible_facts": {
        "discovered_interpreter_python": "/usr/bin/python3"
    },
    "changed": false
}
```

Notice `"changed": false` — Ansible detected that `htop` is already in the desired state and did nothing. This is idempotency in practice.

4. Verify the installation on the managed node:

```bash
ansible webservers -m command -a "htop --version"
```

Expected output:

```
web-01 | SUCCESS => {
    "changed": false,
    "cmd": ["htop", "--version"],
    "rc": 0,
    "stdout": "htop 3.3.0",
    "stdout_lines": ["htop 3.3.0"]
}
```

---

## Common Pitfalls

**Pitfall 1 — Running Ansible from the wrong directory**

`ansible.cfg` is loaded from the current working directory. If you `cd` to a different directory and run `ansible`, your project's configuration is silently ignored and Ansible falls back to `/etc/ansible/ansible.cfg` or no config at all, resulting in "inventory not found" errors or connections using the wrong user.

Incorrect:
```bash
cd /tmp
ansible all -m ping
# [WARNING]: No inventory was parsed, only implicit localhost is available
```

Correct:
```bash
cd ~/my-ansible-project
ansible all -m ping
```

---

**Pitfall 2 — SSH host key prompt blocking automation**

When Ansible tries to connect to a host it has never seen before, SSH asks interactively: `Are you sure you want to continue connecting (yes/no/[fingerprint])?` Because Ansible cannot answer this prompt, the connection times out and the host is marked UNREACHABLE.

Incorrect (`host_key_checking` left at default `True` with new hosts in inventory):
```
192.168.1.50 | UNREACHABLE! => {
    "msg": "Failed to connect to the host via ssh: Host key verification failed.",
    "unreachable": true
}
```

Correct — set in `ansible.cfg` for lab environments:
```ini
[defaults]
host_key_checking = False
```

Or pre-populate `known_hosts` by running `ssh-keyscan` once before using Ansible:
```bash
ssh-keyscan -H 192.168.1.50 >> ~/.ssh/known_hosts
```

---

**Pitfall 3 — Wrong file permissions on SSH private key**

SSH refuses to use a private key if it is readable by other users. Ansible inherits this restriction.

Incorrect (key has too-open permissions):
```bash
ls -la ~/.ssh/ansible_ed25519
# -rw-r--r-- 1 user user 411 ...  ← world-readable!
```
Result: `WARNING: UNPROTECTED PRIVATE KEY FILE! Permissions 0644 are too open.`

Correct:
```bash
chmod 600 ~/.ssh/ansible_ed25519
```

---

**Pitfall 4 — Forgetting `--become` for tasks that need root**

The `apt`, `dnf`, and `service` modules require root privileges. Without `--become` in an ad-hoc command (or `become: true` in a playbook), Ansible connects as the `ansible` user and the module fails with a permission error.

Incorrect:
```bash
ansible all -m ansible.builtin.apt -a "name=nginx state=present"
# FAILED! => {"msg": "Failed to lock apt for exclusive operation: ... permission denied"}
```

Correct:
```bash
ansible all -m ansible.builtin.apt -a "name=nginx state=present" --become
```

---

**Pitfall 5 — Using `/usr/bin/python` instead of `python3` on modern systems**

Some older Ansible tutorials reference `/usr/bin/python`. Many modern distributions (Ubuntu 22.04+, Fedora 34+) no longer provide `/usr/bin/python` as a symlink — only `/usr/bin/python3`. Ansible auto-discovers the interpreter, but if you hard-code the path in inventory you may get a "No such file or directory" error.

Incorrect (`inventory/hosts.ini`):
```ini
web-01 ansible_host=192.168.1.50 ansible_python_interpreter=/usr/bin/python
```

Correct (let Ansible discover it, or specify python3 explicitly):
```ini
web-01 ansible_host=192.168.1.50 ansible_python_interpreter=/usr/bin/python3
```

Or rely on auto-discovery (the default and recommended approach):
```ini
web-01 ansible_host=192.168.1.50
```

---

**Pitfall 6 — YAML indentation errors in inventory or playbooks**

YAML uses indentation to express structure. Mixing tabs and spaces, or using inconsistent indentation levels, causes silent parsing failures or unexpected grouping.

Incorrect (tab character instead of spaces):
```yaml
all:
  children:
	webservers:        # ← tab character here
      hosts:
        web-01:
```

Correct (two-space indentation, spaces only):
```yaml
all:
  children:
    webservers:
      hosts:
        web-01:
```

Use a YAML linter (`pip install yamllint`) and configure your editor to show whitespace characters and prefer spaces over tabs.

---

**Pitfall 7 — Storing secrets in plain text in inventory or `ansible.cfg`**

Putting passwords, API keys, or other sensitive values directly in `hosts.ini` or `group_vars` YAML files and then committing those files to a Git repository exposes your credentials to anyone who can access the repository.

Incorrect:
```ini
# inventory/hosts.ini
db-01 ansible_user=dbadmin ansible_password=SuperSecret123
```

Correct: Use Ansible Vault to encrypt sensitive values. Vault is covered in Module 7. As an immediate alternative, use SSH key authentication (which requires no password in inventory) and `become` with passwordless sudo.

---

**Pitfall 8 — Running `ansible` with no `ansible.cfg` and relying on `/etc/ansible/hosts`**

If you run Ansible without any `ansible.cfg` and without specifying `-i`, Ansible falls back to `/etc/ansible/hosts`. This file is usually empty or contains only comments. New users are confused when `ansible all -m ping` returns "No inventory was parsed" even though they clearly have hosts to manage.

Always specify either a project-local `ansible.cfg` with an `inventory` setting, or pass `-i inventory/hosts.ini` explicitly on the command line.

---

## Summary

- Ansible is an agentless, push-based automation tool that connects to managed nodes over SSH, uploads small Python scripts, executes them, and reports results — no daemon or software installation is required on the managed nodes.
- The control node is the only machine where Ansible is installed; it can be your laptop, a CI server, or a jump host. Install Ansible via the distro package manager (PPA on Ubuntu, EPEL + dnf on RHEL-based, pacman on Arch) or via `pip install ansible` in a virtualenv for version control.
- Every Ansible project should have an `ansible.cfg` in the project root (so it travels with the repository), an `inventory/` directory with a static INI or YAML hosts file and `group_vars`/`host_vars` directories for variables, and a `playbooks/` directory for YAML playbooks.
- SSH key authentication is the standard connection method; generate a dedicated Ed25519 key pair for Ansible, copy the public key to every managed node's `ansible` service account via `ssh-copy-id`, and configure the key path in `ansible.cfg` or `group_vars/all.yml`.
- Validate your setup end-to-end with `ansible-inventory --graph` (confirms inventory parsing), `ansible all -m ping` (confirms SSH connectivity and Python availability), and `ansible all -m setup` (confirms full fact gathering works) before writing any playbooks.

## Further Reading

- [Installing Ansible — Ansible Community Documentation](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html) — The official installation guide covering control node requirements, Python version compatibility, and all supported installation methods including pip.
- [How to Build Your Inventory — Ansible Community Documentation](https://docs.ansible.com/projects/ansible/latest/inventory_guide/intro_inventory.html) — The authoritative reference for INI and YAML inventory formats, group hierarchies, group variables, host variables, and patterns for targeting subsets of hosts.
- [Ansible Configuration Settings — Ansible Community Documentation](https://docs.ansible.com/projects/ansible/latest/reference_appendices/config.html) — A full reference of every `ansible.cfg` setting, their default values, and the environment variables that override them.
- [Connection Methods and Details — Ansible Community Documentation](https://docs.ansible.com/projects/ansible/latest/inventory_guide/connection_details.html) — Covers SSH connection options including `ansible_user`, `ansible_ssh_private_key_file`, `ansible_port`, and how connection variables interact with `ansible.cfg` and SSH config.
- [Introduction to Ad Hoc Commands — Ansible Community Documentation](https://docs.ansible.com/projects/ansible/latest/command_guide/intro_adhoc.html) — Explains the `ansible` CLI syntax, module selection with `-m`, module arguments with `-a`, privilege escalation with `--become`, and practical examples for package management, file operations, and service control.
- [Managing Windows Hosts with Ansible — Ansible Community Documentation](https://docs.ansible.com/projects/ansible/latest/os_guide/intro_windows.html) — The official guide for Windows managed nodes, covering WinRM setup, authentication methods, and the differences from Linux management.
- [Sample Ansible Setup — Ansible Community Documentation](https://docs.ansible.com/projects/ansible/latest/tips_tricks/sample_setup.html) — A reference project layout from the Ansible project itself, showing how to organize inventories, group variables, playbooks, and roles at scale.
- [Ansible vs Ansible-Core — ansiblepilot.com](https://www.ansiblepilot.com/articles/ansible-terminology-ansible-vs-ansible-core-packages) — A clear explanation of the `ansible` vs `ansible-core` package distinction, what each includes, and when to choose one over the other.
