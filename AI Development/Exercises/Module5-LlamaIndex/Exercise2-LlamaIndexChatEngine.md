# Exercise 2: Conversational RAG Chat App with LlamaIndex Chat Engine

> **Subject:** AI Development | **Module:** Module 5 — LlamaIndex | **Difficulty:** Intermediate | **Estimated Time:** 90–120 minutes

---

## Overview

The module introduced `index.as_chat_engine()` with `condense_plus_context` mode for multi-turn conversational RAG and response synthesizer modes (`compact`, `refine`, `tree_summarize`). In this exercise you will combine those concepts into a fully interactive Gradio chat application backed by ChromaDB for persistent vector storage.

Your app will allow a user to:

1. Upload multiple documents and index them into a ChromaDB collection
2. Chat with the indexed content using streaming responses in a Gradio `Chatbot` component
3. See a live "Sources" panel that updates after each response to show which nodes were retrieved
4. Switch between `compact`, `refine`, and `tree_summarize` response synthesizer modes mid-session and observe how answers change
5. Persist the ChromaDB index between app restarts — no re-indexing required unless new files are uploaded

---

## Learning Objectives

By the end of this exercise you will be able to:

- Wire ChromaDB as a persistent vector store backend using `ChromaVectorStore` and `StorageContext`
- Build and reload a `VectorStoreIndex` backed by ChromaDB using `from_documents()` and `from_vector_store()`
- Create a `condense_plus_context` chat engine and call `stream_chat()` to yield tokens progressively
- Stream tokens from a LlamaIndex chat engine response into a Gradio `Chatbot` component
- Expose `response_mode` as a UI control and rebuild the underlying query engine without re-indexing
- Display source node metadata in a separate Gradio panel after each chat turn

---

## Prerequisites

- Ollama running locally with `llama3.2` and `nomic-embed-text` pulled
- Python 3.10 or later with a virtual environment active
- Completed Exercise 1 (LlamaIndexQA) or equivalent familiarity with `VectorStoreIndex` and `Settings`
- Completed Module 5 Sections 5 and 6 (ChromaDB, chat engine, response modes)

---

## Instructions

### Step 1 — Configure Settings and ChromaDB helpers

In `app.py`, implement `configure_settings()` exactly as in Exercise 1 (Ollama LLM, OllamaEmbedding, chunk_size=512, chunk_overlap=50). Call it at module level before any UI construction.

Implement `get_chroma_components()` which:
1. Creates a `chromadb.PersistentClient(path=CHROMA_PATH)`.
2. Calls `client.get_or_create_collection(COLLECTION_NAME)` to get (or create) the collection.
3. Wraps it in `ChromaVectorStore(chroma_collection=collection)`.
4. Creates `StorageContext.from_defaults(vector_store=vector_store)`.
5. Returns `(vector_store, collection, storage_context)`.

### Step 2 — Implement `index_documents(files)`

This function is triggered by the "Index Documents" button:

1. Extract file paths from the Gradio file list (each file object has a `.name` attribute).
2. Load documents with `SimpleDirectoryReader(input_files=paths).load_data()`.
3. Call `get_chroma_components()` to get the vector store and storage context.
4. Index with `VectorStoreIndex.from_documents(documents, storage_context=storage_context, show_progress=True)`.
5. Store the resulting index in a module-level variable (e.g., `_current_index`).
6. Reset the module-level chat engine variable to `None` so it is rebuilt on the next chat turn.
7. Return a status string: `"Indexed N documents. Collection now has M vectors."` where M comes from `collection.count()`.

### Step 3 — Implement `get_or_load_index()`

This helper is called lazily before each operation:

1. If `_current_index` is not `None`, return it.
2. Otherwise, call `get_chroma_components()`. If `collection.count() == 0`, return `None`.
3. Load the index with `VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)`.
4. Store it in `_current_index` and return it.

### Step 4 — Implement the chat engine factory `get_chat_engine(index, response_mode)`

This function creates a fresh chat engine each time the response mode changes:

1. Call `index.as_chat_engine(chat_mode="condense_plus_context", similarity_top_k=4, verbose=False)`.

Note: the `condense_plus_context` chat engine uses the `Settings.llm` for synthesis, but the `response_mode` for the underlying query engine. To support swapping `response_mode`, you need to build the engine differently:

- Create a `RetrieverQueryEngine` using `index.as_query_engine(similarity_top_k=4, response_mode=response_mode)` as the underlying engine.
- Pass `query_engine=...` explicitly when creating the chat engine using `CondensePlusContextChatEngine.from_defaults(query_engine=query_engine, similarity_top_k=4)`.

Alternatively, store the `response_mode` and rebuild a new `as_chat_engine()` call accepting a `query_engine` kwarg. Consult the LlamaIndex API to find the right constructor.

