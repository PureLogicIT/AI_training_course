# Module 6: AI Stack Deployment
> Subject: Ansible | Difficulty: Advanced | Estimated Time: 390 minutes

## Objective

After completing this module, you will be able to write a single idempotent Ansible playbook that provisions a complete, production-ready AI inference stack on a bare Linux server. You will use the `apt` module to install NVIDIA drivers and CUDA toolkit packages, load the required kernel modules with the `modprobe` command module, install Docker Engine and the NVIDIA Container Toolkit so GPU-accelerated containers can run, deploy Ollama as a native systemd service using `get_url` and `unarchive`, pull LLM models idempotently with the `command` module and a `stat`-based pre-check, deploy Open WebUI as a Docker container behind Nginx, render an Nginx reverse-proxy configuration with TLS using the `template` module, set per-service environment variables with `lineinfile` and `environment` blocks, and deploy a FastAPI-based AI application from Git using the `git` and `pip` modules managed as a systemd service. By the end, one `ansible-playbook` invocation takes a freshly imaged Ubuntu 22.04 server to a fully operational AI stack accessible to end users over HTTPS.

## Prerequisites

- Completed Module 1: Ansible Fundamentals — comfortable with inventory files, `ansible.cfg`, ad-hoc commands, and basic playbook structure
- Completed Module 2: Playbook Authoring — familiar with tasks, handlers, variables, and conditionals
- Completed Module 3: Modules In Depth — experience with `apt`, `copy`, `template`, `service`, `user`, and `file` modules
- Completed Module 4: Roles and Reusable Playbooks — understands role directory layout and `include_role`
- Completed Module 5: Secrets Management with Ansible Vault — able to encrypt variables and reference vault files
- A control node running Ansible 2.17 or later (`ansible --version` to verify)
- A target host running Ubuntu 22.04 LTS with an NVIDIA GPU (Ampere or later recommended), at least 16 GB RAM, and 100 GB free disk space
- SSH access to the target host from the control node; the remote user must have `sudo` (passwordless or prompted via `--ask-become-pass`)
- Familiarity with systemd unit files and basic Nginx configuration syntax
- Basic understanding of LLM serving concepts (model files, inference ports, context windows)

## Key Concepts

### Why Deploy the AI Stack with Ansible Instead of Shell Scripts

A shell script that installs NVIDIA drivers, Docker, Ollama, Open WebUI, and Nginx in sequence is straightforward to write but fragile to operate. If the script fails halfway through a CUDA installation it leaves the host in an unknown state. Re-running it may re-install packages, overwrite working configurations, or skip already-completed steps silently. None of that is safe for a production server.

Ansible solves these problems through **idempotency**: every module checks the current state before acting. `apt` will not reinstall a package that is already at the requested version. `systemd` will not restart a service that is already running in the desired state. `template` will only rewrite a file if the rendered content differs from what is on disk, and if it does rewrite the file it can notify a handler to reload Nginx atomically. The result is a playbook you can run repeatedly — during initial provisioning, after a configuration change, and as a drift-correction job in CI — without side effects.

The stack this module deploys has five tightly coupled layers. Each layer must exist before the next one can function:

```
┌─────────────────────────────────────────────┐
│  Users (HTTPS)                              │
├─────────────────────────────────────────────┤
│  Nginx  (reverse proxy, TLS termination)    │  port 443
├─────────────────────────────────────────────┤
│  Open WebUI  (chat UI container)            │  port 8080
│  FastAPI App (custom AI service)            │  port 8000
├─────────────────────────────────────────────┤
│  Ollama  (LLM inference, systemd service)   │  port 11434
├─────────────────────────────────────────────┤
│  NVIDIA Container Toolkit + Docker Engine   │
├─────────────────────────────────────────────┤
│  NVIDIA Driver + CUDA Toolkit               │
└─────────────────────────────────────────────┘
```

Ansible handles this dependency chain through task ordering within a single play, explicit `notify`/`handler` relationships, and `wait_for` tasks that block until a port or socket is ready before proceeding to the next layer.

### Installing NVIDIA Drivers and CUDA with the `apt` Module

Ubuntu 22.04 ships NVIDIA drivers through the `ubuntu-drivers` package and the `graphics-drivers` PPA. CUDA packages are distributed through NVIDIA's own APT repository. Both require adding a GPG key and a sources list entry before packages can be installed. The correct sequence in Ansible is:

1. Add the NVIDIA GPG key using `apt_key` or `get_url` + `apt_key`
2. Add the NVIDIA CUDA APT repository with `apt_repository`
3. Update the APT cache (`update_cache: true` on the first `apt` task that needs it)
4. Install the driver metapackage and CUDA toolkit
5. Load the `nvidia` kernel module with `modprobe`
6. Reboot if the module was newly installed (detect via `register` + `changed_when`)

```yaml
# roles/nvidia/tasks/main.yml

- name: Add NVIDIA CUDA APT keyring
  ansible.builtin.get_url:
    url: https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
    dest: /tmp/cuda-keyring.deb
    mode: "0644"
  register: cuda_keyring_download

- name: Install CUDA keyring package
  ansible.builtin.apt:
    deb: /tmp/cuda-keyring.deb
  when: cuda_keyring_download.changed

- name: Update APT cache after adding CUDA repo
  ansible.builtin.apt:
    update_cache: true
    cache_valid_time: 3600

- name: Install NVIDIA driver and CUDA toolkit
  ansible.builtin.apt:
    name:
      - cuda-drivers
      - cuda-toolkit-12-6
    state: present
  register: cuda_install
  notify: reboot host

- name: Load nvidia kernel module
  community.general.modprobe:
    name: nvidia
    state: present
  failed_when: false
```

The `cache_valid_time: 3600` parameter tells Ansible to skip the cache refresh if it was already run within the last hour, which prevents redundant network calls on re-runs. The `cuda-drivers` metapackage always resolves to the latest driver version compatible with the installed CUDA version, which is preferable to pinning a specific driver number that may become incompatible after a kernel update.

