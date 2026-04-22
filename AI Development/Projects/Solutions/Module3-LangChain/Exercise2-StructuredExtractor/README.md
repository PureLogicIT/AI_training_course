# Exercise 2 — Structured Data Extraction (Solution)

Complete reference solution for Exercise 2.

## Running the Solution

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:7860.

## Docker

```bash
docker build -t structured-extractor:1.0 .
docker run --rm -p 7860:7860 \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  structured-extractor:1.0
```

## What the Solution Demonstrates

- Three Pydantic schemas with `Field(description=...)` for parser format instructions.
- `PydanticOutputParser` + `OutputFixingParser` for resilient JSON extraction.
- `RunnableParallel` to branch after the LLM step: one branch captures raw text via
  `StrOutputParser`, the other validates and parses via `OutputFixingParser`.
- `temperature=0.0` for deterministic structured output.
- Graceful error handling: parse failures surface as a message in the UI, never a traceback.
