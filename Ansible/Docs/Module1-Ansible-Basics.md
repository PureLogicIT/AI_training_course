# Module 1: Ansible Basics
> Subject: Ansible | Difficulty: Beginner | Estimated Time: 150 minutes

## Objective

After completing this module, you will be able to explain what Ansible is and why its agentless architecture makes it well suited for managing AI server infrastructure; install Ansible on a control node using both `pip` and `apt`; write INI and YAML inventory files that organise hosts into groups with per-host variables; run ad-hoc commands using the `ansible` CLI with the `ping`, `shell`, `copy`, and `apt` modules; configure passwordless SSH authentication so Ansible can reach remote hosts without manual intervention; write a complete playbook in YAML that uses plays, tasks, the `become` directive, and the core modules (`ping`, `command`, `shell`, `copy`, `file`, `apt`, `service`, `user`); execute playbooks with `ansible-playbook`; use `--check` mode to preview changes before applying them; control output verbosity with `-v` through `-vvv`; and set project-wide defaults in `ansible.cfg`.

## Prerequisites

- Basic Linux command-line proficiency: navigating the filesystem, editing text files with `nano` or `vim`, understanding file permissions
- Familiarity with SSH (you should know what a key pair is and how `ssh user@host` works)
- Python 3.9 or later installed on the machine that will act as the Ansible control node (verify with `python3 --version`)
- At least one Linux host to manage — this module frames that host as an AI server or GPU box (Ubuntu 22.04 or 24.04 recommended); it can be a VM, a cloud instance, or a physical machine
- No prior Ansible or infrastructure automation experience is assumed

## Key Concepts

### What Ansible Is and Why It Replaces Manual Setup

Ansible is an open-source IT automation platform that lets you define the desired state of your infrastructure in plain YAML files called *playbooks*, then apply those definitions across any number of remote machines simultaneously. Rather than SSH-ing into each server and running commands by hand, you describe what should be true — "Python 3 should be installed," "the `ai-worker` user should exist," "the inference service should be running and enabled" — and Ansible makes it so.

For AI server management this matters immediately. A single GPU box may need dozens of packages, specific system settings (`vm.overcommit_memory`, `nofile` limits), a dedicated service account, model checkpoints on a particular path, and a systemd unit that starts the inference daemon at boot. Doing all of this by hand every time you provision a new box is slow, error-prone, and impossible to audit. Encoding it as Ansible playbooks means every server is provisioned identically in minutes, every change is tracked in version control, and you can rebuild from scratch if a box is lost.

```
Manual workflow (fragile)          Ansible workflow (repeatable)
──────────────────────────         ─────────────────────────────
ssh gpu-box-1                      ansible-playbook setup-ai-server.yml
apt install python3 git curl  →
useradd ai-worker
systemctl enable inference
... (repeat for every box)         Done. All 10 boxes configured.
```

Ansible also serves as living documentation. When a new team member joins, reading `setup-ai-server.yml` tells them exactly what state every server should be in — something no runbook document ever stays current enough to provide.

### Agentless Architecture

The defining architectural choice in Ansible is that it requires no software to be permanently installed on the machines it manages. Most configuration management tools (Chef, Puppet, SaltStack) require a *daemon* or *agent* running on every managed node — a process that must itself be installed, kept up to date, secured, and monitored. Ansible eliminates this entirely.

When Ansible runs a task, it connects to the target host over standard SSH, copies a small Python module to a temporary directory on the remote host, executes it, collects the result, and then removes the temporary file. The entire operation leaves no persistent footprint. The only requirement on managed nodes is that Python 3 is available (which it is by default on every modern Ubuntu and RHEL system) and that an SSH server is running — both of which are true out of the box.

```
Control Node                          Managed Node (AI server)
──────────────                        ────────────────────────
ansible-playbook                      No Ansible agent
     │                                No daemon
     │  SSH connection                ┌──────────────────────┐
     ├──────────────────────────────► │  sshd (always there) │
     │  Upload temp Python module     │  python3 (built-in)  │
     │  Execute                       │  /tmp/ansible_xyz/   │
     │  Collect JSON result           │    (created, run,    │
     │  Delete temp files             │     deleted)         │
     ◄──────────────────────────────  └──────────────────────┘
```

This agentless design has practical consequences: you can run Ansible against a brand-new cloud instance the moment it is reachable via SSH, without a bootstrap step. For AI infrastructure this means you can spin up a new GPU node, add it to your inventory, and have it fully configured with a single command.

### Installing Ansible on the Control Node

Ansible runs on the *control node* — the machine from which you issue commands. This is typically your laptop, a jump host, or a CI server, not the GPU boxes themselves. Ansible is a Python package; there are two common installation methods.

**Method 1 — pip (recommended for most users):**

```bash
# Create an isolated virtual environment so Ansible does not conflict
# with other Python packages on your system
python3 -m venv ~/.venv/ansible
source ~/.venv/ansible/bin/activate

# Install the full Ansible package (includes all bundled modules)
pip install ansible

# Verify the installation
ansible --version
```

