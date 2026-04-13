# Module 2: Roles and Variables
> Subject: Ansible | Difficulty: Intermediate | Estimated Time: 165 minutes

## Objective

After completing this module, you will be able to organize Ansible automation into reusable, self-contained **roles** and control behavior through a well-structured **variable system**. Specifically, you will: scaffold a role with `ansible-galaxy init`; populate the full role directory structure (`tasks`, `handlers`, `templates`, `files`, `vars`, `defaults`, `meta`); write Jinja2 templates using `{{ variable }}` interpolation, filters, and conditionals; deploy rendered templates with the `template` module; declare role dependencies in `meta/main.yml`; install and consume community roles from Ansible Galaxy; use `group_vars` and `host_vars` directories to target variables at specific inventory groups and hosts; explain the full variable precedence order and know when each level applies; write handlers and trigger them with `notify`; use `tags` for selective task execution; loop over lists and dictionaries with `loop`; and use `when:` conditionals to branch task execution. The running example throughout is an `ai_server` role that configures a GPU server from scratch, parameterized by model path, service port, and environment type.

## Prerequisites

- Completed Module 1: Ansible Fundamentals — you should be able to write a basic playbook, run it with `ansible-playbook`, and understand inventory files, ad-hoc commands, and the concept of modules
- Ansible 2.17 or later installed (`ansible --version`; current stable release is Ansible 2.18)
- A target host (VM, cloud instance, or a second machine) reachable over SSH with a configured inventory
- Python 3.10+ on both the control node and managed nodes
- Familiarity with YAML syntax — indentation errors are the most common source of failures
- Basic Linux administration knowledge: systemd service management, file paths, environment variables

## Key Concepts

### Variable Precedence: Who Wins?

Ansible resolves variables from many sources simultaneously. When the same variable is defined in multiple places, a strict precedence order determines which value wins. Understanding this order is essential — unexpected values at runtime almost always trace back to a precedence misunderstanding.

The order from **lowest** to **highest** precedence is:

```
 1  role defaults          (roles/ai_server/defaults/main.yml)
 2  inventory file vars    (vars in hosts/group in the inventory .ini or .yml file)
 3  inventory group_vars   (group_vars/all.yml, group_vars/gpu_servers.yml)
 4  inventory host_vars    (host_vars/gpu01.yml)
 5  playbook group_vars    (group_vars/ next to the playbook file)
 6  playbook host_vars     (host_vars/ next to the playbook file)
 7  host facts             (ansible_os_family, ansible_distribution, etc.)
 8  play vars              (vars: block inside a play)
 9  play vars_prompt       (interactive prompts)
10  play vars_files        (vars_files: block in a play)
11  role vars              (roles/ai_server/vars/main.yml)
12  block vars             (vars: inside a block: directive)
13  task vars              (vars: on an individual task)
14  include_vars           (ansible.builtin.include_vars task)
15  set_facts / registered vars
16  role and include params (vars passed when including a role)
17  extra vars             (-e / --extra-vars on the command line)  ← HIGHEST
```

The practical takeaway has two parts. First, `defaults/main.yml` is the right place for safe, overridable defaults in a role — any operator can change them without editing the role itself. Second, `vars/main.yml` is for constants the role depends on internally and does not want callers to change — those values override nearly everything short of extra vars. Extra vars (`-e`) are the "nuclear option" used by CI pipelines or for emergency one-off overrides; they override everything else.

```bash
# Extra vars override everything — useful for CI pipelines or one-off runs
ansible-playbook site.yml -e "env_type=prod ai_service_port=8080"

# Multiple extra vars can be passed as a YAML/JSON file
ansible-playbook site.yml -e @overrides.yml
```

### group_vars and host_vars Directory Structure

Rather than stuffing all variables into the inventory file, Ansible automatically loads YAML files from two special directories: `group_vars/` and `host_vars/`. Both directories can sit either next to the inventory file or next to the playbook. Ansible merges both locations.

Files in `group_vars/` apply to all hosts in the named group. The special group name `all` applies to every host in the inventory. Files in `host_vars/` apply to exactly one host, identified by the hostname or IP address used in the inventory.

Each entry can be a flat file or a directory. If you use a directory, Ansible loads every `.yml` file inside it — useful for splitting large variable sets into logical files (e.g., `group_vars/gpu_servers/network.yml` and `group_vars/gpu_servers/ai_services.yml`).

```
inventory/
├── hosts.yml                   # Inventory file
├── group_vars/
│   ├── all.yml                 # Applies to every host
│   ├── gpu_servers.yml         # Applies to the gpu_servers group
│   └── gpu_servers/            # Directory form — all files loaded
│       ├── network.yml
│       └── ai_services.yml
└── host_vars/
    ├── gpu01.yml               # Applies only to host named gpu01
    └── gpu02.yml               # Applies only to host named gpu02
```

A concrete example for the `ai_server` use case:

```yaml
# inventory/group_vars/all.yml
ansible_user: ubuntu
ntp_server: pool.ntp.org

# inventory/group_vars/gpu_servers.yml
cuda_version: "12.4"
ai_model_base_path: /opt/models
ai_service_port: 7860
env_type: dev

# inventory/host_vars/gpu01.yml
ai_service_port: 8080          # Override port for this specific host
env_type: prod                 # This host is production
```

### Jinja2 Templating: Syntax, Filters, and Conditionals

Ansible uses the Jinja2 templating engine to evaluate variables and expressions. Jinja2 syntax appears in three places: inside `{{ }}` delimiters for variable substitution, inside `{% %}` delimiters for control flow (loops, conditionals), and inside `{# #}` delimiters for comments.

