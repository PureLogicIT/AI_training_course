# Module 6: System Services
> Subject: Linux | Difficulty: Intermediate | Estimated Time: 150 minutes

## Objective

After completing this module, you will be able to manage Linux system services with `systemctl` (start, stop, restart, enable, disable, status), inspect and filter logs with `journalctl`, write a custom `.service` unit file for an AI inference application (such as Ollama or a FastAPI LLM server), declare service dependencies using `After=` and `Requires=`, inject environment variables into services, apply resource limits (`LimitNOFILE=`, `MemoryMax=`), configure automatic restarts on failure with `Restart=always`, schedule recurring tasks with systemd timers, and understand cron syntax as an alternative scheduling approach.

The central project running through this module is deploying a Python FastAPI LLM inference server as a production-grade systemd service that starts on boot, survives crashes, and ships all logs to `journald`.

## Prerequisites

- A Linux system running systemd (Ubuntu 22.04 LTS, Ubuntu 24.04 LTS, Debian 12, Fedora 39+, or any modern RHEL/Rocky/Alma 9+ derivative) — confirm with `systemctl --version` (current systemd stable release is **256** as of April 2026)
- Familiarity with the Linux command line: navigating directories, editing files with `nano` or `vim`, running commands with `sudo`
- Python 3.10 or later installed (`python3 --version`) — required for the FastAPI server examples
- Completion of prior Linux modules covering file permissions and user management is recommended but not required for understanding this module's core concepts
- No prior systemd knowledge is assumed

## Key Concepts

### What systemd Is and Why It Replaced SysVinit

Every Linux system needs a process to start when the kernel hands over control after boot. That process — PID 1 — is responsible for bringing up all other services: the network, the SSH daemon, the display manager, your database, your AI inference server. Traditionally this role was filled by SysVinit, which used shell scripts in `/etc/init.d/` to start services sequentially, one after another. Sequential startup is slow, error-prone, and difficult to extend.

systemd replaced SysVinit on virtually all mainstream distributions starting around 2012–2015. Its key advances over the old approach are:

- **Parallel startup.** systemd analyzes dependencies and starts services simultaneously where safe, dramatically reducing boot time.
- **Declarative unit files.** Instead of imperative shell scripts full of boilerplate, you describe *what* a service is and systemd handles the *how*.
- **Integrated logging.** systemd includes `journald`, a structured binary log store. All service output goes to the same place with consistent metadata (timestamp, unit name, PID).
- **Socket and D-Bus activation.** Services can be started lazily, the first time a socket they own receives a connection.
- **Cgroup-based resource control.** systemd uses Linux control groups to track and limit exactly which processes belong to a service, enabling accurate CPU, memory, and I/O limits.

```
Kernel boots
     |
     v
  systemd (PID 1)
     |
     +---> network.target
     +---> multi-user.target
     |         |
     |         +---> sshd.service
     |         +---> ollama.service   <-- your AI service
     |         +---> postgresql.service
     v
  graphical.target (if a desktop is present)
```

### Unit Files: The Building Blocks of systemd

Everything in systemd is represented as a **unit**. A unit is described by a plain text configuration file — a **unit file**. There are several unit types:

| Unit type | File suffix | Purpose |
|---|---|---|
| Service | `.service` | A background process (daemon) |
| Timer | `.timer` | A scheduled task — the cron replacement |
| Socket | `.socket` | A network or IPC socket for socket activation |
| Target | `.target` | A grouping of units (like a runlevel) |
| Mount | `.mount` | A filesystem mount point |
| Path | `.path` | Triggers a unit when a file path changes |

Unit files live in one of three locations, evaluated in priority order (lowest to highest):

| Location | Purpose |
|---|---|
| `/lib/systemd/system/` | Shipped by the OS package manager — do not edit these |
| `/etc/systemd/system/` | Administrator-created or -overridden units — your work goes here |
| `~/.config/systemd/user/` | Per-user units that run without root (user sessions only) |

When you create a service for an AI application, you write a `.service` file in `/etc/systemd/system/`.

### Anatomy of a .service Unit File

A service unit file is divided into three sections:

```ini
[Unit]
# Metadata and dependency declarations

[Service]
# How to run the process

[Install]
# How to wire this unit into boot targets
```

Here is a minimal but complete example that runs a Python script as a service:

```ini
[Unit]
Description=My Python Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/myapp/server.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Every directive is explained in the Key Concepts sections below. The full reference hands-on example in this module builds out a production-quality version of this template for a FastAPI LLM server.

### systemctl: Managing Service Lifecycle

`systemctl` is the command-line interface to systemd. It controls the state of units and configures which units activate automatically at boot.

**Controlling a running service:**

```bash
# Start a service (does not persist across reboots)
sudo systemctl start ollama.service

# Stop a service gracefully (sends SIGTERM, then SIGKILL after TimeoutStopSec=)
sudo systemctl stop ollama.service

# Restart a service (stop then start)
sudo systemctl restart ollama.service

# Reload a service's configuration without stopping it (only if the process supports SIGHUP)
sudo systemctl reload ollama.service

# Reload-or-restart: reload if supported, otherwise restart
sudo systemctl reload-or-restart ollama.service
```

**Enabling and disabling services at boot:**

```bash
# Enable: create the symlink that makes this service start automatically on boot
sudo systemctl enable ollama.service

# Disable: remove the symlink so the service no longer starts on boot
sudo systemctl disable ollama.service

# Enable AND start immediately in one command
sudo systemctl enable --now ollama.service

# Disable AND stop immediately in one command
sudo systemctl disable --now ollama.service
```

The distinction between "started" and "enabled" is important and confusing for beginners. **Starting** a service runs it right now. **Enabling** a service tells systemd to start it automatically the next time the system boots. A service can be started without being enabled (runs now, not after reboot) or enabled without being started (will run after next reboot, not right now).

**Inspecting service state:**

```bash
# Show the full status: active/inactive state, PID, last log lines
sudo systemctl status ollama.service

# Check whether a service is currently active (exit code 0 = active)
systemctl is-active ollama.service

# Check whether a service is enabled for boot (exit code 0 = enabled)
systemctl is-enabled ollama.service

# List all loaded services and their states
systemctl list-units --type=service