Expected output (version numbers will vary; 2.17.x was current stable as of mid-2025):
```
ansible [core 2.17.x]
  config file = None
  configured module search path = [...]
  ansible python module location = /home/user/.venv/ansible/lib/python3.x/...
  ansible collection location = /home/user/.ansible/collections:...
  executable location = /home/user/.venv/ansible/bin/ansible
  python version = 3.x.x (...)
  jinja version = 3.x.x
  libyaml = True
```

**Method 2 — apt (Ubuntu/Debian system package):**

```bash
sudo apt update
sudo apt install ansible -y

ansible --version
```

The `pip` method is generally preferred for production and learning because it gives you the latest stable release and keeps Ansible isolated from system Python packages. The `apt` package version may lag behind the latest upstream release by several months.

### Inventory Files: Telling Ansible What to Manage

An *inventory* is the list of hosts Ansible knows about. Before Ansible can do anything, you must tell it which machines exist and how to reach them. Inventories can be written in INI format (simple, great for beginners) or YAML format (more explicit, better for complex setups).

**INI inventory (`inventory.ini`):**

```ini
# Standalone host
gpu-box-01 ansible_host=192.168.1.50 ansible_user=ubuntu

# A group of AI servers
[ai_servers]
gpu-box-01 ansible_host=192.168.1.50 ansible_user=ubuntu
gpu-box-02 ansible_host=192.168.1.51 ansible_user=ubuntu

# A group of CPU-only inference nodes
[inference_nodes]
inf-01 ansible_host=192.168.1.60 ansible_user=ubuntu
inf-02 ansible_host=192.168.1.61 ansible_user=ubuntu

# A meta-group that contains both groups above
[ml_fleet:children]
ai_servers
inference_nodes

# Variables that apply to every host in ai_servers
[ai_servers:vars]
ansible_python_interpreter=/usr/bin/python3
```

**YAML inventory (`inventory.yml`):**

```yaml
all:
  children:
    ai_servers:
      hosts:
        gpu-box-01:
          ansible_host: 192.168.1.50
          ansible_user: ubuntu
        gpu-box-02:
          ansible_host: 192.168.1.51
          ansible_user: ubuntu
      vars:
        ansible_python_interpreter: /usr/bin/python3
    inference_nodes:
      hosts:
        inf-01:
          ansible_host: 192.168.1.60
          ansible_user: ubuntu
        inf-02:
          ansible_host: 192.168.1.61
          ansible_user: ubuntu
  vars:
    ansible_ssh_private_key_file: ~/.ssh/ai_infra_key
```

The built-in `all` group always includes every host. The `ungrouped` implicit group contains hosts that belong to no explicit group. You can also place per-host variable files in a directory called `host_vars/` (one file per host, named after the host) and group variable files in `group_vars/` (one file per group name) — Ansible automatically merges those files with the inventory at runtime.

### SSH Key Setup for Ansible

Because Ansible communicates over SSH, it must be able to authenticate to managed nodes without prompting for a password. The standard approach is public-key authentication.

**Step 1 — Generate a dedicated key pair on the control node:**

```bash
ssh-keygen -t ed25519 -C "ansible-control" -f ~/.ssh/ansible_ed25519
# When prompted for a passphrase, press Enter twice for no passphrase
# (or use ssh-agent if your security policy requires a passphrase)
```

Expected output:
```
Generating public/private ed25519 key pair.
Your identification has been saved in /home/user/.ssh/ansible_ed25519
Your public key has been saved in /home/user/.ssh/ansible_ed25519.pub
The key fingerprint is:
SHA256:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx ansible-control
```

**Step 2 — Copy the public key to each managed node:**

```bash
ssh-copy-id -i ~/.ssh/ansible_ed25519.pub ubuntu@192.168.1.50
```

If `ssh-copy-id` is unavailable, you can copy the public key manually:

```bash
# On the control node, display the public key
cat ~/.ssh/ansible_ed25519.pub

# On the managed node (logged in manually), append it to authorized_keys
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "paste-public-key-content-here" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

**Step 3 — Test that SSH works without a password:**

```bash
ssh -i ~/.ssh/ansible_ed25519 ubuntu@192.168.1.50 "echo SSH works"
```

Expected output:
```
SSH works
```

**Step 4 — Reference the key in your inventory or `ansible.cfg`:**

```ini
# In inventory.ini
gpu-box-01 ansible_host=192.168.1.50 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/ansible_ed25519
```

### Ad-Hoc Commands

Ad-hoc commands let you run a single Ansible task against one or more hosts without writing a playbook. They are ideal for quick checks, one-time operations, and verifying connectivity. The syntax is:

```
ansible <host-pattern> -i <inventory> -m <module> [-a "<module-arguments>"]
```

**Connectivity check with the `ping` module:**

```bash
ansible ai_servers -i inventory.ini -m ping
```

Expected output:
```
gpu-box-01 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
gpu-box-02 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

Note: The Ansible `ping` module does not send an ICMP packet. It opens an SSH connection, imports a small Python module on the remote host, and returns `pong`. It is a full connectivity and authentication test.

**Run a shell command with the `shell` module:**

```bash
ansible ai_servers -i inventory.ini -m shell -a "nvidia-smi --query-gpu=name --format=csv,noheader"
```

