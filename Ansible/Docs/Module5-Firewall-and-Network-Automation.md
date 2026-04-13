# Module 5: Firewall & Network Automation
> Subject: Ansible | Difficulty: Intermediate | Estimated Time: 210 minutes

## Objective

After completing this module, you will be able to automate firewall policy enforcement across a fleet of AI servers using Ansible. You will apply `ufw` rules with full parameter control (`state`, `rule`, `direction`, `port`, `proto`, `from_ip`), manage low-level packet filtering with the `iptables` module, configure network interfaces and static IP addresses with the `nmcli` module, manage `/etc/hosts` for internal service discovery, deploy `dnsmasq` as a lightweight internal DNS server, harden the SSH daemon by modifying `sshd_config` with the `lineinfile` module, automate `fail2ban` deployment with a role, and apply different firewall profiles to `dev` and `prod` inventory groups so that development servers receive open internal access while production servers accept only HTTPS and SSH from a designated bastion host — all while writing idempotent rules that will never disrupt existing connections during a playbook run.

## Prerequisites

- Completed Module 1: Ansible Fundamentals — comfortable with inventory files, ad-hoc commands, and the structure of a playbook
- Completed Module 2: Playbook Authoring — familiar with tasks, handlers, variables, and `when` conditionals
- Completed Module 3: Roles & Galaxy — able to create and apply Ansible roles, use `defaults/main.yml`, and import community roles
- Completed Module 4: Variables, Templates & Vault — comfortable with `group_vars/`, Jinja2 templates, and Vault-encrypted secrets
- Ansible 2.16 or later installed on the control node (verify with `ansible --version`)
- Ten target hosts running Ubuntu 22.04 LTS or RHEL 9 with SSH key authentication configured
- Basic knowledge of Linux networking concepts: subnets, ports, protocols, and packet filtering chains (INPUT, OUTPUT, FORWARD)

## Key Concepts

### The `community.general.ufw` Module

UFW (Uncomplicated Firewall) is the default firewall management layer on Ubuntu and Debian systems. It wraps `iptables`/`nftables` with a simplified CLI and API. Ansible's `community.general.ufw` module lets you drive every aspect of UFW declaratively, so firewall rules are reproduced identically on every host in a play with no manual intervention.

The module's most important parameters are:

| Parameter | Purpose | Common values |
|---|---|---|
| `state` | Operational state of the rule or the firewall service itself | `enabled`, `disabled`, `present`, `absent`, `reset` |
| `rule` | Action to take on matching traffic | `allow`, `deny`, `reject`, `limit` |
| `direction` | Which traffic direction the rule applies to | `in`, `out`, `routed` |
| `port` | Destination port or port range | `22`, `443`, `8000:9000` |
| `proto` | Layer 4 protocol | `tcp`, `udp`, `any` |
| `from_ip` | Source IP address or CIDR block | `10.0.0.0/8`, `192.168.1.5` |
| `to_ip` | Destination IP address or CIDR block | `any`, `192.168.10.0/24` |
| `interface` | Restrict rule to a specific network interface | `eth0`, `ens3` |
| `log` | Whether to log matched packets | `true`, `false` |
| `comment` | A label stored in UFW's rule database | Any descriptive string |

The key distinction between `state: enabled` and `state: present` is scope: `enabled` controls whether the firewall service itself is running; `present` adds or confirms that a specific rule exists without touching the service's on/off status. In practice you use `enabled` once (usually as the first UFW task in a play) and `present` for each subsequent rule.

```yaml
# Enable the firewall service itself — must come before any rule tasks
- name: Enable UFW and set default policies
  community.general.ufw:
    state: enabled
    policy: deny           # default incoming policy
    direction: incoming

- name: Allow SSH on port 22 from the bastion host only
  community.general.ufw:
    rule: allow
    direction: in
    port: "22"
    proto: tcp
    from_ip: "10.0.0.5"   # bastion IP
    comment: "SSH from bastion"

- name: Allow HTTPS from anywhere
  community.general.ufw:
    rule: allow
    direction: in
    port: "443"
    proto: tcp
    comment: "HTTPS inbound"
```

Every task above is idempotent: if the rule already exists with identical parameters, UFW reports no change. If a prior rule differs only in its comment, Ansible will add a new rule rather than modify in place — so keep comments consistent across runs, or omit them if you are concerned about drift.

### Managing `iptables` with the `ansible.builtin.iptables` Module

For systems that use `iptables` directly — RHEL/CentOS without `firewalld`, minimal container-host images, or situations where you need per-packet granularity not available in UFW — Ansible ships the `ansible.builtin.iptables` module as part of the core collection. Unlike UFW, it maps nearly one-to-one with `iptables` CLI arguments.

Critical parameters to know:

| Parameter | Equivalent `iptables` flag | Notes |
|---|---|---|
| `chain` | `-A`/`-I` chain name | `INPUT`, `OUTPUT`, `FORWARD`, or a custom chain |
| `protocol` | `-p` | `tcp`, `udp`, `icmp`, `all` |
| `source` | `-s` | Source CIDR, e.g. `10.0.0.0/8` |
| `destination` | `-d` | Destination CIDR |
| `destination_port` | `--dport` | Single port or range (`8000:9000`) |
| `jump` | `-j` | Target: `ACCEPT`, `DROP`, `REJECT`, `LOG` |
| `in_interface` | `-i` | Incoming interface filter |
| `state` | — | `present` adds the rule; `absent` removes it |
| `ip_version` | — | `ipv4` or `ipv6` (runs `ip6tables` for the latter) |

