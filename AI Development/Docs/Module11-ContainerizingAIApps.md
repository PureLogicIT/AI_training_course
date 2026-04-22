# Module 11: Containerizing AI Apps
> Subject: AI Development | Difficulty: Advanced | Estimated Time: 390 minutes

## Objective

After completing this module, you will be able to explain why containerization solves the reproducibility problems specific to Python AI applications, write production-ready Dockerfiles for FastAPI and LangChain applications that handle heavy ML dependencies correctly, choose and implement the right strategy for getting model files into a container (volume mount, download at startup, or bake-in), run Ollama inside Docker and connect it to sibling application containers using Docker Compose networking, compose a complete local AI stack — Ollama, ChromaDB, and a FastAPI RAG API — using a single `docker-compose.yml` with proper health checks and persistent volumes, configure NVIDIA GPU passthrough for GPU-accelerated inference, and maintain a fast development workflow inside containers using bind mounts and Compose override files. All examples run locally on a Linux host with Docker installed — no cloud provider account is required.

---

## Prerequisites

- Completed **Module 0: Setup and Local AI Stack** — familiar with Ollama, model formats, and local inference
- Completed **Module 1: Working with Local Models** — comfortable with the Ollama REST API
- Completed **Module 3: LangChain Fundamentals** — understands chains and LangChain model wrappers
- Completed **Module 4: RAG** — understands RAG pipelines, embedding models, and vector stores
- Docker Engine installed and running (`docker --version` should show Engine 26 or later)
- Familiarity with Docker fundamentals: images, containers, volumes, port mapping, basic Dockerfile authoring
- Python 3.11 installed on the host (for local testing of app code before containerizing)
- A Linux host or WSL2 environment — all commands are written for Linux shell syntax

---

## Key Concepts

### 1. Why Containerize AI Apps

#### The Reproducibility Problem in AI Development

Python AI applications have a dependency problem that is more severe than typical web applications. A FastAPI CRUD service depends on a handful of pure-Python packages. A FastAPI RAG service depends on:

- `torch` (300–2000 MB depending on CUDA variant, compiled for a specific CUDA version)
- `transformers` (pinned to a specific model architecture version)
- `langchain`, `langchain-chroma`, `langchain-ollama` (rapidly evolving, frequent breaking changes)
- `chromadb` (which brings its own compiled C extensions)
- `llama-cpp-python` (which must be compiled against the right OpenMP and CPU architecture flags)
- System-level shared libraries: `libgomp.so.1`, `libstdc++`, sometimes `libcuda.so`

When a colleague pulls your repository and runs `pip install -r requirements.txt`, they are likely to encounter version conflicts, missing system libraries, or compiled extensions that were built for a different OS or CPU. When you deploy to a server, the mismatch is almost guaranteed.

A container captures the complete environment — OS libraries, Python runtime, compiled extensions, environment variables, and startup commands — in a single reproducible artifact. Anyone with Docker installed can run your AI application with exactly the same behavior you tested.

#### What Containerization Solves

| Problem | Without containers | With containers |
|---|---|---|
| "Works on my machine" | Frequent — different OS, Python version, system libs | Gone — identical environment everywhere |
| ML package installation | `pip install torch` can take 10+ minutes, has CUDA conflicts | One `docker build`, then instant `docker run` |
| Sharing with teammates | "Here are 15 setup steps…" | `docker compose up` |
| Model dependency isolation | Global Python environment gets polluted | Each app has its own isolated environment |
| Reproducible CI/CD | Build server has different packages | Build from the same Dockerfile used in production |
| Service composition | Manual startup of Ollama, ChromaDB, app in three terminals | `docker compose up` starts everything |

#### The AI-Specific Challenge: Model Files

Model files are the one thing containers handle awkwardly. A `llama3.1:8b` GGUF file is roughly 4.7 GB. A containerized application has three options for accessing model files, each with tradeoffs. Section 3 covers these strategies in detail.

#### Composing AI Services

A production-realistic local AI application is not a single process — it is a system:

```
┌──────────────┐      HTTP       ┌──────────────────┐     HTTP      ┌─────────────┐
│   Browser /  │ ─────────────▶ │  FastAPI RAG API  │ ────────────▶ │   Ollama    │
│  curl client │                │  (your app code)  │               │  (LLM host) │
└──────────────┘                │                   │     gRPC      ┌─────────────┐
                                │                   │ ────────────▶ │   ChromaDB  │
                                └──────────────────┘               │ (vector DB) │
                                                                    └─────────────┘
```

Docker Compose manages this entire system as a unit. Section 5 shows the complete Compose file.

---

### 2. Dockerfile for Python AI Apps

#### Choosing a Base Image

The base image is the foundation of your container. For Python AI apps, you have three realistic options:

| Image | Compressed size | Build speed | When to use |
|---|---|---|---|
| `python:3.11-slim` | ~50 MB | Fast | Most AI apps — adds only what you need |
| `python:3.11` | ~350 MB | Medium | When you need many Debian packages pre-installed |
| `ubuntu:22.04` + python | ~28 MB base | Slowest | When you need full Ubuntu toolchain control |

**`python:3.11-slim` is almost always the right choice.** It is a Debian-based image with only the runtime essentials. You install exactly the system packages your app needs and nothing more.

**Do not use `python:3.11-alpine`** for AI apps. Alpine uses `musl libc` instead of `glibc`. PyTorch, llama-cpp-python, and many other compiled ML packages either do not ship Alpine-compatible wheels or have significant performance degradation without glibc.

#### System Dependencies for ML Packages

`python:3.11-slim` strips out many Debian packages that ML libraries need at runtime. The table below lists the most common gaps:

| Package / dependency | System packages required |
|---|---|
| `llama-cpp-python` | `build-essential`, `cmake`, `libgomp1` (runtime), `python3-dev` |
| `torch` (CPU) | Usually none — ships statically linked |
| `torch` (CUDA) | CUDA driver on host, `libcuda.so` available — handled by NVIDIA Container Toolkit |
| `chromadb` | `build-essential` (for compiled tokenizers) — only at build time |
| `transformers` | None — pure Python wheel |

For most FastAPI + LangChain + Ollama stacks (where Ollama handles the heavy inference), you only need `curl` (for health checks) and no other system packages. `llama-cpp-python` is the exception — it must be compiled from source unless you use a pre-built wheel.

#### Multi-Stage Builds for Lean Final Images

A naive Dockerfile that installs `build-essential` and `cmake` to compile `llama-cpp-python` will ship those compilers — roughly 300 MB of build tools — in the final image. Multi-stage builds fix this by compiling in a build stage and copying only the output to a lean runtime stage.

```
Stage 1: builder
  └─ python:3.11-slim + build-essential + cmake + libgomp-dev
     └─ pip install llama-cpp-python (compiled here)
     └─ pip install all other packages into /install

Stage 2: runtime (final image)
  └─ python:3.11-slim + libgomp1 (runtime only)
     └─ COPY --from=builder /install into site-packages
     └─ COPY app code
     └─ CMD
```

The final image contains no compilers, no header files, no CMake — only the runtime binaries.

#### Production-Ready Dockerfile: FastAPI + LangChain + Ollama

The following Dockerfile is for a FastAPI application that uses LangChain with `ChatOllama` (Ollama runs as a sibling container — the app does not bundle Ollama). It uses a multi-stage build and runs as a non-root user.

