# Module 7: Secrets and Vault
> Subject: Ansible | Difficulty: Intermediate | Estimated Time: 255 minutes

## Objective

After completing this module, you will be able to encrypt individual variable values with `ansible-vault encrypt_string`, encrypt whole variable files, and understand the difference between the two approaches. You will configure vault password files and vault IDs so that multiple environments (dev, staging, prod) each carry their own encryption passwords without interference. You will integrate vault seamlessly into playbook runs using `--ask-vault-pass`, `--vault-password-file`, and `--vault-id`. You will structure `group_vars` so that production secrets are physically separated from development secrets and never commingle. You will store real-world API keys — OpenAI keys, Anthropic API keys, HuggingFace tokens — inside vault, and deploy `.env` files to remote servers by rendering those secrets through Jinja2 templates. You will use `no_log: true` to prevent secret values from appearing in Ansible output or logs. You will understand how vault fits into CI/CD pipelines using environment variables or secret-store integrations. Finally, you will know when to reach beyond Ansible Vault to external secret stores such as HashiCorp Vault or AWS Secrets Manager using Ansible lookup plugins, and you will be able to audit your playbooks to locate every point where a secret is consumed.

## Prerequisites

- Completed **Module 1** — comfortable with inventory files, running ad-hoc commands, and the basic playbook structure (`hosts`, `tasks`, `vars`)
- Completed **Module 2** — familiar with variables, `vars_files`, `group_vars/`, and Jinja2 variable substitution (`{{ variable_name }}`)
- Completed **Module 3** — understands roles, `defaults/main.yml`, and `vars/main.yml` inside a role
- Completed **Module 5** — familiar with templates (`ansible.builtin.template`) and the `notify`/`handler` pattern
- Completed **Module 6** — comfortable with multi-environment inventories and `group_vars` directory trees
- Ansible 2.17 or later installed on your control node (`ansible --version`; current stable release is Ansible 11.4.0 / ansible-core 2.17.x)
- Python 3.10 or later on the control node
- A text editor and a terminal with access to at least one managed host (a local VM or a container running SSH is sufficient)

## Key Concepts

---

### Why Secrets Management Deserves Its Own Module

Every AI service infrastructure eventually accumulates secrets: API keys for foundation model providers (OpenAI, Anthropic, Mistral, HuggingFace), database passwords, TLS private keys, OAuth client secrets, and cloud provider credentials. Handling these carelessly — hardcoding them in playbooks, committing them to Git in plain text, printing them in task output — creates vulnerabilities that are difficult to remediate after the fact because secrets can live in Git history indefinitely.

Ansible Vault is Ansible's built-in answer to this problem. It uses AES-256 symmetric encryption to protect secret data at rest inside your repository. The vault password itself never enters the repository; it is supplied at runtime or read from a file or external script that CI/CD systems control.

**The core principle:** encrypt the secret, commit the ciphertext, supply the password out-of-band.

---

### Ansible Vault Fundamentals

#### How Vault Encryption Works

Ansible Vault encrypts data using AES-256-CBC with a key derived from your vault password via PBKDF2-HMAC-SHA256. Every encrypted blob starts with the header line `$ANSIBLE_VAULT;1.1;AES256` (or `$ANSIBLE_VAULT;1.2;AES256` when vault IDs are in use), which tells Ansible — and any human reader — that the file or string is vault-encrypted and not a plain-text mistake. The ciphertext is then stored as a hex string.

Encrypted values are useless without the vault password. Git blame, GitHub diffs, and log files reveal only the ciphertext, which provides no information about the underlying secret.

#### Two Encryption Granularities

| Granularity | Command | Stored As | Best For |
|---|---|---|---|
| Whole file | `ansible-vault encrypt` | A `.yml` file whose entire content is ciphertext | Encrypting a `group_vars` file wholesale |
| Single string | `ansible-vault encrypt_string` | An inline YAML block scalar beginning with `!vault` | Mixing a few secrets into an otherwise-plain variable file |

Choose **whole-file** encryption when a file contains nothing but secrets (e.g., `group_vars/prod/vault.yml`). Choose **inline string** encryption when most variables in a file are non-sensitive and you want to leave them readable.

---

### Encrypting an Entire File

```bash
# Create a plain variable file first
cat > group_vars/prod/vault.yml << 'EOF'
vault_openai_api_key: "sk-prod-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
vault_anthropic_api_key: "sk-ant-prod-xxxxxxxxxxxxxxxxxxxxxxxx"
vault_huggingface_token: "hf_prodxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
vault_db_password: "Sup3rS3cr3tProdDB!"
vault_tls_private_key: |
  -----BEGIN PRIVATE KEY-----
  MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7...
  -----END PRIVATE KEY-----
EOF

# Encrypt the file in-place — you will be prompted for a password
ansible-vault encrypt group_vars/prod/vault.yml
```

