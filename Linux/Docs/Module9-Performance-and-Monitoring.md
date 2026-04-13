# Module 9: Performance and Monitoring
> Subject: Linux | Difficulty: Intermediate | Estimated Time: 240 minutes

## Objective

After completing this module, you will be able to observe and interpret CPU, memory, disk I/O, and network metrics on a Linux server running AI inference workloads. You will use `htop`, `top`, `vmstat`, and `free` to identify CPU saturation and memory pressure; use `nvidia-smi`, `nvtop`, and `watch` to track GPU utilization, VRAM consumption, and thermal throttling; diagnose disk I/O bottlenecks with `iostat` and `iotop`; measure network throughput per process with `iftop`, `nethogs`, and `ss`; aggregate and query structured logs with `journald` and `journalctl`; configure `logrotate` to manage log files produced by long-running AI services; deploy Prometheus `node_exporter` and a GPU exporter to expose server metrics; build a Grafana dashboard that surfaces GPU utilization and inference request latency side by side; understand alerting concepts including threshold-based and anomaly-based rules; apply CPU frequency governor settings, NUMA-aware process placement, and huge pages to reduce inference latency; and profile slow inference paths with `py-spy` and identify where to apply NVIDIA Nsight Systems (`nsys`) profiling.

## Prerequisites

- Completed Module 1 through Module 8 of this Linux series — you should be comfortable with the shell, process management, systemd services, file permissions, and package management
- A Linux server with at minimum one NVIDIA GPU (driver version 535 or later recommended); examples marked `[GPU]` require an NVIDIA card and will be clearly noted — CPU-only learners can follow the conceptual explanations and skip the GPU-specific commands
- Python 3.10 or later installed (used in profiling examples)
- `curl` and `wget` available on the system
- Basic familiarity with YAML syntax (used in Prometheus and Grafana configuration)
- Root or `sudo` access for performance tuning sections

## Key Concepts

### Why AI Inference Workloads Demand Specialized Monitoring

A traditional web server is CPU-bound: requests arrive, the CPU computes a response, and the metric that matters is CPU utilization and request queue depth. AI inference is fundamentally different. The hot path runs almost entirely on the GPU, and the GPU has its own scheduler, its own memory hierarchy (VRAM, L2 cache, shared memory, registers), and thermal dynamics that determine whether it runs at full speed or throttles itself to stay within power limits.

The most common symptom is deceptively mundane: **GPU utilization is low while inference is slow**. Diagnosing this requires answering a sequence of questions in order:

```
Is the GPU being fed data fast enough?
  └─ NO → CPU preprocessing / tokenization is the bottleneck
       └─ Check: htop (single-core saturation), py-spy (Python hot path)
  └─ YES → Is VRAM full?
         └─ YES → Model weights + KV-cache do not fit; batch size too large
              └─ Check: nvidia-smi (memory-used vs memory-total)
         └─ NO → Is the GPU actually computing?
                └─ NO → PCIe bandwidth stall or CUDA synchronization overhead
                     └─ Check: nsys (CUDA API timeline), nvidia-smi pmon
                └─ YES → Is it throttling?
                      └─ Check: nvidia-smi --query-gpu=clocks_throttle_reasons
```

Understanding this diagnostic tree guides which tools to reach for first. The sections below walk through each layer of the stack in this order: CPU/memory, GPU, disk I/O, network, logs, metrics collection, visualization, and tuning.

---

### CPU and Memory Monitoring

#### top

`top` is present on every Linux distribution and requires no installation. It refreshes every three seconds by default and shows a summary header followed by a per-process table sorted by CPU usage.

```
top - 14:32:07 up 3 days,  2:11,  2 users,  load average: 4.21, 3.87, 3.50
Tasks: 312 total,   2 running, 310 sleeping,   0 stopped,   0 zombie
%Cpu(s): 37.2 us,  2.1 sy,  0.0 ni, 58.4 id,  1.8 wa,  0.0 hi,  0.5 si
MiB Mem :  64006.8 total,   8431.2 free,  48320.4 used,   7255.2 buff/cache
MiB Swap:   8192.0 total,   7914.3 free,    277.7 used.  14200.0 avail Mem
```

The header fields that matter most for AI workloads:

| Field | Meaning | AI Inference Signal |
|---|---|---|
| `load average` | 1, 5, 15-minute run-queue depth | Values consistently above CPU count mean CPU saturation |
| `us` (user) | CPU time in user-space | High = preprocessing or Python overhead |
| `sy` (system) | CPU time in kernel | High = excessive syscalls, often I/O or memory allocation |
| `wa` (iowait) | CPU time waiting for I/O | High = disk read of model weights or dataset |
| `si` (softirq) | Interrupt handling | High = heavy network traffic (streaming inference requests) |
| `buff/cache` | Kernel page cache | Large values are healthy; they speed up repeated model loads |
| `avail Mem` | Estimated allocatable memory | This — not `free` — is the number to watch for OOM risk |

Key interactive keystrokes in `top`:

| Key | Action |
|---|---|
| `1` | Toggle per-CPU display (reveals single-core saturation) |
| `M` | Sort by memory usage |
| `P` | Sort by CPU usage (default) |
| `H` | Toggle thread display (important for multi-threaded inference servers) |
| `f` | Field manager — add columns such as VIRT, RES, SHR, nTH |
| `u` | Filter by username (e.g., show only the inference service user) |
| `k` | Kill a process by PID |
| `q` | Quit |

```bash
# Run top with a refresh interval of 1 second, showing threads
top -d 1 -H

# Run non-interactively, capture 5 iterations to a file for later analysis
top -b -n 5 > /tmp/top-snapshot.txt
```

#### htop

`htop` is an enhanced interactive process viewer that adds color, a horizontal CPU bar per core, mouse support, and a friendlier interface for filtering and killing processes.

```bash
# Install htop (Debian/Ubuntu)
sudo apt install htop

# Install htop (RHEL/Rocky/AlmaLinux)
sudo dnf install htop

# Launch
htop
```

The per-CPU bars at the top of `htop` are the most actionable view for AI workloads. When a multi-threaded tokenizer or preprocessor saturates a single core, you will see one bar pinned at 100% while all others are idle. This is the signal that the bottleneck is not parallelism but single-threaded CPU code.

Key `htop` keybindings:

| Key | Action |
|---|---|
| `F2` | Setup — configure columns, color scheme, meters |
| `F3` / `/` | Search processes by name |
| `F4` | Filter processes by name (persists during session) |
| `F5` | Toggle tree view (shows parent-child relationships) |
| `F6` | Sort by any column |
| `F9` | Send signal to process (choose SIGTERM, SIGKILL, etc.) |
| `Space` | Tag a process for bulk operations |
| `t` | Toggle tree / flat view |
| `H` | Toggle user threads |
| `K` | Toggle kernel threads |

