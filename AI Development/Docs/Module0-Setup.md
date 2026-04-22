# Module 0: Setup & Local AI Stack
> Subject: AI Development | Difficulty: Beginner | Estimated Time: 150 minutes

## Objective

After completing this module, you will be able to explain why running models locally is a practical and often preferred alternative to cloud APIs, understand the key model file formats you will encounter (GGUF, Safetensors, GPTQ/AWQ) and choose the right quantization level for your available hardware, install and operate Ollama on Linux including pulling and running models interactively and querying the local REST API with `curl`, build llama.cpp from source, download a GGUF model from Hugging Face Hub, and run inference from the command line, and set up a Python virtual environment with all core packages (`ollama`, `llama-cpp-python`, `huggingface_hub`, `transformers`, `torch`) and verify each import works. By the end of this module your machine will be fully configured for every subsequent module in this series.

## Prerequisites

- A Linux machine or VM running Ubuntu 22.04 LTS / 24.04 LTS, Debian 12, Fedora 40+, or Arch Linux. Most steps also work on Windows Subsystem for Linux 2 (WSL2).
- Python 3.10 or later installed (`python3 --version` to check)
- `sudo` (administrator) privileges
- A terminal emulator and comfort with basic commands (file navigation, running scripts, editing text files with `nano` or `vim`)
- At least 8 GB of RAM and 20 GB of free disk space for the hands-on examples
- An internet connection for downloading packages and models
- No prior AI/ML development experience is required — this is the starting point for the series

## Key Concepts

### What Is Local AI Development?

Local AI development means running large language model inference entirely on your own hardware, with no network call to any external service. The model weights are downloaded once to your machine and executed by a runtime you control. Every token is generated on your CPU or GPU, and no prompt or response leaves your system.

This stands in contrast to cloud-based API services (such as the Anthropic or OpenAI APIs), which are production-ready and offer the largest frontier models, but require sending your data to a third-party server, incur per-token costs that accumulate quickly during development, and are unavailable when you are offline.

The main reasons developers choose local inference are:

- **Privacy.** Sensitive data — customer records, proprietary code, medical information — never leaves your network. This is a hard requirement in many regulated industries.
- **Cost.** After the one-time cost of sufficient hardware, running local models is free. Experimenting with thousands of prompts in a tight development loop costs nothing incrementally.
- **Offline operation.** A local stack works on a plane, in a restricted network environment, or anywhere an internet connection is unavailable or untrusted.
- **Latency control.** There is no network round-trip. On fast hardware, local inference latency for small models can match or beat cloud API response times for the first token.
- **Experimentation freedom.** You can run fine-tuned, uncensored, or custom models that are not available through any cloud provider. You can modify inference parameters and system prompts freely without platform restrictions.

The tradeoff is real: the most powerful frontier models (those with hundreds of billions of parameters) require data-center-class hardware to run locally. For learning, prototyping, and many production use cases, smaller quantized models running on a developer laptop are entirely adequate.

### The Local AI Stack

A functional local AI stack has three layers:

```
┌─────────────────────────────────────────────────┐
│  Application Layer                              │
│  (Python scripts, web UIs, chatbots, agents)    │
├─────────────────────────────────────────────────┤
│  Runtime Layer                                  │
│  (Ollama, llama.cpp, Hugging Face transformers) │
├─────────────────────────────────────────────────┤
│  Model Layer                                    │
│  (GGUF files, Safetensors weights, quantized    │
│   checkpoints stored on disk)                   │
└─────────────────────────────────────────────────┘
```

**Inference** is the process of running a trained model to produce output from a given input. Training adjusts model weights; inference uses fixed weights to generate predictions. Almost everything in this series is inference — you are running models that others have already trained, not training new ones from scratch.

The runtime layer is responsible for loading model weights from disk into RAM (or VRAM), executing the matrix multiplications that power the transformer architecture, and returning generated tokens to the caller. Different runtimes optimize for different things: Ollama prioritizes ease of use and API compatibility, llama.cpp prioritizes raw performance and broad hardware support, and Hugging Face `transformers` prioritizes ecosystem breadth and research flexibility.

### Model Formats

When you download a language model, it arrives as one of several file formats. Understanding them prevents confusion when you search Hugging Face Hub or follow tutorials.

**GGUF** (GGML Unified Format) is the primary format for local CPU and GPU inference today. It was introduced by the llama.cpp project as a replacement for the older GGML format. A GGUF file is a single self-contained binary that embeds the model weights along with all necessary metadata (architecture type, tokenizer, quantization scheme). This single-file design makes GGUF models easy to download, move, and share. Ollama uses GGUF internally. Most models intended for local use on Hugging Face Hub are available as GGUF.

**GGML** is the predecessor to GGUF. It required separate metadata and was less portable. You will occasionally encounter GGML files in older tutorials and repositories, but no new models are released in this format. If you see a `.bin` file described as "GGML," it predates GGUF. Do not use GGML files — download the GGUF version of the same model instead.

**Safetensors** is Hugging Face's open format for storing raw model weights safely (the "safe" refers to avoiding arbitrary code execution during loading, a risk with Python's `pickle`-based `.pt` format). Safetensors files are the standard format for models used with the Hugging Face `transformers` library. A model in Safetensors format is typically split across multiple `.safetensors` files. This format is used for full-precision (F16 or BF16) weights and for fine-tuning workflows. You will work with Safetensors in later modules on fine-tuning.