After installation, loading the kernel module with `community.general.modprobe` is separate from the package install because the module will not be present in the running kernel until after a reboot. The `failed_when: false` flag prevents the task from failing on the first run before the reboot handler fires.

### Installing Docker Engine and the NVIDIA Container Toolkit

Docker Engine on Ubuntu is installed from Docker's official APT repository, not from the Ubuntu universe repository. The universe package (`docker.io`) lags several major versions behind and does not receive the same update cadence. The NVIDIA Container Toolkit is installed from NVIDIA's container repository and requires Docker to already be installed before it can be configured.

```yaml
# roles/docker/tasks/main.yml

- name: Install Docker prerequisites
  ansible.builtin.apt:
    name:
      - ca-certificates
      - curl
      - gnupg
    state: present
    update_cache: true

- name: Create /etc/apt/keyrings directory
  ansible.builtin.file:
    path: /etc/apt/keyrings
    state: directory
    mode: "0755"

- name: Download Docker GPG key
  ansible.builtin.get_url:
    url: https://download.docker.com/linux/ubuntu/gpg
    dest: /etc/apt/keyrings/docker.asc
    mode: "0644"

- name: Add Docker APT repository
  ansible.builtin.apt_repository:
    repo: >-
      deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc]
      https://download.docker.com/linux/ubuntu
      {{ ansible_distribution_release }} stable
    state: present
    filename: docker

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

- name: Enable and start Docker service
  ansible.builtin.systemd:
    name: docker
    enabled: true
    state: started

- name: Add deploy user to docker group
  ansible.builtin.user:
    name: "{{ deploy_user }}"
    groups: docker
    append: true

- name: Add NVIDIA Container Toolkit APT repository
  ansible.builtin.apt_repository:
    repo: >-
      deb https://nvidia.github.io/libnvidia-container/stable/deb/$(ARCH) /
    state: present
    filename: nvidia-container-toolkit

- name: Install NVIDIA Container Toolkit
  ansible.builtin.apt:
    name: nvidia-container-toolkit
    state: present
    update_cache: true

- name: Configure Docker runtime for NVIDIA
  ansible.builtin.command:
    cmd: nvidia-ctk runtime configure --runtime=docker
  register: ctk_configure
  changed_when: "'Updated' in ctk_configure.stdout"
  notify: restart docker
```

The `ansible_distribution_release` fact (e.g., `jammy` for Ubuntu 22.04) is gathered automatically by Ansible's setup module, which runs at the start of every play by default. Using it here means the same role works unchanged on Ubuntu 20.04 (`focal`) and Ubuntu 24.04 (`noble`).

The `nvidia-ctk runtime configure` command writes a `default-runtime: nvidia` entry into `/etc/docker/daemon.json`. The `changed_when` clause inspects the command's stdout to determine idempotency — if Docker is already configured, the command prints a message that does not contain the word `Updated`, and Ansible marks the task as `ok` rather than `changed`.

### Deploying Ollama as a Systemd Service

Ollama is distributed as a single statically-linked binary with an optional install script. For production Ansible deployments the install script is inappropriate because it is not idempotent — it always downloads and overwrites the binary. The correct approach for Ansible is to use `get_url` to download a specific versioned binary, check its hash, and only overwrite if the binary has changed.

```yaml
# roles/ollama/tasks/main.yml

- name: Create ollama system user
  ansible.builtin.user:
    name: ollama
    system: true
    shell: /usr/sbin/nologin
    home: /usr/share/ollama
    create_home: true

- name: Create ollama model storage directory
  ansible.builtin.file:
    path: /var/lib/ollama/models
    state: directory
    owner: ollama
    group: ollama
    mode: "0755"

- name: Download Ollama binary
  ansible.builtin.get_url:
    url: "https://github.com/ollama/ollama/releases/download/{{ ollama_version }}/ollama-linux-amd64"
    dest: /usr/local/bin/ollama
    mode: "0755"
    owner: root
    group: root
    checksum: "sha256:{{ ollama_sha256 }}"
  notify: restart ollama

- name: Deploy Ollama systemd unit file
  ansible.builtin.template:
    src: ollama.service.j2
    dest: /etc/systemd/system/ollama.service
    mode: "0644"
  notify:
    - reload systemd
    - restart ollama

- name: Enable and start Ollama service
  ansible.builtin.systemd:
    name: ollama
    enabled: true
    state: started
    daemon_reload: true
```

The corresponding Jinja2 template for the systemd unit is stored at `roles/ollama/templates/ollama.service.j2`:

```ini
[Unit]
Description=Ollama LLM Inference Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ollama
Group=ollama
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=3
Environment="HOME=/usr/share/ollama"
Environment="OLLAMA_MODELS=/var/lib/ollama/models"
Environment="OLLAMA_HOST={{ ollama_host | default('0.0.0.0') }}"
Environment="OLLAMA_NUM_PARALLEL={{ ollama_num_parallel | default(1) }}"

[Install]
WantedBy=multi-user.target
```

Defining `OLLAMA_HOST` and `OLLAMA_NUM_PARALLEL` as Jinja2 variables in the unit template means you control inference behavior through your inventory or group variables without editing the template itself. `OLLAMA_HOST=0.0.0.0` makes Ollama listen on all interfaces within the server; Nginx handles external access control, so this is safe. `OLLAMA_NUM_PARALLEL` controls how many simultaneous inference requests Ollama accepts — set it conservatively (1 or 2) unless you have multiple high-VRAM GPUs.

### Idempotent Model Management with the `command` Module

Pulling a model with `ollama pull` takes anywhere from two minutes (a small 1B model) to over an hour (a large 70B model), depending on the model size and network speed. Re-pulling a model that is already present wastes that time. The correct pattern is to check whether the model directory already exists before invoking `ollama pull`.