**Variable interpolation** is the most common use:

```yaml
# In a task
- name: Create model directory
  ansible.builtin.file:
    path: "{{ ai_model_base_path }}/{{ model_name }}"
    state: directory
    mode: "0755"
```

**Filters** transform variable values. Ansible ships with all standard Jinja2 filters plus many Ansible-specific ones:

```yaml
# default() — use a fallback value if the variable is undefined
log_level: "{{ custom_log_level | default('info') }}"

# upper / lower — case conversion
service_name: "{{ app_name | upper }}"

# int / float — type coercion
worker_count: "{{ cpu_count | int * 2 }}"

# join — combine a list into a string
gpu_list: "{{ detected_gpus | join(',') }}"

# selectattr — filter a list of dicts
active_ports: "{{ services | selectattr('enabled', 'equalto', true) | map(attribute='port') | list }}"

# to_json / to_yaml — serialize a variable for config file injection
config_block: "{{ service_config | to_json }}"
```

**Conditionals in templates** use Jinja2 `{% if %}` blocks. This is especially powerful inside the `template` module — the template file itself can contain logic:

```jinja2
{# templates/ai_service.conf.j2 #}
[service]
model_path = {{ ai_model_base_path }}/{{ model_name }}
port       = {{ ai_service_port }}
workers    = {{ ai_worker_count | default(4) }}

{% if env_type == 'prod' %}
log_level  = warning
enable_tls = true
tls_cert   = /etc/ssl/certs/ai_service.crt
{% else %}
log_level  = debug
enable_tls = false
{% endif %}

{% for gpu_id in range(gpu_count | int) %}
device_{{ gpu_id }} = cuda:{{ gpu_id }}
{% endfor %}
```

### The template Module

The `ansible.builtin.template` module reads a Jinja2 template file from the role's `templates/` directory, evaluates all variables and expressions against the current host's variable context, and writes the rendered result to a path on the managed node. It is the standard tool for generating any configuration file whose content depends on host-specific data.

The `template` module is distinct from the `copy` module. Use `copy` when the file content is identical for every host. Use `template` when the content must vary by host or group.

```yaml
- name: Deploy AI service configuration
  ansible.builtin.template:
    src: ai_service.conf.j2      # Relative to roles/ai_server/templates/
    dest: /etc/ai_service/ai_service.conf
    owner: ai_service
    group: ai_service
    mode: "0640"
  notify: Restart ai_service     # Trigger a handler if the file changes
```

Key parameters:
- `src` — path to the `.j2` template file, relative to the role's `templates/` directory
- `dest` — absolute path on the remote host
- `owner` / `group` / `mode` — file ownership and permissions, set atomically with the content
- `validate` — an optional command run against the rendered file before it is moved into place (e.g., `validate: nginx -t -c %s`)
- `backup: true` — keeps a timestamped backup of the previous file on the remote host

### Role Directory Structure

A role is a self-contained unit of automation with a fixed directory layout that Ansible understands automatically. When you reference a role in a playbook, Ansible loads each subdirectory that exists according to a well-defined convention — you never have to import individual task files manually.

```
roles/
└── ai_server/
    ├── defaults/
    │   └── main.yml        # Lowest-priority variable defaults (overridable by callers)
    ├── vars/
    │   └── main.yml        # Higher-priority variables (role internals, not for callers)
    ├── tasks/
    │   ├── main.yml        # Entry point — include_tasks calls sub-files from here
    │   ├── packages.yml
    │   ├── cuda.yml
    │   └── service.yml
    ├── handlers/
    │   └── main.yml        # Handlers triggered by notify:
    ├── templates/
    │   └── ai_service.conf.j2
    ├── files/
    │   └── ai_service.service   # Static files copied verbatim with the copy module
    ├── meta/
    │   └── main.yml        # Role metadata: author, dependencies, Galaxy tags
    └── README.md
```

**defaults/main.yml** is where you define every variable a caller might reasonably want to override. Always provide sensible defaults so the role works out-of-the-box with zero caller configuration.

**vars/main.yml** is for internal constants — package names, fixed directory paths, service user names — that callers should not change. Because `vars/main.yml` has higher precedence than `defaults/main.yml`, and much higher precedence than `group_vars`, values here are effectively locked unless the caller uses extra vars.

**tasks/main.yml** is the entry point. For roles with more than a handful of tasks, split tasks into topical sub-files and use `ansible.builtin.include_tasks` to compose them:

```yaml
# roles/ai_server/tasks/main.yml
- name: Install system packages
  ansible.builtin.include_tasks: packages.yml

- name: Configure CUDA
  ansible.builtin.include_tasks: cuda.yml
  when: install_cuda | bool

- name: Deploy AI service
  ansible.builtin.include_tasks: service.yml
```

### Creating a Role with ansible-galaxy init

The `ansible-galaxy` command-line tool scaffolds the full directory structure for a new role in one command. It creates every standard subdirectory and populates each `main.yml` with a commented placeholder so you never have to remember the layout.

```bash
# Create a new role skeleton in the current roles/ directory
ansible-galaxy init roles/ai_server

# The command produces this output:
# - roles/ai_server was created successfully
```

After running this command, the full skeleton exists immediately:

```bash
# Verify the created structure
find roles/ai_server -type f

# Output:
# roles/ai_server/README.md
# roles/ai_server/defaults/main.yml
# roles/ai_server/files/.gitkeep      (may vary by Ansible version)
# roles/ai_server/handlers/main.yml
# roles/ai_server/meta/main.yml
# roles/ai_server/tasks/main.yml
# roles/ai_server/templates/.gitkeep  (may vary by Ansible version)
# roles/ai_server/tests/inventory
# roles/ai_server/tests/test.yml
# roles/ai_server/vars/main.yml
```

To install a community role from Ansible Galaxy rather than writing one from scratch:

```bash
# Install a specific role by its Galaxy name
ansible-galaxy install geerlingguy.nvidia

# Install a list of roles declared in a requirements file
ansible-galaxy install -r requirements.yml

# requirements.yml format
# roles:
#   - name: geerlingguy.nvidia
#     version: "4.2.0"
#   - name: geerlingguy.pip
#     version: "2.2.0"
```

Installed Galaxy roles land in `~/.ansible/roles/` by default, or in a `roles/` directory local to your project if you set `roles_path` in `ansible.cfg`.

### Role Dependencies and meta/main.yml

The `meta/main.yml` file serves two purposes: it declares Galaxy metadata (author, license, supported platforms) and it specifies **role dependencies** — other roles that must run before this one. Ansible resolves and executes all dependencies automatically and in the correct order.

```yaml
# roles/ai_server/meta/main.yml
galaxy_info:
  role_name: ai_server
  author: your_username
  description: Configures a GPU server to run AI inference services
  license: MIT
  min_ansible_version: "2.17"
  platforms:
    - name: Ubuntu
      versions:
        - jammy
        - noble

dependencies:
  - role: geerlingguy.pip
    vars:
      pip_install_packages:
        - name: torch
          version: "2.3.0"
  - role: geerlingguy.nvidia
    vars:
      nvidia_driver_version: "550"
```

When your playbook runs the `ai_server` role, Ansible first runs `geerlingguy.pip` and `geerlingguy.nvidia` (each with the vars specified), then runs `ai_server` itself. Dependency resolution is recursive — if `geerlingguy.nvidia` has its own dependencies, those run first too. Ansible deduplicates: if a dependency appears multiple times in the graph, it runs only once unless `allow_duplicates: true` is set in the dependent role's `meta/main.yml`.

### Handlers: Trigger Actions on Change

A handler is a task that runs only when notified by another task, and only if that notifying task reported a change (i.e., it actually modified something on the host). Handlers are the standard pattern for restarting services after configuration changes — you never want to restart a service unconditionally on every playbook run.

```yaml
# roles/ai_server/handlers/main.yml
- name: Restart ai_service
  ansible.builtin.systemd:
    name: ai_service
    state: restarted
    daemon_reload: true

- name: Reload nginx
  ansible.builtin.systemd:
    name: nginx
    state: reloaded
```

A task triggers a handler using the `notify:` key. The value must exactly match the handler's `name:`:

```yaml
# roles/ai_server/tasks/service.yml
- name: Deploy AI service configuration
  ansible.builtin.template:
    src: ai_service.conf.j2
    dest: /etc/ai_service/ai_service.conf
    owner: ai_service
    group: ai_service
    mode: "0640"
  notify: Restart ai_service

- name: Deploy nginx virtual host
  ansible.builtin.template:
    src: nginx_ai_service.conf.j2
    dest: /etc/nginx/sites-available/ai_service.conf
    mode: "0644"
  notify: Reload nginx
```

By default, handlers run once at the end of the entire play, after all tasks have completed. Multiple tasks can `notify` the same handler — it still only runs once. If you need a handler to run immediately (before subsequent tasks), use `ansible.builtin.meta: flush_handlers`:

```yaml
- name: Deploy TLS certificate
  ansible.builtin.copy:
    src: ai_service.crt
    dest: /etc/ssl/certs/ai_service.crt
  notify: Restart ai_service

- name: Flush handlers before continuing
  ansible.builtin.meta: flush_handlers

- name: Verify service is responding on HTTPS
  ansible.builtin.uri:
    url: "https://{{ inventory_hostname }}:{{ ai_service_port }}/health"
    status_code: 200
```

### Tags for Selective Task Execution

Tags let you label individual tasks, blocks, or entire role inclusions so you can run only the labeled subset on a given `ansible-playbook` invocation. This is critical for large playbooks — rerunning only the "config" tasks against a fleet of already-provisioned servers is far faster than rerunning the full provisioning sequence.

```yaml
# Tagging individual tasks
- name: Install CUDA toolkit
  ansible.builtin.apt:
    name: "cuda-toolkit-{{ cuda_version | replace('.', '-') }}"
    state: present
  tags:
    - cuda
    - packages

- name: Deploy AI service config
  ansible.builtin.template:
    src: ai_service.conf.j2
    dest: /etc/ai_service/ai_service.conf
  notify: Restart ai_service
  tags:
    - config
    - ai_service

# Tagging a block
- name: CUDA installation block
  tags: cuda
  block:
    - name: Add CUDA apt repository
      ansible.builtin.apt_repository:
        repo: "deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64 /"
        state: present

    - name: Install CUDA toolkit
      ansible.builtin.apt:
        name: "cuda-toolkit-{{ cuda_version | replace('.', '-') }}"
        state: present
```

Running with tags:

```bash
# Run only tasks tagged 'config'
ansible-playbook site.yml --tags config

# Run tasks tagged 'cuda' or 'packages'
ansible-playbook site.yml --tags "cuda,packages"

# Run everything except tasks tagged 'cuda' (skip CUDA install on re-runs)
ansible-playbook site.yml --skip-tags cuda

# List all tags defined in a playbook without running it
ansible-playbook site.yml --list-tags
```

