# Module 5: Storage Management
> Subject: Linux | Difficulty: Intermediate | Estimated Time: 330 minutes

## Objective

After completing this module, you will be able to inspect block devices with `lsblk` and `fdisk`, partition disks using `fdisk` and `parted`, format partitions as ext4 or XFS, and mount filesystems both manually and persistently via `/etc/fstab`. You will design and manage an LVM stack — creating physical volumes (PVs), volume groups (VGs), and logical volumes (LVs) — and extend a logical volume online without downtime when a new model download exhausts available space. You will export model directories over NFS, manage 100 GB+ AI model weight files using `df`, `du`, and `ncdu`, create symbolic links to redirect model paths without moving data, use `tmpfs` for fast scratch computation, configure and tune swap, and monitor disk health with `smartctl`. Every technique is framed around a real inference server running large language models.

---

## Prerequisites

- Completed **Module 1** of this Linux series — comfortable with the shell, file permissions, and basic navigation (`ls`, `cd`, `chmod`, `chown`, `sudo`)
- Completed **Module 2** — familiar with process management and system services (`systemctl`, `journalctl`)
- Completed **Module 3** — comfortable with package management (`apt` / `dnf`) and basic text processing (`grep`, `awk`, `sed`)
- Completed **Module 4** — understands Linux networking fundamentals (`ip`, `ss`, firewall basics) which are needed for the NFS section
- A Linux server (physical or VM) running Ubuntu 22.04 LTS / 24.04 LTS or RHEL 9 / Rocky Linux 9 with at least one additional unformatted disk attached (e.g., `/dev/sdb`)
- `sudo` access
- `lvm2`, `nfs-kernel-server` / `nfs-utils`, `smartmontools`, and `ncdu` packages available via the system package manager

---

## Key Concepts

### Inspecting Block Devices: lsblk, fdisk -l, and blkid

Before touching a disk you must understand what is already there. Three tools give you the full picture.

`lsblk` prints a tree of all block devices and their mount points. It reads from `sysfs` and does not require root for a basic listing.

```bash
lsblk
```

Example output on an inference server with one OS disk and two data disks:

```
NAME        MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
sda           8:0    0   500G  0 disk
├─sda1        8:1    0     1G  0 part /boot
├─sda2        8:2    0     4G  0 part [SWAP]
└─sda3        8:3    0   495G  0 part /
sdb           8:16   0     4T  0 disk
sdc           8:32   0     4T  0 disk
nvme0n1     259:0    0   2T    0 disk
└─nvme0n1p1 259:1    0     2T  0 part /models
```

Add `-o NAME,SIZE,FSTYPE,MOUNTPOINT,UUID` to see filesystem types and UUIDs in one view — useful when writing `/etc/fstab` entries.

`fdisk -l` shows the partition table of every disk. It requires root and prints byte-level detail including the partition table format (GPT vs. MBR), sector size, and each partition's start/end sector.

```bash
sudo fdisk -l /dev/sdb
```

`blkid` prints the UUID, filesystem type, and label for every formatted block device. UUIDs are stable across reboots and across cable swaps — always use them in `/etc/fstab` rather than device paths like `/dev/sdb1`.

```bash
sudo blkid /dev/sdb1
# /dev/sdb1: UUID="a1b2c3d4-..." TYPE="xfs" PARTUUID="..."
```

---

### Partitioning Disks: fdisk and parted

For disks up to 2 TB and MBR partition tables, `fdisk` is the standard interactive tool. For disks larger than 2 TB (common for AI model storage) you need GPT partition tables, where `parted` or `gdisk` is the correct choice. Modern Linux installs default to GPT for all disks regardless of size.

**Creating a single GPT partition with `parted` (non-interactive, scriptable):**

```bash
# Confirm the target device first — the next commands are destructive
sudo lsblk /dev/sdb

# Write a GPT label
sudo parted /dev/sdb --script mklabel gpt

# Create one partition spanning the entire disk, named "models"
sudo parted /dev/sdb --script mkpart models xfs 0% 100%

# Verify
sudo parted /dev/sdb print
```

Expected output:

```
Model: ATA SAMSUNG MZ7LH4T0 (scsi)
Disk /dev/sdb: 4001GB
Sector size (logical/physical): 512B/4096B
Partition Table: gpt

Number  Start   End     Size    File system  Name    Flags
 1      1049kB  4001GB  4001GB  xfs          models
```

**Creating a partition interactively with `fdisk`** (for smaller MBR-compatible disks or when you need sub-partition granularity):

```bash
sudo fdisk /dev/sdc
# Inside fdisk:
# g  -> create new GPT partition table
# n  -> new partition (accept all defaults for a single full-disk partition)
# w  -> write and exit
```

After partitioning, inform the kernel of the new layout without rebooting:

```bash
sudo partprobe /dev/sdb
```

---

### Filesystems: ext4 and XFS — Formatting and Mounting

Linux offers several production-grade filesystems. For AI workloads, the two you will encounter most are **ext4** and **XFS**.

**ext4** is the default on Ubuntu and Debian systems. It is mature, well-understood, and has excellent fsck recovery tooling. It supports files up to 16 TB and volumes up to 1 EB.

**XFS** is the default on RHEL/Rocky/Fedora. It excels at large files and high-throughput sequential I/O — exactly the access pattern for reading 70B-parameter model weights that are stored as large binary shards. XFS does not shrink (you can only grow it), so plan your initial size carefully. Its `xfs_repair` utility is powerful but must run on an unmounted volume.

**Formatting a partition:**