```dockerfile
# ── Dockerfile ───────────────────────────────────────────────────────────────────
# Production-ready FastAPI + LangChain app
# Ollama runs as a sibling container — this image handles ONLY the app code.

# ── Stage 1: builder ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time system dependencies.
# build-essential and python3-dev are needed to compile packages with C extensions
# (e.g., chromadb's tokenizer, grpc). They are NOT included in the runtime stage.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first so Docker can cache the pip install layer.
# If requirements.txt has not changed, this layer is reused on every rebuild.
COPY requirements.txt .

# Install all Python packages into a separate directory so we can copy them cleanly.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install only runtime system dependencies.
# curl is needed for the HEALTHCHECK command.
# libgomp1 is needed if any dependency links against OpenMP (e.g., llama-cpp-python).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the installed Python packages from the builder stage.
COPY --from=builder /install /usr/local

# Create a non-root user and group.
# Running as root inside a container is a security risk — if the app is
# compromised, the attacker has root access to everything the container can reach.
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid 1001 --no-create-home appuser

# Copy application code.
COPY --chown=appuser:appgroup ./app /app/app

# Switch to the non-root user for all subsequent commands and at runtime.
USER appuser

# Expose the port the application listens on.
EXPOSE 8000

# Health check: Docker will call this every 30 seconds.
# The app must expose a /health endpoint (shown in the FastAPI code later).
# --start-period=10s gives the app time to initialize before health checks begin.
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use the exec form (JSON array) — required for graceful shutdown signals.
# uvicorn --workers 1: single worker per container; scale with Compose replicas.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

The matching `requirements.txt` for a FastAPI + LangChain + ChromaDB + Ollama stack:

```text
# requirements.txt
fastapi==0.115.12
uvicorn[standard]==0.34.0
langchain==0.3.23
langchain-ollama==0.3.2
langchain-chroma==0.2.4
chromadb==1.0.4
pydantic==2.11.3
httpx==0.28.1
python-multipart==0.0.20
```

#### What Goes in `.dockerignore`

`.dockerignore` prevents files from being sent to the Docker build context, which would slow builds and risk leaking secrets or bloating images with model files.

```
# .dockerignore

# Model files — NEVER bake these into your image accidentally.
# They are gigabytes in size and will make your image unusable.
*.gguf
*.ggml
*.bin
*.safetensors
*.pt
*.pth
models/
model_cache/
.ollama/

# Python runtime artifacts
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.eggs/

# Virtual environments
.venv/
venv/
env/

# Development and secrets
.env
.env.*
.git/
.gitignore
.pytest_cache/
.mypy_cache/
.ruff_cache/
tests/
*.log

# Documentation
README.md
*.md
docs/
```

The model file patterns (`.gguf`, `.bin`, `.safetensors`, etc.) are the most important entries. Without them, a developer who has a model file in the project directory will unknowingly bake several gigabytes into their image.

---

### 3. Handling Model Files in Containers

Model files create a fundamental tension: containers are designed to be self-contained, but model files are too large to treat the way you treat application code. There are three strategies, and the right choice depends on the situation.

#### Strategy 1: Volume Mount (Recommended for Development and Large Models)

Model files live on the host filesystem. The container reads them at runtime via a Docker volume mount. The image itself contains no model data.

```
Host filesystem:               Container filesystem:
/home/user/models/             /models/  (mounted read-only)
  llama3.1-8b-q4.gguf   ────▶   llama3.1-8b-q4.gguf
  mistral-7b-q4.gguf    ────▶   mistral-7b-q4.gguf
```

In `docker-compose.yml`:

```yaml
services:
  app:
    image: my-ai-app:latest
    volumes:
      # Mount the host model directory into the container as read-only.
      # :ro prevents the container from accidentally modifying model files.
      - /home/user/models:/models:ro
    environment:
      - MODEL_PATH=/models/llama3.1-8b-q4.gguf
```

In your FastAPI application:

```python
import os
from llama_cpp import Llama

model_path = os.environ.get("MODEL_PATH", "/models/model.gguf")
llm = Llama(model_path=model_path, n_ctx=4096, n_threads=8)
```

**Advantages:**
- Image is tiny (no model data)
- Swap models without rebuilding the image — just change the environment variable
- Models are shared between containers on the same host

**Disadvantages:**
- Requires manual model download on each new host
- Host path must be configured correctly — easy to forget when deploying

**Best for:** Development, large models (anything over 1 GB), multi-container setups sharing the same models.

#### Strategy 2: Download at Startup (Recommended for CI/CD and Reproducible Deployments)

An entrypoint script checks whether the model exists in a persistent volume. If not, it downloads the model from Hugging Face Hub or pulls it via Ollama before starting the application.

```dockerfile
# entrypoint.sh is copied into the image and executed before the app starts
COPY --chown=appuser:appgroup entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
#!/usr/bin/env bash
# entrypoint.sh
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-/models}"
MODEL_FILE="${MODEL_FILE:-llama-3.1-8b-instruct-q4_k_m.gguf}"
MODEL_REPO="${MODEL_REPO:-bartowski/Meta-Llama-3.1-8B-Instruct-GGUF}"
MODEL_PATH="${MODEL_DIR}/${MODEL_FILE}"

mkdir -p "${MODEL_DIR}"

if [ ! -f "${MODEL_PATH}" ]; then
    echo "[entrypoint] Model not found at ${MODEL_PATH}. Downloading..."
    python3 -c "
from huggingface_hub import hf_hub_download
import os
hf_hub_download(
    repo_id='${MODEL_REPO}',
    filename='${MODEL_FILE}',
    local_dir='${MODEL_DIR}',
    local_dir_use_symlinks=False,
)
print('[entrypoint] Download complete.')
"
else
    echo "[entrypoint] Model found at ${MODEL_PATH}. Skipping download."
fi

# Execute the CMD passed to the container (uvicorn in production, bash in dev)
exec "$@"
```

In `docker-compose.yml`, mount a named volume so the downloaded model persists across container restarts:

```yaml
services:
  app:
    image: my-ai-app:latest
    entrypoint: ["/app/entrypoint.sh"]
    volumes:
      - model_cache:/models
    environment:
      - MODEL_DIR=/models
      - MODEL_FILE=llama-3.1-8b-instruct-q4_k_m.gguf
      - MODEL_REPO=bartowski/Meta-Llama-3.1-8B-Instruct-GGUF

volumes:
  model_cache:
    # This named volume persists on the Docker host.
    # First run downloads the model (~4.7 GB); subsequent runs skip download.
```

**Advantages:**
- Fully reproducible — any machine running `docker compose up` gets the exact model
- Works well in CI/CD pipelines
- Named volume persists the model so download only happens once

**Disadvantages:**
- First startup can be very slow (minutes for large models)
- Requires internet access at startup (unless the volume is pre-populated)
- Makes health check timing tricky — the app is not ready until download completes

**Best for:** CI/CD pipelines, deploying to a new machine, situations where host path configuration is not reliable.

#### Strategy 3: Bake into Image (Only for Very Small Models)

Model files are `COPY`-ed directly into the image layer. The image is self-contained and requires no volume or network access.

```dockerfile
# Only appropriate for tiny models (< 50 MB).
# A 4 GB model file creates a 4 GB image layer that must be
# pushed and pulled in full on every build.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ /app/app/
# This is the bake-in: the model file is part of the image
COPY models/tiny_sentiment_model.bin /app/models/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Advantages:**
- Completely self-contained — `docker run` and it works with no configuration
- No network access needed at runtime

**Disadvantages:**
- Image size equals code size plus model size — impractical for anything over ~50 MB
- Every model update requires a full image rebuild and push
- Docker layer cache is invalidated when the model file changes

**Best for:** Tiny classification models, embedding models under 50 MB, packaging a model for distribution where simplicity outweighs size. This is the wrong approach for anything LLM-sized.

#### Choosing a Strategy

```
Is the model file > 100 MB?
├── YES → Use Volume Mount or Download at Startup
│         ├── Do you need CI/CD reproducibility or deploy to many hosts?
│         │   └── YES → Download at Startup with named volume
│         └── NO → Volume Mount (simpler for local dev)
└── NO → Bake into Image is acceptable if self-containment is worth the tradeoff
```

---

### 4. Containerizing Ollama

#### The Official Ollama Docker Image

