# Module 1: Linux Basics
> Subject: Linux | Difficulty: Beginner | Estimated Time: 135 minutes

## Objective

After completing this module, you will be able to navigate the Linux filesystem hierarchy and explain why key directories matter for AI server administration, locate and manipulate files using `cd`, `ls`, `pwd`, `find`, `cp`, `mv`, `rm`, and `mkdir`, create and manage user accounts and groups with `useradd`, `usermod`, `passwd`, and `sudo`, read and modify file permissions using symbolic (`rwx`) and octet notation with `chmod` and `chown`, install and remove software packages using `apt` and `apt-get`, and perform basic file editing with both `nano` and `vim`. Every skill is framed against the concrete context of managing a Linux server that runs AI workloads.

## Prerequisites

- A Linux environment to follow along: Ubuntu 22.04 LTS or Ubuntu 24.04 LTS on a real or virtual machine, WSL 2 on Windows, or any cloud VM (AWS EC2, GCP Compute Engine, Azure VM) running Ubuntu. The commands in this module are verified against Ubuntu 22.04 LTS and Ubuntu 24.04 LTS.
- No prior Linux experience is assumed. If you have used a terminal on macOS or Windows you will find the concepts familiar, but no prior knowledge is required.
- An understanding of what a file and a directory are at a conceptual level.

## Key Concepts

### The Linux Filesystem Hierarchy

Linux organizes every file — whether it is a program, a configuration file, a hardware device, or a running process — into a single tree rooted at `/`. There are no drive letters like `C:\` or `D:\`. Everything starts at `/`. This layout is standardized across distributions by the Filesystem Hierarchy Standard (FHS).

The directories you will interact with most often when managing an AI server are:

| Directory | Purpose | AI Server Relevance |
|---|---|---|
| `/` | Root of the entire tree | All paths start here |
| `/home` | One subdirectory per user (e.g., `/home/alice`) | Where developers store project code |
| `/root` | Home directory of the `root` superuser | Separate from `/home`; root's personal space |
| `/etc` | System-wide configuration files | Model service config files live here (e.g., `/etc/systemd/system/`) |
| `/var` | Variable data: logs, databases, spool files | Application logs (`/var/log`), runtime data for services |
| `/tmp` | Temporary files; cleared on reboot | Scratch space for short-lived inference outputs |
| `/usr` | Installed programs and libraries | Python, pip packages, CUDA utilities |
| `/usr/local` | Locally compiled/installed programs | Custom builds of frameworks (PyTorch, llama.cpp) |
| `/opt` | Optional, self-contained third-party packages | Nvidia drivers, vendor AI SDKs |
| `/srv` | Data served by services (FTP, HTTP) | Model weights served by an API are sometimes placed here |
| `/dev` | Device files (disk, GPU, keyboard) | GPU devices appear as `/dev/nvidia0`, `/dev/nvidia1`, etc. |
| `/proc` | Virtual filesystem exposing kernel state | Inspect GPU memory via `/proc/driver/nvidia/` |
| `/bin`, `/sbin` | Essential user and system binaries | Core commands like `ls`, `cp` |
| `/lib`, `/lib64` | Shared libraries needed by binaries | CUDA runtime libraries (.so files) |

When you store large model weights, choose a path deliberately. A 70 billion-parameter model file might be 40 GB. Placing it in `/tmp` means it disappears on reboot. Placing it in `/home/youruser` means it is only accessible to that user. A dedicated directory like `/opt/models/` with appropriate ownership is the correct pattern.

```
/
├── etc/          ← service configuration
├── home/
│   └── alice/    ← developer workspace
├── opt/
│   └── models/   ← model weights (production pattern)
├── var/
│   └── log/      ← application logs
└── usr/
    └── local/
        └── bin/  ← custom installed binaries
```

### Navigating the Filesystem

Four commands form the core of filesystem navigation. You will run these dozens of times per session.

**`pwd` — print working directory.** Shows your current location as an absolute path (a path starting from `/`). Always run this when disoriented.

```bash
pwd
# Output: /home/alice
```

**`cd` — change directory.** Moves you to another directory. Accepts absolute paths (start with `/`) or relative paths (start from your current location, no leading `/`).

```bash
# Absolute path: works from anywhere
cd /opt/models

# Relative path: from /home/alice, moves into projects/
cd projects/llm-server

# Go up one level (to the parent directory)
cd ..

# Go up two levels
cd ../..

# Return to your home directory (shorthand)
cd ~

# Return to the previous directory you were in
cd -
```

**`ls` — list directory contents.** The flags you will use constantly:

```bash
# Basic listing of current directory
ls

# Long format: permissions, owner, size, date, name
ls -l

# Long format, including hidden files (names starting with .)
ls -la

# Long format with human-readable file sizes (K, M, G)
ls -lh

# Long format, sorted by modification time (newest first)
ls -lt

# List a specific directory without navigating into it
ls -lh /opt/models/

# Combine flags: long, all hidden, human-readable, sorted by time
ls -laht /var/log/
```

Hidden files in Linux are simply files whose name starts with a dot (`.`). Your shell configuration (`~/.bashrc`), SSH keys (`~/.ssh/`), and Python virtual environment markers all follow this convention.

**`find` — search for files and directories.** `find` walks the filesystem tree from a starting point and tests each entry against criteria you specify. It is the right tool for locating a 40 GB model weight that was saved to the wrong directory, or for auditing which files a service account owns.

```bash
# Find all .pt (PyTorch) files under /opt/models
find /opt/models -name "*.pt"