```bash
# Format as XFS with a human-readable label
sudo mkfs.xfs -L models /dev/sdb1

# Format as ext4 with a label
sudo mkfs.ext4 -L models /dev/sdb1
```

**Mounting manually (temporary, survives until next reboot):**

```bash
sudo mkdir -p /data/models
sudo mount /dev/sdb1 /data/models
# Verify
mount | grep sdb1
df -h /data/models
```

**Persistent mounts via `/etc/fstab`:**

Every line in `/etc/fstab` defines a filesystem the OS mounts automatically at boot. The six fields are:

```
<device>   <mountpoint>   <fstype>   <options>   <dump>   <pass>
```

| Field | Meaning |
|---|---|
| `<device>` | `UUID=...` (preferred), or device path |
| `<mountpoint>` | Absolute directory path |
| `<fstype>` | `xfs`, `ext4`, `nfs`, `tmpfs`, etc. |
| `<options>` | Mount flags; `defaults` covers `rw,suid,dev,exec,auto,nouser,async` |
| `<dump>` | `0` = ignored by the legacy `dump` backup tool (use `0` always) |
| `<pass>` | `0` = no fsck, `1` = root partition, `2` = other partitions |

**A safe workflow for editing `/etc/fstab`:**

```bash
# 1. Get the UUID of the new partition
sudo blkid /dev/sdb1
# UUID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# 2. Create the mount point
sudo mkdir -p /data/models

# 3. Back up fstab before editing
sudo cp /etc/fstab /etc/fstab.bak

# 4. Append the new entry
echo 'UUID=a1b2c3d4-e5f6-7890-abcd-ef1234567890  /data/models  xfs  defaults,nofail  0  2' \
  | sudo tee -a /etc/fstab

# 5. Test the new entry without rebooting
sudo mount -a

# 6. Confirm mount succeeded
df -h /data/models
```

The `nofail` option is important on servers: if the disk is absent at boot (e.g., a detached NVMe), the system still boots rather than dropping into emergency mode.

---

### LVM — Physical Volumes, Volume Groups, and Logical Volumes

LVM (Logical Volume Manager) adds a virtualization layer between physical disks and the filesystems that sit on top of them. Instead of partitioning a disk and being locked into fixed sizes, LVM lets you pool multiple disks into a single **volume group** and carve that pool into **logical volumes** that can be resized online.

This is invaluable on AI servers: when you download a new 70B model that overflows your existing `/data/models` volume, you add a new disk to the pool and extend the volume — no reformatting, no data migration, no downtime.

**Concepts:**

| Layer | Command to create | Inspect with |
|---|---|---|
| Physical Volume (PV) | `pvcreate` | `pvs` / `pvdisplay` |
| Volume Group (VG) | `vgcreate` | `vgs` / `vgdisplay` |
| Logical Volume (LV) | `lvcreate` | `lvs` / `lvdisplay` |

**Creating an LVM stack from scratch:**

```bash
# Assume /dev/sdb and /dev/sdc are blank disks

# Step 1: Initialize disks as physical volumes
sudo pvcreate /dev/sdb /dev/sdc

# Step 2: Create a volume group named "modelsvg" from both PVs
sudo vgcreate modelsvg /dev/sdb /dev/sdc

# Step 3: Create a logical volume using all available space
sudo lvcreate -l 100%FREE -n modelslv modelsvg

# Step 4: Format the logical volume
sudo mkfs.xfs /dev/modelsvg/modelslv

# Step 5: Mount it
sudo mkdir -p /data/models
sudo mount /dev/modelsvg/modelslv /data/models

# Step 6: Add to /etc/fstab (use the LV device path OR its UUID)
echo '/dev/modelsvg/modelslv  /data/models  xfs  defaults,nofail  0  2' \
  | sudo tee -a /etc/fstab
```

**Inspecting the stack:**

```bash
sudo pvs
# PV         VG       Fmt  Attr PSize   PFree
# /dev/sdb   modelsvg lvm2 a--   <4.00t      0
# /dev/sdc   modelsvg lvm2 a--   <4.00t      0

sudo vgs
# VG       #PV #LV #SN Attr   VSize  VFree
# modelsvg   2   1   0 wz--n- <8.00t    0

sudo lvs
# LV       VG       Attr       LSize  Pool Origin ...
# modelslv modelsvg -wi-ao---- <8.00t
```

**Extending an LV when you run out of space (the core AI server scenario):**

```bash
# 1. Add a new physical disk to the server, then initialize it as a PV
sudo pvcreate /dev/sdd

# 2. Extend the volume group to include the new disk
sudo vgextend modelsvg /dev/sdd

# 3. Extend the logical volume to consume all new free space
sudo lvextend -l +100%FREE /dev/modelsvg/modelslv

# 4. Grow the filesystem to fill the extended LV (online, no unmount needed)
# For XFS:
sudo xfs_growfs /data/models
# For ext4:
sudo resize2fs /dev/modelsvg/modelslv

# 5. Confirm
df -h /data/models
```

The XFS `xfs_growfs` command operates on the **mount point**, not the device path. The `resize2fs` command for ext4 operates on the **device path**.

---

### NFS — Sharing Model Storage Across Inference Nodes

When you run a fleet of inference servers, you do not want to store a copy of the same 140 GB model on each node. NFS (Network File System) lets one storage server export a directory over the network; every inference node mounts it as if the files were local.

**On the NFS server (the machine that holds the model files):**

