# Module 8: Monitoring and Maintenance
> Subject: Ansible | Difficulty: Intermediate | Estimated Time: 360 minutes

## Objective

After completing this module you will be able to build and run a complete observability stack for a fleet of AI servers entirely from Ansible playbooks. Specifically, you will: deploy Prometheus `node_exporter` as a binary-installed, systemd-managed service on every host; deploy the NVIDIA DCGM Exporter to expose GPU metrics; stand up a central Prometheus server whose `prometheus.yml` is rendered from a Jinja2 template so it automatically discovers every fleet member; provision Grafana with pre-built dashboards as code using the provisioning API; configure Alertmanager with GPU memory, CPU saturation, and disk-space alert rules; automate log rotation with the `community.general.logrotate` module; run unattended `dist-upgrade` across the fleet; write a certificate-expiry check playbook; surface disk-space warnings from Ansible facts alone; and orchestrate rolling maintenance windows using `serial`, `pre_tasks`, and `post_tasks` so no more than one node is taken offline at a time.

---

## Prerequisites

- Completed Module 1: Ansible Fundamentals — inventory files, ad-hoc commands, playbook structure
- Completed Module 2: Variables and Templates — `vars`, `group_vars`, `host_vars`, Jinja2 `template` module
- Completed Module 3: Roles and Galaxy — role directory layout, `ansible-galaxy role install`, `meta/main.yml`
- Completed Module 4: Handlers and Notifications — `notify`, `handlers`, `flush_handlers`
- Completed Module 5: Ansible Vault — encrypting secrets, `ansible-vault encrypt_string`, vault passwords in CI
- Completed Module 6: Inventory and Dynamic Inventory — static INI/YAML inventories, `group_vars`, host patterns
- Completed Module 7: Idempotency and Testing — `--check`, `--diff`, Molecule basics
- Ansible Core 2.17 or later installed on the control node (`ansible --version`)
- Target hosts running Ubuntu 22.04 LTS or 24.04 LTS with `sudo` access
- NVIDIA drivers already installed on GPU nodes (driver version 525 or later)
- Python 3.10 or later on all nodes (`python3 --version`)
- The `community.general` collection installed (`ansible-galaxy collection install community.general`)

---

## Key Concepts

### The Observability Stack Architecture

An observability stack for AI servers has four layers: **collection**, **aggregation**, **visualisation**, and **alerting**. Ansible's job is to make all four layers reproducible — you run one playbook and every component appears, correctly wired together, on every host that needs it.

The data flow looks like this:

```
AI Server Fleet
┌──────────────────────────────────────────────────────────┐
│  node_exporter :9100   ──────────────────────────────┐   │
│  dcgm_exporter :9400   ──────────────────────────┐   │   │
└──────────────────────────────────────────────────│───│───┘
                                                   │   │
                         scrape (pull, 15s)        │   │
                                                   ▼   ▼
                              ┌─────────────────────────────┐
                              │   Prometheus  :9090         │
                              │   prometheus.yml (template) │
                              └────────────┬────────────────┘
                                           │  query (PromQL)
                                           ▼
                              ┌────────────────────────────┐
                              │   Grafana  :3000           │
                              │   provisioned dashboards   │
                              └────────────────────────────┘
                                           │  fire alerts
                                           ▼
                              ┌────────────────────────────┐
                              │   Alertmanager  :9093      │
                              │   routes → email / Slack   │
                              └────────────────────────────┘
```

Each component is managed as a separate Ansible role so it can be applied independently or composed into a single site playbook. A top-level `site.yml` orchestrates all roles with the correct host targeting.

The key Ansible principle throughout this stack is **idempotence**: every task checks the current state before changing anything. A task that downloads a binary uses `get_url` with a `checksum` parameter so it skips the download when the file already matches. A task that writes a config file uses the `template` module; the handler that restarts the service only fires when the config actually changed.

### Deploying node_exporter as a Binary + systemd Service

Prometheus `node_exporter` exposes hardware and OS metrics from Linux hosts. Because it ships as a single statically-linked Go binary with no runtime dependencies, the cleanest deployment pattern is: download the tarball, extract the binary, place it in `/usr/local/bin`, create a dedicated system user, write a systemd unit file, and enable the service. This avoids package manager lock-in and lets you pin an exact version across every host.

The Ansible tasks follow this sequence:

```yaml
# roles/node_exporter/tasks/main.yml
---
- name: Create node_exporter system user
  ansible.builtin.user:
    name: node_exporter
    system: true
    shell: /usr/sbin/nologin
    create_home: false
    comment: Prometheus node_exporter service account

- name: Download node_exporter tarball
  ansible.builtin.get_url:
    url: "https://github.com/prometheus/node_exporter/releases/download/v{{ node_exporter_version }}/node_exporter-{{ node_exporter_version }}.linux-amd64.tar.gz"
    dest: "/tmp/node_exporter-{{ node_exporter_version }}.tar.gz"
    checksum: "sha256:{{ node_exporter_checksum }}"
    mode: "0644"

- name: Extract node_exporter binary
  ansible.builtin.unarchive:
    src: "/tmp/node_exporter-{{ node_exporter_version }}.tar.gz"
    dest: /tmp
    remote_src: true
    creates: "/tmp/node_exporter-{{ node_exporter_version }}.linux-amd64/node_exporter"

- name: Install node_exporter binary
  ansible.builtin.copy:
    src: "/tmp/node_exporter-{{ node_exporter_version }}.linux-amd64/node_exporter"
    dest: /usr/local/bin/node_exporter
    owner: root
    group: root
    mode: "0755"
    remote_src: true
  notify: Restart node_exporter

- name: Deploy node_exporter systemd unit
  ansible.builtin.template:
    src: node_exporter.service.j2
    dest: /etc/systemd/system/node_exporter.service
    owner: root
    group: root
    mode: "0644"
  notify:
    - Reload systemd
    - Restart node_exporter

- name: Enable and start node_exporter
  ansible.builtin.systemd:
    name: node_exporter
    state: started
    enabled: true
    daemon_reload: true
```

The corresponding Jinja2 unit file template:

```ini
# roles/node_exporter/templates/node_exporter.service.j2
[Unit]
Description=Prometheus node_exporter
Documentation=https://prometheus.io/docs/guides/node-exporter/
After=network-online.target
Wants=network-online.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter \
  --web.listen-address=":{{ node_exporter_port | default('9100') }}" \
  --collector.systemd \
  --collector.processes
Restart=on-failure
RestartSec=5s
SyslogIdentifier=node_exporter

[Install]
WantedBy=multi-user.target
```

Role defaults (`roles/node_exporter/defaults/main.yml`) hold the version and checksum so they can be overridden per environment:

```yaml
# roles/node_exporter/defaults/main.yml
node_exporter_version: "1.8.2"
# SHA-256 for node_exporter-1.8.2.linux-amd64.tar.gz
# Verify at: https://github.com/prometheus/node_exporter/releases
node_exporter_checksum: "sha256:6809dd0b3ec45fd6e992c19071d6b5253aed3ead7bf0686885a51d85c6643c66"
node_exporter_port: "9100"
```