# Find files larger than 1 GB (useful for locating model weights)
find /opt/models -type f -size +1G

# Find files owned by a specific user
find /opt/models -type f -user aiservice

# Find directories (not files) named "checkpoints"
find /home -type d -name "checkpoints"

# Find files modified in the last 24 hours
find /var/log -type f -mtime -1

# Find files and print their size in human-readable form
find /opt/models -type f -size +100M -exec ls -lh {} \;
```

The `-type f` flag means "regular files only" and `-type d` means "directories only". Omitting `-type` matches both.

### File and Directory Manipulation

These commands let you create, copy, move, rename, and delete files and directories. On an AI server you will use them to organize model files, rotate logs, and set up directory structures for new projects.

**`mkdir` — make directory.**

```bash
# Create a single directory
mkdir /opt/models

# Create a path of nested directories in one command (-p = parents)
mkdir -p /opt/models/llama3/70b/quantized

# Create multiple directories at once
mkdir -p /srv/ai-api/{logs,config,weights}
```

The `-p` flag is essential: without it, `mkdir /opt/models/llama3` fails if `/opt/models` does not already exist.

**`cp` — copy files and directories.**

```bash
# Copy a single file
cp model-config.json /opt/models/llama3/

# Copy a file and give it a new name at the destination
cp model-config.json /opt/models/llama3/model-config.backup.json

# Copy a directory and all its contents recursively (-r)
cp -r /opt/models/llama3 /opt/models/llama3-backup

# Preserve file metadata (timestamps, permissions, owner) when copying (-a = archive)
cp -a /opt/models/llama3 /backup/models/llama3
```

Always use `-a` (archive) rather than `-r` when copying model directories to a backup location — it preserves the ownership and permission bits that your service account depends on.

**`mv` — move or rename files and directories.**

```bash
# Move a file to a different directory
mv llama3-70b.gguf /opt/models/llama3/70b/

# Rename a file (mv within the same directory)
mv model_weights_v1.pt model_weights_v2.pt

# Move an entire directory
mv /tmp/downloaded-weights /opt/models/mistral-7b
```

`mv` does not need a `-r` flag to handle directories.

**`rm` — remove files and directories.**

```bash
# Remove a single file
rm old-checkpoint.pt

# Remove multiple files
rm checkpoint-1.pt checkpoint-2.pt checkpoint-3.pt

# Remove a directory and all its contents recursively (-r)
rm -r /opt/models/old-experiment/

# Prompt for confirmation before each deletion (-i = interactive)
rm -i critical-config.json

# Force removal without prompts (-f) — use with extreme caution
rm -rf /opt/models/experiment-to-discard/
```

The combination `rm -rf` is permanently destructive and irreversible. Linux has no Recycle Bin. Before running `rm -rf`, double-check the path with `ls` and `pwd`. A misplaced space in `rm -rf /opt /models` becomes `rm -rf /opt` followed by `/models` — deleting the entire `/opt` directory.

### Users, Groups, and Service Accounts

Linux is a multi-user operating system. Every process runs as a specific user, and every file is owned by a user and a group. On an AI server this matters for two reasons: security isolation (your model inference service should not run as root) and access control (your model weights should be readable only by the service that needs them).

**The root user.** The user with UID (user ID) 0 is `root`, the superuser. `root` can read, write, and execute any file on the system, regardless of permissions. You should never run an AI service daemon as `root`. If the service is compromised, the attacker gains complete control of the machine.

**`useradd` — create a new user.** On Ubuntu the preferred command is `adduser` for interactive use, but `useradd` is universal across all Linux distributions and is better for scripting.

```bash
# Create a system account for an AI inference service
# -r = system account (no aging, UID in system range)
# -s /bin/false = no interactive login shell
# -d /opt/models = home directory
# -M = do not create home directory (we will create it manually)
sudo useradd -r -s /bin/false -d /opt/models -M aiservice

# Create a regular user account for a developer
# -m = create home directory
# -s /bin/bash = set login shell
sudo useradd -m -s /bin/bash alice

# Verify the account was created
id aiservice
# Output: uid=999(aiservice) gid=999(aiservice) groups=999(aiservice)
```

System accounts (created with `-r`) have UIDs below 1000 on most distributions and are intended for services, not humans. They typically have no login shell (`/bin/false` or `/bin/nologin`) so they cannot be used to log into the system interactively.

**`usermod` — modify an existing user account.**

```bash
# Add a user to a supplementary group (e.g., the "docker" group)
# -a = append (do not remove from other groups); -G = supplementary group
sudo usermod -aG docker alice

# Add the aiservice account to the "gpu" group so it can access /dev/nvidia*
sudo usermod -aG gpu aiservice

# Change the home directory of an existing user
sudo usermod -d /new/home/alice alice

# Lock an account to prevent login
sudo usermod -L alice

# Unlock it again
sudo usermod -U alice
```

Always use `-aG` (append + group) when adding a user to a supplementary group. Omitting `-a` replaces all supplementary groups with the one you specify, potentially removing the user from groups they need to be in.

**`passwd` — set or change a password.**

```bash
# Set your own password (no sudo needed)
passwd

# Set another user's password (requires sudo)
sudo passwd alice