# List all service unit files (including disabled ones)
systemctl list-unit-files --type=service
```

**After editing a unit file, you must reload systemd's configuration:**

```bash
sudo systemctl daemon-reload
```

systemd caches unit file contents. Without `daemon-reload`, edits to a `.service` file in `/etc/systemd/system/` have no effect until systemd re-reads them.

### journalctl: Querying the System Log

`journald` captures all output written to stdout and stderr by every systemd service, along with kernel messages and syslog entries, and stores it in a structured binary database at `/var/log/journal/`. `journalctl` is the query interface for that database.

**Basic usage:**

```bash
# Show all logs, oldest first (press q to quit, arrow keys to scroll)
journalctl

# Show logs for a specific service unit
journalctl -u ollama.service

# Follow logs in real time (like tail -f)
journalctl -u ollama.service -f

# Show only the last 50 lines
journalctl -u ollama.service -n 50

# Show logs since a specific time
journalctl -u ollama.service --since "2026-04-10 09:00:00"

# Show logs within a time range
journalctl -u ollama.service --since "1 hour ago" --until "30 min ago"

# Show logs since the last boot
journalctl -u ollama.service -b

# Show kernel messages only
journalctl -k

# Show logs at a specific priority level (err, warning, info, debug)
journalctl -u ollama.service -p err

# Output in JSON format (useful for piping to log aggregators)
journalctl -u ollama.service -o json-pretty | head -40

# Show disk space used by the journal
journalctl --disk-usage
```

**Output format.** Each `journalctl` line looks like this:

```
Apr 10 09:15:32 hostname ollama[3421]: time=2026-04-10T09:15:32Z level=info msg="Listening on :11434"
```

The fields are: date, hostname, unit name + PID in brackets, then the log message as the process wrote it to stdout.

### Writing a .service Unit File for an AI Application

This section walks through every directive you need for a production AI inference service. The target application is a FastAPI server that loads a local LLM and exposes an HTTP API on port 8000.

#### [Unit] Section Directives

```ini
[Unit]
Description=FastAPI LLM Inference Server
Documentation=https://github.com/yourorg/llm-server
After=network-online.target
Wants=network-online.target
```

- **`Description=`** — Human-readable name shown in `systemctl status` output and `journalctl` entries. Keep it concise and accurate.
- **`Documentation=`** — One or more URLs or `man:` references. Optional but useful for operators.
- **`After=`** — Declares ordering: this unit starts *after* the listed units have finished activating. `After=` is purely an ordering constraint; it does not create a hard dependency. Using `network-online.target` (rather than `network.target`) ensures the network is fully configured — important for services that connect to remote APIs or model registries at startup.
- **`Wants=`** — A soft dependency. If the listed unit is not running, systemd will try to start it, but if it fails, this unit still starts. Use `Requires=` for a hard dependency (failure of the dependency prevents this unit from starting).

#### [Service] Section Directives

```ini
[Service]
Type=simple
User=llmserver
Group=llmserver
WorkingDirectory=/opt/llm-server

ExecStart=/opt/llm-server/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -HUP $MAINPID

Restart=always
RestartSec=5
StartLimitIntervalSec=60
StartLimitBurst=3

Environment="MODEL_PATH=/opt/models/mistral-7b-instruct"
Environment="LOG_LEVEL=info"
EnvironmentFile=/etc/llm-server/env

StandardOutput=journal
StandardError=journal
SyslogIdentifier=llm-server
```

**Type options:**

| `Type=` | Meaning |
|---|---|
| `simple` (default) | The process started by `ExecStart=` is the main process. systemd considers the service running as soon as the process starts. |
| `exec` | Like `simple`, but systemd waits until the `exec()` call succeeds before considering the service started. Safer for catching startup errors. |
| `forking` | The process forks and the parent exits. Used with old-style daemons that daemonize themselves. Requires `PIDFile=`. |
| `notify` | The service sends a `sd_notify(3)` message when it is ready. Uvicorn and Gunicorn support this with `--reload` or wrapper scripts. |
| `oneshot` | The process runs to completion and exits. systemd marks the service as active until it exits. Used for setup scripts and timers. |
| `idle` | Like `simple` but the process is started after all pending jobs are dispatched. Rarely needed. |

For a FastAPI/Uvicorn server, `Type=simple` is correct. The process does not fork; it runs in the foreground.

**User and Group:** Always run AI services as a dedicated non-root user. Create the user before deploying the service:

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin llmserver
```

`--system` creates a system account (no password, lower UID range). `--no-create-home` skips home directory creation. `--shell /usr/sbin/nologin` prevents interactive login.

**`WorkingDirectory=`** sets the process's current directory. Relative paths in your application will resolve against this directory.

**`ExecStart=`** is the command that launches the service. The path must be absolute. Arguments are space-separated. Do not use shell features like `&&`, `|`, or `$()` directly in `ExecStart=` — use `ExecStartPre=` for setup commands or write a wrapper script.

**`Restart=` options:**

| Value | Restarts when... |
|---|---|
| `no` | Never restarts |
| `on-success` | Only if the service exits with code 0 |
| `on-failure` | On non-zero exit code, signal termination, timeout, or watchdog timeout |
| `on-abnormal` | On signal, timeout, or watchdog (not clean exits) |
| `always` | Always restarts, regardless of exit code — use this for AI servers |
| `on-abort` | Only on uncaught signals |

For a long-running inference server that must stay available, use `Restart=always`. Pair it with `RestartSec=5` (wait 5 seconds before restarting) to avoid hammering a failing process in a tight loop.

`StartLimitIntervalSec=60` and `StartLimitBurst=3` together mean: if the service fails and restarts more than 3 times within 60 seconds, systemd gives up and marks the service as failed rather than continuing to restart it indefinitely. This prevents runaway restart loops from consuming all system resources.

**Environment variables:**

```ini
# Inline variable (good for non-secret values)
Environment="MODEL_PATH=/opt/models/mistral-7b-instruct"

# Multiple variables, one per Environment= line
Environment="LOG_LEVEL=info"
Environment="MAX_WORKERS=4"

# Load variables from a file (good for secrets and per-environment config)
EnvironmentFile=/etc/llm-server/env
```

The `EnvironmentFile=` points to a plain text file where each line is `KEY=VALUE`. Lines beginning with `#` are comments. Prefix the path with `-` (e.g., `EnvironmentFile=-/etc/llm-server/env`) to make it optional — the service will start even if the file is absent.

