# Exercise 1 — Streaming Chat App

A Gradio chat interface for local Ollama models with streaming responses.

## Prerequisites

- Ollama running locally with at least one model pulled (`ollama pull llama3.2`)
- Python 3.11+ **or** Docker Desktop

---

## Running Locally

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Point at a remote Ollama server
export OLLAMA_HOST=http://your-server:11434   # omit to use localhost

# 4. Start the app
python app.py
```

Open http://localhost:7860 in your browser.

---

## Running with Docker

```bash
# Build the image
docker build -t exercise1-streaming-chat .

# Run — connect to Ollama on the host machine
docker run --rm \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -p 7860:7860 \
  exercise1-streaming-chat
```

Open http://localhost:7860 in your browser.

> On Linux, `host.docker.internal` may not resolve automatically.
> Use your host machine's LAN IP instead:
> `-e OLLAMA_HOST=http://192.168.1.x:11434`

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | URL of the Ollama server |