Ollama publishes an official image at `ollama/ollama` on Docker Hub, supporting both `linux/amd64` and `linux/arm64`. The `latest` tag ships with CUDA support built in (for GPU inference) but does not require a GPU to run — CPU inference works with the same image.

**Running Ollama in a container (CPU only):**

```bash
docker run -d \
  --name ollama \
  -p 11434:11434 \
  -v ollama_data:/root/.ollama \
  ollama/ollama
```

The volume mount at `/root/.ollama` is where Ollama stores its downloaded model files. Without it, models are lost every time the container is recreated.

**Pulling a model into the named volume:**

```bash
# This exec command runs ollama pull inside the running container.
# The model is written to the ollama_data named volume.
docker exec ollama ollama pull llama3.1
```

After this, any new container using the same `ollama_data` volume already has the model and does not need to re-download it.

**Verifying Ollama is responding:**

```bash
curl http://localhost:11434/api/tags
# Should return a JSON list of available models
```

#### Environment Variables for Ollama Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `0.0.0.0:11434` | Address Ollama listens on. Set to `0.0.0.0:11434` inside Docker so it binds to all interfaces (not just localhost) and is reachable by sibling containers. |
| `OLLAMA_MODELS` | `/root/.ollama/models` | Directory where model files are stored. Change this to point to a custom volume mount path. |
| `OLLAMA_NUM_PARALLEL` | `1` | Number of parallel requests to serve. Increase for multi-user scenarios. |
| `OLLAMA_MAX_LOADED_MODELS` | `1` | Maximum number of models loaded in VRAM simultaneously. |
| `OLLAMA_KEEP_ALIVE` | `5m` | How long to keep a model loaded in memory after the last request. |

**Important networking note:** When Ollama runs in a container and your application also runs in a container (same Compose network), the application must connect to `http://ollama:11434`, not `http://localhost:11434`. `localhost` inside a container refers to that container's loopback — it cannot reach a sibling container. Docker Compose creates a shared network and uses the service name as the hostname.

#### Health Check for the Ollama Service

Ollama exposes `GET /` which returns `Ollama is running` when ready. Use this for the health check:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:11434/"]
  interval: 15s
  timeout: 10s
  start_period: 30s
  retries: 5
```

`start_period: 30s` is important — Ollama takes time to initialize, especially on first run when it may need to perform setup tasks. Without a start period, Docker may declare the container unhealthy before it has had a chance to start.

---

### 5. Docker Compose for Local AI Stacks

Docker Compose defines a multi-container application as a single YAML file. For a local AI stack, this means one `docker compose up` starts Ollama, ChromaDB, and your application — all properly networked, with health checks and persistent volumes.

#### Network Isolation

Compose creates a private network for all services in the file. Services communicate by service name:

- `app` reaches Ollama at `http://ollama:11434`
- `app` reaches ChromaDB at `http://chromadb:8000`
- Ports exposed to the host (`ports:`) are for your browser and `curl` — internal communication never uses host ports

#### Environment Variable Management with `.env`

Store configuration in a `.env` file at the same level as `docker-compose.yml`. Compose automatically reads this file when you run `docker compose up`.

```bash
# .env — commit a .env.example with placeholder values; gitignore the real .env

# Application configuration
APP_PORT=8000
LOG_LEVEL=info

# Ollama configuration
OLLAMA_DEFAULT_MODEL=llama3.1
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# ChromaDB configuration
CHROMA_PORT=8001
CHROMA_COLLECTION=rag_documents
```

Reference variables in `docker-compose.yml` with `${VARIABLE_NAME}` syntax. Docker Compose substitutes them at runtime.

#### Complete docker-compose.yml for the Local AI Stack

```yaml
# docker-compose.yml
# Local AI Stack: Ollama + ChromaDB + FastAPI RAG API
#
# Usage:
#   docker compose up -d          # start all services in background
#   docker compose logs -f app    # tail app logs
#   docker compose down           # stop and remove containers (volumes preserved)
#   docker compose down -v        # stop and ALSO delete all volumes (data loss!)

services:

  # ── Ollama: LLM and embedding inference ─────────────────────────────────────
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    ports:
      # Expose to host so you can run `curl http://localhost:11434/api/tags`
      # for debugging. In production, remove this and access only via internal network.
      - "11434:11434"
    volumes:
      # Named volume: models downloaded here persist across container restarts.
      - ollama_data:/root/.ollama
    environment:
      # Bind to all interfaces — required for sibling containers to connect.
      - OLLAMA_HOST=0.0.0.0:11434
      # Keep models loaded for 10 minutes after last request.
      - OLLAMA_KEEP_ALIVE=10m
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/"]
      interval: 15s
      timeout: 10s
      start_period: 30s
      retries: 5
    networks:
      - ai_network

  # ── Model initializer: pulls required models into the Ollama volume ──────────
  # This is a one-shot service that runs once, pulls models, then exits.
  # It depends on Ollama being healthy before it starts.
  model_init:
    image: ollama/ollama:latest
    depends_on:
      ollama:
        condition: service_healthy
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=ollama:11434
    # Pull the LLM and the embedding model, then exit.
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        echo "Pulling LLM: ${OLLAMA_DEFAULT_MODEL:-llama3.1}"
        ollama pull ${OLLAMA_DEFAULT_MODEL:-llama3.1}
        echo "Pulling embedding model: ${OLLAMA_EMBEDDING_MODEL:-nomic-embed-text}"
        ollama pull ${OLLAMA_EMBEDDING_MODEL:-nomic-embed-text}
        echo "Model initialization complete."
    restart: "no"
    networks:
      - ai_network

  # ── ChromaDB: vector store for document embeddings ───────────────────────────
  chromadb:
    image: chromadb/chroma:latest
    container_name: chromadb
    restart: unless-stopped
    ports:
      # Expose to host for debugging with the Chroma HTTP client.
      - "${CHROMA_PORT:-8001}:8000"
    volumes:
      # Named volume: the Chroma index persists across container restarts.
      # Mounting /data is the correct path for the chromadb/chroma image.
      - chroma_data:/data
    environment:
      - ANONYMIZED_TELEMETRY=False
      - ALLOW_RESET=False
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v2/heartbeat"]
      interval: 15s
      timeout: 10s
      start_period: 15s
      retries: 3
    networks:
      - ai_network

  # ── FastAPI RAG application ──────────────────────────────────────────────────
  app:
    build:
      context: .
      dockerfile: Dockerfile
      # Cache-from reduces rebuild time in CI by pulling a previously built image.
      # Remove this line if you are not using a container registry.
      # cache_from:
      #   - my-registry/ai-rag-app:latest
    container_name: rag_app
    restart: unless-stopped
    ports:
      - "${APP_PORT:-8000}:8000"
    volumes:
      # No application code is mounted in production — the code is baked into the image.
      # For development, use docker-compose.override.yml (see Section 8).
      []
    environment:
      # Connection strings use service names as hostnames (Docker Compose DNS)
      - OLLAMA_BASE_URL=http://ollama:11434
      - CHROMA_HOST=chromadb
      - CHROMA_PORT=8000
      - OLLAMA_DEFAULT_MODEL=${OLLAMA_DEFAULT_MODEL:-llama3.1}
      - OLLAMA_EMBEDDING_MODEL=${OLLAMA_EMBEDDING_MODEL:-nomic-embed-text}
      - CHROMA_COLLECTION=${CHROMA_COLLECTION:-rag_documents}
      - LOG_LEVEL=${LOG_LEVEL:-info}
      # Python output buffering: disable so logs appear immediately in docker logs
      - PYTHONUNBUFFERED=1
    depends_on:
      ollama:
        condition: service_healthy
      chromadb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      start_period: 10s
      retries: 3
    networks:
      - ai_network

# ── Named volumes ──────────────────────────────────────────────────────────────
volumes:
  ollama_data:
    # Driver defaults to "local" — data is stored in Docker's volume directory
    # on the host, typically /var/lib/docker/volumes/ollama_data/
  chroma_data:

# ── Networks ───────────────────────────────────────────────────────────────────
networks:
  ai_network:
    driver: bridge
    # Services on this network can reach each other by service name.
    # They are isolated from other Docker networks on the host.
```

#### Understanding `depends_on` with Health Checks

The `condition: service_healthy` syntax tells Compose to wait for the `healthcheck` of the dependency to pass before starting the dependent service. This is critical for AI stacks because:

- Ollama takes time to start and initialize its HTTP server
- ChromaDB needs to initialize its SQLite backend before it can accept connections
- Your app will crash immediately if it tries to connect to Ollama or ChromaDB before they are ready

Without `condition: service_healthy`, `depends_on` only waits for the container to start — not for the service inside it to be responsive. Always use `condition: service_healthy` and always define a `healthcheck` for services that have dependents.

---

### 6. GPU Passthrough in Docker

GPU passthrough allows a container to use the host's NVIDIA GPU for accelerated inference. This can reduce LLM inference time from minutes to seconds for larger models.

**The default for local development is CPU-only.** GPU passthrough requires an NVIDIA GPU, the NVIDIA driver installed on the host, and the NVIDIA Container Toolkit. If you do not have an NVIDIA GPU, skip this section — all examples in this module work correctly in CPU mode.

#### NVIDIA Container Toolkit Installation (Ubuntu/Debian)

The NVIDIA Container Toolkit installs a container runtime that injects GPU device access into containers. It is a one-time setup on the host machine.

```bash
# 1. Add the NVIDIA Container Toolkit repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 2. Install the toolkit
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 3. Configure Docker to use the NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 4. Verify the installation
docker run --rm --gpus all nvidia/cuda:12.3.1-base-ubuntu22.04 nvidia-smi
# Should print the GPU information table
```

#### Passing the GPU to a Container

**Command line (ad hoc):**

```bash
docker run -d \
  --name ollama_gpu \
  --gpus all \
  -p 11434:11434 \
  -v ollama_data:/root/.ollama \
  ollama/ollama
```

**Docker Compose (`docker-compose.yml`):**

The `deploy.resources.reservations.devices` block is the Compose equivalent of `--gpus all`. This syntax is supported in Compose Specification (the current standard, used by Docker Compose v2).

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all          # "all" gives the container all available GPUs
              capabilities: [gpu] # "gpu" is required — without this the device spec is ignored
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
    ports:
      - "11434:11434"
```

To use a specific GPU by ID (from `nvidia-smi`):

```yaml
devices:
  - driver: nvidia
    device_ids: ["0"]   # Use GPU 0 only
    capabilities: [gpu]
```

**Verifying GPU access inside the container:**

```bash
docker exec ollama nvidia-smi
# If GPU passthrough is working, this prints the GPU table.
# If it prints "nvidia-smi: command not found", the toolkit is not configured correctly.
```

```bash
# Or verify via the Ollama API — it reports GPU utilization in its response headers
curl http://localhost:11434/api/generate \
  -d '{"model": "llama3.1", "prompt": "Hello", "stream": false}' \
  | python3 -m json.tool | grep -i "eval_duration"
```

#### AMD ROCm (Brief)

AMD GPU support in Docker uses the `ollama/ollama:rocm` image tag and requires different device pass-through flags:

```bash
docker run -d \
  --device /dev/kfd \
  --device /dev/dri \
  -v ollama_data:/root/.ollama \
  -p 11434:11434 \
  ollama/ollama:rocm
```

ROCm support in Docker Compose requires the `devices:` list syntax (not `deploy.resources.reservations`). Consult the Ollama documentation for current ROCm Compose configuration — it evolves with each ROCm release.

---

### 7. Building a Containerized RAG API

This section builds the complete system introduced conceptually in Section 5: a FastAPI application with `/ingest` and `/query` endpoints, backed by Ollama for inference and ChromaDB for vector storage, running entirely in Docker containers.

#### Project Structure

```
rag-api/
├── Dockerfile
├── docker-compose.yml
├── docker-compose.override.yml   # development overrides (Section 8)
├── .dockerignore
├── .env
├── .env.example
├── requirements.txt
└── app/
    ├── __init__.py
    └── main.py
```

#### FastAPI Application (`app/main.py`)

```python
"""
app/main.py

Containerized RAG API backed by:
  - Ollama (LLM and embeddings) — sibling container at http://ollama:11434
  - ChromaDB (vector store)     — sibling container at http://chromadb:8000

Endpoints:
  POST /ingest  — Add documents to the vector store
  POST /query   — Ask a question; retrieves relevant docs and calls the LLM
  GET  /health  — Health check for Docker and load balancers

Requirements (from requirements.txt):
  fastapi, uvicorn[standard], langchain, langchain-ollama,
  langchain-chroma, chromadb, pydantic, httpx
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import chromadb
from chromadb.config import Settings
from fastapi import FastAPI, HTTPException
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_ollama import ChatOllama, OllamaEmbeddings
from pydantic import BaseModel

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "info").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("rag_api")

# ── Configuration from environment variables ───────────────────────────────────

OLLAMA_BASE_URL       = os.environ.get("OLLAMA_BASE_URL",       "http://ollama:11434")
OLLAMA_DEFAULT_MODEL  = os.environ.get("OLLAMA_DEFAULT_MODEL",  "llama3.1")
OLLAMA_EMBEDDING_MODEL = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
CHROMA_HOST           = os.environ.get("CHROMA_HOST",           "chromadb")
CHROMA_PORT           = int(os.environ.get("CHROMA_PORT",       "8000"))
CHROMA_COLLECTION     = os.environ.get("CHROMA_COLLECTION",     "rag_documents")

# ── Global state ───────────────────────────────────────────────────────────────

# These are initialized in the lifespan context manager (FastAPI startup).
vectorstore: Chroma | None = None
rag_chain: Any | None = None


# ── Lifespan: initialize connections at startup ────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the LangChain components when the application starts."""
    global vectorstore, rag_chain

    logger.info("Initializing RAG pipeline...")
    logger.info("  Ollama:   %s (model: %s)", OLLAMA_BASE_URL, OLLAMA_DEFAULT_MODEL)
    logger.info("  ChromaDB: %s:%s (collection: %s)", CHROMA_HOST, CHROMA_PORT, CHROMA_COLLECTION)

    # Embedding model — used for ingestion and retrieval
    embeddings = OllamaEmbeddings(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_EMBEDDING_MODEL,
    )

    # ChromaDB HTTP client — connects to the sibling chromadb container
    chroma_client = chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        settings=Settings(anonymized_telemetry=False),
    )

    # LangChain Chroma vector store wrapper
    vectorstore = Chroma(
        client=chroma_client,
        collection_name=CHROMA_COLLECTION,
        embedding_function=embeddings,
    )

    # LLM — connects to the sibling Ollama container
    llm = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_DEFAULT_MODEL,
        temperature=0.1,
    )

    # RAG prompt template
    rag_prompt = ChatPromptTemplate.from_template("""
You are a helpful assistant. Answer the question using ONLY the context provided below.
If the context does not contain enough information to answer, say so clearly.

Context:
{context}

Question: {question}

Answer:""".strip())

    def format_docs(docs: list[Document]) -> str:
        return "\n\n---\n\n".join(doc.page_content for doc in docs)

    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4},
    )

    # Build the RAG chain using LangChain Expression Language (LCEL)
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | rag_prompt
        | llm
        | StrOutputParser()
    )

    logger.info("RAG pipeline initialized successfully.")
    yield  # Application runs here

    logger.info("Shutting down RAG pipeline.")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Local RAG API",
    description="A containerized RAG API backed by Ollama and ChromaDB.",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request / response models ──────────────────────────────────────────────────

class IngestRequest(BaseModel):
    documents: list[str]
    chunk_size: int = 500
    chunk_overlap: int = 50

    model_config = {"json_schema_extra": {"examples": [
        {"documents": ["LangChain is a framework for building LLM applications."]}
    ]}}


class IngestResponse(BaseModel):
    chunks_added: int
    message: str


class QueryRequest(BaseModel):
    question: str

    model_config = {"json_schema_extra": {"examples": [
        {"question": "What is LangChain?"}
    ]}}


class QueryResponse(BaseModel):
    answer: str
    question: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Ops"])
async def health() -> dict[str, str]:
    """
    Health check endpoint.
    Docker, load balancers, and the Compose healthcheck all poll this endpoint.
    Returns 200 OK if the application has initialized successfully.
    """
    return {"status": "healthy"}


@app.post("/ingest", response_model=IngestResponse, tags=["RAG"])
async def ingest(request: IngestRequest) -> IngestResponse:
    """
    Ingest documents into the vector store.

    The documents are split into chunks, embedded using the Ollama embedding
    model, and stored in ChromaDB. Subsequent /query calls will retrieve
    these chunks when relevant.
    """
    if vectorstore is None:
        raise HTTPException(status_code=503, detail="Vector store not initialized.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
    )
    docs = [Document(page_content=text) for text in request.documents]
    chunks = splitter.split_documents(docs)

    if not chunks:
        raise HTTPException(status_code=400, detail="No content after splitting.")

    try:
        vectorstore.add_documents(chunks)
    except Exception as exc:
        logger.error("Failed to add documents to vector store: %s", exc)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

    logger.info("Ingested %d document(s) → %d chunk(s).", len(request.documents), len(chunks))
    return IngestResponse(
        chunks_added=len(chunks),
        message=f"Successfully ingested {len(chunks)} chunk(s) into collection '{CHROMA_COLLECTION}'.",
    )


@app.post("/query", response_model=QueryResponse, tags=["RAG"])
async def query(request: QueryRequest) -> QueryResponse:
    """
    Query the RAG pipeline.

    Retrieves the most relevant document chunks from ChromaDB and passes
    them with the question to the Ollama LLM to generate a grounded answer.
    """
    if rag_chain is None:
        raise HTTPException(status_code=503, detail="RAG chain not initialized.")

    try:
        answer = rag_chain.invoke(request.question)
    except Exception as exc:
        logger.error("RAG chain invocation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc

    logger.info("Query: '%s' → %d character answer.", request.question, len(answer))
    return QueryResponse(answer=answer, question=request.question)
```

