# Module 7: GPU & CUDA Setup
> Subject: Linux | Difficulty: Intermediate | Estimated Time: 210 minutes

## Objective

After completing this module, you will be able to identify NVIDIA GPU hardware present on a Linux server using `lspci` and `lshw`, and explain why the open-source nouveau driver must be disabled before installing the official NVIDIA driver. You will install the NVIDIA proprietary driver on Ubuntu/Debian using the official NVIDIA network repository, verify the installation with `nvidia-smi`, and interpret its output fields: GPU utilization, memory consumption, temperature, power draw, and running processes. You will install the CUDA toolkit from the NVIDIA network repository, pin a specific CUDA version for reproducibility, and configure the mandatory `PATH` and `LD_LIBRARY_PATH` environment variables so that the compiler and runtime are discoverable. You will install the NVIDIA Container Toolkit, configure Docker to use the `nvidia` runtime by default, and run GPU-accelerated containers. You will confirm GPU availability from Python using `torch.cuda.is_available()` and related PyTorch calls, and diagnose the most common driver/CUDA version mismatch errors. Finally, you will understand the basics of multi-GPU enumeration and have awareness of AMD ROCm as the equivalent GPU compute stack for Radeon hardware.

---

## Prerequisites

- A Linux server (physical or cloud VM with GPU passthrough) running Ubuntu 22.04 LTS or Ubuntu 24.04 LTS — the commands in this module are written for these distributions; Debian 12 is also compatible with minor differences noted inline
- Root or `sudo` access to the server
- Familiarity with the Linux command line: package management with `apt`, editing files with a terminal editor, and reading shell output
- Basic understanding of what a device driver does and what a shared library is
- Docker Engine installed (any recent version — Docker Engine 26+ is assumed); if not yet installed, follow the official Docker documentation before the Container Toolkit section
- (Optional but recommended) A dedicated GPU — a consumer card such as an RTX 3080, RTX 4090, or a data-center card such as an A100/H100 will all work; the procedures are identical

> **Cloud note:** If you are using a cloud GPU instance (AWS p3/p4, GCP A2, Azure NC-series), the provider often pre-installs the NVIDIA driver. Run `nvidia-smi` first — if it succeeds, skip straight to the CUDA Toolkit section. If it fails, follow this module from the beginning.

---

## Key Concepts

### Why the GPU Needs Its Own Setup

Consumer and server operating systems ship with a minimal, open-source NVIDIA driver called **nouveau**. Nouveau handles basic display output but deliberately omits hardware-acceleration support for compute workloads — it does not expose the CUDA execution model at all. Any attempt to run Ollama, llama.cpp with CUDA, or PyTorch with GPU support will silently fall back to the CPU as long as nouveau is active.

The setup chain has a strict dependency order:

```
Hardware (PCIe slot)
    └── NVIDIA proprietary kernel module (driver)
            └── CUDA runtime libraries (libcuda, libcudart)
                    └── CUDA toolkit (nvcc compiler, cuDNN, etc.)
                            └── Application (PyTorch, llama.cpp, Ollama)
```

Every layer depends on the layer below it. A version mismatch at any boundary causes a failure. Understanding this stack is the most important conceptual foundation for troubleshooting GPU problems.

### The Driver–CUDA Version Relationship

NVIDIA maintains a **minimum driver version** required to run each CUDA release. A newer driver can always run older CUDA code (backward compatibility is guaranteed), but an older driver cannot run newer CUDA code.

| CUDA Version | Minimum Driver (Linux) |
|---|---|
| CUDA 12.0 | 525.60.13 |
| CUDA 12.1 | 530.30.02 |
| CUDA 12.2 | 535.54.03 |
| CUDA 12.3 | 545.23.06 |
| CUDA 12.4 | 550.54.14 |
| CUDA 12.5 | 555.42.02 |
| CUDA 12.6 | 560.28.03 |

> **Verify this table against the current NVIDIA release notes before production use.** NVIDIA publishes the authoritative table at https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html

The practical rule: always install the driver first, then install a CUDA version whose minimum driver requirement is at or below your installed driver version. If you install CUDA 12.4 and the package manager pulls in driver 550, you cannot later upgrade CUDA to 12.6 without also upgrading the driver to 560+.