Example `/etc/llm-server/env`:

```bash
# /etc/llm-server/env
MODEL_PATH=/opt/models/mistral-7b-instruct
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
LOG_LEVEL=info
MAX_WORKERS=4
CUDA_VISIBLE_DEVICES=0
```

Secure this file so only root and the service user can read it:

```bash
sudo chmod 640 /etc/llm-server/env
sudo chown root:llmserver /etc/llm-server/env
```

**Logging directives:**

```ini
StandardOutput=journal
StandardError=journal
SyslogIdentifier=llm-server
```

`StandardOutput=journal` and `StandardError=journal` route stdout and stderr into `journald`. This is the default for systemd services, so these lines are technically redundant — but they are worth including explicitly for documentation clarity. `SyslogIdentifier=llm-server` sets the tag that appears in `journalctl` output, overriding the default (which would be the executable name). A short, lowercase, hyphenated identifier is the convention.

#### [Install] Section Directives

```ini
[Install]
WantedBy=multi-user.target
```

`WantedBy=multi-user.target` is the correct value for almost all server-side services. It means: when `multi-user.target` is activated (which happens on every normal boot), activate this service as part of it. When you run `systemctl enable`, systemd creates a symlink from `multi-user.target.wants/` to your unit file, wiring it into the boot sequence.

`graphical.target` is appropriate only for services that require a display server. AI inference services on a headless server should always use `multi-user.target`.

### Service Dependencies: After=, Requires=, and Wants=

Dependency directives control two distinct things: **ordering** (which unit starts first) and **requirement** (whether this unit can start if another is unavailable).

| Directive | Type | Effect |
|---|---|---|
| `After=B` | Ordering | Start this unit after B. If B is not requested, this has no effect. |
| `Before=B` | Ordering | Start this unit before B. |
| `Requires=B` | Hard dependency | This unit needs B. If B fails to start, this unit also fails. If B stops, this unit stops. |
| `Wants=B` | Soft dependency | Try to start B alongside this unit. If B fails, this unit continues anyway. |
| `BindsTo=B` | Strong binding | Like `Requires=`, but also stops this unit if B enters an inactive state for any reason. |
| `PartOf=B` | Propagation | Stops and restarts when B stops and restarts, but does not require B to start. |

A common pattern for an AI server that requires a database:

```ini
[Unit]
Description=FastAPI LLM Inference Server
After=network-online.target postgresql.service
Requires=postgresql.service
Wants=network-online.target
```

This ensures PostgreSQL is running before the inference server starts. If PostgreSQL fails to start, the inference server fails as well, surfacing the dependency problem clearly rather than starting in a broken state and logging confusing errors.

For Ollama as a backend, you would add:

```ini
After=network-online.target ollama.service
Requires=ollama.service
```

### Resource Limits

systemd exposes cgroup-based resource controls directly in service unit files. For AI inference servers — which can consume large amounts of RAM and hold thousands of file descriptors — these are essential.

```ini
[Service]
# Maximum number of open file descriptors
# Default system limit is often 1024, which is too low for ML frameworks
LimitNOFILE=65536

# Maximum number of processes the service can create
LimitNPROC=4096

# Memory limit — service is OOM-killed if it exceeds this
# Supports K, M, G, T suffixes
MemoryMax=14G

# Reserve this much RAM for the service (soft limit, affects scheduling)
MemoryLow=2G

# CPU time limit (percentage; 200% = 2 full cores)
CPUQuota=200%

# CPU scheduling weight (default 100; higher = more CPU priority)
CPUWeight=150
```

**`LimitNOFILE=`** is the most commonly needed adjustment for AI services. PyTorch, TensorFlow, and ONNX Runtime open many files for memory-mapped model weights. The default OS limit of 1024 causes cryptic "Too many open files" errors. Set it to at least 65536 for any ML workload.

**`MemoryMax=`** is the hard ceiling. If the process exceeds this, the Linux OOM killer terminates it. systemd then applies the `Restart=` policy. This is preferable to an uncontrolled OOM kill that takes down unrelated processes.

After changing resource limits, run `sudo systemctl daemon-reload` and `sudo systemctl restart your-service.service`. Verify the applied limits with:

```bash
systemctl show ollama.service | grep -E "Limit|Memory|CPU"
# Or inspect the live cgroup:
cat /sys/fs/cgroup/system.slice/ollama.service/memory.max
```

### Auto-Restart on Failure

The `Restart=` directive and its companions are the core of service resilience. For an AI inference server:

```ini
[Service]
Restart=always
RestartSec=5
StartLimitIntervalSec=120
StartLimitBurst=5
```

**How the restart loop works:**

1. The service process exits for any reason (crash, OOM kill, uncaught exception).
2. systemd waits `RestartSec=5` seconds.
3. systemd starts the process again.
4. If the process exits again within the `StartLimitIntervalSec=` window (120 seconds), the restart counter increments.
5. If the counter reaches `StartLimitBurst=` (5 restarts in 120 seconds), systemd marks the unit as `failed` and stops restarting.
6. An operator must then run `sudo systemctl reset-failed your-service.service` followed by `sudo systemctl start your-service.service` to resume.

This behavior prevents a misconfigured service (for example, one with an invalid model path) from burning CPU in an infinite tight-restart loop. The `journalctl -u your-service.service -n 50` output will show exactly what went wrong in the last few attempts.

To override the start limit for a deliberate manual restart after fixing a problem:

```bash
sudo systemctl reset-failed llm-server.service
sudo systemctl start llm-server.service
```

### systemd Timers: The Modern Cron

systemd timers replace cron jobs with a more robust, observable scheduling mechanism. A timer is a `.timer` unit file paired with a `.service` unit file that it activates.

Advantages over cron:

- Missed jobs are caught up after boot (configurable with `Persistent=true`).
- All output goes to `journald` automatically — no more lost cron emails.
- `systemctl list-timers` shows exactly when each timer last ran and when it will run next.
- Resource limits defined in the `.service` file apply to scheduled runs too.

**Creating a timer pair.**

Example: run a model cache cleanup script every night at 2:00 AM.

Step 1 — The service file `/etc/systemd/system/model-cleanup.service`:

```ini
[Unit]
Description=Clean up stale LLM model cache files
After=local-fs.target

[Service]
Type=oneshot
User=llmserver
ExecStart=/opt/llm-server/scripts/cleanup_model_cache.sh
StandardOutput=journal
StandardError=journal
SyslogIdentifier=model-cleanup
```

Note `Type=oneshot` — this is the correct type for a task that runs to completion. The service is considered active while the script is running and returns to inactive when it exits.

Step 2 — The timer file `/etc/systemd/system/model-cleanup.timer`:

```ini
[Unit]
Description=Nightly LLM model cache cleanup

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

- **`OnCalendar=`** uses systemd's calendar event syntax. `*-*-* 02:00:00` means every day at 02:00:00. See the calendar syntax table below.
- **`Persistent=true`** — if the machine was off at 2:00 AM, run the job the next time it boots.
- **`RandomizedDelaySec=300`** — add a random delay of 0–300 seconds. Prevents thundering-herd problems when many timers are set to the same clock time.

Enable and start the timer (not the service — timers activate services automatically):

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now model-cleanup.timer
```

**systemd calendar syntax examples:**

| Expression | Meaning |
|---|---|
| `*-*-* 02:00:00` | Every day at 2:00 AM |
| `Mon *-*-* 03:00:00` | Every Monday at 3:00 AM |
| `*-*-1 00:00:00` | First day of every month at midnight |
| `*-*-* 00/6:00:00` | Every 6 hours |
| `hourly` | Shorthand for `*-*-* *:00:00` |
| `daily` | Shorthand for `*-*-* 00:00:00` |
| `weekly` | Shorthand for `Mon *-*-* 00:00:00` |
| `monthly` | Shorthand for `*-*-1 00:00:00` |

**`OnBootSec=` and `OnUnitActiveSec=` for interval-based timers:**

```ini
[Timer]
# Run 5 minutes after boot, then every 30 minutes
OnBootSec=5min
OnUnitActiveSec=30min
```

**Inspecting timers:**

```bash
# List all active timers with their next/last activation times
systemctl list-timers

# Test a calendar expression before deploying it
systemd-analyze calendar "*-*-* 02:00:00"
```

### Cron Basics

Cron remains widely used and is simpler for basic scheduling tasks. Understanding it is essential because you will encounter it in legacy systems, Docker containers without systemd, and cloud infrastructure.

The `crontab -e` command opens your user's crontab for editing. Each line defines one scheduled job:

```
# ┌───── minute (0–59)
# │ ┌───── hour (0–23)
# │ │ ┌───── day of month (1–31)
# │ │ │ ┌───── month (1–12)
# │ │ │ │ ┌───── day of week (0–7, 0 and 7 are Sunday)
# │ │ │ │ │
# * * * * *  command to execute
```

Common crontab patterns:

```bash
# Run a script every day at 2:30 AM
30 2 * * * /opt/llm-server/scripts/cleanup_model_cache.sh

# Run every hour at minute 0
0 * * * * /opt/llm-server/scripts/health_check.sh

# Run every 15 minutes
*/15 * * * * /opt/llm-server/scripts/metrics_push.sh

# Run on the first day of every month at midnight
0 0 1 * * /opt/llm-server/scripts/monthly_report.sh

# Run every weekday (Mon–Fri) at 8:00 AM
0 8 * * 1-5 /opt/llm-server/scripts/warm_up_model.sh

# Redirect output to a log file (cron does not auto-capture stdout)
0 3 * * * /opt/scripts/backup.sh >> /var/log/backup.log 2>&1
```

Useful crontab syntax shortcuts recognized by most cron implementations:

| Shortcut | Equivalent |
|---|---|
| `@reboot` | Run once at startup |
| `@hourly` | `0 * * * *` |
| `@daily` | `0 0 * * *` |
| `@weekly` | `0 0 * * 0` |
| `@monthly` | `0 0 1 * *` |
| `@yearly` | `0 0 1 1 *` |

```bash
# Run a model warm-up on every reboot
@reboot /opt/llm-server/scripts/warm_up_model.sh
```

The system-wide crontab is at `/etc/crontab` and includes a `user` field as the sixth column before the command. Drop-in files can be placed in `/etc/cron.d/`. The `root` crontab is edited with `sudo crontab -e`.

A key limitation of cron: output is emailed to the system user unless you redirect it explicitly with `>> /path/to/logfile 2>&1`. This makes debugging failed cron jobs much harder than debugging failed systemd services. For new AI infrastructure, prefer systemd timers.

## Best Practices

1. **Always run AI services as a dedicated non-root system user.** Create a `llmserver` (or `ollama`, etc.) system account with `useradd --system` and specify `User=` and `Group=` in the `[Service]` section. If a vulnerability in the inference code or a loaded model is exploited, the attacker is constrained to that user's privileges rather than gaining root access.

2. **Use `EnvironmentFile=` for secrets, never inline `Environment=` for credentials.** An inline `Environment="HF_TOKEN=secret"` is visible in `systemctl show` output and in process listings. An `EnvironmentFile=` pointing to a root-owned, mode `640` file keeps secrets out of logs and ps output.

3. **Set `LimitNOFILE=` to at least 65536 for any ML workload.** Memory-mapped model weights, PyTorch's shared memory, and ONNX Runtime's thread pools all open many file descriptors. The default kernel limit of 1024 will cause mysterious failures under load. The symptom is always a logged `OSError: [Errno 24] Too many open files`.

4. **Set `MemoryMax=` to slightly below available RAM.** An inference server without a memory ceiling will eventually OOM-kill other processes including sshd, making the server unreachable. With `MemoryMax=` set, the inference process is OOM-killed in isolation and systemd restarts it per the `Restart=` policy.

5. **Use `Restart=always` with `RestartSec=5` and define a `StartLimitBurst=`.** `Restart=always` ensures recovery from crashes. `RestartSec=5` prevents CPU spin from a process that exits immediately on every start. `StartLimitBurst=` is the circuit breaker that stops the loop if the service cannot start at all, alerting you that operator intervention is needed.

6. **Always run `sudo systemctl daemon-reload` after editing any unit file.** Changes to a `.service` file in `/etc/systemd/system/` are silently ignored until systemd re-reads its configuration. This is the single most common source of confusion for new systemd users: editing the file and not seeing the change take effect.