Ollama stores models in `$OLLAMA_MODELS/<namespace>/<name>` as a collection of blob files and a manifest. The existence of the manifest file is the reliable signal that the model was fully downloaded.

```yaml
# roles/ollama/tasks/pull_models.yml

- name: Wait for Ollama API to become available
  ansible.builtin.wait_for:
    host: 127.0.0.1
    port: 11434
    delay: 5
    timeout: 60

- name: Check which models are already present
  ansible.builtin.stat:
    path: "/var/lib/ollama/models/manifests/registry.ollama.ai/library/{{ item }}"
  register: model_stat
  loop: "{{ ollama_models }}"

- name: Pull missing LLM models
  ansible.builtin.command:
    cmd: "/usr/local/bin/ollama pull {{ item.item }}"
  environment:
    HOME: /usr/share/ollama
    OLLAMA_MODELS: /var/lib/ollama/models
  become: true
  become_user: ollama
  loop: "{{ model_stat.results }}"
  when: not item.stat.exists
  changed_when: true
  async: 3600
  poll: 30
```

The `async: 3600` and `poll: 30` directives tell Ansible to run the pull in the background and check its status every 30 seconds, up to a maximum of 3600 seconds (one hour). Without `async`, Ansible would hold the SSH connection open for the entire download duration, which frequently triggers SSH keep-alive timeouts on large models. The `changed_when: true` override is intentional: Ansible cannot inspect the pull's side effects to determine whether any new layers were downloaded, so always marking it `changed` is honest and ensures downstream handlers fire correctly.

The `ollama_models` variable is defined in `group_vars/ai_servers.yml`:

```yaml
ollama_models:
  - llama3.2
  - mistral
  - nomic-embed-text
```

### Deploying Open WebUI and Nginx as a Reverse Proxy

Open WebUI is an Ollama-compatible chat interface that runs as a Docker container. It connects to Ollama over the local network and exposes a web interface on port 8080. Because you want HTTPS access from users, Nginx sits in front of it and terminates TLS.

```yaml
# roles/open_webui/tasks/main.yml

- name: Create Open WebUI data volume directory
  ansible.builtin.file:
    path: /var/lib/open-webui
    state: directory
    owner: "{{ deploy_user }}"
    group: "{{ deploy_user }}"
    mode: "0755"

- name: Pull Open WebUI Docker image
  community.docker.docker_image:
    name: "ghcr.io/open-webui/open-webui:{{ open_webui_version | default('main') }}"
    source: pull
    state: present

- name: Run Open WebUI container
  community.docker.docker_container:
    name: open-webui
    image: "ghcr.io/open-webui/open-webui:{{ open_webui_version | default('main') }}"
    state: started
    restart_policy: unless-stopped
    ports:
      - "127.0.0.1:8080:8080"
    volumes:
      - /var/lib/open-webui:/app/backend/data
    env:
      OLLAMA_BASE_URL: "http://127.0.0.1:11434"
      WEBUI_SECRET_KEY: "{{ webui_secret_key }}"
    networks:
      - name: ai-stack
```

Binding Open WebUI to `127.0.0.1:8080` rather than `0.0.0.0:8080` is important: it ensures the container port is reachable only from within the server, never directly from the public internet. Nginx is the single entry point.

The Nginx configuration is rendered from a Jinja2 template stored at `roles/nginx/templates/ai-stack.conf.j2`:

```nginx
upstream ollama_backend {
    server 127.0.0.1:11434;
    keepalive 32;
}

upstream webui_backend {
    server 127.0.0.1:8080;
    keepalive 32;
}

upstream fastapi_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name {{ nginx_server_name }};
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name {{ nginx_server_name }};

    ssl_certificate     {{ nginx_ssl_cert_path }};
    ssl_certificate_key {{ nginx_ssl_key_path }};
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # Open WebUI — primary chat interface
    location / {
        proxy_pass         http://webui_backend;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_read_timeout 300s;
    }

    # Ollama API — restricted to internal callers via X-API-Key header
    location /api/ollama/ {
        if ($http_x_api_key != "{{ ollama_api_key }}") {
            return 403;
        }
        proxy_pass         http://ollama_backend/;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_read_timeout 600s;
    }

    # FastAPI AI service
    location /api/v1/ {
        proxy_pass         http://fastapi_backend/;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_read_timeout 120s;
    }
}
```

The Ansible task that deploys this template is:

```yaml
- name: Deploy Nginx AI stack configuration
  ansible.builtin.template:
    src: ai-stack.conf.j2
    dest: /etc/nginx/sites-available/ai-stack.conf
    mode: "0644"
    validate: nginx -t -c /etc/nginx/nginx.conf
  notify: reload nginx

- name: Enable Nginx AI stack site
  ansible.builtin.file:
    src: /etc/nginx/sites-available/ai-stack.conf
    dest: /etc/nginx/sites-enabled/ai-stack.conf
    state: link
  notify: reload nginx
```

The `validate` parameter on the `template` module runs `nginx -t` against the rendered file before writing it to disk. If the configuration contains a syntax error, Ansible aborts the task with an error message and leaves the existing working configuration untouched. This is the critical safety net for proxy configurations — a bad Nginx config that passes `changed` and triggers `reload nginx` would take down the entire AI stack for all users.

### Deploying a FastAPI AI Application with `git` and `pip`

A custom AI application sits on top of Ollama and exposes a documented REST API for programmatic callers. The standard Ansible pattern for Python application deployment uses the `git` module to clone or update the repository, the `pip` module inside a virtualenv to install dependencies, and a `template` task to write the systemd unit file.