**GPTQ** and **AWQ** are quantization schemes applied on top of Safetensors-style weight files. They produce quantized models designed to run efficiently on NVIDIA GPUs. GPTQ (Generative Pre-trained Transformer Quantization) was one of the first widely-used 4-bit quantization approaches. AWQ (Activation-Aware Weight Quantization) is a more recent improvement that achieves better quality at the same bit width by identifying and preserving the most important weights. Both formats require specific kernels (`auto-gptq` or `autoawq` Python packages) to run and are primarily GPU-focused. For the CPU-centric workflow in this module, GGUF is the correct choice.

### Quantization Levels Explained

Quantization reduces the numerical precision of model weights to shrink file size and memory footprint. A full-precision model stores each weight as a 16-bit float (2 bytes per parameter). A quantized model reduces that to 8 bits, 4 bits, or fewer. The tradeoff is quality: more aggressive quantization means smaller size and faster inference, but introduces approximation error that can degrade response quality.

GGUF uses a naming scheme to describe quantization. The most important levels are:

| Format | Bits/Weight | Approx Size (7B) | Approx Size (13B) | Quality vs F16 | Best For |
|---|---|---|---|---|---|
| F16 | 16 | ~14 GB | ~26 GB | Reference (lossless) | GPU inference, quality benchmarking |
| Q8_0 | 8 | ~7.7 GB | ~14 GB | Near-lossless (~0.5% degradation) | Best quality that fits in RAM |
| Q5_K_M | 5 | ~5.0 GB | ~9.1 GB | Excellent (imperceptible for most tasks) | Sweet spot on 8–16 GB systems |
| Q4_K_M | 4 | ~4.1 GB | ~7.4 GB | Good (slight degradation on complex reasoning) | Default starting point for most learners |
| Q3_K_M | 3 | ~3.3 GB | ~5.8 GB | Noticeable degradation | When RAM is very tight |
| Q2_K | 2 | ~2.5 GB | ~4.5 GB | Significant degradation | Not recommended for general use |

The `K_M` suffix (K-Quant Medium) indicates a mixed-precision strategy where attention layers are kept at slightly higher precision than feed-forward layers. This produces noticeably better quality than older uniform quantization at the same average bit width. Prefer `K_M` variants over plain quantization levels (e.g., prefer `Q4_K_M` over `Q4_0`) whenever both are available.

**How to choose:** Start with `Q4_K_M` if you are RAM-constrained. Move to `Q5_K_M` or `Q8_0` if you have headroom and notice quality issues on reasoning-heavy tasks. Never run a model that requires more RAM than you physically have — this causes severe thrashing that makes inference unusably slow.

### Hardware Overview

**CPU Inference** is a fully valid path for learning and many production scenarios. Modern CPUs can run quantized 7B parameter models at 3–10 tokens per second, which is adequate for most interactive and batch tasks. The primary optimization lever for CPU inference is thread count: set the number of threads to match your physical core count (not hyperthreads). For example, on a 4-core / 8-thread CPU, use 4 threads. Using all 8 hyperthreads typically reduces throughput because the model's matrix math is memory-bandwidth-bound, not compute-bound.