One important caveat: `iptables` rules added at runtime do not survive a reboot unless they are saved. You must either use the `ansible.builtin.iptables` module with the `save: true` parameter when saving via `iptables-save` piped to a file, or install `iptables-persistent` and notify it via a handler.

```yaml
- name: Accept established and related connections (must be first)
  ansible.builtin.iptables:
    chain: INPUT
    ctstate:
      - ESTABLISHED
      - RELATED
    jump: ACCEPT

- name: Accept SSH from internal management subnet
  ansible.builtin.iptables:
    chain: INPUT
    protocol: tcp
    source: "10.0.1.0/24"
    destination_port: "22"
    jump: ACCEPT

- name: Drop all other inbound traffic
  ansible.builtin.iptables:
    chain: INPUT
    policy: DROP    # sets default chain policy, not a rule

- name: Persist iptables rules across reboots (Debian/Ubuntu)
  ansible.builtin.shell: |
    iptables-save > /etc/iptables/rules.v4
  args:
    creates: /etc/iptables/rules.v4
```

<!-- verify: the `policy` parameter behavior when used on INPUT chain — confirm it sets the default chain policy rather than inserting a DROP rule -->

Always insert a rule accepting `ESTABLISHED` and `RELATED` traffic before any restrictive policy. Omitting this rule will drop return packets for all active TCP sessions the moment Ansible applies the DROP policy, severing the very SSH connection that is running the playbook.

### Network Interface Configuration with `nmcli`

On systemd-based Linux distributions — including RHEL 8+, Rocky Linux, AlmaLinux, Fedora, and Ubuntu 20.04+ when NetworkManager is present — the `community.general.nmcli` module is the correct way to configure network interfaces declaratively. It manages NetworkManager connection profiles, which persist across reboots automatically.

The module models each interface configuration as a **connection profile** identified by a `conn_name`. Key parameters:

| Parameter | Purpose |
|---|---|
| `conn_name` | Unique name for the NetworkManager connection profile |
| `ifname` | The underlying network interface (e.g., `eth0`, `ens3`, `bond0`) |
| `type` | Connection type: `ethernet`, `bond`, `bridge`, `vlan`, `wifi`, `ipip` |
| `ip4` | Static IPv4 address in CIDR notation (e.g., `192.168.10.5/24`) |
| `gw4` | IPv4 default gateway |
| `dns4` | List of IPv4 DNS servers |
| `state` | `present` creates/updates; `absent` removes; `up` activates; `down` deactivates |
| `autoconnect` | Whether to bring the connection up at boot |

```yaml
- name: Configure static IP on the primary interface
  community.general.nmcli:
    conn_name: "primary-static"
    ifname: "{{ ansible_default_ipv4.interface }}"
    type: ethernet
    ip4: "{{ static_ip }}/{{ prefix_length }}"
    gw4: "{{ gateway }}"
    dns4:
      - "10.0.0.53"
      - "8.8.8.8"
    state: present
    autoconnect: true
  notify: Restart NetworkManager
```

For Ubuntu systems without NetworkManager, the older `interfaces_file` module (`community.general.interfaces_file`) can modify `/etc/network/interfaces` directly, but this approach is largely superseded by NetworkManager in current Ubuntu releases. Prefer `nmcli` on any modern distribution.

### Managing `/etc/hosts` for Internal Service Discovery

Before DNS propagates — or in isolated environments where no internal DNS server exists — `/etc/hosts` provides a fast, authoritative name-to-IP mapping that requires zero infrastructure. In an AI server fleet, `/etc/hosts` is commonly used to map cluster-internal service names (`model-api.internal`, `vector-db.internal`) to stable IPs.

Ansible provides two good approaches: the `ansible.builtin.lineinfile` module for targeted additions, and the `ansible.builtin.template` module for managing the entire file from a Jinja2 template.

The template approach is safer for fleets because it makes the entire file's contents predictable and auditable:

```jinja2
{# templates/hosts.j2 #}
127.0.0.1   localhost
127.0.1.1   {{ inventory_hostname }}

# AI fleet — managed by Ansible, do not edit manually
{% for host in groups['ai_servers'] %}
{{ hostvars[host]['ansible_host'] }}  {{ host }}.internal  {{ host }}
{% endfor %}

# Shared services
10.0.0.10   model-api.internal    model-api
10.0.0.11   vector-db.internal    vector-db
10.0.0.12   metrics.internal      metrics
```

```yaml
- name: Deploy /etc/hosts from template
  ansible.builtin.template:
    src: templates/hosts.j2
    dest: /etc/hosts
    owner: root
    group: root
    mode: "0644"
    backup: true
```

The `backup: true` parameter instructs Ansible to write the previous `/etc/hosts` to a timestamped copy before overwriting, providing a quick rollback path.

### Setting Up Internal DNS with `dnsmasq`

For larger fleets or when you need wildcard DNS records, DHCP integration, or PTR records for reverse lookups, `dnsmasq` is a lightweight DNS forwarder that can be deployed in minutes with Ansible. A typical AI fleet uses dnsmasq on a dedicated management server (`10.0.0.53`) to resolve `*.internal` hostnames, forwarding all other queries upstream.

The deployment pattern uses three Ansible tasks: install the package, template the configuration, and manage the service.