# Expire a password immediately, forcing a change at next login
sudo passwd -e alice

# Lock an account by prepending ! to the password hash
sudo passwd -l alice

# Unlock the account
sudo passwd -u alice
```

Service accounts like `aiservice` should never have a password set. They authenticate through file ownership and group membership, not interactive login.

**`sudo` — run a command as another user (usually root).** `sudo` is the standard way to perform privileged operations without logging in as root directly. It records every command in `/var/log/auth.log`, providing an audit trail.

```bash
# Run a single command as root
sudo apt-get update

# Edit a root-owned file using your own editor preference
sudo nano /etc/hosts

# Open an interactive root shell (use sparingly)
sudo -i

# Run a command as a specific user (not root)
sudo -u aiservice python3 /opt/ai-api/run.py

# Check what sudo permissions your account has
sudo -l
```

**Groups.** Groups are named collections of users. A file's group ownership determines which users get "group" permissions on it. When you have model weights that three inference services all need to read, you create a group, add all three service accounts to it, and set the group ownership of the weights directory to that group.

```bash
# Create a new group for AI service accounts
sudo groupadd aiservices

# List all groups on the system
cat /etc/group

# Show which groups a user belongs to
groups alice
# Output: alice : alice sudo docker

# Show the same information with UIDs and GIDs
id alice
# Output: uid=1001(alice) gid=1001(alice) groups=1001(alice),27(sudo),999(docker)
```

### File Permissions

Every file and directory on Linux has three permission sets: one for the **owner (user)**, one for the **group**, and one for **everyone else (other)**. Each set has three bits: **read (r)**, **write (w)**, and **execute (x)**.

When you run `ls -l`, the first column shows the permission string:

```
-rwxr-xr--  1  aiservice  aiservices  4096  Apr 10 2026  run_inference.py
```

Breaking this down:

```
- rwx r-x r--
│  │   │   │
│  │   │   └── other:  read only (r--)
│  │   └────── group:  read + execute (r-x)
│  └────────── owner:  read + write + execute (rwx)
└───────────── type: - = regular file, d = directory, l = symlink
```

The meaning of each bit:

| Bit | On a file | On a directory |
|---|---|---|
| `r` (read) | Read the file's contents | List the directory's contents (`ls`) |
| `w` (write) | Modify the file | Create, rename, or delete files inside the directory |
| `x` (execute) | Run the file as a program | Enter the directory (`cd`) |

**`chmod` — change mode (permissions).**

Symbolic notation uses letters to describe the change:

```bash
# Give the owner execute permission on a script
chmod u+x run_inference.sh

# Remove write permission from group and other
chmod go-w model_weights.gguf

# Set exact permissions: owner=rwx, group=r-x, other=---
chmod u=rwx,g=rx,o= run_inference.sh

# Apply permissions recursively to a directory and all its contents
chmod -R o-rwx /opt/models/private/
```

Octet (numeric) notation represents each permission set as a three-bit binary number expressed as a decimal digit:

```
r = 4   (binary 100)
w = 2   (binary 010)
x = 1   (binary 001)

rwx = 4+2+1 = 7
rw- = 4+2+0 = 6
r-x = 4+0+1 = 5
r-- = 4+0+0 = 4
--- = 0+0+0 = 0
```

Common permission patterns on an AI server:

```bash
# Model weight files: owner reads/writes, group reads, others nothing
# chmod 640 = rw-r-----
chmod 640 /opt/models/llama3/llama3-70b.gguf

# Inference script: owner reads/writes/executes, group reads/executes, others nothing
# chmod 750 = rwxr-x---
chmod 750 /opt/ai-api/run_inference.py

# Config files with secrets (API keys): owner reads/writes only
# chmod 600 = rw-------
chmod 600 /etc/ai-api/secrets.env

# Public model directory (readable by all, writable only by owner)
# chmod 755 = rwxr-xr-x
chmod 755 /opt/models/

# Recursive: lock down an entire directory to owner + group only
chmod -R 750 /opt/models/private/
```

**`chown` — change ownership.**

```bash
# Change the owner of a file
sudo chown aiservice /opt/models/llama3/llama3-70b.gguf

# Change both owner and group simultaneously (owner:group)
sudo chown aiservice:aiservices /opt/models/llama3/llama3-70b.gguf

# Change ownership recursively on a directory and all its contents
sudo chown -R aiservice:aiservices /opt/models/

# Change only the group (without changing the owner)
sudo chown :aiservices /opt/models/shared/
```

A complete permission setup for a model weights directory looks like this:

```bash
# 1. Create the group that all inference services will share
sudo groupadd aiservices

# 2. Add the service account to the group
sudo usermod -aG aiservices aiservice

# 3. Set the correct owner and group on the weights directory
sudo chown -R aiservice:aiservices /opt/models/

# 4. Owner can read/write, group can read, others cannot access at all
sudo chmod -R 640 /opt/models/llama3/
sudo chmod 750 /opt/models/llama3/   # directory itself needs execute to enter

# 5. Verify
ls -lh /opt/models/llama3/
```

### Package Management with apt

Ubuntu and Debian-based Linux distributions use `apt` (Advanced Package Tool) to install, update, and remove software. The package manager downloads pre-compiled software from online repositories, resolves dependencies automatically, and handles installation cleanly.

`apt` vs `apt-get`: `apt` is the modern, user-friendly command introduced in Ubuntu 14.04. `apt-get` is the older, more scriptable variant. Both are available; in interactive terminal sessions prefer `apt`. In shell scripts, use `apt-get` for more predictable output.

```bash
# Refresh the local package index from online repositories
# Always run this before installing anything
sudo apt update

