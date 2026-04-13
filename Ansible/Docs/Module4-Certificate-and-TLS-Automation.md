# Module 4: Certificate & TLS Automation
> Subject: Ansible | Difficulty: Intermediate | Estimated Time: 300 minutes

## Objective

After completing this module, you will be able to automate the full TLS certificate lifecycle for a fleet of AI API servers using Ansible. You will use the `community.crypto` collection to generate private keys with `openssl_privatekey`, create certificate signing requests with `openssl_csr`, sign certificates with a private CA using `x509_certificate`, and issue public-facing certificates via Let's Encrypt using the `acme_certificate` module. You will write playbooks that distribute a private CA certificate to every server in your fleet and run `update-ca-certificates` idempotently, deploy signed server certificates to Nginx using the `nginxinc.nginx` role, enforce secure file permissions (`0640`, ownership `root:ssl-cert`) for all credential files, configure mutual TLS (mTLS) between internal AI microservices using client certificates, and trigger service-reload handlers only when certificates change. By the end of this module you can eliminate manual certificate steps from your AI infrastructure entirely.

## Prerequisites

- Completed Module 1: Ansible Fundamentals — comfortable writing playbooks, understanding inventory, variables, and the `ansible-playbook` command
- Completed Module 2: Roles and Galaxy — able to install and invoke roles from Ansible Galaxy, understand role directory structure
- Completed Module 3: Secrets Management — familiar with Ansible Vault for encrypting sensitive files such as CA private keys
- The `community.crypto` collection installed (`ansible-galaxy collection install community.crypto`)
- The `community.general` collection installed (provides `ini_file`, `capabilities`, and supporting utilities)
- Ansible 2.15 or later (verify with `ansible --version`; current stable release is Ansible 2.17)
- OpenSSL 3.x available on the control node and managed hosts
- Python `cryptography` library version 3.3 or later installed on **all managed hosts** (`pip install cryptography`)
- A working inventory of AI API servers with SSH access and `become: true` capability

## Key Concepts

### The community.crypto Collection and Module Naming

Ansible's TLS automation lives in the `community.crypto` collection. The collection went through a significant naming transition: the original `openssl_*` module names (e.g., `openssl_privatekey`, `openssl_csr`, `openssl_certificate`) are **aliases** that still work but point to the canonical modules `community.crypto.openssl_privatekey`, `community.crypto.openssl_csr`, and `community.crypto.x509_certificate`. In new playbooks you should always use the fully-qualified collection name (FQCN) to make the source unambiguous and to future-proof your code.

The core certificate-pipeline modules are:

| FQCN | Purpose |
|---|---|
| `community.crypto.openssl_privatekey` | Generate or manage an RSA/EC private key on disk |
| `community.crypto.openssl_csr` | Generate a Certificate Signing Request (CSR) from a private key |
| `community.crypto.x509_certificate` | Issue or sign a certificate from a CSR (self-signed, ownca, or ACME) |
| `community.crypto.openssl_certificate_info` | Inspect an existing certificate and return structured facts |
| `community.crypto.acme_account` | Register or manage an ACME account (Let's Encrypt) |
| `community.crypto.acme_certificate` | Obtain a certificate through ACME challenge/response |
| `community.crypto.certificate_complete_chain` | Verify a certificate chain is complete |
| `community.crypto.openssl_pkcs12` | Bundle key + cert + chain into a PKCS#12 archive |

All modules require the Python `cryptography` package on the host where the module runs. For modules that run on managed hosts (`openssl_privatekey`, `openssl_csr`, `x509_certificate`) install `cryptography` via your OS package manager or pip during a bootstrap play.

### Generating Private Keys and CSRs

The first step in issuing any certificate is creating a private key and then a CSR that describes the entity being certified. Ansible automates both steps idempotently — if the key file already exists and matches the requested parameters, no change is made.

**Generating an EC private key** (preferred for AI service endpoints due to smaller key size and faster TLS handshakes):

```yaml
- name: Generate server private key (EC P-256)
  community.crypto.openssl_privatekey:
    path: /etc/ssl/private/ai-api.key
    type: ECC
    curve: secp256r1
    mode: "0640"
    owner: root
    group: ssl-cert
  become: true
```

**Generating a CSR with Subject Alternative Names:**

```yaml
- name: Generate CSR for ai-api server
  community.crypto.openssl_csr:
    path: /etc/ssl/certs/ai-api.csr
    privatekey_path: /etc/ssl/private/ai-api.key
    common_name: "{{ inventory_hostname }}"
    organization_name: "Acme AI Platform"
    email_address: "pki@example.com"
    subject_alt_name:
      - "DNS:{{ inventory_hostname }}"
      - "DNS:{{ inventory_hostname_short }}"
      - "IP:{{ ansible_default_ipv4.address }}"
    key_usage:
      - digitalSignature
      - keyEncipherment
    extended_key_usage:
      - serverAuth
    mode: "0644"
    owner: root
    group: root
  become: true
```

The `subject_alt_name` list is critical for modern TLS clients. Browsers and the Go/Python HTTP clients used by AI services all reject certificates that lack a SAN matching the hostname or IP being connected to — the `common_name` field alone is no longer sufficient.

### Running a Private CA with x509_certificate

For internal AI services that communicate on a private network, a private Certificate Authority avoids the DNS and internet-connectivity requirements of Let's Encrypt. You maintain the CA key and certificate on your Ansible control node (protected by Ansible Vault), then sign server CSRs using the `ownca` provider of `x509_certificate`.

**CA structure on the control node:**

```
pki/
├── ca.key          # CA private key — encrypted with Ansible Vault
├── ca.crt          # CA certificate — distributed to all servers
└── issued/         # Signed server certificates (one per host)
```

**Signing a server certificate from a CSR using the private CA:**

```yaml
# Runs on the control node (delegate_to: localhost)
- name: Sign server certificate with private CA
  community.crypto.x509_certificate:
    path: "{{ playbook_dir }}/pki/issued/{{ inventory_hostname }}.crt"
    csr_path: "/tmp/{{ inventory_hostname }}.csr"   # fetched from managed host
    provider: ownca
    ownca_path: "{{ playbook_dir }}/pki/ca.crt"
    ownca_privatekey_path: "{{ playbook_dir }}/pki/ca.key"
    ownca_privatekey_passphrase: "{{ vault_ca_key_passphrase }}"
    ownca_not_after: "+365d"
    ownca_not_before: "-1d"
    mode: "0644"
  delegate_to: localhost
  become: false
```

The typical CA signing workflow in a playbook is:
1. Generate key and CSR on each managed host
2. Fetch CSRs to the control node with the `fetch` module
3. Sign each CSR on the control node with `delegate_to: localhost`
4. Copy signed certificates back to each managed host with the `copy` module

### Distributing a Private CA Certificate (update-ca-certificates)

For AI services to trust certificates signed by your private CA, every server in the fleet must have the CA certificate installed in the system trust store. On Debian/Ubuntu systems this means placing the CA cert in `/usr/local/share/ca-certificates/` and running `update-ca-certificates`. On RHEL/CentOS/Rocky systems it means placing the cert in `/etc/pki/ca-trust/source/anchors/` and running `update-ca-trust`.

```yaml
- name: Distribute private CA certificate to all servers
  hosts: ai_servers
  become: true
  tasks:
    - name: Copy CA certificate to trust store directory (Debian/Ubuntu)
      ansible.builtin.copy:
        src: "{{ playbook_dir }}/pki/ca.crt"
        dest: /usr/local/share/ca-certificates/acme-ai-ca.crt
        owner: root
        group: root
        mode: "0644"
      when: ansible_os_family == "Debian"
      notify: Update CA certificates

    - name: Copy CA certificate to trust store directory (RHEL/Rocky)
      ansible.builtin.copy:
        src: "{{ playbook_dir }}/pki/ca.crt"
        dest: /etc/pki/ca-trust/source/anchors/acme-ai-ca.crt
        owner: root
        group: root
        mode: "0644"
      when: ansible_os_family == "RedHat"
      notify: Update CA trust (RHEL)

  handlers:
    - name: Update CA certificates
      ansible.builtin.command: update-ca-certificates
      changed_when: true

    - name: Update CA trust (RHEL)
      ansible.builtin.command: update-ca-trust extract
      changed_when: true
```

Using `notify` and handlers ensures `update-ca-certificates` only runs when the CA cert file actually changed — not on every playbook execution. This matters in large fleets where unnecessary command invocations slow runs and create false change records in your audit log.

### Let's Encrypt Automation with acme_certificate

For AI API endpoints that are publicly accessible (customer-facing APIs, model serving endpoints with public DNS), Let's Encrypt provides free, trusted, automatically renewable certificates. The `community.crypto.acme_certificate` module implements the ACME protocol directly from Ansible without requiring certbot.

The ACME flow has two passes:
1. **Pass 1:** Request the challenge data from Let's Encrypt
2. **Publish the challenge** to your web server or DNS provider
3. **Pass 2:** Ask Let's Encrypt to validate and issue the certificate

```yaml
- name: Obtain Let's Encrypt certificate via HTTP-01 challenge
  hosts: public_ai_endpoints
  become: true
  vars:
    acme_directory: "https://acme-v02.api.letsencrypt.org/directory"
    acme_email: "pki@example.com"
    domain: "{{ inventory_hostname }}"
    cert_dir: "/etc/ssl/acme/{{ domain }}"
    webroot: "/var/www/html"

  tasks:
    - name: Create certificate directory
      ansible.builtin.file:
        path: "{{ cert_dir }}"
        state: directory
        owner: root
        group: ssl-cert
        mode: "0750"

    - name: Generate private key for ACME certificate
      community.crypto.openssl_privatekey:
        path: "{{ cert_dir }}/privkey.pem"
        type: ECC
        curve: secp256r1
        owner: root
        group: ssl-cert
        mode: "0640"

    - name: Generate CSR for ACME certificate
      community.crypto.openssl_csr:
        path: "{{ cert_dir }}/csr.pem"
        privatekey_path: "{{ cert_dir }}/privkey.pem"
        common_name: "{{ domain }}"
        subject_alt_name: "DNS:{{ domain }}"

    - name: ACME pass 1 — request challenge
      community.crypto.acme_certificate:
        account_key_src: "{{ playbook_dir }}/pki/acme-account.key"
        account_email: "{{ acme_email }}"
        acme_directory: "{{ acme_directory }}"
        acme_version: 2
        terms_are_agreed: true
        challenge: http-01
        csr: "{{ cert_dir }}/csr.pem"
        dest: "{{ cert_dir }}/fullchain.pem"
        chain_dest: "{{ cert_dir }}/chain.pem"
        remaining_days: 30
      register: acme_challenge

    - name: Create .well-known/acme-challenge directory
      ansible.builtin.file:
        path: "{{ webroot }}/.well-known/acme-challenge"
        state: directory
        owner: root
        group: www-data
        mode: "0755"
      when: acme_challenge is changed

    - name: Write HTTP-01 challenge token to webroot
      ansible.builtin.copy:
        dest: "{{ webroot }}/.well-known/acme-challenge/{{ acme_challenge['challenge_data'][domain]['http-01']['token'] }}"
        content: "{{ acme_challenge['challenge_data'][domain]['http-01']['resource_value'] }}"
        owner: root
        group: www-data
        mode: "0644"
      when: acme_challenge is changed

    - name: ACME pass 2 — validate and retrieve certificate
      community.crypto.acme_certificate:
        account_key_src: "{{ playbook_dir }}/pki/acme-account.key"
        account_email: "{{ acme_email }}"
        acme_directory: "{{ acme_directory }}"
        acme_version: 2
        terms_are_agreed: true
        challenge: http-01
        csr: "{{ cert_dir }}/csr.pem"
        dest: "{{ cert_dir }}/fullchain.pem"
        chain_dest: "{{ cert_dir }}/chain.pem"
        remaining_days: 30
        data: "{{ acme_challenge }}"
      when: acme_challenge is changed
      notify: Reload Nginx

    - name: Clean up challenge token
      ansible.builtin.file:
        path: "{{ webroot }}/.well-known/acme-challenge/{{ acme_challenge['challenge_data'][domain]['http-01']['token'] }}"
        state: absent
      when: acme_challenge is changed

  handlers:
    - name: Reload Nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

The `remaining_days: 30` parameter is how you implement renewal: run this playbook on a schedule (cron, AWX schedule, or CI pipeline). If the existing certificate has more than 30 days left, `acme_certificate` makes no changes and the handler never fires. If it is within 30 days of expiry, a new certificate is obtained and Nginx is reloaded — all without human intervention.

### Deploying Certificates to Nginx and Managing Permissions

Once certificates are on disk, Nginx must be pointed at them and must be able to read the private key. The security requirement is that private key files must never be world-readable. The conventional setup on Linux is:

- Private keys: `mode: 0640`, `owner: root`, `group: ssl-cert`
- Certificates and chains: `mode: 0644`, `owner: root`, `group: root`
- The `nginx` or `www-data` user must be a member of the `ssl-cert` group

```yaml
- name: Add nginx user to ssl-cert group
  ansible.builtin.user:
    name: "{{ nginx_user }}"   # typically 'nginx' on RHEL, 'www-data' on Debian
    groups: ssl-cert
    append: true
  become: true
  notify: Restart Nginx
```

A reusable task file for deploying a certificate bundle to Nginx:

```yaml
# tasks/deploy_cert.yml
- name: Ensure ssl-cert group exists
  ansible.builtin.group:
    name: ssl-cert
    system: true
  become: true

- name: Deploy server private key
  ansible.builtin.copy:
    src: "{{ cert_src_dir }}/{{ inventory_hostname }}.key"
    dest: "/etc/ssl/private/{{ cert_name }}.key"
    owner: root
    group: ssl-cert
    mode: "0640"
  become: true
  notify: Reload Nginx

- name: Deploy server certificate
  ansible.builtin.copy:
    src: "{{ cert_src_dir }}/{{ inventory_hostname }}.crt"
    dest: "/etc/ssl/certs/{{ cert_name }}.crt"
    owner: root
    group: root
    mode: "0644"
  become: true
  notify: Reload Nginx

- name: Deploy CA chain certificate
  ansible.builtin.copy:
    src: "{{ playbook_dir }}/pki/ca.crt"
    dest: "/etc/ssl/certs/acme-ai-ca.crt"
    owner: root
    group: root
    mode: "0644"
  become: true
```

A minimal Nginx server block that references the deployed files:

```nginx
# /etc/nginx/conf.d/ai-api.conf
server {
    listen 443 ssl;
    server_name {{ inventory_hostname }};

    ssl_certificate     /etc/ssl/certs/ai-api.crt;
    ssl_certificate_key /etc/ssl/private/ai-api.key;
    ssl_trusted_certificate /etc/ssl/certs/acme-ai-ca.crt;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Deploy this template with `ansible.builtin.template` so that `{{ inventory_hostname }}` is resolved per host, then notify the `Reload Nginx` handler.

### Certificate Expiry Monitoring

Issuing certificates is only half the problem. You must also detect certificates that are approaching expiry before they expire, because an expired certificate on an AI inference endpoint causes client-side failures that are difficult to distinguish from application bugs.

Use `community.crypto.openssl_certificate_info` to read certificate metadata and register facts:

```yaml
- name: Check certificate expiry on all AI servers
  hosts: ai_servers
  become: true
  tasks:
    - name: Read certificate info
      community.crypto.openssl_certificate_info:
        path: /etc/ssl/certs/ai-api.crt
        valid_at:
          point_30d: "+30d"
          point_7d: "+7d"
      register: cert_info

    - name: Warn if certificate expires within 30 days
      ansible.builtin.debug:
        msg: >
          WARNING: Certificate on {{ inventory_hostname }} expires
          {{ cert_info.not_after }} — less than 30 days remaining.
      when: not cert_info.valid_at.point_30d

    - name: Fail playbook if certificate expires within 7 days
      ansible.builtin.fail:
        msg: >
          CRITICAL: Certificate on {{ inventory_hostname }} expires
          {{ cert_info.not_after }}. Immediate renewal required.
      when: not cert_info.valid_at.point_7d
```

Run this playbook as a separate monitoring job (daily via cron or AWX) that is distinct from your certificate-issuance playbook. This gives you an early-warning system with enough lead time to investigate and remediate any renewal failures before they cause an outage.

### Mutual TLS (mTLS) Between AI Microservices

Internal AI infrastructure often has multiple services that call each other — an API gateway, a model inference server, a vector database, and an embedding service. Standard one-way TLS authenticates the server to the client, but it does not stop a compromised host inside your network from sending requests. Mutual TLS (mTLS) requires the client to present its own certificate signed by your private CA, so both sides are authenticated cryptographically.

The Ansible workflow for mTLS adds client certificate issuance on top of the server certificate workflow:

```yaml
# Generate client certificate for the AI gateway service
- name: Generate client private key for ai-gateway
  community.crypto.openssl_privatekey:
    path: /etc/ssl/private/ai-gateway-client.key
    type: ECC
    curve: secp256r1
    owner: root
    group: ssl-cert
    mode: "0640"
  become: true

- name: Generate client CSR for ai-gateway
  community.crypto.openssl_csr:
    path: /etc/ssl/certs/ai-gateway-client.csr
    privatekey_path: /etc/ssl/private/ai-gateway-client.key
    common_name: "ai-gateway"
    organization_name: "Acme AI Platform"
    extended_key_usage:
      - clientAuth          # critical: marks this as a client certificate
    key_usage:
      - digitalSignature
  become: true
```

On the server side (e.g., the inference server's Nginx), enable client certificate verification:

```nginx
# mTLS configuration in Nginx
ssl_client_certificate /etc/ssl/certs/acme-ai-ca.crt;
ssl_verify_client on;
ssl_verify_depth 2;
```

With `ssl_verify_client on`, Nginx rejects any connection that does not present a valid client certificate signed by your private CA. This means even if an attacker reaches the inference server's network port, they cannot send requests without a CA-signed client certificate.

## Best Practices

1. **Always use fully-qualified collection names (FQCNs) for all `community.crypto` modules.** Using bare names like `openssl_certificate` risks collisions if another collection installs a module with the same short name and makes playbooks harder to audit for collection dependencies.

2. **Encrypt CA private keys with Ansible Vault before committing them to version control.** The CA key is the root of trust for your entire fleet — if it leaks, every certificate it issued is compromised. Use `ansible-vault encrypt_string` or encrypt the key file directly with `ansible-vault encrypt`.

3. **Generate private keys on the target host, not the control node, then never copy them off the host.** Moving private keys over SSH introduces exposure windows. Use `delegate_to: localhost` only for signing operations on the control node's CA key, not for distributing server private keys.

4. **Set `remaining_days` on every `acme_certificate` and `x509_certificate` task to implement renewal by default.** Without this parameter the module issues a new certificate every run, wasting API calls and causing unnecessary Nginx reloads across your fleet.

5. **Always notify a handler to reload (not restart) the service after deploying a certificate.** A reload (`nginx -s reload`) completes gracefully without dropping active connections, whereas a restart terminates them — unacceptable for an inference server handling long-running generation requests.

6. **Use the `ssl-cert` group and `0640` permissions for all private key files.** World-readable private keys allow any local process to impersonate your service. The `ssl-cert` group is the Linux standard for this purpose; add only the service user (nginx, gunicorn, etc.) to that group.

7. **Separate your CA-issuance playbook from your certificate-deployment playbook.** The CA operations require Vault credentials and run on the control node; the deployment operations run on managed hosts. Keeping them separate makes each playbook simpler to test, audit, and schedule independently.

8. **Run a dedicated expiry-monitoring playbook daily and alert on failures.** Automated renewal playbooks can silently fail due to DNS changes, rate limits, or Vault connectivity issues. A daily monitoring check provides a safety net independent of the renewal mechanism.

9. **Pin the `community.crypto` collection version in `requirements.yml`.** The collection evolves quickly; pinning (e.g., `version: ">=2.15.0,<3.0.0"`) prevents a Galaxy update from silently changing module parameter behavior in production pipelines.

10. **Use ECC (P-256 or P-384) keys rather than RSA-2048 for new deployments.** EC keys provide equivalent security with smaller size, faster TLS handshakes, and lower CPU overhead — meaningful at AI inference scale where the TLS handshake cost is amortized over fewer long-lived connections than a traditional web server.

## Use Cases

### Use Case 1: Zero-Touch Internal PKI for a Private AI Cluster

**Problem:** A team running a private LLM inference cluster needs TLS on all internal API calls, but the servers have no public internet access and cannot use Let's Encrypt. Managing certificates by hand across 20 GPU servers is error-prone and certificates regularly expire without notice.

**Concepts applied:** `openssl_privatekey` and `openssl_csr` to generate per-host keys and CSRs, `x509_certificate` with the `ownca` provider to sign from a private CA, CA distribution via `update-ca-certificates`, expiry monitoring with `openssl_certificate_info`, and `remaining_days` for automatic renewal scheduling.

**Expected outcome:** Every server in the cluster has a unique, CA-signed server certificate. The CA cert is trusted system-wide. A scheduled playbook renews certificates 30 days before expiry and reloads affected services with zero human intervention.

### Use Case 2: Let's Encrypt Certificates for a Public Model API

**Problem:** A team exposing a fine-tuned model via a public HTTPS API needs publicly trusted certificates that auto-renew. Certbot installed directly on hosts creates a management burden across a horizontally-scaled fleet and its renewal hooks are not centrally auditable.

**Concepts applied:** `acme_certificate` with the `http-01` challenge managed from Ansible, `remaining_days: 30` for idempotent renewal, handlers to reload Nginx only on certificate change, and centralized scheduling via AWX or a cron job on the control node.

**Expected outcome:** Public API endpoints have browser-trusted certificates that renew automatically whenever the scheduled playbook runs and the certificate is within 30 days of expiry, with all certificate operations logged in Ansible's change record.

### Use Case 3: mTLS Enforcement Between AI Microservices

**Problem:** An AI platform consists of a gateway, two inference servers, and a vector store. The team needs to ensure that only authorised internal services can call the inference servers — a compromised host on the same private subnet must not be able to send model requests.

**Concepts applied:** Client certificate issuance using `openssl_csr` with `extended_key_usage: clientAuth`, signing with the private CA, distributing client certs to gateway and embedding services, configuring Nginx on inference servers with `ssl_verify_client on` and `ssl_client_certificate` pointing to the CA cert.

**Expected outcome:** The inference server rejects any connection that does not present a valid CA-signed client certificate, enforcing service identity independently of network-level controls such as firewall rules.

### Use Case 4: Certificate Rotation Without Downtime on a Live Inference Fleet

**Problem:** The private CA certificate is expiring and must be replaced fleet-wide. The inference cluster serves real-time requests and cannot tolerate a restart window.

**Concepts applied:** New CA key and certificate generated on the control node, distributed to all servers via `update-ca-certificates` handler, new server certificates signed with the new CA and deployed with Ansible, Nginx reloaded (not restarted) via handler, expiry monitoring to confirm the old CA cert is gone from all trust stores.

**Expected outcome:** The CA is rotated and new server certificates are live across the entire fleet with no dropped connections, confirmed by a final monitoring playbook run showing all certificates valid for 365 days.

## Hands-on Examples

### Example 1: Build a Private CA and Issue Your First Server Certificate

This example walks through the complete private CA workflow from scratch: creating the CA, distributing it, and issuing a signed certificate for a single AI API server.

1. Install the required collection on your control node:

   ```bash
   ansible-galaxy collection install community.crypto
   ```

   Expected output:
   ```
   Starting galaxy collection install process
   Process install dependency map
   Starting collection install process
   Installing 'community.crypto:2.21.0' to '~/.ansible/collections/...'
   community.crypto:2.21.0 was installed successfully
   ```

2. Create the PKI directory on your control node and generate the CA key (this runs locally, not against managed hosts):

   ```bash
   mkdir -p ~/ansible/pki/issued
   ```

   ```yaml
   # playbooks/create-ca.yml
   ---
   - name: Create private CA on control node
     hosts: localhost
     connection: local
     gather_facts: false
     vars:
       pki_dir: "{{ playbook_dir }}/../pki"

     tasks:
       - name: Generate CA private key
         community.crypto.openssl_privatekey:
           path: "{{ pki_dir }}/ca.key"
           type: ECC
           curve: secp384r1
           mode: "0600"
           owner: "{{ ansible_user_id }}"

       - name: Generate CA self-signed certificate
         community.crypto.x509_certificate:
           path: "{{ pki_dir }}/ca.crt"
           privatekey_path: "{{ pki_dir }}/ca.key"
           provider: selfsigned
           selfsigned_not_after: "+3650d"
           selfsigned_not_before: "-1d"
           subject:
             commonName: "Acme AI Internal CA"
             organizationName: "Acme AI Platform"
           basic_constraints:
             - "CA:TRUE"
           basic_constraints_critical: true
           key_usage:
             - keyCertSign
             - cRLSign
           mode: "0644"
   ```

   Run it:

   ```bash
   ansible-playbook playbooks/create-ca.yml
   ```

   Expected output:
   ```
   PLAY [Create private CA on control node] *************************************

   TASK [Generate CA private key] ***********************************************
   changed: [localhost]

   TASK [Generate CA self-signed certificate] ***********************************
   changed: [localhost]

   PLAY RECAP *******************************************************************
   localhost                  : ok=2    changed=2    unreachable=0    failed=0
   ```

3. Distribute the CA certificate to all AI servers:

   ```yaml
   # playbooks/distribute-ca.yml
   ---
   - name: Install private CA in system trust store
     hosts: ai_servers
     become: true
     vars:
       pki_dir: "{{ playbook_dir }}/../pki"

     tasks:
       - name: Copy CA cert (Debian/Ubuntu)
         ansible.builtin.copy:
           src: "{{ pki_dir }}/ca.crt"
           dest: /usr/local/share/ca-certificates/acme-ai-ca.crt
           owner: root
           group: root
           mode: "0644"
         when: ansible_os_family == "Debian"
         notify: Update CA certificates

       - name: Copy CA cert (RHEL/Rocky)
         ansible.builtin.copy:
           src: "{{ pki_dir }}/ca.crt"
           dest: /etc/pki/ca-trust/source/anchors/acme-ai-ca.crt
           owner: root
           group: root
           mode: "0644"
         when: ansible_os_family == "RedHat"
         notify: Update CA trust

     handlers:
       - name: Update CA certificates
         ansible.builtin.command: update-ca-certificates
         changed_when: true

       - name: Update CA trust
         ansible.builtin.command: update-ca-trust extract
         changed_when: true
   ```

   ```bash
   ansible-playbook playbooks/distribute-ca.yml
   ```

   Expected output (Debian hosts):
   ```
   TASK [Copy CA cert (Debian/Ubuntu)] ******************************************
   changed: [ai-server-01]
   changed: [ai-server-02]

   RUNNING HANDLER [Update CA certificates] *************************************
   changed: [ai-server-01]
   changed: [ai-server-02]
   ```

4. Issue a server certificate for one host. This playbook runs tasks on the managed host to generate the key and CSR, fetches the CSR to the control node, signs it there, then copies the cert back:

   ```yaml
   # playbooks/issue-server-cert.yml
   ---
   - name: Issue server certificate from private CA
     hosts: ai_servers
     become: true
     vars:
       pki_dir: "{{ playbook_dir }}/../pki"

     tasks:
       - name: Ensure ssl-cert group exists
         ansible.builtin.group:
           name: ssl-cert
           system: true

       - name: Generate server private key
         community.crypto.openssl_privatekey:
           path: /etc/ssl/private/ai-api.key
           type: ECC
           curve: secp256r1
           owner: root
           group: ssl-cert
           mode: "0640"

       - name: Generate CSR
         community.crypto.openssl_csr:
           path: /tmp/{{ inventory_hostname }}.csr
           privatekey_path: /etc/ssl/private/ai-api.key
           common_name: "{{ inventory_hostname }}"
           subject_alt_name:
             - "DNS:{{ inventory_hostname }}"
             - "IP:{{ ansible_default_ipv4.address }}"
           extended_key_usage:
             - serverAuth
           key_usage:
             - digitalSignature
             - keyEncipherment

       - name: Fetch CSR to control node
         ansible.builtin.fetch:
           src: /tmp/{{ inventory_hostname }}.csr
           dest: "{{ pki_dir }}/issued/{{ inventory_hostname }}.csr"
           flat: true

       - name: Sign CSR with CA (runs on control node)
         community.crypto.x509_certificate:
           path: "{{ pki_dir }}/issued/{{ inventory_hostname }}.crt"
           csr_path: "{{ pki_dir }}/issued/{{ inventory_hostname }}.csr"
           provider: ownca
           ownca_path: "{{ pki_dir }}/ca.crt"
           ownca_privatekey_path: "{{ pki_dir }}/ca.key"
           ownca_not_after: "+365d"
           ownca_not_before: "-1d"
           mode: "0644"
         delegate_to: localhost
         become: false

       - name: Copy signed certificate to server
         ansible.builtin.copy:
           src: "{{ pki_dir }}/issued/{{ inventory_hostname }}.crt"
           dest: /etc/ssl/certs/ai-api.crt
           owner: root
           group: root
           mode: "0644"
         notify: Reload Nginx

     handlers:
       - name: Reload Nginx
         ansible.builtin.service:
           name: nginx
           state: reloaded
   ```

   Expected result: `/etc/ssl/private/ai-api.key` (mode 0640) and `/etc/ssl/certs/ai-api.crt` exist on each managed host; Nginx is reloaded on hosts where the cert file changed.

---

### Example 2: Automated Let's Encrypt Renewal Playbook

This example sets up an ACME certificate for a public-facing AI API endpoint and demonstrates the idempotent renewal pattern.

1. Create an ACME account key (one-time, stored on the control node):

   ```yaml
   # playbooks/create-acme-account.yml
   ---
   - name: Create ACME account key
     hosts: localhost
     connection: local
     gather_facts: false
     vars:
       pki_dir: "{{ playbook_dir }}/../pki"

     tasks:
       - name: Generate ACME account private key
         community.crypto.openssl_privatekey:
           path: "{{ pki_dir }}/acme-account.key"
           type: ECC
           curve: secp256r1
           mode: "0600"

       - name: Register ACME account with Let's Encrypt
         community.crypto.acme_account:
           account_key_src: "{{ pki_dir }}/acme-account.key"
           acme_directory: "https://acme-v02.api.letsencrypt.org/directory"
           acme_version: 2
           state: present
           terms_are_agreed: true
           contact:
             - "mailto:pki@example.com"
   ```

   ```bash
   ansible-playbook playbooks/create-acme-account.yml
   ```

2. Run the renewal playbook (same playbook handles both first-issue and renewal):

   ```bash
   ansible-playbook playbooks/acme-certificate.yml --limit public_ai_endpoints
   ```

   On first run (no certificate exists), expected output:
   ```
   TASK [ACME pass 1 — request challenge] ***************************************
   changed: [api.example.com]

   TASK [Write HTTP-01 challenge token to webroot] ******************************
   changed: [api.example.com]

   TASK [ACME pass 2 — validate and retrieve certificate] ***********************
   changed: [api.example.com]

   RUNNING HANDLER [Reload Nginx] ***********************************************
   changed: [api.example.com]
   ```

   On a subsequent run where the certificate still has more than 30 days remaining:
   ```
   TASK [ACME pass 1 — request challenge] ***************************************
   ok: [api.example.com]

   TASK [Write HTTP-01 challenge token to webroot] ******************************
   skipping: [api.example.com]

   TASK [ACME pass 2 — validate and retrieve certificate] ***********************
   skipping: [api.example.com]

   PLAY RECAP *******************************************************************
   api.example.com            : ok=4    changed=0    unreachable=0    failed=0
   ```

   No changes, no Nginx reload — the playbook is fully idempotent until renewal is actually due.

3. Schedule the renewal playbook to run daily via cron on your control node:

   ```bash
   # /etc/cron.d/ansible-cert-renewal
   0 3 * * * ansible /usr/bin/ansible-playbook /opt/ansible/playbooks/acme-certificate.yml >> /var/log/ansible-cert-renewal.log 2>&1
   ```

---

### Example 3: Certificate Expiry Monitoring Play

This example creates a standalone monitoring playbook that can be run on demand or scheduled daily to verify certificate health across the fleet.

```yaml
# playbooks/check-cert-expiry.yml
---
- name: Certificate expiry health check
  hosts: ai_servers
  become: true
  gather_facts: false

  vars:
    cert_path: /etc/ssl/certs/ai-api.crt
    warn_days: 30
    critical_days: 7

  tasks:
    - name: Read certificate metadata
      community.crypto.openssl_certificate_info:
        path: "{{ cert_path }}"
        valid_at:
          warn_threshold: "+{{ warn_days }}d"
          critical_threshold: "+{{ critical_days }}d"
      register: cert_info

    - name: Display certificate subject and expiry
      ansible.builtin.debug:
        msg: >
          {{ inventory_hostname }}: subject={{ cert_info.subject.commonName }},
          expires={{ cert_info.not_after }},
          serial={{ cert_info.serial_number }}

    - name: Warn on certificates expiring soon
      ansible.builtin.debug:
        msg: "WARN: {{ inventory_hostname }} cert expires in less than {{ warn_days }} days ({{ cert_info.not_after }})"
      when: not cert_info.valid_at.warn_threshold

    - name: Fail on critically short-lived certificates
      ansible.builtin.fail:
        msg: "CRITICAL: {{ inventory_hostname }} cert expires in less than {{ critical_days }} days. Run renewal playbook immediately."
      when: not cert_info.valid_at.critical_threshold
```

Run it:

```bash
ansible-playbook playbooks/check-cert-expiry.yml
```

Expected output when all certs are healthy:
```
TASK [Display certificate subject and expiry] ************************************
ok: [ai-server-01] => {
    "msg": "ai-server-01: subject=ai-server-01.internal, expires=20261015120000Z, serial=12345"
}
ok: [ai-server-02] => {
    "msg": "msg": "ai-server-02: subject=ai-server-02.internal, expires=20261015120001Z, serial=12346"
}

TASK [Warn on certificates expiring soon] ****************************************
skipping: [ai-server-01]
skipping: [ai-server-02]

TASK [Fail on critically short-lived certificates] *******************************
skipping: [ai-server-01]
skipping: [ai-server-02]

PLAY RECAP ***********************************************************************
ai-server-01               : ok=2    changed=0    unreachable=0    failed=0
ai-server-02               : ok=2    changed=0    unreachable=0    failed=0
```

## Common Pitfalls

### Pitfall 1: Using bare module names instead of FQCNs

**Description:** Writing `openssl_certificate` or `openssl_privatekey` instead of the fully-qualified `community.crypto.x509_certificate` and `community.crypto.openssl_privatekey`.

**Why it happens:** Older tutorials and blog posts predate the FQCN convention. The short names still work as aliases but generate deprecation warnings and will eventually be removed.

**Incorrect:**
```yaml
- openssl_privatekey:
    path: /etc/ssl/private/server.key
    type: RSA
    size: 2048
```

**Correct:**
```yaml
- community.crypto.openssl_privatekey:
    path: /etc/ssl/private/server.key
    type: ECC
    curve: secp256r1
```

---

### Pitfall 2: Missing the Python cryptography library on managed hosts

**Description:** The play fails with `"Failed to find required Python library: cryptography"` on managed hosts even though OpenSSL is installed at the OS level.

**Why it happens:** The `community.crypto` modules use Python's `cryptography` package for key and certificate operations, not the `openssl` CLI binary. OS-level OpenSSL and Python's `cryptography` package are independent installations.

**Incorrect:** Assuming `openssl` being present on the host is sufficient, or installing `python3-openssl` (which is a different, older package — `pyOpenSSL`).

**Correct:** Include a bootstrap task before any crypto tasks:
```yaml
- name: Install Python cryptography library
  ansible.builtin.package:
    name: python3-cryptography
    state: present
  become: true
```

---

### Pitfall 3: Forgetting `delegate_to: localhost` when signing with the CA

**Description:** The `x509_certificate` task with `provider: ownca` runs on the managed host and fails because the CA key does not exist there (and should not).

**Why it happens:** Ansible runs tasks on the managed host by default. The CA key is on the control node and must stay there.

**Incorrect:**
```yaml
- name: Sign certificate
  community.crypto.x509_certificate:
    path: /etc/ssl/certs/server.crt
    csr_path: /tmp/server.csr
    provider: ownca
    ownca_path: /pki/ca.crt
    ownca_privatekey_path: /pki/ca.key
```

**Correct:**
```yaml
- name: Sign certificate (on control node)
  community.crypto.x509_certificate:
    path: "{{ pki_dir }}/issued/{{ inventory_hostname }}.crt"
    csr_path: "{{ pki_dir }}/issued/{{ inventory_hostname }}.csr"
    provider: ownca
    ownca_path: "{{ pki_dir }}/ca.crt"
    ownca_privatekey_path: "{{ pki_dir }}/ca.key"
  delegate_to: localhost
  become: false
```

---

### Pitfall 4: Running ACME pass 2 unconditionally

**Description:** The second `acme_certificate` task (which asks Let's Encrypt to validate the challenge) runs even when `acme_challenge` was not changed, causing an `acme_challenge` variable that lacks the required `data` structure and a confusing error from the ACME server.

**Why it happens:** The `when: acme_challenge is changed` guard is omitted or placed incorrectly.

**Incorrect:**
```yaml
- name: ACME pass 2
  community.crypto.acme_certificate:
    data: "{{ acme_challenge }}"
    # ... other params
  # no 'when' guard
```

**Correct:**
```yaml
- name: ACME pass 2
  community.crypto.acme_certificate:
    data: "{{ acme_challenge }}"
    # ... other params
  when: acme_challenge is changed
```

---

### Pitfall 5: Using restart instead of reload for Nginx after cert deployment

**Description:** The Nginx handler uses `state: restarted` instead of `state: reloaded`, dropping all active TLS connections during a certificate rotation.

**Why it happens:** `restarted` is the default go-to for "apply new config" and works for most services, but Nginx supports graceful reload (`nginx -s reload`) which applies new certificates to new connections while completing existing ones.

**Incorrect:**
```yaml
handlers:
  - name: Restart Nginx
    ansible.builtin.service:
      name: nginx
      state: restarted
```

**Correct:**
```yaml
handlers:
  - name: Reload Nginx
    ansible.builtin.service:
      name: nginx
      state: reloaded
```

---

### Pitfall 6: Committing unencrypted CA keys to version control

**Description:** The `ca.key` file is committed to the Git repository in plaintext.

**Why it happens:** Developers treat the PKI directory the same as other playbook files and `git add .` without thinking.

**Incorrect:** `git add pki/ca.key && git commit`

**Correct:** Add the CA key to `.gitignore` and encrypt it separately with Ansible Vault before committing:
```bash
echo "pki/*.key" >> .gitignore
ansible-vault encrypt pki/ca.key
git add pki/ca.key.vault  # or keep it out of git entirely
```

---

### Pitfall 7: Not setting `subject_alt_name` on server certificates

**Description:** The issued certificate is rejected by Python's `requests` library, Go's `net/http`, or any modern TLS client with an error like `certificate has no SANs` or `x509: certificate relies on legacy Common Name field`.

**Why it happens:** RFC 2818 (2000) deprecated using `commonName` for host verification. All major runtimes now require `subjectAltName`. The `openssl_csr` module does not add a SAN by default.

**Incorrect:**
```yaml
- community.crypto.openssl_csr:
    path: /tmp/server.csr
    privatekey_path: /etc/ssl/private/server.key
    common_name: "ai-server-01.internal"
    # no subject_alt_name
```

**Correct:**
```yaml
- community.crypto.openssl_csr:
    path: /tmp/server.csr
    privatekey_path: /etc/ssl/private/server.key
    common_name: "ai-server-01.internal"
    subject_alt_name:
      - "DNS:ai-server-01.internal"
      - "IP:10.0.1.50"
```

---

### Pitfall 8: Scheduling the ACME renewal playbook too infrequently

**Description:** The renewal playbook is scheduled weekly or monthly. Let's Encrypt's rate limits or a transient DNS outage causes a renewal to fail silently, and the certificate expires before the next scheduled run.

**Why it happens:** Teams assume a 90-day certificate with `remaining_days: 30` means monthly scheduling is safe. It is — until one run fails.

**Incorrect:** A weekly cron job for certificate renewal with no alerting on failure.

**Correct:** Schedule the renewal playbook daily, configure the cron job to email on non-zero exit codes, and run the monitoring playbook separately to catch any cert that slipped through. Daily renewal attempts are cheap — the playbook makes no ACME API calls when `remaining_days` has not been crossed.

## Summary

- The `community.crypto` collection provides `openssl_privatekey`, `openssl_csr`, and `x509_certificate` as the core building blocks for automating private CA certificate issuance across a fleet; use FQCNs for all module references and pin the collection version in `requirements.yml`.
- Distributing a private CA certificate requires copying to the OS trust store directory and running `update-ca-certificates` (Debian) or `update-ca-trust extract` (RHEL) via a handler, so the command only runs when the CA cert actually changes.
- The `acme_certificate` module implements the ACME protocol natively in Ansible; the two-pass challenge pattern with `when: acme_challenge is changed` and `remaining_days: 30` makes the same playbook handle both first issuance and renewal idempotently.
- All private key files must be owned `root:ssl-cert` with mode `0640`; only service users that need them (Nginx, Gunicorn) should be added to the `ssl-cert` group, and CA private keys must be encrypted with Ansible Vault before touching version control.
- Mutual TLS between AI microservices is implemented by issuing client certificates with `extended_key_usage: clientAuth` from the private CA and configuring Nginx with `ssl_verify_client on`, providing cryptographic service identity independent of network-layer controls.

## Further Reading

- [community.crypto Collection Index — Ansible Documentation](https://docs.ansible.com/ansible/latest/collections/community/crypto/index.html) — The official module reference for every module in `community.crypto`, including full parameter tables, return values, and version compatibility notes for `openssl_privatekey`, `openssl_csr`, `x509_certificate`, `acme_certificate`, and `openssl_certificate_info`.

- [acme_certificate Module — Ansible Documentation](https://docs.ansible.com/ansible/latest/collections/community/crypto/acme_certificate_module.html) — Deep-dive reference for the ACME module covering all challenge types (http-01, dns-01, tls-alpn-01), account key management, rate limit handling, and the full two-pass workflow with complete parameter descriptions.

- [Let's Encrypt Rate Limits](https://letsencrypt.org/docs/rate-limits/) — Official documentation on Let's Encrypt's issuance rate limits (50 certificates per registered domain per week, 5 duplicate certificates per week), essential for sizing your fleet's renewal schedule and understanding when to use the staging environment for testing.

- [NIST SP 800-57 Part 1 Rev. 5 — Recommendation for Key Management](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final) — NIST's authoritative guidance on cryptographic key lifetimes, algorithm selection (covering EC vs RSA), and key storage practices; the source of record for justifying your CA key algorithm and certificate validity period choices to auditors.

- [Nginx SSL Termination and mTLS Configuration](https://nginx.org/en/docs/http/ngx_http_ssl_module.html) — Official Nginx documentation for all `ssl_*` directives including `ssl_verify_client`, `ssl_client_certificate`, `ssl_verify_depth`, `ssl_protocols`, and `ssl_ciphers`; required reading for correctly configuring the server-side mTLS Nginx blocks deployed by your Ansible playbooks.

- [Ansible Vault — Encrypting Content](https://docs.ansible.com/ansible/latest/vault_guide/index.html) — Official guide to encrypting variables, files, and strings with Ansible Vault; covers `ansible-vault encrypt`, `encrypt_string`, vault IDs for multi-password workflows, and how to pass vault passwords in CI/CD pipelines — all necessary for protecting CA private keys in your PKI playbooks.

- [RFC 5280 — Internet X.509 PKI Certificate and CRL Profile](https://www.rfc-editor.org/rfc/rfc5280) — The IETF standard defining the X.509 certificate structure, extension semantics (`subjectAltName`, `basicConstraints`, `keyUsage`, `extendedKeyUsage`), and validity rules; indispensable when debugging why a certificate is rejected by a strict TLS client or why a CA cert is not trusted as an issuer.
