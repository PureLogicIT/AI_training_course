# Exercise 3 - Multi-Turn Conversational Assistant

A Gradio application featuring persistent multi-turn conversation using
LangChain's RunnableWithMessageHistory, automatic history trimming, named
session save/load, and a chain graph inspector.

## Prerequisites

- Ollama running: `ollama serve`
- At least one model pulled: `ollama pull llama3.2`
- Python 3.11+

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:7860.

## Docker Compose (includes Ollama)

```bash
docker-compose up --build
```

This starts both the app and an Ollama server. On first run, pull the model
inside the Ollama container:

```bash
docker exec -it ollama ollama pull llama3.2
```

Then refresh http://localhost:7860.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `SESSIONS_DIR` | `./sessions` | Directory for saved session JSON files |

## Session Files

Saved sessions are stored as `{SESSIONS_DIR}/{session_id}.json`. Each file
contains a JSON array of message objects:

```json
[
  {"role": "human", "content": "What is a generator?"},
  {"role": "ai",    "content": "A generator is a function that..."}
]
```