```bash
# Launch htop showing only processes owned by a specific user
htop -u inference_user

# Launch with a specific delay between refreshes (in tenths of a second)
htop -d 5
```

#### vmstat

`vmstat` reports virtual memory, CPU, and I/O statistics in a compact columnar format. It is particularly useful for spotting memory pressure, swap activity, and context-switch storms that are invisible in `top`.

```bash
# Print a new line every 2 seconds (runs until interrupted)
vmstat 2

# Print 10 iterations then exit
vmstat 2 10

# Include timestamps
vmstat -t 2
```

Sample output and field meanings:

```
procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu-----
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st
 3  0  28416 412800  65536 7200000    2    0   128    64 4200 9800 38  3 57  2  0
```

| Column | Meaning | Warning Level for AI Workloads |
|---|---|---|
| `r` | Processes waiting for CPU (run queue) | Sustained > number of cores = CPU saturation |
| `b` | Processes in uninterruptible sleep (I/O wait) | Any sustained value > 0 is worth investigating |
| `swpd` | Virtual memory used (kB) | Any non-zero value during inference means RAM exhaustion |
| `si` / `so` | Swap-in / swap-out rate (kB/s) | Non-zero `so` means the system is actively swapping out — severe performance impact |
| `bi` / `bo` | Block device reads / writes (blocks/s) | High `bi` during inference = model weights being read from disk |
| `in` | Interrupts per second | Sudden spike can indicate a runaway device |
| `cs` | Context switches per second | Extremely high values (> 500k/s) suggest lock contention |
| `us` / `sy` / `id` / `wa` | CPU breakdown: user / system / idle / iowait | Same as `top` |

#### free

`free` provides a one-shot snapshot of memory usage. Despite its simplicity, it is routinely misread.

```bash
# Human-readable output
free -h

# Refresh every 2 seconds
free -h -s 2

# Show memory in megabytes
free -m
```

Sample output:

```
               total        used        free      shared  buff/cache   available
Mem:            62Gi        47Gi       8.2Gi       1.1Gi       6.6Gi        13Gi
Swap:          8.0Gi       271Mi       7.7Gi
```

The critical column is `available`, not `free`. The kernel aggressively uses RAM for the page cache (shown in `buff/cache`). This cache is beneficial — it makes repeated model loads faster — but it is reclaimable. The `available` column estimates how much memory can be allocated to a new process before the system must resort to swapping.

For an AI inference server, a healthy baseline is:
- `available` > total size of the largest model you serve, plus headroom for OS and service overhead
- `swap used` at or near zero during steady-state operation

```bash
# Watch memory every second during a model load to observe VRAM and RAM allocation
watch -n 1 free -h
```

---

### GPU Monitoring

#### nvidia-smi [GPU]

`nvidia-smi` (NVIDIA System Management Interface) is the primary command-line tool for querying and managing NVIDIA GPUs. It reads from the NVML (NVIDIA Management Library) and is installed as part of the NVIDIA driver package.

```bash
# Default summary table — shows all GPUs, driver version, CUDA version
nvidia-smi

# Continuous refresh every 1 second (equivalent to top for GPUs)
nvidia-smi -l 1

# Show detailed per-process GPU memory usage
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits

# Custom query — the most useful for AI inference monitoring
nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw,power.limit,clocks.current.sm,clocks_throttle_reasons.active --format=csv,noheader,nounits

# Same query, refreshing every 2 seconds
nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw,power.limit,clocks.current.sm,clocks_throttle_reasons.active --format=csv,noheader,nounits -l 2
```

Key fields in the default `nvidia-smi` output:

| Field | Meaning | AI Inference Signal |
|---|---|---|
| `GPU-Util` | Percentage of time the GPU was executing at least one kernel | Low during inference = GPU is idle, waiting for data or CPU |
| `Mem-Usage` | VRAM used / total (MiB) | Near-full VRAM with low GPU-Util = KV-cache or activation overflow |
| `Temp` | GPU core temperature (°C) | Above ~83°C on most datacenter cards triggers throttling |
| `Power` | Current draw / TDP limit (W) | Sustained at TDP limit = power-limited; throughput is capped |
| `SM Clock` | Current shader multiprocessor clock frequency (MHz) | Below base clock = thermal or power throttle is active |

Understanding throttle reasons is essential for GPU performance debugging:

```bash
# Show active throttle reasons in human-readable form
nvidia-smi --query-gpu=clocks_throttle_reasons.active,clocks_throttle_reasons.gpu_idle,clocks_throttle_reasons.applications_clocks_setting,clocks_throttle_reasons.sw_power_cap,clocks_throttle_reasons.hw_slowdown,clocks_throttle_reasons.sw_thermal_slowdown,clocks_throttle_reasons.sync_boost --format=csv -l 2
```

Common throttle reasons and their remedies:

| Throttle Reason | Cause | Remedy |
|---|---|---|
| `gpu_idle` | No kernels submitted; GPU waiting | Increase batch size; fix CPU preprocessing bottleneck |
| `sw_power_cap` | Driver-enforced power limit hit | Raise power limit with `nvidia-smi -pl <watts>` (if cooling allows) |
| `hw_slowdown` | Hardware thermal protection | Improve airflow; reduce ambient temperature |
| `sw_thermal_slowdown` | Software thermal protection (below hw limit) | Same as above; check fan speed with `nvidia-smi --query-gpu=fan.speed --format=csv` |
| `sync_boost` | MIO/NvLink sync boost active | Normal in multi-GPU setups; usually benign |

Useful `nvidia-smi` management commands:

```bash
# Set persistence mode (prevents driver unload between runs — reduces initialization latency)
sudo nvidia-smi -pm 1

# Set power limit to 300W on GPU 0 (requires root; check max with nvidia-smi -q -d POWER)
sudo nvidia-smi -i 0 -pl 300

# Enable compute-exclusive mode (only one process can use the GPU at a time)
sudo nvidia-smi -i 0 -c EXCLUSIVE_PROCESS

# Lock SM and memory clocks to their maximum for deterministic benchmarking
sudo nvidia-smi -i 0 --lock-gpu-clocks=<min_mhz>,<max_mhz>
sudo nvidia-smi -i 0 --lock-memory-clocks=<mhz>

# Reset locked clocks after benchmarking
sudo nvidia-smi -i 0 --reset-gpu-clocks
sudo nvidia-smi -i 0 --reset-memory-clocks
```

#### nvtop [GPU]

`nvtop` (NVIDIA top) is an interactive, `htop`-style terminal UI for GPU monitoring. It shows real-time utilization graphs, per-process VRAM usage, and supports multiple GPUs side by side.

```bash
# Install nvtop (Debian/Ubuntu — package name varies by distribution version)
sudo apt install nvtop

# Install from source if package is outdated (nvtop 3.x supports NVIDIA, AMD, Intel, and Apple GPUs)
# See: https://github.com/Syllo/nvtop

# Launch
nvtop
```