---

## Section 1: Identifying Your GPU Hardware

Before installing anything, confirm that the system actually sees the GPU over PCIe.

### Using lspci

`lspci` lists all PCI/PCIe devices on the system. It reads from the kernel's PCI subsystem and requires no special privileges.

```bash
lspci | grep -i nvidia
```

Example output on a system with a single RTX 4090:

```
01:00.0 VGA compatible controller: NVIDIA Corporation AD102 [GeForce RTX 4090] (rev a1)
01:00.1 Audio device: NVIDIA Corporation AD102 High Definition Audio Controller (rev a1)
```

The first column (`01:00.0`) is the PCIe bus address in `BUS:DEVICE.FUNCTION` notation. The VGA-compatible controller line is the GPU itself. The audio device line is the HDMI audio output built into the same chip — it is harmless to see it here.

For more verbose output including the driver currently bound to the device:

```bash
lspci -k | grep -A 3 -i nvidia
```

Example output before installing the NVIDIA driver:

```
01:00.0 VGA compatible controller: NVIDIA Corporation AD102 [GeForce RTX 4090] (rev a1)
        Subsystem: NVIDIA Corporation Device 1685
        Kernel driver in use: nouveau
        Kernel modules: nvidiafb, nouveau
```

Once the NVIDIA proprietary driver is installed and loaded, the `Kernel driver in use` line will read `nvidia` instead of `nouveau`.

### Using lshw

`lshw` (List Hardware) produces a structured hardware inventory. The `-C video` flag limits output to video/display class devices. It requires `sudo` to read certain firmware details.

```bash
sudo lshw -C video
```

Example output:

```
  *-display
       description: VGA compatible controller
       product: AD102 [GeForce RTX 4090]
       vendor: NVIDIA Corporation
       physical id: 0
       bus info: pci@0000:01:00.0
       logical name: /dev/fb0
       version: a1
       width: 64 bits
       clock: 33MHz
       capabilities: pm msi pciexpress vga_controller bus_master cap_list rom fb
       configuration: depth=32 driver=nouveau latency=0 resolution=1024,768
       resources: iomemory:600-5ff iomemory:600-5ff irq:127 memory:...
```

The `configuration: driver=nouveau` entry confirms nouveau is active. After installing the NVIDIA driver this reads `driver=nvidia`.

> **If no NVIDIA device appears** in either `lspci` or `lshw`, stop. The GPU is either not physically seated, not receiving PCIe power, or the server's BIOS/UEFI has it disabled. No software step will fix a hardware or firmware problem.

---

## Section 2: Installing the NVIDIA Proprietary Driver

### Step 1 — Add the NVIDIA Package Repository

NVIDIA publishes its own APT repository that provides drivers, CUDA, and related libraries. Using this repository is strongly preferred over Ubuntu's `ubuntu-drivers` tool or manually downloaded `.run` installers because:

- Package manager tracks the installation and handles upgrades cleanly
- Dependencies (kernel headers, DKMS) are resolved automatically
- The repository is kept current as new driver versions are released

Install the prerequisites and add the keyring:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Download and install NVIDIA's GPG signing key
curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/3bf863cc.pub \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-archive-keyring.gpg
```

> **Ubuntu 22.04:** Replace `ubuntu2404` with `ubuntu2204` in the URL above and in all subsequent repository URLs in this section.

> **Debian 12:** Replace with `debian12` and the appropriate architecture string. See https://developer.download.nvidia.com/compute/cuda/repos/ for the full directory listing of supported distributions.

Add the repository to APT sources:

```bash
echo "deb [signed-by=/usr/share/keyrings/nvidia-archive-keyring.gpg] \
  https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/ /" \
  | sudo tee /etc/apt/sources.list.d/nvidia-cuda.list

sudo apt-get update
```

### Step 2 — Disable nouveau

The nouveau driver must be blacklisted before the NVIDIA driver can be loaded. If both modules are present, they will conflict and the system may fail to boot graphically or hang during driver initialization.

```bash
# Create a blacklist file for nouveau
sudo tee /etc/modprobe.d/blacklist-nouveau.conf <<'EOF'
blacklist nouveau
options nouveau modeset=0
EOF

