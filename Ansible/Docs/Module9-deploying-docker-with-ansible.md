# Deploying Docker with Ansible
### A Step-by-Step Training Exercise

---

## Prerequisites

Before starting this exercise, ensure you have the following in place:

- A **control node** (your local machine or a jump host) with Ansible installed
- One or more **target hosts** (Linux PCs) accessible via SSH
- Python 3.x installed on all target hosts
- A user account with `sudo` privileges on the target hosts
- Basic familiarity with the Linux command line

> **Note:** This exercise uses Ubuntu 22.04 LTS as the target OS. Commands may differ slightly on other distributions.

---

## Overview

In this exercise, you will progressively build an Ansible project to automate the installation and configuration of Docker on a remote PC. Each stage builds on the last, introducing new Ansible concepts along the way.

| Stage | Topic |
|-------|-------|
| 1 | Setting up your Ansible project structure |
| 2 | Defining your inventory |
| 3 | Testing connectivity |
| 4 | Writing your first playbook |
| 5 | Installing Docker |
| 6 | Configuring Docker post-install |
| 7 | Verifying the deployment |
| 8 | Using variables and making it reusable |

---

## Stage 1 — Project Structure

Good Ansible projects follow a consistent directory layout. Start by creating the project skeleton.

```bash
mkdir ansible-docker-deploy
cd ansible-docker-deploy

mkdir -p roles/docker/{tasks,handlers,defaults,templates}
touch inventory.ini
touch playbook.yml
touch ansible.cfg
```

Your project should now look like this:

```
ansible-docker-deploy/
├── ansible.cfg
├── inventory.ini
├── playbook.yml
└── roles/
    └── docker/
        ├── defaults/
        ├── handlers/
        ├── tasks/
        └── templates/
```

### Configure `ansible.cfg`

This file tells Ansible where to find your inventory and sets sensible defaults.

```ini
[defaults]
inventory       = inventory.ini
remote_user     = your_ssh_user
private_key_file = ~/.ssh/id_rsa
host_key_checking = False

[privilege_escalation]
become      = True
become_method = sudo
```

> **Checkpoint:** What is the purpose of `become = True` in the config? Discuss with your instructor before moving on.

---

## Stage 2 — Defining the Inventory

The inventory tells Ansible which machines to manage and how to reach them.

Edit `inventory.ini`:

```ini
[docker_hosts]
pc01 ansible_host=192.168.1.10
pc02 ansible_host=192.168.1.11

[docker_hosts:vars]
ansible_python_interpreter=/usr/bin/python3
```

Replace the IP addresses with those of your target machines.

> **Tip:** You can also use hostnames instead of IP addresses, provided DNS resolution is working correctly.

---

## Stage 3 — Testing Connectivity

Before writing any automation, confirm Ansible can reach your hosts.

### Ping Test

```bash
ansible all -m ping
```

**Expected output:**

```
pc01 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
pc02 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

### Gather Facts

Run an ad-hoc command to check the OS details on your targets:

```bash
ansible all -m setup -a "filter=ansible_distribution*"
```

> **Checkpoint:** If the ping test fails, what would you check first? Work through the troubleshooting with your partner before asking for help.

---

## Stage 4 — Writing Your First Playbook

Start simple. Write a playbook that updates the package cache on all hosts.

Edit `playbook.yml`:

```yaml
---
- name: Deploy Docker to target hosts
  hosts: docker_hosts
  become: true

  tasks:
    - name: Update apt package cache
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600
```

Run the playbook:

```bash
ansible-playbook playbook.yml
```

Observe the output carefully. Note the `changed` and `ok` status for each task.

> **Concept:** Ansible is **idempotent** — running the same playbook multiple times should produce the same result without causing unintended side effects. Run the playbook a second time and compare the output.

---

## Stage 5 — Installing Docker

Now you'll build out the Docker role with the full installation steps.

### 5.1 — Install Required Dependencies

Create `roles/docker/tasks/main.yml`:

```yaml
---
- name: Install prerequisite packages
  ansible.builtin.apt:
    name:
      - apt-transport-https
      - ca-certificates
      - curl
      - gnupg
      - lsb-release
    state: present
    update_cache: true
```

### 5.2 — Add Docker's GPG Key

Append to `roles/docker/tasks/main.yml`:

```yaml
- name: Create keyrings directory
  ansible.builtin.file:
    path: /etc/apt/keyrings
    state: directory
    mode: '0755'

- name: Download Docker's official GPG key
  ansible.builtin.get_url:
    url: https://download.docker.com/linux/ubuntu/gpg
    dest: /etc/apt/keyrings/docker.asc
    mode: '0644'
```

### 5.3 — Add the Docker Repository

```yaml
- name: Add Docker apt repository
  ansible.builtin.apt_repository:
    repo: >-
      deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc]
      https://download.docker.com/linux/ubuntu
      {{ ansible_distribution_release }} stable
    state: present
    filename: docker
```

### 5.4 — Install Docker Engine

```yaml
- name: Install Docker Engine
  ansible.builtin.apt:
    name:
      - docker-ce
      - docker-ce-cli
      - containerd.io
      - docker-buildx-plugin
      - docker-compose-plugin
    state: present
    update_cache: true
```

### 5.5 — Link the Role to the Playbook

Update `playbook.yml` to call the role:

```yaml
---
- name: Deploy Docker to target hosts
  hosts: docker_hosts
  become: true

  tasks:
    - name: Update apt package cache
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600

  roles:
    - docker