> **Version note:** node_exporter 1.8.2 was the current stable release as of mid-2025. Before running this playbook, verify the latest release and its SHA-256 checksum at the official GitHub releases page and update `defaults/main.yml` accordingly.

### Deploying NVIDIA DCGM Exporter for GPU Metrics

The DCGM Exporter is NVIDIA's official tool for exposing GPU telemetry to Prometheus. It wraps the Data Center GPU Manager (DCGM) library and exports counters such as `DCGM_FI_DEV_GPU_UTIL` (utilisation), `DCGM_FI_DEV_FB_USED` (framebuffer memory used), `DCGM_FI_DEV_SM_CLOCK` (SM clock speed), and `DCGM_FI_DEV_POWER_USAGE` (power draw in watts).

There are two deployment options: Docker container (simpler, but requires Docker on GPU nodes) and bare-metal binary with systemd (no container runtime required). For AI server fleets where Docker may already be occupied by training workloads, the bare-metal approach avoids resource contention.

```yaml
# roles/dcgm_exporter/tasks/main.yml
---
- name: Install DCGM exporter prerequisite packages
  ansible.builtin.apt:
    name:
      - datacenter-gpu-manager
    state: present
    update_cache: true
  when: ansible_os_family == "Debian"

- name: Download DCGM exporter binary
  ansible.builtin.get_url:
    url: "https://github.com/NVIDIA/dcgm-exporter/releases/download/v{{ dcgm_exporter_version }}/dcgm-exporter-{{ dcgm_exporter_version }}-linux-amd64.tar.gz"
    dest: "/tmp/dcgm-exporter-{{ dcgm_exporter_version }}.tar.gz"
    checksum: "sha256:{{ dcgm_exporter_checksum }}"
    mode: "0644"

- name: Extract and install DCGM exporter binary
  ansible.builtin.unarchive:
    src: "/tmp/dcgm-exporter-{{ dcgm_exporter_version }}.tar.gz"
    dest: /usr/local/bin
    remote_src: true
    extra_opts: ["--strip-components=1"]
    creates: /usr/local/bin/dcgm-exporter
    mode: "0755"

- name: Deploy DCGM exporter metrics configuration
  ansible.builtin.copy:
    src: dcgm-default-counters.csv
    dest: /etc/dcgm-exporter/default-counters.csv
    owner: root
    group: root
    mode: "0644"
  notify: Restart dcgm_exporter

- name: Deploy DCGM exporter systemd unit
  ansible.builtin.template:
    src: dcgm_exporter.service.j2
    dest: /etc/systemd/system/dcgm_exporter.service
    owner: root
    group: root
    mode: "0644"
  notify:
    - Reload systemd
    - Restart dcgm_exporter

- name: Enable and start DCGM exporter
  ansible.builtin.systemd:
    name: dcgm_exporter
    state: started
    enabled: true
    daemon_reload: true
```

The metrics counters file (`roles/dcgm_exporter/files/dcgm-default-counters.csv`) controls which GPU fields are exported. A minimal set for AI workload monitoring:

```csv
# Format: DCGM field name, prometheus metric type, help string
DCGM_FI_DEV_GPU_UTIL,       gauge, GPU utilization (%)
DCGM_FI_DEV_MEM_COPY_UTIL,  gauge, Memory bandwidth utilization (%)
DCGM_FI_DEV_FB_FREE,        gauge, Framebuffer memory free (MiB)
DCGM_FI_DEV_FB_USED,        gauge, Framebuffer memory used (MiB)
DCGM_FI_DEV_SM_CLOCK,       gauge, SM clock frequency (MHz)
DCGM_FI_DEV_MEM_CLOCK,      gauge, Memory clock frequency (MHz)
DCGM_FI_DEV_POWER_USAGE,    gauge, Power draw (W)
DCGM_FI_DEV_GPU_TEMP,       gauge, GPU temperature (C)
DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL, counter, NVLink bandwidth total (bytes)
```

> **Version note:** DCGM Exporter release versions are tied to DCGM library versions. Verify the latest compatible release for your driver version at `https://github.com/NVIDIA/dcgm-exporter/releases` and update `dcgm_exporter_version` and `dcgm_exporter_checksum` in the role defaults accordingly.

### Deploying Prometheus Server with a Template-Generated Config

The Prometheus server role deploys a central scrape aggregator. Its most important file is `prometheus.yml`, which must list every host in the fleet as a scrape target. Maintaining this file by hand breaks the moment a host is added or removed. The Ansible `template` module solves this: iterate over inventory groups with Jinja2 to generate the full scrape config from the live inventory.

```yaml
# roles/prometheus/tasks/main.yml
---
- name: Create prometheus system user
  ansible.builtin.user:
    name: prometheus
    system: true
    shell: /usr/sbin/nologin
    create_home: false

- name: Create prometheus data directory
  ansible.builtin.file:
    path: "{{ prometheus_data_dir }}"
    state: directory
    owner: prometheus
    group: prometheus
    mode: "0755"

- name: Download Prometheus tarball
  ansible.builtin.get_url:
    url: "https://github.com/prometheus/prometheus/releases/download/v{{ prometheus_version }}/prometheus-{{ prometheus_version }}.linux-amd64.tar.gz"
    dest: "/tmp/prometheus-{{ prometheus_version }}.tar.gz"
    checksum: "sha256:{{ prometheus_checksum }}"
    mode: "0644"

- name: Extract Prometheus binaries
  ansible.builtin.unarchive:
    src: "/tmp/prometheus-{{ prometheus_version }}.tar.gz"
    dest: /tmp
    remote_src: true
    creates: "/tmp/prometheus-{{ prometheus_version }}.linux-amd64/prometheus"

- name: Install prometheus and promtool binaries
  ansible.builtin.copy:
    src: "/tmp/prometheus-{{ prometheus_version }}.linux-amd64/{{ item }}"
    dest: "/usr/local/bin/{{ item }}"
    owner: root
    group: root
    mode: "0755"
    remote_src: true
  loop:
    - prometheus
    - promtool
  notify: Restart prometheus

- name: Deploy prometheus.yml from template
  ansible.builtin.template:
    src: prometheus.yml.j2
    dest: /etc/prometheus/prometheus.yml
    owner: prometheus
    group: prometheus
    mode: "0640"
    validate: /usr/local/bin/promtool check config %s
  notify: Restart prometheus

- name: Deploy alert rules
  ansible.builtin.template:
    src: alert_rules.yml.j2
    dest: /etc/prometheus/alert_rules.yml
    owner: prometheus
    group: prometheus
    mode: "0640"
    validate: /usr/local/bin/promtool check rules %s
  notify: Restart prometheus

- name: Deploy Prometheus systemd unit
  ansible.builtin.template:
    src: prometheus.service.j2
    dest: /etc/systemd/system/prometheus.service
    owner: root
    group: root
    mode: "0644"
  notify:
    - Reload systemd
    - Restart prometheus

- name: Enable and start Prometheus
  ansible.builtin.systemd:
    name: prometheus
    state: started
    enabled: true
    daemon_reload: true
```

The template that auto-generates scrape targets from inventory groups:

