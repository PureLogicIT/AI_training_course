# Exercise 2: PDF Research Assistant with FAISS + Gradio

> Module: Module4-RAG | Difficulty: Intermediate | Estimated Time: 90–150 minutes

## Scenario

You are building a tool for a research team that accumulates large PDF collections
— papers, reports, technical manuals. They need to query across all of them without
sending proprietary documents to a cloud service. They also want to understand *why*
the system gives a particular answer: which PDF pages contributed, what the similarity
scores looked like, and how chunking choices affect what gets retrieved.

Your task is to build a Gradio research assistant that:
- Accepts one or more PDFs via drag-and-drop.
- Chunks and indexes them with FAISS and `sentence-transformers` (fully offline — no
  Ollama required for embeddings).
- Provides a chat interface for multi-turn Q&A.
- Shows a "Sources" panel with the PDF file name, page number, and similarity score
  for every retrieved chunk.
- Exposes chunk-size and overlap sliders so the user can re-index with different
  settings and observe how retrieval changes.
- Has a "Debug mode" toggle that reveals raw similarity scores alongside retrieved
  snippets.

---

## Learning Objectives

By completing this exercise you will be able to:

1. Load multi-page PDFs with `PyPDFLoader` and inspect per-page metadata.
2. Build and save a FAISS vector store using `HuggingFaceEmbeddings` (sentence-
   transformers) for fully offline embeddings.
3. Query a FAISS store with `similarity_search_with_score()` to obtain raw distance
   scores.
4. Implement a Gradio chat interface (`gr.Chatbot`) that maintains conversation history.
5. Expose chunking parameters as interactive sliders and rebuild the index on demand.
6. Present a structured "Sources" panel that cites page numbers and similarity scores.
7. Build a Debug mode that surfaces retrieval internals in the UI.

---

## Prerequisites

- Python 3.11 with a virtual environment activated.
- Ollama running locally with `llama3.2` pulled (embeddings are handled by
  `sentence-transformers` — no Ollama embedding model required):
  ```bash
  ollama pull llama3.2
  ```
- One or more PDF files to test with (any PDF with selectable text works; a
  documentation PDF or research paper is ideal).
- Docker Desktop (for the bonus containerisation step).

---

## Project Structure

```
Exercise2-PDFResearchAssistant/
├── app.py              # Gradio interface  <-- you edit this
├── indexer.py          # PDF loading, chunking, FAISS indexing  <-- you edit this
├── retriever.py        # Query logic and scoring  <-- you edit this
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Instructions

### Step 1 — Implement PDF indexing in `indexer.py`

Open `indexer.py`. Implement the function `build_index(pdf_paths, chunk_size, chunk_overlap)`:

1. For each path in `pdf_paths`, load it with `PyPDFLoader` and extend a master
   document list with the result. Each page becomes one `Document`; its metadata
   already contains `"source"` (file path) and `"page"` (zero-indexed integer).
2. Split all documents with `RecursiveCharacterTextSplitter` using the supplied
   `chunk_size` and `chunk_overlap` values.
3. Create `HuggingFaceEmbeddings` with `model_name="all-MiniLM-L6-v2"`. On first run
   the model (~80 MB) downloads automatically and is cached for offline use.
4. Build the FAISS vector store with `FAISS.from_documents(chunks, embeddings)`.
5. Return a tuple `(vectorstore, chunks)` — the caller needs the chunk list to display
   indexing statistics.

Hint: `PyPDFLoader` returns one `Document` per page. A 20-page PDF produces 20
`Document` objects before splitting.

### Step 2 — Implement scored retrieval in `retriever.py`

Open `retriever.py`. Implement `retrieve_with_scores(vectorstore, question, k=5)`:

1. Call `vectorstore.similarity_search_with_score(question, k=k)`.
2. This returns a list of `(Document, float)` tuples. The float is the L2 distance —
   **lower means more similar**.
3. Return the list as-is so the caller can display both the document and its score.

Also implement `build_rag_chain(vectorstore, k=5)`:

1. Create a `ChatOllama` LLM (`model="llama3.2"`, `temperature=0.0`, `num_ctx=8192`).
2. Create a standard similarity retriever with `as_retriever(search_kwargs={"k": k})`.
3. Build and return a `create_retrieval_chain` chain with an appropriate RAG system
   prompt (instruct the model to cite page numbers when known).

### Step 3 — Implement `app.py`

Open `app.py`. You must implement three callback functions:

**`handle_upload_and_index(files, chunk_size, chunk_overlap)`**
- Receives uploaded file objects from Gradio and the current slider values.
- Calls `build_index(pdf_paths, chunk_size, chunk_overlap)`.
- Stores the vectorstore globally and rebuilds the RAG chain.
- Returns a status string: `"Indexed N PDF(s) — M total chunks (chunk_size=X, overlap=Y)."`.

**`handle_chat(message, history, debug_mode, k_value)`**
- Guards against no index being loaded.
- Calls `retrieve_with_scores(vectorstore, message, k=k_value)` to obtain scored chunks.
- Calls the RAG chain to generate an answer.
- Appends `(message, answer)` to `history` (Gradio chatbot format).
- Formats the sources panel:
  - Always show: file name (basename only), page number (1-indexed: `page + 1`),
    and a 250-character excerpt.
  - If `debug_mode` is True, also show the raw L2 distance score formatted to 4
    decimal places.
- Returns `(updated_history, sources_text)`.

**`handle_reindex(files, chunk_size, chunk_overlap)`**
- Same logic as `handle_upload_and_index` but clears `history` and resets the chat.
- Returns `(status_string, [], "")` — status, empty chat history, empty sources.

### Step 4 — Build the Gradio layout

Still in `app.py`, assemble the UI with `gr.Blocks`:

- A `gr.File` component (multiple, `.pdf` only) for uploads.
- Sliders: `chunk_size` (range 100–1500, step 50, default 600) and
  `chunk_overlap` (range 0–300, step 25, default 75).
- An "Index PDFs" button that calls `handle_upload_and_index`.
- A "Re-index with new settings" button that calls `handle_reindex`.
- A status `gr.Textbox` (read-only).
- A `gr.Chatbot` for the conversation history.
- A `gr.Textbox` for the user message input.
- A "Send" button that calls `handle_chat`.
- A `gr.Checkbox` labelled "Debug mode (show similarity scores)".
- A `gr.Slider` for K (retrieved chunks, range 1–10, default 5).
- A `gr.Textbox` (read-only, lines=15) labelled "Sources".

### Step 5 — Run and verify

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:7860`.

