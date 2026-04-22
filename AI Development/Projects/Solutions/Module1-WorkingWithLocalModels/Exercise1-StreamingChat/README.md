# Exercise 1 — Streaming Chat App (Solution)

A Gradio chat interface for local Ollama models with streaming responses.

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:7860.

## Running with Docker

```bash
docker build -t exercise1-streaming-chat .
docker run --rm \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -p 7860:7860 \
  exercise1-streaming-chat
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | URL of the Ollama server |