After encryption, the file looks like:

```
$ANSIBLE_VAULT;1.1;AES256
66386439653762333665353930626661323237396334363830363230343561396132643133653839
3463306630636561303565333461646437373232316261620a3139363330633739626666...
```

To view the decrypted content without writing it to disk:

```bash
ansible-vault view group_vars/prod/vault.yml
```

To decrypt in-place (use sparingly — avoid leaving plaintext secrets on disk):

```bash
ansible-vault decrypt group_vars/prod/vault.yml
```

To edit without decrypting to a file on disk:

```bash
ansible-vault edit group_vars/prod/vault.yml
```

To change the vault password for a file:

```bash
ansible-vault rekey group_vars/prod/vault.yml
```

---

### Encrypting Individual Strings with `encrypt_string`

When your variable file is mostly non-sensitive (hostnames, port numbers, feature flags) but contains a handful of secrets, encrypting the whole file makes every value opaque. `encrypt_string` is better: it encrypts just the value and produces an inline YAML block scalar you paste into your file.

```bash
# Encrypt a single value — you will be prompted for the vault password
ansible-vault encrypt_string 'sk-ant-staging-xxxxxxxxxxxxxxxx' \
  --name 'vault_anthropic_api_key'
```

Output:

```yaml
vault_anthropic_api_key: !vault |
          $ANSIBLE_VAULT;1.1;AES256
          34323435363037393039306330386337373663626664343433373338666531346537333065303035
          3666613561303534613866353661376462376531393538300a333163623039313164323763613834
          65363939646363376163343662343930363435336233653934353465636338353231353063383036
          3866383032306131303363663730646261346663616661350a3166363938303332353363643165
```

Paste that block directly into your `group_vars/staging/vars.yml`:

```yaml
# group_vars/staging/vars.yml
# Non-sensitive values — readable by everyone
ai_model_endpoint: "https://api.anthropic.com/v1/messages"
ai_model_name: "claude-3-5-sonnet-20241022"
inference_timeout_seconds: 30
log_level: "info"

# Sensitive values — encrypted inline
vault_anthropic_api_key: !vault |
          $ANSIBLE_VAULT;1.1;AES256
          34323435363037393039306330386337373663626664343433373338666531346537333065303035
          3666613561303534613866353661376462376531393538300a333163623039313164323763613834
          65363939646363376163343662343930363435336233653934353465636338353231353063383036
          3866383032306131303363663730646261346663616661350a3166363938303332353363643165
```

The convention of prefixing secret variable names with `vault_` (e.g., `vault_anthropic_api_key` rather than `anthropic_api_key`) is widely adopted. It makes secrets immediately identifiable during code review and makes it simple to grep for every vault-sourced value.

---

### Vault Password Files

Typing the vault password interactively works in development but breaks automation. Ansible accepts a password file: any file whose first line is the vault password.

```bash
# Create the password file — NEVER commit this to Git
echo 'MyVaultPassw0rd!' > ~/.ansible/vault_pass.txt
chmod 600 ~/.ansible/vault_pass.txt
```

Add the file to `.gitignore` at the repository root:

```
# .gitignore
.vault_pass*
*.vault_pass
vault_pass.txt
~/.ansible/
```

Reference it at the command line:

```bash
ansible-playbook deploy_ai_services.yml --vault-password-file ~/.ansible/vault_pass.txt
```

Or set it permanently in `ansible.cfg` so you never need to type the flag:

```ini
# ansible.cfg
[defaults]
vault_password_file = ~/.ansible/vault_pass.txt
```

The password file can also be an executable script. Ansible checks whether the file is executable; if it is, Ansible runs it and uses stdout as the password. This lets you fetch the password from a credential manager at runtime:

```bash
#!/usr/bin/env bash
# vault_pass_script.sh — fetch from macOS Keychain, 1Password CLI, etc.
security find-generic-password -a ansible -s vault_master -w
```

```bash
chmod +x vault_pass_script.sh
ansible-playbook deploy_ai_services.yml --vault-password-file ./vault_pass_script.sh
```

---

### Vault IDs — Multiple Passwords for Multiple Environments

A production fleet typically runs dev, staging, and prod environments. You want dev engineers to decrypt dev secrets without ever having access to the prod vault password. Vault IDs solve this.

A vault ID is a label you attach to both the encrypted content and the password source. The format is `label@source`.

#### Encrypting with a Vault ID