# Regenerate the initramfs so the blacklist takes effect on next boot
sudo update-initramfs -u
```

### Step 3 — Install the Driver Package

List available driver versions from the NVIDIA repository:

```bash
apt-cache search nvidia-driver | grep "^nvidia-driver-[0-9]"
```

Install the current recommended production driver. As of mid-2025, the production branch for data-center and workstation use is the 550.x series; the latest open-kernel-module branch is the 560.x series. The exact current version in the repository takes precedence — substitute the version number you see in `apt-cache search`:

```bash
# Install driver (example: 550 series — confirm the latest from apt-cache search)
sudo apt-get install -y nvidia-driver-550
```

The meta-package `nvidia-driver-550` pulls in the kernel module (via DKMS), the userspace libraries (`libcuda1`, `libnvidia-compute-550`), and management tools.

> **DKMS** (Dynamic Kernel Module Support) compiles the NVIDIA kernel module against your running kernel headers. This happens automatically during installation. If kernel headers are missing, the build will fail. Fix with: `sudo apt-get install -y linux-headers-$(uname -r)`

### Step 4 — Reboot

```bash
sudo reboot
```

After rebooting, verify the driver loaded:

```bash
lsmod | grep nvidia
```

You should see several lines beginning with `nvidia`. If the output is empty, the module did not load — see the Troubleshooting section.

---

## Section 3: Verifying the Driver with nvidia-smi

`nvidia-smi` (NVIDIA System Management Interface) is the primary tool for inspecting GPU state. It is installed automatically with the driver package.

### Basic Output

```bash
nvidia-smi
```

```
Thu Apr 10 09:14:22 2026
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 550.144.03             Driver Version: 550.144.03   CUDA Version: 12.4      |
|-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 4090        Off |   00000000:01:00.0 Off |                  N/A |
| 30%   42C    P8              18W / 450W |       0MiB / 24564MiB |      0%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------------------------------------------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI        PID   Type   Process name                              GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|  No running compute processes found.                                                    |
+-----------------------------------------------------------------------------------------+
```

**Reading the output fields:**

| Field | Meaning |
|---|---|
| `Driver Version` | Installed NVIDIA kernel module version |
| `CUDA Version` | Maximum CUDA version this driver supports |
| `Persistence-M` | Persistence mode — keeps the driver loaded even when no compute job is running; reduces job startup latency |
| `Bus-Id` | PCIe bus address — matches the address seen in `lspci` |
| `Disp.A` | Display active — whether a monitor is attached and using this GPU |
| `Fan` | Fan speed as a percentage of maximum RPM |
| `Temp` | GPU die temperature in Celsius |
| `Perf` | Performance state, P0 (maximum performance) through P12 (minimum); P8 is a common idle state |
| `Pwr:Usage/Cap` | Current power draw / thermal design power (TDP) limit |
| `Memory-Usage` | VRAM used / total VRAM (MiB) |
| `GPU-Util` | Percentage of time the GPU compute units were active in the last sample window |
| `Compute M.` | Compute mode: Default (multiple processes share), Exclusive Process (one process at a time), or Prohibited |

### Useful nvidia-smi Flags

```bash
# Continuous monitoring, refreshed every 1 second
nvidia-smi -l 1

# Show all running compute processes with their VRAM consumption
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv

# Query specific fields for scripting (no table formatting)
nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total \
           --format=csv,noheader,nounits

# Show detailed information for each GPU in a verbose format
nvidia-smi -q