```yaml
- name: Install dnsmasq
  ansible.builtin.package:
    name: dnsmasq
    state: present

- name: Deploy dnsmasq configuration
  ansible.builtin.template:
    src: templates/dnsmasq.conf.j2
    dest: /etc/dnsmasq.conf
    owner: root
    group: root
    mode: "0644"
    validate: "dnsmasq --test --conf-file=%s"
  notify: Restart dnsmasq

- name: Enable and start dnsmasq
  ansible.builtin.service:
    name: dnsmasq
    state: started
    enabled: true
```

```jinja2
{# templates/dnsmasq.conf.j2 #}
# dnsmasq configuration — managed by Ansible
domain=internal
local=/internal/
expand-hosts
no-resolv
no-poll

# Upstream DNS servers
server=8.8.8.8
server=1.1.1.1

# Static host records for the AI fleet
{% for host in groups['ai_servers'] %}
address=/{{ host }}.internal/{{ hostvars[host]['ansible_host'] }}
{% endfor %}

# Service records
address=/model-api.internal/10.0.0.10
address=/vector-db.internal/10.0.0.11
address=/metrics.internal/10.0.0.12

listen-address=127.0.0.1,{{ ansible_default_ipv4.address }}
bind-interfaces
```

The `validate` parameter on the template task runs `dnsmasq --test` before writing the file to disk. If the configuration has a syntax error, Ansible aborts the task and leaves the running configuration untouched.

### Hardening `sshd_config` with `lineinfile`

The `ansible.builtin.lineinfile` module is purpose-built for making precise, targeted changes to configuration files where replacing the whole file would be overly invasive. It matches a line using a regular expression (`regexp`) and either replaces the match or inserts `line` if no match is found. This is exactly the right tool for `sshd_config`, where you want to set specific directives without touching every other line.

Key `lineinfile` parameters for `sshd_config` hardening:

| Parameter | Purpose |
|---|---|
| `path` | The file to modify |
| `regexp` | Python-compatible regex to match the target line |
| `line` | The exact line to write when the regexp matches (or when inserting) |
| `state` | `present` ensures the line exists; `absent` removes matching lines |
| `validate` | Shell command to validate the file before it is committed |
| `backup` | Write a timestamped backup before modifying |

```yaml
- name: Harden sshd_config
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: "{{ item.regexp }}"
    line: "{{ item.line }}"
    state: present
    validate: "sshd -t -f %s"
    backup: true
  loop:
    - { regexp: '^#?PermitRootLogin',        line: 'PermitRootLogin no' }
    - { regexp: '^#?PasswordAuthentication', line: 'PasswordAuthentication no' }
    - { regexp: '^#?PubkeyAuthentication',   line: 'PubkeyAuthentication yes' }
    - { regexp: '^#?X11Forwarding',          line: 'X11Forwarding no' }
    - { regexp: '^#?MaxAuthTries',           line: 'MaxAuthTries 3' }
    - { regexp: '^#?LoginGraceTime',         line: 'LoginGraceTime 30' }
    - { regexp: '^#?AllowUsers',             line: 'AllowUsers deploy ansible' }
    - { regexp: '^#?ClientAliveInterval',    line: 'ClientAliveInterval 300' }
    - { regexp: '^#?ClientAliveCountMax',    line: 'ClientAliveCountMax 2' }
  notify: Restart sshd
```

The `validate: "sshd -t -f %s"` directive instructs Ansible to write the changes to a temporary file and run `sshd -t` (config-test mode) against it before replacing the live file. If the config is syntactically invalid, the task fails safely without corrupting the running SSH daemon.

### `fail2ban` Role Automation

`fail2ban` monitors log files for brute-force patterns and bans offending IPs by inserting temporary `iptables`/`nftables` rules. Deploying it via an Ansible role keeps the configuration reproducible and avoids configuration drift across the fleet.

The recommended community role is `geerlingguy.security` or a dedicated `fail2ban` role. The pattern below shows a self-contained role structure so you understand what each piece does even if you use a community role from Ansible Galaxy.

```
roles/
└── fail2ban/
    ├── defaults/
    │   └── main.yml          # tuneable defaults
    ├── tasks/
    │   └── main.yml          # install + configure + service
    ├── templates/
    │   ├── jail.local.j2     # per-environment jail overrides
    │   └── fail2ban.conf.j2  # global daemon settings
    └── handlers/
        └── main.yml          # restart fail2ban on config change
```

```yaml
# roles/fail2ban/defaults/main.yml
fail2ban_bantime: "1h"
fail2ban_findtime: "10m"
fail2ban_maxretry: 5
fail2ban_backend: "systemd"       # use journald log source
fail2ban_ssh_enabled: true
fail2ban_ssh_port: "ssh"
fail2ban_ssh_logpath: "%(sshd_log)s"  # <!-- verify: path variable name in current fail2ban -->
fail2ban_ignoreip:
  - "127.0.0.1/8"
  - "::1"
  - "10.0.0.0/8"   # never ban internal management subnet
```

```yaml
# roles/fail2ban/tasks/main.yml
- name: Install fail2ban
  ansible.builtin.package:
    name: fail2ban
    state: present

- name: Deploy fail2ban jail configuration
  ansible.builtin.template:
    src: jail.local.j2
    dest: /etc/fail2ban/jail.local
    owner: root
    group: root
    mode: "0644"
  notify: Restart fail2ban

- name: Enable and start fail2ban
  ansible.builtin.service:
    name: fail2ban
    state: started
    enabled: true
```