RAM is the hard limit for CPU inference. The model weights must fit entirely in RAM at runtime. Add approximately 1–2 GB overhead above the model file size for the KV cache (the runtime's working memory for the context window). A rule of thumb:

| Model Size | Minimum RAM (Q4_K_M) | Comfortable RAM (Q5_K_M) | RAM for Q8_0 |
|---|---|---|---|
| 3B parameters | 4 GB | 5 GB | 6 GB |
| 7B parameters | 6 GB | 7 GB | 10 GB |
| 13B parameters | 10 GB | 12 GB | 16 GB |
| 34B parameters | 22 GB | 26 GB | 38 GB |
| 70B parameters | 42 GB | 48 GB | 78 GB |

**GPU Acceleration** dramatically increases tokens-per-second, but requires the model to fit in VRAM. Partial GPU offloading (loading some layers to GPU and keeping the rest in RAM) is supported by both Ollama and llama.cpp using the `-ngl` flag (number of GPU layers). This is useful when your model is slightly larger than your VRAM.

- **NVIDIA CUDA** — the most widely supported path. Requires CUDA toolkit 12.x installed alongside drivers. Both Ollama and llama.cpp auto-detect CUDA if the toolkit is present.
- **AMD ROCm** — supported by Ollama (via the ROCm build) and llama.cpp (via `-DGGML_HIP=ON`). Requires ROCm 6.x or later.
- **Apple Metal** — used on Apple Silicon Macs (M1, M2, M3, M4). Ollama uses Metal automatically on macOS. Not applicable to Linux.

This module covers GPU only at the conceptual level. GPU driver setup is outside scope here — the entire hands-on workflow runs correctly on CPU only.

### Choosing Your Runtime: Ollama vs llama.cpp vs Transformers

| Criterion | Ollama | llama.cpp (`llama-cli` / `llama-server`) | Hugging Face `transformers` |
|---|---|---|---|
| Installation effort | Very low (single script) | Moderate (build from source) | Low (`pip install`) |
| Model acquisition | `ollama pull <name>` (automatic) | Manual GGUF download from Hub | `from_pretrained()` auto-download |
| Model format | GGUF (managed internally) | GGUF (direct file path) | Safetensors (primary), GGUF (limited) |
| REST API | Built-in, OpenAI-compatible at `localhost:11434` | Built-in via `llama-server` at configurable port | Not built-in (use `FastAPI` wrapper) |
| Python SDK | `pip install ollama` | `pip install llama-cpp-python` | `pip install transformers` |
| Performance | Good (wraps llama.cpp internally) | Excellent (direct C++ with full flag control) | Good for GPU, slower on CPU |
| Hardware auto-detection | Yes (CUDA, ROCm, Metal) | Manual build flags required | Automatic via PyTorch |
| Best use case | Quick prototyping, local API server, chat UIs | Fine-grained inference control, production server | Research, fine-tuning, Hugging Face ecosystem |
| Model ecosystem | Ollama library (~hundreds of models) | Any GGUF on Hugging Face (~thousands) | Full Hugging Face Hub (~hundreds of thousands) |

**Recommendation for this series:** Install Ollama first for ease of use and interactive experimentation. Install llama.cpp for hands-on understanding of how inference actually works at the binary level. The `transformers` library becomes the focus in later modules covering fine-tuning and RAG.

---

## Section 1: Installing Ollama

### 1.1 Automated Install (Recommended)

Ollama distributes a shell script that detects your distribution, downloads the correct binary, creates a systemd service, and handles GPU library detection automatically.

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

The script will:
1. Download the Ollama binary to `/usr/local/bin/ollama`
2. Create an `ollama` system user for the service to run under
3. Install a systemd service unit at `/etc/systemd/system/ollama.service`
4. Enable and start the `ollama` service automatically
5. Detect NVIDIA or AMD GPU libraries if present

After the script finishes, verify the service is running:

```bash
sudo systemctl status ollama
```

Expected output (abbreviated):

```
● ollama.service - Ollama Service
     Loaded: loaded (/etc/systemd/system/ollama.service; enabled; preset: enabled)
     Active: active (running) since ...
```

Check the installed version:

```bash
ollama -v
```

Expected output:

```
ollama version is 0.6.x
```

### 1.2 Manual Install (Alternative)

If you need to install without running a remote shell script (common in corporate environments or airgapped machines), download the tarball directly:

```bash
# Download the AMD64 tarball
curl -L https://ollama.com/download/ollama-linux-amd64.tgz -o ollama-linux-amd64.tgz

# Extract to /usr (installs ollama binary to /usr/bin/ollama)
sudo tar -C /usr -xzf ollama-linux-amd64.tgz
```

Then create and enable the systemd service manually. First, create a dedicated user:

```bash
sudo useradd -r -s /bin/false -U -m -d /usr/share/ollama ollama
sudo usermod -a -G ollama $USER
```

Create the service file:

```bash
sudo tee /etc/systemd/system/ollama.service <<EOF
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="HOME=/usr/share/ollama"

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ollama
```

### 1.3 macOS

On macOS, install Ollama via the downloadable application from `https://ollama.com/download`. Open the `.dmg`, drag to Applications, and launch the app. Ollama runs in the menu bar and provides the same CLI and REST API on `localhost:11434`. macOS 14 Sonoma or later is required. All CLI commands in this module work identically on macOS.

### 1.4 The Ollama CLI Reference

| Command | Description |
|---|---|
| `ollama pull <model>` | Download a model from the Ollama library |
| `ollama run <model>` | Pull (if needed) and start an interactive chat session |
| `ollama run <model> "prompt"` | Run a model with a one-shot prompt (non-interactive) |
| `ollama list` | List all locally downloaded models with their sizes |
| `ollama ps` | List models currently loaded in memory |
| `ollama show <model>` | Display model architecture, parameter count, quantization, and license |
| `ollama rm <model>` | Remove a model from local storage |
| `ollama stop <model>` | Unload a model from memory without removing it |
| `ollama serve` | Start the Ollama server manually (use when not running as a systemd service) |
| `ollama -v` | Print the installed Ollama version |

### 1.5 The Ollama Model Library and REST API

The Ollama model library at `https://ollama.com/library` lists all models available via `ollama pull`. Each entry shows model variants as tags (e.g., `llama3.2:3b`, `llama3.2:1b`). The default tag when no tag is specified is `latest`, which typically points to the most capable variant that fits on consumer hardware.

Ollama exposes a local HTTP server on port `11434`. It provides two API surfaces:

- **Native API** at `http://localhost:11434/api/` — Ollama-specific format with endpoints such as `/api/generate` and `/api/chat`
- **OpenAI-compatible API** at `http://localhost:11434/v1/` — drop-in replacement for the OpenAI API format; compatible with any SDK or tool that targets OpenAI

The OpenAI-compatible endpoint matters because an enormous ecosystem of tools (SDKs, UIs, agent frameworks) already supports the OpenAI API format. Pointing them at `localhost:11434/v1` instead of `api.openai.com/v1` requires only a URL change.

---

## Section 2: Installing llama.cpp

### 2.1 Prerequisites

Install the build dependencies. You need `git`, `cmake`, `make`, and a C/C++ compiler.

**Ubuntu / Debian:**

```bash
sudo apt update
sudo apt install git cmake build-essential
```

**Fedora / RHEL:**

```bash
sudo dnf install git cmake gcc-c++ make
```

**Arch Linux:**

```bash
sudo pacman -S git cmake base-devel
```

Verify cmake is available:

```bash
cmake --version
```

Expected output:

```
cmake version 3.x.x
```

### 2.2 Clone and Build (CPU)

```bash
# Clone the repository
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp

# Configure the build (CPU-only, no GPU flags)
cmake -B build

# Compile — -j $(nproc) uses all available CPU cores to speed up compilation
cmake --build build --config Release -j $(nproc)
```

Compilation takes 3–10 minutes depending on your CPU. When it completes, the binaries are in `./build/bin/`:

```bash
ls build/bin/
```

Expected output includes (among others):

```
llama-cli
llama-server
llama-embedding
llama-bench
```

### 2.3 Build with NVIDIA CUDA Acceleration (Optional)

If you have an NVIDIA GPU and the CUDA toolkit installed (verify with `nvcc --version`), rebuild with the CUDA flag:

```bash
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j $(nproc)
```

Note: This flag changed from `-DLLAMA_CUDA=ON` (used in older documentation) to `-DGGML_CUDA=ON` in recent llama.cpp versions. Always refer to the repository's `docs/build.md` for the current flag names.

### 2.4 Downloading a GGUF Model from Hugging Face Hub

Install the `huggingface_hub` CLI tool:

```bash
pip install huggingface_hub
```

Download the Llama 3.2 3B Instruct model in Q4_K_M quantization from Bartowski's repository (a trusted GGUF conversion maintainer on Hugging Face):

```bash
huggingface-cli download bartowski/Llama-3.2-3B-Instruct-GGUF \
  --include "Llama-3.2-3B-Instruct-Q4_K_M.gguf" \
  --local-dir ./models
```

This downloads approximately 2 GB to `./models/Llama-3.2-3B-Instruct-Q4_K_M.gguf`.

### 2.5 Running Inference with llama-cli

```bash
./build/bin/llama-cli \
  -m ./models/Llama-3.2-3B-Instruct-Q4_K_M.gguf \
  -p "Explain what a transformer model is in two sentences." \
  -n 200 \
  -t $(nproc)
```

Key flags:

| Flag | Description |
|---|---|
| `-m <path>` | Path to the GGUF model file |
| `-p <text>` | The prompt to complete |
| `-n <number>` | Maximum number of tokens to generate (-1 for unlimited) |
| `-t <number>` | Number of CPU threads to use |
| `--temp <float>` | Sampling temperature (0.0 = deterministic, 1.0 = default creative) |
| `-cnv` | Enable conversation mode (maintains context across turns) |
| `-ngl <number>` | Number of layers to offload to GPU (0 = CPU only) |

### 2.6 Running the llama-server (Local API)

`llama-server` provides an HTTP API compatible with the OpenAI format, suitable for connecting Python scripts or other tools:

```bash
./build/bin/llama-server \
  -m ./models/Llama-3.2-3B-Instruct-Q4_K_M.gguf \
  --port 8080 \
  -t $(nproc)
```

The server starts on `http://localhost:8080`. A built-in web UI is available at that address in a browser. The OpenAI-compatible endpoint is at `http://localhost:8080/v1/chat/completions`.

---

## Section 3: Python Environment Setup

### 3.1 Python Version

All modules in this series require Python 3.10 or later. Check your version:

```bash
python3 --version
```

If you need to manage multiple Python versions, `pyenv` is the recommended tool. To install pyenv and set up Python 3.12 (the current stable release as of 2026):

```bash
# Install pyenv dependencies
sudo apt install -y build-essential libssl-dev zlib1g-dev libbz2-dev \
  libreadline-dev libsqlite3-dev libncursesw5-dev libxml2-dev \
  libxmlsec1-dev libffi-dev liblzma-dev

# Install pyenv
curl https://pyenv.run | bash

# Add to shell profile (.bashrc or .zshrc)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc
source ~/.bashrc

# Install Python 3.12
pyenv install 3.12
pyenv global 3.12
```

If your system Python is already 3.10+, you can skip pyenv entirely.

### 3.2 Creating a Virtual Environment

Always use a virtual environment for Python AI work. The packages in this space are large and frequently updated, and installing them globally is a reliable way to create version conflicts.

```bash
# Create a virtual environment named .venv in the current directory
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Confirm you are in the virtual environment
which python
# Expected output: /path/to/.venv/bin/python
```

Your shell prompt should now show `(.venv)` as a prefix. Every `pip install` from this point installs packages only into this environment.

### 3.3 Installing Core Packages

Install all required packages for this module series:

```bash
pip install --upgrade pip

# Ollama Python SDK
pip install ollama

# llama.cpp Python bindings (CPU build)
pip install llama-cpp-python

# Hugging Face ecosystem
pip install huggingface_hub transformers

# PyTorch (CPU-only build — significantly smaller download)
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

> **CUDA build for llama-cpp-python (optional):** If you have an NVIDIA GPU, install the CUDA-enabled build instead. This compiles llama.cpp with CUDA support during `pip install`:
> ```bash
> CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python
> ```
> This takes significantly longer than the CPU build and requires the CUDA toolkit (`nvcc`) to be on your PATH.

### 3.4 requirements.txt for This Series

Create a `requirements.txt` file to document and reproduce the environment:

```
ollama>=0.4.0
llama-cpp-python>=0.3.0
huggingface_hub>=0.27.0
transformers>=4.47.0
torch>=2.5.0
```

To install from this file on a fresh environment:

```bash
pip install -r requirements.txt
```

For the PyTorch CPU-only variant, use:

```bash
pip install -r requirements.txt --index-url https://download.pytorch.org/whl/cpu
```

### 3.5 Verifying All Imports

Test that every package installed correctly:

```python
# save as verify_setup.py and run with: python verify_setup.py

import importlib
import sys

packages = [
    ("ollama", "ollama"),
    ("llama_cpp", "llama-cpp-python"),
    ("huggingface_hub", "huggingface_hub"),
    ("transformers", "transformers"),
    ("torch", "torch"),
]

all_ok = True
for module_name, package_name in packages:
    try:
        mod = importlib.import_module(module_name)
        version = getattr(mod, "__version__", "unknown")
        print(f"  OK  {package_name} (version: {version})")
    except ImportError as e:
        print(f"  FAIL  {package_name}: {e}")
        all_ok = False

if all_ok:
    print("\nAll packages imported successfully. Environment is ready.")
else:
    print("\nSome packages failed to import. Check the errors above.")
    sys.exit(1)
```

Expected output:

```
  OK  ollama (version: 0.4.x)
  OK  llama-cpp-python (version: 0.3.x)
  OK  huggingface_hub (version: 0.27.x)
  OK  transformers (version: 4.47.x)
  OK  torch (version: 2.5.x)

All packages imported successfully. Environment is ready.
```

---

## Best Practices

1. **Always match model size to available RAM before downloading.** Attempting to run a model larger than your RAM does not cause a clean error — it causes thrashing that makes the session unusable. Use the RAM table in the Hardware section to choose a model size your system can handle comfortably.

2. **Prefer `Q4_K_M` or `Q5_K_M` over older Q4_0 and Q5_0 variants.** The `K_M` (K-Quant Medium) variants use mixed-precision quantization that preserves attention layer quality. At the same average bit width, `Q4_K_M` produces noticeably better output than `Q4_0` with the same memory footprint.

3. **Use virtual environments for every AI project without exception.** AI/ML packages are large, fast-moving, and regularly introduce breaking changes. Global installations of `torch`, `transformers`, or `llama-cpp-python` will conflict across projects within weeks.

4. **Set thread count explicitly for llama.cpp CPU inference.** The default thread count is often not optimal. Use `-t $(nproc)` to set threads to your physical core count. Avoid using hyperthreads (logical cores) — for memory-bandwidth-bound workloads like LLM inference, more threads beyond physical cores reduces throughput.

5. **Let Ollama manage models rather than manually placing GGUF files.** Ollama tracks model versions, handles storage in `~/.ollama/models`, and cleans up correctly. Placing model files manually in arbitrary locations works but creates version confusion over time.

6. **Keep llama.cpp up to date by pulling and rebuilding regularly.** llama.cpp releases are frequent and often include support for new model architectures, quantization formats, and performance improvements. Running `git pull && cmake --build build --config Release -j $(nproc)` from the repo directory updates the binary without re-cloning.

7. **Use the OpenAI-compatible endpoints (`/v1/`) rather than native APIs when building integrations.** Both Ollama and llama-server expose `/v1/chat/completions`. Building against this interface means your integration code is portable — you can swap between Ollama, llama-server, and actual cloud APIs by changing only the base URL and API key.

8. **Verify GPU detection before running inference.** Both Ollama and llama.cpp will silently fall back to CPU if GPU libraries are not found. Check `ollama show <model>` for a GPU layers indicator, or watch for `ggml_cuda_init: GGML_CUDA_FORCE_MMQ` in llama.cpp output to confirm CUDA is active.

---

## Use Cases

### Use Case 1: Private Coding Assistant for a Development Team

A software consultancy handles client code that is covered by NDAs. Sending code snippets to a cloud API would violate those agreements. The team installs Ollama on a shared development server, pulls a code-capable model (such as `qwen2.5-coder:7b`), and points their IDE extensions at `http://server-ip:11434/v1`. Every code completion and explanation stays within the internal network. The concepts from this module that apply are the Ollama installation and REST API configuration, the OpenAI-compatible endpoint for IDE tool compatibility, and the hardware RAM-to-model-size matching to choose a model that fits the server's memory.

### Use Case 2: Offline Document Processing Pipeline

A researcher needs to process several thousand PDF documents to extract structured data. The pipeline will run on a laptop during field work with no internet access. Using `llama-cpp-python` directly in a Python script, they load a quantized 7B model once at startup and process documents in a loop. No API keys, no network calls, no per-document cost. The concepts that apply are the Python environment setup from Section 3, the llama-cpp-python CPU build, and RAM capacity planning to ensure the model and document buffers fit in memory.

### Use Case 3: Learning Prompt Engineering Without API Cost Anxiety

A developer new to LLMs wants to run hundreds of prompt experiments to understand how system prompts, temperature, and context affect outputs. Running every experiment through a cloud API would cost tens of dollars and introduce latency. With Ollama running locally, experiments are free and nearly instantaneous for small models. The developer uses `ollama run llama3.2:3b` for quick interactive testing and switches to the Python `ollama` SDK for scripted batch experiments. The concepts that apply are Ollama installation, the CLI interactive mode, and the Python SDK setup.

### Use Case 4: Prototype Before Committing to a Cloud Provider

A startup is evaluating whether an LLM fits their product before deciding on a cloud provider. They use a local stack to prototype the entire application logic — conversation management, system prompts, response parsing — using a small local model as a stand-in. Because both Ollama and llama-server expose an OpenAI-compatible API, swapping to a production cloud endpoint later requires only changing the base URL and API key in one configuration file. The concepts that apply are the OpenAI-compatible endpoint understanding and the comparison table in the Key Concepts section.

---

## Hands-on Examples

### Example 1: Install Ollama, Run a Model Interactively, and Query the REST API

In this example you will install Ollama on a fresh Linux system, pull the Llama 3.2 3B model, run it interactively in the terminal, and then call it programmatically using `curl` against the local REST API.

**Step 1:** Install Ollama using the automated script.

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Wait for the script to complete. The output will report that the service is started and enabled.

**Step 2:** Confirm the service is running.

```bash
sudo systemctl status ollama
```

Expected output includes `Active: active (running)`.

**Step 3:** Pull the Llama 3.2 3B model.

```bash
ollama pull llama3.2:3b
```

Expected output:

```
pulling manifest
pulling dde5aa3fc5ff: 100% |█████████| 2.0 GB/2.0 GB
pulling 966de95ca8a6: 100% |█████████| 1.4 KB/1.4 KB
pulling fcc5a6bec9da: 100% |█████████| 7.7 KB/7.7 KB
pulling a70ff7e570d9: 100% |█████████| 6.0 KB/6.0 KB
pulling 56bb8bd477a5: 100% |█████████| 96 B/96 B
verifying sha256 digest
writing manifest
success
```

**Step 4:** Inspect the model details.

```bash
ollama show llama3.2:3b
```

Expected output:

```
  Model
    architecture        llama
    parameters          3.2B
    context length      131072
    embedding length    3072
    quantization        Q4_K_M

  Parameters
    stop    "<|start_header_id|>"
    stop    "<|end_header_id|>"
    stop    "<|eot_id|>"
```

**Step 5:** Run the model interactively.

```bash
ollama run llama3.2:3b
```

The shell drops into an interactive chat prompt. Type a message and press Enter:

```
>>> What is a large language model in one sentence?
A large language model (LLM) is a type of artificial intelligence trained on
massive amounts of text data to understand, generate, and reason about natural
language.

>>> /bye
```

Type `/bye` to exit the interactive session.

**Step 6:** Query the model via the REST API using `curl`.

The Ollama server is already running on `localhost:11434`. Use the native `/api/generate` endpoint:

```bash
curl http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:3b",
    "prompt": "What is inference in the context of machine learning? Answer in one sentence.",
    "stream": false
  }'
```

Expected response (JSON, formatted for readability):

```json
{
  "model": "llama3.2:3b",
  "created_at": "2026-04-14T10:00:00.000Z",
  "response": "In the context of machine learning, inference refers to the process of using a trained model to make predictions or generate outputs from new input data, without any further training.",
  "done": true,
  "total_duration": 4521000000,
  "eval_count": 45
}
```

**Step 7:** Use the OpenAI-compatible endpoint (the format all later modules use):

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:3b",
    "messages": [
      {"role": "system", "content": "You are a concise technical assistant."},
      {"role": "user", "content": "What is the difference between a 7B and 13B model?"}
    ]
  }'