```

Run the playbook again:

```bash
ansible-playbook playbook.yml
```

> **Checkpoint:** Watch the task output. How many tasks ran as `changed` vs `ok`? What does this tell you about the state of your target machines?

---

## Stage 6 — Post-Installation Configuration

Docker is installed, but it needs a few extra steps to be production-ready.

### 6.1 — Enable and Start the Docker Service

Add to `roles/docker/tasks/main.yml`:

```yaml
- name: Enable and start Docker service
  ansible.builtin.systemd:
    name: docker
    state: started
    enabled: true
```

### 6.2 — Add a User to the Docker Group

Running Docker as `root` for every command is poor practice. Add your user to the `docker` group.

```yaml
- name: Add deploy user to docker group
  ansible.builtin.user:
    name: "{{ docker_user }}"
    groups: docker
    append: true
```

### 6.3 — Set the Default Variable

Edit `roles/docker/defaults/main.yml`:

```yaml
---
docker_user: "{{ ansible_user }}"
```

### 6.4 — Add a Handler to Restart Docker

Handlers only run when notified, and only once per playbook run — ideal for service restarts.

Edit `roles/docker/handlers/main.yml`:

```yaml
---
- name: Restart Docker
  ansible.builtin.systemd:
    name: docker
    state: restarted
```

> **Concept:** Where would you add a `notify: Restart Docker` directive? Why use a handler instead of a direct restart task? Discuss this with your group.

---

## Stage 7 — Verifying the Deployment

After a successful playbook run, verify Docker is working correctly on the target hosts.

### Via Ansible Ad-Hoc Command

```bash
ansible docker_hosts -m command -a "docker --version"
```

**Expected output:**

```
pc01 | CHANGED | rc=0 >>
Docker version 26.x.x, build xxxxxxx
```

### Run a Test Container

```bash
ansible docker_hosts -m command -a "docker run --rm hello-world"
```

A successful run will print Docker's welcome message, confirming the engine, image pull, and container execution all work correctly.

### Check the Service Status

```bash
ansible docker_hosts -m systemd -a "name=docker" --become
```

Confirm that `ActiveState` is `active` and `UnitFileState` is `enabled`.

> **Checkpoint:** What does it mean if `UnitFileState` is `disabled`? How would you fix it using an Ansible task?

---

## Stage 8 — Variables and Reusability

Hardcoded values make playbooks brittle. Let's make the role configurable.

### 8.1 — Expand Role Defaults

Update `roles/docker/defaults/main.yml`:

```yaml
---
docker_user: "{{ ansible_user }}"
docker_edition: "ce"
docker_packages:
  - "docker-{{ docker_edition }}"
  - "docker-{{ docker_edition }}-cli"
  - containerd.io
  - docker-buildx-plugin
  - docker-compose-plugin
docker_service_state: started
docker_service_enabled: true
```

### 8.2 — Reference Variables in Tasks

Update the install task to use the `docker_packages` variable:

```yaml
- name: Install Docker Engine
  ansible.builtin.apt:
    name: "{{ docker_packages }}"
    state: present
    update_cache: true
```

Update the service task to use the service state variables:

```yaml
- name: Enable and start Docker service
  ansible.builtin.systemd:
    name: docker
    state: "{{ docker_service_state }}"
    enabled: "{{ docker_service_enabled }}"
```

### 8.3 — Override Variables at Runtime

You can override any default at the command line:

```bash
ansible-playbook playbook.yml -e "docker_user=myuser"
```

Or in a separate host/group variable file:

```bash
mkdir -p group_vars
cat > group_vars/docker_hosts.yml << EOF
docker_user: deployuser
docker_service_enabled: true
EOF
```

> **Exercise:** Add a variable to control whether the `hello-world` test container is run after installation. Implement the conditional task using `when:`.

---

## Final Playbook — Complete Reference

```yaml
---
- name: Deploy Docker to target hosts
  hosts: docker_hosts
  become: true

  tasks:
    - name: Update apt package cache
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600

  roles:
    - docker
```

```
roles/docker/
├── defaults/
│   └── main.yml      ← default variables
├── handlers/
│   └── main.yml      ← restart handler
└── tasks/
    └── main.yml      ← all installation tasks
```

---

## Troubleshooting Reference

| Problem | Likely Cause | Resolution |
|---------|-------------|------------|
| `UNREACHABLE` on ping | SSH not reachable / wrong IP | Check network, firewall, SSH service |
| `Permission denied` | `sudo` not configured | Add user to sudoers on target host |
| GPG key download fails | No internet access on target | Check proxy settings or pre-stage the key |
| Docker service not starting | Port conflict or daemon error | Check `journalctl -u docker` on the host |
| User not in docker group | Group change requires re-login | Log out and back in on the target host |

---

## Summary

In this exercise you have:

- Structured an Ansible project using roles
- Defined a static inventory and configured connectivity
- Written a playbook that installs Docker Engine end-to-end
- Applied idempotency principles throughout
- Used variables and defaults to make the role reusable
- Verified the deployment with ad-hoc commands and a test container

**Next steps:** Extend this role to also deploy Docker Compose projects, configure the Docker daemon with a custom `daemon.json`, or add TLS for remote Docker API access.

---

*Training material — internal use only*