#### The Dockerfile (Production)

Use the Dockerfile from Section 2 without modification. The only requirement is that the application code is in the `app/` directory and that `requirements.txt` lists all dependencies.

For the RAG API stack, `requirements.txt` should be:

```text
# requirements.txt — RAG API stack
fastapi==0.115.12
uvicorn[standard]==0.34.0
langchain==0.3.23
langchain-ollama==0.3.2
langchain-chroma==0.2.4
chromadb==1.0.4
pydantic==2.11.3
httpx==0.28.1
python-multipart==0.0.20
```

#### Running the Complete Stack

```bash
# 1. Create the .env file
cat > .env << 'EOF'
APP_PORT=8000
CHROMA_PORT=8001
OLLAMA_DEFAULT_MODEL=llama3.1
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
CHROMA_COLLECTION=rag_documents
LOG_LEVEL=info
EOF

# 2. Build the application image
docker compose build

# 3. Start the full stack (Ollama, model_init, ChromaDB, app)
# The first run pulls llama3.1 (~4.7 GB) and nomic-embed-text (~274 MB).
# This can take several minutes on first launch.
docker compose up -d

# 4. Wait for all services to be healthy
docker compose ps
# All services should show "healthy" in the STATUS column.

# 5. Verify the app is running
curl http://localhost:8000/health
# {"status":"healthy"}

# 6. Ingest a document
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      "Docker is a platform for building, shipping, and running applications in containers. Containers package code and its dependencies together so applications run reliably across environments.",
      "A Dockerfile is a text file containing instructions for building a Docker image. Each instruction creates a layer in the image. Layers are cached, so unchanged layers do not need to be rebuilt."
    ]
  }'
# {"chunks_added": 2, "message": "Successfully ingested 2 chunk(s) into collection 'rag_documents'."}

# 7. Query the RAG pipeline
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is a Dockerfile?"}'
# {"answer": "A Dockerfile is a text file containing instructions...", "question": "What is a Dockerfile?"}
```

#### Volume Persistence for ChromaDB

The `chroma_data` named volume persists the Chroma index across container restarts. To verify:

```bash
# Ingest some documents, then restart the stack
docker compose restart chromadb

# Wait for chromadb to become healthy again
docker compose ps

# Query again — documents should still be retrievable
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is a Dockerfile?"}'
# The answer uses the previously ingested documents — they persisted through the restart.
```

---

### 8. Development Workflow with Containers

Running the full stack in Docker during development creates one problem: every code change requires rebuilding the image and restarting the container. For a Python app with heavy dependencies, this rebuild can take 2–5 minutes, destroying developer velocity.

The solution is a combination of bind mounts and Compose override files.

#### Bind Mounts for Live Code Reloading

A bind mount replaces the app code inside the container with a live link to your local source directory. When you save a file on your host, the change is immediately visible inside the container. Combined with `uvicorn --reload`, this enables sub-second code reload.

```
Host filesystem:               Container filesystem:
./app/main.py     ────bind────▶  /app/app/main.py   (live link)
./app/main.py     ────────────▶  Uvicorn detects change → restarts
```

#### Compose Override Files

Docker Compose automatically merges `docker-compose.yml` (base, production-ready) with `docker-compose.override.yml` (development overrides) when you run `docker compose up`. This pattern keeps the production configuration clean while providing a development-specific overlay.

```yaml
# docker-compose.override.yml
# This file is AUTOMATICALLY merged with docker-compose.yml by Docker Compose.
# It is intentionally NOT committed if it contains developer-specific paths.
# Add docker-compose.override.yml to .gitignore; commit docker-compose.override.yml.example instead.

services:
  app:
    build:
      # Re-use the same Dockerfile — override only the CMD for development.
      context: .
      dockerfile: Dockerfile
    # Bind mount: your local ./app directory replaces the baked-in code.
    # Changes on the host are immediately visible inside the container.
    volumes:
      - ./app:/app/app:cached
    # Override CMD: use uvicorn --reload so the server restarts on file changes.
    # --reload-dir limits the watcher to only the app directory (faster, avoids
    # reloading on volume changes in /models or /data).
    command:
      - "uvicorn"
      - "app.main:app"
      - "--host"
      - "0.0.0.0"
      - "--port"
      - "8000"
      - "--reload"
      - "--reload-dir"
      - "/app/app"
    environment:
      # Override log level for development — DEBUG shows all LangChain internals.
      - LOG_LEVEL=debug
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
```

#### Development Workflow Commands

```bash
# Start the full stack with the override file applied automatically:
docker compose up -d

# Tail the app logs to see reload events:
docker compose logs -f app
# You will see:
#   INFO:     Started reloader process [1] using WatchFiles
#   INFO:     Started server process [8]
# When you save a file:
#   WARNING:  WatchFiles detected changes in 'app/main.py'. Reloading...
#   INFO:     Stopping server process [8]
#   INFO:     Started server process [9]

# Edit a source file on your host — the container reloads automatically:
echo "# change" >> app/main.py
# Uvicorn detects the change within ~1 second and restarts the worker

# Open an interactive shell inside the running app container:
docker exec -it rag_app bash
# Explore: ls /app, python3, pip list, etc.

# Run a one-off Python script against the running stack:
docker exec rag_app python3 -c "import chromadb; print('chromadb version:', chromadb.__version__)"

# View logs from a specific service:
docker compose logs --tail=50 ollama

# Restart a single service without restarting the full stack:
docker compose restart app

# Rebuild the image after changing requirements.txt:
docker compose build app
docker compose up -d app   # replace the running container with the new image

# Run the stack in production mode (no override file):
docker compose -f docker-compose.yml up -d
```