A simpler working approach: use `index.as_chat_engine(chat_mode="condense_plus_context", similarity_top_k=4)` and accept that `response_mode` changes require rebuilding the chat engine by setting `_chat_engine = None` when the mode dropdown changes.

### Step 5 — Implement `chat(user_message, history, response_mode)`

This generator function drives the Gradio streaming chat:

1. Load the index with `get_or_load_index()`. If `None`, yield `(history + [["Error", "No index loaded."]], "")` and return.
2. Get or build the chat engine (rebuild if `response_mode` has changed since last call).
3. Call `chat_engine.stream_chat(user_message)`.
4. Yield progressively by iterating over `streaming_response.response_gen`, appending each token to a buffer, and yielding `(updated_history, "")` after each token. Update the last assistant message in `history` in-place.
5. After the stream completes, build a sources string from `streaming_response.source_nodes` (file name, score, first 300 characters of text). Yield `(final_history, sources_string)`.

### Step 6 — Implement `clear_chat()`

Reset the module-level `_chat_engine` to `None` and return `([], "")` — an empty history and empty sources panel. This lets the user start a fresh conversation without re-indexing.

### Step 7 — Build the Gradio UI

Create a `gr.Blocks()` layout with two columns or tabs:

**Left / top panel — Document management:**
- `gr.File` accepting `.txt`, `.md`, `.pdf` (multiple files)
- "Index Documents" button → calls `index_documents` → updates a status textbox
- `gr.Radio` with choices `["compact", "refine", "tree_summarize"]`, default `"compact"`, label "Response Mode"

**Right / main panel — Chat:**
- `gr.Chatbot` component (set `height=500`)
- `gr.Textbox` for user input (single line, placeholder "Ask a question about your documents...")
- "Send" button that calls the `chat` generator
- "Clear Chat" button that calls `clear_chat`
- `gr.Textbox` for sources, `lines=12`, label "Retrieved Sources (last response)", `interactive=False`

Wire the response-mode `gr.Radio` so that when its value changes, `_chat_engine` is set to `None` (use a small helper function as the event handler that returns a status update).

### Step 8 — Run and verify

```bash
cd "AI Development/Projects/Starters/Exercise2-LlamaIndexChatEngine"
pip install -r requirements.txt
python app.py
```

Upload two or more documents, index them, then hold a three-turn conversation where each follow-up question builds on the previous answer. Verify that follow-up context is maintained (the engine rewrites the question using history). Then switch the response mode and ask the same question again — observe whether the answer length or structure changes.

---

## Expected Outcome

- [ ] The app starts and the Gradio UI opens at `http://127.0.0.1:7860`
- [ ] Uploading files and clicking "Index Documents" shows "Indexed N documents. Collection now has M vectors."
- [ ] Sending a first message returns a streamed response visible token-by-token in the chatbot
- [ ] A follow-up message that says "tell me more about that" produces a coherent answer related to the first response (history is used)
- [ ] The Sources panel updates after each response showing file names, scores, and passage snippets
- [ ] Switching from `compact` to `tree_summarize` and re-asking a broad question produces a visibly more structured or longer answer
- [ ] Clicking "Clear Chat" empties the chatbot history and sources panel
- [ ] Restarting the app and chatting **without re-uploading** works because ChromaDB persisted the index
- [ ] The Dockerfile builds successfully with `docker build -t llamaindex-chat .`

---

## Hints

- Streaming into a Gradio `gr.Chatbot` requires your handler to be a generator (`yield` not `return`). Initialise the history with the user message and an empty assistant message, then update the assistant message token by token.
- `stream_chat()` returns a `StreamingAgentChatResponse`. Its `.source_nodes` attribute is populated **after** the stream is fully consumed — iterate the full `response_gen` before reading `.source_nodes`.
- When building the chat engine, `condense_plus_context` mode issues two LLM calls per turn (one to rewrite the question, one to synthesize). With Ollama on average hardware this can take 20–40 seconds total. Increase `request_timeout` to at least `180.0`.
- Do not call `index.storage_context.persist()` when using ChromaDB — ChromaDB's `PersistentClient` persists automatically. Calling `persist()` on top of ChromaDB creates inconsistent state (see Module 5 Pitfall 3).
- The `gr.Radio` value is passed as a positional argument to your chat function. Make it the third parameter so that `(user_message, history, response_mode)` matches Gradio's call signature.

---

## Bonus Challenges

1. Add a `gr.Slider` for `similarity_top_k` (range 1–8) and wire it to the chat engine reconstruction.
2. Show the conversation turn count and a "Tokens in history" estimate in a `gr.Markdown` status bar.
3. Add a "Download Chat" button that saves the full conversation as a `.txt` file using `gr.File`.
4. Implement a side-by-side mode: two chatbots that answer the same question simultaneously using two different response modes, allowing direct comparison.