`nvtop` key bindings:

| Key | Action |
|---|---|
| `F2` / `s` | Setup — toggle which GPUs and processes to display |
| `F9` | Send signal to a GPU process |
| `q` | Quit |

The utilization graph in `nvtop` is the fastest way to spot the sawtooth pattern that indicates a batch pipeline bottleneck: GPU utilization spikes to 100% while a batch is processed, then drops to 0% while the CPU assembles the next batch.

#### watch nvidia-smi [GPU]

For quick monitoring without installing `nvtop`, `watch` polls any command at a fixed interval and redraws the terminal.

```bash
# Refresh the default nvidia-smi summary every 1 second
watch -n 1 nvidia-smi

# Watch only the fields relevant to inference
watch -n 1 'nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,clocks.current.sm --format=csv'

# Watch per-process GPU memory alongside the summary
watch -n 2 'nvidia-smi; echo; nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv'
```

---

### Disk I/O Monitoring

Model weights for large language models can be tens to hundreds of gigabytes. Even with NVMe SSDs, loading a 70B parameter model from disk takes seconds. During that load, inference throughput is zero. Understanding disk I/O is critical for minimizing cold-start latency and avoiding I/O stalls during dataset streaming.

#### iostat

`iostat` is part of the `sysstat` package and reports CPU and block device I/O statistics.

```bash
# Install sysstat
sudo apt install sysstat        # Debian/Ubuntu
sudo dnf install sysstat        # RHEL/Rocky

# Show extended disk statistics, refreshing every 2 seconds
iostat -xz 2

# Show only specific devices
iostat -xz 2 /dev/nvme0n1

# Include timestamps
iostat -xzt 2
```

Key columns in `iostat -x` output:

| Column | Meaning | AI Workload Signal |
|---|---|---|
| `r/s` | Read operations per second | High during model loading |
| `w/s` | Write operations per second | High during checkpoint saving or logging |
| `rMB/s` | Read throughput (MB/s) | Compare against device max (NVMe: ~3500 MB/s; SATA SSD: ~550 MB/s) |
| `wMB/s` | Write throughput (MB/s) | |
| `r_await` | Average read request latency (ms) | Values > 5ms on NVMe indicate I/O saturation |
| `w_await` | Average write request latency (ms) | |
| `%util` | Percentage of time device was busy | Near 100% = device saturated; requests are queuing |
| `aqu-sz` | Average I/O queue depth | Values > 1 on a single device indicate saturation |

```bash
# Quick check: which devices are doing the most work right now
iostat -xz 1 3 | grep -v "^$\|^Linux\|^Device\|loop"
```

#### iotop

`iotop` shows per-process I/O bandwidth in real time, similar to how `top` shows per-process CPU usage.

```bash
# Install iotop
sudo apt install iotop

# Run in interactive mode (requires root)
sudo iotop

# Show only processes with active I/O (less noise)
sudo iotop -o

# Non-interactive, batch mode, 5 snapshots, 2-second interval
sudo iotop -b -n 5 -d 2

# Filter to a specific process by PID
sudo iotop -p 12345
```

Interactive `iotop` keystrokes:

| Key | Action |
|---|---|
| `o` | Toggle show-only-active-I/O filter |
| `p` | Toggle accumulate/live stats |
| `a` | Toggle between bandwidth and accumulated I/O |
| `q` | Quit |

---

### Network Throughput Monitoring

For AI inference APIs, network is rarely the primary bottleneck, but it can become one when serving large responses (image generation, audio) or when doing distributed training with high-speed interconnects. It is also the first place to check when request rates are high but GPU utilization is still low.

#### iftop

`iftop` shows bandwidth per connection pair in real time, similar to `top` for network interfaces.

```bash
# Install iftop
sudo apt install iftop

# Monitor the default interface
sudo iftop

# Monitor a specific interface
sudo iftop -i eth0

# Show port numbers
sudo iftop -i eth0 -P

# Do not resolve hostnames (faster, less noisy)
sudo iftop -i eth0 -n
```

`iftop` displays three bandwidth columns for each connection: the last 2 seconds, last 10 seconds, and last 40 seconds. This makes it easy to distinguish a burst from sustained throughput.

#### nethogs

`nethogs` groups bandwidth by process rather than by connection, making it the right tool for identifying which service is consuming network bandwidth.

```bash
# Install nethogs
sudo apt install nethogs

# Monitor all interfaces
sudo nethogs

# Monitor a specific interface
sudo nethogs eth0

# Refresh every 1 second
sudo nethogs -d 1 eth0
```

#### ss

`ss` (socket statistics) replaces the older `netstat` command and queries the kernel's socket tables directly. It is extremely fast and provides detailed connection state information.

```bash
# Show all TCP connections with process names and ports
ss -tulpn

# Show only listening sockets
ss -tlnp

# Show connections to a specific port (e.g., inference API on port 8000)
ss -tnp sport = :8000

# Show connection counts by state (useful for detecting SYN flood or connection exhaustion)
ss -s

# Watch for connections accumulating on the inference port
watch -n 1 'ss -tnp | grep :8000 | wc -l'

# Show detailed socket statistics including memory usage (useful for detecting socket buffer bloat)
ss -tm
```

The `ss -s` summary output is useful for detecting connection table exhaustion on busy inference servers:

```bash
ss -s
# Output:
# Total: 4821
# TCP:   4804 (estab 4200, closed 150, orphaned 12, timewait 142)
```

A large number of `TIME_WAIT` connections is normal after connection teardown. A large and growing number of `CLOSE_WAIT` connections indicates that the application is not properly closing sockets — a common memory leak pattern in Python inference servers.

---

### Log Management

#### journald and journalctl

`systemd-journald` collects log output from all systemd services, the kernel, and processes that write to stdout/stderr. For AI services managed by systemd, journald is the primary log sink.

```bash
# Follow logs from a specific service in real time
journalctl -u inference-api.service -f

# Show logs since a specific time
journalctl -u inference-api.service --since "2026-04-10 12:00:00"

# Show logs in the last 30 minutes
journalctl -u inference-api.service --since "30 min ago"

# Show only error-level and above from all services
journalctl -p err -f

# Show logs with full metadata (timestamps, PID, unit name)
journalctl -u inference-api.service -o verbose

# Export logs as JSON for ingestion into a log aggregation system
journalctl -u inference-api.service -o json --since "1 hour ago" > /tmp/inference-logs.json

# Check how much disk space the journal is using
journalctl --disk-usage

# Restrict journal size (edit /etc/systemd/journald.conf)
# SystemMaxUse=2G
# RuntimeMaxUse=500M
sudo systemctl restart systemd-journald
```

The journal stores structured data. Priority levels follow the syslog convention:

| Priority | Value | journalctl `-p` shorthand |
|---|---|---|
| Emergency | 0 | `emerg` |
| Alert | 1 | `alert` |
| Critical | 2 | `crit` |
| Error | 3 | `err` |
| Warning | 4 | `warning` |
| Notice | 5 | `notice` |
| Informational | 6 | `info` |
| Debug | 7 | `debug` |

For AI services that write structured JSON logs, combine `journalctl` output with `jq`:

```bash
# Parse structured JSON logs from the inference service, filter for slow requests
journalctl -u inference-api.service -o json --since "1 hour ago" | \
  jq -r 'select(.MESSAGE | fromjson? | .latency_ms > 500) | .MESSAGE | fromjson | [.timestamp, .request_id, .latency_ms] | @csv'
```

#### logrotate

AI services that write to their own log files (not journald) can accumulate hundreds of gigabytes over time, especially when logging per-request metrics at high throughput. `logrotate` prevents disk exhaustion by rotating, compressing, and deleting old log files on a schedule.

`logrotate` is typically invoked daily by a cron job or systemd timer from `/etc/cron.daily/logrotate` or `/lib/systemd/system/logrotate.timer`.

Create a logrotate configuration for an AI service:

```bash
sudo nano /etc/logrotate.d/inference-api
```

```
# /etc/logrotate.d/inference-api
/var/log/inference-api/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 inference_user inference_group
    sharedscripts
    postrotate
        # Send SIGHUP to the inference service so it reopens its log file handle
        systemctl kill --kill-who=main --signal=HUP inference-api.service 2>/dev/null || true
    endscript
}
```

Configuration directive reference:

| Directive | Meaning |
|---|---|
| `daily` / `weekly` / `monthly` | Rotation frequency |
| `rotate 14` | Keep 14 rotated files before deleting the oldest |
| `compress` | Compress rotated files with gzip |
| `delaycompress` | Skip compressing the most-recently rotated file (allows the service one more cycle to close it) |
| `missingok` | Do not error if the log file is missing |
| `notifempty` | Do not rotate if the log file is empty |
| `create 0640 user group` | Create a new empty log file with these permissions after rotation |
| `postrotate` / `endscript` | Shell commands to run after rotation (used to signal the service to reopen log file handles) |
| `copytruncate` | Copy the log file, then truncate the original in place — use when the service cannot reopen its log handle; note: can lose a few log lines |
| `size 500M` | Rotate when file exceeds 500 MB regardless of time |
| `maxage 30` | Delete rotated files older than 30 days regardless of `rotate` count |

```bash
# Test a logrotate configuration without making changes
sudo logrotate -d /etc/logrotate.d/inference-api

# Force rotation immediately (useful for testing)
sudo logrotate -f /etc/logrotate.d/inference-api

# Check the rotation status log
sudo cat /var/lib/logrotate/status | grep inference
```

---

### Prometheus and node_exporter

Prometheus is a pull-based metrics collection system that scrapes HTTP endpoints (called exporters) on a configurable interval and stores time-series data in its local TSDB. `node_exporter` is the official Prometheus exporter for Linux system metrics — CPU, memory, disk, network, filesystem, system load, and many more.

#### Installing node_exporter

```bash
# Download node_exporter (verify latest version at https://github.com/prometheus/node_exporter/releases)
# As of early 2026, the current stable release is 1.8.x
NODE_EXPORTER_VERSION="1.8.2"
wget https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz

# Verify the checksum (download the sha256sums file from the same release page)
sha256sum node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz

# Extract and install
tar xzf node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz
sudo cp node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter /usr/local/bin/
sudo chown root:root /usr/local/bin/node_exporter
sudo chmod 755 /usr/local/bin/node_exporter
```

Create a dedicated system user and systemd service:

```bash
# Create a system user with no login shell and no home directory
sudo useradd --system --no-create-home --shell /bin/false node_exporter
```

```bash
sudo nano /etc/systemd/system/node_exporter.service
```

```ini
[Unit]
Description=Prometheus Node Exporter
Documentation=https://github.com/prometheus/node_exporter
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter \
    --collector.systemd \
    --collector.processes \
    --collector.interrupts \
    --web.listen-address=127.0.0.1:9100
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now node_exporter

# Verify the exporter is running and exposing metrics
curl -s http://127.0.0.1:9100/metrics | head -40
```

The `--web.listen-address=127.0.0.1:9100` flag binds the exporter to localhost only. If Prometheus runs on a separate host, bind to the server's private IP instead and restrict access with firewall rules.

#### GPU Metrics with nvidia_gpu_exporter [GPU]

`node_exporter` does not expose GPU metrics. The `nvidia_gpu_exporter` (also known as `nvidia-gpu-exporter`) is a popular community exporter that wraps `nvidia-smi` queries and exposes them as Prometheus metrics.

```bash
# Download nvidia_gpu_exporter (verify latest at https://github.com/utkuozdemir/nvidia_gpu_exporter/releases)
# Current stable as of early 2026: 1.2.x
GPU_EXPORTER_VERSION="1.2.1"
wget https://github.com/utkuozdemir/nvidia_gpu_exporter/releases/download/v${GPU_EXPORTER_VERSION}/nvidia_gpu_exporter_${GPU_EXPORTER_VERSION}_linux_x86_64.tar.gz
tar xzf nvidia_gpu_exporter_${GPU_EXPORTER_VERSION}_linux_x86_64.tar.gz
sudo cp nvidia_gpu_exporter /usr/local/bin/
```

```bash
sudo nano /etc/systemd/system/nvidia_gpu_exporter.service
```

```ini
[Unit]
Description=NVIDIA GPU Prometheus Exporter
After=network.target

[Service]
User=root
Type=simple
ExecStart=/usr/local/bin/nvidia_gpu_exporter --web.listen-address=127.0.0.1:9835
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nvidia_gpu_exporter

# Verify GPU metrics are exposed
curl -s http://127.0.0.1:9835/metrics | grep nvidia_smi_utilization_gpu
```

#### Installing and Configuring Prometheus

```bash
# Download Prometheus (verify latest at https://github.com/prometheus/prometheus/releases)
# Current stable as of early 2026: 2.52.x
PROMETHEUS_VERSION="2.52.0"
wget https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz
tar xzf prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz

sudo cp prometheus-${PROMETHEUS_VERSION}.linux-amd64/prometheus /usr/local/bin/
sudo cp prometheus-${PROMETHEUS_VERSION}.linux-amd64/promtool /usr/local/bin/

# Create directories
sudo mkdir -p /etc/prometheus /var/lib/prometheus
sudo useradd --system --no-create-home --shell /bin/false prometheus
sudo chown prometheus:prometheus /var/lib/prometheus
```

Write the Prometheus configuration:

```bash
sudo nano /etc/prometheus/prometheus.yml
```

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files: []

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets: ["127.0.0.1:9090"]

  - job_name: "node"
    static_configs:
      - targets: ["127.0.0.1:9100"]

  - job_name: "nvidia_gpu"
    static_configs:
      - targets: ["127.0.0.1:9835"]

  - job_name: "inference_api"
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:8000"]
```

```bash
sudo nano /etc/systemd/system/prometheus.service
```

```ini
[Unit]
Description=Prometheus Monitoring System
Documentation=https://prometheus.io/docs/introduction/overview/
After=network.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/var/lib/prometheus \
    --storage.tsdb.retention.time=30d \
    --web.console.templates=/etc/prometheus/consoles \
    --web.console.libraries=/etc/prometheus/console_libraries \
    --web.listen-address=127.0.0.1:9090
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now prometheus

# Validate the configuration
promtool check config /etc/prometheus/prometheus.yml

# Open the Prometheus UI (from the server's browser, or use SSH port forwarding)
# http://127.0.0.1:9090
```

#### Useful PromQL Queries for AI Inference Monitoring

PromQL (Prometheus Query Language) is used both in the Prometheus UI and in Grafana panel queries.

```promql
# CPU utilization across all cores (percentage, last 5 minutes)
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Available memory in gigabytes
node_memory_MemAvailable_bytes / 1024 / 1024 / 1024

# Disk read throughput in MB/s
rate(node_disk_read_bytes_total{device="nvme0n1"}[5m]) / 1024 / 1024

# GPU utilization percentage (from nvidia_gpu_exporter)
nvidia_smi_utilization_gpu_ratio * 100

# GPU VRAM used in MiB
nvidia_smi_memory_used_bytes / 1024 / 1024

# GPU temperature
nvidia_smi_temperature_gpu

# GPU power draw in watts
nvidia_smi_power_draw_watts

# Network receive throughput in MB/s
rate(node_network_receive_bytes_total{device="eth0"}[5m]) / 1024 / 1024

# Inference API request rate (requires the API to expose a counter named http_requests_total)
rate(http_requests_total{job="inference_api"}[1m])

# 95th percentile inference latency (requires a histogram named http_request_duration_seconds)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="inference_api"}[5m]))
```

---

### Grafana Basics and Dashboard Setup

Grafana is a visualization platform that connects to Prometheus (and dozens of other data sources) and renders time-series data as panels arranged on dashboards.

#### Installing Grafana

```bash
# Add the Grafana APT repository (Debian/Ubuntu)
sudo apt install -y apt-transport-https software-properties-common wget
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /usr/share/keyrings/grafana.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt update && sudo apt install grafana

# Start and enable Grafana
sudo systemctl enable --now grafana-server

# Default Grafana port is 3000
# Access: http://<server-ip>:3000
# Default credentials: admin / admin (you will be prompted to change the password on first login)
```

#### Adding Prometheus as a Data Source

1. Log in to Grafana at `http://<server-ip>:3000`
2. Navigate to **Connections > Data sources > Add data source**
3. Select **Prometheus**
4. Set **Prometheus server URL** to `http://127.0.0.1:9090` (or the address of your Prometheus server)
5. Leave authentication settings at defaults for a local setup
6. Click **Save & test** — you should see "Successfully queried the Prometheus API"

#### Building a GPU Inference Dashboard

The recommended approach for a new dashboard is to start with the key questions you need to answer, then build one panel per question.

For an AI inference server, the core questions are:

1. Is the GPU actually running kernels? (GPU utilization over time)
2. How much VRAM is consumed? (VRAM used vs total)
3. Is the GPU thermally or power-throttled? (temperature + power draw)
4. How many requests are being served? (request rate)
5. What is the tail latency? (p95 latency)
6. Is the CPU keeping the GPU fed? (CPU utilization, per-core)
7. Is the system under memory pressure? (available memory)

To create a dashboard:

1. Click **Dashboards > New > New dashboard**
2. Click **Add visualization**
3. Select your Prometheus data source
4. Enter a PromQL query in the query editor
5. Choose the visualization type (Time series, Gauge, Stat, Bar chart, Heatmap)
6. Set the panel title, units, and thresholds
7. Repeat for each panel; drag and resize panels to arrange them
8. Click the floppy-disk icon to save the dashboard; give it a meaningful name

Dashboard layout recommendation for a GPU inference server:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Row 1: GPU Health (full width)                                      │
│  ┌──────────────────┐  ┌───────────────────┐  ┌──────────────────┐  │
│  │  GPU Utilization │  │  VRAM Used / Free  │  │  GPU Temp & Power│  │
│  │  (time series)   │  │  (time series)     │  │  (time series)   │  │
│  └──────────────────┘  └───────────────────┘  └──────────────────┘  │
│  Row 2: Inference API                                                │
│  ┌──────────────────┐  ┌───────────────────┐                        │
│  │  Request Rate    │  │  p95 Latency (ms)  │                        │
│  │  (time series)   │  │  (time series)     │                        │
│  └──────────────────┘  └───────────────────┘                        │
│  Row 3: System Resources                                             │
│  ┌──────────────────┐  ┌───────────────────┐  ┌──────────────────┐  │
│  │  CPU Utilization │  │  Available Memory  │  │  Disk I/O (MB/s) │  │
│  │  per core        │  │  (gauge)           │  │  (time series)   │  │
│  └──────────────────┘  └───────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

Panel configuration tips:

- For GPU utilization, set the Y axis range to 0–100 and add a threshold line at 80% to highlight when the GPU is well-utilized
- For VRAM, use a **Stat** panel showing current VRAM used alongside total; set a red threshold at 90% of total VRAM
- For latency, use a **Time series** panel with the `ms` unit; add reference lines at your SLO targets (e.g., 500ms p95)
- Enable **Relative time ranges** in the time picker so the dashboard defaults to the last 30 minutes

#### Alerting Concepts

Grafana can send alerts when a metric crosses a threshold. Alert rules evaluate PromQL expressions on a schedule and fire when the condition is true for a configurable duration.

```
Alert Rule Anatomy:
┌──────────────────────────────────────────────────────┐
│  Rule name: GPU utilization below threshold           │
│  Query: avg(nvidia_smi_utilization_gpu_ratio) * 100   │
│  Condition: IS BELOW 20                               │
│  For: 5m   ← must be true for 5 continuous minutes   │
│  Labels: severity=warning, team=ml-infra              │
│  Annotations:                                         │
│    summary: GPU underutilized                         │
│    description: GPU utilization has been below 20%    │
│                 for 5 minutes. Check for CPU          │
│                 preprocessing bottleneck.             │
└──────────────────────────────────────────────────────┘
```

Alert states in Grafana:

