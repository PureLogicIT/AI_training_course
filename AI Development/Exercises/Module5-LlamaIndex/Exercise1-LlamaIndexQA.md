# Exercise 1: Local Document Q&A with LlamaIndex and Gradio

> **Subject:** AI Development | **Module:** Module 5 — LlamaIndex | **Difficulty:** Beginner | **Estimated Time:** 60–90 minutes

---

## Overview

The module showed you how to build a command-line document Q&A system using `VectorStoreIndex`, `SimpleDirectoryReader`, and Ollama. In this exercise you will take those same concepts and wrap them in a Gradio web UI so that any user — without touching the terminal — can upload files, trigger indexing, ask questions, and see which source passages were retrieved.

You will build a single-page Gradio app that:

1. Accepts file uploads (`.txt`, `.md`, `.pdf`) via a Gradio `File` component
2. Indexes the uploaded files into a `VectorStoreIndex` backed by LlamaIndex's built-in JSON persistence (`index.storage_context.persist()`)
3. Answers questions by calling `query_engine.query()` on the loaded index
4. Displays the answer **and** the raw text of the top retrieved nodes below each answer
5. Persists the index between Gradio sessions — restarting the app does not require re-indexing unchanged files

---

## Learning Objectives

By the end of this exercise you will be able to:

- Configure `Settings.llm` and `Settings.embed_model` **before** any index is constructed
- Use `SimpleDirectoryReader(input_files=[...])` to load a dynamic list of uploaded files
- Build and persist a `VectorStoreIndex` using `index.storage_context.persist()`
- Reload an existing index with `StorageContext.from_defaults(persist_dir=...)` and `load_index_from_storage()`
- Call `query_engine.query()` and extract both the answer string and `response.source_nodes`
- Wire a Gradio UI to LlamaIndex so that upload, indexing, and querying happen through the browser

---

## Prerequisites

- Ollama is running locally and you have pulled both required models:
  ```bash
  ollama pull llama3.2
  ollama pull nomic-embed-text
  ```
- Python 3.10 or later with a virtual environment active
- Completed Module 5 reading (at minimum Sections 2, 3, and 5)

---

## Instructions

### Step 1 — Configure the Settings singleton

Open `app.py` in the starter project. At the top of the file, after the imports, call the `configure_settings()` function.

Inside `configure_settings()`:
- Set `Settings.llm` to an `Ollama` instance using `model="llama3.2"`, `request_timeout=120.0`, and `context_window=8192`.
- Set `Settings.embed_model` to an `OllamaEmbedding` instance using `model_name="nomic-embed-text"`.
- Set `Settings.chunk_size = 512` and `Settings.chunk_overlap = 50`.

`configure_settings()` must be called **before** any index is built or loaded. This is enforced by calling it at module import time (i.e., at the bottom of the file outside any function).

### Step 2 — Implement `build_index(file_paths)`

This function receives a list of file paths (strings) from Gradio's file-upload component and must:

1. Load the files with `SimpleDirectoryReader(input_files=file_paths).load_data()`.
2. Create a `VectorStoreIndex` from the documents using `VectorStoreIndex.from_documents(documents, show_progress=True)`.
3. Persist the index to the `PERSIST_DIR` directory with `index.storage_context.persist(persist_dir=PERSIST_DIR)`.
4. Return a status string indicating how many documents were indexed.

If `file_paths` is empty or `None`, return an error message string without attempting to index.

### Step 3 — Implement `load_or_none()`

This function is called at startup to check whether a saved index already exists:

1. If `PERSIST_DIR` exists on disk, load the index using `StorageContext.from_defaults(persist_dir=PERSIST_DIR)` and `load_index_from_storage(storage_context)`, then return the index.
2. If `PERSIST_DIR` does not exist, return `None`.

### Step 4 — Implement `answer_question(question, index)`

This function is called each time the user submits a question:

1. If `index` is `None`, return `("No index loaded. Please upload documents first.", "")`.
2. Create a query engine with `index.as_query_engine(similarity_top_k=3, response_mode="compact")`.
3. Call `query_engine.query(question)` and capture the response.
4. Build a **sources string** by iterating over `response.source_nodes`. For each node, include:
   - The file name from `node.node.metadata.get("file_name", "unknown")`
   - The similarity score formatted to three decimal places
   - The first 400 characters of `node.node.get_content()`
5. Return a tuple of `(answer_text, sources_text)`.

### Step 5 — Wire the Gradio interface

In the `build_ui(initial_index)` function, create a `gr.Blocks()` app with:

- A `gr.File` component accepting multiple files with `file_types=[".txt", ".md", ".pdf"]`
- An "Index Documents" button that calls `build_index` with the uploaded file paths and updates a status `gr.Textbox`
- A `gr.Textbox` for the question input
- An "Ask" button (or `submit` on the textbox) that calls `answer_question`
- A `gr.Textbox` (or `gr.Markdown`) for the answer output
- A `gr.Textbox` for the sources output, with `lines=10` so retrieved passages are readable

Use a `gr.State` to hold the current index object and update it when new files are indexed.

### Step 6 — Run and verify

```bash
cd "AI Development/Projects/Starters/Exercise1-LlamaIndexQA"
pip install -r requirements.txt
python app.py
```

Open the URL printed to the terminal (default: `http://127.0.0.1:7860`).

Upload one or more `.txt` or `.md` files, click "Index Documents", then type a question and click "Ask". Verify that:
- The answer is relevant to the uploaded content
- The sources panel shows file names and passage snippets
- Restarting `app.py` without re-uploading still loads the previous index

---

## Expected Outcome

- [ ] The app starts without errors and the Gradio UI opens in the browser
- [ ] Uploading files and clicking "Index Documents" prints a success status (e.g., "Indexed 3 documents. 12 nodes stored.")
- [ ] Asking a question returns a non-empty answer drawn from the uploaded content
- [ ] The sources panel shows at least one retrieved node with file name, score, and passage text
- [ ] Stopping and restarting the app, then asking a question **without re-uploading**, still returns a correct answer (index persisted to disk)
- [ ] The Dockerfile builds successfully with `docker build -t llamaindex-qa .`

---

## Hints

- `gr.File` returns a list of file objects. Each object has a `.name` attribute that gives you the temp file path on disk. Pass these paths directly to `SimpleDirectoryReader(input_files=...)`.
- The `index` object cannot be stored directly in a Gradio `gr.State` if it holds non-serialisable objects. Store it in a Python module-level variable instead and use the `gr.State` only as a trigger signal, or just rebuild from disk on each query call.
- `response.source_nodes` is a list of `NodeWithScore` objects. The text of each node is at `node.node.get_content()` or `node.node.text`. The similarity score is at `node.score`.
- If you see `ImportError: cannot import name 'openai'` when building the index, it means `Settings.embed_model` was not set before `VectorStoreIndex.from_documents()` was called.
- The built-in persistence stores vectors in JSON files inside `PERSIST_DIR`. Do **not** mix this with ChromaDB — use one or the other.

---

## Bonus Challenges

1. Add a "Clear Index" button that deletes `PERSIST_DIR` and resets the app state.
2. Display the total number of vectors currently stored in the index in the UI header.
3. Add a slider to let the user adjust `similarity_top_k` (1–10) before querying.
4. Allow switching between `response_mode` values (`compact`, `refine`, `tree_summarize`) via a `gr.Radio` component and display which mode was used alongside the answer.
