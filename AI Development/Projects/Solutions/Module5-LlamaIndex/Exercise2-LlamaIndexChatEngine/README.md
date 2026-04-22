# Exercise 2 — Conversational RAG Chat App (Solution)

This is the complete reference solution for Exercise 2.

## Quick Start

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
pip install -r requirements.txt
python app.py
```

Open [http://localhost:7860](http://localhost:7860).

## Running with Docker

```bash
docker build -t llamaindex-chat-solution .
docker run -p 7860:7860 \
    -v $(pwd)/chroma_chat:/app/chroma_chat \
    llamaindex-chat-solution
```

Note: on macOS/Windows Docker, set `OLLAMA_BASE_URL = "http://host.docker.internal:11434"` in `app.py`.