| State | Meaning |
|---|---|
| `Normal` | Query result does not meet the firing condition |
| `Pending` | Condition is true but has not persisted for the `For` duration yet |
| `Firing` | Condition has been true for the full `For` duration — notifications are sent |
| `NoData` | No data points returned by the query (exporter may be down) |
| `Error` | Query itself failed to execute |

Configure a contact point (where alerts are sent) under **Alerting > Contact points**. Grafana supports email, Slack, PagerDuty, webhook, and many others.

Recommended alert rules for an AI inference server:

| Alert | Condition | For | Severity |
|---|---|---|---|
| GPU underutilized | GPU util < 20% during serving hours | 5m | warning |
| VRAM near capacity | VRAM used > 90% of total | 2m | critical |
| GPU thermal throttle | GPU temp > 80°C | 3m | warning |
| High inference latency | p95 latency > 1000ms | 5m | critical |
| High CPU iowait | iowait > 30% | 5m | warning |
| Available memory low | available_mem < 4 GiB | 5m | critical |
| node_exporter down | No scrape data from target | 2m | critical |

---

### Performance Tuning for AI Inference

#### CPU Frequency Governor

The Linux CPU frequency scaling governor determines how the kernel adjusts CPU clock speed. For AI inference, the most important behavior is that the CPU must be able to spin up quickly to maximum frequency when preprocessing bursts of requests.

Available governors on most systems:

| Governor | Behavior | Recommendation |
|---|---|---|
| `performance` | Always runs at maximum frequency | Best for inference servers; eliminates frequency ramp-up latency |
| `powersave` | Always runs at minimum frequency | Never use on inference servers |
| `ondemand` | Scales up on load, down on idle | Adequate but introduces latency spikes on bursty workloads |
| `conservative` | Scales more slowly than ondemand | Not recommended for inference |
| `schedutil` | Uses the kernel scheduler's load signal | Good default in modern kernels; similar to ondemand but tighter |

```bash
# Check current governor on all CPUs
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Check available governors
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors

# Set performance governor on all CPUs (takes effect immediately, does not persist across reboots)
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Install cpupower for a more convenient interface
sudo apt install linux-tools-generic     # Debian/Ubuntu
sudo dnf install kernel-tools            # RHEL/Rocky

# Set performance governor using cpupower
sudo cpupower frequency-set -g performance

# Check the result
cpupower frequency-info
```

To persist the governor across reboots on a systemd system:

```bash
sudo nano /etc/systemd/system/cpu-performance-governor.service
```

```ini
[Unit]
Description=Set CPU frequency governor to performance
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/sh -c 'echo performance | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now cpu-performance-governor.service
```

#### NUMA (Non-Uniform Memory Access)

On multi-socket servers, memory is physically attached to specific CPU sockets. A CPU accessing memory on a remote socket (cross-NUMA) incurs significantly higher latency than accessing local memory. For a large language model server, misaligned NUMA placement can add 30–50% latency to inference operations that depend heavily on moving data between CPU and GPU.

```bash
# Check NUMA topology
numactl --hardware

# Example output on a 2-socket server:
# available: 2 nodes (0-1)
# node 0 cpus: 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
# node 0 size: 128000 MB
# node 0 free: 31200 MB
# node 1 cpus: 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31
# node 1 size: 128000 MB
# node 1 free: 29100 MB
# node distances:
# node   0   1
#   0:  10  21
#   1:  21  10

# Check which NUMA node a GPU is connected to (PCIe affinity)
nvidia-smi topo -m
# Look for the CPU Affinity column — it tells you which NUMA node the GPU is on

# Pin an inference process to the NUMA node that contains the GPU
# Replace 0 with the correct NUMA node number from nvidia-smi topo
numactl --cpunodebind=0 --membind=0 python -m your_inference_server

# Check the NUMA placement of a running process
numastat -p <PID>

# Install numactl if not present
sudo apt install numactl
```

The key principle: run the inference process on the same NUMA node as the GPU it uses. This ensures that CPU-side preprocessing, tokenization, and result post-processing access local memory and that PCIe DMA transfers for input tensors stay on the nearest memory bus.

#### Huge Pages

The Linux kernel manages memory in 4 KiB pages by default. For a large language model server that may allocate tens of gigabytes for model weights and KV-cache, managing millions of 4 KiB pages creates significant overhead in TLB (Translation Lookaside Buffer) entries and page table walks.

Huge pages (2 MiB on x86_64) reduce TLB pressure by covering the same memory with 512x fewer entries. Transparent Huge Pages (THP) is the kernel's automatic mechanism; explicit huge pages provide more control.

**Transparent Huge Pages (THP):**

```bash
# Check current THP setting
cat /sys/kernel/mm/transparent_hugepage/enabled
# Output: always [madvise] never
# Bracketed value is the current setting

# For AI inference, 'madvise' is preferred over 'always'
# 'always' can cause latency spikes during huge page compaction
# 'madvise' enables THP only when the application explicitly requests it via madvise(MADV_HUGEPAGE)
echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled

# Disable THP defragmentation to reduce compaction stalls
echo defer+madvise | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
```

**Explicit (Static) Huge Pages:**

PyTorch and some inference frameworks can use explicit huge pages via `hugetlbfs` for significant throughput improvements on large batch sizes.

```bash
# Check current huge page allocation
cat /proc/meminfo | grep -i huge
# HugePages_Total:    0    ← number allocated
# HugePages_Free:     0
# HugePages_Rsvd:     0
# HugePages_Surp:     0
# Hugepagesize:    2048 kB
# Hugetlb:            0 kB

# Allocate 2048 huge pages (2048 × 2 MiB = 4 GiB)
# Best done at boot before memory becomes fragmented
echo 2048 | sudo tee /proc/sys/vm/nr_hugepages

# Make the allocation persistent across reboots
echo "vm.nr_hugepages = 2048" | sudo tee /etc/sysctl.d/99-hugepages.conf
sudo sysctl -p /etc/sysctl.d/99-hugepages.conf

# Mount hugetlbfs so applications can mmap into the huge page pool
sudo mkdir -p /mnt/hugepages
sudo mount -t hugetlbfs nodev /mnt/hugepages
# To mount at boot, add to /etc/fstab:
# nodev /mnt/hugepages hugetlbfs defaults 0 0

# Verify allocation
cat /proc/meminfo | grep -i huge
```

Note: Huge page allocation can fail if memory is fragmented. Allocate them early in the boot process or at system startup before the inference service starts.

---

### Profiling Slow Inference

#### py-spy

`py-spy` is a sampling profiler for Python processes that operates entirely from outside the target process. It reads the call stack of a running Python program without injecting any code into it, making it safe to use on production inference servers.