7. **Use `journalctl -u your-service -f` as your primary debugging tool.** The `-f` flag follows the log in real time. When a service fails to start, run `journalctl -u your-service -n 100` immediately after to see the last 100 log lines including the failure reason. This is faster and more complete than looking for scattered log files.

8. **Prefer systemd timers over cron for new AI infrastructure.** Timers are observable (`systemctl list-timers`), recoverable after missed runs (`Persistent=true`), and automatically ship logs to `journald`. The only reason to use cron is compatibility with existing systems or when systemd is not available (minimal containers, BSD systems).

9. **Validate unit file syntax before reloading.** Run `systemd-analyze verify /etc/systemd/system/your-service.service` to catch syntax errors and common configuration mistakes before they cause a service failure. On older systemd versions that do not have this subcommand, `systemctl status` will report the parse error after `daemon-reload`.

10. **Pin the `ExecStart=` binary to an absolute path within a virtual environment.** Writing `ExecStart=/opt/llm-server/venv/bin/uvicorn ...` rather than `ExecStart=uvicorn ...` guarantees that the correct, isolated Python environment is used, independent of `PATH` settings, regardless of which user's shell environment is active.

## Use Cases

### Use Case 1: Deploying Ollama as a System Service

A developer has installed Ollama and wants it to start automatically when the server reboots and to restart if it crashes, rather than starting it manually each session.

- **Problem:** Running `ollama serve` in a terminal session means the process dies when the SSH session closes, and it does not survive reboots.
- **Concepts applied:** Writing a `.service` unit file, `User=ollama`, `Restart=always`, `systemctl enable --now`, `journalctl -u ollama -f`
- **Expected outcome:** Ollama starts on every boot, restarts within 5 seconds of a crash, and its logs are queryable from `journalctl` at any time.

### Use Case 2: Running a FastAPI LLM Server in Production

A team has built a FastAPI endpoint that wraps a local LLaMA model with Uvicorn and wants it deployed reliably on a GPU server, with environment-specific configuration (model path, GPU device, API token) kept separate from the unit file.

- **Problem:** The server needs to start on boot, use a specific Python virtual environment, read secrets from a file, and stay within the GPU server's RAM budget.
- **Concepts applied:** `EnvironmentFile=`, `WorkingDirectory=`, absolute `ExecStart=` path to venv, `MemoryMax=`, `LimitNOFILE=`, `User=llmserver`
- **Expected outcome:** The service starts cleanly on boot using the configured virtual environment and model path, is bounded to 14 GB of RAM, and secrets are never exposed in `systemctl show` output.

### Use Case 3: Scheduling Nightly Model Cache Cleanup

Model artifacts, temporary inference files, and partially downloaded weights accumulate over time. The team wants a cleanup script to run nightly at 2 AM without setting up a separate cron daemon.

- **Problem:** Cron job output is not captured anywhere useful; if the job fails silently, no one notices until disk space is exhausted.
- **Concepts applied:** `Type=oneshot` service, paired `.timer` unit, `OnCalendar=*-*-* 02:00:00`, `Persistent=true`, `systemctl list-timers`
- **Expected outcome:** The cleanup script runs nightly, its output is visible in `journalctl -u model-cleanup`, and if the server was off at 2 AM, the job runs at next boot.

### Use Case 4: Configuring a Health-Check Service with Dependency Ordering

The inference server depends on a local vector database (Qdrant) that must be fully up before the inference server accepts connections.

- **Problem:** If both services start in parallel and the inference server boots faster, it fails to connect to Qdrant on startup and crashes, even though Qdrant is fine.
- **Concepts applied:** `After=qdrant.service`, `Requires=qdrant.service`, service dependency ordering, `Restart=always` as a fallback
- **Expected outcome:** systemd starts Qdrant first; the inference server only starts after Qdrant has reached an active state. If Qdrant is stopped, the inference server also stops.

## Hands-on Examples

### Example 1: Install and Inspect the Ollama System Service

Ollama ships its own systemd unit file when installed via its official install script. This example shows you how to inspect and manage it, which teaches the same skills you will apply to your own custom services.

1. Install Ollama using the official install script (skip if already installed):

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

The installer creates `/etc/systemd/system/ollama.service` and enables it automatically.

2. Verify the service file was installed and inspect its contents:

```bash
cat /etc/systemd/system/ollama.service
```

Expected output (structure will resemble):
```
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

[Install]
WantedBy=default.target
```

3. Check the service status:

```bash
sudo systemctl status ollama.service
```

Expected output:
```
● ollama.service - Ollama Service
     Loaded: loaded (/etc/systemd/system/ollama.service; enabled; vendor preset: enabled)
     Active: active (running) since Thu 2026-04-10 09:15:28 UTC; 2min 14s ago
   Main PID: 1823 (ollama)
      Tasks: 14 (limit: 4699)
     Memory: 512.3M
        CPU: 1.234s
     CGroup: /system.slice/ollama.service
             └─1823 /usr/local/bin/ollama serve
```

4. Follow the live logs:

```bash
journalctl -u ollama.service -f
```

Open a second terminal and run a model pull to generate log activity:

```bash
ollama pull llama3.2:1b
```

Watch the download progress appear in the journal stream. Press `Ctrl+C` to stop following.

5. Query recent logs with a time filter:

```bash
journalctl -u ollama.service --since "5 minutes ago"
```

6. Restart the service and observe it coming back:

```bash
sudo systemctl restart ollama.service
journalctl -u ollama.service -n 20
```

Expected: log entries show the service stopping and then restarting, with a new PID.

7. Check boot-enabled status:

```bash
systemctl is-enabled ollama.service
```

Expected output:
```
enabled
```

---

### Example 2: Write and Deploy a Custom FastAPI LLM Server Service

You have a FastAPI application that serves a text generation endpoint. You will write its unit file from scratch, deploy it, and verify it with `systemctl` and `journalctl`.

**Setup: create the application.**

