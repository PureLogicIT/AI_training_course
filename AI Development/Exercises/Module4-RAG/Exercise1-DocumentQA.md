# Exercise 1: Local Document Q&A with Gradio + Chroma

> Module: Module4-RAG | Difficulty: Beginner | Estimated Time: 60–90 minutes

## Scenario

You work on a small engineering team that maintains a growing collection of internal
text and markdown documents — runbooks, architecture notes, on-call guides. New team
members spend hours digging through files to answer simple questions.

Your task is to build a Gradio web app that lets anyone upload those documents through
a browser, index them locally with Chroma and `nomic-embed-text` (via Ollama), then
ask natural-language questions and receive grounded answers. Crucially, the retrieved
source chunks must be shown alongside the answer so team members can verify the
information themselves.

The entire system runs locally — no cloud API calls, no data leaves the machine.

---

## Learning Objectives

By completing this exercise you will be able to:

1. Receive uploaded files from a Gradio `gr.File` component and save them to a
   temporary working directory.
2. Load `.txt` and `.md` files with `TextLoader` and chunk them with
   `RecursiveCharacterTextSplitter`.
3. Build an in-session Chroma vector store with `OllamaEmbeddings` (`nomic-embed-text`).
4. Assemble a `create_retrieval_chain` RAG chain backed by a `ChatOllama` LLM.
5. Return both the generated answer and the retrieved source chunks to the Gradio UI.
6. Containerise the app with a production-quality Dockerfile (non-root user, health check).

---

## Prerequisites

- Ollama running locally with `nomic-embed-text` and `llama3.2` pulled:
  ```bash
  ollama pull nomic-embed-text
  ollama pull llama3.2
  ```
- Python 3.11 with a virtual environment activated.
- Docker Desktop (for the bonus containerisation step).

---

## Project Structure

```
Exercise1-DocumentQA/
├── app.py              # Main Gradio application  <-- you edit this
├── rag_engine.py       # Indexing and RAG chain logic  <-- you edit this
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Instructions

### Step 1 — Implement `index_documents()` in `rag_engine.py`

Open `rag_engine.py`. The function `index_documents(file_paths)` receives a list of
file paths (strings) for the uploaded files. You must:

1. Load each file with `TextLoader` (set `encoding="utf-8"`). Collect all loaded
   `Document` objects into a single list.
2. Split the documents with `RecursiveCharacterTextSplitter` using
   `chunk_size=500` and `chunk_overlap=50`.
3. Create an `OllamaEmbeddings` instance with `model="nomic-embed-text"`.
4. Build an **in-memory** Chroma vector store from the chunks using
   `Chroma.from_documents()`. Do **not** set `persist_directory` — this index lives
   only for the current session.
5. Return the `Chroma` vectorstore object.

Hint: If a file cannot be loaded (e.g., encoding error), catch the exception, print
a warning, and skip that file rather than crashing.

### Step 2 — Implement `build_rag_chain()` in `rag_engine.py`

The function `build_rag_chain(vectorstore)` receives the Chroma store you just built.
You must:

1. Create a `ChatOllama` LLM with `model="llama3.2"`, `temperature=0.0`, and
   `num_ctx=8192`.
2. Create a retriever from the vector store using MMR search (`search_type="mmr"`)
   with `k=4` and `fetch_k=15`.
3. Write a `ChatPromptTemplate` with a system message that instructs the model to
   answer using only the provided context and to say "I don't have information about
   that in the uploaded documents." when the answer is not present.
4. Build the chain using `create_stuff_documents_chain` and `create_retrieval_chain`.
5. Return the chain.

### Step 3 — Implement `ask_question()` in `rag_engine.py`

The function `ask_question(rag_chain, question)` runs a single question through the
chain. You must:

1. Call `rag_chain.invoke({"input": question})`.
2. Extract the `"answer"` string from the result dict.
3. Extract the source chunk list from `result["context"]`.
4. Return a tuple `(answer, source_chunks)` where `source_chunks` is the list of
   `Document` objects.

### Step 4 — Wire up the Gradio UI in `app.py`

Open `app.py`. You must implement the two callback functions:

**`handle_upload(files)`**
- Receives the list of uploaded file paths from Gradio.
- Calls `index_documents(file_paths)` from `rag_engine`.
- Stores the resulting vectorstore and rag_chain in the module-level state variables
  (`_vectorstore`, `_rag_chain`).
- Returns a status string such as `"Indexed 3 file(s) — 47 chunks stored."`.

Hint: Count the total chunks with `vectorstore._collection.count()`.

**`handle_question(question)`**
- Guards against an empty question or no index loaded yet (return a helpful message
  in both cases).
- Calls `ask_question(_rag_chain, question)`.
- Formats the answer as a plain string.
- Formats the sources panel: for each source `Document`, output its `source` metadata
  and the first 300 characters of its `page_content`.
- Returns `(answer_text, sources_text)` as two strings for the two Gradio `Textbox`
  outputs.

### Step 5 — Run and verify

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:7860` in your browser.

1. Upload two or three `.txt` or `.md` files using the file picker.
2. Confirm the status message shows the chunk count.
3. Ask a question whose answer is present in one of your files.
4. Confirm the answer is grounded and the sources panel shows the relevant chunks.
5. Ask a question that is NOT in any file. Confirm the model says it does not have
   that information rather than hallucinating.

### Step 6 (Bonus) — Docker

Build and run the containerised app:

```bash
docker build -t doc-qa:1.0 .
docker run --rm -p 7860:7860 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  doc-qa:1.0
```

Verify `http://localhost:7860` still works and file uploads function correctly inside
the container.

---

## Expected Outcome

- [ ] Uploading `.txt` / `.md` files displays a status message that includes the number
      of chunks indexed (e.g., `"Indexed 2 file(s) — 31 chunks stored."`).
- [ ] Asking a question whose answer is in the uploaded documents returns a relevant,
      grounded answer.
- [ ] The "Sources" panel shows at minimum the file name and a content excerpt for each
      retrieved chunk.
- [ ] Asking a question not covered by the documents returns the configured "I don't
      have information" phrase rather than a fabricated answer.
- [ ] `python app.py` starts without errors and the Gradio interface loads at
      `http://localhost:7860`.
- [ ] (Bonus) `docker build` completes without errors and the container serves the app.

---

## Hints

- `TextLoader` raises `UnicodeDecodeError` on binary files. Wrap each load in
  `try/except` so one bad file does not abort the whole upload.
- `Chroma.from_documents()` without `persist_directory` creates an in-memory
  collection that is automatically cleared when the process restarts. For this
  exercise that is intentional — each upload session starts fresh.
- `gr.File(file_count="multiple", file_types=[".txt", ".md"])` restricts the picker
  to the correct file types and allows multi-select.
- MMR retrieval (`search_type="mmr"`) reduces redundancy when the uploaded files
  contain repeated or near-duplicate sections.
- Set `OLLAMA_BASE_URL` as an environment variable and pass it to `OllamaEmbeddings`
  and `ChatOllama` via the `base_url` parameter — this is what makes the Docker image
  point to the host Ollama server.