```yaml
# roles/fastapi_app/tasks/main.yml

- name: Create application user
  ansible.builtin.user:
    name: "{{ app_user }}"
    system: true
    shell: /usr/sbin/nologin
    home: "{{ app_home }}"
    create_home: true

- name: Clone or update FastAPI application repository
  ansible.builtin.git:
    repo: "{{ app_repo_url }}"
    dest: "{{ app_home }}/app"
    version: "{{ app_git_ref | default('main') }}"
    force: false
  become: true
  become_user: "{{ app_user }}"
  register: git_result
  notify: restart fastapi

- name: Install Python dependencies into virtualenv
  ansible.builtin.pip:
    requirements: "{{ app_home }}/app/requirements.txt"
    virtualenv: "{{ app_home }}/venv"
    virtualenv_command: python3 -m venv
  become: true
  become_user: "{{ app_user }}"
  when: git_result.changed

- name: Write application environment file
  ansible.builtin.template:
    src: fastapi.env.j2
    dest: "{{ app_home }}/.env"
    owner: "{{ app_user }}"
    group: "{{ app_user }}"
    mode: "0600"
  notify: restart fastapi

- name: Deploy FastAPI systemd unit
  ansible.builtin.template:
    src: fastapi.service.j2
    dest: "/etc/systemd/system/{{ app_service_name }}.service"
    mode: "0644"
  notify:
    - reload systemd
    - restart fastapi

- name: Enable and start FastAPI service
  ansible.builtin.systemd:
    name: "{{ app_service_name }}"
    enabled: true
    state: started
    daemon_reload: true
```

The `.env` file template (`roles/fastapi_app/templates/fastapi.env.j2`) centralises all service-specific configuration:

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL={{ ollama_default_model }}
APP_API_KEY={{ app_api_key }}
APP_LOG_LEVEL={{ app_log_level | default('info') }}
APP_WORKERS={{ app_workers | default(2) }}
```

The systemd unit for FastAPI reads that file via `EnvironmentFile`:

```ini
[Unit]
Description={{ app_description | default('FastAPI AI Service') }}
After=network.target ollama.service

[Service]
Type=simple
User={{ app_user }}
Group={{ app_user }}
WorkingDirectory={{ app_home }}/app
EnvironmentFile={{ app_home }}/.env
ExecStart={{ app_home }}/venv/bin/uvicorn main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers ${APP_WORKERS}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Declaring `After=ollama.service` in the FastAPI unit file means systemd will not start FastAPI until Ollama is up. This mirrors the dependency ordering that Ansible enforces during provisioning.

### Structuring the Master Playbook

All the roles above are composed in a single top-level playbook that deploys the complete stack in one run. The `pre_tasks` section handles host-level prerequisites, and `post_tasks` verifies the stack is healthy before the play completes.

```yaml
# site.yml  —  AI Stack deployment playbook

- name: Deploy complete AI inference stack
  hosts: ai_servers
  become: true
  gather_facts: true

  vars_files:
    - vars/common.yml
    - vars/secrets.yml         # Ansible Vault encrypted

  pre_tasks:
    - name: Ensure Python 3 is available on target
      ansible.builtin.raw: test -e /usr/bin/python3 || apt-get install -y python3
      changed_when: false

    - name: Gather facts after Python check
      ansible.builtin.setup:

    - name: Set hostname
      ansible.builtin.hostname:
        name: "{{ inventory_hostname }}"

  roles:
    - role: nvidia          # NVIDIA drivers + CUDA
    - role: docker          # Docker Engine + NVIDIA Container Toolkit
    - role: ollama          # Ollama binary + systemd unit
    - role: ollama_models   # Pull LLM models idempotently
    - role: open_webui      # Open WebUI container
    - role: fastapi_app     # Custom FastAPI AI service
    - role: nginx           # Reverse proxy + TLS

  post_tasks:
    - name: Verify Ollama is responding
      ansible.builtin.uri:
        url: http://127.0.0.1:11434/api/tags
        status_code: 200
      register: ollama_health
      retries: 5
      delay: 10
      until: ollama_health.status == 200

    - name: Verify Open WebUI is responding
      ansible.builtin.uri:
        url: http://127.0.0.1:8080
        status_code: 200
      register: webui_health
      retries: 5
      delay: 10
      until: webui_health.status == 200

    - name: Print stack access URL
      ansible.builtin.debug:
        msg: "AI stack deployed. Access at https://{{ nginx_server_name }}"
```

## Best Practices

1. **Pin every version variable in `group_vars`**, including `ollama_version`, `cuda_toolkit_*`, and `open_webui_version` — version drift between runs is the single largest source of "works the first time, breaks on update" failures in AI stack deployments because CUDA and driver versions have strict compatibility requirements.

2. **Use `checksum` on every `get_url` task** that downloads a binary or archive — NVIDIA and Ollama distribute SHA256 checksums alongside their releases; verifying them prevents a corrupted download from silently installing a broken binary.

3. **Separate secrets into an Ansible Vault file** (`vars/secrets.yml`) and never store `webui_secret_key`, `ollama_api_key`, or `app_api_key` in plaintext inventory or role defaults — a leaked key in a public repository grants API-level access to your GPU server.

4. **Always use `validate:` on the `template` module when rendering Nginx configs** — running `nginx -t` before writing the file prevents a bad proxy configuration from taking down all services on the server.

5. **Use `async` and `poll` for long-running `command` tasks like model pulls** — holding an SSH connection open for 30+ minutes while a large model downloads is guaranteed to time out on most network setups; async tasks avoid this entirely.

6. **Bind all backend services to `127.0.0.1`, not `0.0.0.0`** — Ollama on port 11434, Open WebUI on 8080, and FastAPI on 8000 should never be directly reachable from the internet; Nginx is the sole ingress, giving you a single point to enforce authentication and rate limiting.

7. **Declare `After=` dependencies in systemd unit templates** between services (e.g., `After=ollama.service` in the FastAPI unit) — this ensures the correct startup order on reboots, not just on first provision.

8. **Use `become_user` with a dedicated non-root service account** for `git clone`, `pip install`, and model pulls — running these as root produces files owned by root inside application directories, breaking later updates that run as the service user.