```bash
# Encrypt a file and tag it with the 'prod' vault ID
ansible-vault encrypt group_vars/prod/vault.yml --vault-id prod@~/.ansible/vault_pass_prod.txt

# Encrypt a staging file with the 'staging' vault ID
ansible-vault encrypt group_vars/staging/vault.yml --vault-id staging@~/.ansible/vault_pass_staging.txt

# Encrypt a dev file with the 'dev' vault ID
ansible-vault encrypt group_vars/dev/vault.yml --vault-id dev@~/.ansible/vault_pass_dev.txt
```

The encrypted header now carries the label:

```
$ANSIBLE_VAULT;1.2;AES256;prod
```

#### Running a Playbook with Multiple Vault IDs

```bash
ansible-playbook site.yml \
  --vault-id dev@~/.ansible/vault_pass_dev.txt \
  --vault-id staging@~/.ansible/vault_pass_staging.txt \
  --vault-id prod@~/.ansible/vault_pass_prod.txt
```

Ansible tries each supplied password in order until one decrypts each vault blob successfully. You can supply as many `--vault-id` flags as you have environments.

For interactive use, append `prompt` instead of a file path:

```bash
ansible-playbook site.yml --vault-id prod@prompt
```

---

### Structuring `group_vars` for Multi-Environment Secrets

A clean layout separates the encrypted vault file from the plain variable file within each environment group. This makes diffs readable — reviewers see plain config changes without sifting through ciphertext.

```
inventory/
├── hosts.ini
group_vars/
├── all/
│   ├── vars.yml          # Non-sensitive defaults for all hosts
│   └── vault.yml         # Encrypted: secrets shared across all environments
├── dev/
│   ├── vars.yml          # Non-sensitive dev overrides
│   └── vault.yml         # Encrypted with 'dev' vault ID
├── staging/
│   ├── vars.yml          # Non-sensitive staging overrides
│   └── vault.yml         # Encrypted with 'staging' vault ID
└── prod/
    ├── vars.yml          # Non-sensitive prod overrides
    └── vault.yml         # Encrypted with 'prod' vault ID
```

**`group_vars/prod/vars.yml`** (plain — committed as-is):

```yaml
# group_vars/prod/vars.yml
ai_service_port: 8080
ai_model_name: "claude-opus-4-5"
ai_inference_endpoint: "https://api.anthropic.com/v1/messages"
openai_base_url: "https://api.openai.com/v1"
huggingface_inference_endpoint: "https://api-inference.huggingface.co/models"
log_level: "warning"
deploy_env: "prod"
```

**`group_vars/prod/vault.yml`** (encrypted — shows only ciphertext in Git):

```yaml
# This file is encrypted with: ansible-vault encrypt --vault-id prod@...
# Plaintext contents (for documentation purposes only — do not commit plaintext):
#   vault_openai_api_key: "sk-prod-..."
#   vault_anthropic_api_key: "sk-ant-prod-..."
#   vault_huggingface_token: "hf_prod..."
#   vault_db_password: "..."
#   vault_redis_password: "..."
```

In your playbooks and roles, reference the vault variable directly:

```yaml
- name: Configure AI service environment
  ansible.builtin.template:
    src: ai_service.env.j2
    dest: /opt/ai_service/.env
    owner: ai_service
    group: ai_service
    mode: "0600"
```

---

### Storing and Deploying AI Service API Keys

This section walks through the full workflow of encrypting API keys for an AI service fleet and deploying them as a `.env` file.

#### Step 1 — Create the Vault File with All API Keys

```bash
# Decrypt (or create fresh) the prod vault file
ansible-vault edit group_vars/prod/vault.yml --vault-id prod@~/.ansible/vault_pass_prod.txt
```

Inside the editor, write:

```yaml
vault_openai_api_key: "sk-prod-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
vault_anthropic_api_key: "sk-ant-prod-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
vault_huggingface_token: "hf_prodxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
vault_db_password: "Prod_DB_P@ssw0rd_2024!"
vault_redis_password: "Prod_Redis_S3cr3t!"
vault_tls_private_key_content: |
  -----BEGIN PRIVATE KEY-----
  MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7o4qne60TB3wo
  ...full key content...
  -----END PRIVATE KEY-----
```

Save and close the editor. Ansible re-encrypts the file automatically.

#### Step 2 — Create the Jinja2 Template for the `.env` File