```

Expected response (JSON, abbreviated):

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "model": "llama3.2:3b",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "A 7B model has 7 billion parameters while a 13B model has 13 billion. The 13B model generally produces higher quality outputs and handles complex reasoning better, but requires roughly twice the RAM and runs at half the speed on the same hardware."
      },
      "finish_reason": "stop"
    }
  ]
}
```

---

### Example 2: Build llama.cpp from Source and Run CLI Inference

In this example you will build the llama.cpp binaries from source, download a GGUF model from Hugging Face, and run a single-shot inference from the command line.

**Step 1:** Install build dependencies (Ubuntu/Debian shown; adapt for your distro per Section 2.1).

```bash
sudo apt update
sudo apt install git cmake build-essential
```

**Step 2:** Clone the repository.

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
```

**Step 3:** Build the project (CPU-only).

```bash
cmake -B build
cmake --build build --config Release -j $(nproc)
```

The build output will show compilation progress. Expect output like:

```
-- The C compiler identification is GNU 13.x
-- The CXX compiler identification is GNU 13.x
...
[100%] Built target llama-cli
[100%] Built target llama-server
```

**Step 4:** Verify the binary is present.

```bash
./build/bin/llama-cli --version
```

Expected output:

```
version: xxxx (some_git_hash)
built with cc (GCC) ...
```

**Step 5:** Install the Hugging Face CLI and download a model.

```bash
pip install huggingface_hub