# Install a package
sudo apt install python3-pip

# Install multiple packages at once
sudo apt install build-essential git curl wget

# Remove a package (keeps configuration files)
sudo apt remove python3-pip

# Remove a package and its configuration files
sudo apt purge python3-pip

# Remove orphaned packages that were installed as dependencies but are no longer needed
sudo apt autoremove

# Upgrade all installed packages to the latest available versions
sudo apt upgrade

# Search for a package by name or description
apt search nvidia-driver

# Show detailed information about a package before installing
apt show python3-pip

# List all installed packages
apt list --installed

# List packages that have available upgrades
apt list --upgradable
```

On an AI server, the typical first-setup sequence is:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv build-essential curl git
```

The `-y` flag answers "yes" automatically to all prompts, which is useful for automated provisioning scripts but should be used carefully in interactive sessions.

**Package pinning.** When you need a specific version of a package (e.g., CUDA 12.4 rather than whatever is latest), you can request it explicitly:

```bash
# List all available versions of a package
apt-cache policy cuda-toolkit-12-4

# Install a specific version
sudo apt install cuda-toolkit-12-4=12.4.0-1
```

### Text Editors: nano and vim

Almost every Linux administration task eventually requires editing a text file — a configuration file, a startup script, a cron job, a systemd unit file. You need at least one terminal-based editor because graphical interfaces are often unavailable on servers.

**nano — beginner-friendly.** nano is simple and shows its own keyboard shortcuts at the bottom of the screen. It is installed by default on Ubuntu.

```bash
# Open a file for editing (creates it if it does not exist)
nano /etc/ai-api/config.env

# Open a file and jump to a specific line number
nano +42 /etc/ai-api/config.env
```

Essential nano key bindings (the `^` symbol means hold Ctrl):

| Key | Action |
|---|---|
| `^O` then Enter | Save (Write Out) |
| `^X` | Exit (prompts to save if unsaved changes exist) |
| `^W` | Search (Where is) |
| `^K` | Cut the current line |
| `^U` | Paste (Uncut) |
| `^G` | Open the help screen |
| `^C` | Show current cursor line and column |
| `^\` | Find and replace |

**vim — powerful, modal editor.** vim has a steep learning curve but is available everywhere and allows extremely fast editing once mastered. Understanding the basics prevents you from getting trapped in an open vim session with no way to exit — a famously common beginner panic.

vim has distinct modes. You start in **Normal mode**, where every key is a command, not a character. To type text you must enter **Insert mode** first.

```bash
# Open a file in vim
vim /etc/systemd/system/ai-inference.service