```bash
# Install py-spy
pip install py-spy

# Top-like live view of a running Python process (find PID first with ps aux | grep python)
sudo py-spy top --pid <PID>

# Record a flame graph for 30 seconds
sudo py-spy record -o /tmp/profile.svg --pid <PID> --duration 30

# Record a flame graph of a new process from launch
sudo py-spy record -o /tmp/profile.svg -- python -m your_inference_server --args

# Non-sudo usage: set the ptrace capability on py-spy once
sudo setcap cap_sys_ptrace+ep $(which py-spy)
py-spy top --pid <PID>
```

Interpreting the flame graph output (`profile.svg`, opened in a browser):

```
Wide bars at the top = functions spending the most wall-clock time
Tall stacks = deep call chains

Common AI inference hot paths to look for:
  - tokenizer.encode() / tokenizer.decode() taking > 10% → consider batched tokenization or Rust tokenizers (tokenizers library)
  - json.loads() / json.dumps() in a hot path → use orjson
  - numpy operations → check if they can be moved to GPU (torch tensors)
  - time.sleep() or asyncio.sleep() unexpectedly high → something is rate-limiting or polling
  - torch.cuda.synchronize() in a loop → unnecessary synchronization, remove or batch
```

```bash
# Dump the current call stack of all threads in a running process (non-invasive snapshot)
sudo py-spy dump --pid <PID>
```

#### NVIDIA Nsight Systems (nsys) [GPU]

`nsys` (NVIDIA Nsight Systems) is a system-wide performance profiler that traces CUDA API calls, kernel execution, memory transfers, and GPU/CPU timeline overlap. It is the tool to reach for when `nvidia-smi` shows low GPU utilization but `py-spy` shows the Python code is not obviously bottlenecked.

```bash
# nsys is part of the NVIDIA CUDA Toolkit (available from https://developer.nvidia.com/cuda-downloads)
# Verify installation
nsys --version

# Profile an inference script for 30 seconds and write a report
nsys profile \
    --trace=cuda,nvtx,osrt \
    --output=/tmp/inference-profile \
    --duration=30 \
    python run_inference.py

# Open the report in the Nsight Systems GUI (on a desktop workstation)
# nsys-ui /tmp/inference-profile.nsys-rep

# Generate a CLI summary of the report (useful on headless servers)
nsys stats /tmp/inference-profile.nsys-rep
```

What to look for in `nsys` output for low GPU utilization:

| Pattern | Diagnosis |
|---|---|
| Long gaps between CUDA kernels | CPU is not submitting work fast enough; check Python overhead, GIL contention |
| `cudaMemcpy` (H2D) taking longer than kernel execution | Input tensor transfer is the bottleneck; consider pinned memory (`pin_memory=True` in DataLoader) |
| Many short kernel launches vs. a few long ones | Kernel launch overhead; consider `torch.compile()` or TensorRT |
| `cudaStreamSynchronize` called frequently | Explicit synchronization forcing serial CPU/GPU execution; use async streams |
| Memory allocations during inference | VRAM allocations are slow; pre-allocate buffers or use CUDA graphs |

---

## Hands-On Examples

### Example 1: Diagnosing a GPU Underutilization Problem

This example walks through the diagnostic tree from the Key Concepts section using real commands.

**Scenario**: An inference API is serving requests but response times are slow. A colleague claims the GPU is "not doing anything."

**Step 1: Confirm GPU utilization is low.**

```bash
# Watch GPU utilization for 30 seconds
watch -n 1 'nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv'
```

Observe: `utilization.gpu` stays at 5–15% even while requests are being processed.

**Step 2: Rule out VRAM saturation.**

VRAM is at 12 GiB / 24 GiB — not full. The GPU is not stalled on a memory error.

**Step 3: Find the CPU bottleneck.**

```bash
# Open htop and press '1' to see per-core CPU usage
htop
```

Observe: one CPU core is pinned at 100%; all other cores are idle. This is a single-threaded bottleneck.

**Step 4: Find the hot function.**

```bash
# Get the PID of the inference server
pgrep -f "python.*inference"

# Profile it for 20 seconds
sudo py-spy record -o /tmp/profile.svg --pid <PID> --duration 20
```

Open `/tmp/profile.svg` in a browser. The widest bar at the top of the flame graph shows `tokenizer.encode()` consuming 78% of wall time. The tokenizer is a pure-Python implementation running in a single thread before each GPU batch.

**Remedy**: Switch to the Hugging Face `tokenizers` library (Rust-based, automatically parallelizes), or move tokenization off the critical path with a producer-consumer queue.

---

### Example 2: Setting Up a GPU Monitoring Dashboard

**Step 1: Verify all exporters are running.**

```bash
# Check that node_exporter, nvidia_gpu_exporter, and Prometheus are active
systemctl is-active node_exporter nvidia_gpu_exporter prometheus

# Spot-check that GPU metrics are reaching Prometheus
curl -s 'http://127.0.0.1:9090/api/v1/query?query=nvidia_smi_utilization_gpu_ratio' | python3 -m json.tool
```

**Step 2: Open Grafana and create a new dashboard.**

Navigate to `http://<server-ip>:3000` and create a new dashboard.

**Step 3: Add a GPU utilization time-series panel.**

- Visualization: **Time series**
- Query A: `nvidia_smi_utilization_gpu_ratio * 100`
- Legend: `GPU {{ index }}`
- Unit: `Percent (0-100)`
- Title: `GPU Utilization (%)`
- Thresholds: green at 0, yellow at 50, red at 90

**Step 4: Add a VRAM gauge panel.**

- Visualization: **Gauge**
- Query A: `nvidia_smi_memory_used_bytes`
- Query B: `nvidia_smi_memory_total_bytes`
- Use override to show Query A as "VRAM Used" and Query B as "VRAM Total"
- Unit: `bytes (IEC)`
- Title: `GPU VRAM`

**Step 5: Add an inference latency panel.**

- Visualization: **Time series**
- Query A: `histogram_quantile(0.50, rate(http_request_duration_seconds_bucket{job="inference_api"}[5m])) * 1000`
- Query B: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="inference_api"}[5m])) * 1000`
- Query C: `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{job="inference_api"}[5m])) * 1000`
- Legends: `p50`, `p95`, `p99`
- Unit: `Milliseconds (ms)`
- Title: `Inference Latency`

**Step 6: Save the dashboard and pin it.**

Click the save icon, name it "AI Inference Server", and star it to pin it to the Grafana home page.

---

### Example 3: Configuring logrotate for a High-Volume Inference Service

**Scenario**: An inference API writes one log line per request to `/var/log/inference-api/requests.log`. At 1,000 requests/second, this file grows at approximately 200 MB/hour.

```bash
# Create the log directory with correct ownership
sudo mkdir -p /var/log/inference-api
sudo chown inference_user:inference_group /var/log/inference-api

