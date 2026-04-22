# Exercise 3: Personal Knowledge Base with Advanced RAG

> Module: Module4-RAG | Difficulty: Hard | Estimated Time: 180–240 minutes

## Scenario

You want to build a personal knowledge base that ingests documents from multiple
sources — PDFs, plain text, Markdown files, and live web pages — and answers questions
about them using advanced retrieval techniques. Unlike a one-shot Q&A script, this
system must:

- **Persist across restarts**: The Chroma index survives container restarts via a
  Docker volume mount.
- **Handle diverse inputs**: PDF, TXT, MD files, and web URLs through a unified upload
  interface.
- **Improve recall on ambiguous questions**: `MultiQueryRetriever` generates multiple
  phrasings of each question and unions the results.
- **Support metadata filtering**: The user can restrict retrieval to a specific source
  file or document type.
- **Let users manage the index**: A management tab shows all indexed documents and lets
  the user delete individual ones.
- **Track usage**: The app displays the number of documents, chunks, and queries
  answered.

The system is deployed with Docker Compose — the app container, an Ollama service, and
a ChromaDB service all run as separate containers.

---

## Learning Objectives

By completing this exercise you will be able to:

1. Connect a LangChain app to a **remote ChromaDB** server using `HttpClient`.
2. Implement multi-source document loading (PDF, TXT, MD, web URLs) behind a single
   unified interface.
3. Use `MultiQueryRetriever` to improve recall on ambiguous queries.
4. Apply metadata filters at query time to scope retrieval to a specific source or
   type.
5. Delete individual documents from a Chroma collection using `collection.delete()`.
6. Build a multi-tab Gradio app with state shared across tabs.
7. Author a `docker-compose.yml` that wires a Python app, Ollama, and ChromaDB as
   services with health checks and named volumes.

---

## Prerequisites

- Docker Desktop with Compose support.
- Ollama running (either locally or as the Docker service) with these models pulled:
  ```bash
  ollama pull llama3.2
  ollama pull nomic-embed-text
  ```
- Python 3.11 with a virtual environment for local development (optional — Docker is
  the primary path for this exercise).
- Internet access for `WebBaseLoader` to fetch web pages.

---

## Project Structure

```
Exercise3-PersonalKnowledgeBase/
├── app.py                  # Multi-tab Gradio app  <-- you edit this
├── knowledge_base.py       # Document loading, indexing, retrieval  <-- you edit this
├── stats.py                # Usage statistics tracking  <-- you edit this
├── requirements.txt
├── Dockerfile
├── docker-compose.yml      <-- you edit this
└── README.md
```

---

## Instructions

### Step 1 — Complete `knowledge_base.py`: document loading

Open `knowledge_base.py`. Implement `load_documents(source, source_type)` where
`source` is either a file path string or a URL string, and `source_type` is one of
`"pdf"`, `"txt"`, `"md"`, or `"url"`.

1. **`"pdf"`**: Use `PyPDFLoader(source).load()`. Add `doc_type="pdf"` to each
   document's metadata.
2. **`"txt"` and `"md"`**: Use `TextLoader(source, encoding="utf-8").load()`. Add
   `doc_type` as `"txt"` or `"md"` accordingly.
3. **`"url"`**: Use `WebBaseLoader(web_paths=[source]).load()`. Add `doc_type="url"`
   and `source=source` to metadata (the loader may not set `source`).
4. Return the list of `Document` objects.

### Step 2 — Complete `knowledge_base.py`: connecting to ChromaDB

Implement `get_chroma_client(host, port)` that returns a `chromadb.HttpClient`
connected to the remote ChromaDB server. The host and port come from environment
variables `CHROMA_HOST` (default `"localhost"`) and `CHROMA_PORT` (default `8000`).

Implement `get_vectorstore(chroma_client, embedding_function)` that returns a
`Chroma` vectorstore instance backed by the remote client:

```python
from langchain_chroma import Chroma
vectorstore = Chroma(
    client=chroma_client,
    collection_name="personal_kb",
    embedding_function=embedding_function,
)
```

### Step 3 — Complete `knowledge_base.py`: indexing