```yaml
# roles/prometheus/templates/prometheus.yml.j2
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: "{{ prometheus_cluster_name | default('ai-fleet') }}"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - "{{ alertmanager_host }}:9093"

rule_files:
  - /etc/prometheus/alert_rules.yml

scrape_configs:
  - job_name: node_exporter
    static_configs:
{% for host in groups['all_fleet'] %}
      - targets:
          - "{{ hostvars[host]['ansible_host'] | default(host) }}:9100"
        labels:
          instance: "{{ host }}"
          role: "{{ hostvars[host]['server_role'] | default('generic') }}"
{% endfor %}

  - job_name: dcgm_exporter
    static_configs:
{% for host in groups['gpu_nodes'] %}
      - targets:
          - "{{ hostvars[host]['ansible_host'] | default(host) }}:9400"
        labels:
          instance: "{{ host }}"
          gpu_model: "{{ hostvars[host]['gpu_model'] | default('unknown') }}"
{% endfor %}

  - job_name: prometheus
    static_configs:
      - targets:
          - "localhost:9090"
```

The `validate` parameter on the `template` task is a critical safety net: Ansible runs `promtool check config /tmp/tmpXXX` on the rendered file before committing it to `/etc/prometheus/prometheus.yml`. If the rendered config is syntactically invalid, the task fails and the running Prometheus instance is left untouched.

### Deploying Grafana with Provisioned Dashboards

Grafana's provisioning system lets you ship data sources and dashboards as YAML/JSON files that Grafana loads on startup — no manual UI clicks required. Ansible deploys the Grafana package, writes the provisioning files, and places dashboard JSON files in the right directory. Grafana detects them automatically.

```yaml
# roles/grafana/tasks/main.yml
---
- name: Add Grafana APT repository key
  ansible.builtin.apt_key:
    url: https://apt.grafana.com/gpg.key
    state: present

- name: Add Grafana APT repository
  ansible.builtin.apt_repository:
    repo: "deb https://apt.grafana.com stable main"
    state: present
    filename: grafana

- name: Install Grafana
  ansible.builtin.apt:
    name: "grafana={{ grafana_version }}"
    state: present
    update_cache: true

- name: Deploy Grafana main configuration
  ansible.builtin.template:
    src: grafana.ini.j2
    dest: /etc/grafana/grafana.ini
    owner: root
    group: grafana
    mode: "0640"
  notify: Restart grafana

- name: Deploy Prometheus data source provisioning
  ansible.builtin.template:
    src: datasource_prometheus.yml.j2
    dest: /etc/grafana/provisioning/datasources/prometheus.yml
    owner: root
    group: grafana
    mode: "0640"
  notify: Restart grafana

- name: Deploy dashboard provisioning config
  ansible.builtin.copy:
    src: dashboard_provider.yml
    dest: /etc/grafana/provisioning/dashboards/default.yml
    owner: root
    group: grafana
    mode: "0640"
  notify: Restart grafana

- name: Create Grafana dashboards directory
  ansible.builtin.file:
    path: /var/lib/grafana/dashboards
    state: directory
    owner: grafana
    group: grafana
    mode: "0755"

- name: Deploy GPU monitoring dashboard JSON
  ansible.builtin.copy:
    src: "{{ item }}"
    dest: "/var/lib/grafana/dashboards/{{ item | basename }}"
    owner: grafana
    group: grafana
    mode: "0644"
  loop: "{{ query('fileglob', role_path + '/files/dashboards/*.json') }}"
  notify: Restart grafana

- name: Enable and start Grafana
  ansible.builtin.systemd:
    name: grafana-server
    state: started
    enabled: true
```

The data source provisioning template:

```yaml
# roles/grafana/templates/datasource_prometheus.yml.j2
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: "http://{{ prometheus_host }}:9090"
    isDefault: true
    jsonData:
      timeInterval: "15s"
      queryTimeout: "60s"
```

The dashboard provider configuration tells Grafana where to find dashboard JSON files:

```yaml
# roles/grafana/files/dashboard_provider.yml
apiVersion: 1
providers:
  - name: default
    orgId: 1
    type: file
    disableDeletion: true
    updateIntervalSeconds: 30
    allowUiUpdates: false
    options:
      path: /var/lib/grafana/dashboards
```

> **Version note:** Grafana releases new minor versions frequently. Set `grafana_version` in your group_vars to a pinned version (e.g., `11.1.0`) rather than using `latest` to keep the fleet consistent.

### Configuring Alertmanager and Alert Rules

Alertmanager receives firing alerts from Prometheus and routes them to notification channels. Ansible deploys both the Alertmanager binary (same binary-install pattern as node_exporter) and the Prometheus alert rule files that define the conditions.

Alert rules for an AI server fleet should cover at minimum: GPU memory exhaustion, GPU being offline (exporter not reachable), high CPU saturation, disk filling up, and a Prometheus "dead man's switch" (an alert that always fires, so silence means something broke).

```yaml
# roles/prometheus/templates/alert_rules.yml.j2
groups:
  - name: gpu_alerts
    interval: 30s
    rules:
      - alert: GPUMemoryNearlyFull
        expr: |
          (DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE)) > 0.90
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "GPU memory > 90% on {{ "{{" }} $labels.instance {{ "}}" }}"
          description: "GPU {{ "{{" }} $labels.gpu {{ "}}" }} on {{ "{{" }} $labels.instance {{ "}}" }} has used {{ "{{" }} $value | humanizePercentage {{ "}}" }} of framebuffer memory for 5 minutes."

      - alert: GPUMemoryCritical
        expr: |
          (DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE)) > 0.98
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "GPU memory > 98% on {{ "{{" }} $labels.instance {{ "}}" }}"

      - alert: GPUExporterDown
        expr: up{job="dcgm_exporter"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "DCGM exporter unreachable on {{ "{{" }} $labels.instance {{ "}}" }}"

  - name: host_alerts
    rules:
      - alert: HighCPUSaturation
        expr: |
          100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 90
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "CPU > 90% on {{ "{{" }} $labels.instance {{ "}}" }} for 10 minutes"

      - alert: DiskSpaceLow
        expr: |
          (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"}) < 0.15
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Disk < 15% free on {{ "{{" }} $labels.instance {{ "}}" }} ({{ "{{" }} $labels.mountpoint {{ "}}" }})"

      - alert: DiskSpaceCritical
        expr: |
          (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"}) < 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Disk < 5% free on {{ "{{" }} $labels.instance {{ "}}" }}"

  - name: watchdog
    rules:
      - alert: Watchdog
        expr: vector(1)
        labels:
          severity: none
        annotations:
          summary: "Prometheus is alive and alert pipeline is functional"
```

The Alertmanager configuration template:

```yaml
# roles/alertmanager/templates/alertmanager.yml.j2
global:
  resolve_timeout: 5m
  smtp_smarthost: "{{ alertmanager_smtp_host }}:587"
  smtp_from: "{{ alertmanager_smtp_from }}"
  smtp_auth_username: "{{ alertmanager_smtp_user }}"
  smtp_auth_password: "{{ alertmanager_smtp_password }}"

route:
  group_by: ['alertname', 'instance']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: default
  routes:
    - match:
        severity: critical
      receiver: pagerduty
      repeat_interval: 1h
    - match:
        severity: warning
      receiver: email

receivers:
  - name: default
    email_configs:
      - to: "{{ alertmanager_default_email }}"

  - name: email
    email_configs:
      - to: "{{ alertmanager_ops_email }}"
        send_resolved: true

  - name: pagerduty
    pagerduty_configs:
      - service_key: "{{ alertmanager_pagerduty_key }}"
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal: ['alertname', 'instance']
```