huggingface-cli download bartowski/Llama-3.2-3B-Instruct-GGUF \
  --include "Llama-3.2-3B-Instruct-Q4_K_M.gguf" \
  --local-dir ./models
```

Expected output:

```
Fetching 1 files: 100%|██████████| 1/1 [02:30<00:00]
./models/Llama-3.2-3B-Instruct-Q4_K_M.gguf
```

**Step 6:** Run inference from the CLI.

```bash
./build/bin/llama-cli \
  -m ./models/Llama-3.2-3B-Instruct-Q4_K_M.gguf \
  -p "Write a Python function that reverses a string." \
  -n 200 \
  -t $(nproc) \
  --temp 0.2
```

Expected output includes the model's response followed by performance statistics:

```
def reverse_string(s):
    return s[::-1]

llama_print_timings:        load time =    832.45 ms
llama_print_timings:      sample time =     12.31 ms /    55 runs
llama_print_timings: prompt eval time =    234.56 ms /    12 tokens
llama_print_timings:        eval time =   3421.00 ms /    55 runs (   62.20 ms per token,   16.08 tokens/sec)
```

**Step 7:** Start the llama-server and query it via curl.

In one terminal, start the server:

```bash
./build/bin/llama-server \
  -m ./models/Llama-3.2-3B-Instruct-Q4_K_M.gguf \
  --port 8080 \
  -t $(nproc)
