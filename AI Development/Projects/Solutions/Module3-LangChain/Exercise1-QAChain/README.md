# Exercise 1 — LangChain LCEL Q&A Chain (Solution)

Complete reference solution for Exercise 1.

## Running the Solution

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:7860.

## Docker

```bash
docker build -t qa-chain-app:1.0 .
docker run --rm -p 7860:7860 \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  qa-chain-app:1.0
```

## What the Solution Demonstrates

- `ChatOllama` instantiated per-request so model and host settings take effect immediately.
- LCEL pipe operator (`|`) connecting `ChatPromptTemplate`, `ChatOllama`, and `StrOutputParser`.
- Generator-based streaming: each `yield` in `answer_question` pushes an incremental update to Gradio.
- `OLLAMA_HOST` environment variable for Docker compatibility.