### Automating Log Rotation, System Updates, and Certificate Checks

Beyond metrics, day-to-day maintenance of an AI fleet involves three recurring tasks: rotating logs before disks fill, applying OS security patches, and monitoring TLS certificate expiry.

**Log rotation** uses the `community.general.logrotate` module, which writes a file to `/etc/logrotate.d/` without requiring you to manage the file content as a raw template:

```yaml
# In a maintenance role or playbook
- name: Configure log rotation for AI training logs
  community.general.logrotate:
    name: ai_training
    path: /var/log/training/*.log
    state: present
    options:
      - daily
      - rotate 14
      - compress
      - delaycompress
      - missingok
      - notifempty
      - create 0640 ubuntu ubuntu
      - postrotate
      - systemctl kill --signal=HUP training-service 2>/dev/null || true
      - endscript
```

**System updates** use the `ansible.builtin.apt` module with `upgrade: dist`. The `dist` value maps directly to `apt-get dist-upgrade`, which resolves dependency changes that a plain `upgrade` would skip. Run this under a `pre_tasks` / `post_tasks` guard so you verify the host is healthy before and after:

```yaml
# playbooks/update_fleet.yml
---
- name: Unattended dist-upgrade across fleet
  hosts: all_fleet
  serial: 1
  max_fail_percentage: 0
  become: true

  pre_tasks:
    - name: Verify host is reachable before patching
      ansible.builtin.ping:

    - name: Record pre-patch uptime
      ansible.builtin.command: uptime -s
      register: pre_patch_uptime
      changed_when: false

  tasks:
    - name: Update apt cache
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 0

    - name: Apply dist-upgrade
      ansible.builtin.apt:
        upgrade: dist
        autoremove: true
        autoclean: true
      register: apt_result

    - name: Check if reboot is required
      ansible.builtin.stat:
        path: /var/run/reboot-required
      register: reboot_required

    - name: Reboot if kernel was updated
      ansible.builtin.reboot:
        msg: "Rebooting after dist-upgrade"
        reboot_timeout: 300
      when: reboot_required.stat.exists

  post_tasks:
    - name: Verify node_exporter is running after update
      ansible.builtin.systemd:
        name: node_exporter
        state: started
      register: exporter_state

    - name: Fail loudly if exporter is not running
      ansible.builtin.fail:
        msg: "node_exporter is not running on {{ inventory_hostname }} after patching"
      when: exporter_state.status.ActiveState != "active"
```

**Certificate expiry checks** use the `community.crypto.x509_certificate_info` module to read a local certificate file, then `ansible.builtin.fail` when days-until-expiry fall below a threshold:

```yaml
# playbooks/check_certificates.yml
---
- name: Audit TLS certificate expiry across fleet
  hosts: all_fleet
  gather_facts: false
  become: true

  vars:
    cert_paths:
      - /etc/ssl/certs/fleet-node.crt
      - /etc/prometheus/tls/prometheus.crt
    cert_warn_days: 30
    cert_critical_days: 7

  tasks:
    - name: Read certificate information
      community.crypto.x509_certificate_info:
        path: "{{ item }}"
      loop: "{{ cert_paths }}"
      register: cert_info
      ignore_errors: true

    - name: Calculate days until expiry
      ansible.builtin.set_fact:
        cert_expiry_results: >-
          {{
            cert_expiry_results | default([]) + [{
              'path': item.item,
              'expired': item.expired | default(false),
              'days_remaining': (
                (item.not_after | to_datetime('%Y%m%d%H%M%SZ')) - (ansible_date_time.iso8601 | to_datetime('%Y-%m-%dT%H:%M:%SZ'))
              ).days | int
            }]
          }}
      loop: "{{ cert_info.results }}"
      when: not item.failed | default(false)

    - name: Warn on certificates expiring within {{ cert_warn_days }} days
      ansible.builtin.debug:
        msg: "WARNING: Certificate {{ item.path }} expires in {{ item.days_remaining }} days"
      loop: "{{ cert_expiry_results | default([]) }}"
      when: item.days_remaining <= cert_warn_days and item.days_remaining > cert_critical_days

    - name: Fail on certificates expiring within {{ cert_critical_days }} days
      ansible.builtin.fail:
        msg: "CRITICAL: Certificate {{ item.path }} expires in {{ item.days_remaining }} days on {{ inventory_hostname }}"
      loop: "{{ cert_expiry_results | default([]) }}"
      when: item.days_remaining <= cert_critical_days
```

### Disk Space Alerting with Ansible Facts

Before Prometheus is fully deployed, or for a quick health check that doesn't require a running metrics stack, you can surface disk-space problems using only Ansible's own fact-gathering system. `ansible_mounts` is populated automatically during the `gather_facts` phase and contains free/total bytes for every mounted filesystem.

```yaml
# playbooks/disk_space_check.yml
---
- name: Check disk space using Ansible facts
  hosts: all_fleet
  gather_facts: true

  vars:
    disk_warn_threshold_pct: 80
    disk_critical_threshold_pct: 90
    excluded_fstypes:
      - tmpfs
      - devtmpfs
      - overlay
      - squashfs

  tasks:
    - name: Evaluate disk usage for each mount
      ansible.builtin.set_fact:
        disk_issues: >-
          {{
            ansible_mounts
            | selectattr('fstype', 'not in', excluded_fstypes)
            | selectattr('size_total', 'gt', 0)
            | map(attribute='mount')
            | map('extract', ansible_mounts | items2dict(key_name='mount'))
            | list
            | selectattr('size_available', 'defined')
            | map('combine', {})
            | list
          }}

    - name: Report mounts above warning threshold
      ansible.builtin.debug:
        msg: >-
          {{ item.mount }}: {{ ((1 - item.size_available / item.size_total) * 100) | round(1) }}% used
          ({{ (item.size_available / 1073741824) | round(2) }} GiB free of {{ (item.size_total / 1073741824) | round(2) }} GiB)
      loop: "{{ ansible_mounts | selectattr('fstype', 'not in', excluded_fstypes) | list }}"
      when:
        - item.size_total > 0
        - ((1 - item.size_available / item.size_total) * 100) >= disk_warn_threshold_pct

    - name: Fail on mounts above critical threshold
      ansible.builtin.fail:
        msg: "CRITICAL: {{ item.mount }} is {{ ((1 - item.size_available / item.size_total) * 100) | round(1) }}% full on {{ inventory_hostname }}"
      loop: "{{ ansible_mounts | selectattr('fstype', 'not in', excluded_fstypes) | list }}"
      when:
        - item.size_total > 0
        - ((1 - item.size_available / item.size_total) * 100) >= disk_critical_threshold_pct
```

### Rolling Updates with serial, pre_tasks, and post_tasks