**Install a package with the `apt` module (requires `--become` for sudo):**

```bash
ansible ai_servers -i inventory.ini -m apt -a "name=curl state=present update_cache=yes" --become
```

**Copy a file to all managed nodes:**

```bash
ansible ai_servers -i inventory.ini -m copy \
  -a "src=./configs/limits.conf dest=/etc/security/limits.d/ai.conf mode=0644" \
  --become
```

Common modules available for ad-hoc use:

| Module | Purpose |
|---|---|
| `ping` | Test SSH connectivity and Python availability |
| `command` | Run a command (no shell features like pipes or redirects) |
| `shell` | Run a command through `/bin/sh` (supports pipes, redirects, globs) |
| `copy` | Upload a file from the control node to the managed node |
| `apt` | Manage packages on Debian/Ubuntu systems |
| `file` | Manage files, directories, symlinks, and permissions |
| `service` | Start, stop, restart, enable, or disable system services |
| `user` | Create, modify, or remove OS user accounts |

### Your First Playbook

A *playbook* is a YAML file that describes one or more *plays*. Each play targets a group of hosts and contains an ordered list of *tasks*. Each task calls an Ansible module with specific arguments. Playbooks are idempotent by design: running the same playbook twice should produce the same end state, not duplicate work.

The anatomy of a playbook:

```
playbook.yml
├── play 1
│   ├── hosts: ai_servers        # which inventory group to target
│   ├── become: true             # run tasks with sudo
│   └── tasks:
│       ├── task 1: ping
│       ├── task 2: apt (install python3)
│       └── task 3: user (create ai-worker account)
└── play 2
    ├── hosts: inference_nodes
    └── tasks:
        └── task 1: service (start inference daemon)
```

A complete minimal playbook that provisions an AI server:

```yaml
---
- name: Provision AI server baseline
  hosts: ai_servers
  become: true

  tasks:
    - name: Verify Ansible connectivity
      ansible.builtin.ping:

    - name: Update apt package cache
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600

    - name: Install AI server baseline packages
      ansible.builtin.apt:
        name:
          - python3
          - python3-pip
          - python3-venv
          - git
          - curl
          - htop
          - tmux
        state: present

    - name: Create ai-worker service account
      ansible.builtin.user:
        name: ai-worker
        comment: Service account for AI daemons
        shell: /bin/bash
        create_home: true
        system: true

    - name: Ensure /opt/ai directory exists with correct ownership
      ansible.builtin.file:
        path: /opt/ai
        state: directory
        owner: ai-worker
        group: ai-worker
        mode: "0755"
```

Key YAML syntax rules for playbooks:
- The file starts with `---` (document start marker)
- A play is a list item starting with `-`
- `name:` fields are optional but strongly recommended — they appear in output and serve as documentation
- Module arguments are a dictionary nested under the module name
- Strings containing special YAML characters (`:`, `{`, `}`) must be quoted

### Running Playbooks and Controlling Output

**Execute a playbook:**

```bash
ansible-playbook -i inventory.ini setup-ai-server.yml
```

**Dry-run with `--check` mode:**

```bash
ansible-playbook -i inventory.ini setup-ai-server.yml --check
```

In `--check` mode, Ansible evaluates every task and reports what *would* change without making any actual modifications. This is invaluable before running a playbook against production servers for the first time. Note that some modules (particularly `command` and `shell`) cannot determine what would happen without running, so they always report `skipped` or `ok` in check mode even when they would make changes.

**Control verbosity:**

```bash
# Default output — task names and pass/fail status only
ansible-playbook -i inventory.ini setup-ai-server.yml

# -v: show module return values for changed/failed tasks
ansible-playbook -i inventory.ini setup-ai-server.yml -v

# -vv: show task invocation details (what arguments were passed)
ansible-playbook -i inventory.ini setup-ai-server.yml -vv

# -vvv: show SSH connection details and raw module output (debug level)
ansible-playbook -i inventory.ini setup-ai-server.yml -vvv
```

Use `-v` during normal development to understand what a task is doing. Use `-vvv` when a task is failing in an unexpected way and you need to see the raw SSH exchange.

**Limit execution to a subset of hosts:**

```bash
# Run only against gpu-box-01, even though the play targets ai_servers
ansible-playbook -i inventory.ini setup-ai-server.yml --limit gpu-box-01
```

### ansible.cfg: Project Configuration File

`ansible.cfg` is an INI-format configuration file that sets defaults for all Ansible commands run from the same directory. Ansible searches for it in this order: the current directory (`./ansible.cfg`), `~/.ansible.cfg`, then `/etc/ansible/ansible.cfg`. A project-local `ansible.cfg` always wins.

A practical `ansible.cfg` for an AI infrastructure project:

```ini
[defaults]
# Path to the default inventory file
inventory = ./inventory.ini

# Disable host key checking (acceptable in trusted lab networks;
# review for production environments)
host_key_checking = False

# Default remote user
remote_user = ubuntu

# Default private key
private_key_file = ~/.ssh/ansible_ed25519

# Number of hosts to manage in parallel
forks = 10

# Log Ansible output to a file (useful for auditing)
log_path = ./ansible.log

# Suppress deprecation warnings for cleaner output while learning
deprecation_warnings = False

[privilege_escalation]
# Always use sudo for privilege escalation
become = True
become_method = sudo
become_user = root
```

