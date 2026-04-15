# Module 0: Setup
> Subject: GIT | Difficulty: Beginner | Estimated Time: 120 minutes

## Objective

After completing this module, you will be able to install Git on Linux using the package manager appropriate for your distribution, perform the essential first-time configuration (identity, editor, default branch name), create and secure a GitHub account with two-factor authentication and a personal access token, run a self-hosted Gitea server using either a Linux binary install or Docker Compose, generate an ed25519 SSH key pair and register it with both GitHub and Gitea, configure HTTPS credential helpers so you are not prompted for a password on every push, clone a repository over both SSH and HTTPS, and choose the right protocol for a given situation. By the end of this module your development machine will be fully wired up and ready for every subsequent module in this series.

## Prerequisites

- A Linux machine or VM running a modern distribution (Ubuntu 22.04 LTS / 24.04 LTS, Fedora 39+, Arch Linux, or equivalent) — most commands also work on Windows Subsystem for Linux (WSL2)
- sudo (administrator) privileges on that machine
- A terminal emulator and basic comfort typing commands (changing directories, creating files)
- An internet connection for downloading packages and creating accounts
- No prior Git knowledge is required — this is the starting point

## Key Concepts

### What Git Is and Why Setup Matters

Git is a **distributed version control system**: it tracks every change you make to a set of files over time, allows you to revert to any previous state, and lets multiple people work on the same project simultaneously without overwriting each other's work. Unlike older systems that relied on a single central server, every Git clone contains the complete history of the project, so you can work entirely offline and synchronize with others when you reconnect.

Before you can do any of that, three things must be in place:

1. **Git itself** — the command-line tool installed on your machine.
2. **Your identity** — every commit you create is permanently stamped with your name and email address. Setting this correctly from the start means your contribution history is always accurate.
3. **A remote host** — a server that holds a copy of your repository so others (or your other machines) can access it. This can be GitHub (a public cloud service), Gitea (a lightweight server you run yourself), or any other Git hosting platform.

This module walks through all three in order.

### SSH vs HTTPS — Two Ways to Talk to a Git Server

Git communicates with remote servers using two main protocols:

| Feature | SSH | HTTPS |
|---|---|---|
| Authentication | Cryptographic key pair (no password prompts after setup) | Username + PAT (storable via credential helper) |
| Firewall friendliness | May be blocked on port 22 in some corporate networks | Almost never blocked (port 443) |
| Initial setup effort | Moderate (key generation + uploading public key) | Low (just a token) |
| Security model | Private key never leaves your machine | Token travels in the HTTPS handshake (encrypted) |
| Typical clone URL | `git@github.com:user/repo.git` | `https://github.com/user/repo.git` |

**Rule of thumb:** use SSH for machines you control and work on regularly. Use HTTPS when you are on a shared or temporary machine, or when SSH port 22 is blocked by a firewall.

---

## Section 1: Installing Git on Linux

### 1.1 Choosing the Right Package Manager

Linux distributions use different tools for installing software. The three most common are:

- **apt** — used by Debian, Ubuntu, Linux Mint, Pop!_OS, and derivatives
- **dnf** — used by Fedora, Red Hat Enterprise Linux (RHEL) 8+, AlmaLinux, Rocky Linux
- **pacman** — used by Arch Linux, Manjaro, EndeavourOS, and derivatives

Run `cat /etc/os-release` if you are unsure which distribution you have.

### 1.2 Installing Git with apt (Debian / Ubuntu)

The default Ubuntu and Debian repositories include Git, but they often lag behind the current stable release. The **git-core PPA** maintained by the Ubuntu Git Maintainers gives you the latest stable version.

```bash
# Step 1: Add the git-core PPA for the latest stable Git
sudo add-apt-repository ppa:git-core/ppa

# Step 2: Update the package list to include the new PPA
sudo apt update

# Step 3: Install Git
sudo apt install git
```

If you prefer to stay with the version your distribution ships (which is fine for all exercises in this series), you can skip the PPA step:

```bash
sudo apt update
sudo apt install git
```

### 1.3 Installing Git with dnf (Fedora / RHEL / AlmaLinux)

```bash
sudo dnf install git
```

On RHEL 8 and clones you may need to enable the AppStream repository first if the package is not found:

```bash
sudo dnf module enable git:2.43
sudo dnf install git
```

### 1.4 Installing Git with pacman (Arch Linux)

```bash
sudo pacman -S git
```

Arch always ships the latest stable release, so no additional repository configuration is needed.

### 1.5 Verifying the Installation

After installation, confirm Git is available and note the version:

```bash
git --version
```

Expected output (version numbers may vary; 2.43+ is fine for all exercises):

```
git version 2.53.0
```

> **Note:** The current Git stable release as of early 2026 is **2.53.0**. Any version 2.40 or later supports all features covered in this training series.

### 1.6 First-Time Global Configuration

Git reads configuration from three levels: system-wide (`/etc/gitconfig`), user-wide (`~/.gitconfig`), and per-repository (`.git/config`). The `--global` flag writes to the user-wide file, which applies to every repository you work in. Set these four values before making your first commit.

**Your identity** — baked permanently into every commit you author:

```bash
git config --global user.name "Your Full Name"
git config --global user.email "you@example.com"
```