```jinja2
{# roles/fail2ban/templates/jail.local.j2 #}
[DEFAULT]
bantime  = {{ fail2ban_bantime }}
findtime = {{ fail2ban_findtime }}
maxretry = {{ fail2ban_maxretry }}
backend  = {{ fail2ban_backend }}
ignoreip = {{ fail2ban_ignoreip | join(' ') }}

[sshd]
enabled  = {{ fail2ban_ssh_enabled | lower }}
port     = {{ fail2ban_ssh_port }}
logpath  = {{ fail2ban_ssh_logpath }}
maxretry = {{ fail2ban_maxretry }}
```

### Dev vs. Prod Firewall Profiles with Inventory Groups

Ansible's group variable system (`group_vars/`) is the idiomatic way to apply different policies to different environments. Define your inventory with `dev` and `prod` groups, place environment-specific variable files under `group_vars/`, and write a single parameterised playbook that both groups share.

```
inventory/
├── hosts.ini
├── group_vars/
│   ├── all.yml           # variables shared by every host
│   ├── dev.yml           # dev-specific overrides
│   └── prod.yml          # prod-specific overrides
```

```ini
# inventory/hosts.ini
[dev]
ai-dev-01 ansible_host=10.0.1.11
ai-dev-02 ansible_host=10.0.1.12
ai-dev-03 ansible_host=10.0.1.13

[prod]
ai-prod-01 ansible_host=10.0.2.11
ai-prod-02 ansible_host=10.0.2.12
ai-prod-03 ansible_host=10.0.2.13
ai-prod-04 ansible_host=10.0.2.14
ai-prod-05 ansible_host=10.0.2.15
ai-prod-06 ansible_host=10.0.2.16
ai-prod-07 ansible_host=10.0.2.17

[ai_servers:children]
dev
prod
```

```yaml
# inventory/group_vars/all.yml
ssh_port: 22
management_subnet: "10.0.0.0/8"
internal_subnet: "10.0.0.0/8"
```

```yaml
# inventory/group_vars/dev.yml
firewall_default_policy: allow
firewall_allowed_sources:
  - "10.0.0.0/8"
firewall_open_ports:
  - { port: "22",   proto: tcp }
  - { port: "80",   proto: tcp }
  - { port: "443",  proto: tcp }
  - { port: "8080", proto: tcp }
  - { port: "9000", proto: tcp }
```

```yaml
# inventory/group_vars/prod.yml
firewall_default_policy: deny
bastion_ip: "10.0.0.5"
firewall_allowed_sources:
  - "{{ bastion_ip }}"
firewall_open_ports:
  - { port: "22",  proto: tcp, from_ip: "{{ bastion_ip }}" }
  - { port: "443", proto: tcp, from_ip: "any" }
```

The playbook then loops over `firewall_open_ports` to apply whichever port list is in scope for that inventory group, with no conditionals needed in the task itself:

```yaml
# site.yml (excerpt)
- name: Apply UFW rules from group variables
  community.general.ufw:
    rule: allow
    direction: in
    port: "{{ item.port }}"
    proto: "{{ item.proto }}"
    from_ip: "{{ item.from_ip | default('any') }}"
  loop: "{{ firewall_open_ports }}"
```

## Best Practices

1. **Always accept ESTABLISHED/RELATED traffic before applying a default DROP policy.** This ensures that Ansible's own SSH session — and any open TCP connections on the host — are not terminated mid-playbook when the DROP rule is inserted.

2. **Use `validate:` on every configuration task that has a built-in syntax checker.** Both `sshd -t -f %s` and `dnsmasq --test --conf-file=%s` catch errors before the live file is replaced, preventing a bad config from locking you out of the server.

3. **Never hardcode IP addresses inside task files — put them in `group_vars/` or `host_vars/`.** IPs change; playbooks don't. Centralising them in variable files means a firewall rule update requires editing one YAML file, not hunting through ten playbooks.

4. **Add `comment:` parameters to every UFW rule.** UFW stores comments in its rule database and displays them in `ufw status verbose`, making audits far faster than reading raw `iptables -L` output.

5. **Manage rule order explicitly with `iptables` by using `action: insert` with an explicit `rule_num`.** Appended rules evaluate after all existing rules; if you append an ACCEPT before an existing DROP you may get unexpected ordering. Inserting at position 1 guarantees evaluation priority.

6. **Flush and rebuild iptables rules from scratch rather than appending incrementally.** Incremental append runs accumulate duplicate rules over time, bloating the rule set. Use a block that flushes chains first, then re-adds all rules in the correct order.

7. **Include `fail2ban_ignoreip` covering your Ansible control node and all management subnets.** If Ansible retries a failing task in a rapid loop, `fail2ban` may ban the control node itself, making the fleet unreachable.

8. **Test firewall changes against `dev` before promoting to `prod` by running `--limit dev` first.** Even idempotent rules can have logical errors (wrong CIDR, wrong port); catching them on dev avoids a production outage.

9. **Use `--check --diff` on firewall playbooks before applying to production.** The diff output shows exactly which lines in `/etc/hosts`, `sshd_config`, and `/etc/fail2ban/jail.local` will change, letting you review the delta before it hits the fleet.

10. **Pin the Ansible collection versions in `requirements.yml`.** `community.general` releases can change default parameter behavior across minor versions. Pinning ensures `ansible-galaxy collection install -r requirements.yml` produces the same collection version across all control nodes.

## Use Cases