The most dangerous moment for a fleet is a simultaneous update: if the new configuration is broken and Ansible runs it on all 40 nodes at once, the entire fleet goes down. The `serial` keyword limits parallelism so Ansible updates one node (or a batch), verifies it, then moves to the next. `max_fail_percentage` sets the circuit-breaker: abort the whole play if too many nodes fail, preventing a cascading rollout of a bad change.

```yaml
# playbooks/rolling_update_observability.yml
---
- name: Rolling update of observability stack
  hosts: all_fleet
  serial: 1
  max_fail_percentage: 0
  become: true

  pre_tasks:
    - name: Assert node_exporter is running before update
      ansible.builtin.systemd:
        name: node_exporter
      register: pre_state
      failed_when: pre_state.status.ActiveState != "active"

    - name: Check disk space before update
      ansible.builtin.assert:
        that:
          - item.size_available > 524288000
        fail_msg: "Insufficient disk space on {{ item.mount }} before update"
        success_msg: "Disk space OK on {{ item.mount }}"
      loop: "{{ ansible_mounts | selectattr('mount', 'equalto', '/') | list }}"

    - name: Drain this node from load balancer (if applicable)
      ansible.builtin.uri:
        url: "http://{{ lb_host }}/api/v1/drain/{{ inventory_hostname }}"
        method: POST
        status_code: [200, 204]
      delegate_to: localhost
      when: lb_host is defined
      ignore_errors: true

  roles:
    - node_exporter
    - dcgm_exporter

  post_tasks:
    - name: Wait for node_exporter to respond
      ansible.builtin.wait_for:
        host: "{{ ansible_host | default(inventory_hostname) }}"
        port: 9100
        delay: 5
        timeout: 60

    - name: Verify node_exporter metrics endpoint
      ansible.builtin.uri:
        url: "http://{{ ansible_host | default(inventory_hostname) }}:9100/metrics"
        method: GET
        status_code: 200
      register: metrics_check
      delegate_to: localhost
      retries: 3
      delay: 5
      until: metrics_check.status == 200

    - name: Re-add node to load balancer
      ansible.builtin.uri:
        url: "http://{{ lb_host }}/api/v1/undrain/{{ inventory_hostname }}"
        method: POST
        status_code: [200, 204]
      delegate_to: localhost
      when: lb_host is defined
      ignore_errors: true

    - name: Log successful update
      ansible.builtin.debug:
        msg: "{{ inventory_hostname }} successfully updated and verified"
```

`serial: 1` means Ansible processes one host at a time through the entire play cycle. You can also specify a list — `serial: [1, 2, 5, "10%"]` — to start cautiously with one host, then increase batch size progressively once you gain confidence in the new version. `max_fail_percentage: 0` means any single host failure aborts the entire play, protecting the remaining fleet.

---

## Best Practices

1. **Always include a `checksum` on every `get_url` task.** Without it, a corrupted or MITM-substituted binary will install silently. A SHA-256 mismatch causes an immediate task failure before the binary is placed on disk.

2. **Use `validate:` on every `template` task that writes a config file for a daemon.** The `promtool check config %s` and `nginx -t -c %s` patterns catch syntax errors before the running daemon is restarted, turning a potential outage into a failed playbook run.

3. **Pin versions in `defaults/main.yml`, not in tasks.** Setting `node_exporter_version: "1.8.2"` in defaults lets you upgrade the entire fleet by changing one variable and re-running the playbook, rather than hunting through task files.

4. **Use `notify` + handlers instead of `ansible.builtin.systemd: state: restarted` in tasks.** Handlers fire once at the end of a play regardless of how many tasks notified them, preventing a service from restarting multiple times when several config files change in one run.

5. **Set `max_fail_percentage: 0` for all production rolling updates.** A batch size of one host with zero tolerance for failure means a bad change affects exactly one node before the playbook stops, making rollback a matter of reverting one host rather than thirty.

6. **Store Alertmanager credentials in Ansible Vault, not in group_vars plaintext.** Alertmanager SMTP passwords, PagerDuty keys, and Slack webhooks are sensitive. Use `ansible-vault encrypt_string` to store them in vault-encrypted variables that are checked into the repository safely.

7. **Use `when: ansible_os_family == "Debian"` guards on `apt` tasks.** A fleet that mixes Ubuntu and RHEL/Rocky nodes will fail on `apt` tasks run against non-Debian hosts. Explicit guards make roles portable and surface mismatches early.

8. **Use `delegate_to: localhost` for HTTP health checks in `post_tasks`.** The Ansible control node is outside the host being updated, making it the correct vantage point for end-to-end verification. Checking a port from the same host tells you the service started; checking it from the control node tells you it's reachable from the network.

9. **Add `creates:` to `unarchive` tasks.** Without `creates:`, the `unarchive` module re-extracts the tarball on every playbook run even if the binary is already present and unchanged, wasting time and generating unnecessary diff output.

10. **Schedule maintenance playbooks with `ansible.builtin.cron` rather than crontab entries managed outside Ansible.** A cron entry managed by Ansible is visible in version control, auditable, and idempotent. An out-of-band cron entry is invisible to the playbook and will cause divergence.

---

## Use Cases

### Bootstrapping Observability for a New AI Server Cluster

A team provisions twelve A100 servers for a new LLM fine-tuning project. Before any training jobs run, they need to verify that GPU utilisation, memory pressure, and temperature behave as expected under load — and get paged if a GPU goes offline during an overnight run.

The team runs the `site.yml` playbook against the new cluster. Ansible deploys `node_exporter` and `dcgm_exporter` on all twelve GPU nodes, stands up Prometheus and Alertmanager on a dedicated monitoring node, and provisions Grafana with GPU dashboards imported from the NVIDIA community dashboard set. The `GPUExporterDown` alert is configured to page the on-call engineer within two minutes of a GPU node going unreachable.

**Concepts applied:** binary install + systemd (node_exporter, dcgm_exporter), template-generated `prometheus.yml` with inventory-driven scrape targets, Grafana provisioning, Alertmanager critical-severity routing to PagerDuty.

**Expected outcome:** Within thirty minutes of running the playbook, all twelve nodes appear in Grafana's GPU dashboard, training job GPU utilisation is visible in real time, and a test alert fires and routes correctly to the on-call rotation.

### Monthly Security Patching Without Service Disruption

A production inference cluster serves live API traffic. The security team requires all OS packages to be current within thirty days of release, but a simultaneous reboot of all nodes would take the API offline.

An operator runs the `update_fleet.yml` playbook with `serial: 1`. Ansible patches one node at a time: runs `dist-upgrade`, checks `/var/run/reboot-required`, reboots if needed, waits for `node_exporter` to come back on port 9100, and verifies the metrics endpoint responds before moving to the next node. The entire thirty-node cluster is patched within a maintenance window with zero API downtime.

**Concepts applied:** `apt` module with `upgrade: dist`, `reboot` module, `wait_for` in `post_tasks`, rolling update with `serial: 1` and `max_fail_percentage: 0`.

**Expected outcome:** All nodes show updated package versions; `node_exporter` confirms all nodes returned to service; the Prometheus scrape gap per node is less than five minutes.

### Certificate Expiry Audit Before a Compliance Review