#### Rebuilding When Dependencies Change

The bind mount approach only reloads code — it does not update installed packages. When you add or update a package in `requirements.txt`, you must rebuild:

```bash
# After editing requirements.txt:
docker compose build app
# Docker rebuilds only the layers that changed.
# If only requirements.txt changed, the code-copy layer is rebuilt from there.
# If only app code changed (and you are not using bind mounts), only the code layer rebuilds.

# Replace the running container with the newly built image:
docker compose up -d --no-deps app
# --no-deps: do not restart Ollama or ChromaDB — only the app container changes.
```

#### Debugging Inside Containers

```bash
# Stream all logs from all services:
docker compose logs -f

# Inspect environment variables inside the app container:
docker exec rag_app env | sort

# Check which Python packages are installed:
docker exec rag_app pip list

# Run a Python REPL inside the container (useful for testing imports):
docker exec -it rag_app python3

# Check Ollama connectivity from inside the app container:
docker exec rag_app curl -s http://ollama:11434/api/tags | python3 -m json.tool

# Check ChromaDB connectivity from inside the app container:
docker exec rag_app curl -s http://chromadb:8000/api/v2/heartbeat

# Inspect the ChromaDB volume contents on the host:
docker volume inspect chroma_data
# Shows the Mountpoint — you can browse it with sudo on the host.

# Check container resource usage:
docker stats --no-stream
```

---

## Common Pitfalls

**Pitfall 1: Model files accidentally baked into the image**

If you forget `.dockerignore` entries for model files and your project directory contains `.gguf` or `.bin` files, `COPY . .` will include them in the image. A 4.7 GB model file becomes a 4.7 GB image layer. The build appears to succeed but `docker push` and `docker pull` take an hour.

Prevention: Add `.dockerignore` with all model file patterns before writing your first `COPY` instruction. Keep the `.dockerignore` in version control.

Detection: Check image size after building: `docker images my-ai-app`. If the size is unexpectedly large, run `docker history my-ai-app` to see which layer is responsible.

**Pitfall 2: Ollama not ready when the app container starts — health check timing**

The `depends_on: condition: service_healthy` syntax prevents the `app` container from starting until Ollama's health check passes. But the health check must be defined on the Ollama service with appropriate timing parameters.

A common mistake is setting `start_period` too short. Ollama can take 15–30 seconds to initialize on first run. If `start_period` is only 5 seconds, Docker declares it unhealthy before it has had a chance to start, and the dependent app never starts.

```yaml
# WRONG — start_period too short for Ollama initialization
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:11434/"]
  start_period: 5s

# CORRECT — give Ollama enough time to initialize
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:11434/"]
  start_period: 30s
  interval: 15s
  timeout: 10s
  retries: 5
```

**Pitfall 3: Container can't reach Ollama on localhost**

This is the most common networking mistake when containerizing AI apps. Inside a container, `localhost` refers to the container's own loopback interface — it does not reach sibling containers.

```python
# WRONG — works on the host but fails inside a container
llm = ChatOllama(base_url="http://localhost:11434", model="llama3.1")

# CORRECT — uses the Docker Compose service name as the hostname
llm = ChatOllama(base_url="http://ollama:11434", model="llama3.1")
```

Configure this via an environment variable so the same code works in both local development (without Docker) and in containers:

```python
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
llm = ChatOllama(base_url=OLLAMA_BASE_URL, model="llama3.1")
```

When running locally (without Docker), `OLLAMA_BASE_URL` defaults to `localhost`. When running in Docker Compose, set `OLLAMA_BASE_URL=http://ollama:11434` in the `environment:` block.

**Pitfall 4: llama-cpp-python build failures in containers**

`llama-cpp-python` must be compiled from source in the Docker build stage. Common failure modes:

- `cmake: command not found` — missing `cmake` in the builder stage. Add `cmake` to the `apt-get install` command.
- `cannot find -lgomp` — missing OpenMP. Install `libgomp-dev` in the builder stage and `libgomp1` in the runtime stage.
- `Python.h: No such file or directory` — missing Python development headers. Install `python3-dev` in the builder stage.
- Build times out — `llama-cpp-python` compilation takes 3–8 minutes even in a container. Set a `--timeout` on your `docker build` command if your CI system kills slow builds.

```dockerfile
# Builder stage system packages for llama-cpp-python:
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libgomp-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*
```

If you are not using `llama-cpp-python` directly (relying on Ollama for inference instead), none of these compilation issues apply. The Ollama container handles compilation internally.

**Pitfall 5: ChromaDB volume permissions**

ChromaDB writes its SQLite database to `/data` inside the container. If the container runs as a non-root user (as recommended in Section 2) and the `/data` directory is owned by root (which is the default for named volumes), ChromaDB fails with a permission error.

The `chromadb/chroma` official image handles this internally and runs as a non-root user that owns `/data`. The issue arises when you use a custom ChromaDB setup or mount a bind mount (not a named volume) with host directory permissions that do not match the container user.

Fix: Use named volumes (not bind mounts) for ChromaDB data in production. Docker named volumes are managed by Docker and avoid host permission issues.

If you must use a bind mount for ChromaDB data (for example, to inspect the SQLite file directly):

```bash
# Create the directory and set permissions before starting the stack
mkdir -p ./chroma_data
chmod 777 ./chroma_data   # permissive — adjust to match the container user UID
```

**Pitfall 6: model_init service restarts in a loop**

The `model_init` service in the Compose file is designed to run once and exit. If it is marked as `restart: always` (or if the default restart policy applies), Compose will restart it indefinitely after it exits successfully, causing it to repeatedly try to pull models that are already downloaded.

Always set `restart: "no"` on one-shot initialization services:

```yaml
model_init:
  restart: "no"   # do not restart after successful exit
```

---

## Best Practices

**Pin image versions in production.** Using `:latest` means your production deploy can pull a different image version than the one you tested. Pin specific versions:

```yaml
# Development (acceptable):
image: ollama/ollama:latest

# Production (required):
image: ollama/ollama:0.7.1
image: chromadb/chroma:1.0.4
```

**Never put secrets in the Dockerfile or docker-compose.yml.** API keys, tokens, and passwords should come from a `.env` file that is listed in `.gitignore`. Commit a `.env.example` with placeholder values to document what variables are required.

**Use one process per container.** Run one uvicorn process per app container, one Ollama process per Ollama container. Let Compose or an orchestrator handle scaling. This makes health checks accurate — if the process dies, the container dies, and Compose knows to restart it.

**Set `PYTHONUNBUFFERED=1` in every Python container.** Without this, Python buffers stdout and stderr, which means `docker compose logs` shows nothing until the buffer flushes. Errors during startup may be invisible.

**Use `--no-cache-dir` with pip.** The pip download cache is useless inside a container build — it wastes layer space. Always use `pip install --no-cache-dir`.

**Clean apt lists in the same RUN layer as apt-get install.** Each Docker instruction creates a new layer. If you install packages in one `RUN` and delete `/var/lib/apt/lists/` in a later `RUN`, the list files are still in the earlier layer and contribute to image size. Chain them in a single `RUN`:

```dockerfile
# CORRECT — apt lists are deleted in the same layer they were created
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*
```

**Prefer named volumes over bind mounts for persistent data in production.** Named volumes are managed by Docker, survive container recreation, and avoid host permission issues. Use bind mounts only for development (source code) and for host-managed model files.

**Always define a health check for services that have dependents.** `depends_on: condition: service_healthy` only works if the dependency has a `healthcheck` defined. Without it, Compose falls back to `condition: service_started` (container running but not necessarily responsive).

---

## Hands-On Examples

### Example 1: Containerize a Simple Ollama-Backed Chatbot