With `ansible.cfg` in place, the long command:

```bash
ansible-playbook -i inventory.ini --private-key ~/.ssh/ansible_ed25519 -u ubuntu setup-ai-server.yml
```

becomes simply:

```bash
ansible-playbook setup-ai-server.yml
```

## Best Practices

1. **Always write playbook tasks in fully qualified collection name (FQCN) form, such as `ansible.builtin.apt` instead of just `apt`.** This prevents ambiguity when multiple collections provide modules with the same short name, and makes it immediately clear which module is being used.

2. **Set `host_key_checking = False` only in trusted lab environments, never in production.** Host key checking exists to detect man-in-the-middle attacks; disabling it in production means a compromised DNS entry or ARP spoofing attack could silently redirect Ansible commands to a malicious host.

3. **Run `ansible-playbook --check` before every playbook execution against production hosts.** Dry-run mode catches logical errors — tasks that would unexpectedly overwrite files or restart services — without any impact to running systems.

4. **Use named tasks for every single task in a playbook.** The `name:` field is not syntactically required, but unnamed tasks produce output like `TASK [apt]` which is useless for debugging; a name like `TASK [Install AI server baseline packages]` is immediately meaningful in logs and CI output.

5. **Store your inventory, playbooks, and `ansible.cfg` in a version-control repository from the first day.** Ansible playbooks are the source of truth for your infrastructure state; without version control, you cannot audit what changed, roll back a bad change, or collaborate with teammates.

6. **Never hard-code passwords or API keys in inventory files or playbooks.** Use `ansible-vault encrypt_string` to store secrets encrypted at rest, or reference environment variables with `"{{ lookup('env', 'MY_SECRET') }}"`. Committing plaintext credentials to a repository is a critical security failure.

7. **Pin the Ansible version in your `requirements.txt` or CI configuration.** Ansible releases regularly change module behaviour and default values; an unpinned upgrade can silently break playbooks that have been running for months.

8. **Use the `apt` module with `update_cache: true` and `cache_valid_time: 3600` together.** Running `update_cache: true` alone refreshes the cache on every playbook run, adding seconds of latency per host; `cache_valid_time` skips the refresh if the cache is newer than the specified number of seconds, making repeated runs faster.

9. **Use `become: true` at the play level only when most tasks in the play require privilege elevation; use it at the task level when only a few tasks need it.** Applying `become` more narrowly reduces the window of elevated privilege and makes the playbook's intent clearer to readers.

10. **Test playbooks for idempotency by running them twice and verifying that the second run reports zero `changed` tasks.** If the second run changes anything, the playbook is not idempotent, which means running it in CI or repeatedly in production will produce unpredictable results.

## Use Cases

### Use Case 1: Provisioning a New GPU Server from Zero

A machine learning team acquires a new GPU server for model training. It has a fresh Ubuntu 24.04 install and nothing else. A junior engineer needs to replicate the exact same package set, user accounts, and directory structure as the existing fleet.

- **Problem:** Without automation, the engineer must manually follow a multi-page runbook, risk missing steps, and produce a subtly different environment from the other servers — which will cause "it works on gpu-box-01 but not gpu-box-03" problems later.
- **Concepts applied:** Inventory file (add the new host to `[ai_servers]`), `ansible.builtin.apt` to install all required packages, `ansible.builtin.user` to create the `ai-worker` service account, `ansible.builtin.file` to create and permission the `/opt/ai` directory tree, `ansible-playbook` to execute.
- **Expected outcome:** The engineer adds the new host to `inventory.ini`, runs `ansible-playbook setup-ai-server.yml --limit gpu-box-04`, and within minutes the new server is in an identical state to every other server in the fleet.

### Use Case 2: Verifying the Health of the Entire AI Fleet at Once

An operations engineer wants to confirm that all twelve servers in the `ml_fleet` group are reachable, running the correct Python version, and have the inference service active before a scheduled training run begins.

- **Problem:** SSH-ing into twelve servers one at a time to check these three things takes ten minutes and is easily forgotten when under deadline pressure.
- **Concepts applied:** Ad-hoc `ansible.builtin.ping` across the `ml_fleet` group, ad-hoc `shell` module to run `python3 --version`, ad-hoc `service` module with `state: started` to confirm service status; verbosity flag `-v` to see return values.
- **Expected outcome:** A single `ansible ml_fleet -m ping` command returns success or failure for all twelve hosts in parallel within seconds, immediately identifying any unreachable node.

### Use Case 3: Rolling Out a Configuration Change Safely

The team needs to update `/etc/security/limits.conf` on all GPU servers to raise the `nofile` limit for the `ai-worker` user before a large training job that opens thousands of file descriptors.