A company's internal AI API gateway uses mutual TLS. A compliance review requires proof that no certificate expires within the next thirty days. Manually SSH-ing to forty nodes and running `openssl x509 -enddate` is error-prone and not repeatable.

An operator runs `check_certificates.yml` against the full fleet. Ansible reads each certificate file using `community.crypto.x509_certificate_info`, calculates days remaining, prints a warning for any certificate within thirty days, and fails the playbook if any certificate falls within the seven-day critical window.

**Concepts applied:** `community.crypto.x509_certificate_info`, Ansible facts and `set_fact`, conditional `fail` with threshold variables.

**Expected outcome:** The playbook produces a structured report of all certificate expiry dates. Any certificate within seven days causes a non-zero exit code that fails the CI job, triggering an immediate renewal workflow.

### Disk Space Early Warning Before a Long Training Run

A team is about to launch a 72-hour LLM pre-training run that will write model checkpoints every two hours. Before starting, they want to confirm that every node has at least 200 GiB free on its checkpoint volume.

An operator runs `disk_space_check.yml` against the training cluster. Ansible gathers facts on all nodes, filters `ansible_mounts` to the checkpoint volume, and fails the playbook for any node below the threshold. The run does not start until every node clears the check.

**Concepts applied:** `ansible_mounts` fact, `selectattr` Jinja2 filter, `assert` module, threshold variables in `vars`.

**Expected outcome:** The playbook exits zero if all nodes have sufficient space, or lists the specific nodes and mounts that are below threshold so they can be remediated before the run begins.

---

## Hands-on Examples

### Example 1: Deploy node_exporter on a Single Host and Verify Metrics

This example walks through creating the `node_exporter` role from scratch, running it against a single test host, and confirming the metrics endpoint responds correctly.

1. Create the role directory structure:

   ```bash
   mkdir -p roles/node_exporter/{tasks,templates,handlers,defaults}
   ```

2. Write `roles/node_exporter/defaults/main.yml`:

   ```yaml
   node_exporter_version: "1.8.2"
   node_exporter_checksum: "sha256:6809dd0b3ec45fd6e992c19071d6b5253aed3ead7bf0686885a51d85c6643c66"
   node_exporter_port: "9100"
   ```

   > Before running: confirm this checksum at https://github.com/prometheus/node_exporter/releases/tag/v1.8.2

3. Write `roles/node_exporter/handlers/main.yml`:

   ```yaml
   ---
   - name: Reload systemd
     ansible.builtin.systemd:
       daemon_reload: true

   - name: Restart node_exporter
     ansible.builtin.systemd:
       name: node_exporter
       state: restarted
   ```

4. Write the systemd unit template at `roles/node_exporter/templates/node_exporter.service.j2` (use the template shown in the Key Concepts section above).

5. Write `roles/node_exporter/tasks/main.yml` (use the task list shown in the Key Concepts section above).

6. Write a playbook `deploy_node_exporter.yml`:

   ```yaml
   ---
   - name: Deploy node_exporter
     hosts: test_node
     become: true
     roles:
       - node_exporter
   ```

7. Run the playbook:

   ```bash
   ansible-playbook -i inventory.yml deploy_node_exporter.yml
   ```

   Expected output (abbreviated):

   ```
   PLAY [Deploy node_exporter] ************************************

   TASK [node_exporter : Create node_exporter system user] ********
   changed: [test-gpu-01]

   TASK [node_exporter : Download node_exporter tarball] **********
   changed: [test-gpu-01]

   TASK [node_exporter : Install node_exporter binary] ************
   changed: [test-gpu-01]

   TASK [node_exporter : Deploy node_exporter systemd unit] *******
   changed: [test-gpu-01]

   RUNNING HANDLERS ***********************************************
   changed: [test-gpu-01] (Reload systemd)
   changed: [test-gpu-01] (Restart node_exporter)

   PLAY RECAP *****************************************************
   test-gpu-01 : ok=6 changed=6 unreachable=0 failed=0
   ```

8. Verify the metrics endpoint from the control node:

   ```bash
   curl -s http://test-gpu-01:9100/metrics | grep node_cpu_seconds_total | head -5
   ```

   Expected output:

   ```
   # HELP node_cpu_seconds_total Seconds the CPUs spent in each mode.
   # TYPE node_cpu_seconds_total counter
   node_cpu_seconds_total{cpu="0",mode="idle"} 12345.67
   node_cpu_seconds_total{cpu="0",mode="iowait"} 23.45
   node_cpu_seconds_total{cpu="0",mode="irq"} 0
   ```

9. Run the playbook a second time to verify idempotency:

   ```bash
   ansible-playbook -i inventory.yml deploy_node_exporter.yml
   ```

   Expected output: all tasks show `ok` (not `changed`), and no handler fires.

### Example 2: Generate prometheus.yml from Inventory and Validate It

This example demonstrates the template-driven Prometheus config with `promtool` validation.

1. Create an inventory file `inventory.yml` with GPU and CPU-only nodes:

   ```yaml
   all:
     children:
       all_fleet:
         hosts:
           gpu-node-01:
             ansible_host: 10.0.1.11
             server_role: training
             gpu_model: A100-80GB
           gpu-node-02:
             ansible_host: 10.0.1.12
             server_role: training
             gpu_model: A100-80GB
           cpu-node-01:
             ansible_host: 10.0.1.21
             server_role: inference
       gpu_nodes:
         hosts:
           gpu-node-01:
           gpu-node-02:
       monitoring:
         hosts:
           monitor-01:
             ansible_host: 10.0.1.5
   ```

2. Set group_vars in `group_vars/monitoring/vars.yml`:

   ```yaml
   prometheus_version: "2.53.0"
   prometheus_checksum: "sha256:d4f89eef23ab9659dafd31e2afe55acdb18e3b4d53de8a51a2b5e2e04a99d6ab"
   prometheus_data_dir: /var/lib/prometheus
   prometheus_cluster_name: ai-fleet-prod
   alertmanager_host: monitor-01
   ```

   > Before running: verify this checksum at https://github.com/prometheus/prometheus/releases

3. Render the template locally to preview the output (without connecting to the monitoring host):

   ```bash
   ansible -i inventory.yml monitor-01 -m template \
     -a "src=roles/prometheus/templates/prometheus.yml.j2 dest=/tmp/prometheus_preview.yml" \
     --check --diff
   ```

4. Deploy the Prometheus role:

   ```bash
   ansible-playbook -i inventory.yml site.yml --limit monitoring
   ```

5. Verify `promtool` accepted the config on the remote host:

   ```bash
   ansible -i inventory.yml monitor-01 -m ansible.builtin.command \
     -a "/usr/local/bin/promtool check config /etc/prometheus/prometheus.yml" \
     --become
   ```

   Expected output:

   ```
   monitor-01 | CHANGED | rc=0 >>
   Checking /etc/prometheus/prometheus.yml
     SUCCESS: 1 rule files found
    SUCCESS: rules found
   ```

6. Query the Prometheus API to confirm both GPU nodes are being scraped:

   ```bash
   curl -s 'http://10.0.1.5:9090/api/v1/targets' | \
     python3 -c "import json,sys; [print(t['labels']['instance'], t['health']) for t in json.load(sys.stdin)['data']['activeTargets']]"
   ```

   Expected output:

   ```
   gpu-node-01 up
   gpu-node-02 up
   cpu-node-01 up
   monitor-01 up
   ```

