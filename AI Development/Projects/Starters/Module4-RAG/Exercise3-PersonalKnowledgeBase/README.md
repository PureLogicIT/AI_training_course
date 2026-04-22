# Exercise 3 — Personal Knowledge Base

A multi-source knowledge base with persistent Chroma storage, MultiQueryRetriever,
metadata filtering, and a document management UI. Runs as three Docker Compose
services: the Gradio app, Ollama, and ChromaDB.

## Quick Start (Docker Compose)

```bash
# Build and start all services
docker compose up --build

# Pull required models (first run only)
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull nomic-embed-text
```

Open http://localhost:7860.

## Local Development (without Docker)

```bash
# Start ChromaDB locally
pip install chromadb
chroma run --path ./chroma_storage --port 8000

# In a separate terminal, start Ollama and pull models
ollama pull llama3.2
ollama pull nomic-embed-text

# Run the app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
CHROMA_HOST=localhost CHROMA_PORT=8000 python app.py
```

## Features

- Add PDFs, TXT, MD files, and web URLs through a browser UI
- Persistent Chroma index (survives container restarts via Docker volume)
- MultiQueryRetriever generates multiple query phrasings to improve recall
- Filter Q&A by specific document source
- Delete individual documents from the index
- Usage stats: document count, chunk count, queries answered

## Stack

| Component | Library / Image |
|---|---|
| UI | Gradio 4.x |
| LLM + Embeddings | Ollama (llama3.2 + nomic-embed-text) |
| Vector store | ChromaDB 0.5.x (remote HTTP client) |
| Retrieval | MultiQueryRetriever (LangChain) |
| PDF loading | PyPDFLoader |
| Web loading | WebBaseLoader (beautifulsoup4 + lxml) |
| Orchestration | Docker Compose |