# Show only memory information
nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv,noheader
```

### Enabling Persistence Mode

For server deployments where GPUs will be repeatedly loaded and unloaded, persistence mode reduces the cold-start latency of CUDA initialization from several seconds to milliseconds:

```bash
sudo nvidia-smi -pm 1
```

To make persistence mode survive reboots, create a systemd service:

```bash
sudo tee /etc/systemd/system/nvidia-persistence.service <<'EOF'
[Unit]
Description=Enable NVIDIA Persistence Mode
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/nvidia-smi -pm 1
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now nvidia-persistence.service
```

---

## Section 4: Installing the CUDA Toolkit

The NVIDIA driver includes `libcuda.so` (the low-level CUDA driver API), but the CUDA toolkit provides the full development and runtime suite: `nvcc` (the CUDA compiler), `libcudart` (the CUDA runtime), `cuBLAS`, `cuDNN` (if installed separately), and header files. PyTorch and llama.cpp with CUDA backend require these libraries at runtime even if you do not compile CUDA code yourself.

### Installing a Pinned CUDA Version

Using a version-pinned package name rather than the unversioned `cuda` meta-package prevents surprise upgrades that could break a working environment.

```bash
# Install CUDA Toolkit 12.4 (adjust to your target version)
sudo apt-get install -y cuda-toolkit-12-4
```

The `cuda-toolkit-12-4` package installs:
- `/usr/local/cuda-12.4/` — the full toolkit tree
- A symlink `/usr/local/cuda` pointing to `/usr/local/cuda-12.4/`
- `nvcc`, `cuda-gdb`, profiling tools, and all runtime libraries

> **Do not install the unversioned `cuda` meta-package** unless you intentionally want the repository's current latest. It will pull in whatever version the repository currently defaults to, which changes when NVIDIA releases a new version and can break existing workflows.

### Installing Multiple CUDA Versions Side by Side

Multiple CUDA versions can coexist because each installs into its own versioned directory:

```bash
# Install both 12.2 and 12.4
sudo apt-get install -y cuda-toolkit-12-2 cuda-toolkit-12-4
```

Both will be present under `/usr/local/`:

```
/usr/local/cuda-12.2/
/usr/local/cuda-12.4/
/usr/local/cuda -> /usr/local/cuda-12.4/   (symlink, points to default)
```

Switching the active version is done by updating the symlink:

```bash
sudo ln -sfn /usr/local/cuda-12.2 /usr/local/cuda
```

---

## Section 5: CUDA Environment Variables

Two environment variables must be set for the system to find CUDA executables and shared libraries. Without them, running `nvcc` produces "command not found" and Python imports of CUDA-dependent libraries fail with linker errors.

### Setting Variables System-Wide (Recommended for Servers)

Create a profile script that is sourced for every login shell:

```bash
sudo tee /etc/profile.d/cuda.sh <<'EOF'
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
EOF

# Apply immediately in the current shell without logging out
source /etc/profile.d/cuda.sh
```

### Setting Variables Per-User

Add the same lines to `~/.bashrc` (non-login interactive shells) and `~/.bash_profile` or `~/.profile` (login shells) if you want per-user control:

```bash
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

### Verifying the Environment

```bash
# Confirm nvcc is on PATH and shows the expected version
nvcc --version
```

Expected output (for CUDA 12.4):

```
nvcc: NVIDIA (R) Cuda compiler driver
Copyright (c) 2005-2024 NVIDIA Corporation
Built on Thu_Mar_28_02:18:24_PDT_2024
Cuda compilation tools, release 12.4, V12.4.131
Build cuda_12.4.r12.4/compiler.33961263_0
```

```bash
# Confirm the runtime library is findable by the dynamic linker
ldconfig -p | grep libcuda
```

You should see `libcuda.so.1` listed. If not, run `sudo ldconfig` to refresh the linker cache, then check again.

---

## Section 6: NVIDIA Container Toolkit

The NVIDIA Container Toolkit (previously called `nvidia-docker2`) allows Docker containers to access the host's NVIDIA GPU. It works by injecting the NVIDIA driver libraries and device files into the container at runtime without baking them into the container image. This means a single image can run on any host that has a compatible driver — the container does not need to bundle its own driver.

### How It Works

```
Docker container
    └── requests GPU access via --gpus flag
            └── Docker runtime calls nvidia-container-runtime hook
                    └── Hook injects /dev/nvidia* device files
                    └── Hook bind-mounts libcuda.so from host into container
                            └── CUDA code inside container talks to actual GPU
```

Because the driver libraries are injected from the host, the CUDA toolkit version inside the container must be compatible with (i.e., require a driver no newer than) the host driver. The CUDA toolkit inside the container does not have to match the host — this is the key insight that makes CUDA container versioning manageable.

### Installing the NVIDIA Container Toolkit

Add the NVIDIA Container Toolkit repository and install:

```bash
# Add the repository GPG key
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

# Add the repository
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
```