### AI Fleet Hardening Before a Production Launch

An ML platform team is preparing to move their model inference cluster from a staging environment to production. All ten servers are accessible from the full internal RFC1918 space, and the team needs to lock them down to accept only HTTPS inference requests from clients and SSH only from the designated bastion before the cluster goes live.

The `prod` group variables set `firewall_default_policy: deny`, define the bastion IP, and list only ports 22 (from bastion) and 443 (from any). The single `site.yml` playbook runs against the `prod` group, enables UFW with a deny-incoming default policy, then loops over `firewall_open_ports` to add the two permitted rules. The entire fleet is hardened in a single `ansible-playbook -i inventory/ site.yml --limit prod` run lasting under two minutes.

### Consistent Internal Name Resolution Across a Distributed Training Cluster

A research team runs a distributed GPU training job across eight servers. The training framework resolves node addresses by hostname at job startup. Because cloud provider DNS can be slow or inconsistent, the team wants every server to resolve all peer hostnames from a local `/etc/hosts` file.

The template module renders `/etc/hosts` using a Jinja2 loop over `groups['ai_servers']`, pulling each host's `ansible_host` variable. Every time a node is added to the inventory, a single playbook run distributes the updated `/etc/hosts` to all servers within seconds, eliminating DNS-related training-job failures.

### Protecting the SSH Daemon After a Credential Leak

A security audit reveals that a deployment key was accidentally committed to a public repository. The immediate mitigation is to disable password authentication, reduce `MaxAuthTries`, and restrict `AllowUsers` to only the `deploy` and `ansible` service accounts across all servers.

The `lineinfile` loop in the SSH hardening task applies all five directives atomically, validates the config with `sshd -t` before writing, and notifies the `Restart sshd` handler. The entire fleet is patched in one playbook run; the handler ensures sshd is reloaded only after all `lineinfile` tasks complete successfully.

### Automated Brute-Force Protection with Per-Environment Thresholds

The dev group experiences frequent failed login attempts from developers testing scripts. The prod group needs stricter thresholds before banning. By setting `fail2ban_maxretry: 10` in `group_vars/dev.yml` and `fail2ban_maxretry: 3` in `group_vars/prod.yml`, the same `fail2ban` role deploys with different sensitivity on each group. Running `ansible-playbook -i inventory/ firewall.yml` applies both configurations in one pass, with each host receiving the correct threshold for its environment.

## Hands-on Examples

### Example 1: Apply Dev and Prod UFW Profiles to 10 AI Servers

This example builds the complete inventory and playbook structure used to enforce the dev/prod firewall split described throughout this module. You will run the playbook in check mode first, then apply it for real.

1. Create the project layout:

```bash
mkdir -p ai-fleet/{inventory/group_vars,roles,templates}
cd ai-fleet
```

2. Write the inventory file:

```ini
# inventory/hosts.ini
[dev]
ai-dev-01 ansible_host=10.0.1.11
ai-dev-02 ansible_host=10.0.1.12
ai-dev-03 ansible_host=10.0.1.13

[prod]
ai-prod-01 ansible_host=10.0.2.11
ai-prod-02 ansible_host=10.0.2.12
ai-prod-03 ansible_host=10.0.2.13
ai-prod-04 ansible_host=10.0.2.14
ai-prod-05 ansible_host=10.0.2.15
ai-prod-06 ansible_host=10.0.2.16
ai-prod-07 ansible_host=10.0.2.17

[ai_servers:children]
dev
prod
```

3. Write the group variable files:

```yaml
# inventory/group_vars/all.yml
ansible_user: deploy
ansible_ssh_private_key_file: ~/.ssh/ai_fleet_key
```

```yaml
# inventory/group_vars/dev.yml
firewall_default_incoming: allow
firewall_open_ports:
  - { port: "22",   proto: tcp, from_ip: "10.0.0.0/8" }
  - { port: "80",   proto: tcp, from_ip: "any" }
  - { port: "443",  proto: tcp, from_ip: "any" }
  - { port: "8080", proto: tcp, from_ip: "10.0.0.0/8" }
  - { port: "9000", proto: tcp, from_ip: "10.0.0.0/8" }
```

```yaml
# inventory/group_vars/prod.yml
firewall_default_incoming: deny
bastion_ip: "10.0.0.5"
firewall_open_ports:
  - { port: "22",  proto: tcp, from_ip: "10.0.0.5" }
  - { port: "443", proto: tcp, from_ip: "any" }
```

4. Write the firewall playbook:

```yaml
# firewall.yml
---
- name: Apply firewall policy to AI server fleet
  hosts: ai_servers
  become: true
  tasks:

    - name: Install ufw
      ansible.builtin.package:
        name: ufw
        state: present

    - name: Reset UFW to a clean state
      community.general.ufw:
        state: reset
      changed_when: false   # reset always reports changed; suppress noise

    - name: Set default incoming policy
      community.general.ufw:
        state: enabled
        policy: "{{ firewall_default_incoming }}"
        direction: incoming

    - name: Set default outgoing policy to allow
      community.general.ufw:
        state: enabled
        policy: allow
        direction: outgoing

    - name: Apply port-specific rules
      community.general.ufw:
        rule: allow
        direction: in
        port: "{{ item.port }}"
        proto: "{{ item.proto }}"
        from_ip: "{{ item.from_ip }}"
        comment: "Managed by Ansible — {{ inventory_hostname }}"
      loop: "{{ firewall_open_ports }}"
```

