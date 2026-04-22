# Exercise 1 — LangChain LCEL Q&A Chain

A Gradio application that wraps a three-step LangChain LCEL chain
(`ChatPromptTemplate` -> `ChatOllama` -> `StrOutputParser`) with a browser UI.

## Prerequisites

- Ollama installed and running: `ollama serve`
- At least one model pulled: `ollama pull llama3.2`
- Python 3.11+

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:7860 in your browser.

## Docker

Build:

```bash
docker build -t qa-chain-app:1.0 .
```

Run (the `--add-host` flag lets the container reach Ollama on the host):

```bash
docker run --rm -p 7860:7860 \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  qa-chain-app:1.0
```

Open http://localhost:7860.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL. Override when running in Docker. |