### Configuring Docker to Use the NVIDIA Runtime

```bash
# Configure the NVIDIA runtime with the Docker daemon
sudo nvidia-ctk runtime configure --runtime=docker

# Restart Docker to apply the new runtime configuration
sudo systemctl restart docker
```

The `nvidia-ctk runtime configure` command edits `/etc/docker/daemon.json` to register the NVIDIA container runtime. Inspect the result:

```bash
cat /etc/docker/daemon.json
```

```json
{
    "runtimes": {
        "nvidia": {
            "args": [],
            "path": "nvidia-container-runtime"
        }
    }
}
```

Optionally, set the NVIDIA runtime as the Docker default so that every container has GPU access without specifying `--gpus`:

```bash
sudo tee /etc/docker/daemon.json <<'EOF'
{
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "args": [],
            "path": "nvidia-container-runtime"
        }
    }
}
EOF
sudo systemctl restart docker
```

> **Security consideration:** Setting `nvidia` as the default runtime means every container — including ones that do not need a GPU — will have the NVIDIA hooks run on startup. For most dedicated AI inference servers this is acceptable. For multi-tenant environments, leave it as an explicit opt-in (`--gpus` flag only).

### Verifying the Container Toolkit

Run `nvidia-smi` inside a container to confirm the toolkit is working end-to-end:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

You should see the same `nvidia-smi` table you see on the host. If this succeeds, any CUDA-capable container image will have GPU access on this host.

```bash
# Test with a specific GPU by index
docker run --rm --gpus '"device=0"' nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

# Test requesting a specific number of GPUs
docker run --rm --gpus 2 nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

---

## Section 7: Multi-GPU Basics

Servers with multiple GPUs are common in AI training workloads. Here is how to enumerate and address them.

### Listing All GPUs

```bash
nvidia-smi -L
```

```
GPU 0: NVIDIA A100 80GB PCIe (UUID: GPU-a1b2c3d4-...)
GPU 1: NVIDIA A100 80GB PCIe (UUID: GPU-e5f6a7b8-...)
GPU 2: NVIDIA A100 80GB PCIe (UUID: GPU-c9d0e1f2-...)
GPU 3: NVIDIA A100 80GB PCIe (UUID: GPU-03041516-...)
```

GPUs are zero-indexed. GPU 0 is the default device for any process that does not explicitly select a device.

### Controlling Which GPUs a Process Can See

The `CUDA_VISIBLE_DEVICES` environment variable restricts which GPUs are visible to a process. This is the standard way to assign workloads to specific GPUs on a shared server.

```bash
# Make only GPU 0 visible to the next command
CUDA_VISIBLE_DEVICES=0 python3 inference.py

# Make GPUs 0 and 2 visible (they appear as device 0 and 1 inside the process)
CUDA_VISIBLE_DEVICES=0,2 python3 train.py

# Hide all GPUs (force CPU execution)
CUDA_VISIBLE_DEVICES="" python3 script.py
```

Setting this variable persistently in `/etc/environment` or a user's `.bashrc` is a common way to partition GPUs among multiple users on a shared server.

### Per-GPU nvidia-smi Monitoring

```bash
# Monitor GPU 1 only
nvidia-smi -i 1

# Monitor all GPUs with per-GPU utilization in a loop
watch -n 2 nvidia-smi
```

---

## Section 8: Verifying GPU Access from Python

After installing the driver, CUDA toolkit, and (if using containers) the Container Toolkit, confirm that Python can reach the GPU through PyTorch — the most common framework for AI inference and training.

### Installing PyTorch with CUDA Support

Install PyTorch using the official index URL for your target CUDA version:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

Replace `cu124` with the CUDA version you installed (e.g., `cu122` for CUDA 12.2). The full list of available wheel variants is at https://download.pytorch.org/whl/torch/

### Basic GPU Availability Check

```python
import torch