Two special built-in tags exist: `always` (task runs even when other tags are specified) and `never` (task never runs unless explicitly included with `--tags never`). The `never` tag is useful for destructive or slow tasks like database resets.

### Loops: Iterating Over Lists and Dictionaries

The `loop:` keyword (the modern replacement for the deprecated `with_items:`) lets a single task execute repeatedly over a list of items. On each iteration, the current item is available as `{{ item }}`.

```yaml
# Loop over a flat list of package names
- name: Install AI service dependencies
  ansible.builtin.apt:
    name: "{{ item }}"
    state: present
  loop:
    - python3-pip
    - python3-venv
    - git
    - curl
    - build-essential

# Loop over a list of dictionaries
- name: Create model directories
  ansible.builtin.file:
    path: "{{ ai_model_base_path }}/{{ item.name }}"
    state: directory
    owner: ai_service
    group: ai_service
    mode: "{{ item.mode | default('0755') }}"
  loop:
    - name: llama3
      mode: "0750"
    - name: stable-diffusion
      mode: "0750"
    - name: whisper

# Loop over a variable defined elsewhere (e.g., in group_vars)
- name: Open firewall ports for AI services
  ansible.builtin.ufw:
    rule: allow
    port: "{{ item }}"
    proto: tcp
  loop: "{{ ai_service_ports }}"

# loop_control — customize the label shown in output (avoids verbose dict dumps)
- name: Configure systemd service environments
  ansible.builtin.lineinfile:
    path: /etc/systemd/system/ai_service.service
    regexp: "^Environment={{ item.key }}"
    line: "Environment={{ item.key }}={{ item.value }}"
  loop: "{{ ai_env_vars | dict2items }}"
  loop_control:
    label: "{{ item.key }}"
  notify: Restart ai_service
```

The `with_items:` syntax still works in Ansible 2.17 and 2.18 but is considered legacy. All new playbooks should use `loop:`. The `loop:` keyword does not flatten nested lists — if you need that behavior, use the `flatten` filter: `loop: "{{ nested_list | flatten(levels=1) }}"`.

### Conditionals: The when: Clause

The `when:` clause controls whether a task runs at all on a given host. It accepts a Jinja2 expression that evaluates to a boolean. When the expression is false (or the variable is undefined), the task is skipped and Ansible reports "skipping" for that host.

```yaml
# Run only on Ubuntu/Debian hosts (uses a gathered fact)
- name: Install packages via apt
  ansible.builtin.apt:
    name: python3-pip
    state: present
  when: ansible_os_family == "Debian"

# Run only in production environments (uses a custom variable)
- name: Enable TLS on AI service
  ansible.builtin.template:
    src: ai_service_tls.conf.j2
    dest: /etc/ai_service/tls.conf
  when: env_type == "prod"

# Multiple conditions — all must be true (AND logic)
- name: Install GPU monitoring tools
  ansible.builtin.apt:
    name: nvidia-smi
    state: present
  when:
    - ansible_os_family == "Debian"
    - install_cuda | bool
    - gpu_count | int > 0

# OR logic — use the 'or' operator in a single expression
- name: Restart service in dev or staging
  ansible.builtin.systemd:
    name: ai_service
    state: restarted
  when: env_type == "dev" or env_type == "staging"

# Check if a variable is defined before using it
- name: Configure optional proxy
  ansible.builtin.template:
    src: proxy.conf.j2
    dest: /etc/ai_service/proxy.conf
  when: http_proxy is defined and http_proxy | length > 0
```

A `when:` clause on a block applies to every task in the block. This avoids repeating the same condition on dozens of individual tasks:

```yaml
- name: Production-only hardening
  when: env_type == "prod"
  block:
    - name: Disable debug endpoints
      ansible.builtin.lineinfile:
        path: /etc/ai_service/ai_service.conf
        regexp: "^debug_endpoint"
        state: absent

    - name: Set restrictive file permissions
      ansible.builtin.file:
        path: /etc/ai_service
        recurse: true
        mode: "o-rwx"
```

## Best Practices

1. **Put all externally overridable variables in `defaults/main.yml`, not `vars/main.yml`.** Defaults have the lowest precedence, so operators can override them via `group_vars`, `host_vars`, or `-e` without touching the role source. Values in `vars/main.yml` silently override `group_vars`, which causes hard-to-debug surprises.

2. **Name handlers as verb-noun sentences describing the desired end state, not the action taken.** Use "Restart ai_service" rather than "ai_service restart" — this reads naturally in the `notify:` declaration and makes playbook output self-documenting.

3. **Never use bare variable names in `when:` clauses for boolean checks.** Write `when: install_cuda | bool` rather than `when: install_cuda`, because Ansible's YAML parser may load the string `"false"` as the string literal rather than the boolean `False`, causing the condition to evaluate as truthy unexpectedly.

4. **Use `loop_control.label` whenever looping over dictionaries or complex objects.** Without it, Ansible prints the entire dictionary on each iteration, making output unreadably verbose and obscuring actual errors.

5. **Pin community role versions in `requirements.yml`.** Galaxy roles are updated independently of your playbook. A role update can break your automation. `version: "4.2.0"` in `requirements.yml` ensures repeatable installs.

6. **Split large `tasks/main.yml` files using `include_tasks` with topic-based sub-files.** A tasks file longer than roughly 50 lines is a sign it should be split. `include_tasks` is dynamic (evaluated at runtime), which also lets you conditionally include entire sub-files with a `when:` on the include statement.

