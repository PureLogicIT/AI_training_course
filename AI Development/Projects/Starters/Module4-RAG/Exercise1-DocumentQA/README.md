# Exercise 1 — Local Document Q&A

Upload `.txt` or `.md` files and ask questions about them.  
All processing is local — no cloud API calls.

## Quick Start

```bash
# 1. Pull required Ollama models
ollama pull nomic-embed-text
ollama pull llama3.2

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Open http://localhost:7860 in your browser.

## Docker

```bash
docker build -t doc-qa:1.0 .
docker run --rm -p 7860:7860 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  doc-qa:1.0
```

## Stack

| Component | Library |
|---|---|
| UI | Gradio 4.x |
| LLM | Ollama (llama3.2) via langchain-ollama |
| Embeddings | Ollama (nomic-embed-text) via langchain-ollama |
| Vector store | Chroma (in-memory, per session) |
| Document loading | LangChain TextLoader |
| Chunking | RecursiveCharacterTextSplitter |