```

Expected startup output:

```
llama server listening at http://0.0.0.0:8080
```

In a second terminal, send a request:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is GGUF format in one sentence?"}
    ]
  }'
```

---

### Example 3: Set Up a Python Virtual Environment and Verify All Imports

In this example you will create a clean Python virtual environment, install all core packages for the series, and run a verification script that confirms each package is correctly installed and can communicate with Ollama.

**Step 1:** Create a working directory and enter it.

```bash
mkdir ai-dev-training
cd ai-dev-training
```

**Step 2:** Create and activate the virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt should now show `(.venv)` as a prefix.

**Step 3:** Upgrade pip and install all packages.

```bash
pip install --upgrade pip

pip install ollama llama-cpp-python huggingface_hub transformers

pip install torch --index-url https://download.pytorch.org/whl/cpu
```

This will take 3–10 minutes depending on your connection speed. PyTorch CPU-only is approximately 200 MB.

**Step 4:** Create the verification script.

```bash
cat > verify_setup.py << 'EOF'
import importlib
import sys

packages = [
    ("ollama", "ollama"),
    ("llama_cpp", "llama-cpp-python"),
    ("huggingface_hub", "huggingface_hub"),
    ("transformers", "transformers"),
    ("torch", "torch"),
]

all_ok = True
for module_name, package_name in packages:
    try:
        mod = importlib.import_module(module_name)
        version = getattr(mod, "__version__", "unknown")
        print(f"  OK  {package_name} (version: {version})")
    except ImportError as e:
        print(f"  FAIL  {package_name}: {e}")
        all_ok = False

print()

# Test live connection to Ollama
try:
    import ollama
    models = ollama.list()
    print(f"  OK  Ollama server reachable — {len(models.models)} model(s) available locally")
except Exception as e:
    print(f"  WARN  Ollama server not reachable: {e}")
    print("        Start Ollama with: ollama serve")

if all_ok:
    print("\nEnvironment is ready for the AI Development series.")
else:
    print("\nSome packages failed to import. Re-run the install steps above.")
    sys.exit(1)
EOF
```