7. **Use the `validate:` parameter on the `template` module for any configuration file that has a syntax checker.** For nginx configs, `validate: nginx -t -c %s` catches Jinja2 rendering errors that produce invalid config before the file is written, preventing a broken service restart.

8. **Commit `roles/requirements.yml` to version control but not the installed role directories themselves.** Add the Galaxy roles installation directory to `.gitignore`. This keeps your repo lean and ensures the install step is explicit and reproducible.

9. **Apply meaningful tags at the block level rather than duplicating tags on every task.** A block tag propagates to all tasks within it, keeping tag declarations DRY and making the tag taxonomy easier to audit.

10. **Always quote strings that contain colons or leading `{` in YAML values.** `dest: /etc/ai_service/{{ model_name }}.conf` must be written as `dest: "/etc/ai_service/{{ model_name }}.conf"` — an unquoted value starting with `{` is parsed as a YAML mapping, causing a cryptic parse error.

## Use Cases

### Provisioning a Fleet of New GPU Servers for an LLM Inference Cluster

A team is deploying ten new NVIDIA H100 servers and needs each one configured identically: CUDA toolkit, Python virtual environment, model weights synced to the correct path, systemd service for the inference API, and nginx reverse proxy. Each server hosts a different model endpoint, so the model name and service port vary per host.

The `ai_server` role provides a single, tested blueprint for all ten servers. The `roles/ai_server/defaults/main.yml` file defines the model path base and default port. Each server's specific values are declared in `host_vars/gpuXX.yml`. The role's `meta/main.yml` declares the `geerlingguy.nvidia` dependency, so CUDA driver installation is handled automatically before the role's own tasks run. Running `ansible-playbook site.yml` provisions all ten servers in one command; re-running it is idempotent.

### Promoting Configuration Changes from Dev to Prod Without Code Duplication

The same `ai_server` role is used for both development and production environments, but production requires TLS, stricter log levels, and disabled debug endpoints. Rather than maintaining two separate playbooks, `env_type` is set to `dev` in `group_vars/dev_servers.yml` and to `prod` in `group_vars/prod_servers.yml`. The role's Jinja2 template emits different config blocks based on `env_type`, and `when: env_type == "prod"` conditionals gate the hardening tasks. Promotion consists of moving a host between inventory groups — no playbook code changes.

### Selective Configuration Updates Without Full Re-Provisioning

After a model is updated in production, only the service configuration needs to change — reinstalling CUDA drivers or recreating the virtual environment wastes time and risks disruption. Tasks that manage the config file and service restart are tagged `config`. The operator runs `ansible-playbook site.yml --tags config`, which skips all package installation and CUDA tasks, updates only the configuration file via the `template` module, and — because the file changed — triggers the "Restart ai_service" handler. The entire operation completes in seconds instead of minutes.

### Installing and Extending a Community Role for GPU Drivers

Writing NVIDIA driver installation from scratch is complex and error-prone. The team installs `geerlingguy.nvidia` from Ansible Galaxy via `ansible-galaxy install -r requirements.yml`, then declares it as a dependency in `ai_server`'s `meta/main.yml` with the required driver version passed as a role variable. The community role is treated as a black box. The team's own `ai_server` role focuses only on the application layer: model directories, service config, and the inference daemon. This separation means driver updates can be applied by bumping the version pin in `requirements.yml` without touching `ai_server` at all.

## Hands-on Examples

### Example 1: Scaffold and Populate the ai_server Role

You have a working Ansible project directory and want to create the `ai_server` role from scratch. This example takes you from an empty `roles/` directory to a role with defaults, variables, a template, and a basic task file.

1. Navigate to your Ansible project root and scaffold the role:

   ```bash
   mkdir -p roles
   ansible-galaxy init roles/ai_server
   ```

   Expected output:
   ```
   - roles/ai_server was created successfully
   ```

2. Define default variables in `roles/ai_server/defaults/main.yml`:

   ```yaml
   ---
   # roles/ai_server/defaults/main.yml

   # Base directory where model weights are stored
   ai_model_base_path: /opt/models

   # Port the inference API listens on
   ai_service_port: 7860

   # Environment type controls TLS, log verbosity, and debug endpoints
   env_type: dev

   # Name of the model this server hosts
   model_name: default_model

   # Number of GPU worker processes
   ai_worker_count: 4

   # Whether to install the CUDA toolkit
   install_cuda: true

   # CUDA version to install (major.minor)
   cuda_version: "12.4"
   ```

3. Define internal role constants in `roles/ai_server/vars/main.yml`:

   ```yaml
   ---
   # roles/ai_server/vars/main.yml

   # OS user that runs the AI service
   ai_service_user: ai_service

   # Systemd service name
   ai_service_name: ai_service

   # Configuration directory (not meant to be overridden)
   ai_config_dir: /etc/ai_service
   ```

4. Write the Jinja2 configuration template at `roles/ai_server/templates/ai_service.conf.j2`:

   ```jinja2
   # AI Service Configuration
   # Generated by Ansible — do not edit manually.
   # Host: {{ inventory_hostname }} | Environment: {{ env_type }}

   [server]
   model_path = {{ ai_model_base_path }}/{{ model_name }}
   port       = {{ ai_service_port }}
   workers    = {{ ai_worker_count | default(4) }}

   {% if env_type == 'prod' %}
   [security]
   log_level  = warning
   enable_tls = true
   tls_cert   = /etc/ssl/certs/ai_service.crt
   tls_key    = /etc/ssl/private/ai_service.key
   {% else %}
   [security]
   log_level  = debug
   enable_tls = false
   {% endif %}

   [hardware]
   {% for gpu_id in range(ai_worker_count | int) %}
   device_{{ gpu_id }} = cuda:{{ gpu_id }}
   {% endfor %}
   ```

