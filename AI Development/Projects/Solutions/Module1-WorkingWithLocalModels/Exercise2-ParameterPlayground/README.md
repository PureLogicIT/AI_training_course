# Exercise 2 — Model Parameter Tuning Playground (Solution)

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:7860.

## Running with Docker (Ollama backend only)

```bash
docker build -t exercise2-playground .
docker run --rm \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=llama3.2 \
  -p 7860:7860 \
  exercise2-playground
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Model to use with Ollama backend |