1. Create the user and application directory:

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin llmserver
sudo mkdir -p /opt/llm-server/scripts
sudo chown -R llmserver:llmserver /opt/llm-server
```

2. Create a Python virtual environment and install dependencies:

```bash
sudo -u llmserver python3 -m venv /opt/llm-server/venv
sudo -u llmserver /opt/llm-server/venv/bin/pip install fastapi uvicorn
```

3. Create the application file `/opt/llm-server/app/__init__.py` (empty):

```bash
sudo mkdir -p /opt/llm-server/app
sudo touch /opt/llm-server/app/__init__.py
sudo chown -R llmserver:llmserver /opt/llm-server/app
```

4. Create the main application file `/opt/llm-server/app/main.py`:

```python
# /opt/llm-server/app/main.py
import os
import logging
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Inference Server", version="1.0.0")

class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 200

@app.get("/health")
async def health():
    model_path = os.environ.get("MODEL_PATH", "not configured")
    logger.info("Health check requested")
    return {"status": "ok", "model_path": model_path}

@app.post("/generate")
async def generate(request: GenerateRequest):
    model_path = os.environ.get("MODEL_PATH", "not configured")
    logger.info("Generate request: prompt length=%d", len(request.prompt))
    # In production, this would call Ollama or a local inference engine
    return {
        "prompt": request.prompt,
        "response": f"[Model at {model_path}] Echo: {request.prompt}",
        "tokens_generated": min(len(request.prompt), request.max_tokens)
    }
```

```bash
sudo chown llmserver:llmserver /opt/llm-server/app/main.py
```

**Deploy: write the environment file.**

5. Create the configuration directory and environment file:

```bash
sudo mkdir -p /etc/llm-server
sudo tee /etc/llm-server/env > /dev/null <<'EOF'
MODEL_PATH=/opt/models/llama3-8b-instruct
LOG_LEVEL=info
MAX_WORKERS=2
EOF
sudo chmod 640 /etc/llm-server/env
sudo chown root:llmserver /etc/llm-server/env
```

**Deploy: write the unit file.**

6. Create `/etc/systemd/system/llm-server.service`:

```bash
sudo tee /etc/systemd/system/llm-server.service > /dev/null <<'EOF'
[Unit]
Description=FastAPI LLM Inference Server
Documentation=https://github.com/yourorg/llm-server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=llmserver
Group=llmserver
WorkingDirectory=/opt/llm-server

ExecStart=/opt/llm-server/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

Restart=always
RestartSec=5
StartLimitIntervalSec=120
StartLimitBurst=5

EnvironmentFile=/etc/llm-server/env

LimitNOFILE=65536
MemoryMax=8G

StandardOutput=journal
StandardError=journal
SyslogIdentifier=llm-server

[Install]
WantedBy=multi-user.target
EOF
```

7. Reload systemd, start the service, and enable it for boot:

```bash
sudo systemctl daemon-reload
sudo systemctl start llm-server.service
sudo systemctl enable llm-server.service
```

8. Check the service came up:

```bash
sudo systemctl status llm-server.service
```

Expected output (key lines):
```
● llm-server.service - FastAPI LLM Inference Server
     Loaded: loaded (/etc/systemd/system/llm-server.service; enabled; ...)
     Active: active (running) since ...
   Main PID: 4217 (uvicorn)
     Memory: 84.2M (max: 8.0G available: 7.9G)
```

9. Test the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected output:
```json
{"status":"ok","model_path":"/opt/models/llama3-8b-instruct"}
```

10. View the service logs:

```bash
journalctl -u llm-server.service -n 30
```

Expected output includes uvicorn startup lines such as:
```
Apr 10 09:30:01 hostname llm-server[4217]: INFO:     Started server process [4217]
Apr 10 09:30:01 hostname llm-server[4217]: INFO:     Application startup complete.
Apr 10 09:30:01 hostname llm-server[4217]: INFO:     Uvicorn running on http://0.0.0.0:8000
```

11. Test the auto-restart. Find the main PID and send SIGKILL to simulate a crash:

```bash
# Get the PID
systemctl show llm-server.service --property=MainPID

# Kill the process (replace 4217 with the actual PID)
sudo kill -9 4217

# Wait 6 seconds (RestartSec=5) then check status
sleep 6
sudo systemctl status llm-server.service
```

Expected: the service is `active (running)` with a new PID. The journal will show an entry like `Process: 4217 ExecStart=... (code=killed, signal=KILL)` followed by `Started FastAPI LLM Inference Server`.

---

### Example 3: Configure Resource Limits and Verify Them

Building on Example 2, you will add resource limits to the service and verify they are applied to the live cgroup.

1. Edit the service file to tighten the memory limit and add a CPU quota:

```bash
sudo systemctl edit llm-server.service
```

This opens a drop-in override editor. Add the following content (drop-in files override only the directives you specify, leaving the rest of the base unit file unchanged):

```ini
[Service]
MemoryMax=4G
CPUQuota=150%
LimitNOFILE=131072
```

Save and exit. systemd automatically places this in `/etc/systemd/system/llm-server.service.d/override.conf` and runs `daemon-reload`.

2. Restart the service to apply the new limits:

```bash
sudo systemctl restart llm-server.service
```

3. Verify the effective limits via `systemctl show`:

```bash
systemctl show llm-server.service | grep -E "MemoryMax|CPUQuota|LimitNOFILE"
```

Expected output:
```
LimitNOFILE=131072
MemoryMax=4294967296
CPUQuotaPerSecUSec=1500000
```

(`4294967296` bytes = 4 GiB; `1500000` microseconds per second = 150% CPU.)

4. Inspect the live cgroup memory limit:

```bash
# On a system using cgroups v2 (most modern distros):
sudo cat /sys/fs/cgroup/system.slice/llm-server.service/memory.max
```

Expected output:
```
4294967296
```

---

### Example 4: Create a systemd Timer for Scheduled Model Cache Cleanup

You will create a timer that runs a cache cleanup script every night at 2:00 AM, with catchup enabled so a missed run executes at next boot.

1. Create the cleanup script:

```bash
sudo tee /opt/llm-server/scripts/cleanup_model_cache.sh > /dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

CACHE_DIR="/tmp/llm-inference-cache"
MAX_AGE_DAYS=2

echo "Starting model cache cleanup at $(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [ -d "$CACHE_DIR" ]; then
    DELETED=$(find "$CACHE_DIR" -type f -mtime +${MAX_AGE_DAYS} -print -delete | wc -l)
    echo "Deleted ${DELETED} stale cache files older than ${MAX_AGE_DAYS} days"