print("PyTorch version:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
print("CUDA version PyTorch was built with:", torch.version.cuda)
print("Number of GPUs:", torch.cuda.device_count())

if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        print(f"  GPU {i}: {props.name}")
        print(f"    Total VRAM: {props.total_memory / 1024**3:.1f} GB")
        print(f"    CUDA Capability: {props.major}.{props.minor}")
        print(f"    Multiprocessors: {props.multi_processor_count}")
```

Expected output on a system with one RTX 4090:

```
PyTorch version: 2.4.0+cu124
CUDA available: True
CUDA version PyTorch was built with: 12.4
Number of GPUs: 1
  GPU 0: NVIDIA GeForce RTX 4090
    Total VRAM: 24.0 GB
    CUDA Capability: 8.9
    Multiprocessors: 128
```

### Running a Simple Tensor Operation on the GPU

```python
import torch

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)

# Allocate a large tensor on the GPU and do a matrix multiplication
a = torch.randn(4096, 4096, device=device)
b = torch.randn(4096, 4096, device=device)

import time
start = time.time()
c = torch.matmul(a, b)
# Synchronize to ensure the GPU has completed before measuring time
torch.cuda.synchronize()
elapsed = time.time() - start

print(f"Matrix multiply (4096x4096) on {device}: {elapsed * 1000:.1f} ms")
print(f"VRAM used after operation: {torch.cuda.memory_allocated() / 1024**2:.1f} MB")
```

If this script runs without error and `Using device: cuda` is printed, the full driver-CUDA-Python stack is working correctly.

---

## Section 9: Common Errors and How to Resolve Them

### Error: `nvidia-smi: command not found` after Installation

The driver package did not install cleanly, or the package manager installed the libraries but not the management tools.

```bash
# Check whether the nvidia-utils package is installed
dpkg -l | grep nvidia-utils

# If missing, install it explicitly
sudo apt-get install -y nvidia-utils-550
```

### Error: `NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver`

The kernel module is not loaded. This is the most common post-install error.

```bash
# Check if the module is loaded
lsmod | grep nvidia

# Attempt to load it manually and capture the error
sudo modprobe nvidia

# If modprobe fails, check the kernel log for the specific error
sudo dmesg | grep -i nvidia | tail -30
```

Common causes:
1. **Secure Boot is enabled** — The NVIDIA kernel module must be signed to load under Secure Boot. Either enroll a machine owner key (MOK) or disable Secure Boot in the BIOS/UEFI. DKMS should have offered to sign the module during installation if Secure Boot was detected.
2. **Kernel headers were missing during DKMS build** — The module was never compiled. Run `sudo dkms status` to check. If the NVIDIA module shows `build error`, install headers and rebuild: `sudo apt-get install -y linux-headers-$(uname -r) && sudo dkms autoinstall`
3. **nouveau is still loaded** — Verify the blacklist file exists and `update-initramfs -u` was run, then reboot again.

### Error: `torch.cuda.is_available()` Returns `False`

Work through this checklist in order:

```bash
# 1. Confirm the driver is loaded
nvidia-smi

# 2. Confirm the CUDA library is on LD_LIBRARY_PATH
ldconfig -p | grep libcuda

# 3. Confirm the PATH includes the CUDA bin directory
which nvcc

# 4. Check which CUDA version PyTorch was built for
python3 -c "import torch; print(torch.version.cuda)"
```

If `torch.version.cuda` shows `None`, you installed the CPU-only PyTorch wheel. Reinstall with the correct `--index-url` for your CUDA version (see Section 8).

If `torch.version.cuda` shows a version number but `is_available()` is still `False`, the installed CUDA version is newer than the driver supports:

```bash
# Driver's maximum supported CUDA is shown in nvidia-smi top line
nvidia-smi | head -3
# Compare to the CUDA version PyTorch requires
python3 -c "import torch; print(torch.version.cuda)"
```

If the PyTorch CUDA version is higher than the driver's maximum supported CUDA, either upgrade the driver or install an older PyTorch wheel.

### Error: `CUDA error: no kernel image is available for execution on the device`

This error means the PyTorch binary was compiled for an older GPU architecture (compute capability) than the GPU in the system. Example: a PyTorch wheel built for compute capability 7.x will not run on an older Kepler GPU (compute capability 3.x).

```bash
# Check your GPU's compute capability
nvidia-smi --query-gpu=compute_cap --format=csv,noheader
```

Install a PyTorch version that includes a PTX (portable) build for your architecture, or compile PyTorch from source with `TORCH_CUDA_ARCH_LIST` set to your GPU's compute capability.

### Version Conflict: Multiple CUDA Installations

If `nvcc --version` and `nvidia-smi`'s CUDA version disagree, check for multiple CUDA installations:

```bash
ls /usr/local/ | grep cuda
# Expected: cuda (symlink), cuda-12.2, cuda-12.4, etc.

