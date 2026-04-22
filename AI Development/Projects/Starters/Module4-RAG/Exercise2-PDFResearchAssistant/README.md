# Exercise 2 — PDF Research Assistant

Upload one or more PDFs, ask questions in a chat interface, and inspect retrieved
source pages with optional similarity scores.  All embeddings run locally with
`sentence-transformers` — no Ollama required for the embedding step.

## Quick Start

```bash
# Pull the LLM (embeddings are handled by sentence-transformers, not Ollama)
ollama pull llama3.2

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:7860.

## Docker

```bash
docker build -t pdf-assistant:1.0 .
docker run --rm -p 7860:7860 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  pdf-assistant:1.0
```

## Features

- Multi-PDF upload with drag-and-drop
- FAISS vector store (fully in-memory, fast)
- Offline embeddings via `all-MiniLM-L6-v2` (sentence-transformers)
- Chat interface with conversation history
- Sources panel showing file name, page number, and content excerpt
- Debug mode toggle that reveals L2 similarity scores
- Chunk size / overlap sliders with live re-indexing

## Stack

| Component | Library |
|---|---|
| UI | Gradio 4.x |
| LLM | Ollama (llama3.2) via langchain-ollama |
| Embeddings | HuggingFaceEmbeddings (all-MiniLM-L6-v2) — fully offline |
| Vector store | FAISS (in-memory) |
| PDF loading | PyPDFLoader (langchain-community) |
| Chunking | RecursiveCharacterTextSplitter |
