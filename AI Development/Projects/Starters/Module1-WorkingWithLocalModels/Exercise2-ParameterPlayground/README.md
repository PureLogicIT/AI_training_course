# Exercise 2 — Model Parameter Tuning Playground

Experiment with Ollama and llama-cpp-python inference parameters through a live Gradio UI.

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: set Ollama server address
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=llama3.2

python app.py
```

Open http://localhost:7860.

### Using llama-cpp-python backend

Make sure `llama-cpp-python` is installed and enter the path to your GGUF file
in the "GGUF Model Path" field after selecting the `llama-cpp-python` backend.

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
| `OLLAMA_MODEL` | `llama3.2` | Model name for Ollama backend |