5. Write the main task file at `roles/ai_server/tasks/main.yml`:

   ```yaml
   ---
   # roles/ai_server/tasks/main.yml

   - name: Create AI service config directory
     ansible.builtin.file:
       path: "{{ ai_config_dir }}"
       state: directory
       owner: "{{ ai_service_user }}"
       group: "{{ ai_service_user }}"
       mode: "0750"
     tags: config

   - name: Deploy AI service configuration
     ansible.builtin.template:
       src: ai_service.conf.j2
       dest: "{{ ai_config_dir }}/ai_service.conf"
       owner: "{{ ai_service_user }}"
       group: "{{ ai_service_user }}"
       mode: "0640"
     notify: Restart ai_service
     tags: config

   - name: Create model directories
     ansible.builtin.file:
       path: "{{ ai_model_base_path }}/{{ item }}"
       state: directory
       owner: "{{ ai_service_user }}"
       group: "{{ ai_service_user }}"
       mode: "0750"
     loop:
       - "{{ model_name }}"
       - cache
       - logs
     tags: config
   ```

6. Write the handler at `roles/ai_server/handlers/main.yml`:

   ```yaml
   ---
   # roles/ai_server/handlers/main.yml

   - name: Restart ai_service
     ansible.builtin.systemd:
       name: "{{ ai_service_name }}"
       state: restarted
       daemon_reload: true
   ```

7. Verify the structure:

   ```bash
   find roles/ai_server -type f -name "*.yml" | sort
   ```

   Expected output:
   ```
   roles/ai_server/defaults/main.yml
   roles/ai_server/handlers/main.yml
   roles/ai_server/meta/main.yml
   roles/ai_server/tasks/main.yml
   roles/ai_server/templates/ai_service.conf.j2
   roles/ai_server/vars/main.yml
   ```

---

### Example 2: Set Up group_vars and host_vars for a Two-Environment Inventory

You have two GPU servers: `gpu01` is production and `gpu02` is dev. Both use the `ai_server` role, but they need different port and environment settings without modifying the role itself.

1. Create the inventory directory structure:

   ```bash
   mkdir -p inventory/group_vars inventory/host_vars
   ```

2. Write `inventory/hosts.yml`:

   ```yaml
   ---
   all:
     children:
       gpu_servers:
         hosts:
           gpu01:
             ansible_host: 192.168.1.101
           gpu02:
             ansible_host: 192.168.1.102
   ```

3. Write `inventory/group_vars/all.yml` (applies to all hosts):

   ```yaml
   ---
   ansible_user: ubuntu
   ansible_ssh_private_key_file: ~/.ssh/id_ed25519
   ```

4. Write `inventory/group_vars/gpu_servers.yml` (applies to all GPU servers):

   ```yaml
   ---
   ai_model_base_path: /opt/models
   model_name: llama3-8b
   ai_worker_count: 4
   cuda_version: "12.4"
   env_type: dev
   ai_service_port: 7860
   ```

5. Write `inventory/host_vars/gpu01.yml` (overrides for production server only):

   ```yaml
   ---
   env_type: prod
   ai_service_port: 8080
   ```

6. Write the site playbook `site.yml`:

   ```yaml
   ---
   - name: Configure GPU servers
     hosts: gpu_servers
     become: true
     roles:
       - role: ai_server
   ```

7. Perform a dry run to verify variable resolution:

   ```bash
   ansible-playbook site.yml --check --diff -i inventory/hosts.yml
   ```

   For `gpu01`, the rendered `ai_service.conf` will show `env_type = prod` and `port = 8080`. For `gpu02`, it will show `env_type = dev` and `port = 7860`, confirming that `host_vars/gpu01.yml` correctly overrode the group default.

---

### Example 3: Install a Community Role and Declare It as a Dependency

You want to use the `geerlingguy.pip` community role to handle Python package installation rather than writing that logic inside `ai_server` directly.

1. Create `requirements.yml` at the project root:

   ```yaml
   ---
   roles:
     - name: geerlingguy.pip
       version: "2.2.0"
   ```

2. Install the community role:

   ```bash
   ansible-galaxy install -r requirements.yml
   ```

   Expected output:
   ```
   Starting galaxy role install process
   - downloading role 'pip', owned by geerlingguy
   - downloading role from https://github.com/geerlingguy/ansible-role-pip/...
   - extracting geerlingguy.pip to /home/user/.ansible/roles/geerlingguy.pip
   - geerlingguy.pip (2.2.0) was installed successfully
   ```

3. Declare the dependency in `roles/ai_server/meta/main.yml`:

   ```yaml
   ---
   galaxy_info:
     role_name: ai_server
     author: your_username
     description: Configures a GPU server to run AI inference services
     license: MIT
     min_ansible_version: "2.17"
     platforms:
       - name: Ubuntu
         versions:
           - jammy
           - noble

   dependencies:
     - role: geerlingguy.pip
       vars:
         pip_install_packages:
           - name: torch
             version: "2.3.0"
           - name: transformers
             version: "4.41.0"
           - name: uvicorn
   ```