# Confirm which version the symlink points to
readlink -f /usr/local/cuda
```

If an older `nvcc` from a system package is shadowing the CUDA toolkit installation, check PATH ordering:

```bash
which nvcc
# Should print /usr/local/cuda/bin/nvcc
# If it prints /usr/bin/nvcc, the system package is taking precedence
```

Ensure `/usr/local/cuda/bin` appears before `/usr/bin` in `PATH`.

---

## Section 10: Running AI Workloads with GPU Access

With the stack verified, here is how to confirm GPU usage with the most common AI tools.

### Ollama

Ollama detects the NVIDIA driver automatically at startup. After installation:

```bash
ollama serve &
ollama run llama3.2

# In a separate terminal, confirm Ollama is using the GPU
nvidia-smi --query-compute-apps=process_name,used_memory --format=csv
```

If Ollama is using the GPU, `ollama` will appear in the process list with VRAM usage.

### llama.cpp (CUDA build)

llama.cpp must be compiled with CUDA support — pre-built binaries may use CPU only:

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
mkdir build && cd build
cmake .. -DGGML_CUDA=ON
cmake --build . --config Release -j $(nproc)

# Run inference (substitute your model path)
./bin/llama-cli -m /path/to/model.gguf -p "Hello, world" -n 50 --n-gpu-layers 35
```

The `--n-gpu-layers` flag controls how many transformer layers are offloaded to the GPU. Set it to a large number (e.g., 999) to offload all layers, then reduce if you run out of VRAM.

Watch GPU utilization during inference:

```bash
watch -n 1 'nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader'
```

### PyTorch Inference Script

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

model_id = "meta-llama/Llama-3.2-1B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id)

# Load directly onto GPU
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.float16,
    device_map="cuda"
)

inputs = tokenizer("The capital of France is", return_tensors="pt").to("cuda")

with torch.no_grad():
    output = model.generate(**inputs, max_new_tokens=20)

