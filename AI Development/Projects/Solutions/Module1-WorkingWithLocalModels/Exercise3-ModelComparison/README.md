# Exercise 3 — Multi-Turn Model Comparison App (Solution)

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

ollama pull llama3.2
ollama pull phi4-mini

python app.py
```

Open http://localhost:7860.

## Running with Docker Compose

```bash
docker compose up --build
```

Pull models into the running Ollama container:

```bash
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull phi4-mini
```

Open http://localhost:7860.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