- **Problem:** The change must be applied consistently to all servers, and the engineer wants to preview what will change before touching production.
- **Concepts applied:** `ansible.builtin.copy` module to deploy the updated limits file, `--check` mode to preview which hosts need the change, `--limit` to apply incrementally to a subset first, verbosity `-v` to confirm the exact file content written.
- **Expected outcome:** The engineer first runs with `--check`, confirms only the expected file would be modified, then runs without `--check` and all servers receive the updated limits file with the correct permissions.

### Use Case 4: Creating a Service Account for AI Daemons Across the Fleet

A new policy requires that all inference daemons run under a dedicated `ai-worker` OS user with a home directory at `/home/ai-worker`, no login shell for security, and membership in the `docker` group so it can manage containers.

- **Problem:** Manually creating a consistent user account across a fleet of servers is tedious and produces inconsistencies (wrong UID, wrong group memberships) that break service startup scripts.
- **Concepts applied:** `ansible.builtin.user` module with `name`, `comment`, `shell`, `groups`, `append`, `create_home`, and `system` parameters; `become: true` for the privilege needed to create system users.
- **Expected outcome:** One playbook task creates the user identically on every server in the inventory, with subsequent runs being idempotent — if the user already exists with the correct attributes, Ansible reports `ok` and makes no changes.

## Hands-on Examples

### Example 1: Install Ansible and Ping Your AI Server

You will install Ansible on your control node, create a minimal inventory pointing at an AI server, configure SSH key authentication, and confirm that Ansible can reach the server.

1. Create a Python virtual environment and install Ansible.

```bash
python3 -m venv ~/.venv/ansible
source ~/.venv/ansible/bin/activate
pip install ansible
ansible --version
```

Expected output (abbreviated):
```
ansible [core 2.17.x]
  config file = None
  ...
  python version = 3.x.x
```

2. Generate an SSH key pair dedicated to Ansible.

```bash
ssh-keygen -t ed25519 -C "ansible-control" -f ~/.ssh/ansible_ed25519
# Press Enter twice to skip the passphrase
```