# Write the logrotate configuration
sudo nano /etc/logrotate.d/inference-api
```

```
/var/log/inference-api/*.log {
    hourly
    rotate 48
    compress
    delaycompress
    missingok
    notifempty
    size 500M
    maxage 3
    create 0640 inference_user inference_group
    sharedscripts
    postrotate
        systemctl kill --kill-who=main --signal=HUP inference-api.service 2>/dev/null || true
    endscript
}
```

```bash
# Test the configuration
sudo logrotate -d /etc/logrotate.d/inference-api

# For hourly rotation, logrotate needs to run hourly.
# Create a systemd timer alongside the existing daily job:
sudo nano /etc/systemd/system/logrotate-hourly.service
```

```ini
[Unit]
Description=Hourly logrotate run

[Service]
Type=oneshot
ExecStart=/usr/sbin/logrotate /etc/logrotate.d/inference-api
```

```bash
sudo nano /etc/systemd/system/logrotate-hourly.timer
```

```ini
[Unit]
Description=Run logrotate every hour

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now logrotate-hourly.timer
```

---

## Common Pitfalls

**Mistaking `free` memory for available memory.** The `free` column in `free -h` output shows memory not currently allocated to anything, including the page cache. The `available` column is what matters — it includes reclaimable cache. A system with 1 GiB `free` but 30 GiB `available` has plenty of memory. A system with 1 GiB `free` and 1.5 GiB `available` is near an OOM condition.

**Monitoring GPU utilization instead of GPU compute utilization.** `nvidia-smi`'s `GPU-Util` field measures the percentage of time the GPU was executing at least one kernel. This is a coarse metric. A GPU that runs a tiny kernel for 1 ms out of every 100 ms reports 1% utilization, not 0%. For fine-grained analysis, use `nvidia-smi pmon -s u` or `nsys` to see per-kernel utilization.

**Setting `vm.nr_hugepages` on a running, loaded system.** Huge page allocation requires contiguous physical memory. On a system that has been running for hours, memory becomes fragmented and allocations fail silently (the count in `/proc/meminfo` stays at 0). Always allocate huge pages at boot or early in the server startup sequence.

**Running `iotop` without `-o`.** Without the `-o` flag, `iotop` shows all processes, the vast majority of which have zero I/O. The output scrolls too fast to read. Always use `sudo iotop -o`.

**Binding node_exporter to 0.0.0.0 on a public-facing server.** The `node_exporter` metrics endpoint is unauthenticated by default and exposes detailed hardware and OS information. Bind to `127.0.0.1` and use a reverse proxy with authentication if Prometheus needs to scrape from a remote host.

**Ignoring NUMA topology on multi-socket servers.** A common deployment mistake is to launch an inference server without `numactl` on a dual-socket machine and then wonder why latency is 40% higher than on a single-socket machine. Always run `nvidia-smi topo -m` when setting up a new server and pin the inference process to the correct NUMA node.

**Using `copytruncate` in logrotate when the service can accept SIGHUP.** `copytruncate` copies the entire log file before truncating it. On a 500 MB log file written every hour, this causes a brief I/O spike and a small window where log lines can be lost. Use `postrotate` with `systemctl kill --signal=HUP` instead when the service supports it.

**Leaving the CPU governor at `ondemand` during benchmarking.** Benchmark results collected on a system with `ondemand` governor are not reproducible. The CPU may be at different frequencies between runs. Always set `performance` governor before benchmarking inference latency.

---

## Summary

This module covered the full observability and tuning stack for a Linux server running AI inference workloads:

- **CPU and memory** — `top`, `htop`, `vmstat`, and `free` reveal CPU saturation, per-core bottlenecks, memory pressure, and swap activity
- **GPU** — `nvidia-smi` and `nvtop` expose utilization, VRAM, temperature, power draw, and throttle reasons; the `--query-gpu` flag enables scriptable, custom metric collection
- **Disk I/O** — `iostat` measures device throughput and queue depth; `iotop` identifies the process responsible for I/O
- **Network** — `iftop` shows per-connection bandwidth; `nethogs` identifies per-process throughput; `ss` provides socket-level diagnostics
- **Logs** — `journalctl` queries structured logs from systemd services; `logrotate` prevents log disk exhaustion on high-volume inference APIs
- **Metrics collection** — Prometheus with `node_exporter` and `nvidia_gpu_exporter` collects system and GPU metrics; PromQL queries extract actionable signals
- **Visualization and alerting** — Grafana dashboards surface GPU utilization alongside inference latency; alert rules catch degradation before users notice
- **Performance tuning** — the `performance` CPU governor eliminates frequency ramp-up latency; NUMA-aware process placement reduces cross-socket memory access; huge pages reduce TLB pressure for large model allocations
- **Profiling** — `py-spy` identifies Python-level CPU bottlenecks without modifying the production process; `nsys` traces the full CUDA timeline to explain GPU idle time

---

## Further Reading

- [Prometheus Documentation — Getting Started](https://prometheus.io/docs/prometheus/latest/getting_started/) — Official guide to installing Prometheus, writing a `prometheus.yml` configuration, and running your first PromQL queries. Covers scrape configs, relabeling, and the data model in depth.

- [Grafana Documentation — Build your first dashboard](https://grafana.com/docs/grafana/latest/getting-started/build-first-dashboard/) — Step-by-step walkthrough for creating panels, selecting visualizations, and configuring Grafana's built-in alerting system; includes examples using Prometheus as the data source.

- [NVIDIA System Management Interface (nvidia-smi) Documentation](https://docs.nvidia.com/deploy/nvml-api/nvml-api-reference.html) — Reference for all NVML-backed fields exposed by `nvidia-smi`, including the complete list of `--query-gpu` field names, their units, and driver version requirements.

- [node_exporter GitHub Repository — Collector Reference](https://github.com/prometheus/node_exporter) — Lists every collector built into `node_exporter`, the metrics each one exposes, the flags required to enable or disable them, and known limitations per platform.

- [py-spy GitHub Repository — Usage and Flame Graph Interpretation](https://github.com/benfred/py-spy) — Documentation for all `py-spy` subcommands including `top`, `record`, and `dump`; explains how to read flame graphs and discusses known limitations with async Python frameworks.

- [NVIDIA Nsight Systems User Guide](https://docs.nvidia.com/nsight-systems/UserGuide/index.html) — Comprehensive reference for `nsys` CLI flags, report formats, and the GUI timeline view; includes a section on profiling PyTorch workloads and interpreting CUDA API trace data.

- [Linux man page — numactl(8)](https://man7.org/linux/man-pages/man8/numactl.8.html) — Full reference for `numactl` flags including `--cpunodebind`, `--membind`, `--interleave`, and `--physcpubind`; explains NUMA policy inheritance by child processes.

- [Kernel Documentation — Transparent Hugepage Support](https://www.kernel.org/doc/html/latest/admin-guide/mm/transhuge.html) — Authoritative explanation of THP modes (`always`, `madvise`, `never`), the defrag policies, and the trade-offs relevant to latency-sensitive workloads.