# View a file read-only (prevents accidental edits)
vim -R /etc/systemd/system/ai-inference.service
```

Essential vim commands — Normal mode (what you see when vim first opens):

| Command | Action |
|---|---|
| `i` | Enter Insert mode at cursor position |
| `a` | Enter Insert mode after cursor |
| `o` | Open a new line below and enter Insert mode |
| `Esc` | Return to Normal mode from any other mode |
| `:w` | Save the file (write) |
| `:q` | Quit (fails if there are unsaved changes) |
| `:wq` | Save and quit |
| `:q!` | Quit without saving (force) |
| `/searchterm` | Search forward for "searchterm" |
| `n` | Jump to the next search match |
| `dd` | Delete (cut) the current line |
| `yy` | Yank (copy) the current line |
| `p` | Paste below the cursor |
| `u` | Undo last change |
| `Ctrl-r` | Redo |
| `gg` | Jump to the top of the file |
| `G` | Jump to the bottom of the file |
| `:set number` | Show line numbers |

The single most important thing to remember: **press `Esc` first if unsure what mode you are in, then type `:wq` to save and exit, or `:q!` to exit without saving.**

## Best Practices

1. **Never run AI services or long-running daemons as the root user.** If the service is exploited, the attacker inherits root access to the entire server, including model weights, API keys stored in environment files, and cloud credential files under `/root/.aws` or `/root/.config`. Use a dedicated system account (`useradd -r`).

2. **Set the most restrictive permissions that still allow the service to function.** Model weight files do not need to be world-readable. Use `chmod 640` and `chown aiservice:aiservices` so only the owning account and designated group can read them. This limits blast radius if any other process on the server is compromised.

3. **Always run `sudo apt update` before `sudo apt install`.** Package repositories evolve daily; without refreshing the index, `apt install` may fetch an outdated package, miss a required dependency, or fail with a "package not found" error that resolves instantly with a fresh index.

4. **Use `mkdir -p` when creating nested directory structures in scripts.** Without `-p`, a script creating `/opt/models/llama3/70b/quantized` will fail if any intermediate directory is missing. With `-p`, the entire path is created idempotently — running the script twice does not cause an error.

5. **Avoid `rm -rf` on paths that include variables without verifying the variable is not empty first.** The command `rm -rf "$MODEL_DIR/"` deletes root (`/`) if `$MODEL_DIR` is empty or unset. In scripts, always validate variables before using them in destructive commands, and prefer `rm -ri` (interactive) when working interactively.

6. **Use `cp -a` rather than `cp -r` when copying model directories to a backup location.** The `-a` (archive) flag is equivalent to `-r -p --preserve=links` — it preserves timestamps, permissions, symlinks, and ownership. A backup with wrong permissions will not work when you restore it.

7. **When adding a user to a supplementary group with `usermod`, always include the `-a` flag.** Running `sudo usermod -G docker alice` without `-a` silently removes Alice from every other supplementary group she was in. The correct form is `sudo usermod -aG docker alice`.

8. **Keep configuration files that contain secrets (API keys, database passwords) at `chmod 600`, owned by the service account.** A file with `chmod 644` is world-readable — any user on the system can `cat` your OpenAI API key or HuggingFace token. Secrets must be readable only by the account that needs them.

9. **Use `/opt/` for self-contained AI software and model weights, not `/usr/local/` or `/home`.** `/opt` is the FHS-designated location for add-on application software packages. It keeps third-party tools cleanly separated from OS-managed paths and is straightforward to back up, move to a larger disk, or mount as a separate volume.

10. **Prefer `nano` for quick single-file edits on servers you do not own or administer regularly; invest time in `vim` for servers you manage daily.** The productivity gains from vim's motion commands compound over thousands of editing sessions, but there is zero benefit to fighting vim on a server you are touching once.

## Use Cases

### Use Case 1: Provisioning a Server for a New AI Inference Service

A team is deploying a FastAPI-based inference server that loads a 7 billion-parameter GGUF model. The server needs to be configured so the service runs as a non-root account, model weights are protected, and the right software is installed.

- **Problem:** Without proper user separation and permissions, the inference process runs as root, making a prompt-injection attack that causes file system writes catastrophic rather than contained.
- **Concepts applied:** `useradd -r` for a system account, `mkdir -p` to create the directory structure, `chown` and `chmod` to secure model files, `apt install` to install Python and dependencies.
- **Expected outcome:** An `aiservice` system account owns `/opt/models/` and `/opt/ai-api/`. The model weights are `chmod 640`, readable only by `aiservice` and the `aiservices` group. The inference process has no ability to write outside its designated directories.

### Use Case 2: Auditing Disk Usage After a Training Run

A GPU training job fills the disk. The administrator needs to find which directory consumed the space and clean up temporary checkpoints that were saved to the wrong location.

- **Problem:** A training script saved intermediate checkpoints to `/tmp/` instead of the project's checkpoint directory. The server now has 200 GB of `.pt` files scattered across unexpected locations.
- **Concepts applied:** `find /tmp -type f -name "*.pt" -size +1G` to locate the files, `ls -lh` to confirm sizes and ownership, `rm` to remove them after verification.
- **Expected outcome:** All orphaned checkpoint files are identified by path, confirmed as safe to delete, and removed. Disk space is recovered without touching any files in the legitimate model storage location.

### Use Case 3: Rotating API Keys Stored in a Config File

A security audit reveals that the inference service config file was accidentally committed to Git. The team needs to rotate the API key and ensure the file is locked down correctly going forward.

- **Problem:** The file `/etc/ai-api/secrets.env` has `chmod 644` (world-readable). It contains an active HuggingFace token. Any user on the system — or any container with a bind mount — could read it.
- **Concepts applied:** `nano` or `vim` to edit the file and replace the key, `chmod 600` to remove world and group read permissions, `chown` to confirm the service account is the sole owner.
- **Expected outcome:** The file is `rw-------`, owned by `aiservice:aiservice`. Only the inference process (running as `aiservice`) can read it. No other user or process on the system can access it without sudo.

### Use Case 4: Onboarding a New Developer

A new team member needs access to the AI server to run experiments. They need their own user account, membership in the `aiservices` group to read shared model weights, and the ability to install Python packages.

- **Problem:** Creating an account manually without understanding groups means the developer cannot read the shared models directory and re-downloads 40 GB of weights into their home directory instead.
- **Concepts applied:** `useradd -m -s /bin/bash` to create the account, `passwd` to set the initial password, `usermod -aG` to add them to the `aiservices` group, `id` to verify group membership, `find` to show the developer where the shared models are stored.
- **Expected outcome:** The developer can read files in `/opt/models/` through group membership but cannot modify or delete them. Their experiments stay in their home directory. The 40 GB model files are shared, not duplicated.

## Hands-on Examples

### Example 1: Setting Up the AI Server Directory Structure

You will create the canonical directory layout for a Linux-hosted AI inference server, create a system service account, and apply appropriate ownership and permissions to each directory.

1. Update the package index and install tree (a utility that displays directory structure visually).

```bash
sudo apt update
sudo apt install -y tree
```

Expected output (abbreviated):
```
Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease
...
Setting up tree (2.0.2-1) ...
```

2. Create the directory hierarchy.

```bash
sudo mkdir -p /opt/models/llama3/70b
sudo mkdir -p /opt/models/mistral/7b
sudo mkdir -p /opt/ai-api/logs
sudo mkdir -p /opt/ai-api/config
```

3. Create a system service account with no interactive login shell.

```bash
sudo useradd -r -s /bin/false -d /opt/ai-api -M aiservice
```

4. Confirm the account exists.

```bash
id aiservice
```

Expected output:
```
uid=999(aiservice) gid=999(aiservice) groups=999(aiservice)
```
(The exact UID will differ based on your system, but it will be below 1000 for a system account.)

5. Create a shared group for AI service accounts.

```bash
sudo groupadd aiservices
sudo usermod -aG aiservices aiservice
```

6. Set ownership of both directories to the service account.

```bash
sudo chown -R aiservice:aiservices /opt/models/
sudo chown -R aiservice:aiservices /opt/ai-api/
```

7. Set permissions: directories need execute (`x`) to be entered; files need read (`r`). Apply a sensible baseline.

```bash
# Directories: owner rwx, group r-x, other ---
sudo find /opt/models -type d -exec chmod 750 {} \;
sudo find /opt/ai-api -type d -exec chmod 750 {} \;