Implement `index_documents(vectorstore, file_path_or_url, source_type)`:

1. Detect the `source_type` automatically if not provided:
   - `.pdf` extension → `"pdf"`, `.md` → `"md"`, starts with `http` → `"url"`,
     otherwise `"txt"`.
2. Call `load_documents()` to get raw documents.
3. Add a `doc_name` metadata field set to the basename of the file path or the URL
   string (this is the key used later for deletion and filtering).
4. Split with `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)`.
5. Add the chunks to the vectorstore using `vectorstore.add_documents(chunks)`.
6. Return the number of chunks added.

### Step 4 — Complete `knowledge_base.py`: MultiQueryRetriever

Implement `build_multi_query_chain(vectorstore, filter_metadata=None)`:

1. Create `OllamaEmbeddings(model="nomic-embed-text")` — use the `OLLAMA_BASE_URL`
   environment variable for the `base_url` parameter.
2. Create `ChatOllama` for the query LLM (`temperature=0.3`, `num_ctx=2048`) and a
   separate one for the answer LLM (`temperature=0.0`, `num_ctx=8192`).
3. Build a base retriever:
   - If `filter_metadata` is not None, pass it as the `filter` argument to
     `as_retriever()` via `search_kwargs={"k": 4, "filter": filter_metadata}`.
   - Otherwise use plain `search_kwargs={"k": 4}`.
4. Wrap it with `MultiQueryRetriever.from_llm(retriever=base_retriever, llm=query_llm)`.
5. Build a `create_stuff_documents_chain` + `create_retrieval_chain` using the answer
   LLM and an appropriate RAG system prompt.
6. Return the chain.

### Step 5 — Complete `knowledge_base.py`: document management

Implement `list_indexed_documents(vectorstore)`:
- Call `vectorstore.get()` to retrieve all stored items.
- Extract the unique `doc_name` values from the metadatas list.
- Return a sorted list of unique document names.

Implement `delete_document(vectorstore, doc_name)`:
- Get the internal Chroma collection: `collection = vectorstore._collection`.
- Query for all chunk IDs that belong to `doc_name`:
  ```python
  results = collection.get(where={"doc_name": doc_name})
  ids_to_delete = results["ids"]
  ```
- Call `collection.delete(ids=ids_to_delete)`.
- Return the number of chunks deleted.

### Step 6 — Complete `stats.py`

Open `stats.py`. It contains a simple in-memory stats tracker. Implement:

- `increment_queries()` — adds 1 to the query counter.
- `get_stats(vectorstore)` — returns a dict with:
  - `"queries_answered"`: the running count.
  - `"total_chunks"`: `vectorstore._collection.count()`.
  - `"unique_documents"`: `len(list_indexed_documents(vectorstore))`.

### Step 7 — Build the Gradio UI in `app.py`

Open `app.py`. Build a `gr.Blocks` app with three tabs:

**Tab 1 — "Add Documents"**
- A `gr.File` component (multiple, accepts `.pdf`, `.txt`, `.md`).
- A `gr.Textbox` for entering a web URL.
- An "Add Files" button.
- An "Add URL" button.
- A status `gr.Textbox` showing how many chunks were added.

**Tab 2 — "Ask Questions"**
- A `gr.Dropdown` labelled "Filter by document" with choices populated from
  `list_indexed_documents()`. Include an `"(All documents)"` option as the default.
- A `gr.Chatbot` for conversation history.
- A user input `gr.Textbox` and "Ask" button.
- A sources `gr.Textbox` (read-only, lines=12).
- A stats `gr.Textbox` (read-only) showing the output of `get_stats()`.

Implement `handle_ask(message, history, filter_choice)`:
- Build the chain with `build_multi_query_chain()`, passing the filter metadata only
  when `filter_choice != "(All documents)"` (use `{"doc_name": filter_choice}`).
- Invoke the chain, increment stats, format sources (show `doc_name`, `page` if
  present, and first 200 chars of content).
- Return `(updated_history, sources_text, stats_text)`.

**Tab 3 — "Manage Index"**
- A `gr.Dropdown` labelled "Select document to delete" populated from
  `list_indexed_documents()`.