5. Run in check mode first to preview changes:

```bash
ansible-playbook -i inventory/ firewall.yml --check --diff
```

Expected output (excerpt for one prod host):
```
TASK [Set default incoming policy] ***************************
--- before
+++ after
@@ -1,3 +1,3 @@
-default incoming policy: allow
+default incoming policy: deny

TASK [Apply port-specific rules] *****************************
ok: [ai-prod-01] => (item={'port': '22', 'proto': 'tcp', 'from_ip': '10.0.0.5'})
ok: [ai-prod-01] => (item={'port': '443', 'proto': 'tcp', 'from_ip': 'any'})
```

6. Apply the changes:

```bash
ansible-playbook -i inventory/ firewall.yml
```

Expected result: All seven prod hosts have UFW enabled with `deny` incoming, permitting only port 22 from the bastion and port 443 from anywhere. All three dev hosts have `allow` incoming with five open ports.

---

### Example 2: SSH Hardening with `lineinfile` and Handler-Controlled Reload

This example applies SSH daemon hardening across the entire `ai_servers` group. The use of `validate:` means a bad entry in the loop list will abort the task without touching the live `sshd_config`.

1. Add an SSH hardening play to `firewall.yml` (or create `ssh-hardening.yml`):

```yaml
# ssh-hardening.yml
---
- name: Harden SSH daemon across AI fleet
  hosts: ai_servers
  become: true
  handlers:
    - name: Restart sshd
      ansible.builtin.service:
        name: sshd
        state: restarted

  tasks:
    - name: Apply sshd_config directives
      ansible.builtin.lineinfile:
        path: /etc/ssh/sshd_config
        regexp: "{{ item.regexp }}"
        line: "{{ item.line }}"
        state: present
        validate: "sshd -t -f %s"
        backup: true
      loop:
        - { regexp: '^#?PermitRootLogin',        line: 'PermitRootLogin no' }
        - { regexp: '^#?PasswordAuthentication', line: 'PasswordAuthentication no' }
        - { regexp: '^#?PubkeyAuthentication',   line: 'PubkeyAuthentication yes' }
        - { regexp: '^#?X11Forwarding',          line: 'X11Forwarding no' }
        - { regexp: '^#?MaxAuthTries',           line: 'MaxAuthTries 3' }
        - { regexp: '^#?LoginGraceTime',         line: 'LoginGraceTime 30' }
        - { regexp: '^#?AllowUsers',             line: 'AllowUsers deploy ansible' }
        - { regexp: '^#?ClientAliveInterval',    line: 'ClientAliveInterval 300' }
        - { regexp: '^#?ClientAliveCountMax',    line: 'ClientAliveCountMax 2' }
      notify: Restart sshd
```

2. Run with `--diff` to confirm each line change:

```bash
ansible-playbook -i inventory/ ssh-hardening.yml --diff
```

Expected output (for any host where `PermitRootLogin` was previously commented or set to `yes`):
```
TASK [Apply sshd_config directives] **************************
--- /etc/ssh/sshd_config   (before)
+++ /etc/ssh/sshd_config   (after)
@@ -32,1 +32,1 @@
-#PermitRootLogin prohibit-password
+PermitRootLogin no
```

3. Verify the change on one host:

```bash
ansible ai-prod-01 -i inventory/ -m ansible.builtin.shell \
  -a "sshd -T | grep -E 'permitrootlogin|passwordauthentication|maxauthtries'" \
  --become
```

Expected output:
```
ai-prod-01 | CHANGED | rc=0 >>
permitrootlogin no
passwordauthentication no
maxauthtries 3
```

---

### Example 3: Deploying `dnsmasq` as Internal DNS and Updating `/etc/hosts`

This example deploys dnsmasq to a dedicated DNS server (`dns-server` host) and then pushes an updated `/etc/hosts` to every AI server so they resolve fleet hostnames locally while forwarding unknown queries to dnsmasq.

1. Add the DNS server to inventory:

```ini
# inventory/hosts.ini (add to top)
[dns_servers]
dns-01 ansible_host=10.0.0.53
```

2. Create the dnsmasq configuration template:

```jinja2
{# templates/dnsmasq.conf.j2 #}
domain=internal
local=/internal/
expand-hosts
no-resolv
no-poll

server=8.8.8.8
server=1.1.1.1

{% for host in groups['ai_servers'] %}
address=/{{ host }}.internal/{{ hostvars[host]['ansible_host'] }}
{% endfor %}

address=/model-api.internal/10.0.0.10
address=/vector-db.internal/10.0.0.11

listen-address=127.0.0.1,{{ ansible_default_ipv4.address }}
bind-interfaces
cache-size=1000
```

3. Create the `/etc/hosts` template:

```jinja2
{# templates/hosts.j2 #}
127.0.0.1   localhost
127.0.1.1   {{ inventory_hostname }}

# AI fleet — managed by Ansible {{ ansible_date_time.date }}
{% for host in groups['ai_servers'] %}
{{ hostvars[host]['ansible_host'] }}  {{ host }}.internal  {{ host }}
{% endfor %}

# Shared internal services
10.0.0.10   model-api.internal   model-api
10.0.0.11   vector-db.internal   vector-db
10.0.0.53   dns-01.internal      dns-01
```

4. Write the DNS playbook:

```yaml
# dns.yml
---
- name: Deploy dnsmasq to DNS server
  hosts: dns_servers
  become: true
  handlers:
    - name: Restart dnsmasq
      ansible.builtin.service:
        name: dnsmasq
        state: restarted

  tasks:
    - name: Install dnsmasq
      ansible.builtin.package:
        name: dnsmasq
        state: present

    - name: Deploy dnsmasq configuration
      ansible.builtin.template:
        src: templates/dnsmasq.conf.j2
        dest: /etc/dnsmasq.conf
        owner: root
        group: root
        mode: "0644"
        validate: "dnsmasq --test --conf-file=%s"
        backup: true
      notify: Restart dnsmasq

    - name: Enable and start dnsmasq
      ansible.builtin.service:
        name: dnsmasq
        state: started
        enabled: true

- name: Update /etc/hosts on all AI servers
  hosts: ai_servers
  become: true
  tasks:
    - name: Deploy /etc/hosts from template
      ansible.builtin.template:
        src: templates/hosts.j2
        dest: /etc/hosts
        owner: root
        group: root
        mode: "0644"
        backup: true
```

5. Run the playbook:

```bash
ansible-playbook -i inventory/ dns.yml
```

6. Verify name resolution from any AI server:

```bash
ansible ai-prod-01 -i inventory/ -m ansible.builtin.shell \
  -a "getent hosts model-api.internal"
```

Expected output:
```
ai-prod-01 | CHANGED | rc=0 >>
10.0.0.10       model-api.internal model-api
```

## Common Pitfalls

### Pitfall 1: Cutting Your Own SSH Session by Applying DROP Before Allowing Established Traffic

**Description:** Applying a default DROP policy on the INPUT chain before inserting an ACCEPT rule for ESTABLISHED/RELATED connections drops the return packets for the current SSH session, immediately terminating the Ansible connection.

**Why it happens:** TCP connections consist of a bidirectional packet flow. Once your SSH connection is open, the server sends ACKs and data packets back to your control node. If those return packets match the default DROP rule before they match an ALLOW rule, they are silently discarded.

**Incorrect pattern:**
```yaml
- name: Set default DROP  # WRONG — done before allowing established
  ansible.builtin.iptables:
    chain: INPUT
    policy: DROP

- name: Allow established connections  # Too late — SSH is already dead
  ansible.builtin.iptables:
    chain: INPUT
    ctstate: [ESTABLISHED, RELATED]
    jump: ACCEPT
```

**Correct pattern:**
```yaml
- name: Allow established connections FIRST
  ansible.builtin.iptables:
    chain: INPUT
    ctstate: [ESTABLISHED, RELATED]
    jump: ACCEPT

- name: Now set default DROP
  ansible.builtin.iptables:
    chain: INPUT
    policy: DROP
```

---

### Pitfall 2: Forgetting `state: reset` Causes UFW Rule Accumulation

**Description:** Running the UFW play repeatedly without resetting first appends new rules to any already-existing rules, producing duplicates and unexpected matches.

**Why it happens:** UFW does not deduplicate rules that differ in any parameter. If you change a `from_ip` between runs, both the old and new rules remain active.

**Incorrect pattern:**
```yaml
- name: Apply rule (accumulates on every run)
  community.general.ufw:
    rule: allow
    port: "443"
    proto: tcp
    from_ip: "10.0.1.0/24"
```

**Correct pattern:**
```yaml
- name: Reset UFW rule set before re-applying
  community.general.ufw:
    state: reset

- name: Apply clean rule set
  community.general.ufw:
    rule: allow
    port: "443"
    proto: tcp
    from_ip: "10.0.1.0/24"
```

---

### Pitfall 3: Missing `validate:` on `sshd_config` Modifications

**Description:** A typo in a `lineinfile` directive (e.g., `AllowUsers depoy` instead of `deploy`) is written to `sshd_config` without validation. After the handler restarts sshd, the daemon refuses to start — locking all users out of the server permanently (until console access is used).

**Why it happens:** Without `validate:`, Ansible writes the file and notifies the handler regardless of content validity.

**Incorrect pattern:**
```yaml
- name: Restrict AllowUsers
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#?AllowUsers'
    line: 'AllowUsers depoy'   # typo — no validate to catch it
  notify: Restart sshd
```

**Correct pattern:**
```yaml
- name: Restrict AllowUsers
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^#?AllowUsers'
    line: 'AllowUsers deploy ansible'
    validate: "sshd -t -f %s"   # catches errors before file is written
  notify: Restart sshd
```

---

### Pitfall 4: Using `ansible.builtin.iptables` Without Persisting Rules

**Description:** Rules added with the `iptables` module exist only in kernel memory. After a host reboot, all rules vanish and the host reverts to an unprotected state.

**Why it happens:** `iptables` is stateless at the kernel level. Persistence requires either `iptables-save`/`iptables-restore` via an init script or a tool like `iptables-persistent`.

**Incorrect pattern:**
```yaml
- name: Block port 23
  ansible.builtin.iptables:
    chain: INPUT
    protocol: tcp
    destination_port: "23"
    jump: DROP
# Rules are lost on reboot
```

**Correct pattern:**
```yaml
- name: Block port 23
  ansible.builtin.iptables:
    chain: INPUT
    protocol: tcp
    destination_port: "23"
    jump: DROP

- name: Install iptables-persistent
  ansible.builtin.package:
    name: iptables-persistent
    state: present

- name: Save iptables rules
  ansible.builtin.shell: iptables-save > /etc/iptables/rules.v4
  changed_when: true
```

---