```bash
# Install the NFS server package
sudo apt install nfs-kernel-server    # Ubuntu/Debian
sudo dnf install nfs-utils            # RHEL/Rocky

# Create the export directory
sudo mkdir -p /data/models

# Define the export in /etc/exports
# Syntax: <path>  <client_cidr>(<options>)
echo '/data/models  192.168.10.0/24(ro,sync,no_subtree_check,no_root_squash)' \
  | sudo tee -a /etc/exports

# Apply the export configuration
sudo exportfs -arv

# Enable and start the NFS server
sudo systemctl enable --now nfs-server

# Verify exports
sudo exportfs -v
```

**Key NFS export options:**

| Option | Meaning |
|---|---|
| `ro` | Read-only (inference nodes only need to read model weights) |
| `rw` | Read-write (use for a shared scratch directory) |
| `sync` | Write to disk before acknowledging client — safer than `async` |
| `no_subtree_check` | Disables subtree checking; reduces stale file handle errors with large trees |
| `no_root_squash` | Allows root on the client to act as root on the server — use only on trusted nodes |
| `root_squash` | (default) Maps client root to `nfsnobody` — safer for untrusted clients |

**On each NFS client (inference node):**

```bash
# Install client utilities
sudo apt install nfs-common           # Ubuntu/Debian
sudo dnf install nfs-utils            # RHEL/Rocky

# Create mount point
sudo mkdir -p /mnt/models

# Test mount manually first
sudo mount -t nfs 192.168.10.5:/data/models /mnt/models

# List model files to confirm
ls -lh /mnt/models

# Add persistent mount to /etc/fstab
echo '192.168.10.5:/data/models  /mnt/models  nfs  ro,hard,intr,timeo=600,retrans=3,nofail,_netdev  0  0' \
  | sudo tee -a /etc/fstab
```

**NFS mount options explained:**

| Option | Why it matters for AI workloads |
|---|---|
| `ro` | Inference nodes should never accidentally overwrite the shared model repository |
| `hard` | If the NFS server is temporarily unreachable, I/O blocks and retries rather than failing with an error — prevents inference crashes mid-forward-pass |
| `intr` | Allows the blocked I/O to be interrupted by a signal so you can kill a hung process |
| `timeo=600` | 60-second timeout before a retry (units are tenths of a second) |
| `retrans=3` | Retry the request 3 times before escalating |
| `_netdev` | Tells the init system this mount requires the network to be up before attempting |

---

### Managing Large Files: df, du, and ncdu

AI model weight files are large. A 7B-parameter model in float16 occupies roughly 14 GB; a 70B model occupies roughly 140 GB; a 405B model can exceed 800 GB. Understanding exactly where disk space is being consumed is a critical operational skill.

**`df` — disk free space by filesystem:**

```bash
# Human-readable sizes, all mounted filesystems
df -h

# Show only specific filesystems
df -h /data/models /tmp

# Include filesystem type in output
df -hT
```

Example output:

```
Filesystem                    Type   Size  Used Avail Use% Mounted on
/dev/modelsvg/modelslv        xfs    7.9T  6.2T  1.7T  79% /data/models
192.168.10.5:/data/models     nfs    7.9T  6.2T  1.7T  79% /mnt/models
tmpfs                         tmpfs   32G  512M   32G   2% /dev/shm
```

**`du` — disk usage by directory:**

```bash
# Show sizes of immediate subdirectories in /data/models, human-readable
du -h --max-depth=1 /data/models

# Find the ten largest items under /data/models
du -ah /data/models | sort -rh | head -10

# Count only the total for a single model directory
du -sh /data/models/llama-3-70b-instruct
# 138G    /data/models/llama-3-70b-instruct
```

`du` traverses every file and can be slow on very large directories. For production use, schedule it off-peak or use `ncdu`.

**`ncdu` — interactive disk usage browser:**

`ncdu` (NCurses Disk Usage) is a terminal UI that builds the same data as `du` but presents it as a navigable tree. It is the fastest way to find what is filling a partition.

```bash
# Install
sudo apt install ncdu           # Ubuntu/Debian
sudo dnf install ncdu           # RHEL/Rocky

# Scan /data/models and open the interactive browser
sudo ncdu /data/models
```

Inside ncdu: arrow keys navigate, `d` deletes the selected item (with confirmation), `q` quits. Items are sorted by size descending by default.

**Practical tip — finding large model shard files quickly:**

```bash
# Find all files larger than 5 GB under /data/models
find /data/models -type f -size +5G -exec ls -lh {} \;
```

---

### Symbolic Links for Model Directories

Inference frameworks (vLLM, Ollama, HuggingFace Transformers, TensorRT-LLM) expect model weights at a specific path defined in a config file or environment variable. When you move models to a larger volume or reorganize storage, symlinks let you maintain the expected path without reconfiguring every service.

**Scenario:** Your original model path was `/models` on the root partition. You have moved the weights to `/data/models`. Create a symlink so existing services require no reconfiguration:

```bash
# Move the data (only once)
sudo mv /models /data/models

# Create a symlink from the old path to the new location
sudo ln -s /data/models /models

# Verify: following the link reaches the real data
ls -la /models
# lrwxrwxrwx 1 root root 12 Apr 10 09:00 /models -> /data/models

readlink -f /models
# /data/models
```

**Model version symlinks** — a common pattern for zero-downtime model upgrades:

```bash
# Directory layout on the NFS server
/data/models/
  llama-3-70b-v1/          # old weights
  llama-3-70b-v2/          # new weights, being validated
  llama-3-70b-current -> llama-3-70b-v2/   # symlink the service uses

# Atomic promotion: point the symlink at the new version
sudo ln -sfn /data/models/llama-3-70b-v2 /data/models/llama-3-70b-current
```