else
    echo "Cache directory ${CACHE_DIR} does not exist; nothing to clean"
fi

echo "Cleanup complete"
EOF
sudo chmod 750 /opt/llm-server/scripts/cleanup_model_cache.sh
sudo chown llmserver:llmserver /opt/llm-server/scripts/cleanup_model_cache.sh
```

2. Create the oneshot service unit `/etc/systemd/system/model-cleanup.service`:

```bash
sudo tee /etc/systemd/system/model-cleanup.service > /dev/null <<'EOF'
[Unit]
Description=Clean stale LLM inference cache files
After=local-fs.target

[Service]
Type=oneshot
User=llmserver
Group=llmserver
ExecStart=/opt/llm-server/scripts/cleanup_model_cache.sh
StandardOutput=journal
StandardError=journal
SyslogIdentifier=model-cleanup
EOF
```

3. Create the timer unit `/etc/systemd/system/model-cleanup.timer`:

```bash
sudo tee /etc/systemd/system/model-cleanup.timer > /dev/null <<'EOF'
[Unit]
Description=Nightly LLM inference cache cleanup timer

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF
```

4. Reload, enable, and start the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now model-cleanup.timer
```

5. Verify the timer is scheduled:

```bash
systemctl list-timers model-cleanup.timer
```

Expected output:
```
NEXT                        LEFT          LAST PASSED UNIT                  ACTIVATES
Fri 2026-04-11 02:03:47 UTC 14h left      n/a  n/a    model-cleanup.timer   model-cleanup.service
```

6. Run the service immediately to test it without waiting for the timer:

```bash
sudo systemctl start model-cleanup.service
```

7. View the output in the journal:

```bash
journalctl -u model-cleanup.service
```

Expected output:
```
Apr 10 09:45:01 hostname model-cleanup[5102]: Starting model cache cleanup at 2026-04-10T09:45:01Z
Apr 10 09:45:01 hostname model-cleanup[5102]: Cache directory /tmp/llm-inference-cache does not exist; nothing to clean
Apr 10 09:45:01 hostname model-cleanup[5102]: Cleanup complete
```

8. Validate the calendar expression syntax:

```bash
systemd-analyze calendar "*-*-* 02:00:00"
```

Expected output:
```
  Original form: *-*-* 02:00:00
Normalized form: *-*-* 02:00:00
    Next elapse: Fri 2026-04-11 02:00:00 UTC
       (in UTC): Fri 2026-04-11 02:00:00 UTC
       From now: 14h 14min left
```

## Common Pitfalls

### Pitfall 1: Editing a Unit File But Forgetting `daemon-reload`

**Description:** An operator edits `/etc/systemd/system/llm-server.service` to change a memory limit or fix a path, then restarts the service — but the old configuration is still in effect.

**Why it happens:** systemd caches unit file contents in memory. Until `daemon-reload` is called, systemd continues using the cached version, ignoring the file on disk entirely. Restarting the service applies the cached (old) configuration.

**Incorrect pattern:**
```bash
sudo nano /etc/systemd/system/llm-server.service
# (change MemoryMax from 8G to 14G)
sudo systemctl restart llm-server.service
# MemoryMax is still 8G — the edit was ignored
```

**Correct pattern:**
```bash
sudo nano /etc/systemd/system/llm-server.service
sudo systemctl daemon-reload
sudo systemctl restart llm-server.service
# MemoryMax is now 14G
```

---

### Pitfall 2: Confusing `systemctl start` with `systemctl enable`

**Description:** A developer starts a service with `systemctl start`, reboots the server for kernel updates, and finds the AI inference service is not running. They had never enabled it.

**Why it happens:** `start` and `enable` are orthogonal operations. `start` runs the service right now. `enable` creates the symlink that makes the service start on boot. Neither implies the other.

**Incorrect pattern:**
```bash
sudo systemctl start llm-server.service
# Server reboots; llm-server is not running
```

**Correct pattern:**
```bash
# Start now AND configure to start on every future boot
sudo systemctl enable --now llm-server.service
```

---

### Pitfall 3: Using a Relative Path in `ExecStart=`

**Description:** A unit file contains `ExecStart=uvicorn app.main:app --port 8000`. The service fails to start with `No such file or directory` or starts the wrong binary from an unexpected location.

**Why it happens:** systemd does not invoke a shell to run `ExecStart=`. There is no `$PATH` resolution by default. The executable must be specified as an absolute path.

**Incorrect pattern:**
```ini
[Service]
ExecStart=uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Correct pattern:**
```ini
[Service]
ExecStart=/opt/llm-server/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

### Pitfall 4: Running the Service as Root

**Description:** A unit file omits `User=` and `Group=`, so the service runs as root. When the LLM server is exposed to the network, any remote code execution vulnerability in the model serving code gives an attacker root access to the machine.

**Why it happens:** If `User=` is omitted, systemd defaults to running the service as `root`. The dangerous default is silent.

**Incorrect pattern:**
```ini
[Service]
ExecStart=/opt/llm-server/venv/bin/uvicorn app.main:app --port 8000
# Runs as root — no User= specified
```

**Correct pattern:**
```bash
# Create the service user first
sudo useradd --system --no-create-home --shell /usr/sbin/nologin llmserver
```
```ini
[Service]
User=llmserver
Group=llmserver
ExecStart=/opt/llm-server/venv/bin/uvicorn app.main:app --port 8000
```

---

### Pitfall 5: `Restart=always` Without `StartLimitBurst=`

**Description:** A service has a bad configuration — for example, the model file path is wrong. With `Restart=always` and no start limit, systemd restarts the process hundreds of times per minute, consuming CPU and flooding the journal with thousands of identical error messages.

**Why it happens:** `Restart=always` restarts unconditionally. Without a burst limit, there is no circuit breaker.

**Incorrect pattern:**
```ini
[Service]
Restart=always
RestartSec=1
# No StartLimitBurst — will restart indefinitely if misconfigured
```

**Correct pattern:**
```ini
[Service]
Restart=always
RestartSec=5
StartLimitIntervalSec=120
StartLimitBurst=5
# After 5 failures in 120 seconds, systemd marks the unit failed and stops
```

---

### Pitfall 6: Storing Secrets in `Environment=` Directives