### Pitfall 5: `/etc/hosts` Template Omitting `127.0.1.1` for the Hostname

**Description:** A rendered `/etc/hosts` that lacks the `127.0.1.1  <hostname>` line causes `sudo` to print the warning `sudo: unable to resolve host <hostname>` on every command, and some applications that rely on `hostname -f` returning a fully qualified name will fail.

**Why it happens:** The template author copies a minimal `/etc/hosts` without realising that Debian/Ubuntu expects `127.0.1.1` to map to the local hostname.

**Incorrect pattern:**
```jinja2
127.0.0.1   localhost
# Missing 127.0.1.1 entry
```

**Correct pattern:**
```jinja2
127.0.0.1   localhost
127.0.1.1   {{ inventory_hostname }}.internal  {{ inventory_hostname }}
```

---

### Pitfall 6: Including the Control Node's IP in `fail2ban` Without Adding It to `ignoreip`

**Description:** If an Ansible playbook fails and retries tasks rapidly, `fail2ban` may see repeated authentication attempts from the control node and ban it. This makes the entire fleet unreachable until the ban expires or is manually lifted.

**Why it happens:** From fail2ban's perspective, many rapid SSH connections from one IP — even successful ones — can trigger the threshold.

**Incorrect pattern:**
```yaml
# group_vars/all.yml
fail2ban_ignoreip:
  - "127.0.0.1/8"  # Only loopback — control node can be banned
```

**Correct pattern:**
```yaml
# group_vars/all.yml
fail2ban_ignoreip:
  - "127.0.0.1/8"
  - "::1"
  - "10.0.0.0/8"       # management subnet including control node
  - "192.168.100.50"    # explicit control node IP as a belt-and-suspenders safeguard
```

---

### Pitfall 7: Using `regexp` in `lineinfile` That Matches Multiple Lines

**Description:** A too-broad `regexp` pattern matches more than one line in `sshd_config`, causing Ansible to replace the last match rather than the intended directive, leaving the other matched lines unchanged and potentially conflicting.

**Why it happens:** `lineinfile` replaces only the last matching line by default. If your `regexp` matches `MaxAuthTries` and `MaxSessions` (because the pattern is `'^Max'`), only the last match is replaced.

**Incorrect pattern:**
```yaml
- regexp: '^Max'       # matches MaxAuthTries AND MaxSessions
  line: 'MaxAuthTries 3'
```

**Correct pattern:**
```yaml
- regexp: '^#?MaxAuthTries\b'    # \b word boundary anchors the match
  line: 'MaxAuthTries 3'
```

## Summary

- The `community.general.ufw` module manages UFW firewall rules declaratively; using `state: reset` before applying a full rule set prevents rule accumulation across repeated playbook runs, and the `comment:` parameter makes auditing fast.
- The `ansible.builtin.iptables` module provides granular packet-filter control for non-UFW systems, but requires an explicit persistence step (`iptables-save`) to survive reboots.
- Ansible's `group_vars/` system is the correct mechanism for applying different firewall profiles to `dev` and `prod` inventory groups — a single parameterised playbook reads whichever variable file matches the target group, eliminating environment-specific conditionals in task files.
- The `lineinfile` module with `validate: "sshd -t -f %s"` is the safest way to modify `sshd_config` because it runs a syntax check against a temp file before overwriting the live configuration, preventing the SSH daemon from being left in an unbootable state.
- Always protect your Ansible control node and management subnets in `fail2ban_ignoreip` — failure to do so risks banning the control node itself during rapid retry loops, making the entire fleet unreachable.

## Further Reading

- [Ansible `community.general.ufw` module documentation](https://docs.ansible.com/ansible/latest/collections/community/general/ufw_module.html) — the authoritative reference for every UFW module parameter, return value, and worked example; check here first when a parameter behaves unexpectedly.
- [Ansible `ansible.builtin.iptables` module documentation](https://docs.ansible.com/ansible/latest/collections/ansible/builtin/iptables_module.html) — covers all parameters including `ctstate`, `ip_version`, and the distinction between rule insertion and append; essential reading before managing iptables at scale.
- [Ansible `community.general.nmcli` module documentation](https://docs.ansible.com/ansible/latest/collections/community/general/nmcli_module.html) — full parameter reference for managing NetworkManager connection profiles, including bond, VLAN, and bridge types relevant to AI cluster network topologies.
- [UFW community guide (Ubuntu documentation)](https://help.ubuntu.com/community/UFW) — explains the UFW rule database, application profiles, logging levels, and `ufw status verbose` output in plain language; a good complement to the Ansible module docs.
- [fail2ban documentation — Jails configuration](https://fail2ban.readthedocs.io/en/latest/filters.html) — covers filter expressions, action scripts, and the jail configuration format used in the `jail.local.j2` template in this module.
- [dnsmasq man page](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html) — the canonical reference for every dnsmasq configuration directive including `address=`, `local=`, `server=`, and `bind-interfaces`; use this to extend the template beyond what is shown in this module.
- [SSH hardening guide — Mozilla InfoSec](https://infosec.mozilla.org/guidelines/openssh) — a widely adopted, regularly updated set of recommended `sshd_config` values with explanations of the security rationale behind each directive; useful for validating the choices made in the `lineinfile` loop in this module.
- [Ansible Best Practices — content organisation](https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html) — covers the `group_vars/` and `host_vars/` directory layout, variable precedence, and the recommended project structure for multi-environment inventories like the dev/prod split used throughout this module.