9. **Add a `wait_for` task before any task that depends on a port** (e.g., wait for Ollama port 11434 before pulling models) — services take 2–15 seconds to finish startup after systemd marks them `active`, and a `command` task that fires immediately will fail with a connection refused error.

10. **Tag your roles** with `--tags nvidia`, `--tags models`, etc. so you can re-run individual layers during development without reprovisioning the entire stack every time.

## Use Cases

### Provisioning a New AI Research Server from Scratch

A team receives a bare-metal server with an NVIDIA H100 GPU and Ubuntu 22.04 installed. Within a single working hour they need a functional Ollama instance with Llama 3.2 and Mistral available, a web interface for non-technical users, and a documented API for scripts. Running `ansible-playbook site.yml -i inventory/research.ini` handles every step: CUDA installation, Docker configuration, model downloads, and Nginx TLS setup. The `post_tasks` health checks confirm success. The entire provisioning is version-controlled and reproducible; a second identical server can be deployed the same afternoon with one command.

**Concepts applied:** Full role sequence, `get_url` + `checksum` for Ollama binary, idempotent model pulls, `template` for Nginx config, `post_tasks` with `uri` health checks.
**Expected outcome:** Running AI stack accessible at `https://ai.company.internal` within 60–90 minutes of starting the playbook.

### Updating the LLM Model Catalogue Without Touching Infrastructure

New models become available monthly. The operations team updates `ollama_models` in `group_vars/ai_servers.yml` to add `qwen2.5` and `phi3.5`, then runs `ansible-playbook site.yml --tags models`. The idempotent `stat` pre-check skips models already present and only pulls the two new ones, which takes 15 minutes. Existing services are not restarted.

**Concepts applied:** Idempotent model management with `stat` + `loop`, `async`/`poll` for large downloads, role tagging.
**Expected outcome:** Two new models added to the Ollama catalogue; all other services untouched.

### Rotating API Keys and Secrets Across a Fleet

The security team requires quarterly rotation of the `webui_secret_key` and `app_api_key`. An engineer updates the values in the Ansible Vault file and runs the playbook. The `template` tasks for the `.env` file and the Nginx config detect the changed content, rewrite the files, and trigger `restart fastapi` and `reload nginx` handlers. No manual SSH access to any server is needed.

**Concepts applied:** Ansible Vault for secrets, `template` + `notify` + handlers, `lineinfile` for environment files.
**Expected outcome:** All secrets rotated and services reloaded within one playbook run; the change is recorded in Git history as a vault-encrypted diff.

### Rebuilding After a Kernel Update Breaks the NVIDIA Driver

A kernel update (`apt upgrade`) applied outside of Ansible removes the NVIDIA kernel module binding. The GPU becomes unavailable and Ollama falls back to CPU inference. Re-running the playbook detects that the `cuda-drivers` package is already at the correct version but that the `nvidia` kernel module is not loaded, triggers a reboot handler, and restores GPU inference without re-downloading CUDA packages.

**Concepts applied:** `modprobe` task with `failed_when: false`, reboot handler, `changed_when` on driver install, `async` model pre-check.
**Expected outcome:** GPU-accelerated inference restored after a single playbook run and automatic reboot.

## Hands-on Examples

### Example 1: Installing CUDA and Verifying GPU Access

This example walks through deploying the `nvidia` role against a test server and confirming that CUDA is installed and the GPU is visible to Docker.

**Setup:** You have a target host `gpu01` in your inventory with an NVIDIA RTX 4090, Ubuntu 22.04, and passwordless sudo configured. Your `group_vars/ai_servers.yml` sets `cuda_version: "12-6"`. SSH access from your control node works.

1. Create the role skeleton:

```bash
mkdir -p roles/nvidia/{tasks,handlers,templates,vars}
```

2. Write `roles/nvidia/vars/main.yml`:

```yaml
cuda_keyring_url: "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb"
cuda_keyring_deb: "/tmp/cuda-keyring_1.1-1_all.deb"
```

3. Write `roles/nvidia/tasks/main.yml` (abbreviated to the key tasks):

```yaml
- name: Download CUDA keyring
  ansible.builtin.get_url:
    url: "{{ cuda_keyring_url }}"
    dest: "{{ cuda_keyring_deb }}"
    mode: "0644"

- name: Install CUDA keyring
  ansible.builtin.apt:
    deb: "{{ cuda_keyring_deb }}"

- name: Install cuda-drivers and cuda-toolkit
  ansible.builtin.apt:
    name:
      - cuda-drivers
      - "cuda-toolkit-{{ cuda_version }}"
    state: present
    update_cache: true
  register: cuda_install

- name: Reboot if CUDA was newly installed
  ansible.builtin.reboot:
    reboot_timeout: 300
  when: cuda_install.changed
```

4. Write `roles/nvidia/handlers/main.yml`:

```yaml
- name: reboot host
  ansible.builtin.reboot:
    reboot_timeout: 300
```

5. Run the role in check mode first to confirm tasks resolve without errors:

```bash
ansible-playbook site.yml --tags nvidia --check -i inventory/hosts.ini
```

Expected output (check mode):

```
PLAY [Deploy complete AI inference stack] ************************************

TASK [nvidia : Download CUDA keyring] ****************************************
changed: [gpu01]

TASK [nvidia : Install CUDA keyring] *****************************************
changed: [gpu01]

TASK [nvidia : Install cuda-drivers and cuda-toolkit] ************************
changed: [gpu01]

PLAY RECAP *******************************************************************
gpu01  : ok=3  changed=3  unreachable=0  failed=0  skipped=0
```

6. Run for real, then verify:

```bash
ansible-playbook site.yml --tags nvidia -i inventory/hosts.ini
ansible gpu01 -m command -a "nvidia-smi" -i inventory/hosts.ini
```