**Step 5:** Run the verification script.

```bash
python verify_setup.py
```

Expected output:

```
  OK  ollama (version: 0.4.x)
  OK  llama-cpp-python (version: 0.3.x)
  OK  huggingface_hub (version: 0.27.x)
  OK  transformers (version: 4.47.x)
  OK  torch (version: 2.5.x)

  OK  Ollama server reachable — 1 model(s) available locally

Environment is ready for the AI Development series.
```

**Step 6:** Create the `requirements.txt` for the series.

```bash
pip freeze | grep -E "^(ollama|llama.cpp|huggingface.hub|transformers|torch)==" > requirements.txt
cat requirements.txt
```

Alternatively, create it manually with version lower bounds:

```bash
cat > requirements.txt << 'EOF'
ollama>=0.4.0
llama-cpp-python>=0.3.0
huggingface_hub>=0.27.0
transformers>=4.47.0
torch>=2.5.0
EOF
```

---

## Common Pitfalls

### Pitfall 1: Choosing a Model Too Large for Available RAM

**Description:** Downloading and attempting to run a 13B parameter model on a machine with 8 GB of RAM.

**Why it happens:** Model file sizes look manageable (a `Q4_K_M` 13B file is about 7.4 GB), but the runtime needs additional RAM for the KV cache, the runtime itself, and other system processes. The total exceeds available RAM and the OS begins swapping to disk.

**Incorrect pattern:**
```bash
# On an 8 GB RAM machine
ollama pull llama3:13b
ollama run llama3:13b
# Model loads extremely slowly or freezes entirely due to swap
```

**Correct pattern:**
```bash
# Check available RAM first
free -h
# Available: ~6 GB free

# Choose a model that fits comfortably
ollama pull llama3.2:3b   # 2.0 GB — fits easily
```

---

### Pitfall 2: CUDA Not Detected by Ollama or llama.cpp

**Description:** A machine has an NVIDIA GPU but inference still uses the CPU, resulting in slow throughput.

**Why it happens:** CUDA support requires both the NVIDIA driver and the CUDA toolkit runtime to be installed. Having only the GPU driver is not sufficient. Additionally, Ollama must have been installed after the CUDA toolkit, or the ROCm/CUDA libraries were not present at install time.

**Symptom:** `ollama show llama3.2:3b` shows no GPU layer information. llama.cpp output does not show `ggml_cuda_init`.

**Incorrect assumption:**
```bash
# GPU driver installed, but CUDA toolkit missing
nvidia-smi   # Shows GPU fine
nvcc --version  # Command not found -- CUDA toolkit not installed
ollama run llama3.2:3b  # Runs on CPU silently
```

**Correct pattern:**
```bash
# Verify CUDA toolkit is installed
nvcc --version
# If missing, install: sudo apt install nvidia-cuda-toolkit

# After CUDA toolkit install, reinstall Ollama to pick up CUDA libraries
curl -fsSL https://ollama.com/install.sh | sh
```

---

### Pitfall 3: Installing llama-cpp-python Without a C Compiler

**Description:** `pip install llama-cpp-python` fails with a compilation error.

**Why it happens:** `llama-cpp-python` compiles llama.cpp from source during `pip install`. It requires `gcc`, `g++`, and `cmake`. On minimal cloud VMs or fresh WSL installs, these build tools are often absent.

**Symptom:**
```
error: command 'gcc' failed: No such file or directory
```