**Description:** An API key or Hugging Face token is placed directly in the `[Service]` section as `Environment="HF_TOKEN=hf_xxxx"`. This value is visible to any user who can run `systemctl show llm-server.service` or read `/proc/<pid>/environ`.

**Why it happens:** `Environment=` is the simplest way to pass variables, and beginners do not realize the value is exposed.

**Incorrect pattern:**
```ini
[Service]
Environment="HF_TOKEN=hf_abcdefghijklmnop"
```

**Correct pattern:**
```bash
# Write the secret to a file readable only by root and the service user
sudo tee /etc/llm-server/env > /dev/null <<'EOF'
HF_TOKEN=hf_abcdefghijklmnop
EOF
sudo chmod 640 /etc/llm-server/env
sudo chown root:llmserver /etc/llm-server/env
```
```ini
[Service]
EnvironmentFile=/etc/llm-server/env
```

---

### Pitfall 7: Enabling the .service File Instead of the .timer File

**Description:** A developer creates a `model-cleanup.timer` / `model-cleanup.service` pair and runs `systemctl enable model-cleanup.service` instead of `systemctl enable model-cleanup.timer`. The service is now wired into `multi-user.target` and runs on every boot as a foreground `oneshot`, rather than on schedule.

**Why it happens:** `enable` on a service is the natural reflex; the distinction between enabling the timer vs. the service is non-obvious.

**Incorrect pattern:**
```bash
sudo systemctl enable model-cleanup.service
# Now runs on every boot, not on the timer schedule
```

**Correct pattern:**
```bash
# Enable and start the TIMER, not the service
sudo systemctl enable --now model-cleanup.timer
# The timer will activate the service on schedule
```

---

### Pitfall 8: Forgetting `2>&1` in Cron Jobs

**Description:** A cron job fails silently. The developer checks the crontab, sees the job is scheduled, but finds no log output anywhere and no indication of failure.

**Why it happens:** By default, cron mails output to the local system user. On servers without a mail agent configured, this output is discarded. Errors on stderr are swallowed without a trace.

**Incorrect pattern:**
```crontab
0 2 * * * /opt/llm-server/scripts/cleanup_model_cache.sh
# stdout goes to /dev/null or system mail; stderr is also lost
```

**Correct pattern:**
```crontab
0 2 * * * /opt/llm-server/scripts/cleanup_model_cache.sh >> /var/log/model-cleanup.log 2>&1
```

Or, better, switch the job to a systemd timer where `journald` captures all output automatically.

## Summary

- systemd is the init system on all major modern Linux distributions. It manages service lifecycle, boot ordering, logging, and scheduled tasks through declarative unit files in `/etc/systemd/system/`.
- `systemctl start/stop/restart/enable/disable/status` are the five core verbs for managing services. Enabling and starting are separate operations: enable configures boot persistence; start runs the service now.
- `daemon-reload` must be run after every edit to a unit file, before the change takes effect.
- A `.service` unit file's `[Service]` section controls the process type (`Type=`), the command (`ExecStart=`), the user it runs as (`User=`), restart behavior (`Restart=always`, `RestartSec=`, `StartLimitBurst=`), environment variables (`Environment=`, `EnvironmentFile=`), resource limits (`LimitNOFILE=`, `MemoryMax=`), and log routing (`SyslogIdentifier=`).
- `journalctl -u service-name -f` is the primary tool for debugging a service. Filter by unit, time range, or priority to focus on relevant events.
- systemd timers replace cron with observable, journal-integrated scheduling. A timer file activates a paired `oneshot` service on a calendar schedule. `Persistent=true` catches up missed runs after downtime.
- Cron remains useful and widely deployed; the five-field `minute hour day-of-month month day-of-week command` syntax and `@reboot`/`@daily` shortcuts are essential knowledge for working with existing systems.

## Further Reading

- [systemd.service(5) — freedesktop.org Man Page](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html) — The authoritative reference for every directive in the `[Unit]`, `[Service]`, and `[Install]` sections of a service unit file; the definitive source for `Restart=`, `ExecStart=`, `Type=`, and all resource control options.
- [systemd.timer(5) — freedesktop.org Man Page](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html) — Complete reference for timer unit files including all `OnCalendar=`, `OnBootSec=`, `OnUnitActiveSec=`, and `Persistent=` directives with behavioral details and examples.
- [journalctl(1) — freedesktop.org Man Page](https://www.freedesktop.org/software/systemd/man/latest/journalctl.html) — Full reference for every `journalctl` flag and output format including JSON output, priority filtering, cursor-based pagination, and remote journal access.
- [systemd Calendar and Time Span Syntax — freedesktop.org](https://www.freedesktop.org/software/systemd/man/latest/systemd.time.html) — Explains the full calendar event syntax used in `OnCalendar=` and the time span syntax used in `OnBootSec=`, `RestartSec=`, and related directives; essential before writing any non-trivial timer.
- [Ollama systemd Service Documentation — Ollama GitHub](https://github.com/ollama/ollama/blob/main/docs/linux.md) — Official guidance from the Ollama project for running Ollama as a systemd service on Linux, including GPU passthrough configuration, `EnvironmentFile=` usage for proxy settings, and the default unit file structure shipped by the installer.
- [DigitalOcean: How To Use systemctl to Manage systemd Services and Units](https://www.digitalocean.com/community/tutorials/how-to-use-systemctl-to-manage-systemd-services-and-units) — A practitioner-oriented tutorial with worked examples for every common `systemctl` operation; includes coverage of masking units, target management, and reading `systemctl show` output.
- [Red Hat: Using systemd Unit Files to Customize and Optimize Your System — RHEL 9 Docs](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_systemd_unit_files_to_customize_and_optimize_your_system/index) — Red Hat's production-focused documentation for systemd unit files on RHEL 9 / Rocky 9 / Alma 9, covering drop-in overrides (`systemctl edit`), security hardening directives (`PrivateTmp=`, `NoNewPrivileges=`, `ProtectSystem=`), and resource management — directly applicable to AI server deployments.
- [Arch Linux Wiki: systemd](https://wiki.archlinux.org/title/systemd) — One of the most comprehensive community-maintained references for systemd; covers topics not found in man pages including practical troubleshooting workflows, journal disk usage management, and the systemd user session model.