### Example 3: Disk Space Check Playbook on Live Fleet

This example runs a standalone disk-space audit that produces a human-readable report and exits non-zero if any node is critically full.

1. Create `playbooks/disk_space_check.yml` (use the full playbook from the Key Concepts section above).

2. Run against the entire fleet:

   ```bash
   ansible-playbook -i inventory.yml playbooks/disk_space_check.yml
   ```

   Expected output on a healthy fleet:

   ```
   PLAY [Check disk space using Ansible facts] ********************

   TASK [Gathering Facts] *****************************************
   ok: [gpu-node-01]
   ok: [gpu-node-02]
   ok: [cpu-node-01]

   TASK [Report mounts above warning threshold] *******************
   skipping: [gpu-node-01] => (item={'mount': '/', ...})
   skipping: [gpu-node-02] => (item={'mount': '/', ...})
   ok: [cpu-node-01] => (item=...) =>
     msg: "/data: 82.3% used (183.4 GiB free of 1024.0 GiB)"

   TASK [Fail on mounts above critical threshold] *****************
   skipping: [gpu-node-01]
   skipping: [gpu-node-02]
   skipping: [cpu-node-01]

   PLAY RECAP *****************************************************
   gpu-node-01 : ok=2 changed=0 unreachable=0 failed=0
   gpu-node-02 : ok=2 changed=0 unreachable=0 failed=0
   cpu-node-01 : ok=3 changed=0 unreachable=0 failed=0
   ```

3. To test the critical failure path, temporarily lower the threshold:

   ```bash
   ansible-playbook -i inventory.yml playbooks/disk_space_check.yml \
     -e "disk_critical_threshold_pct=5"
   ```

   On a node with `/data` at 82% used this still skips; change the threshold to `80` to trigger a failure:

   ```bash
   ansible-playbook -i inventory.yml playbooks/disk_space_check.yml \
     -e "disk_critical_threshold_pct=80"
   ```

   Expected output on `cpu-node-01`:

   ```
   TASK [Fail on mounts above critical threshold] *****************
   fatal: [cpu-node-01]: FAILED! =>
     msg: "CRITICAL: /data is 82.3% full on cpu-node-01"

   PLAY RECAP *****************************************************
   cpu-node-01 : ok=2 changed=0 unreachable=0 failed=1
   ```

### Example 4: Rolling dist-upgrade Across a Three-Node Subset

This example runs a controlled `dist-upgrade` across three nodes with pre-task health checks, automatic reboot if needed, and post-task verification.

1. Create a `maintenance` host group in your inventory pointing to three nodes.

2. Create `playbooks/update_fleet.yml` (use the full playbook from the Key Concepts section above).

3. Run a dry-run first with `--check`:

   ```bash
   ansible-playbook -i inventory.yml playbooks/update_fleet.yml \
     --limit maintenance --check --diff
   ```

4. Run the actual update:

   ```bash
   ansible-playbook -i inventory.yml playbooks/update_fleet.yml \
     --limit maintenance
   ```

   Expected output sequence for one node (three similar blocks appear, one per host):

   ```
   TASK [Apply dist-upgrade] **************************************
   changed: [gpu-node-01]

   TASK [Check if reboot is required] *****************************
   ok: [gpu-node-01]

   TASK [Reboot if kernel was updated] ****************************
   changed: [gpu-node-01]

   TASK [Verify node_exporter is running after update] ************
   ok: [gpu-node-01]

   TASK [Fail loudly if exporter is not running] ******************
   skipping: [gpu-node-01]
   ```

5. Confirm all nodes are patched by checking the apt history log:

   ```bash
   ansible -i inventory.yml maintenance -m ansible.builtin.shell \
     -a "grep 'dist-upgrade' /var/log/apt/history.log | tail -1" \
     --become
   ```

   Expected output on each node:

   ```
   gpu-node-01 | CHANGED | rc=0 >>
   Commandline: apt-get dist-upgrade -y
   ```

---

## Common Pitfalls

### Pitfall 1: Forgetting daemon_reload Before Enabling a New Unit File

**Description:** After writing a new systemd unit file with the `template` or `copy` module, the `systemd` module fails with "Unit not found" or silently uses a stale cached unit definition.

**Why it happens:** systemd caches unit file definitions in memory. Until `systemctl daemon-reload` runs, the new file on disk is not visible to systemd.

**Incorrect pattern:**

```yaml
- name: Deploy unit file
  ansible.builtin.template:
    src: node_exporter.service.j2
    dest: /etc/systemd/system/node_exporter.service

- name: Enable service
  ansible.builtin.systemd:
    name: node_exporter
    state: started
    enabled: true
```

**Correct pattern:**

```yaml
- name: Deploy unit file
  ansible.builtin.template:
    src: node_exporter.service.j2
    dest: /etc/systemd/system/node_exporter.service
  notify:
    - Reload systemd
    - Restart node_exporter

# In handlers/main.yml:
- name: Reload systemd
  ansible.builtin.systemd:
    daemon_reload: true

- name: Restart node_exporter
  ansible.builtin.systemd:
    name: node_exporter
    state: restarted
```

Alternatively: `ansible.builtin.systemd: daemon_reload: true` can be set directly on the enable task, but using handlers ensures it only fires when the unit file actually changed.

### Pitfall 2: Using serial Without max_fail_percentage

**Description:** A rolling update with `serial: 1` but no `max_fail_percentage` will continue updating remaining nodes even after one node fails, potentially rolling a broken change to the entire fleet.

**Why it happens:** Without `max_fail_percentage`, Ansible's default behaviour is to continue with remaining hosts when one host in a serial batch fails.

**Incorrect pattern:**

```yaml
- name: Rolling update
  hosts: all_fleet
  serial: 1
```

**Correct pattern:**

```yaml
- name: Rolling update
  hosts: all_fleet
  serial: 1
  max_fail_percentage: 0
```

`max_fail_percentage: 0` means zero hosts in any batch may fail before the play aborts entirely.

### Pitfall 3: Jinja2 Curly Braces in Prometheus Alert Rule Templates

**Description:** Prometheus alert rule files use `{{ $labels.instance }}` syntax. When Ansible processes a `.j2` template, it interprets `{{ }}` as Jinja2 expressions and errors or substitutes empty strings.

**Why it happens:** Both Jinja2 and PromQL use double curly braces for variable interpolation. Ansible processes the template before it reaches Prometheus.

**Incorrect pattern** (in a `.j2` template file):

```yaml
annotations:
  summary: "High CPU on {{ $labels.instance }}"
```

**Correct pattern** (escape the PromQL curly braces using Jinja2 raw escaping):

```yaml
annotations:
  summary: "High CPU on {{ '{{' }} $labels.instance {{ '}}' }}"
```

Or use Jinja2's `{% raw %}` block for multi-line sections with many PromQL references:

```yaml
{% raw %}
annotations:
  summary: "High CPU on {{ $labels.instance }}"
  description: "{{ $value | humanize }}% CPU on {{ $labels.instance }}"
{% endraw %}
```

