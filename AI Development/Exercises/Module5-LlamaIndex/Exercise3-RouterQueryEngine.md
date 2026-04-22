# Exercise 3: Multi-Index Routing Assistant with LlamaIndex RouterQueryEngine

> **Subject:** AI Development | **Module:** Module 5 — LlamaIndex | **Difficulty:** Hard | **Estimated Time:** 150–210 minutes

---

## Overview

The module showed you how `RouterQueryEngine` with `LLMSingleSelector` can intelligently direct queries to either a `VectorStoreIndex` (precise semantic lookup) or a `SummaryIndex` (broad corpus reasoning). In this exercise you will build a Gradio application that makes the routing mechanism fully visible and interactive, and adds metadata filtering and optional re-ranking on top.

Your app maintains **two independent indexes**:

- **Facts Index** — a `VectorStoreIndex` with small chunks (256 tokens) and high recall, designed for precise factual questions
- **Summaries Index** — a `SummaryIndex` with large chunks (1024 tokens), designed for broad questions that require reasoning across an entire document set

A `RouterQueryEngine` with `LLMSingleSelector` automatically selects which index answers each query. The app reveals the routing decision in a dedicated panel and supports a side-by-side mode where the same query is answered by each index separately **and** by the router, so you can evaluate whether the router chose correctly.

---

## Learning Objectives

By the end of this exercise you will be able to:

- Build two independent LlamaIndex indexes from the same or different document sets with different chunking strategies
- Construct a `RouterQueryEngine` with `LLMSingleSelector` and descriptive `QueryEngineTool` wrappers
- Parse the router's selection output to extract which index was chosen and the reasoning given
- Apply `MetadataFilters` to scope retrieval within the Facts index to a specific document category
- Attach `SentenceTransformerRerank` as a post-processor and toggle it on/off at query time
- Organise a multi-tab Gradio application for ingestion, querying, comparison, and configuration

---

## Prerequisites

- Ollama running locally with `llama3.2` and `nomic-embed-text` pulled
- Python 3.10 or later with a virtual environment active
- Completed Exercises 1 and 2, or strong familiarity with `VectorStoreIndex`, `StorageContext`, and ChromaDB from Module 5
- At least 8 GB of RAM (the re-ranker model downloads ~85 MB on first use)

---

## Instructions

### Step 1 — Configure Settings with two chunk-size profiles

In `app.py`, implement `configure_settings()`:
- Set `Settings.llm` to `Ollama(model="llama3.2", request_timeout=180.0, context_window=8192)`.
- Set `Settings.embed_model` to `OllamaEmbedding(model_name="nomic-embed-text")`.
- Set `Settings.chunk_size = 256` and `Settings.chunk_overlap = 25` — the Facts index uses this default.

Note: the Summaries index overrides `chunk_size` locally (1024 tokens) by passing a custom `SentenceSplitter` when building the `SummaryIndex`. You will implement that override in Step 2.

### Step 2 — Implement `build_facts_index(file_paths, category_tag)`

The Facts index is a `VectorStoreIndex` backed by ChromaDB collection `"facts_index"`:

1. Load documents from `file_paths` with `SimpleDirectoryReader(input_files=file_paths).load_data()`.
2. Inject a `"category"` metadata key into every document's `metadata` dict using the `category_tag` string passed from the UI. This enables metadata filtering later.
3. Set up ChromaDB with `CHROMA_PATH` and collection name `"facts_index"`.
4. Index with `VectorStoreIndex.from_documents(documents, storage_context=storage_context, show_progress=True)`.
5. Store the index in module-level `_facts_index`.
6. Return a status string including document count and vector count.

### Step 3 — Implement `build_summaries_index(file_paths)`

The Summaries index is a `SummaryIndex` (not `VectorStoreIndex`):

1. Load documents from `file_paths`.
2. Apply a `SentenceSplitter(chunk_size=1024, chunk_overlap=100)` explicitly by calling `splitter.get_nodes_from_documents(documents)` to produce large-chunk nodes.
3. Build `SummaryIndex(nodes)` directly from the node list (not `from_documents`).
4. Store in module-level `_summaries_index`.
5. Return a status string.