`ln -sfn` updates an existing symlink atomically (`-s` = symbolic, `-f` = force overwrite, `-n` = treat the destination as a file not a directory when it is a symlink). Running inference processes that have already opened the old path are unaffected; new requests use the new path.

---

### tmpfs — Fast Scratch Space for Inference

`tmpfs` is a virtual filesystem backed entirely by RAM (and swap if RAM fills). Reads and writes are as fast as memory access — orders of magnitude faster than any disk. This makes it ideal for:

- Temporary KV-cache files that inference engines dump to disk during long contexts
- Intermediate activation checkpoints during fine-tuning
- Scratch space for tokenization preprocessing pipelines

**Mounting a 32 GB tmpfs as a scratch space:**

```bash
sudo mkdir -p /scratch
sudo mount -t tmpfs -o size=32g tmpfs /scratch
```

**Persistent tmpfs in `/etc/fstab`:**

```bash
echo 'tmpfs  /scratch  tmpfs  size=32g,mode=1777  0  0' \
  | sudo tee -a /etc/fstab
```

`mode=1777` gives all users write access with the sticky bit set (like `/tmp`), preventing users from deleting each other's files.

**Important:** tmpfs content is lost on reboot and when the filesystem is unmounted. Never store the only copy of model weights in tmpfs. Use it only for ephemeral, reproducible intermediates.

**`/dev/shm`** is a tmpfs that is always present on Linux and is used by PyTorch's shared-memory tensor passing between DataLoader workers. Check its size and resize if workers OOM:

```bash
df -h /dev/shm
# If too small:
sudo mount -o remount,size=64g /dev/shm
```

---

### Swap Configuration

Swap extends virtual memory to disk. On an AI inference server, swap is a last resort — swapping model tensors to disk is thousands of times slower than RAM. However, some swap is still valuable:

- Prevents the OOM killer from terminating the inference process during a brief memory spike
- Allows the OS to page out rarely-used kernel buffers, keeping RAM available for model weights
- Provides a safety net during model loading when the full model is briefly resident in RAM

**Creating a swap file (preferred over a swap partition on LVM systems):**

```bash
# Allocate a 16 GB swap file (use fallocate for speed; dd is slower but more portable)
sudo fallocate -l 16G /swapfile

# Secure the permissions — swap files must not be world-readable
sudo chmod 600 /swapfile

# Format as swap space
sudo mkswap /swapfile

# Enable immediately
sudo swapon /swapfile

# Verify
swapon --show
free -h

# Persist across reboots
echo '/swapfile  none  swap  sw  0  0' | sudo tee -a /etc/fstab
```

**Tuning `swappiness`:**

The kernel's `vm.swappiness` parameter (0–200 on Linux 5.8+; 0–100 on older kernels) controls how aggressively the kernel reclaims anonymous memory to swap vs. reclaiming file-backed page cache.

For AI inference servers, a low value like `10` keeps model tensors in RAM longer:

```bash
# Temporary change
sudo sysctl vm.swappiness=10

# Permanent change (survives reboot)
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.d/99-ai-server.conf
sudo sysctl -p /etc/sysctl.d/99-ai-server.conf
```

---

### Disk Health Monitoring with smartctl

`smartctl` (part of the `smartmontools` package) queries a disk's built-in SMART (Self-Monitoring, Analysis, and Reporting Technology) diagnostics. On a storage server that holds irreplaceable model repositories, knowing a drive is developing bad sectors before it fails completely is critical.

```bash
# Install
sudo apt install smartmontools       # Ubuntu/Debian
sudo dnf install smartmontools       # RHEL/Rocky

# Check if SMART is supported and enabled on a disk
sudo smartctl -i /dev/sdb

# Run a quick self-test (takes ~2 minutes, drive stays online)
sudo smartctl -t short /dev/sdb

# Run a long self-test (can take hours for large drives, drive stays online)
sudo smartctl -t long /dev/sdb

# View all SMART attributes and test results
sudo smartctl -a /dev/sdb
```

**Critical SMART attributes to watch:**

| Attribute | ID | What it means |
|---|---|---|
| `Reallocated_Sector_Ct` | 5 | Count of bad sectors remapped to spare area — any value above 0 warrants concern |
| `Reported_Uncorrect` | 187 | Uncorrectable read errors — non-zero means data loss risk |
| `Current_Pending_Sector` | 197 | Sectors waiting to be reallocated — non-zero means imminent failure risk |
| `Offline_Uncorrectable` | 198 | Sectors found bad during offline scan |
| `Power_On_Hours` | 9 | Total runtime; plan replacement around manufacturer's rated MTTF |

**Enabling automated SMART monitoring with `smartd`:**

```bash
sudo systemctl enable --now smartd
```

`smartd` runs in the background, polls all drives at a configured interval, and can email alerts when thresholds are exceeded. Configure it in `/etc/smartd.conf`.

---

## Best Practices

1. **Always use UUIDs, not device paths, in `/etc/fstab`.** Device paths like `/dev/sdb1` are assigned by the kernel at boot based on detection order and can change if you add, remove, or reseat disks — UUIDs are stable and tied to the filesystem itself.

2. **Include `nofail` in `/etc/fstab` for every non-root mount on a server.** If a disk fails, is removed, or a network mount is unreachable at boot time, `nofail` prevents the system from dropping into emergency maintenance mode and becoming inaccessible remotely.

