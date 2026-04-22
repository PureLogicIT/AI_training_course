# Exercise 2 — Conversational RAG Chat App with LlamaIndex Chat Engine

A Gradio chat application that uses LlamaIndex's `as_chat_engine()` with `condense_plus_context` mode for multi-turn RAG conversations, backed by ChromaDB for persistent storage.

## Quick Start

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
pip install -r requirements.txt
python app.py
```

Open [http://localhost:7860](http://localhost:7860).

## Features to Implement

- ChromaDB-backed persistent vector store
- Streaming chat responses (token by token)
- Sources panel showing retrieved passages
- Response mode selector (compact / refine / tree_summarize)
- Clear conversation history

## Running with Docker

```bash
docker build -t llamaindex-chat .
docker run -p 7860:7860 \
    -v $(pwd)/chroma_chat:/app/chroma_chat \
    llamaindex-chat
```

## Project Structure

```
Exercise2-LlamaIndexChatEngine/
├── app.py           # Main Gradio application (complete the TODOs)
├── requirements.txt
├── Dockerfile
└── README.md
```

## Key Concepts Practised

- `ChromaVectorStore` + `StorageContext` for persistent vector storage
- `VectorStoreIndex.from_vector_store()` for loading without re-embedding
- `index.as_chat_engine(chat_mode="condense_plus_context")`
- `chat_engine.stream_chat()` and streaming into Gradio `Chatbot`
- `response_mode` parameter and its effect on answer quality