This example containerizes a minimal FastAPI chatbot. The LLM runs in an Ollama sibling container. The application code is kept intentionally simple so the focus is on the container setup.

**File: `chatbot/app/main.py`**

```python
"""
chatbot/app/main.py

A minimal FastAPI chatbot backed by Ollama in a sibling container.
"""

import os
from fastapi import FastAPI, HTTPException
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL",    "llama3.1")

llm = ChatOllama(base_url=OLLAMA_BASE_URL, model=OLLAMA_MODEL, temperature=0.7)

app = FastAPI(title="Local Chatbot", version="1.0.0")


class ChatRequest(BaseModel):
    message: str
    system_prompt: str = "You are a helpful assistant."


class ChatResponse(BaseModel):
    response: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        messages = [
            SystemMessage(content=request.system_prompt),
            HumanMessage(content=request.message),
        ]
        response = llm.invoke(messages)
        return ChatResponse(response=response.content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

**File: `chatbot/requirements.txt`**

```text
fastapi==0.115.12
uvicorn[standard]==0.34.0
langchain-ollama==0.3.2
langchain-core==0.3.51
pydantic==2.11.3
```

**File: `chatbot/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid 1001 --no-create-home appuser

COPY --chown=appuser:appgroup ./app /app/app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**File: `chatbot/docker-compose.yml`**

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: chatbot_ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
      - OLLAMA_KEEP_ALIVE=10m
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/"]
      interval: 15s
      timeout: 10s
      start_period: 30s
      retries: 5
    networks:
      - chatbot_net

  model_init:
    image: ollama/ollama:latest
    depends_on:
      ollama:
        condition: service_healthy
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=ollama:11434
    entrypoint: ["/bin/sh", "-c", "ollama pull llama3.1 && echo 'Model ready.'"]
    restart: "no"
    networks:
      - chatbot_net

  chatbot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: chatbot_app
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - OLLAMA_MODEL=llama3.1
      - PYTHONUNBUFFERED=1
    depends_on:
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      start_period: 10s
      retries: 3
    networks:
      - chatbot_net

volumes:
  ollama_data:

networks:
  chatbot_net:
    driver: bridge
```

**Running and testing:**

```bash
cd chatbot/
docker compose up -d

# Wait for all services to be healthy (Ollama model pull takes a few minutes on first run)
docker compose ps

# Test the health endpoint
curl http://localhost:8000/health

# Send a chat message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain Docker volumes in one sentence.",
    "system_prompt": "You are a concise technical assistant."
  }'

# Expected response (content will vary):
# {"response": "Docker volumes are persistent storage mechanisms that allow data to survive beyond the lifecycle of a container."}

# Shut down
docker compose down
```

---

### Example 2: Full Local AI Stack with RAG

This example runs the complete docker-compose.yml from Section 5 with the FastAPI RAG application from Section 7. It adds a second test that verifies volume persistence.

**Setup:**

Create the project directory structure:

```bash
mkdir -p rag-stack/app
cd rag-stack/
```

Copy the following files into the directory:
- `app/main.py` — the full RAG application from Section 7
- `requirements.txt` — the RAG API requirements from Section 7
- `Dockerfile` — the production Dockerfile from Section 2
- `docker-compose.yml` — the complete Compose file from Section 5
- `.dockerignore` — from Section 2

Create the `.env` file:

```bash
cat > .env << 'EOF'
APP_PORT=8000
CHROMA_PORT=8001
OLLAMA_DEFAULT_MODEL=llama3.1
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
CHROMA_COLLECTION=rag_documents
LOG_LEVEL=info
EOF
```

**Build and start:**

```bash
docker compose build
docker compose up -d

# Monitor startup — this can take 5-10 minutes on first run
# due to model downloads
docker compose logs -f model_init
# When you see "Model initialization complete." the models are ready.

docker compose ps
# All services should show "healthy"
```

**Ingest and query:**

```bash
# Ingest documents about Docker
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      "Docker Compose is a tool for defining and running multi-container applications. With Compose, you use a YAML file to configure your application services, then create and start all services with a single command.",
      "Named volumes in Docker are the preferred mechanism for persisting data generated and used by Docker containers. Unlike bind mounts which depend on the directory structure of the host machine, volumes are completely managed by Docker.",
      "The HEALTHCHECK instruction in a Dockerfile tells Docker how to test that a container is still working. When a health check fails, the container is marked as unhealthy and Docker can stop routing traffic to it."
    ],
    "chunk_size": 400,
    "chunk_overlap": 40
  }'

# Query the ingested documents
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I persist data across container restarts?"}'

# Test volume persistence
docker compose restart chromadb
sleep 15  # wait for chromadb to become healthy again
docker compose ps

curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is a named volume?"}'
# The answer should use the previously ingested content — persistence confirmed.
```

**Inspect volumes:**

```bash
# List all volumes used by this stack
docker volume ls | grep rag-stack

# Inspect the ChromaDB volume location on the host
docker volume inspect rag-stack_chroma_data
# The Mountpoint field shows where Docker stores the volume data

# Inspect the Ollama model volume
docker volume inspect rag-stack_ollama_data
```

---

### Example 3: Development Workflow with Live Reload

This example demonstrates the full development workflow: starting the stack with the override file for live reload, making a code change, and seeing the server restart automatically.

**Setup:**

Use the same `rag-stack/` directory from Example 2. Create the override file:

```bash
cat > docker-compose.override.yml << 'EOF'
services:
  app:
    volumes:
      - ./app:/app/app:cached
    command:
      - "uvicorn"
      - "app.main:app"
      - "--host"
      - "0.0.0.0"
      - "--port"
      - "8000"
      - "--reload"
      - "--reload-dir"
      - "/app/app"
    environment:
      - LOG_LEVEL=debug
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
EOF
```

**The development cycle:**

```bash
# Start the stack with the override file (applied automatically)
docker compose up -d

# Confirm uvicorn is running in reload mode
docker compose logs app | grep "reloader"
# Should show: Started reloader process [1] using WatchFiles

# Make a code change on your host (add a new endpoint)
cat >> app/main.py << 'EOF'


@app.get("/ping")
async def ping() -> dict[str, str]:
    return {"pong": "true"}
EOF

# Watch the app logs — within ~1 second you should see:
docker compose logs -f app
# WARNING:  WatchFiles detected changes in 'app/main.py'. Reloading...
# INFO:     Stopping server process [8]
# INFO:     Started server process [9]
# INFO:     Application startup complete.

# Test the new endpoint immediately — no rebuild needed
curl http://localhost:8000/ping
# {"pong":"true"}

# Simulate adding a new package
echo "httpx[cli]==0.28.1" >> requirements.txt
# Bind mounts do NOT update installed packages — rebuild is needed

docker compose build app            # rebuild the image with the new package
docker compose up -d --no-deps app  # replace only the app container
# Ollama and ChromaDB keep running — only the app container is replaced

# Switch to production mode (no bind mounts, no --reload)
# Run the stack using only docker-compose.yml (skip the override file)
docker compose -f docker-compose.yml up -d

# Verify the production container uses the baked-in code (no bind mount)
docker inspect rag_app | python3 -m json.tool | grep -A 5 '"Mounts"'
# In production mode, Mounts should be empty (no bind mounts)