Note: `SummaryIndex` does not use a vector store — it stores nodes in memory. It will not persist across restarts. This is intentional and demonstrates the trade-off: the Facts index survives restarts via ChromaDB, the Summaries index must be rebuilt each session.

### Step 4 — Implement `build_router_engine(use_reranker)`

This function assembles the `RouterQueryEngine`:

1. Retrieve `_facts_index` and `_summaries_index`. If either is `None`, return `None` and an error message.
2. Build the facts query engine:
   - `_facts_index.as_query_engine(similarity_top_k=6, response_mode="compact")`
   - If `use_reranker` is `True`, attach `SentenceTransformerRerank(model="cross-encoder/ms-marco-MiniLM-L-2-v2", top_n=3)` via the `node_postprocessors` parameter.
3. Build the summaries query engine:
   - `_summaries_index.as_query_engine(response_mode="tree_summarize")`
4. Wrap each engine in a `QueryEngineTool.from_defaults()` with a precise description string. The description is what `LLMSingleSelector` reads — write it carefully:
   - Facts tool: `"Use this for specific factual questions about named concepts, procedures, definitions, or details mentioned in the documents. Examples: 'What is X?', 'How does Y work?', 'What are the steps for Z?'"`
   - Summaries tool: `"Use this for broad questions requiring a high-level overview or synthesis across many documents. Examples: 'Summarise everything', 'What are the main themes?', 'Give me an overview.'"`
5. Create `RouterQueryEngine(selector=LLMSingleSelector.from_defaults(), query_engine_tools=[facts_tool, summaries_tool], verbose=True)`.
6. Store in module-level `_router_engine` and return `(_router_engine, "Router engine ready.")`.

### Step 5 — Implement `query_with_routing(question, category_filter, use_reranker)`

This function runs a query through the router and extracts the routing decision:

1. Ensure `_router_engine` is built (call `build_router_engine` if needed).
2. Apply a `MetadataFilters` object if `category_filter` is non-empty:
   - `MetadataFilter(key="category", value=category_filter, operator=FilterOperator.EQ)`
   - Pass this filter when rebuilding the facts query engine (you will need to rebuild the router engine to apply the filter, or apply filters at retriever level).

   A simpler approach: before calling the router, check if a filter is active. If yes, bypass the router and use the facts query engine directly with the filter applied. Clearly indicate in the routing panel that "Metadata filter active — Facts Index used directly."

3. Call `router_engine.query(question)`.
4. Capture the standard output of the router call (it prints the selection reason when `verbose=True`). Use `io.StringIO` and redirect `sys.stdout` during the query call to capture the routing decision text.
5. Return `(answer_text, routing_decision_text)`.

### Step 6 — Implement `compare_indexes(question)`

This function answers the same question with all three paths and returns three answers:

1. Answer 1: Facts index directly — `_facts_index.as_query_engine(similarity_top_k=4, response_mode="compact").query(question)`
2. Answer 2: Summaries index directly — `_summaries_index.as_query_engine(response_mode="tree_summarize").query(question)`
3. Answer 3: Router engine — `_router_engine.query(question)` plus captured routing decision

Return `(facts_answer, summaries_answer, router_answer, routing_decision)`.

### Step 7 — Build the Gradio UI with four tabs

Create a `gr.Blocks()` app with `gr.Tabs()`:

**Tab 1 — "Ingest Documents":**
- Two sub-sections side by side or stacked:
  - Facts Index section: `gr.File` (multiple), a `gr.Textbox` for `category_tag` (default `"general"`), "Build Facts Index" button, status textbox
  - Summaries Index section: `gr.File` (multiple), "Build Summaries Index" button, status textbox
- A "Build Router Engine" button with a `gr.Checkbox` for "Enable Re-ranker", and a status textbox showing router build result

**Tab 2 — "Query Router":**
- `gr.Textbox` for question input
- `gr.Textbox` for category filter (leave blank to disable), label "Metadata Filter (category tag, optional)"
- "Ask Router" button
- `gr.Textbox` for answer, `lines=8`
- `gr.Textbox` for routing decision panel, `lines=6`, label "Routing Decision (which index and why)"