```
# templates/ai_service.env.j2
# Generated by Ansible — DO NOT EDIT MANUALLY
# Deployed: {{ ansible_date_time.iso8601 }}
# Environment: {{ deploy_env }}

# Foundation Model API Keys
OPENAI_API_KEY={{ vault_openai_api_key }}
ANTHROPIC_API_KEY={{ vault_anthropic_api_key }}
HUGGINGFACE_TOKEN={{ vault_huggingface_token }}

# Inference configuration
AI_MODEL_NAME={{ ai_model_name }}
AI_INFERENCE_ENDPOINT={{ ai_inference_endpoint }}
OPENAI_BASE_URL={{ openai_base_url }}
HUGGINGFACE_INFERENCE_ENDPOINT={{ huggingface_inference_endpoint }}

# Database
DATABASE_URL=postgresql://ai_service:{{ vault_db_password }}@{{ db_host }}:5432/ai_service_{{ deploy_env }}

# Cache
REDIS_URL=redis://:{{ vault_redis_password }}@{{ redis_host }}:6379/0

# Application
LOG_LEVEL={{ log_level }}
DEPLOY_ENV={{ deploy_env }}
```

#### Step 3 — Write the Deployment Task

```yaml
# roles/ai_service/tasks/main.yml
- name: Deploy AI service environment file
  ansible.builtin.template:
    src: ai_service.env.j2
    dest: /opt/ai_service/.env
    owner: ai_service
    group: ai_service
    mode: "0600"
  no_log: true
  notify: Restart ai_service
```

`mode: "0600"` restricts the deployed `.env` file so only the owning service account can read it. `no_log: true` prevents the rendered template content — including the decrypted API keys — from appearing in Ansible's task output.

#### Step 4 — Deploy TLS Private Key

```yaml
- name: Deploy TLS private key
  ansible.builtin.copy:
    content: "{{ vault_tls_private_key_content }}"
    dest: /etc/ssl/private/ai_service.key
    owner: root
    group: ssl-cert
    mode: "0640"
  no_log: true
```

---

### Using `no_log: true` to Suppress Sensitive Output

By default, Ansible prints the details of every task — including `changed` diffs that may contain variable values — to stdout and to any configured callback plugins. For tasks that handle secrets, `no_log: true` completely suppresses task output. The task name and status (ok/changed/failed) still appear; only the parameters are hidden.

```yaml
- name: Set application secret key in config
  ansible.builtin.lineinfile:
    path: /opt/ai_service/config.ini
    regexp: '^SECRET_KEY='
    line: "SECRET_KEY={{ vault_app_secret_key }}"
  no_log: true

- name: Create database user with password
  community.postgresql.postgresql_user:
    name: ai_service
    password: "{{ vault_db_password }}"
    db: ai_service_prod
    priv: "ALL"
  no_log: true
  become: true
  become_user: postgres
```

**Apply `no_log: true` to any task that:**
- Writes a password, token, or key to a file
- Creates or updates a database user with a password
- Makes an API call that includes a credential in the body or URL
- Modifies a config file that will contain a secret

You can also suppress logging at the play level, but this is rarely advisable because it also hides useful debugging output for non-sensitive tasks:

```yaml
- hosts: ai_servers
  no_log: true   # Applies to every task in this play — use with caution
  tasks:
    - name: This task's output is also hidden
      ansible.builtin.debug:
        msg: "This message will not appear"
```

A practical pattern is to group all secret-handling tasks into a dedicated task file and import it with `no_log` at the `include_tasks` level rather than suppressing the entire play.

---

### Running Playbooks with Vault — CLI Reference

| Scenario | Command |
|---|---|
| Prompt interactively for a single vault password | `ansible-playbook site.yml --ask-vault-pass` |
| Supply a password file | `ansible-playbook site.yml --vault-password-file ~/.ansible/vault_pass.txt` |
| Supply a vault ID with a password file | `ansible-playbook site.yml --vault-id prod@~/.ansible/vault_pass_prod.txt` |
| Multiple vault IDs simultaneously | `ansible-playbook site.yml --vault-id dev@dev.txt --vault-id prod@prod.txt` |
| Prompt for a named vault ID | `ansible-playbook site.yml --vault-id prod@prompt` |
| Use `ansible.cfg` to set a default | Set `vault_password_file` in `[defaults]` — no flag needed |

---

### Vault in CI/CD Pipelines

In a CI/CD system (GitHub Actions, GitLab CI, Jenkins, CircleCI), you cannot type a vault password interactively. The standard pattern is to store the vault password as a CI/CD secret environment variable and write it to a temporary file at the start of the pipeline job.

#### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy AI Services

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Install Ansible
        run: pip install ansible==11.4.0

      - name: Write vault password file
        run: |
          echo "${{ secrets.ANSIBLE_VAULT_PASS_PROD }}" > /tmp/vault_pass_prod.txt
          chmod 600 /tmp/vault_pass_prod.txt

      - name: Run deployment playbook
        run: |
          ansible-playbook site.yml \
            --vault-id prod@/tmp/vault_pass_prod.txt \
            -i inventory/prod/hosts.ini

      - name: Clean up vault password file
        if: always()
        run: rm -f /tmp/vault_pass_prod.txt