print(tokenizer.decode(output[0], skip_special_tokens=True))
print(f"VRAM used: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
```

---

## Section 11: AMD GPUs and ROCm

If your server has an AMD Radeon or AMD Instinct GPU instead of NVIDIA, the equivalent compute stack is **ROCm** (Radeon Open Compute). ROCm aims for CUDA compatibility: PyTorch can be installed with ROCm support and many CUDA programs run unmodified through ROCm's HIP translation layer.

Key differences for AMD users:

| Topic | NVIDIA (CUDA) | AMD (ROCm) |
|---|---|---|
| Driver | `nvidia-driver-*` package | `amdgpu-dkms` (from `amdgpu-install` tool) |
| Compute runtime | CUDA | ROCm HIP |
| GPU query tool | `nvidia-smi` | `rocm-smi` |
| Compiler | `nvcc` | `hipcc` |
| PyTorch index | `--index-url .../whl/cu124` | `--index-url .../whl/rocm6.1` |
| Container toolkit | NVIDIA Container Toolkit | ROCm Docker (`--device /dev/kfd --device /dev/dri`) |
| Environment variable | `CUDA_VISIBLE_DEVICES` | `ROCR_VISIBLE_DEVICES` or `HIP_VISIBLE_DEVICES` |

Consumer AMD GPUs (RX 7000 series) have limited ROCm support compared to AMD Instinct data-center cards (MI250, MI300). Check the ROCm supported hardware list at https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html before committing to an AMD GPU for AI inference.

> This module focuses on NVIDIA/CUDA. ROCm installation is covered in depth in Module 8.

---

## Hands-On Exercises

### Exercise 1: Hardware Audit (15 minutes)

Run `lspci`, `lshw`, and `lsmod` on your server and document:
1. The full GPU model name and PCIe bus address
2. Which driver is currently bound (`nouveau` or `nvidia`)
3. Whether any NVIDIA modules are currently loaded

### Exercise 2: Driver Installation and Verification (30 minutes)

Following Section 2, install the NVIDIA driver from the official repository. After rebooting:
1. Confirm `lsmod | grep nvidia` shows loaded modules
2. Run `nvidia-smi` and record the Driver Version and maximum supported CUDA version
3. Enable persistence mode and verify it with `nvidia-smi -q | grep -i persistence`

### Exercise 3: CUDA Toolkit and Environment (20 minutes)

Install `cuda-toolkit-12-4` (or the current stable release). Then:
1. Set up `/etc/profile.d/cuda.sh` with the correct `PATH` and `LD_LIBRARY_PATH`
2. Open a new shell and confirm `nvcc --version` shows the expected version
3. Confirm `ldconfig -p | grep libcuda` returns at least one result

### Exercise 4: Container Toolkit Validation (25 minutes)

Install the NVIDIA Container Toolkit and configure Docker. Then:
1. Run `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` and confirm it outputs the same GPU table as the host
2. Run `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi --query-gpu=name,memory.total --format=csv` to verify GPU details are visible inside the container

### Exercise 5: Python GPU Validation (20 minutes)

Create a Python virtual environment, install PyTorch with CUDA support, and:
1. Run the basic GPU availability check from Section 8
2. Run the matrix multiplication benchmark script and record the time
3. Open a second terminal and watch `nvidia-smi -l 1` during the benchmark to confirm GPU utilization spikes

### Exercise 6: Fault Diagnosis (30 minutes)

Simulate a broken environment by temporarily unsetting `LD_LIBRARY_PATH`:

```bash
# In a subshell (does not permanently affect your session)
(unset LD_LIBRARY_PATH; python3 -c "import torch; print(torch.cuda.is_available())")
```

1. Record the error or unexpected output
2. Apply the diagnostic steps from Section 9 to identify the cause
3. Confirm the fix restores expected behavior

---

## Summary

A working GPU compute environment on Linux requires four distinct components installed in a specific order: the proprietary NVIDIA driver (which replaces nouveau and provides `libcuda`), the CUDA toolkit (which provides `nvcc` and `libcudart`), correctly configured environment variables (`PATH` and `LD_LIBRARY_PATH`), and — for containerized workloads — the NVIDIA Container Toolkit. Missing or mismatched any one of these four components produces a distinct class of error that can be diagnosed using `nvidia-smi`, `lsmod`, `ldconfig`, and `torch.cuda.is_available()`. Multi-GPU servers use `CUDA_VISIBLE_DEVICES` to route workloads to specific devices. AMD users follow the same conceptual sequence using ROCm in place of CUDA.

---

## Further Reading

- [CUDA Installation Guide for Linux — NVIDIA Official Docs](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/index.html) — The authoritative step-by-step guide for installing CUDA on every supported Linux distribution; includes the network and local repository methods, post-install actions, and the runfile installer as an alternative.
- [CUDA Toolkit Release Notes — NVIDIA](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html) — Lists every CUDA release with the minimum required driver version; essential for checking compatibility before upgrading either the driver or the toolkit.
- [NVIDIA Container Toolkit Installation Guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) — Official walkthrough for installing nvidia-container-toolkit, configuring Docker/Podman/containerd runtimes, and running validation tests.
- [nvidia-smi Documentation and Field Descriptions](https://developer.nvidia.com/nvidia-system-management-interface) — Complete reference for every `nvidia-smi` flag and output field, including the programmatic NVML library that `nvidia-smi` wraps.
- [PyTorch — Get Started (Official)](https://pytorch.org/get-started/locally/) — The official PyTorch installation matrix; select your OS, package manager, Python version, and CUDA version to get the exact `pip install` command with the correct `--index-url`.
- [ROCm Compatibility Matrix — AMD](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html) — Lists which AMD GPU architectures are supported by each ROCm release; use this before purchasing or deploying an AMD GPU for AI inference.
- [llama.cpp CUDA Build Instructions — GitHub](https://github.com/ggerganov/llama.cpp/blob/master/docs/build.md) — Official build instructions for llama.cpp with CUDA (GGML_CUDA), including CMake flags, troubleshooting compilation errors, and `--n-gpu-layers` guidance.