Expected output from `nvidia-smi`:

```
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 560.35.03   Driver Version: 560.35.03   CUDA Version: 12.6     |
|-----------------------------------------+------------------------+----------------------+
| GPU  Name           Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
|   0  NVIDIA RTX 4090       Off  |  00000000:01:00.0  Off |                  Off |
```

7. Verify GPU access from Docker:

```bash
ansible gpu01 -m command \
  -a "docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi" \
  -i inventory/hosts.ini
```

Expected: same `nvidia-smi` table as above, confirming Docker has GPU passthrough.

---

### Example 2: Deploying Ollama and Pulling Models Idempotently

This example deploys the Ollama binary, starts the systemd service, and pulls two models while demonstrating that a second playbook run skips the model downloads.

**Setup:** CUDA and Docker are already installed from Example 1. `group_vars/ai_servers.yml` contains `ollama_version: "v0.3.12"`, `ollama_sha256: "<sha256-from-releases-page>"`, and `ollama_models: ["llama3.2", "nomic-embed-text"]`.

1. Create the role and templates directory:

```bash
mkdir -p roles/ollama/{tasks,handlers,templates,defaults}
```

2. Write `roles/ollama/defaults/main.yml`:

```yaml
ollama_version: "v0.3.12"
ollama_host: "0.0.0.0"
ollama_num_parallel: 1
ollama_models: []
```

3. Write `roles/ollama/handlers/main.yml`:

```yaml
- name: reload systemd
  ansible.builtin.systemd:
    daemon_reload: true

- name: restart ollama
  ansible.builtin.systemd:
    name: ollama
    state: restarted
```

4. Run the playbook with only the `ollama` and `models` tags:

```bash
ansible-playbook site.yml --tags "ollama,models" -i inventory/hosts.ini
```

Expected output (first run — both models absent):

```
TASK [ollama : Download Ollama binary] ***************************************
changed: [gpu01]

TASK [ollama : Deploy Ollama systemd unit file] ******************************
changed: [gpu01]

TASK [ollama_models : Check which models are already present] ****************
ok: [gpu01] => (item=llama3.2)
ok: [gpu01] => (item=nomic-embed-text)

TASK [ollama_models : Pull missing LLM models] *******************************
changed: [gpu01] => (item={'item': 'llama3.2', 'stat': {'exists': False}, ...})
changed: [gpu01] => (item={'item': 'nomic-embed-text', 'stat': {'exists': False}, ...})

PLAY RECAP *******************************************************************
gpu01  : ok=12  changed=4  unreachable=0  failed=0  skipped=0
```

5. Run the playbook a second time immediately after:

Expected output (second run — both models present):

```
TASK [ollama : Download Ollama binary] ***************************************
ok: [gpu01]

TASK [ollama_models : Check which models are already present] ****************
ok: [gpu01] => (item=llama3.2)
ok: [gpu01] => (item=nomic-embed-text)

TASK [ollama_models : Pull missing LLM models] *******************************
skipped: [gpu01] => (item={'item': 'llama3.2', 'stat': {'exists': True}, ...})
skipped: [gpu01] => (item={'item': 'nomic-embed-text', 'stat': {'exists': True}, ...})

PLAY RECAP *******************************************************************
gpu01  : ok=10  changed=0  unreachable=0  failed=0  skipped=2
```

The zero `changed` count on the second run confirms full idempotency. No models were re-downloaded, no services restarted unnecessarily.

---

### Example 3: Rendering the Nginx Reverse Proxy Config with TLS

This example renders the Nginx configuration from the Jinja2 template, validates it, and confirms that HTTPS access routes correctly to Open WebUI.