3. **Size LVM logical volumes conservatively at first and extend online.** It is always possible to grow a logical volume without downtime; it is not always possible to shrink one safely (XFS cannot be shrunk at all). Leave free space in your volume group for future growth rather than allocating it all upfront.

4. **Export NFS model directories read-only (`ro`) to inference nodes.** An accidental write from a buggy inference process or a misconfigured fine-tuning job can corrupt a shared model repository that dozens of nodes depend on. Read-only exports make this impossible at the filesystem level.

5. **Use symlinks for model path indirection, not hard-coded absolute paths in service configs.** Storing model paths as symlinks (e.g., `/models/current -> /data/models/llama-3-70b-v2`) decouples service configuration from storage layout and enables zero-downtime model version promotions.

6. **Run `smartctl -t long` monthly on every data disk and review the results.** SMART long tests exercise the full disk surface and catch developing bad sectors before they cause data loss. Schedule them during off-peak hours since they generate I/O.

7. **Keep `vm.swappiness` at 10 or lower on inference servers.** The default value of 60 causes the kernel to aggressively page out process memory — including model weight buffers — to swap, which on disk is catastrophically slow for inference latency. A value of 10 tells the kernel to prefer evicting page cache over anonymous memory.

8. **Scan large model directories with `ncdu` before deleting anything.** The `du -sh *` command can take many minutes on a directory containing multi-gigabyte sharded files. `ncdu` scans once and lets you navigate interactively, reducing the chance of deleting the wrong file under pressure.

9. **Keep at least 15–20% free space on XFS volumes.** XFS performance degrades as a volume approaches full because the allocator has fewer choices for contiguous extent placement. This is especially visible with large sequential writes during model downloads.

10. **Use `fallocate` to pre-allocate space before downloading large models.** Running `fallocate -l 150G /data/models/llama-3-70b.download` before starting a download ensures the space is available and prevents a partially downloaded model from consuming space it cannot complete.

---

## Use Cases

### Use Case 1: The Root Partition Is Full Because Someone Downloaded a 70B Model There

**Problem:** A team member ran `huggingface-cli download meta-llama/Llama-3-70B` without specifying a cache directory. The model downloaded to `~/.cache/huggingface/hub/` on the root partition. `/` is now 98% full, breaking log writes, cron jobs, and new SSH sessions.

**Concepts applied:** `df`, `du`, `ncdu`, symbolic links, `/etc/fstab`, LVM extension.

**Expected outcome:** The model is moved to the dedicated model volume, the root partition is freed, and the HuggingFace cache is redirected via symlink so future downloads go directly to the model volume.

```bash
df -h /
# / is 98% full

du -sh ~/.cache/huggingface
# 141G   /home/ubuntu/.cache/huggingface

# Move to the model volume (already mounted at /data/models)
sudo mv ~/.cache/huggingface /data/models/huggingface-cache

# Create a symlink so HuggingFace CLI finds its cache at the expected path
ln -s /data/models/huggingface-cache ~/.cache/huggingface

df -h /
# / is now 15% full
```

### Use Case 2: Deploying a Shared Model Repository Across an Inference Cluster

**Problem:** An organization runs ten vLLM inference nodes. Each node would need 140 GB of storage for a single model, totaling 1.4 TB of duplicate data. A new model version needs to be deployed simultaneously to all nodes.

**Concepts applied:** NFS export/import, `no_root_squash`, `ro` mounts, symlinks for version promotion, `_netdev` fstab option.

**Expected outcome:** One NFS server exports `/data/models` to all ten nodes. Each node mounts it at `/mnt/models`. A symlink `current` on the NFS server is atomically updated to point to the new model version, and all nodes immediately serve the new version without any per-node changes.

### Use Case 3: Extending Storage Online When Downloading a New Model Family

**Problem:** The LVM volume group `modelsvg` has 10 GB of free space remaining. A new batch of Qwen2.5-72B models (230 GB total) needs to be downloaded. The server has an unallocated 4 TB NVMe attached as `/dev/sdd`.

**Concepts applied:** `pvcreate`, `vgextend`, `lvextend`, `xfs_growfs`, online resize.

**Expected outcome:** The new disk is added to the existing volume group, the logical volume and filesystem are extended online with no service interruption, and the download proceeds into the newly available space.

### Use Case 4: Monitoring Disk Health on a High-Write Training Server

**Problem:** A GPU training server writes model checkpoints to disk every 100 steps. After six months of continuous operation, writes begin occasionally failing. The team suspects disk wear.

**Concepts applied:** `smartctl -a`, `smartctl -t long`, reallocated sectors attribute, `smartd` daemon.

**Expected outcome:** `smartctl -a /dev/sda` reveals a non-zero `Reallocated_Sector_Ct` and several `Current_Pending_Sector` entries. The team schedules a disk replacement during the next maintenance window and enables `smartd` email alerts going forward.

---

## Hands-on Examples

### Example 1: Partition, Format, and Persistently Mount a New 4 TB Data Disk

**Setup:** You have received a new server for your inference cluster. It has an OS disk at `/dev/sda` and a blank 4 TB NVMe at `/dev/nvme1n1`. You will partition it, format it as XFS, and mount it persistently at `/data/models`.

**Steps:**

1. Confirm the disk is blank and has the correct size:

```bash
sudo lsblk /dev/nvme1n1
# nvme1n1  259:1    0   3.6T  0 disk
sudo fdisk -l /dev/nvme1n1
# Device does not contain a recognized partition table.
```

2. Create a GPT partition table and a single partition:

```bash
sudo parted /dev/nvme1n1 --script mklabel gpt
sudo parted /dev/nvme1n1 --script mkpart models xfs 0% 100%
sudo partprobe /dev/nvme1n1
```

3. Verify the partition exists:

```bash
lsblk /dev/nvme1n1
# nvme1n1      259:1    0   3.6T  0 disk
# └─nvme1n1p1  259:2    0   3.6T  0 part
```

4. Format the partition as XFS with a label:

```bash
sudo mkfs.xfs -L models /dev/nvme1n1p1
```

Expected output (abbreviated):
```
meta-data=/dev/nvme1n1p1  isize=512    agcount=4, agsize=234741760 blks
data     =                bsize=4096   blocks=938967040, imaxpct=5
naming   =version 2       bsize=4096   ascii-ci=0, ftype=1
log      =internal log    bsize=4096   blocks=458480
realtime =none            extsz=4096   blocks=0, rtextents=0
```

5. Get the UUID:

```bash
sudo blkid /dev/nvme1n1p1
# /dev/nvme1n1p1: LABEL="models" UUID="f4a1b2c3-d4e5-6789-abcd-ef0123456789" TYPE="xfs"
```

6. Create the mount point and add the entry to `/etc/fstab`:

```bash
sudo mkdir -p /data/models
sudo cp /etc/fstab /etc/fstab.bak

# Replace the UUID below with the one from step 5
echo 'UUID=f4a1b2c3-d4e5-6789-abcd-ef0123456789  /data/models  xfs  defaults,nofail  0  2' \
  | sudo tee -a /etc/fstab
```

7. Mount and verify:

```bash
sudo mount -a
df -hT /data/models
```

Expected output:
```
Filesystem          Type  Size  Used Avail Use% Mounted on
/dev/nvme1n1p1      xfs   3.6T   36M  3.6T   1% /data/models
```

---

### Example 2: Build an LVM Stack and Extend It Online

**Setup:** Your inference server has two 4 TB disks (`/dev/sdb`, `/dev/sdc`) that you will pool using LVM into an 8 TB logical volume. Later, a third disk (`/dev/sdd`) is added and you extend the volume online.

**Steps:**

1. Install LVM tools if not already present:

```bash
sudo apt install lvm2        # Ubuntu/Debian
sudo dnf install lvm2        # RHEL/Rocky
```

2. Initialize the disks as physical volumes:

```bash
sudo pvcreate /dev/sdb /dev/sdc
```

Expected output:
```
  Physical volume "/dev/sdb" successfully created.
  Physical volume "/dev/sdc" successfully created.
```

3. Create a volume group:

```bash
sudo vgcreate modelsvg /dev/sdb /dev/sdc
sudo vgs
```

Expected output:
```
  VG       #PV #LV #SN Attr   VSize  VFree
  modelsvg   2   0   0 wz--n- <7.99t <7.99t
```

4. Create a logical volume using all space:

```bash
sudo lvcreate -l 100%FREE -n modelslv modelsvg
sudo lvs
```

Expected output:
```
  LV       VG       Attr       LSize  Pool Origin ...
  modelslv modelsvg -wi-a----- <7.99t
```

5. Format and mount:

```bash
sudo mkfs.xfs /dev/modelsvg/modelslv
sudo mkdir -p /data/models
sudo mount /dev/modelsvg/modelslv /data/models
df -h /data/models
```

Expected output:
```
Filesystem                     Size  Used Avail Use% Mounted on
/dev/mapper/modelsvg-modelslv  8.0T   54M  8.0T   1% /data/models
```

6. Simulate running out of space and extending (add `/dev/sdd`):

```bash
sudo pvcreate /dev/sdd
sudo vgextend modelsvg /dev/sdd
sudo lvextend -l +100%FREE /dev/modelsvg/modelslv
sudo xfs_growfs /data/models
df -h /data/models
```

Expected output after extension:
```
Filesystem                     Size  Used Avail Use% Mounted on
/dev/mapper/modelsvg-modelslv   12T   54M   12T   1% /data/models
```

The filesystem grew from ~8 TB to ~12 TB with the inference server running continuously.

---

### Example 3: Set Up NFS Model Sharing Between a Storage Server and Two Inference Nodes

**Setup:** Three machines on the `192.168.10.0/24` subnet:
- `storage-01` (192.168.10.5): holds model weights at `/data/models`
- `infer-01` (192.168.10.11): vLLM inference node
- `infer-02` (192.168.10.12): vLLM inference node

**Steps — on `storage-01`:**

1. Install and configure the NFS server:

```bash
sudo apt install nfs-kernel-server
sudo systemctl enable --now nfs-server
```

2. Ensure `/data/models` is owned correctly:

```bash
sudo chown -R root:root /data/models
sudo chmod 755 /data/models
```

3. Define the export:

```bash
sudo cp /etc/exports /etc/exports.bak
echo '/data/models  192.168.10.0/24(ro,sync,no_subtree_check)' \
  | sudo tee -a /etc/exports
sudo exportfs -arv
```

Expected output:
```
exporting 192.168.10.0/24:/data/models
```

4. Open the firewall (Ubuntu with UFW):

```bash
sudo ufw allow from 192.168.10.0/24 to any port nfs
sudo ufw reload
```

**Steps — on `infer-01` and `infer-02` (run on each node):**

5. Install NFS client:

```bash
sudo apt install nfs-common
```

6. Create mount point and test:

```bash
sudo mkdir -p /mnt/models
sudo mount -t nfs 192.168.10.5:/data/models /mnt/models
ls /mnt/models
# llama-3-70b-instruct  qwen2.5-72b  mistral-7b-v0.3
```

7. Add persistent mount:

```bash
echo '192.168.10.5:/data/models  /mnt/models  nfs  ro,hard,intr,timeo=600,retrans=3,nofail,_netdev  0  0' \
  | sudo tee -a /etc/fstab
```

8. Verify on both nodes:

```bash
df -h /mnt/models
# Filesystem                 Size  Used Avail Use% Mounted on
# 192.168.10.5:/data/models  7.9T  6.2T  1.7T  79% /mnt/models
```

---

### Example 4: Diagnose and Free Disk Space on a Full Model Partition

**Setup:** Your `/data/models` volume is at 97% capacity. The team is not sure what is consuming the space — could be model weights, old checkpoints, or downloaded tokenizer caches.

**Steps:**

1. Confirm the problem:

```bash
df -h /data/models
# Filesystem                     Size  Used Avail Use% Mounted on
# /dev/mapper/modelsvg-modelslv  8.0T  7.8T  200G  97% /data/models
```

2. Scan with `ncdu` to find the largest consumers:

```bash
sudo ncdu /data/models
```

Navigate the tree to identify the top space consumers. Suppose you find:
```
 4.2T  checkpoints/
 2.1T  models/
 1.4T  datasets/
  96G  .trash/
```

3. Check the checkpoints directory more closely (without leaving `ncdu`, or via `du`):

```bash
du -h --max-depth=2 /data/models/checkpoints | sort -rh | head -10
# 4.2T   /data/models/checkpoints
# 2.1T   /data/models/checkpoints/llama-finetune-2024-11
# 2.1T   /data/models/checkpoints/llama-finetune-2024-10
```

4. Confirm which checkpoints are no longer needed (check with the team) and remove stale ones:

```bash
sudo rm -rf /data/models/checkpoints/llama-finetune-2024-10
```

5. If there is a large `.trash/` directory from a GUI file manager or automated deletion script, empty it:

```bash
sudo rm -rf /data/models/.trash/*
```

6. Verify the space is recovered:

```bash
df -h /data/models
# Filesystem                     Size  Used Avail Use% Mounted on
# /dev/mapper/modelsvg-modelslv  8.0T  3.7T  4.3T  47% /data/models
```

---

## Common Pitfalls

### Pitfall 1: Using Device Paths Instead of UUIDs in /etc/fstab

**Description:** Writing `/dev/sdb1` instead of `UUID=...` in `/etc/fstab`.

**Why it happens:** Device paths are shorter and seem obvious when you are staring at `lsblk` output.

**Why it is wrong:** If a second disk is added, or a cable is swapped, or a disk is reseat, the kernel may assign `/dev/sdb` to a different physical drive than intended. The system will mount the wrong filesystem — or fail to boot.

**Incorrect:**
```
/dev/sdb1  /data/models  xfs  defaults  0  2
```

**Correct:**
```
UUID=a1b2c3d4-e5f6-7890-abcd-ef1234567890  /data/models  xfs  defaults,nofail  0  2
```

---

### Pitfall 2: Forgetting to Run xfs_growfs After lvextend

**Description:** After extending the logical volume with `lvextend`, the filesystem reports the same old size.

**Why it happens:** `lvextend` grows the block device but does not touch the filesystem metadata. The filesystem still sees the old size until you explicitly tell it to expand.

**Incorrect (stopping after lvextend):**
```bash
sudo lvextend -l +100%FREE /dev/modelsvg/modelslv
df -h /data/models   # Still shows old size — mistake!
```

**Correct:**
```bash
sudo lvextend -l +100%FREE /dev/modelsvg/modelslv
sudo xfs_growfs /data/models     # For XFS (use the mount point)
sudo resize2fs /dev/modelsvg/modelslv  # For ext4 (use the device path)
df -h /data/models   # Now shows new size
```

---

### Pitfall 3: Mounting NFS Without the _netdev Option

**Description:** An NFS entry in `/etc/fstab` without `_netdev` causes a boot hang if the network is not up when `mount -a` runs.

**Why it happens:** The default init system processing order tries to mount all filesystems in `/etc/fstab` before the network is fully initialized. NFS requires network connectivity.

**Incorrect:**
```
192.168.10.5:/data/models  /mnt/models  nfs  ro,hard,intr,nofail  0  0
```

**Correct:**
```
192.168.10.5:/data/models  /mnt/models  nfs  ro,hard,intr,nofail,_netdev  0  0
```

---

### Pitfall 4: Trying to Shrink an XFS Filesystem

**Description:** Running `xfs_growfs` with a smaller size target, or attempting to `lvreduce` an XFS volume.

**Why it happens:** Users assume XFS works like ext4, which supports both grow and shrink via `resize2fs`.

**Why it fails:** XFS does not implement filesystem shrink. The command will return an error, but if the user proceeds to shrink the block device anyway (with `lvreduce`), the filesystem metadata is truncated and the volume becomes unrecoverable.

**Incorrect:**
```bash
sudo lvreduce -L -500G /dev/modelsvg/modelslv   # Destroys XFS data silently
```

**Correct approach:** Plan XFS volumes to grow-only. If you need to reclaim space, back up the data, recreate the LV at the smaller size, reformat, and restore — or migrate to a different filesystem.

---

### Pitfall 5: Setting vm.swappiness=0 on an Inference Server

**Description:** Setting `vm.swappiness=0` in hopes of eliminating all swapping and keeping everything in RAM.