1. Upload one or two PDFs and index them.
2. Ask a question you know is answered in the PDFs. Verify the sources panel shows the
   correct page numbers.
3. Enable Debug mode and re-ask the question. Verify similarity scores appear.
4. Change the chunk size slider to 200, click "Re-index". Ask the same question again
   and compare the source excerpts — smaller chunks produce shorter, more focused
   excerpts.
5. Ask a question not in the PDFs. The model should say it cannot find the answer.

### Step 6 (Bonus) — Docker

```bash
docker build -t pdf-assistant:1.0 .
docker run --rm -p 7860:7860 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  pdf-assistant:1.0
```

---

## Expected Outcome

- [ ] Uploading PDFs displays a status message with the PDF count, total chunks,
      chunk size, and overlap (e.g., `"Indexed 2 PDF(s) — 183 total chunks (chunk_size=600, overlap=75)."`).
- [ ] The chat interface accepts questions and returns grounded answers.
- [ ] The Sources panel shows the PDF file name and page number for every retrieved
      chunk.
- [ ] Enabling Debug mode adds L2 distance scores to the Sources panel.
- [ ] Changing chunk size and clicking "Re-index" rebuilds the index and resets the
      chat.
- [ ] K slider changes how many source chunks are shown per answer.
- [ ] Asking an out-of-scope question produces an "I don't know" response rather than
      a fabricated answer.
- [ ] (Bonus) Docker image builds and serves the app on port 7860.

---

## Hints

- `PyPDFLoader` returns pages with `metadata["page"]` as a **zero-indexed** integer.
  Add 1 when displaying to match what users expect (`Page 1`, not `Page 0`).
- FAISS L2 distance is the **square of the Euclidean distance**. A score near `0.0`
  means highly similar; scores above `1.5` are typically a poor match. You can show
  this as-is or convert to a pseudo-similarity with `1 / (1 + score)`.
- `HuggingFaceEmbeddings` caches the model in `~/.cache/huggingface/` after the first
  download — subsequent runs are fully offline.
- When re-indexing, delete any reference to the old FAISS object before calling
  `from_documents()` again so Python can garbage-collect it.
- Gradio's `gr.Chatbot` expects history as a list of `[user_message, bot_message]`
  pairs (list of lists), not tuples, in older Gradio versions. Check your installed
  version and adjust if needed.
- The `sentence-transformers` first-run download can take 30–60 seconds. Display a
  "Embedding model loading..." message in the status box while indexing.