3. Copy the public key to the AI server (replace `192.168.1.50` with your server's IP and `ubuntu` with your remote username).

```bash
ssh-copy-id -i ~/.ssh/ansible_ed25519.pub ubuntu@192.168.1.50
```

Expected output:
```
Number of key(s) added: 1

Now try logging into the machine, with:   "ssh 'ubuntu@192.168.1.50'"
and check to make sure that only the key(s) you wanted were added.
```

4. Create a project directory and a minimal inventory file.

```bash
mkdir ~/ansible-ai && cd ~/ansible-ai

cat > inventory.ini << 'EOF'
[ai_servers]
gpu-box-01 ansible_host=192.168.1.50 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/ansible_ed25519
EOF
```

5. Create an `ansible.cfg` to suppress host key prompts.

```bash
cat > ansible.cfg << 'EOF'
[defaults]
inventory = ./inventory.ini
host_key_checking = False
EOF
```

6. Run the `ping` module against the `ai_servers` group.

```bash
ansible ai_servers -m ping
```

Expected output:
```
gpu-box-01 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

7. Gather quick facts about the server using the `shell` module.

```bash
ansible ai_servers -m shell -a "uname -a && free -h"
```

Expected output (values will differ based on your server):
```
gpu-box-01 | CHANGED | rc=0 >>
Linux gpu-box-01 6.8.0-51-generic #52-Ubuntu SMP PREEMPT_DYNAMIC x86_64 x86_64 x86_64 GNU/Linux
               total        used        free      shared  buff/cache   available
Mem:            62Gi       4.2Gi        55Gi        12Mi       2.8Gi        57Gi
Swap:          2.0Gi          0B       2.0Gi
```

---

### Example 2: Install AI Baseline Packages with an Ad-Hoc Command

You will use ad-hoc commands to update the apt cache and install the core packages that every AI server needs: `python3`, `python3-pip`, `git`, and `curl`.

1. First, use `--check` mode to preview what the apt module would do.

```bash
ansible ai_servers -m ansible.builtin.apt \
  -a "name=git state=present update_cache=yes" \
  --become --check
```

Expected output:
```
gpu-box-01 | CHANGED => {
    "changed": true,
    ...
}
```
(If git is already installed, you will see `"changed": false` instead.)

2. Apply the change for real (remove `--check`).

```bash
ansible ai_servers -m ansible.builtin.apt \
  -a "name=git state=present update_cache=yes" \
  --become
```

Expected output:
```
gpu-box-01 | CHANGED => {
    "changed": true,
    "stderr": "",
    "stderr_lines": [],
    ...
}
```

3. Install multiple packages at once using a comma-separated list in the `name` argument.

```bash
ansible ai_servers -m ansible.builtin.apt \
  -a "name=python3,python3-pip,python3-venv,curl,htop state=present" \
  --become
```

4. Verify the installations.

```bash
ansible ai_servers -m shell -a "python3 --version && git --version && curl --version | head -1"
```

Expected output:
```
gpu-box-01 | CHANGED | rc=0 >>
Python 3.12.3
git version 2.43.0
curl 8.5.0 (x86_64-pc-linux-gnu) libcurl/8.5.0 OpenSSL/3.0.13
```

---

### Example 3: Write and Run Your First Playbook

You will write a complete playbook that creates the `ai-worker` service account and ensures the `/opt/ai` directory exists with the correct ownership. Then you will run it in check mode first, followed by the real run.

1. In your `~/ansible-ai` directory, create `setup-ai-server.yml`.

```yaml
---
- name: Provision AI server baseline
  hosts: ai_servers
  become: true

  tasks:
    - name: Verify Ansible connectivity
      ansible.builtin.ping:

    - name: Update apt package cache
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600

    - name: Install AI server baseline packages
      ansible.builtin.apt:
        name:
          - python3
          - python3-pip
          - python3-venv
          - git
          - curl
          - htop
          - tmux
        state: present

    - name: Create ai-worker service account
      ansible.builtin.user:
        name: ai-worker
        comment: Service account for AI daemons
        shell: /usr/sbin/nologin
        create_home: true
        system: true

    - name: Ensure /opt/ai directory exists
      ansible.builtin.file:
        path: /opt/ai
        state: directory
        owner: ai-worker
        group: ai-worker
        mode: "0755"

    - name: Ensure /opt/ai/models directory exists
      ansible.builtin.file:
        path: /opt/ai/models
        state: directory
        owner: ai-worker
        group: ai-worker
        mode: "0755"
```

2. Run the playbook in check (dry-run) mode.

```bash
ansible-playbook setup-ai-server.yml --check
```

Expected output:
```
PLAY [Provision AI server baseline] *******************************************

TASK [Gathering Facts] ********************************************************
ok: [gpu-box-01]

TASK [Verify Ansible connectivity] ********************************************
ok: [gpu-box-01]

TASK [Update apt package cache] ***********************************************
changed: [gpu-box-01]

TASK [Install AI server baseline packages] ************************************
changed: [gpu-box-01]

TASK [Create ai-worker service account] ***************************************
changed: [gpu-box-01]

TASK [Ensure /opt/ai directory exists] ****************************************
changed: [gpu-box-01]

TASK [Ensure /opt/ai/models directory exists] *********************************
changed: [gpu-box-01]

PLAY RECAP ********************************************************************
gpu-box-01                 : ok=7    changed=5    unreachable=0    failed=0    skipped=0
```

3. Apply the playbook for real.

```bash
ansible-playbook setup-ai-server.yml
```

4. Run the playbook a second time to confirm idempotency — every task should report `ok`, not `changed`.

```bash
ansible-playbook setup-ai-server.yml
```

Expected output (PLAY RECAP line):
```
gpu-box-01                 : ok=7    changed=0    unreachable=0    failed=0    skipped=0
```

5. Use `-v` to confirm the `ai-worker` user was created with the correct attributes.

```bash
ansible-playbook setup-ai-server.yml -v
```

---

### Example 4: Use --check and Verbosity to Debug a Change

You will intentionally change a task's configuration, use `--check -vvv` to understand exactly what Ansible would do, and observe how verbosity levels differ.

1. Modify the `/opt/ai` directory task in `setup-ai-server.yml` to change the mode to `0700`.

```yaml
    - name: Ensure /opt/ai directory exists
      ansible.builtin.file:
        path: /opt/ai
        state: directory
        owner: ai-worker
        group: ai-worker
        mode: "0700"
```

2. Run with `--check` and standard verbosity.

```bash
ansible-playbook setup-ai-server.yml --check
```

Expected output for that task:
```
TASK [Ensure /opt/ai directory exists] ****************************************
changed: [gpu-box-01]
```

3. Run with `--check -v` to see what the module would change.

```bash
ansible-playbook setup-ai-server.yml --check -v
```

Expected output for that task (abbreviated):
```
TASK [Ensure /opt/ai directory exists] ****************************************
changed: [gpu-box-01] => {
    "changed": true,
    "diff": {
        "after": {
            "mode": "0700"
        },
        "before": {
            "mode": "0755"
        }
    },
    "path": "/opt/ai"
}
```

4. Run with `--check -vvv` to see the full SSH connection trace.

```bash
ansible-playbook setup-ai-server.yml --check -vvv 2>&1 | head -40
```

Expected output (abbreviated):
```
PLAYBOOK: setup-ai-server.yml **************************************************
...
<192.168.1.50> SSH: EXEC ssh -C -o ControlMaster=auto -o ControlPersist=60s ...
<192.168.1.50> (0, b'', b'')
...
```

5. Revert the mode back to `0755` in the playbook and apply the real change.

```bash
ansible-playbook setup-ai-server.yml
```

Expected PLAY RECAP:
```
gpu-box-01                 : ok=7    changed=0    unreachable=0    failed=0    skipped=0
```
(No changes because you reverted to the previously applied state.)

## Common Pitfalls

### Pitfall 1: Forgetting `--become` for Tasks That Require Root

**Description:** Tasks that install packages, create system users, manage services, or write to system paths (`/etc/`, `/opt/`) require root privileges. Running the task without `--become` (or `become: true` in the playbook) causes a permission denied error.

**Why it happens:** When you SSH in manually, your user either already has sudo or you remember to run `sudo`. With Ansible, privilege escalation is a separate, explicit step that beginners overlook.

**Incorrect pattern:**
```bash
ansible ai_servers -m apt -a "name=git state=present"
# Returns: FAILED! => {"msg": "Failed to lock apt for exclusive operation"}
```

**Correct pattern:**
```bash
ansible ai_servers -m apt -a "name=git state=present" --become
```

Or in a playbook:
```yaml
- name: Provision AI server baseline
  hosts: ai_servers
  become: true        # applies to all tasks in this play
```

---

### Pitfall 2: Indentation Errors in YAML Playbooks

**Description:** YAML is indentation-sensitive. A task that is indented one space too many or too few will either cause a parse error or, worse, be silently attached to the wrong parent element, changing the playbook's meaning without an obvious error message.

**Why it happens:** Mixing tabs and spaces, or copying YAML from a web page that uses non-standard whitespace, produces invisible indentation errors that are difficult to spot visually.

**Incorrect pattern:**
```yaml
  tasks:
    - name: Install git
    ansible.builtin.apt:   # wrong: this is at tasks level, not inside the task
        name: git
        state: present
```

**Correct pattern:**
```yaml
  tasks:
    - name: Install git
      ansible.builtin.apt:  # correct: indented two spaces under the list item
        name: git
        state: present
```

Use a linter such as `ansible-lint` or at minimum run `ansible-playbook --syntax-check playbook.yml` before every execution.

---

### Pitfall 3: Using the `command` Module When `shell` Features Are Needed

**Description:** The `command` module does not invoke a shell, so it does not support pipes (`|`), redirects (`>`), environment variable expansion (`$HOME`), or glob patterns (`*.log`). Using `command` with any of these constructs silently fails or produces incorrect results.

**Why it happens:** `command` and `shell` look identical in usage, and `command` is listed first in most documentation, leading beginners to use it by default.

**Incorrect pattern:**
```yaml
- name: Count log files
  ansible.builtin.command: ls /var/log/*.log | wc -l
  # Error: ls will receive "*.log | wc -l" as a literal filename argument
```

**Correct pattern:**
```yaml
- name: Count log files
  ansible.builtin.shell: ls /var/log/*.log | wc -l
```

Reserve `command` for simple, no-pipe invocations; use `shell` only when you genuinely need shell interpretation.

---

### Pitfall 4: Not Testing Idempotency by Running the Playbook Twice

**Description:** A playbook that uses `shell` or `command` to run scripts like `echo "config" >> /etc/file` is not idempotent. Each run appends a duplicate line to the file. After ten automated runs the file has ten copies of the same configuration.

**Why it happens:** Shell commands do exactly what you type and have no concept of desired state. Ansible modules like `ansible.builtin.lineinfile` or `ansible.builtin.blockinfile` are designed to be idempotent; raw shell commands are not.

**Incorrect pattern:**
```yaml
- name: Add kernel parameter
  ansible.builtin.shell: echo "vm.overcommit_memory=1" >> /etc/sysctl.conf
  # Appends a duplicate line on every run
```

**Correct pattern:**
```yaml
- name: Add kernel parameter
  ansible.builtin.lineinfile:
    path: /etc/sysctl.conf
    line: "vm.overcommit_memory=1"
    state: present
  # Idempotent: checks whether the line exists before adding it
```

---

### Pitfall 5: Inventory Host Variables Overriding Each Other Unexpectedly

**Description:** When the same variable is defined in multiple places — the inventory file, `host_vars/`, `group_vars/`, and playbook `vars:` — Ansible applies a precedence order that is not obvious. A variable set in `group_vars/all.yml` may be silently overridden by one in `host_vars/gpu-box-01.yml`, causing one host to behave differently from the group without a clear reason.

**Why it happens:** Ansible has over 20 levels of variable precedence. Beginners set variables wherever is convenient rather than in a consistent, documented location.

**Incorrect pattern:**
```ini
# inventory.ini
[ai_servers:vars]
ansible_user=ubuntu

# host_vars/gpu-box-01.yml
ansible_user: admin   # silently overrides the group variable for this host
```

**Correct pattern:** Establish a convention for your project: put defaults in `group_vars/`, put host-specific overrides only when genuinely necessary in `host_vars/`, and document the override with a comment explaining why it differs.

---

### Pitfall 6: Running as Root via `become` When It Is Not Needed

**Description:** Setting `become: true` at the play level causes every task — including harmless read operations and pings — to use sudo. On hardened systems, excessive sudo usage triggers security alerts, slows execution (sudo invocations take time), and violates the principle of least privilege.

**Why it happens:** Setting `become: true` once at the play level is the path of least resistance; it is easy to forget to remove it from tasks that do not need it.

**Incorrect pattern:**
```yaml
- name: Check disk space
  hosts: ai_servers
  become: true         # unnecessary for a disk check

  tasks:
    - name: Check free disk space
      ansible.builtin.shell: df -h /opt/ai
```

**Correct pattern:**
```yaml
- name: Check disk space
  hosts: ai_servers    # no become at play level

  tasks:
    - name: Check free disk space
      ansible.builtin.shell: df -h /opt/ai
      # No become needed; any user can run df

    - name: Clean old logs (needs root)
      ansible.builtin.file:
        path: /var/log/inference/old.log
        state: absent
      become: true     # become only where required
```

---

### Pitfall 7: Relying on `host_key_checking = False` in Production

**Description:** Disabling SSH host key checking allows Ansible to connect to any host that responds on the expected IP address without verifying its identity. In a production or cloud environment this means a malicious server that has taken over an IP address will be trusted and managed as if it were the real server.

**Why it happens:** `host_key_checking = False` is the first suggestion in many tutorials because it removes a friction point when learning. Beginners copy it into production configs.

**Incorrect pattern:**
```ini
# ansible.cfg
[defaults]
host_key_checking = False   # acceptable in a trusted lab, dangerous in production
```

**Correct pattern:** On production systems, pre-populate `~/.ssh/known_hosts` on the control node with the actual host keys of all managed nodes using `ssh-keyscan`:

```bash
ssh-keyscan -H 192.168.1.50 >> ~/.ssh/known_hosts
```

Then leave `host_key_checking` at its default (`True`) or explicitly set it to `True` in `ansible.cfg`.

---

### Pitfall 8: Hardcoding Secrets in Inventory Files or Playbooks

**Description:** Writing passwords, API tokens, or private keys directly in `inventory.ini` or a playbook variable means those secrets are committed to version control and visible to anyone with repository access.

**Why it happens:** It is the fastest way to get a working playbook; the implications for secret exposure are not immediately visible.

**Incorrect pattern:**
```ini
# inventory.ini — never do this
gpu-box-01 ansible_host=192.168.1.50 ansible_become_pass=MySuperSecretPassword123
```

**Correct pattern:** Use Ansible Vault to encrypt sensitive values:

```bash
# Encrypt a value inline
ansible-vault encrypt_string 'MySuperSecretPassword123' --name 'ansible_become_pass'
```

Then reference the encrypted string in your inventory or vars file. At runtime, provide the vault password with `--ask-vault-pass` or a vault password file.

## Summary

- Ansible is an agentless automation platform that manages remote Linux servers exclusively over SSH, requiring no permanent software installation on managed nodes; this makes it uniquely well suited for managing AI infrastructure where GPU servers need to be provisioned quickly and kept in a consistent, auditable state.
- Inventory files — written in INI or YAML format — define which hosts Ansible manages, how to reach them, and what variables apply to individual hosts or groups; a well-structured inventory is the foundation of every Ansible project.
- Ad-hoc commands let you run a single module against any number of hosts immediately from the command line, making them ideal for fleet-wide checks and one-time operations without the overhead of writing a full playbook.
- Playbooks are ordered YAML files of plays and tasks that describe the desired state of your infrastructure in a human-readable, version-controllable form; their idempotent design means running the same playbook repeatedly produces the same result, which is critical for automated provisioning pipelines.
- The `--check` flag, verbosity levels (`-v` through `-vvv`), and `ansible.cfg` are the three most important operational tools for developing reliable playbooks: check mode prevents unintended changes, verbosity exposes what is actually happening over SSH, and `ansible.cfg` eliminates repetitive command-line flags so your commands stay readable.

## Further Reading

- [Ansible Getting Started Guide — Official Docs](https://docs.ansible.com/ansible/latest/getting_started/index.html) — The canonical first-read for new users, covering installation, inventory basics, and running your first ad-hoc command and playbook; start here if you want to explore beyond this module.
- [Ansible Playbook Concepts — Official Docs](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_intro.html) — Deep coverage of playbook structure including plays, tasks, handlers, variables, and conditionals; the essential next reference after completing this module.
- [Ansible Inventory Guide — Official Docs](https://docs.ansible.com/ansible/latest/inventory_guide/intro_inventory.html) — Complete reference for both INI and YAML inventory formats, group variables, host variables, and dynamic inventory plugins; covers everything needed for managing a multi-group AI fleet.
- [Ansible Built-in Module Index — Official Docs](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/index.html) — The authoritative reference for every module in the `ansible.builtin` collection, with full parameter lists, return values, and examples; bookmark this for whenever you need to check exact module syntax.
- [Ansible Configuration Settings Reference — Official Docs](https://docs.ansible.com/ansible/latest/reference_appendices/config.html) — Complete list of every `ansible.cfg` setting with allowed values and descriptions; essential reading once you start customising Ansible behaviour beyond the defaults covered here.
- [Ansible Best Practices: Content Organization — Official Docs](https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html) — Official guidance on project directory layout, role organisation, and variable management patterns; the right read when your project grows beyond a single playbook file.
- [ansible-lint Documentation](https://ansible-lint.readthedocs.io/en/latest/) — Documentation for the community-standard Ansible linter, which catches YAML syntax errors, deprecated module usage, and style violations before they reach production; integrating `ansible-lint` into CI is a key maturity step for any Ansible project.
- [Jeff Geerling — Ansible for DevOps (book site)](https://www.ansiblefordevops.com/) — Resource page for the most widely recommended community book on Ansible, with free sample chapters and example playbooks covering real-world infrastructure patterns including server provisioning and application deployment.