**Correct pattern:**
```bash
# Ubuntu/Debian: install build tools first
sudo apt install build-essential cmake

# Then install the package
pip install llama-cpp-python
```

---

### Pitfall 4: Running ollama Commands When the Daemon Is Not Started

**Description:** Running `ollama run` or `ollama pull` fails because the Ollama service is not running.

**Why it happens:** On systems where Ollama was installed manually (not via the install script), the systemd service may not be running. Also occurs after a reboot if the service was not enabled.

**Symptom:**
```
Error: could not connect to ollama app, is it running?
```

**Incorrect pattern:**
```bash
# Trying to pull without the daemon running
ollama pull llama3.2:3b
# Error: could not connect to ollama app
```

**Correct pattern:**
```bash
# Option A: Start and enable the service (persistent across reboots)
sudo systemctl enable --now ollama

# Option B: Run the server in the foreground for testing
ollama serve
# Then run ollama commands in a second terminal
```

---

### Pitfall 5: Using GGML Model Files Instead of GGUF

**Description:** Downloading a `.bin` file described as a "GGML model" and attempting to use it with llama.cpp or Ollama, resulting in a load failure.

**Why it happens:** Older Hugging Face repositories and tutorials from 2023 and earlier used the GGML format. The format was superseded by GGUF in August 2023. Many search results still link to GGML repositories.

**Symptom:**
```
llama_model_load: error loading model: ...
```
Or the file loads but produces garbled output.

**Correct pattern:**
```bash
# Search for a GGUF version — look for repositories with "GGUF" in the name
# Bartowski and the original author's own pages are reliable sources
huggingface-cli download bartowski/Llama-3.2-3B-Instruct-GGUF \
  --include "*.gguf" \
  --local-dir ./models
```

---

### Pitfall 6: Wrong Virtual Environment Active When Installing Packages

**Description:** Packages are installed globally instead of into the project virtual environment, causing import errors when the correct environment is activated later.

**Why it happens:** Running `pip install` in a terminal where the virtual environment has not been activated (or was deactivated) installs packages globally. The virtual environment then cannot find them.

**Symptom:**
```python
# Inside .venv
import ollama
# ModuleNotFoundError: No module named 'ollama'
```

**Correct pattern:**
```bash
# Always check which Python/pip you are using
which python   # Should show .venv/bin/python
which pip      # Should show .venv/bin/pip

# If not inside .venv, activate it first
source .venv/bin/activate

# Then install
pip install ollama
```

---

## Summary

- Local AI development means running model inference entirely on your own hardware, offering privacy, zero per-token cost, offline capability, and freedom to experiment with any model — at the cost of being limited to models your hardware can fit in RAM.
- GGUF is the standard format for local inference; prefer `Q4_K_M` as a default quantization level and move to `Q5_K_M` or `Q8_0` as RAM allows. Avoid the legacy GGML format entirely.
- Ollama is the easiest entry point — a single `curl` install script sets up a systemd service, a full CLI, and an OpenAI-compatible REST API on `localhost:11434` that works with any existing OpenAI-compatible tool.
- llama.cpp provides direct C++ performance with fine-grained control over threads, GPU layer offloading, and sampling parameters; build it from source with `cmake`, then run `llama-cli` for single-shot inference or `llama-server` for a local API server.
- A Python virtual environment with `ollama`, `llama-cpp-python`, `huggingface_hub`, `transformers`, and `torch` provides the full foundation for every module in this series.

## Further Reading

- [Ollama Official Documentation — Linux Install](https://docs.ollama.com/linux) — The authoritative guide to installing Ollama on Linux, including manual install steps, GPU configuration (NVIDIA CUDA and AMD ROCm), and systemd service management.
- [Ollama CLI Reference](https://docs.ollama.com/cli) — Complete reference for all Ollama CLI commands with syntax descriptions; covers `run`, `pull`, `serve`, `ps`, `show`, `rm`, `stop`, and more.
- [Ollama REST API Reference](https://github.com/ollama/ollama/blob/main/docs/api.md) — Documents every native Ollama API endpoint (`/api/generate`, `/api/chat`, `/api/tags`, etc.) with request/response schemas and curl examples; the source of truth for programmatic Ollama integration.
- [llama.cpp Build Documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md) — The official build instructions for llama.cpp on all platforms, including all current cmake flag names for CUDA, ROCm, Vulkan, and BLAS acceleration.
- [llama-cpp-python on PyPI](https://pypi.org/project/llama-cpp-python/) — PyPI page for the Python bindings, listing current version, CPU build instructions, CUDA/ROCm wheel options, and links to the full documentation.
- [GGUF Format Documentation — Hugging Face Hub](https://huggingface.co/docs/hub/gguf) — Explains the GGUF file format structure, metadata fields, and how Hugging Face Hub handles GGUF model discovery; useful background for understanding what a GGUF file contains.
- [Hugging Face Hub CLI Guide](https://huggingface.co/docs/huggingface_hub/main/en/guides/cli) — Complete reference for `huggingface-cli download`, including `--include` glob patterns for selective file download, `--local-dir` options, and authentication for gated models.
- [Ollama OpenAI Compatibility](https://docs.ollama.com/api/openai-compatibility) — Documents which OpenAI API endpoints Ollama supports (`/v1/chat/completions`, `/v1/models`, `/v1/embeddings`, etc.) and notes on any behavioral differences; essential reading before building OpenAI-compatible integrations on top of Ollama.
