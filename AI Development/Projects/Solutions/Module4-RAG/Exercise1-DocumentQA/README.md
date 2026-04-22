# Exercise 1 — Local Document Q&A (Solution)

Upload `.txt` or `.md` files and ask questions about them.
All processing is local — no cloud API calls.

## Quick Start

```bash
ollama pull nomic-embed-text
ollama pull llama3.2

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:7860.

## Docker

```bash
docker build -t doc-qa:1.0 .
docker run --rm -p 7860:7860 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  doc-qa:1.0
```
