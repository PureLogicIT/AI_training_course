# Exercise 3 — Personal Knowledge Base (Solution)

A multi-source knowledge base with persistent Chroma storage, MultiQueryRetriever,
metadata filtering, and a document management UI. Runs as three Docker Compose
services: the Gradio app, Ollama, and ChromaDB.

## Quick Start (Docker Compose)

```bash
docker compose up --build

# Pull required models inside the Ollama container (first run only)
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull nomic-embed-text
```

Open http://localhost:7860.

## Local Development

```bash
# Start ChromaDB
pip install chromadb
chroma run --path ./chroma_storage --port 8000

# Start Ollama and pull models
ollama pull llama3.2
ollama pull nomic-embed-text

# Run the app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
CHROMA_HOST=localhost CHROMA_PORT=8000 python app.py
```

## Architecture

```
browser
  └── Gradio app (port 7860)
        ├── ChromaDB HTTP client  →  chromadb service (port 8000, volume: chroma_data)
        └── OllamaEmbeddings      →  ollama service   (port 11434, volume: ollama_data)
```

The Chroma index persists in the named Docker volume `chroma_data` and survives
`docker compose down` / `docker compose up` cycles.