**Setup:** Open WebUI is running on `127.0.0.1:8080`. TLS certificates are already on the server at `/etc/ssl/ai-stack/fullchain.pem` and `/etc/ssl/ai-stack/privkey.pem` (from Let's Encrypt or your internal CA). Variables `nginx_server_name`, `nginx_ssl_cert_path`, `nginx_ssl_key_path`, and `ollama_api_key` are defined in `group_vars/ai_servers.yml` (with the API key in the vault file).

1. Define variables in `group_vars/ai_servers.yml`:

```yaml
nginx_server_name: ai.example.internal
nginx_ssl_cert_path: /etc/ssl/ai-stack/fullchain.pem
nginx_ssl_key_path: /etc/ssl/ai-stack/privkey.pem
```

2. Define in `vars/secrets.yml` (vault-encrypted):

```yaml
ollama_api_key: "supersecretkey123"
webui_secret_key: "anothersecretkey456"
```

3. Run the nginx role:

```bash
ansible-playbook site.yml --tags nginx -i inventory/hosts.ini \
  --vault-password-file ~/.vault_pass.txt
```

Expected output:

```
TASK [nginx : Deploy Nginx AI stack configuration] ***************************
changed: [gpu01]

TASK [nginx : Enable Nginx AI stack site] ************************************
changed: [gpu01]

RUNNING HANDLER [nginx : reload nginx] ***************************************
changed: [gpu01]

PLAY RECAP *******************************************************************
gpu01  : ok=8  changed=3  unreachable=0  failed=0  skipped=0
```

4. Verify HTTPS routing from the control node:

```bash
curl -sk https://ai.example.internal/ | head -5
```

Expected: the first five lines of the Open WebUI HTML response, confirming TLS termination and proxy routing are working.

5. Confirm the Ollama API is protected:

```bash
# Without key — expect 403
curl -sk https://ai.example.internal/api/ollama/api/tags

# With correct key — expect JSON list of models
curl -sk -H "X-API-Key: supersecretkey123" \
  https://ai.example.internal/api/ollama/api/tags
```

Expected: first `curl` returns HTTP 403; second returns JSON with `{"models": [...]}`.

---

### Example 4: Full Stack Smoke Test with `uri` Module

After a complete provisioning run, this example uses Ansible's `uri` module from the control node to verify every service in the stack is responding correctly — a lightweight integration test you can add to your CI pipeline.

**Setup:** The full playbook has completed. All roles have run. Inventory has `ai_servers` group with `gpu01`.

1. Create `smoke_test.yml` in the playbook root:

```yaml
- name: AI Stack smoke test
  hosts: ai_servers
  become: false
  gather_facts: false

  vars_files:
    - vars/secrets.yml

  tasks:
    - name: Check Ollama API
      ansible.builtin.uri:
        url: http://127.0.0.1:11434/api/tags
        return_content: true
        status_code: 200
      register: ollama_check

    - name: Assert at least one model is loaded
      ansible.builtin.assert:
        that:
          - ollama_check.json.models | length > 0
        fail_msg: "Ollama has no models loaded"
        success_msg: "Ollama OK — {{ ollama_check.json.models | length }} model(s) available"

    - name: Check Open WebUI
      ansible.builtin.uri:
        url: http://127.0.0.1:8080
        status_code: 200

    - name: Check FastAPI health endpoint
      ansible.builtin.uri:
        url: http://127.0.0.1:8000/health
        status_code: 200

    - name: Check HTTPS via Nginx
      ansible.builtin.uri:
        url: "https://{{ nginx_server_name }}/"
        validate_certs: false
        status_code: 200
      delegate_to: localhost
```

2. Run the smoke test:

```bash
ansible-playbook smoke_test.yml -i inventory/hosts.ini \
  --vault-password-file ~/.vault_pass.txt
```

Expected output:

```
TASK [Check Ollama API] ******************************************************
ok: [gpu01]

TASK [Assert at least one model is loaded] ***********************************
ok: [gpu01] => {
    "msg": "Ollama OK — 2 model(s) available"
}

TASK [Check Open WebUI] ******************************************************
ok: [gpu01]

TASK [Check FastAPI health endpoint] *****************************************
ok: [gpu01]

TASK [Check HTTPS via Nginx] *************************************************
ok: [gpu01]

PLAY RECAP *******************************************************************
gpu01  : ok=5  changed=0  unreachable=0  failed=0  skipped=0
```

All five checks passing confirms the full stack is operational end-to-end.

## Common Pitfalls

### 1. Installing `docker.io` Instead of `docker-ce`

**Description:** Using `apt: name=docker.io` instead of adding Docker's official APT repository and installing `docker-ce`.

**Why it happens:** `docker.io` is in the Ubuntu universe repository and requires no additional APT configuration, which makes it the path of least resistance.

**Incorrect pattern:**
```yaml
- name: Install Docker
  ansible.builtin.apt:
    name: docker.io
    state: present
```

**Correct pattern:**
```yaml
- name: Install Docker CE from official repository
  ansible.builtin.apt:
    name:
      - docker-ce
      - docker-ce-cli
      - containerd.io
    state: present
```

The `docker.io` package in Ubuntu 22.04 ships Docker 20.x, which lacks `docker compose` (plugin) support, does not receive security updates at the same cadence as Docker CE, and may be incompatible with the NVIDIA Container Toolkit configuration steps.

---

### 2. Running `ollama pull` Without a `wait_for` Preceding It

**Description:** Placing the model pull task immediately after the `systemd: state=started` task for Ollama without waiting for the API socket to be ready.

**Why it happens:** The `systemd` task returns `ok` as soon as systemd marks the unit as `active (running)`, but Ollama's HTTP server takes 2–5 additional seconds to bind to port 11434.

**Incorrect pattern:**
```yaml
- name: Start Ollama
  ansible.builtin.systemd:
    name: ollama
    state: started

- name: Pull model  # fails with "connection refused" ~40% of the time
  ansible.builtin.command:
    cmd: ollama pull llama3.2
```

**Correct pattern:**
```yaml
- name: Start Ollama
  ansible.builtin.systemd:
    name: ollama
    state: started

- name: Wait for Ollama API port
  ansible.builtin.wait_for:
    host: 127.0.0.1
    port: 11434
    delay: 3
    timeout: 60

- name: Pull model
  ansible.builtin.command:
    cmd: ollama pull llama3.2
```

---

### 3. Omitting `async`/`poll` on Model Pull Commands

**Description:** Running `ollama pull` for a large model (7B+) as a synchronous `command` task without `async` and `poll`.

**Why it happens:** `async` feels like added complexity when you are used to shell scripts that simply wait for commands to finish.

**Incorrect pattern:**
```yaml
- name: Pull large model (blocks SSH for 30+ minutes)
  ansible.builtin.command:
    cmd: ollama pull mistral
```

**Correct pattern:**
```yaml
- name: Pull large model asynchronously
  ansible.builtin.command:
    cmd: ollama pull mistral
  async: 3600
  poll: 30
```

Without `async`, Ansible holds the SSH connection open for the entire download. Most SSH server configurations (and cloud provider firewalls) drop idle connections after 10–20 minutes, causing the task to fail with a broken pipe even though the download continues on the server.

---

### 4. Using `changed_when: false` on Model Pull Tasks

**Description:** Suppressing the `changed` status of `ollama pull` tasks to "clean up" the play recap, preventing downstream handlers from firing.

**Why it happens:** `ollama pull` always produces output and Ansible marks it `changed` by default, which makes the play recap look noisy on re-runs.

**Incorrect pattern:**
```yaml
- name: Pull model
  ansible.builtin.command:
    cmd: ollama pull llama3.2
  changed_when: false   # suppresses notifications incorrectly
```

**Correct pattern:**
Use the `stat` pre-check from the Key Concepts section instead. Skip the pull entirely when the model is present, and use `changed_when: true` on pulls that actually execute. The `stat` check produces a clean recap without hiding real changes.

---

### 5. Storing Secrets in `group_vars` Plaintext

**Description:** Defining `webui_secret_key`, `ollama_api_key`, or database passwords as plaintext YAML in `group_vars/all.yml` or `group_vars/ai_servers.yml`.

**Why it happens:** It is the fastest way to get variables defined, and encryption adds an extra step.

**Incorrect pattern:**
```yaml
# group_vars/ai_servers.yml  — committed to Git in plaintext
webui_secret_key: "myrealpassword123"
ollama_api_key: "anotherapikey456"
```

**Correct pattern:**
```bash
# Create and encrypt the secrets file
ansible-vault create vars/secrets.yml
# Add to vars_files in your playbook
```

A plaintext secret in a Git repository — even a private one — can be exfiltrated through CI logs, `git log -p` output, repository backup leaks, or accidental public visibility changes.

---

### 6. Not Using `validate:` on Nginx Template Tasks

**Description:** Writing the rendered Nginx config directly to `/etc/nginx/sites-available/` without the `validate` parameter.

**Why it happens:** The `validate` parameter is not prominently documented alongside the `template` module examples.

**Incorrect pattern:**
```yaml
- name: Deploy Nginx config
  ansible.builtin.template:
    src: ai-stack.conf.j2
    dest: /etc/nginx/sites-available/ai-stack.conf
  notify: reload nginx
```

**Correct pattern:**
```yaml
- name: Deploy Nginx config
  ansible.builtin.template:
    src: ai-stack.conf.j2
    dest: /etc/nginx/sites-available/ai-stack.conf
    validate: nginx -t -c /etc/nginx/nginx.conf
  notify: reload nginx
```

A bad template variable (a missing `nginx_server_name`, an incorrect path) produces a syntactically invalid Nginx config. Without `validate`, the config is written, the handler fires, and `nginx -s reload` loads the broken config, returning 502 to every user. The `validate` parameter catches this before writing.

---

### 7. Forgetting `daemon_reload: true` After Deploying New Systemd Units

**Description:** Deploying a new `.service` file with `template` and then calling `systemd: state=started` without `daemon_reload: true`, causing systemd to start the old cached unit or raise an error.

**Why it happens:** Developers familiar with shell workflows remember to run `systemctl daemon-reload` manually but forget to encode it in the Ansible task.

**Incorrect pattern:**
```yaml
- name: Deploy FastAPI unit
  ansible.builtin.template:
    src: fastapi.service.j2
    dest: /etc/systemd/system/fastapi.service

- name: Start FastAPI
  ansible.builtin.systemd:
    name: fastapi
    state: started
    # Missing daemon_reload: true
```

**Correct pattern:**
```yaml
- name: Deploy FastAPI unit
  ansible.builtin.template:
    src: fastapi.service.j2
    dest: /etc/systemd/system/fastapi.service
  notify:
    - reload systemd
    - restart fastapi
```

With a handler that calls `ansible.builtin.systemd: daemon_reload: true`, systemd re-reads all unit files before the restart, ensuring it picks up the new definition.

## Summary

- A single Ansible playbook can provision a complete GPU-accelerated AI inference stack — NVIDIA drivers, CUDA, Docker, Ollama, Open WebUI, FastAPI, and Nginx — by orchestrating roles in dependency order and using handlers to coordinate service restarts safely.
- Idempotency in AI stack deployments requires deliberate engineering: using `stat` to skip model pulls that already completed, `checksum` on downloaded binaries, `changed_when` tied to real change signals, and `validate` on config templates before writing.
- Long-running operations such as model downloads must use `async` and `poll` to avoid SSH timeout failures; a `wait_for` task must gate any task that connects to a service port so it does not race the service startup.
- Secrets — API keys, TLS private keys, web UI signing secrets — must live in Ansible Vault encrypted files, never in plaintext inventory or role defaults, because AI inference servers are high-value targets with direct access to expensive GPU compute.
- Post-task `uri` health checks and a dedicated smoke-test playbook turn deployment verification from a manual checklist into an automated assertion that runs as part of every provisioning job.

## Further Reading

- [Ansible `apt` module documentation](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/apt_module.html) — complete parameter reference for the `apt` module including `deb`, `update_cache`, `cache_valid_time`, and `state` options essential for CUDA and Docker repository management.
- [NVIDIA CUDA Installation Guide for Linux](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/) — official NVIDIA documentation covering the network and local installer methods, driver version compatibility matrices, and post-installation verification steps for Ubuntu.
- [NVIDIA Container Toolkit Installation Guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) — step-by-step guide for installing and configuring the NVIDIA Container Toolkit with Docker, including the `nvidia-ctk runtime configure` command and `daemon.json` settings referenced in this module.
- [Ollama GitHub Releases](https://github.com/ollama/ollama/releases) — the authoritative source for versioned Ollama binary downloads, SHA256 checksums, and the changelog — required reading before pinning `ollama_version` and `ollama_sha256` in your inventory.
- [Ansible `async` and `poll` — Asynchronous Actions and Polling](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_async.html) — official documentation explaining how `async`, `poll`, and `async_status` work together, with patterns for fire-and-forget tasks and status checking during long operations like model downloads.
- [Open WebUI Documentation — Getting Started](https://docs.openwebui.com/getting-started/) — covers environment variables, volume mounts, and network configuration for the Open WebUI Docker container, including `OLLAMA_BASE_URL` and `WEBUI_SECRET_KEY` settings used in the `docker_container` task in this module.
- [Nginx `proxy_pass` and Upstream Configuration](https://nginx.org/en/docs/http/ngx_http_proxy_module.html) — official Nginx documentation for the `proxy_pass`, `proxy_set_header`, and `upstream` directives used in the reverse proxy template, including `keepalive` tuning and WebSocket upgrade headers required by Open WebUI.
- [Ansible `template` module — `validate` parameter](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/template_module.html) — reference for the `validate` parameter pattern, which is critical for safely deploying Nginx configurations and any other service configuration file where a syntax error causes an immediate outage.