**Why it happens:** Developers read that "swappiness=0 means no swapping" — which was true on older kernels but is not accurate on Linux 3.5+.

**Why it is wrong:** On modern kernels, `vm.swappiness=0` means "avoid swapping anonymous pages unless there is absolutely no other option" — swap is still used. More importantly, setting it to `0` actually causes the kernel to aggressively evict file-backed page cache (including cached model weights) before touching swap, which can degrade inference performance. A value of `10` gives the best balance for inference workloads.

**Incorrect:**
```bash
echo 'vm.swappiness=0' | sudo tee -a /etc/sysctl.d/99-ai-server.conf
```

**Correct:**
```bash
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.d/99-ai-server.conf
```

---

### Pitfall 6: Not Including nofail on Non-Root Mounts

**Description:** A data disk or NFS mount is listed in `/etc/fstab` without `nofail`, and after a disk failure or network outage the server boots into emergency maintenance mode rather than continuing normally.

**Why it happens:** `nofail` is not part of the `defaults` option set and must be specified explicitly.

**Why it matters:** An AI inference server that becomes inaccessible because a secondary data disk is missing is worse than one that boots normally and simply lacks access to one of its model directories.

**Incorrect:**
```
UUID=a1b2c3d4-...  /data/models  xfs  defaults  0  2
```

**Correct:**
```
UUID=a1b2c3d4-...  /data/models  xfs  defaults,nofail  0  2
```

---

### Pitfall 7: Using ln -s With a Relative Source Path That Breaks After Moving the Symlink

**Description:** Creating a symlink with a relative path and then moving the symlink to a different directory, causing it to resolve to the wrong target.

**Why it happens:** `ln -s target linkname` is intuitive but the path is relative to the symlink's location, not the current directory.

**Incorrect:**
```bash
cd /data/models
ln -s llama-3-70b-v2 current      # Relative symlink — breaks if 'current' is moved
```

**Correct (use absolute paths for symlinks in production):**
```bash
ln -s /data/models/llama-3-70b-v2 /data/models/current
# Or verify what a symlink resolves to before relying on it:
readlink -f /data/models/current
```

---

## Summary

- Disk inspection (`lsblk`, `fdisk -l`, `blkid`), partitioning (`parted`), and filesystem creation (`mkfs.xfs`, `mkfs.ext4`) are the foundational steps before any storage can be used; always identify disks by UUID rather than device path to avoid boot failures after hardware changes.
- LVM abstracts physical disks into pools (volume groups) from which logical volumes can be carved and extended online, making it the correct tool for AI model storage where space requirements grow unpredictably as new model families are downloaded.
- NFS enables a single model repository to serve an entire inference cluster without duplicating terabytes of weights; mounting with `ro`, `hard`, `_netdev`, and `nofail` produces a robust setup that survives storage server outages without crashing inference nodes.
- `df`, `du`, and `ncdu` form a three-tier toolkit for disk usage investigation — `df` for per-filesystem summary, `du` for directory-level accounting, and `ncdu` for fast interactive exploration of large storage hierarchies.
- Symbolic links, `tmpfs` scratch space, conservative `vm.swappiness`, and proactive SMART monitoring (`smartctl`) collectively constitute the operational hygiene layer that keeps an AI model server running reliably at scale.

---

## Further Reading

- [Linux man page: lvm(8)](https://man7.org/linux/man-pages/man8/lvm.8.html) — The authoritative reference for all LVM subcommands, covering `pvcreate`, `vgcreate`, `lvcreate`, `lvextend`, and every flag they accept; essential when scripting automated volume management.

- [Red Hat Storage Administration Guide — LVM](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/configuring_and_managing_logical_volumes/index) — Red Hat's production-grade guide to LVM on RHEL 9 including clustered LVM, thin provisioning, and snapshot volumes; covers advanced use cases beyond the scope of this module.

- [Arch Linux Wiki: NFS](https://wiki.archlinux.org/title/NFS) — A comprehensive NFS setup and troubleshooting guide covering NFSv3 vs. NFSv4, Kerberos authentication, and common failure modes; the troubleshooting section is particularly useful when inference nodes cannot mount the model share.

- [XFS Documentation — xfs.org](https://xfs.wiki.kernel.org/) — The upstream XFS project wiki covering filesystem internals, `xfs_repair` usage, performance tuning via `mkfs.xfs` options, and known limitations including the no-shrink constraint.

- [smartmontools Documentation](https://www.smartmontools.org/wiki/TocDoc) — Full reference for `smartctl` and `smartd`, including how to interpret all SMART attribute IDs, configure automated testing schedules in `smartd.conf`, and set up email alerts for failing drives.

- [Linux Kernel Documentation: vm.swappiness](https://www.kernel.org/doc/html/latest/admin-guide/sysctl/vm.html) — The kernel's own documentation for all `vm.*` sysctl parameters, including the precise semantics of `swappiness` on Linux 5.8+ (which changed from the 0–100 scale behavior in earlier versions).

- [NFS Performance Tuning for Large Sequential Files — Linux Foundation](https://www.linuxfoundation.org/resources/) — Covers NFS `rsize`/`wsize` tuning, `async` vs. `sync`, and NFSv4.1 pNFS for parallel I/O — relevant when NFS throughput becomes the bottleneck for loading large model shards.

- [ncdu — NCurses Disk Usage](https://dev.yorhel.nl/ncdu) — The official site for ncdu including installation instructions, keyboard shortcuts, and JSON export mode for scripted disk usage reporting across multiple servers.
