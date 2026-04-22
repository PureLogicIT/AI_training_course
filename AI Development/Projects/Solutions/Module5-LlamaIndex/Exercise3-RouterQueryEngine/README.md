# Exercise 3 — Multi-Index Routing Assistant (Solution)

This is the complete reference solution for Exercise 3.

## Quick Start

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
pip install -r requirements.txt
python app.py
```

Open [http://localhost:7860](http://localhost:7860).

## Running with Docker Compose

```bash
docker-compose up --build
```

After the stack is up, pull models into the Ollama container:

```bash
docker exec ollama ollama pull llama3.2
docker exec ollama ollama pull nomic-embed-text
```

The app will be at `http://localhost:7860`.

## Key Implementation Details

- The Facts Index uses `VectorStoreIndex` with 256-token chunks backed by ChromaDB. It survives restarts.
- The Summaries Index uses `SummaryIndex` with 1024-token chunks held in memory. It must be rebuilt each session.
- The Router uses `LLMSingleSelector` — an LLM call that reads your question and the tool descriptions to pick the right index. This adds 10-20 seconds of latency before retrieval begins.
- Metadata filtering bypasses the router entirely and queries the Facts Index with a `MetadataFilters` constraint.
- The re-ranker (`cross-encoder/ms-marco-MiniLM-L-2-v2`) downloads ~85 MB on first use and is then cached locally.
- `OLLAMA_BASE_URL` is read from the environment variable, defaulting to `http://localhost:11434`. The docker-compose sets it to `http://ollama:11434` for container-to-container networking.
