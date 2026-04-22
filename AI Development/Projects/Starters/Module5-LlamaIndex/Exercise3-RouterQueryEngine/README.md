# Exercise 3 — Multi-Index Routing Assistant with RouterQueryEngine

A Gradio app that maintains two independent LlamaIndex indexes and uses `RouterQueryEngine` with `LLMSingleSelector` to route queries to the right one automatically.

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

The app will be at `http://localhost:7860`. Ollama runs as a sidecar container.

After the stack is up, pull models into the Ollama container:

```bash
docker exec ollama ollama pull llama3.2
docker exec ollama ollama pull nomic-embed-text
```

## Project Structure

```
Exercise3-RouterQueryEngine/
├── app.py               # Main Gradio application (complete the TODOs)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml   # Starts app + Ollama together
└── README.md
```

## Key Concepts Practised

- `VectorStoreIndex` (small chunks) vs `SummaryIndex` (large chunks)
- `RouterQueryEngine` with `LLMSingleSelector`
- `QueryEngineTool.from_defaults()` with descriptive tool descriptions
- `MetadataFilters` with `FilterOperator.EQ` for scoped retrieval
- `SentenceTransformerRerank` as a node post-processor
- Capturing verbose routing output via stdout redirect
