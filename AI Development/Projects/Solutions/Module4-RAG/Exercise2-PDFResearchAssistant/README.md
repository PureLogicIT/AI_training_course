# Exercise 2 — PDF Research Assistant (Solution)

Upload PDFs, ask questions in a chat interface, inspect source pages with optional
similarity scores. Fully offline embeddings via sentence-transformers.

## Quick Start

```bash
ollama pull llama3.2

python -m venv .venv
source .venv/bin/activate
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