**Tab 3 — "Compare Indexes":**
- `gr.Textbox` for question
- "Compare All" button
- Three `gr.Textbox` outputs side by side (or stacked): "Facts Index Answer", "Summaries Index Answer", "Router Answer"
- `gr.Textbox` for routing decision

**Tab 4 — "Configuration":**
- Display current settings as a `gr.Markdown` block: Ollama URL, LLM model, embedding model, chunk sizes for both indexes, re-ranker status
- A `gr.Button` "Rebuild Router (toggle re-ranker)" that rebuilds the router engine with the opposite re-ranker setting

### Step 8 — Run with docker-compose

The starter includes a `docker-compose.yml` that starts the Gradio app and an Ollama container together. Verify you can start the stack with:

```bash
cd "AI Development/Projects/Starters/Exercise3-RouterQueryEngine"
docker-compose up --build
```

The app should be accessible at `http://localhost:7860` and Ollama at `http://localhost:11434`.

---

## Expected Outcome

- [ ] The app starts and all four tabs are visible at `http://127.0.0.1:7860`
- [ ] Uploading files to the Facts Index tab with a category tag of `"technical"` and clicking "Build Facts Index" shows a success status
- [ ] Uploading the same or different files to the Summaries Index tab works independently
- [ ] Clicking "Build Router Engine" (with re-ranker off) shows "Router engine ready."
- [ ] A specific factual question (e.g. "What does the chunk_overlap parameter do?") routes to the Facts Index and the routing panel shows the selection and reason
- [ ] A broad question (e.g. "Give me a summary of all the documents") routes to the Summaries Index
- [ ] The Compare tab shows three distinct answers for the same question
- [ ] Enabling the re-ranker and rebuilding the router does not break querying
- [ ] Entering a category filter of `"technical"` and asking a question returns results only from nodes with that category metadata tag
- [ ] The Dockerfile builds with `docker build -t router-assistant .`
- [ ] `docker-compose up --build` starts both services without error

---

## Hints

- `SummaryIndex` is imported from `llama_index.core` as `from llama_index.core import SummaryIndex`. It does not take a `storage_context` with a vector store — it is purely list-based.
- Capturing the routing decision from `verbose=True` output requires redirecting stdout during the `.query()` call. Use a context manager:
  ```python
  import sys, io
  buf = io.StringIO()
  old_stdout = sys.stdout
  sys.stdout = buf
  response = router_engine.query(question)
  sys.stdout = old_stdout
  routing_text = buf.getvalue()
  ```
- `SentenceTransformerRerank` is from `llama_index.postprocessor.sentence_transformer_rerank`. Its first run downloads the cross-encoder model — expect a 30-60 second delay. Subsequent runs use the cached model.
- For metadata filtering on the Facts Index, apply the filter when building the query engine inside `build_router_engine()`: `index.as_query_engine(similarity_top_k=6, filters=MetadataFilters(...))`. However, since the filter comes from the UI at query time, you need to rebuild the router engine (or the facts tool) each time the filter changes. A simpler approach is to bypass the router for filtered queries and call the facts retriever directly.
- The `LLMSingleSelector` calls `Settings.llm` to decide routing — this is a separate LLM call that adds latency. On slow hardware, expect 10–20 seconds of routing overhead before the actual retrieval begins.
- Docker compose: the Gradio app should wait for Ollama to be healthy before starting. Use `depends_on` with a health check on the Ollama container.

---

## Bonus Challenges

1. Add `LLMMultiSelector` as an alternative selector mode (it can select multiple indexes simultaneously and merge answers). Wire a `gr.Radio` to switch between `LLMSingleSelector` and `LLMMultiSelector`.
2. Implement `SubQuestionQueryEngine` as a fourth comparison mode in the Compare tab, showing how complex multi-part questions are decomposed into sub-questions.
3. Add a query history log that persists to a local SQLite database, recording the question, which index was selected, the answer, and a user-provided rating (1–5 stars).
4. Extend the metadata filtering to support compound filters (AND/OR) with a dynamic `gr.Dataframe` where the user adds filter rows.