### Pitfall 4: Scrape Targets Using inventory_hostname Instead of ansible_host

**Description:** The generated `prometheus.yml` contains hostnames that Prometheus cannot resolve, so targets appear as "down" even though the exporters are running.

**Why it happens:** `inventory_hostname` is the key used in the inventory file, which may be a logical name (`gpu-node-01`) rather than a routable IP or FQDN. Prometheus must be able to reach the target over the network.

**Incorrect pattern** (in `prometheus.yml.j2`):

```yaml
{% for host in groups['all_fleet'] %}
      - targets:
          - "{{ host }}:9100"
{% endfor %}
```

**Correct pattern:**

```yaml
{% for host in groups['all_fleet'] %}
      - targets:
          - "{{ hostvars[host]['ansible_host'] | default(host) }}:9100"
{% endfor %}
```

The `| default(host)` fallback handles cases where `ansible_host` is not explicitly set.

### Pitfall 5: Not Pinning Grafana's Package Version

**Description:** Re-running the playbook after a new Grafana minor release upgrades Grafana unexpectedly, potentially breaking provisioned dashboards or plugin compatibility.

**Why it happens:** `apt: name: grafana state: present` with no version installed the package as-is on the first run, but `state: present` will not upgrade it on subsequent runs. However, if the playbook uses `state: latest`, it upgrades on every run.

**Incorrect pattern:**

```yaml
- name: Install Grafana
  ansible.builtin.apt:
    name: grafana
    state: latest
```

**Correct pattern:**

```yaml
- name: Install Grafana
  ansible.builtin.apt:
    name: "grafana={{ grafana_version }}"
    state: present
```

With `grafana_version: "11.1.0"` in group_vars, the version is explicit, auditable, and upgraded deliberately.

### Pitfall 6: Missing ignore_errors on Certificate Check When File Does Not Exist

**Description:** The `community.crypto.x509_certificate_info` task fails hard on a host where the certificate file does not exist, rather than recording the missing cert as a finding.

**Why it happens:** If a certificate path is listed in `cert_paths` but the file was never deployed to a particular host, the module raises a fatal error and skips all subsequent hosts in the play.

**Incorrect pattern:**

```yaml
- name: Read certificate information
  community.crypto.x509_certificate_info:
    path: "{{ item }}"
  loop: "{{ cert_paths }}"
  register: cert_info
```

**Correct pattern:**

```yaml
- name: Read certificate information
  community.crypto.x509_certificate_info:
    path: "{{ item }}"
  loop: "{{ cert_paths }}"
  register: cert_info
  ignore_errors: true

- name: Report missing certificate files
  ansible.builtin.debug:
    msg: "Certificate file not found: {{ item.item }} on {{ inventory_hostname }}"
  loop: "{{ cert_info.results }}"
  when: item.failed | default(false)
```

### Pitfall 7: Running apt upgrade: dist Without Checking for Reboot

**Description:** Kernel updates applied by `dist-upgrade` require a reboot to take effect. If the `reboot` task is omitted, the old kernel continues running, security patches that require a new kernel are not active, and node_exporter may report the wrong kernel version to Prometheus.

**Why it happens:** `ansible.builtin.apt` with `upgrade: dist` does not reboot automatically. Ansible has no way to know whether a reboot is semantically required — it only knows which packages changed.

**Incorrect pattern:**

```yaml
- name: Apply dist-upgrade
  ansible.builtin.apt:
    upgrade: dist
```

**Correct pattern:**

```yaml
- name: Apply dist-upgrade
  ansible.builtin.apt:
    upgrade: dist

- name: Check if reboot is required
  ansible.builtin.stat:
    path: /var/run/reboot-required
  register: reboot_required

- name: Reboot if kernel was updated
  ansible.builtin.reboot:
    reboot_timeout: 300
  when: reboot_required.stat.exists
```

Ubuntu's `update-notifier-common` package writes `/var/run/reboot-required` whenever a package update requires a restart. Checking that file is the canonical way to detect this condition.

---

## Summary

- Ansible manages an entire observability stack — node_exporter, DCGM Exporter, Prometheus, Grafana, and Alertmanager — by composing focused roles, each following the binary-install + systemd pattern, with version-pinned defaults and checksum-verified downloads.
- The `template` module with Jinja2 iteration over inventory groups generates a `prometheus.yml` that is always consistent with the live fleet; the `validate:` parameter uses `promtool` to catch syntax errors before any running service is restarted.
- Alerting for GPU memory saturation, CPU load, disk space, and exporter availability is expressed as PromQL rules deployed alongside Prometheus, with Alertmanager routing warnings to email and critical alerts to PagerDuty.
- Recurring maintenance tasks — `dist-upgrade`, log rotation, and certificate audits — are expressed as standalone playbooks that use Ansible facts and module return values rather than external tooling, making them runnable from any control node without extra infrastructure.
- Rolling updates use `serial: 1` and `max_fail_percentage: 0` with `pre_tasks` health gates and `post_tasks` endpoint verification to guarantee that a bad change affects at most one node before the play stops, making the fleet safe to maintain without downtime.

---

## Further Reading

- [Prometheus node_exporter — Official Documentation](https://prometheus.io/docs/guides/node-exporter/) — Covers the full list of built-in collectors, command-line flags, and how to enable optional collectors like `--collector.systemd`; essential reading before customising the ExecStart line in the unit template.
- [NVIDIA DCGM Exporter — GitHub Repository and Releases](https://github.com/NVIDIA/dcgm-exporter) — The canonical source for release binaries, SHA-256 checksums, the default counter CSV format, and the list of DCGM field IDs available for export; check here before pinning a version in role defaults.
- [Prometheus Configuration Reference](https://prometheus.io/docs/prometheus/latest/configuration/configuration/) — Complete reference for every field in `prometheus.yml` including scrape interval overrides, relabelling rules, TLS configuration, and remote write; use this when extending the Jinja2 template beyond basic static targets.
- [Grafana Provisioning Documentation](https://grafana.com/docs/grafana/latest/administration/provisioning/) — Explains the full data source and dashboard provisioning file format, including the `allowUiUpdates` and `disableDeletion` options and how Grafana handles provisioned versus user-created dashboards across restarts.
- [Ansible ansible.builtin.systemd Module](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/systemd_module.html) — Reference for all parameters including `daemon_reload`, `scope`, and `force`; particularly important for understanding the difference between `state: started` (idempotent) and `state: restarted` (always restarts).
- [Ansible community.general.logrotate Module](https://docs.ansible.com/ansible/latest/collections/community/general/logrotate_module.html) — Documents all logrotate directives that the module supports, including `postrotate` scripts and `su` directives; required reading before using this module on logs owned by non-root service accounts.
- [Prometheus Alerting Rules Documentation](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/) — Covers the full PromQL syntax for alert expressions, the `for` duration field, label and annotation templating with `$labels` and `$value`, and `promtool` validation commands; the authoritative reference for writing the alert rules template.
- [Ansible Rolling Updates Pattern — Official Guide](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_strategies.html) — Explains all values for `serial` (integer, percentage, list), interaction with `max_fail_percentage`, and the `any_errors_fatal` directive; covers the difference between linear and free strategies for large fleets.
