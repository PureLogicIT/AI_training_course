# Exercise 1 — Local Document Q&A with LlamaIndex and Gradio

A Gradio web app that lets you upload documents, index them locally with LlamaIndex, and ask questions in the browser. No cloud APIs — Ollama runs everything locally.

## Quick Start

### Prerequisites

- [Ollama](https://ollama.com) installed and running
- Python 3.10+

### 1. Pull required models

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
python app.py
```

Open [http://localhost:7860](http://localhost:7860) in your browser.

## Usage

1. Upload one or more `.txt`, `.md`, or `.pdf` files using the file picker.
2. Click **Index Documents** — wait for the status message confirming indexing.
3. Type a question in the question box and click **Ask**.
4. The answer appears above, and the source passages used appear below.
5. The index persists on disk — restart the app without re-uploading and it still works.

## Running with Docker

```bash
# Build the image
docker build -t llamaindex-qa .

# Run (Ollama must be accessible from the container)
docker run -p 7860:7860 \
    -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
    -v $(pwd)/index_storage:/app/index_storage \
    llamaindex-qa
```

## Project Structure

```
Exercise1-LlamaIndexQA/
├── app.py           # Main Gradio application (complete the TODOs)
├── requirements.txt
├── Dockerfile
└── README.md
```

## Key Concepts Practised

- `Settings.llm` and `Settings.embed_model` configuration order
- `SimpleDirectoryReader(input_files=[...])` for dynamic file lists
- `VectorStoreIndex.from_documents()` and `index.storage_context.persist()`
- `load_index_from_storage(StorageContext.from_defaults(persist_dir=...))`
- `query_engine.query()` and `response.source_nodes` inspection
