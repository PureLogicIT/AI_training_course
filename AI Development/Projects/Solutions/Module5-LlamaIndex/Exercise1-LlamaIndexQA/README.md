# Exercise 1 — Local Document Q&A with LlamaIndex and Gradio (Solution)

This is the complete reference solution for Exercise 1.

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
docker build -t llamaindex-qa-solution .
docker run -p 7860:7860 \
    -v $(pwd)/index_storage:/app/index_storage \
    llamaindex-qa-solution
```

Note: the container connects to Ollama on `http://localhost:11434`. When running in Docker on macOS/Windows, change `OLLAMA_BASE_URL` in `app.py` to `http://host.docker.internal:11434`.