```

The `if: always()` condition on the cleanup step ensures the password file is removed even if the deployment fails. The secret `ANSIBLE_VAULT_PASS_PROD` is configured in the GitHub repository's Settings > Secrets and Variables > Actions.

#### GitLab CI Example

```yaml
# .gitlab-ci.yml
deploy_prod:
  stage: deploy
  image: python:3.12-slim
  before_script:
    - pip install ansible==11.4.0
    - echo "$ANSIBLE_VAULT_PASS_PROD" > /tmp/vault_pass_prod.txt
    - chmod 600 /tmp/vault_pass_prod.txt
  script:
    - ansible-playbook site.yml
        --vault-id prod@/tmp/vault_pass_prod.txt
        -i inventory/prod/hosts.ini
  after_script:
    - rm -f /tmp/vault_pass_prod.txt
  only:
    - main
  environment:
    name: production
```

**Key principles for vault in CI/CD:**
- Store the vault password only in the CI/CD system's native secret store, never in the repository
- Use `if: always()` or `after_script` to clean up password files regardless of job outcome
- Use separate vault IDs and separate CI/CD secrets for each environment — a staging deploy job should never have access to the prod vault password
- Consider rotating vault passwords on a schedule and updating them in the CI/CD secret store separately from re-encrypting the vault files

---

### External Secret Stores — HashiCorp Vault and AWS Secrets Manager

Ansible Vault is excellent for teams managing secrets inside a Git repository, but large organizations often centralize secrets in a dedicated secret store. Ansible's `lookup` plugin system lets playbooks fetch secrets at runtime from these stores without storing the secret locally at all.

#### `community.hashi_vault.hashi_vault` Lookup Plugin

The `hashi_vault` lookup fetches secrets from a HashiCorp Vault server. Install the collection first:

```bash
ansible-galaxy collection install community.hashi_vault
```

Usage in a playbook:

```yaml
- name: Deploy AI service environment file using HashiCorp Vault secrets
  hosts: ai_servers
  vars:
    openai_api_key: >-
      {{ lookup('community.hashi_vault.hashi_vault',
         'secret=secret/data/ai_services/prod:openai_api_key
          url=https://vault.internal.example.com:8200
          auth_method=approle
          role_id={{ lookup("env", "VAULT_ROLE_ID") }}
          secret_id={{ lookup("env", "VAULT_SECRET_ID") }}') }}
  tasks:
    - name: Write environment file
      ansible.builtin.template:
        src: ai_service.env.j2
        dest: /opt/ai_service/.env
        mode: "0600"
      no_log: true
```

#### `amazon.aws.aws_secret` Lookup Plugin

The `aws_secret` lookup fetches secrets from AWS Secrets Manager. Install the collection first:

```bash
ansible-galaxy collection install amazon.aws
```

Usage in a playbook:

```yaml
- name: Deploy AI service using AWS Secrets Manager
  hosts: ai_servers
  vars:
    anthropic_api_key: >-
      {{ lookup('amazon.aws.aws_secret',
         'prod/ai_services/anthropic_api_key',
         region='us-east-1') }}
    db_password: >-
      {{ lookup('amazon.aws.aws_secret',
         'prod/ai_services/db_password',
         region='us-east-1') }}
  tasks:
    - name: Write environment file
      ansible.builtin.template:
        src: ai_service.env.j2
        dest: /opt/ai_service/.env
        mode: "0600"
      no_log: true
```

AWS credentials must be available on the control node — either via instance profile, environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`), or `~/.aws/credentials`.

#### Ansible Vault vs. External Secret Stores

| Factor | Ansible Vault | HashiCorp Vault / AWS Secrets Manager |
|---|---|---|
| Infrastructure required | None — lives in Git | Dedicated service to operate or pay for |
| Secret rotation | Manual re-encryption and commit | Automated rotation policies |
| Audit logging | None built-in | Full access audit trail |
| Dynamic secrets | Not supported | Supported (e.g., ephemeral DB creds) |
| Team size sweet spot | Small to medium teams | Medium to large organizations |
| Zero-trust posture | Partial — anyone with vault password sees all secrets | Fine-grained ACLs per secret/path |
| Git history risk | Ciphertext in Git — low risk if password is safe | No secrets in Git at all |

For an AI service fleet at a startup or a small engineering team, Ansible Vault is typically sufficient and has no operational overhead. For enterprises with compliance requirements, a dedicated secret store plus Ansible lookup plugins is the right architecture.

---

### What to Vault vs. What to Leave Plain

Not everything should be encrypted. Over-encrypting makes diffs unreadable and slows collaboration. Under-encrypting creates exposure.

**Always vault:**
- API keys and tokens for any external service (OpenAI, Anthropic, HuggingFace, Stripe, Twilio, etc.)
- Database passwords and connection string passwords
- TLS/SSL private keys and certificate private key files
- OAuth client secrets and JWT signing keys
- SSH private keys managed by Ansible
- Any password a human or service uses to authenticate

**Leave plain (never vault):**
- Hostnames, IP addresses, and port numbers
- Feature flags and application configuration (log levels, timeouts, thread counts)
- Software version numbers and package names
- Non-sensitive environment identifiers (`deploy_env: prod`)
- Public keys and public certificates
- URLs (unless the URL itself encodes a credential — avoid embedding credentials in URLs)

**Edge cases:**
- Internal hostnames and IP ranges may be considered sensitive under certain threat models; vault them if your organization requires it
- HuggingFace model IDs (`meta-llama/Meta-Llama-3-8B-Instruct`) are public — never vault; but the HuggingFace access token to download a gated model must be vaulted

---

### Auditing Secrets Usage in Playbooks

Before pushing changes or reviewing a colleague's PR, verify that every task consuming a vault variable is properly protected.

#### Finding All Vault Variable References

The naming convention of prefixing vault variables with `vault_` makes auditing trivial:

```bash
# Find every reference to a vault variable across the entire project
grep -r 'vault_' --include='*.yml' --include='*.j2' .
```

#### Verifying `no_log` Is Present Where Required

```bash
# Find tasks that reference a vault variable but lack no_log
grep -rn 'vault_' --include='*.yml' . | grep -v 'no_log: true' | grep -v 'vault.yml'
```

This is a heuristic — review each hit manually to decide whether `no_log` is warranted. Template tasks (`ansible.builtin.template`) deserve special attention because the entire rendered output is secret when the template contains vault variables.

#### Verifying No Plaintext Secrets in the Repository

```bash
# Scan for common API key patterns that may have been accidentally committed
grep -rn 'sk-[a-zA-Z0-9_-]\{20,\}' --include='*.yml' .
grep -rn 'hf_[a-zA-Z0-9]\{20,\}' --include='*.yml' .
grep -rn 'sk-ant-' --include='*.yml' .
```

For teams using Git, add a pre-commit hook or integrate a tool such as `git-secrets` or `trufflehog` into CI to catch accidental plaintext secret commits before they reach the remote.

#### Listing All Encrypted Files in the Repository

```bash
# Find every file that Ansible Vault has encrypted
grep -rl '\$ANSIBLE_VAULT' .
```

Review this list periodically to confirm that no files have been accidentally decrypted and committed in plaintext.

---

## Hands-On Examples

### Example 1 — Encrypting a Variable File and Viewing Its Contents

This example takes approximately 15 minutes.

**Goal:** Create a `group_vars/staging/vault.yml` file containing staging AI service credentials, encrypt it with a vault ID, and verify that the ciphertext is what ends up on disk.

```bash
# 1. Create the directory structure
mkdir -p group_vars/staging

# 2. Write the plaintext vault file
cat > group_vars/staging/vault.yml << 'EOF'
vault_anthropic_api_key: "sk-ant-staging-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
vault_huggingface_token: "hf_stagingxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
vault_db_password: "StagingDB_P@ssw0rd!"
EOF

# 3. Create the staging vault password file
echo 'StagingVaultPass123' > ~/.ansible/vault_pass_staging.txt
chmod 600 ~/.ansible/vault_pass_staging.txt

# 4. Encrypt the file with the 'staging' vault ID
ansible-vault encrypt group_vars/staging/vault.yml \
  --vault-id staging@~/.ansible/vault_pass_staging.txt

# 5. Confirm the file is now ciphertext
cat group_vars/staging/vault.yml

# 6. View the decrypted contents without writing to disk
ansible-vault view group_vars/staging/vault.yml \
  --vault-id staging@~/.ansible/vault_pass_staging.txt
```

Expected output from step 5 — the first line should be the vault header:

```
$ANSIBLE_VAULT;1.2;AES256;staging
```

Expected output from step 6 — the original YAML:

```yaml
vault_anthropic_api_key: "sk-ant-staging-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
vault_huggingface_token: "hf_stagingxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
vault_db_password: "StagingDB_P@ssw0rd!"
```

---

### Example 2 — Deploying an AI Service `.env` File with Vault Secrets

This example takes approximately 45 minutes. It requires a managed host reachable via SSH (a local VM or container is sufficient).

**Goal:** Write a playbook that reads encrypted API keys from `group_vars/prod/vault.yml` and deploys a rendered `.env` file to `/opt/ai_service/.env` on a prod host, suppressing all secret output.

**Directory structure to build:**

```
.
├── ansible.cfg
├── inventory/
│   └── prod/
│       └── hosts.ini
├── group_vars/
│   └── prod/
│       ├── vars.yml
│       └── vault.yml         (will be encrypted)
├── templates/
│   └── ai_service.env.j2
└── deploy_ai_secrets.yml
```

**`ansible.cfg`:**

```ini
[defaults]
inventory = inventory/prod/hosts.ini
remote_user = deploy
host_key_checking = False
```

**`inventory/prod/hosts.ini`:**

```ini
[ai_servers]
ai-prod-01 ansible_host=192.168.56.10
```

**`group_vars/prod/vars.yml`:**

```yaml
deploy_env: "prod"
ai_model_name: "claude-opus-4-5"
ai_inference_endpoint: "https://api.anthropic.com/v1/messages"
openai_base_url: "https://api.openai.com/v1"
huggingface_inference_endpoint: "https://api-inference.huggingface.co/models"
log_level: "warning"
db_host: "db.prod.internal"
redis_host: "redis.prod.internal"
```

**`group_vars/prod/vault.yml`** (create and immediately encrypt):

```bash
cat > group_vars/prod/vault.yml << 'EOF'
vault_openai_api_key: "sk-prod-replace-with-real-key"
vault_anthropic_api_key: "sk-ant-prod-replace-with-real-key"
vault_huggingface_token: "hf_prod_replace_with_real_token"
vault_db_password: "Prod_DB_P@ssw0rd_2024!"
vault_redis_password: "Prod_Redis_S3cr3t_2024!"
EOF

echo 'ProdVaultPass456' > ~/.ansible/vault_pass_prod.txt
chmod 600 ~/.ansible/vault_pass_prod.txt

ansible-vault encrypt group_vars/prod/vault.yml \
  --vault-id prod@~/.ansible/vault_pass_prod.txt
```

**`templates/ai_service.env.j2`:**

```
# Generated by Ansible on {{ ansible_date_time.iso8601 }}
# Environment: {{ deploy_env }}

OPENAI_API_KEY={{ vault_openai_api_key }}
ANTHROPIC_API_KEY={{ vault_anthropic_api_key }}
HUGGINGFACE_TOKEN={{ vault_huggingface_token }}
AI_MODEL_NAME={{ ai_model_name }}
AI_INFERENCE_ENDPOINT={{ ai_inference_endpoint }}
OPENAI_BASE_URL={{ openai_base_url }}
HUGGINGFACE_INFERENCE_ENDPOINT={{ huggingface_inference_endpoint }}
DATABASE_URL=postgresql://ai_service:{{ vault_db_password }}@{{ db_host }}:5432/ai_service_prod
REDIS_URL=redis://:{{ vault_redis_password }}@{{ redis_host }}:6379/0
LOG_LEVEL={{ log_level }}
DEPLOY_ENV={{ deploy_env }}
```

**`deploy_ai_secrets.yml`:**

```yaml
---
- name: Deploy AI service secrets and environment file
  hosts: ai_servers
  become: true

  tasks:
    - name: Ensure /opt/ai_service directory exists
      ansible.builtin.file:
        path: /opt/ai_service
        state: directory
        owner: ai_service
        group: ai_service
        mode: "0750"

    - name: Deploy AI service .env file from vault variables
      ansible.builtin.template:
        src: ai_service.env.j2
        dest: /opt/ai_service/.env
        owner: ai_service
        group: ai_service
        mode: "0600"
      no_log: true

    - name: Confirm .env file exists and has correct permissions
      ansible.builtin.stat:
        path: /opt/ai_service/.env
      register: env_file_stat

    - name: Assert .env file is present and not world-readable
      ansible.builtin.assert:
        that:
          - env_file_stat.stat.exists
          - env_file_stat.stat.mode == '0600'
        fail_msg: ".env file is missing or has insecure permissions"
        success_msg: ".env file deployed with correct permissions"
```

**Run the playbook:**

```bash
ansible-playbook deploy_ai_secrets.yml \
  --vault-id prod@~/.ansible/vault_pass_prod.txt
```

Observe that the template task shows `changed` but does not print any of the rendered content. The assert task confirms the file landed with the expected permissions.

---

### Example 3 — Inline `encrypt_string` for a Mixed Variable File

This example takes approximately 20 minutes.

**Goal:** Add a vault-encrypted HuggingFace token to an existing plain variable file using `encrypt_string`.

```bash
# 1. Generate the encrypted string
ansible-vault encrypt_string 'hf_devXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX' \
  --name 'vault_huggingface_token' \
  --vault-id dev@~/.ansible/vault_pass_dev.txt
```

Copy the output block. Then open `group_vars/dev/vars.yml` and add it:

```yaml
# group_vars/dev/vars.yml
deploy_env: "dev"
ai_model_name: "claude-haiku-3-5"
log_level: "debug"
db_host: "localhost"
redis_host: "localhost"

# Encrypted with: ansible-vault encrypt_string --vault-id dev@...
vault_huggingface_token: !vault |
          $ANSIBLE_VAULT;1.2;AES256;dev
          61616161616161616161616161616161616161616161616161616161616161616161616161616161
          6161616161616161616161616161616161616161610a616161616161616161616161616161616161
          61616161616161616161616161616161616161616161616161616161616161616161616161616161
          6161616161616161616161616161616161616161610a3131
```

Verify the value decrypts correctly using `ansible` ad-hoc debug:

```bash
ansible localhost -m ansible.builtin.debug \
  -a "var=vault_huggingface_token" \
  -e "@group_vars/dev/vars.yml" \
  --vault-id dev@~/.ansible/vault_pass_dev.txt
```

The output will show the decrypted token value — confirming the inline vault string works as a normal variable.

---

## Summary

Ansible Vault provides AES-256 encryption for secrets stored inside your repository. The two primary tools are `ansible-vault encrypt` for entire files and `ansible-vault encrypt_string` for individual values. Vault IDs (`label@source`) allow a single playbook run to decrypt secrets encrypted with different passwords, enabling per-environment isolation where a staging engineer never holds the prod vault password. The naming convention of `vault_`-prefixed variable names, combined with a split `vars.yml` / `vault.yml` layout inside each `group_vars` environment directory, keeps diffs readable while ensuring secrets are never committed in plain text.

For AI service infrastructure specifically, this means storing OpenAI, Anthropic, and HuggingFace credentials encrypted in vault, deploying them to servers exclusively through `ansible.builtin.template` with `mode: "0600"` and `no_log: true`, and rotating them by editing the vault file and re-running the deployment playbook. In CI/CD, the vault password lives as a pipeline secret and is written to a temporary file that is cleaned up regardless of job outcome. For organizations that outgrow vault's model, lookup plugins for HashiCorp Vault and AWS Secrets Manager provide a direct path to centralized, auditable, dynamically-rotated secrets without changing the playbook structure significantly.

## Further Reading

- [Ansible Vault Guide — Official Documentation](https://docs.ansible.com/ansible/latest/vault_guide/index.html) — The authoritative reference for all `ansible-vault` subcommands, vault ID syntax, and integration patterns; covers both `ansible-core` 2.15+ and older releases.
- [Encrypting Content with Ansible Vault](https://docs.ansible.com/ansible/latest/vault_guide/vault_encrypting_content.html) — Dedicated page covering `encrypt`, `decrypt`, `view`, `edit`, `rekey`, and `encrypt_string` with full syntax and flag descriptions.
- [Using Vault in Playbooks](https://docs.ansible.com/ansible/latest/vault_guide/vault_using_encrypted_content.html) — Documents `--vault-id`, `--vault-password-file`, `--ask-vault-pass`, and how Ansible resolves multiple vault IDs at runtime.
- [community.hashi_vault Collection on Ansible Galaxy](https://galaxy.ansible.com/ui/repo/published/community/hashi_vault/) — The `hashi_vault` lookup plugin and full connection/authentication options for integrating Ansible with a HashiCorp Vault server; includes AppRole, token, LDAP, and AWS IAM auth methods.
- [amazon.aws Collection — aws_secret Lookup](https://docs.ansible.com/ansible/latest/collections/amazon/aws/aws_secret_lookup.html) — Reference for the AWS Secrets Manager lookup plugin including region, profile, and versioning parameters.
- [Best Practices for Variables and Vaults — Ansible Tips and Tricks](https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html#keep-vaulted-variables-safely-visible) — Official guidance on the `vars.yml` / `vault.yml` split pattern, including the recommendation to prefix vault variables with `vault_`.
- [Trufflehog — Secret Scanner for Git Repositories](https://github.com/trufflesecurity/trufflehog) — Open-source tool that scans Git history and working trees for accidentally committed secrets; integrates into pre-commit hooks and CI pipelines to catch plaintext API keys before they reach a remote.