Replace the values with your actual name and the email address you used (or will use) for your GitHub/Gitea account. Mismatched emails break contribution graphs on hosting platforms.

**Your default editor** — opened whenever Git needs you to write a message (merge commits, interactive rebase instructions, etc.):

```bash
# Use nano (beginner-friendly, always present on Linux)
git config --global core.editor nano

# Use VS Code (requires "code" to be in your PATH)
git config --global core.editor "code --wait"

# Use Vim
git config --global core.editor vim
```

**Default branch name** — Git 2.28 and later let you set the name used when you run `git init`. The industry standard is `main`:

```bash
git config --global init.defaultBranch main
```

**Verify your configuration** by reading the file Git wrote:

```bash
git config --global --list
```

Expected output:

```
user.name=Your Full Name
user.email=you@example.com
core.editor=nano
init.defaultbranch=main
```

> **Tip:** The `~/.gitconfig` file is plain text. You can also open and edit it directly with `nano ~/.gitconfig` if you prefer.

---

## Section 2: Setting Up a GitHub Account

GitHub is the world's largest Git hosting platform and the one most used in open-source and professional development. Even if you plan to run your own server (covered in Section 3), a GitHub account is useful for accessing public repositories and collaborating on open-source projects.

### 2.1 Creating an Account

1. Open [https://github.com](https://github.com) in your browser.
2. Click **Sign up** in the top-right corner.
3. Enter a username, email address, and password. The username becomes part of your public profile URL (`github.com/your-username`) and your SSH clone URLs, so choose something professional.
4. Complete the CAPTCHA verification.
5. Choose the **Free** plan — it includes unlimited public and private repositories, unlimited collaborators on public repos, and generous Actions minutes.
6. Verify your email address by clicking the link GitHub sends to your inbox.

### 2.2 Configuring Your Profile

A complete profile helps collaborators and employers find and trust your work:

1. Click your profile picture (top-right) then **Settings**.
2. Fill in **Name**, **Bio**, and **Location** under the **Public profile** section.
3. Upload a profile picture — projects and pull requests show your avatar.
4. Click **Save profile**.

### 2.3 Enabling Two-Factor Authentication (2FA)

GitHub requires 2FA for all accounts that contribute to code. Enabling it immediately protects your account and prevents lockout notices later.

1. Go to **Settings → Password and authentication**.
2. Scroll to **Two-factor authentication** and click **Enable two-factor authentication**.
3. Choose an authentication method:
   - **Authenticator app** (recommended) — use any TOTP app such as Aegis (Android/Linux), Bitwarden, or Google Authenticator. Scan the QR code and enter the six-digit code to confirm.
   - **SMS** — less secure, not recommended for development accounts.
4. Download and store your **recovery codes** in a secure location (a password manager is ideal). These are the only way to recover access if you lose your authenticator device.

### 2.4 Creating a Personal Access Token (PAT) for HTTPS Authentication

GitHub no longer accepts your account password for `git push` or `git pull` over HTTPS. Instead, you use a **Personal Access Token** in place of the password. GitHub offers two token types; for most individual use the **fine-grained token** is preferred because it limits the token's scope to exactly what it needs.

**Creating a fine-grained token:**

1. Go to **Settings → Developer settings → Personal access tokens → Fine-grained tokens**.
2. Click **Generate new token**.
3. Give the token a descriptive name (e.g., `laptop-git-access`).
4. Set an **Expiration** — 90 days is a reasonable default. Avoid tokens with no expiry on machines you do not fully control.
5. Under **Repository access**, select **All repositories** (or choose specific repositories if you want tighter control).
6. Under **Permissions → Repository permissions**, set **Contents** to **Read and write**. This is the minimum needed to clone, push, and pull.
7. Click **Generate token**.
8. Copy the token immediately — GitHub will only show it once. Store it in a password manager.

> **Tip:** If you need to push to GitHub Actions or manage webhooks, you will need additional permissions. For everyday `git push`/`git pull`, Contents read+write is sufficient.

**Classic token** (alternative for compatibility):

Some older tools and scripts require a classic token. Navigate to **Settings → Developer settings → Personal access tokens → Tokens (classic)**, click **Generate new token (classic)**, check the **repo** scope (full repository access), set an expiry, and click **Generate token**.

---

## Section 3: Installing Gitea on Linux or Docker

Gitea is an open-source, self-hosted Git service written in Go. It is lightweight enough to run on a Raspberry Pi and provides a GitHub-like web interface. Running your own server gives you full control over your data and is common in private companies, home labs, and air-gapped environments.

Current stable release: **Gitea 1.25.5**.

### Method A: Binary Install on Linux

This method installs Gitea as a native systemd service on any Linux distribution that uses systemd (Ubuntu, Fedora, Arch, and most others).

**Step 1: Create a dedicated system user**

Running services as a dedicated unprivileged user limits the damage if the service is ever compromised.

```bash
sudo adduser \
  --system \
  --shell /bin/bash \
  --gecos 'Gitea - Git Version Control' \
  --group \
  --disabled-password \
  --home /home/git \
  git
```

**Step 2: Create the directory structure**

```bash
sudo mkdir -p /var/lib/gitea/{custom,data,log}
sudo chown -R git:git /var/lib/gitea/
sudo chmod -R 750 /var/lib/gitea/
sudo mkdir /etc/gitea
sudo chown root:git /etc/gitea
sudo chmod 770 /etc/gitea
```

**Step 3: Download the Gitea binary**

```bash
# Download the binary for 64-bit x86 Linux
sudo wget -O /usr/local/bin/gitea \
  https://dl.gitea.com/gitea/1.25.5/gitea-1.25.5-linux-amd64

# Make it executable
sudo chmod +x /usr/local/bin/gitea

# Verify the download
gitea --version
```

Expected output:
```
Gitea version 1.25.5 built with GNU/Linux
```

> **Note:** If you are on an ARM machine (such as a Raspberry Pi 4), replace `linux-amd64` with `linux-arm64` in the download URL.

**Step 4: Create the systemd service file**

```bash
sudo nano /etc/systemd/system/gitea.service
```

Paste the following content exactly:

```ini
[Unit]
Description=Gitea (Git with a cup of tea)
After=network.target

[Service]
RestartSec=2s
Type=simple
User=git
Group=git
WorkingDirectory=/var/lib/gitea/
ExecStart=/usr/local/bin/gitea web --config /etc/gitea/app.ini
Restart=always
Environment=USER=git HOME=/home/git GITEA_WORK_DIR=/var/lib/gitea

[Install]
WantedBy=multi-user.target
```

Save and close the file (in nano: `Ctrl+O`, Enter, `Ctrl+X`).

**Step 5: Enable and start the service**

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gitea
```

Check that Gitea started correctly:

```bash
sudo systemctl status gitea
```

Expected output (look for `Active: active (running)`):

```
* gitea.service - Gitea (Git with a cup of tea)
     Loaded: loaded (/etc/systemd/system/gitea.service; enabled)
     Active: active (running) since Mon 2026-04-13 10:00:00 UTC; 5s ago
```

**Step 6: Initial web setup**

Open your browser and navigate to `http://your-server-ip:3000`. You will see the Gitea installation wizard. Key settings to configure:

- **Database type:** SQLite3 is fine for personal use or small teams. Choose PostgreSQL or MySQL for production deployments with many users.
- **Site title:** A name for your Gitea instance (e.g., `My Gitea`).
- **Repository root path:** Leave as the default `/home/git/gitea-repositories`.
- **Run as username:** `git`.
- **SSH server domain:** The IP address or hostname of your server.
- **HTTP port:** `3000` (or change if needed).
- **Base URL:** `http://your-server-ip:3000/` — use your actual domain if you have one.
- **Administrator account:** Create the first admin user during this step. Choose a strong password.

Click **Install Gitea**. The page will redirect to the login screen.

---

### Method B: Docker Compose Install

Docker Compose is the fastest way to get Gitea running, especially if Docker is already installed. It also makes upgrades and backups straightforward.

**Step 1: Install Docker and Docker Compose**

```bash
# Debian / Ubuntu
sudo apt update
sudo apt install docker.io docker-compose-plugin

# Fedora
sudo dnf install docker docker-compose-plugin

# Arch Linux
sudo pacman -S docker docker-compose

# Enable and start Docker
sudo systemctl enable --now docker

# Allow your user to run Docker without sudo (log out and back in after this)
sudo usermod -aG docker $USER
```

**Step 2: Create the project directory and compose file**

```bash
mkdir -p ~/gitea
cd ~/gitea
nano docker-compose.yml
```

Paste the following content:

```yaml
networks:
  gitea:
    external: false

services:
  server:
    image: docker.gitea.com/gitea:1.25.5
    container_name: gitea
    environment:
      - USER_UID=1000
      - USER_GID=1000
    restart: always
    networks:
      - gitea
    volumes:
      - ./gitea:/data
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
    ports:
      - "3000:3000"
      - "222:22"
```

Save and close the file.

> **Note:** Port `222` on the host maps to port `22` inside the container for SSH access. This avoids conflicts with your system's own SSH server. When cloning over SSH you will use port `222` (e.g., `ssh://git@your-server:222/user/repo.git`).

**Step 3: Start Gitea**

```bash
docker compose up -d
```

Expected output:
```
[+] Running 2/2
 * Network gitea_gitea  Created
 * Container gitea       Started
```

Check logs to confirm Gitea started cleanly:

```bash
docker compose logs -f server
```

Look for a line like `Listen: http://0.0.0.0:3000`. Press `Ctrl+C` to stop following logs.

**Step 4: Initial web setup**

Navigate to `http://your-server-ip:3000` and complete the same web installer described in Method A, Step 6. The only difference is the repository root path, which inside the container is `/data/gitea/repositories`.

To stop or restart Gitea:

```bash
# Stop
docker compose down

# Restart
docker compose up -d
```

---

### 3.3 Key app.ini Configuration Highlights

After the initial setup wizard runs, Gitea writes its configuration to `/etc/gitea/app.ini` (binary install) or `./gitea/gitea/conf/app.ini` (Docker Compose, inside the `./gitea` data volume). You can edit this file directly to tune behavior. Always restart Gitea after editing it.

The file uses an INI-style format with named sections in square brackets:

```ini
[server]
; The domain users type in their browser
DOMAIN        = your-server-ip
; The full URL including port, used in clone URLs and emails
ROOT_URL      = http://your-server-ip:3000/
; Port Gitea listens on
HTTP_PORT     = 3000
; SSH port reported in clone URLs (222 if using Docker, 22 if binary install)
SSH_PORT      = 22

[repository]
; Default branch for new repositories
DEFAULT_BRANCH = main

[security]
; Set to true after installation to disable the web setup page
INSTALL_LOCK   = true
; Minimum password length for new user accounts
MIN_PASSWORD_LENGTH = 12

[service]
; When true, only admins can create accounts (good for private servers)
DISABLE_REGISTRATION = false
; Require email verification for new accounts
REGISTER_EMAIL_CONFIRM = false
```

> **Tip:** You can override any `app.ini` setting in the Docker Compose environment without editing the file. The format is `GITEA__section__KEY=value`. For example, to disable registration: add `- GITEA__service__DISABLE_REGISTRATION=true` under the `environment:` key in `docker-compose.yml`, then run `docker compose up -d`.

---

## Section 4: Connecting to a Git Server

### 4.1 Generating an SSH Key Pair

SSH authentication uses a **key pair**: a private key that stays on your machine and a public key that you upload to GitHub or Gitea. When you connect, the server challenges your client to prove it holds the private key without ever transmitting it.

The **ed25519** algorithm is recommended: it produces smaller keys than RSA, is faster to compute, and is considered more secure.

```bash
# Generate the key pair
# Replace the email with the one on your GitHub/Gitea account
ssh-keygen -t ed25519 -C "you@example.com"
```

You will see three prompts:

```
Generating public/private ed25519 key pair.
Enter file in which to save the key (/home/you/.ssh/id_ed25519):
```

Press **Enter** to accept the default path unless you have a specific reason to change it.

```
Enter passphrase (empty for no passphrase):
```

Enter a strong passphrase. This encrypts the private key on disk — if someone copies your `~/.ssh/id_ed25519` file, they cannot use it without this passphrase. Press **Enter** again to confirm.

```
Your identification has been saved in /home/you/.ssh/id_ed25519
Your public key has been saved in /home/you/.ssh/id_ed25519.pub
The key fingerprint is:
SHA256:abc123xyz... you@example.com
```

Two files now exist in `~/.ssh/`:

| File | Contents | Share it? |
|---|---|---|
| `id_ed25519` | **Private key** — never share this | No — keep it secret |
| `id_ed25519.pub` | **Public key** — upload this to servers | Yes |

### 4.2 Starting the SSH Agent and Loading Your Key

The SSH agent holds your decrypted private key in memory so you only need to enter the passphrase once per session rather than on every connection.

```bash
# Start the agent (outputs the shell commands to configure your session)
eval "$(ssh-agent -s)"

# Add your key to the agent
ssh-add ~/.ssh/id_ed25519
```

You will be prompted for the passphrase once. After that, all SSH operations in this terminal session will authenticate automatically.

To make the agent start automatically in every new shell session, add both lines to your `~/.bashrc` or `~/.bash_profile`:

```bash
# Add to ~/.bashrc so the agent starts automatically
echo 'eval "$(ssh-agent -s)" > /dev/null' >> ~/.bashrc
echo 'ssh-add ~/.ssh/id_ed25519 2>/dev/null' >> ~/.bashrc
```

### 4.3 Viewing Your Public Key

To copy your public key, display it with:

```bash
cat ~/.ssh/id_ed25519.pub
```

The output will look like:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... you@example.com
```

Select and copy the entire line — from `ssh-ed25519` through your email address, with no trailing newline.

### 4.4 Adding Your SSH Key to GitHub

1. Go to [https://github.com/settings/keys](https://github.com/settings/keys) (or navigate: **Settings → SSH and GPG keys**).
2. Click **New SSH key**.
3. In the **Title** field, enter a recognisable label for this machine (e.g., `Ubuntu Laptop`).
4. Leave **Key type** as **Authentication Key**.
5. Paste the contents of `~/.ssh/id_ed25519.pub` into the **Key** field.
6. Click **Add SSH key** and confirm with your GitHub password or 2FA prompt.

**Test the connection:**

```bash
ssh -T git@github.com
```

Expected output (first connection will ask you to confirm the host fingerprint — type `yes`):

```
Hi your-username! You've successfully authenticated, but GitHub does not provide shell access.
```

If you see `Permission denied (publickey)`, re-check that you pasted the `.pub` file contents (not the private key) and that the ssh-agent is running.

### 4.5 Adding Your SSH Key to Gitea

1. Log in to your Gitea instance and click your avatar in the top-right corner, then **Settings**.
2. In the left sidebar, click **SSH / GPG Keys**.
3. Click **Add Key**.
4. Enter a **Key Name** (e.g., `Ubuntu Laptop`).
5. Paste the contents of `~/.ssh/id_ed25519.pub` into the **Content** field.
6. Click **Add Key**.

**Test the connection (binary install — default port 22):**

```bash
ssh -T git@your-gitea-server-ip
```

**Test the connection (Docker Compose install — port 222):**

```bash
ssh -T git@your-gitea-server-ip -p 222
```

Expected output:

```
Hi your-username! You've successfully authenticated with key named Ubuntu Laptop, but Gitea does not provide shell access.
```

**Simplify Docker SSH with a config alias:**

If your Gitea runs on a non-standard port, add a Host entry to `~/.ssh/config` so you never have to type `-p 222` again:

```bash
nano ~/.ssh/config
```

Add the following (replace `your-gitea-server-ip` with your actual IP or hostname):

```
Host gitea
    HostName your-gitea-server-ip
    User git
    Port 222
    IdentityFile ~/.ssh/id_ed25519
```

After saving, you can test with:

```bash
ssh -T gitea
```

And clone using:

```bash
git clone gitea:username/repo.git
```

### 4.6 Configuring HTTPS with a Credential Helper

When you use HTTPS clone URLs, Git will ask for your username and password (PAT) on every network operation unless you configure a credential helper to remember it.

**Option 1: cache (stores in memory, best for shared machines)**

Credentials are held in RAM and forgotten after the timeout expires (default: 15 minutes). Nothing is ever written to disk.

```bash
# Remember credentials for 8 hours (28800 seconds)
git config --global credential.helper 'cache --timeout=28800'
```

**Option 2: store (stores in a plain-text file, convenient but less secure)**

Credentials are saved to `~/.git-credentials` and never expire. Only use this on a machine you fully trust and control.

```bash
git config --global credential.helper store
```

**Option 3: Git Credential Manager (GCM, recommended for desktop machines)**

GCM integrates with your system's secure keychain (or prompts via a GUI) and is the most secure option for a personal Linux workstation.

```bash
# Download and install GCM (check https://github.com/git-ecosystem/git-credential-manager/releases for latest)
wget https://github.com/git-ecosystem/git-credential-manager/releases/latest/download/gcm-linux_amd64.deb
sudo dpkg -i gcm-linux_amd64.deb

# Configure Git to use GCM
git credential-manager configure
```

> **Note:** GCM requires a credential store backend on Linux. After installation it will guide you through selecting `secretservice` (GNOME Keyring), `gpg` (GPG + pass), or `plaintext` depending on your desktop environment.

**Using your PAT the first time:**

After configuring any helper, the first time you run a HTTPS `git push` or `git pull`, Git will prompt for your credentials. Enter your GitHub username and paste your PAT as the password. The helper saves the credentials so subsequent operations proceed without prompting.

```bash
# Example first push — Git will prompt for username and PAT
git push origin main

Username for 'https://github.com': your-username
Password for 'https://your-username@github.com': [paste your PAT here]
```

All future pushes and pulls will authenticate silently.

### 4.7 Cloning a Repository

Once authentication is configured, cloning works identically regardless of the hosting platform.

**Clone via SSH (GitHub):**

```bash
git clone git@github.com:username/repository-name.git
```

**Clone via HTTPS (GitHub):**

```bash
git clone https://github.com/username/repository-name.git
```

**Clone via SSH (Gitea, binary install):**

```bash
git clone git@your-gitea-ip:username/repository-name.git
```

**Clone via SSH (Gitea, Docker Compose with port 222, using the ssh config alias):**

```bash
git clone gitea:username/repository-name.git
```

**Clone via HTTPS (Gitea):**

```bash
git clone http://your-gitea-ip:3000/username/repository-name.git
```

**Clone into a specific directory:**

```bash
git clone git@github.com:username/repository-name.git my-local-folder-name
```

After cloning, Git automatically creates a remote named `origin` pointing back to the source URL:

```bash
cd repository-name
git remote -v
```

Expected output:

```
origin  git@github.com:username/repository-name.git (fetch)
origin  git@github.com:username/repository-name.git (push)
```

---

## Best Practices

1. **Set `user.name` and `user.email` globally before your very first commit.** These values are embedded in every commit you author and cannot be changed after pushing without rewriting history. Use the same email as your hosting account so contribution graphs display correctly.

2. **Use a passphrase on your SSH private key.** A key file without a passphrase is a single point of failure — anyone who copies the file gains complete access to every server where the public key is registered. The ssh-agent means you only type the passphrase once per session.

3. **Store PATs in a password manager, never in a text file or shell history.** Tokens that appear in your bash history or a Notes app are frequently leaked through accidental screen shares, repository commits, or device theft.

4. **Set a PAT expiry date.** GitHub allows tokens without expiry, but a token that never expires is a persistent security risk. Set a 90-day expiry and add a calendar reminder to rotate it.

5. **Use fine-grained tokens with the minimum necessary permissions.** A token with only Contents read+write cannot be used to delete your account, modify settings, or create new repositories. Limiting scope reduces the blast radius if a token is ever leaked.

6. **Lock down your Gitea instance before exposing it to the internet.** Set `DISABLE_REGISTRATION = true` in `app.ini` if you do not want strangers to create accounts, and configure `INSTALL_LOCK = true` after the initial setup to prevent the installer from being re-run.

7. **Prefer SSH for machines you own and HTTPS for everything else.** SSH keys are machine-bound by design; a key on your laptop cannot authenticate from your colleague's machine. HTTPS with GCM works better when you need to authenticate on multiple machines using a single token.

8. **Keep Git up to date.** Security patches and protocol improvements are released regularly. Use the git-core PPA (Ubuntu), `dnf upgrade git` (Fedora), or `pacman -Syu git` (Arch) periodically.

---

## Use Cases

### Use Case 1: A Developer's First Machine Setup

A new developer joins a team that uses GitHub for code hosting. They have a fresh Ubuntu 24.04 laptop and need to be fully configured and able to push code by the end of their first day.

- **Problem:** No Git is installed, no GitHub account exists, and the company's firewall blocks outbound SSH on port 22.
- **Concepts applied:** `apt install git`, global config, GitHub account creation + 2FA, PAT creation, HTTPS credential helper (GCM), HTTPS clone
- **Expected outcome:** Git installed and configured with identity, credentials cached via GCM, able to clone and push to the team repository over HTTPS without password prompts.

### Use Case 2: A Solo Developer Building a Home Lab

A developer runs a Raspberry Pi 4 at home and wants a private Git server for personal projects without paying for a private repository plan.

- **Problem:** Public cloud hosting has privacy implications and costs money for certain features; the developer wants complete control.
- **Concepts applied:** Gitea binary install on ARM64 Linux, systemd service, SSH key pair generation, Gitea SSH key registration, SSH clone
- **Expected outcome:** Gitea running on the Pi as a systemd service, accessible at `http://raspberrypi.local:3000`, with SSH authentication configured so `git push` works from the developer's laptop.

### Use Case 3: A Team Adding a Self-Hosted CI/CD Server

A small team wants a self-hosted Gitea instance running alongside their existing Docker infrastructure so they can wire it up to a local runner.

- **Problem:** Manual setup and upgrades of a Git server are fragile; they need a reproducible, easily-updated deployment.
- **Concepts applied:** Docker Compose Gitea install, environment variable configuration overrides, Docker volume management, SSH port remapping
- **Expected outcome:** Gitea running in a Docker container with data persisted in a named volume, easily upgraded by changing the image tag and running `docker compose up -d`, SSH access working on port 222.

---

## Hands-on Examples

### Example 1: Install Git and Configure Your Identity

This example walks through a complete first-time Git installation on Ubuntu, confirming each step before moving on.

1. Open a terminal and update your package list.

```bash
sudo apt update
```

2. Install Git.

```bash
sudo apt install git
```

3. Confirm Git installed successfully.

```bash
git --version
```

Expected output:
```
git version 2.43.0
```

4. Set your identity globally.

```bash
git config --global user.name "Alex Rivera"
git config --global user.email "alex@example.com"
git config --global core.editor nano
git config --global init.defaultBranch main
```

5. Verify all four settings were saved.

```bash
git config --global --list
```

Expected output:
```
user.name=Alex Rivera
user.email=alex@example.com
core.editor=nano
init.defaultbranch=main
```

6. Check where Git stored this configuration.

```bash
cat ~/.gitconfig
```

Expected output:
```
[user]
        name = Alex Rivera
        email = alex@example.com
[core]
        editor = nano
[init]
        defaultBranch = main
```

---

### Example 2: Generate an SSH Key and Connect to GitHub

This example generates a new ed25519 key, adds it to GitHub, and tests the connection.

1. Generate the key pair.

```bash
ssh-keygen -t ed25519 -C "alex@example.com"
```

Accept the default file path by pressing **Enter**. Enter a passphrase when prompted.

2. Start the SSH agent and load the key.

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

Enter your passphrase when prompted. Output:
```
Identity added: /home/alex/.ssh/id_ed25519 (alex@example.com)
```

3. Display the public key.

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the entire line of output.

4. In your browser, go to [https://github.com/settings/keys](https://github.com/settings/keys), click **New SSH key**, paste the public key, give it the title `Ubuntu Workstation`, and click **Add SSH key**.

5. Test the GitHub SSH connection.

```bash
ssh -T git@github.com
```

Type `yes` to accept GitHub's host fingerprint on the first connection.

Expected output:
```
Hi alex-rivera! You've successfully authenticated, but GitHub does not provide shell access.
```

6. Clone a repository using SSH to confirm everything works end-to-end.

```bash
git clone git@github.com:octocat/Hello-World.git
cd Hello-World
git log --oneline -3
```

Expected output (commit hashes will differ):
```
7fd1a60 Merge pull request #6 from Spaceghost/patch-1
553c207 Merge branch 'master' of github.com:octocat/Hello-World
b6568db Create styles.css and updated README
```

---

### Example 3: Deploy Gitea with Docker Compose and Test SSH Access

This example launches a local Gitea instance, creates an admin account, registers an SSH key, and clones from it.

1. Create the project directory.

```bash
mkdir -p ~/gitea
cd ~/gitea
```

2. Create the `docker-compose.yml` file.

```bash
cat > docker-compose.yml << 'EOF'
networks:
  gitea:
    external: false

services:
  server:
    image: docker.gitea.com/gitea:1.25.5
    container_name: gitea
    environment:
      - USER_UID=1000
      - USER_GID=1000
    restart: always
    networks:
      - gitea
    volumes:
      - ./gitea:/data
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
    ports:
      - "3000:3000"
      - "222:22"
EOF
```

3. Start Gitea.

```bash
docker compose up -d
```

4. Follow the logs until Gitea is ready (look for `Listen: http://0.0.0.0:3000`, then press `Ctrl+C`).

```bash
docker compose logs -f server
```

5. Open `http://localhost:3000` in your browser. Complete the installation wizard:
   - Database: SQLite3
   - Site title: My Gitea
   - SSH port: 22 (Gitea's internal port)
   - HTTP port: 3000
   - Base URL: `http://localhost:3000/`
   - Create an administrator account: username `gitea-admin`, strong password

6. Click **Install Gitea** and log in.

7. Add your SSH public key to Gitea: click your avatar → **Settings → SSH / GPG Keys → Add Key**. Paste the contents of `~/.ssh/id_ed25519.pub` and click **Add Key**.

8. Create a test repository: click the **+** icon → **New Repository**. Name it `test-repo`, check **Initialize this repository**, click **Create Repository**.

9. Test SSH access (note port 222 on the host):

```bash
ssh -T git@localhost -p 222
```

Expected output:
```
Hi gitea-admin! You've successfully authenticated with key named Ubuntu Workstation, but Gitea does not provide shell access.
```

10. Add an SSH config alias for convenience.

```bash
cat >> ~/.ssh/config << 'EOF'

Host gitea-local
    HostName localhost
    User git
    Port 222
    IdentityFile ~/.ssh/id_ed25519
EOF
```

11. Clone the test repository using the alias.

```bash
cd ~
git clone gitea-local:gitea-admin/test-repo.git
cd test-repo
ls
```

Expected output:
```
README.md
```

---

### Example 4: Configure HTTPS with a PAT and the cache Credential Helper

This example demonstrates authenticating over HTTPS using a GitHub PAT and storing it with the cache helper.

1. Configure the credential cache for 8 hours.

```bash
git config --global credential.helper 'cache --timeout=28800'
```

2. Clone a private repository (or any repository you have write access to) over HTTPS.

```bash
git clone https://github.com/your-username/your-private-repo.git
```

3. When prompted, enter your GitHub username and paste your PAT as the password.

```
Username for 'https://github.com': your-username
Password for 'https://your-username@github.com': ghp_xxxxxxxxxxxxxxxxxxxx
```

4. Make a small change and push it to confirm credentials are cached.

```bash
cd your-private-repo
echo "# test" >> README.md
git add README.md
git commit -m "Test HTTPS push with cached credentials"
git push origin main
```

Expected output (no credential prompt this time):
```
Enumerating objects: 5, done.
Writing objects: 100% (3/3), 289 bytes | 289.00 KiB/s, done.
To https://github.com/your-username/your-private-repo.git
   abc1234..def5678  main -> main
```

---

## Common Pitfalls

### Pitfall 1: Using Your GitHub Account Password Instead of a PAT

**Description:** A developer tries to `git push` over HTTPS using their GitHub login password and receives an authentication failure.

**Why it happens:** GitHub removed password authentication for Git operations in August 2021. The error message is not always clear about what is needed instead.

**Incorrect pattern:**
```bash
git push origin main
Username for 'https://github.com': your-username
Password for 'https://your-username@github.com': [account password]
# Error: remote: Support for password authentication was removed.
```

**Correct pattern:**
```bash
# Use your PAT (starts with ghp_ for classic or github_pat_ for fine-grained)
git push origin main
Username for 'https://github.com': your-username
Password for 'https://your-username@github.com': ghp_yourpersonalaccesstoken
```

---

### Pitfall 2: Uploading the Private Key Instead of the Public Key

**Description:** A developer copies the wrong file — `id_ed25519` instead of `id_ed25519.pub` — and pastes it into GitHub or Gitea's SSH key field.

**Why it happens:** Both files have similar names and both contain what looks like a block of random text. The private key does not include `.pub` in its name, which is easy to overlook.

**How to identify the mistake:**
```bash
# The PUBLIC key starts with "ssh-ed25519" — safe to share
cat ~/.ssh/id_ed25519.pub
# Output: ssh-ed25519 AAAA... your@email.com

# The PRIVATE key starts with "-----BEGIN OPENSSH PRIVATE KEY-----" — NEVER share this
cat ~/.ssh/id_ed25519
# Output: -----BEGIN OPENSSH PRIVATE KEY-----
```

**Correct pattern:** Always copy the output of `cat ~/.ssh/id_ed25519.pub` (with the `.pub` extension) into any web form.

---

### Pitfall 3: SSH Connection Refused Because the Agent Is Not Running

**Description:** A developer generates a key with a passphrase, adds the public key to GitHub, but `git push` still prompts for the passphrase on every operation — or fails entirely with `Agent admitted failure to sign using the key`.

**Why it happens:** Without the ssh-agent, SSH must decrypt the private key on disk every time. If the key was generated with a passphrase, this prompts every operation.

**Incorrect pattern:**
```bash
# Key generated but agent not started
git push origin main
# Prompts for passphrase on every single push
```

**Correct pattern:**
```bash
# Start the agent and add the key once per session
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
# Enter passphrase once
git push origin main
# No further prompts
```

---

### Pitfall 4: Gitea Docker SSH on the Wrong Port

**Description:** After setting up Gitea with Docker Compose, a developer tries to clone with `git@localhost:username/repo.git` and gets `Connection refused`.

**Why it happens:** The Docker Compose configuration maps port `222` on the host to port `22` inside the container. The standard SSH port `22` on the host belongs to the system's own SSH server, not Gitea.

**Incorrect pattern:**
```bash
git clone git@localhost:gitea-admin/test-repo.git
# ssh: connect to host localhost port 22: Connection refused
```

**Correct pattern:**
```bash
# Specify port 222 explicitly
git clone ssh://git@localhost:222/gitea-admin/test-repo.git

# Or use an SSH config alias (recommended)
# In ~/.ssh/config:
# Host gitea-local
#     HostName localhost
#     Port 222
#     User git
git clone gitea-local:gitea-admin/test-repo.git
```

---

### Pitfall 5: Global Config Not Set, Leading to Anonymous or Wrong Commits

**Description:** A developer installs Git and starts committing without running `git config --global user.name` and `git config --global user.email`. Commits are attributed to the system username or a previous user's identity.

**Why it happens:** Git does not enforce identity configuration before the first commit. On shared machines or fresh installs, the fallback identity is often wrong.

**Incorrect pattern:**
```bash
git init
git add .
git commit -m "Initial commit"
# Commit author: root <root@hostname> (or whatever the system default is)
```

**Correct pattern:**
```bash
# Always run these before any commits on a new machine
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git commit -m "Initial commit"
# Commit author: Your Name <you@example.com>
```

Verify your identity is set correctly with:
```bash
git config --global user.name
git config --global user.email
```

---

### Pitfall 6: PAT Expired, Causing Silent Authentication Failures

**Description:** A developer sets a 90-day PAT expiry and forgets to rotate it. After the expiry date, `git push` starts failing with authentication errors and the developer cannot identify why — the credentials are still cached.

**Why it happens:** The credential cache or store holds the expired token. Git sees cached credentials and tries them, but the server rejects them. The error message says authentication failed, not that the token expired.

**Incorrect pattern:**
```bash
git push origin main
# remote: Invalid credentials.
# fatal: Authentication failed for 'https://github.com/...'
# (Developer spends time debugging — token was cached and is now expired)
```

**Correct pattern:**
```bash
# 1. Clear the cached credentials
git credential reject <<EOF
protocol=https
host=github.com
EOF

# 2. Generate a new PAT on GitHub
# 3. Push again — Git will prompt for the new token
git push origin main

# 4. Set a calendar reminder before the new token expires
```

---

## Summary

- Install Git with `apt install git`, `dnf install git`, or `pacman -S git` depending on your Linux distribution, then verify with `git --version`. Use the git-core PPA on Ubuntu for the latest stable release.
- Run `git config --global` to set your name, email, editor, and default branch name before making any commits — these values are baked into every commit you author.
- GitHub accounts require email verification and 2FA. Use a fine-grained Personal Access Token (PAT) with Contents read+write permission in place of your account password for HTTPS Git operations.
- Gitea can be deployed as a native Linux binary managed by systemd, or as a Docker Compose service. Both approaches produce a web-accessible Git server on port 3000 with an SSH endpoint. Docker Compose maps host port 222 to container port 22.
- SSH authentication uses an ed25519 key pair: the private key stays on your machine; the public key (`.pub` file) is uploaded to GitHub or Gitea. The ssh-agent eliminates per-operation passphrase prompts.
- Credential helpers (`cache`, `store`, or GCM) save your PAT so HTTPS operations do not prompt repeatedly. Use `cache` on shared machines and GCM or `store` on machines you fully control.
- Prefer SSH for machines you own; prefer HTTPS when SSH port 22 is blocked or you are on a temporary machine.

---

## Further Reading

- [Git Official Download for Linux — git-scm.com](https://git-scm.com/download/linux) — The official installation page listing the canonical package manager commands for every major Linux distribution; use this to verify commands for distributions not covered in this module.
- [Pro Git Book, Chapter 1: Getting Started — git-scm.com](https://git-scm.com/book/en/v2/Getting-Started-About-Version-Control) — The authoritative free book written by Git contributors; chapters 1 and 8 cover initial setup and Git configuration in depth, expanding on every `git config` command in this module.
- [Generating a New SSH Key — GitHub Docs](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent) — GitHub's official, always-current instructions for SSH key generation across Linux, macOS, and Windows; includes notes on hardware security key support (FIDO2/WebAuthn).
- [Managing Personal Access Tokens — GitHub Docs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) — Comprehensive reference for fine-grained and classic PATs: creation, permission scopes, rotation, auditing, and revocation procedures.
- [Installation from Binary — Gitea Documentation](https://docs.gitea.com/installation/install-from-binary) — The official Gitea binary install guide with architecture-specific download URLs, directory layout requirements, and a link to the sample systemd service file in the Gitea GitHub repository.
- [Installation with Docker — Gitea Documentation](https://docs.gitea.com/installation/install-with-docker) — Gitea's Docker Compose reference including database integration (MySQL, PostgreSQL), environment variable overrides for app.ini settings, and upgrade procedures.
- [Git Credential Storage — Pro Git Book](https://git-scm.com/book/en/v2/Git-Tools-Credential-Storage) — In-depth explanation of how the cache, store, and platform-native credential helpers work internally, including how to build a custom helper; directly extends Section 4.6 of this module.
- [Git Credential Manager Releases — GitHub](https://github.com/git-ecosystem/git-credential-manager/releases/latest) — Download page for the cross-platform GCM binary; the README covers Linux-specific setup for GNOME Keyring, GPG/pass, and headless environments.