# Any files already present: owner rw-, group r--, other ---
sudo find /opt/models -type f -exec chmod 640 {} \;
sudo find /opt/ai-api -type f -exec chmod 640 {} \;
```

8. Verify the structure and permissions.

```bash
ls -lh /opt/
```

Expected output:
```
total 8.0K
drwxr-x--- 4 aiservice aiservices 4096 Apr 10 2026 ai-api
drwxr-x--- 4 aiservice aiservices 4096 Apr 10 2026 models
```

```bash
tree /opt/models/
```

Expected output:
```
/opt/models/
├── llama3
│   └── 70b
└── mistral
    └── 7b

4 directories, 0 files
```

---

### Example 2: Finding and Cleaning Up Orphaned Model Files

You will simulate a training script that left large temporary files in the wrong location, find them, and remove them safely.

1. Create some simulated orphaned checkpoint files in `/tmp`.

```bash
# Create placeholder files that represent model checkpoints
# (using truncate to create sparse files of specified size without consuming real disk space)
sudo truncate -s 2G /tmp/checkpoint-epoch-001.pt
sudo truncate -s 2G /tmp/checkpoint-epoch-002.pt
sudo truncate -s 500M /tmp/training-log.txt
```

2. Find all files larger than 1 GB in `/tmp`.

```bash
find /tmp -type f -size +1G
```

Expected output:
```
/tmp/checkpoint-epoch-001.pt
/tmp/checkpoint-epoch-002.pt
```

3. Find all `.pt` files anywhere under `/tmp` regardless of size.

```bash
find /tmp -type f -name "*.pt"
```

Expected output:
```
/tmp/checkpoint-epoch-001.pt
/tmp/checkpoint-epoch-002.pt
```

4. Confirm ownership and size before deleting.

```bash
ls -lh /tmp/checkpoint-epoch-001.pt /tmp/checkpoint-epoch-002.pt
```

Expected output:
```
-rw-r--r-- 1 root root 2.0G Apr 10 2026 /tmp/checkpoint-epoch-001.pt
-rw-r--r-- 1 root root 2.0G Apr 10 2026 /tmp/checkpoint-epoch-002.pt
```

5. Remove the orphaned checkpoint files.

```bash
sudo rm /tmp/checkpoint-epoch-001.pt /tmp/checkpoint-epoch-002.pt
```

6. Verify they are gone.

```bash
find /tmp -type f -name "*.pt"
```

Expected output: (no output — the files are gone)

7. Clean up the log file too.

```bash
sudo rm /tmp/training-log.txt
```

---

### Example 3: Editing a Configuration File with nano and Locking It Down

You will create a configuration file for a hypothetical inference service, edit it with nano, and then apply correct permissions.

1. Create the config file as root.

```bash
sudo nano /opt/ai-api/config/secrets.env
```

2. Inside nano, type the following content exactly.

```
HF_TOKEN=hf_exampletoken1234567890
OPENAI_API_KEY=sk-examplekey0987654321
MODEL_PATH=/opt/models/llama3/70b/llama3-70b-q4.gguf
```

3. Save and exit: press `Ctrl+O`, then `Enter` to confirm the filename, then `Ctrl+X` to exit.

4. Verify the file was created correctly.

```bash
cat /opt/ai-api/config/secrets.env
```

Expected output:
```
HF_TOKEN=hf_exampletoken1234567890
OPENAI_API_KEY=sk-examplekey0987654321
MODEL_PATH=/opt/models/llama3/70b/llama3-70b-q4.gguf
```

5. Check the current permissions (newly created files default to 644 — world-readable).

```bash
ls -l /opt/ai-api/config/secrets.env
```

Expected output:
```
-rw-r--r-- 1 root root 102 Apr 10 2026 /opt/ai-api/config/secrets.env
```

6. Fix the ownership and permissions so only `aiservice` can read it.

```bash
sudo chown aiservice:aiservice /opt/ai-api/config/secrets.env
sudo chmod 600 /opt/ai-api/config/secrets.env
```

7. Verify the locked-down state.

```bash
ls -l /opt/ai-api/config/secrets.env
```

Expected output:
```
-rw------- 1 aiservice aiservice 102 Apr 10 2026 /opt/ai-api/config/secrets.env
```

8. Confirm that your regular user account cannot read the file.

```bash
# Try to read the file as your own (non-root) user
cat /opt/ai-api/config/secrets.env
```

Expected output:
```
cat: /opt/ai-api/config/secrets.env: Permission denied
```

The permissions are working correctly. Only `aiservice` (and root via sudo) can read this file.

---

### Example 4: Creating a Developer Account with Correct Group Membership

You will create a new developer account, add them to the group that grants access to shared model weights, and verify they can navigate the models directory.

1. Create the developer's user account.

```bash
sudo useradd -m -s /bin/bash devuser
sudo passwd devuser
```

When prompted, enter and confirm a password (e.g., `ChangeMe123!`).

Expected output after `passwd`:
```
New password:
Retype new password:
passwd: password updated successfully
```

2. Verify the account and its default groups.

```bash
id devuser
```

Expected output:
```
uid=1001(devuser) gid=1001(devuser) groups=1001(devuser)
```

Note that `devuser` is not yet in the `aiservices` group and therefore cannot access `/opt/models/`.

3. Try to list the models directory as `devuser` before adding them to the group.

```bash
sudo -u devuser ls /opt/models/
```

Expected output:
```
ls: cannot open directory '/opt/models/': Permission denied
```

4. Add `devuser` to the `aiservices` group.

```bash
sudo usermod -aG aiservices devuser
```

5. Verify the group membership is now correct.

```bash
id devuser
```

Expected output:
```
uid=1001(devuser) gid=1001(devuser) groups=1001(devuser),1000(aiservices)
```

6. Try listing the models directory again. For the group change to take effect, the user must start a new session. Simulate this with `su`.

```bash
sudo su - devuser -c "ls /opt/models/"
```

Expected output:
```
llama3  mistral
```

The developer can now read the shared model directory through group membership without owning the files themselves.

## Common Pitfalls

### Pitfall 1: Running Services as Root

**Description:** Launching an inference API, Jupyter notebook server, or model download script as the root user because it avoids permission headaches during setup.

**Why it happens:** Root can access everything without any permission configuration, making it the path of least resistance when you are still learning the system.

**Incorrect pattern:**
```bash
# Running the inference server as root — never do this
sudo python3 /opt/ai-api/app.py
```

**Correct pattern:**
```bash
# Set correct ownership first, then run as the service account
sudo chown -R aiservice:aiservices /opt/ai-api/
sudo -u aiservice python3 /opt/ai-api/app.py
```

---

### Pitfall 2: Forgetting `-a` When Adding a User to a Group

**Description:** Running `sudo usermod -G docker alice` instead of `sudo usermod -aG docker alice` silently removes Alice from all her other supplementary groups (e.g., `sudo`, `aiservices`) and replaces them with only `docker`.

**Why it happens:** The `-G` flag means "set supplementary groups to this list." Without `-a` (append), it replaces rather than extends.

**Incorrect pattern:**
```bash
# This removes alice from every group she was in, leaving only "docker"
sudo usermod -G docker alice
```

**Correct pattern:**
```bash
# The -a flag appends docker to alice's existing group memberships
sudo usermod -aG docker alice
```

---

### Pitfall 3: Forgetting `sudo apt update` Before Installing Packages

**Description:** Running `sudo apt install cuda-toolkit-12-4` on a freshly cloned server returns "E: Unable to locate package" even though the package definitely exists.

**Why it happens:** `apt install` consults a local package index cache, not the live repository. On a fresh Ubuntu instance or after months without updates, this cache is stale and does not know about packages that have been added or moved.

**Incorrect pattern:**
```bash
# Fails if the local index is out of date
sudo apt install cuda-toolkit-12-4
# E: Unable to locate package cuda-toolkit-12-4
```

**Correct pattern:**
```bash
# Always refresh the index first
sudo apt update
sudo apt install cuda-toolkit-12-4
```

---

### Pitfall 4: Using `chmod -R 777` to "Fix" Permission Errors

**Description:** When a service cannot read a file and returns a permission error, a common instinct is to run `chmod -R 777 /opt/models/` to make everything accessible. This sets world read/write/execute on every model weight, configuration file, and secret in the directory.

**Why it happens:** 777 eliminates all permission-related errors immediately, which feels like a solution during a debugging session. The security implications are not immediately visible.

**Incorrect pattern:**
```bash
# Makes every file readable, writable, and executable by every user on the system
sudo chmod -R 777 /opt/models/
```

**Correct pattern:**
```bash
# Diagnose the actual problem: is it ownership or permission?
ls -lh /opt/models/llama3/llama3-70b.gguf
# Identify the right fix: correct owner or correct group membership
sudo chown aiservice:aiservices /opt/models/llama3/llama3-70b.gguf
sudo chmod 640 /opt/models/llama3/llama3-70b.gguf
```

---

### Pitfall 5: Creating Directories Without `-p` in Automation Scripts

**Description:** A provisioning script runs `mkdir /opt/models/llama3/70b/quantized` and fails because `/opt/models` does not yet exist. The script exits with an error and the rest of the setup is skipped.

**Why it happens:** `mkdir` by default only creates the final component of the path and requires all parent directories to already exist.

**Incorrect pattern:**
```bash
# Fails if /opt/models or /opt/models/llama3 does not exist
mkdir /opt/models/llama3/70b/quantized
# mkdir: cannot create directory '/opt/models/llama3/70b/quantized': No such file or directory
```

**Correct pattern:**
```bash
# Creates the entire path, silently succeeds even if it already exists
mkdir -p /opt/models/llama3/70b/quantized
```

---

### Pitfall 6: Getting Stuck in vim With No Way to Exit

**Description:** A user opens a file with `vim` (or is dropped into vim by `git commit` or `crontab -e`) and cannot figure out how to exit. They close the terminal, losing changes, or sit frozen.

**Why it happens:** vim's modal design means keys do not type characters in Normal mode — every key is a command. The concept of modes is not intuitive to someone accustomed to conventional text editors.

**Incorrect pattern:**
```
# User opens vim, types some characters, they appear as commands rather than text
# User presses Ctrl+C, nothing useful happens
# User is stuck
```

**Correct pattern:**
```
1. Press Esc (gets you to Normal mode no matter what mode you are in)
2. To save and exit: type :wq then press Enter
3. To exit without saving: type :q! then press Enter
4. If you accidentally entered text in Normal mode (gibberish appeared): type u repeatedly to undo
```

---

### Pitfall 7: Misreading Octet Permission Numbers

**Description:** A developer means to set `chmod 640` (owner rw, group r, others nothing) but types `chmod 460` instead — which sets read-only for the owner, rw for the group, and nothing for others. The service account that owns the file can no longer write to it.

**Why it happens:** The three digits map left-to-right to owner, group, other. Beginners sometimes misremember the order or conflate the digit positions.

**Incorrect pattern:**
```bash
# 4=r-- for owner, 6=rw- for group, 0=--- for other
# Owner cannot write their own file
chmod 460 model_config.json
```

**Correct pattern:**
```bash
# 6=rw- for owner, 4=r-- for group, 0=--- for other
chmod 640 model_config.json
```

The memory aid: read the digits left to right in order of decreasing privilege — the owner always comes first (leftmost digit), then group (middle), then other (rightmost).

---

### Pitfall 8: Leaving Secrets Files World-Readable After Creation

**Description:** A developer creates `/etc/ai-api/secrets.env` with `nano` and leaves the default `644` permissions. Every user on the server — including other developers, compromised application accounts, and anyone who escapes a container with a bind mount — can read the API keys inside.

**Why it happens:** Files created by root with `nano` or `touch` inherit a default umask that typically yields `644`. Restricting permissions requires a deliberate, separate step that is easy to forget.

**Incorrect pattern:**
```bash
sudo nano /etc/ai-api/secrets.env
# File is created as -rw-r--r-- (world-readable) by default
```

**Correct pattern:**
```bash
sudo nano /etc/ai-api/secrets.env
# Immediately lock it down after creation
sudo chown aiservice:aiservice /etc/ai-api/secrets.env
sudo chmod 600 /etc/ai-api/secrets.env
```

## Summary

- The Linux filesystem hierarchy places everything under `/`, with well-defined directories for configuration (`/etc`), variable data (`/var`), installed software (`/usr`, `/opt`), and temporary files (`/tmp`); choosing the right location for model weights, configs, and logs is the first step toward a maintainable AI server.
- Every file is owned by a user and a group, with three separate read/write/execute permission sets for owner, group, and everyone else; this model lets you share model weights with multiple service accounts through group membership without making them world-readable.
- Service accounts created with `useradd -r -s /bin/false` provide isolated identities for AI daemons that cannot be used for interactive login, limiting the blast radius of a compromised service.
- `apt update` refreshes the local package index and must precede `apt install`; the two are almost always run together when provisioning an AI server or installing a new framework dependency.
- `nano` provides an accessible starting point for editing configuration and secret files on servers; `vim` rewards long-term investment with speed and is universally available on every Linux system you will ever administer.

## Further Reading

- [Ubuntu Server Guide — Ubuntu Documentation](https://ubuntu.com/server/docs) — The official Ubuntu server administration guide covering installation, user management, networking, and security hardening; the authoritative reference for everything Ubuntu-specific in this module.
- [Filesystem Hierarchy Standard 3.0 — Linux Foundation](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/index.html) — The formal specification defining what belongs in each top-level Linux directory; essential reading for understanding why `/opt`, `/srv`, and `/var` exist as separate directories rather than one general-purpose folder.
- [Linux File Permissions Explained — DigitalOcean Community Tutorials](https://www.digitalocean.com/community/tutorials/linux-permissions-basics-and-how-to-use-umask-on-a-vps) — A practitioner-focused walkthrough of the `rwx` permission model, octet notation, `umask`, and `setuid`/`setgid` bits with concrete examples; a reliable complement to this module's permissions section.
- [An Introduction to Linux Users and Groups — DigitalOcean Community Tutorials](https://www.digitalocean.com/community/tutorials/an-introduction-to-linux-basics) — Covers user account types, `/etc/passwd`, `/etc/shadow`, and `/etc/group` file formats; useful for understanding what `useradd` and `usermod` actually write to disk.
- [apt — Debian Documentation](https://wiki.debian.org/apt) — The Debian project's documentation for apt, covering repository configuration (`/etc/apt/sources.list`), package pinning, key management, and the difference between `apt`, `apt-get`, and `dpkg`; directly applicable to Ubuntu.
- [OpenSSH Security Best Practices — NIST SP 800-53](https://www.ssh.com/academy/ssh/security) — Covers SSH hardening for Linux servers including key-based authentication, disabling root login, and `sshd_config` options; the natural next step after securing local user accounts and permissions as covered in this module.
- [Vim Adventures](https://vim-adventures.com) — An interactive browser-based game that teaches vim's motion commands and modes through gameplay; far more effective than reading documentation for building vim muscle memory.
- [Linux Command Line Basics — The Linux Command Line by William Shotts (free online)](https://linuxcommand.org/tlcl.php) — A freely available book covering the shell, navigation, permissions, and scripting in depth; the most recommended introductory Linux text in the practitioner community and a natural next resource after this module.
