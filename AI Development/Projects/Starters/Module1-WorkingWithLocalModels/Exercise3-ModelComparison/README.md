# Exercise 3 — Multi-Turn Model Comparison App

A Gradio app with three tabs: multi-turn chat with model switching and token stats,
conversation save/load, and side-by-side model comparison.

## Prerequisites

- Ollama running with at least two models pulled:
  ```
  ollama pull llama3.2
  ollama pull phi4-mini
  ```
- Python 3.11+ or Docker Desktop

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export OLLAMA_HOST=http://localhost:11434   # optional, this is the default

python app.py
```

Open http://localhost:7860.

## Running with Docker Compose

```bash
docker compose up --build
```

This starts two containers:
- `ollama` — the Ollama server (port 11434)
- `app`    — the Gradio UI (port 7860)

Open http://localhost:7860.

Pull models into the Ollama container after first start:

```bash
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull phi4-mini
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