4. Re-run the playbook and observe the dependency executing first:

   ```bash
   ansible-playbook site.yml -i inventory/hosts.yml --list-tasks
   ```

   Expected (truncated) output:
   ```
   playbook: site.yml

     play #1 (gpu_servers): Configure GPU servers
       tasks:
         geerlingguy.pip : Install pip packages  TAGS: []
         ai_server : Create AI service config directory  TAGS: [config]
         ai_server : Deploy AI service configuration     TAGS: [config]
         ai_server : Create model directories             TAGS: [config]
   ```

   The `geerlingguy.pip` tasks appear before any `ai_server` tasks, confirming correct dependency ordering.

---

### Example 4: Run Only Configuration Tasks Using Tags and Flush Handlers

After initial provisioning, the model name is updated. You need to regenerate the config file and restart the service without re-running the full provisioning sequence.

1. Update the model name in `inventory/host_vars/gpu01.yml`:

   ```yaml
   ---
   env_type: prod
   ai_service_port: 8080
   model_name: llama3-70b
   ```

2. Run only tasks tagged `config` against the production host:

   ```bash
   ansible-playbook site.yml -i inventory/hosts.yml \
     --limit gpu01 \
     --tags config
   ```

   Expected output (condensed):
   ```
   PLAY [Configure GPU servers] **************************************************

   TASK [ai_server : Create AI service config directory] *************************
   ok: [gpu01]

   TASK [ai_server : Deploy AI service configuration] ****************************
   changed: [gpu01]

   TASK [ai_server : Create model directories] ***********************************
   changed: [gpu01]

   RUNNING HANDLER [ai_server : Restart ai_service] ******************************
   changed: [gpu01]

   PLAY RECAP ****************************************************
   gpu01 : ok=4  changed=3  unreachable=0  failed=0  skipped=0
   ```

   The handler fired because the template task reported `changed`. CUDA installation and package tasks were entirely skipped because they carry no `config` tag.

## Common Pitfalls

### Pitfall 1: Putting Mutable Defaults in vars/main.yml Instead of defaults/main.yml

**Description:** A developer defines the service port in `roles/ai_server/vars/main.yml`, expecting it to be easily overridable in `group_vars`.

**Why it happens:** The distinction between `vars/` and `defaults/` is not obvious from the directory names. Both hold YAML key-value pairs, and the difference is entirely in precedence.

**Incorrect pattern:**
```yaml
# roles/ai_server/vars/main.yml
ai_service_port: 7860    # Defined here — now group_vars CANNOT override this
```

**Correct pattern:**
```yaml
# roles/ai_server/defaults/main.yml
ai_service_port: 7860    # group_vars and host_vars can now override this as expected
```

---

### Pitfall 2: Forgetting to Quote Jinja2 Expressions That Start a YAML Value

**Description:** A task fails with a YAML parse error when a variable reference is at the start of a value string.

**Why it happens:** YAML interprets a bare `{` as the start of a mapping literal. Ansible does not parse the Jinja2 before YAML does, so the YAML parser sees an invalid construct.

**Incorrect pattern:**
```yaml
dest: {{ ai_config_dir }}/ai_service.conf   # SyntaxError: mapping values not allowed here
```

**Correct pattern:**
```yaml
dest: "{{ ai_config_dir }}/ai_service.conf"   # Quotes tell YAML this is a string
```

---

### Pitfall 3: Notifying a Handler with a Name That Does Not Match Exactly

**Description:** A handler is defined but never runs, even when the notifying task reports `changed`.

**Why it happens:** Handler matching is case-sensitive and whitespace-sensitive. A single extra space or different capitalization silently causes the notification to be discarded. Ansible does not raise an error for an unmatched handler name.

**Incorrect pattern:**
```yaml
# Handler defined as:
- name: Restart ai_service

# Task notifies with a different string:
notify: restart ai_service   # lowercase 'r' — no match, handler never runs
```

**Correct pattern:**
```yaml
notify: Restart ai_service   # Must be byte-for-byte identical to the handler name
```

---

### Pitfall 4: Using with_items Instead of loop for New Playbooks

**Description:** A developer writes `with_items:` in a new role, which works but triggers deprecation warnings and is inconsistent with the rest of the codebase.

**Why it happens:** `with_items` was the original Ansible looping syntax. Many tutorials and blog posts still use it. It is not removed in Ansible 2.17 or 2.18 but it is deprecated and its behavior differs subtly from `loop` — `with_items` flattens single-level nested lists automatically, which `loop` does not.

**Incorrect pattern:**
```yaml
- name: Install packages
  ansible.builtin.apt:
    name: "{{ item }}"
  with_items:
    - python3-pip
    - git
```

**Correct pattern:**
```yaml
- name: Install packages
  ansible.builtin.apt:
    name: "{{ item }}"
  loop:
    - python3-pip
    - git
```

---

### Pitfall 5: Expecting Handlers to Run Mid-Play Without flush_handlers

**Description:** A handler is notified by an early task, but a later task in the same play needs the handler's effect (e.g., a service restart) to have already happened. The later task fails because the service has not restarted yet.

**Why it happens:** By default, all notified handlers run once at the end of the play, after all tasks complete. This is a deliberate design choice to avoid multiple restarts during a single run, but it catches people off guard.

**Incorrect pattern:**
```yaml
- name: Deploy new TLS certificate
  ansible.builtin.copy:
    src: ai_service.crt
    dest: /etc/ssl/certs/ai_service.crt
  notify: Restart ai_service

# This task will fail if the service needs the new cert to be loaded
- name: Check HTTPS health endpoint
  ansible.builtin.uri:
    url: "https://{{ inventory_hostname }}:{{ ai_service_port }}/health"
    status_code: 200
```