- A "Delete Document" button.
- A `gr.Textbox` showing the result (e.g., `"Deleted 'report.pdf' — 23 chunks removed."`).
- A "Refresh document list" button that updates both dropdowns (Tab 2 and Tab 3).

### Step 8 — Complete `docker-compose.yml`

Open `docker-compose.yml`. It has the skeleton for three services. Fill in the TODOs:

1. **`ollama` service**: Use image `ollama/ollama:0.4.7`. Mount a named volume
   `ollama_data` at `/root/.ollama`. Expose port `11434`.
2. **`chromadb` service**: Use image `chromadb/chroma:0.5.20`. Mount a named volume
   `chroma_data` at `/chroma/chroma`. Expose port `8000`. Set environment variable
   `IS_PERSISTENT=TRUE`.
3. **`app` service**: Build from the local `Dockerfile`. Set environment variables:
   - `OLLAMA_BASE_URL=http://ollama:11434`
   - `CHROMA_HOST=chromadb`
   - `CHROMA_PORT=8000`
   Declare `depends_on` for both `ollama` and `chromadb`. Map host port `7860` to
   container port `7860`.
4. Define the named volumes `ollama_data` and `chroma_data` at the top level.

### Step 9 — Run with Docker Compose

```bash
docker compose up --build
```

Pull the Ollama models inside the running container (first run only):
```bash
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull nomic-embed-text
```

Open `http://localhost:7860`.

1. Add a PDF and a web URL in Tab 1. Verify the chunk counts.
2. In Tab 2, ask a question with "(All documents)" — observe `MultiQueryRetriever`
   logging.
3. Switch the filter dropdown to the PDF. Ask the same question — verify only chunks
   from that document appear in sources.
4. In Tab 3, delete the PDF. Refresh both dropdowns. Confirm it no longer appears.
5. Stop and restart `docker compose` — verify the index is still intact (volume
   persistence).

---

## Expected Outcome

- [ ] Adding a PDF, TXT, MD file, or web URL succeeds and displays chunk count.
- [ ] The Q&A tab answers questions using `MultiQueryRetriever` (check logs for
      `"Generated queries:"` output).
- [ ] Filtering by a specific document restricts source chunks to that document.
- [ ] Deleting a document in the Manage tab removes it from both dropdowns and from
      retrieval results.
- [ ] Stats panel shows correct document count, chunk count, and query count.
- [ ] Restarting Docker Compose preserves the indexed documents (volume mount works).
- [ ] `docker compose up --build` starts all three services without errors.
- [ ] Health checks pass for all services (`docker compose ps` shows `healthy`).

---

## Hints

- ChromaDB's `HttpClient` requires the `chromadb` package. The `Chroma` LangChain
  class accepts a `client=` parameter to use an external client instead of its own
  embedded one.
- `vectorstore.get()` returns a dict with keys `"ids"`, `"documents"`, `"metadatas"`,
  `"embeddings"`. You only need `"metadatas"` to list document names — pass
  `include=["metadatas"]` to avoid fetching embeddings.
- `MultiQueryRetriever` makes an LLM call per question to generate alternative
  phrasings. This adds latency (~2–5 seconds). Consider showing a loading indicator
  in the UI while the chain runs.
- `WebBaseLoader` requires `beautifulsoup4` and `lxml` to parse HTML. Include both in
  `requirements.txt`.
- When `filter_metadata` is applied, Chroma uses MongoDB-style operators. The simple
  equality filter `{"doc_name": "myfile.pdf"}` is sufficient — no `$eq` wrapper
  needed for exact string matches in the current Chroma version.
- The `ollama/ollama:0.4.7` image does not pre-pull any models. You must run
  `ollama pull` inside the container after the service starts, or add an `entrypoint`
  script that pulls required models automatically on startup.
- Use `gr.Dropdown(choices=..., value="(All documents)")` and set `interactive=True`
  so users can update the selection without submitting the form.
- To refresh both Tab 2 and Tab 3 dropdowns from a single button click, have the
  "Refresh" button return two `gr.Dropdown.update(choices=...)` values connected to
  both components.