# Clean up
docker compose down
```

---

## Key Terminology

**Base image** — The starting point for a Dockerfile, specified with the `FROM` instruction. For Python AI apps, `python:3.11-slim` is the standard choice. The base image determines the OS, system libraries, and Python version available in the container.

**Bind mount** — A volume mount that links a host filesystem path directly into a container. Changes on the host are immediately reflected inside the container. Used during development for live code reload; not recommended for persistent data in production.

**Build stage** — A section of a multi-stage Dockerfile, beginning with a `FROM` instruction and labeled with `AS name`. Each stage is an isolated build environment. Files are transferred between stages using `COPY --from=stage_name`.

**ChromaDB** — An open-source vector database used in this module as the persistent store for document embeddings. Runs as a Docker container, persisting data to a named volume at `/data`.

**Container runtime** — The component that executes containers on the host. Docker Engine's default runtime is `runc`. The NVIDIA Container Toolkit adds an `nvidia` runtime that injects GPU device access into containers.

**`depends_on`** — A Compose directive that defines startup dependencies between services. `condition: service_healthy` causes Compose to wait for the dependency's health check to pass before starting the dependent service.

**`.dockerignore`** — A text file listing patterns of files to exclude from the Docker build context. Critical for AI projects to prevent accidental inclusion of multi-gigabyte model files in images.

**Health check** — A command Docker runs periodically inside a running container to determine if the service is functioning. Defined with the `HEALTHCHECK` Dockerfile instruction or the `healthcheck:` Compose block. Services can be `starting`, `healthy`, or `unhealthy`.

**Multi-stage build** — A Dockerfile technique that uses multiple `FROM` instructions, each beginning a new build stage. Allows compilation in a full-toolchain stage and produces a lean final image by copying only the runtime artifacts.

**Named volume** — A Docker-managed persistent storage volume identified by a name (e.g., `ollama_data`). Data persists across container restarts and removals. Preferred over bind mounts for production data (ChromaDB index, Ollama models).

**NVIDIA Container Toolkit** — A set of utilities that configures the Docker runtime to pass NVIDIA GPU devices into containers. Required for GPU-accelerated inference in Docker. Installed once on the host; any subsequent container can use `--gpus all` or the Compose `deploy.resources` block.

**`OLLAMA_HOST`** — An environment variable that controls the address Ollama binds its HTTP server to. Must be set to `0.0.0.0:11434` inside Docker so sibling containers on the Compose network can connect to it.

**Compose override file** — A secondary `docker-compose.override.yml` that Docker Compose automatically merges with `docker-compose.yml`. Used to apply development-specific configuration (bind mounts, `--reload`) without modifying the production Compose file.

**`python:3.11-slim`** — The recommended Python base image for AI apps. A Debian-based image with the Python runtime and minimal system libraries. Smaller than the full `python:3.11` image; compatible with glibc-linked ML packages unlike Alpine variants.

---

## Summary

- Python AI applications have uniquely severe dependency problems — OS libraries, compiled C extensions, CUDA versions, and rapidly evolving ML packages — that containers solve by packaging the complete environment into a reproducible artifact.
- Use `python:3.11-slim` as the base image. Avoid Alpine for AI apps (musl libc incompatibility). Use multi-stage builds to keep compilers out of the final image.
- Model files must be handled separately from application code. The three strategies are volume mount (recommended for development and large models), download at startup via entrypoint script (recommended for CI/CD), and bake into image (only for models under ~50 MB). Always add model file patterns to `.dockerignore`.
- The official `ollama/ollama` Docker image runs CPU and GPU inference. Mount a named volume at `/root/.ollama` so model files persist across container restarts. Pre-pull models using `docker exec ollama ollama pull <model>` or a one-shot `model_init` service in Compose.
- Inside a Docker Compose network, containers reach each other by service name. `http://localhost:11434` fails inside a container — use `http://ollama:11434`. Always configure the Ollama URL via an environment variable so the same code works in both development (host Ollama) and Docker (container Ollama).
- Define health checks on every service that has dependents. Use `depends_on: condition: service_healthy` — not the default `service_started` — to ensure containers wait for services to be actually responsive before connecting.
- GPU passthrough requires the NVIDIA Container Toolkit on the host. Use `deploy.resources.reservations.devices` in Compose to pass GPUs to the Ollama container. CPU-only is the correct default for local development.
- The development workflow uses `docker-compose.override.yml` with a bind mount and `uvicorn --reload`. Production uses the base `docker-compose.yml` with code baked into the image. Run production-only with `docker compose -f docker-compose.yml up -d`.

---

## Further Reading

- [Docker Official Documentation — Dockerfile Best Practices](https://docs.docker.com/build/building/best-practices/) — The canonical reference for Dockerfile authoring, covering layer caching, multi-stage builds, `.dockerignore`, and build context optimization. Required reading before writing any production Dockerfile.

- [FastAPI Deployment with Docker — FastAPI Official Docs](https://fastapi.tiangolo.com/deployment/docker/) — The official FastAPI guide to containerization, covering base image selection, `CMD` exec form requirements for graceful shutdown, Docker Compose setup, and multi-worker configuration. Directly complements the Dockerfile patterns in Section 2.

- [Ollama Docker Documentation — docs.ollama.com/docker](https://docs.ollama.com/docker) — The official Ollama documentation for Docker deployment, covering CPU, NVIDIA GPU, and AMD ROCm configurations, volume mounts for model persistence, and environment variable reference. Use this when upgrading Ollama versions or configuring GPU support.

- [ChromaDB Docker Deployment Guide — docs.trychroma.com](https://docs.trychroma.com/guides/deploy/docker) — The official ChromaDB documentation for running the vector store in Docker, including volume mount paths, environment variables, client connection configuration, and observability with OpenTelemetry. Reference this when upgrading ChromaDB versions.

- [NVIDIA Container Toolkit Installation Guide — docs.nvidia.com](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) — The official NVIDIA guide for installing the Container Toolkit on Ubuntu, Debian, RHEL, and other distributions. Covers repository setup, package installation, Docker runtime configuration, and verification steps.

- [Enable GPU Support in Docker Compose — Docker Docs](https://docs.docker.com/compose/how-tos/gpu-support/) — The Docker reference for the `deploy.resources.reservations.devices` syntax used to pass GPUs to containers in Compose. Covers NVIDIA and generic GPU device specification, `count` vs `device_ids`, and the required `capabilities` field.

- [Docker Best Practices for Python Developers — TestDriven.io](https://testdriven.io/blog/docker-best-practices/) — A practitioner guide covering non-root users, layer caching, multi-stage builds, `.dockerignore`, and health checks for Python applications. Particularly useful for understanding the security and performance rationale behind each Dockerfile directive.

- [Docker Compose Override Files — Docker Docs](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/) — The official reference for how Docker Compose merges multiple Compose files, including override file behavior, merge semantics for lists and maps, and the `--file` flag for specifying alternate files. Essential for understanding the dev/prod configuration split in Section 8.

- [Snyk Blog: Best Practices for Containerizing Python Applications](https://snyk.io/blog/best-practices-containerizing-python-docker/) — A security-focused guide to Python containerization covering supply chain risks in base images, non-root users, secret management, and vulnerability scanning. Extends the security practices introduced in this module with practical remediation steps.

- [LangChain Chroma Integration — langchain-chroma Docs](https://python.langchain.com/docs/integrations/vectorstores/chroma/) — The official LangChain documentation for the ChromaDB integration, covering `HttpClient` configuration, collection management, retrieval modes, and persistence patterns. Reference this when customizing the retrieval behavior of the RAG pipeline in Section 7.

Sources:
- [FastAPI in Containers - Docker - FastAPI](https://fastapi.tiangolo.com/deployment/docker/)
- [FastAPI Docker Best Practices - Better Stack Community](https://betterstack.com/community/guides/scaling-python/fastapi-docker-best-practices/)
- [Docker - Ollama](https://docs.ollama.com/docker)
- [ollama/ollama - Docker Image](https://hub.docker.com/r/ollama/ollama)
- [Docker - Chroma Docs](https://docs.trychroma.com/guides/deploy/docker)
- [chromadb/chroma - Docker Image](https://hub.docker.com/r/chromadb/chroma)
- [Installing the NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- [Enable GPU support - Docker Docs](https://docs.docker.com/compose/how-tos/gpu-support/)
- [Docker Best Practices for Python Developers - TestDriven.io](https://testdriven.io/blog/docker-best-practices/)
- [GitHub - abetlen/llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