**Correct pattern:**
```yaml
- name: Deploy new TLS certificate
  ansible.builtin.copy:
    src: ai_service.crt
    dest: /etc/ssl/certs/ai_service.crt
  notify: Restart ai_service

- name: Flush handlers so service restarts before health check
  ansible.builtin.meta: flush_handlers

- name: Check HTTPS health endpoint
  ansible.builtin.uri:
    url: "https://{{ inventory_hostname }}:{{ ai_service_port }}/health"
    status_code: 200
```

---

### Pitfall 6: Applying Tags Only to Some Tasks in a Role, Causing Partial Runs to Break

**Description:** Some tasks in a role have tags and others do not. Running with `--tags config` runs the tagged tasks but skips untagged prerequisites, causing failures (e.g., the config directory does not exist because the task creating it had no tag).

**Why it happens:** Developers add tags incrementally as they think about which tasks are "re-runnable." They forget that tagged tasks may depend on untagged setup tasks.

**Incorrect pattern:**
```yaml
- name: Create config directory   # No tag — skipped on --tags config runs
  ansible.builtin.file:
    path: /etc/ai_service
    state: directory

- name: Deploy config file        # Has tag — runs, but fails because dir doesn't exist
  ansible.builtin.template:
    src: ai_service.conf.j2
    dest: /etc/ai_service/ai_service.conf
  tags: config
```

**Correct pattern:**
```yaml
- name: Create config directory
  ansible.builtin.file:
    path: /etc/ai_service
    state: directory
  tags: config                    # Tag the prerequisite too

- name: Deploy config file
  ansible.builtin.template:
    src: ai_service.conf.j2
    dest: /etc/ai_service/ai_service.conf
  tags: config
```

---

### Pitfall 7: Referencing a Variable in when: Before It Is Defined

**Description:** A task with `when: gpu_count | int > 0` fails with an `AnsibleUndefinedVariable` error when `gpu_count` is not set anywhere in the variable hierarchy.

**Why it happens:** Unlike many languages, Ansible does not have implicit `None` for undefined variables — it raises an error at template evaluation time. This is most common for optional variables the role does not define in `defaults/main.yml`.

**Incorrect pattern:**
```yaml
# defaults/main.yml — gpu_count not defined here
# tasks/main.yml:
- name: Install GPU monitoring
  ansible.builtin.apt:
    name: nvidia-smi
  when: gpu_count | int > 0      # Fails if gpu_count is not defined anywhere
```

**Correct pattern:**
```yaml
# defaults/main.yml
gpu_count: 0                     # Define a safe default

# tasks/main.yml:
- name: Install GPU monitoring
  ansible.builtin.apt:
    name: nvidia-smi
  when: gpu_count | int > 0      # Now safe — evaluates to false if default is used
```

## Summary

- Ansible's 17-level variable precedence order means `defaults/main.yml` is for operator-overridable defaults, `vars/main.yml` is for internal role constants, `group_vars` and `host_vars` directories target variables at groups and individual hosts, and `--extra-vars` overrides everything.
- The `ansible-galaxy init` command scaffolds the full role directory structure in one step; the `meta/main.yml` file declares role dependencies that Ansible resolves and executes automatically before the role's own tasks.
- Jinja2 templating with `{{ }}`, filters, and `{% if %}`/`{% for %}` blocks inside `.j2` files, combined with the `template` module, is the standard pattern for generating host-specific configuration files.
- Handlers run once at the end of a play when notified by changed tasks; `ansible.builtin.meta: flush_handlers` forces immediate execution when subsequent tasks depend on the handler's effect.
- Tags, `loop:`, and `when:` are the three primary tools for controlling which tasks run and how they iterate: tags select task subsets at invocation time, `loop:` repeats a single task over a list, and `when:` gates execution on runtime conditions.

## Further Reading

- [Ansible Roles Documentation](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html) — The official reference for role directory structure, role execution order, role dependencies, and all supported role keywords, including `allow_duplicates` and `public` role variables.

- [Ansible Variable Precedence Reference](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html#understanding-variable-precedence) — The authoritative, numbered list of all 22 precedence levels with explanations of when each applies; essential reading before designing any multi-environment variable hierarchy.

- [Ansible Galaxy User Guide](https://docs.ansible.com/ansible/latest/galaxy/user_guide.html) — Covers installing roles and collections, writing `requirements.yml`, using private Galaxy servers, and the difference between roles and collections in modern Ansible.

- [Jinja2 Template Designer Documentation](https://jinja.palletsprojects.com/en/3.1.x/templates/) — The full Jinja2 reference covering all built-in filters, tests, control structures, whitespace control, and template inheritance; Ansible's templating layer is a strict superset of this.

- [Ansible Filters Reference](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_filters.html) — Documents all Ansible-specific Jinja2 filters (`dict2items`, `selectattr`, `combine`, `to_json`, `b64encode`, etc.) that are not available in plain Jinja2; these are used constantly in production roles.

- [Ansible Handlers and Notification](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_handlers.html) — Explains handler deduplication, `listen:` topics for decoupled handler triggering, `flush_handlers`, and the `force_handlers` play option for running handlers even when a task fails.

- [Jeff Geerling — Ansible for DevOps (Book)](https://www.ansiblefordevops.com/) — The most widely recommended practical Ansible book; covers roles, Galaxy, testing with Molecule, and real-world playbook patterns for server configuration at scale.

- [Ansible lint Documentation](https://ansible.readthedocs.io/projects/lint/) — The official linter for Ansible playbooks and roles; enforces best practices including FQCN module names, `loop` over `with_items`, proper `when:` boolean handling, and role structure conventions.
