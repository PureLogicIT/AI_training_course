"""
Exercise 3 — Multi-Index Routing Assistant with LlamaIndex RouterQueryEngine
=============================================================================
SOLUTION: fully implemented version.

Architecture:
  - Facts Index:     VectorStoreIndex, small chunks (256 tokens), ChromaDB backed
  - Summaries Index: SummaryIndex, large chunks (1024 tokens), in-memory
  - RouterQueryEngine with LLMSingleSelector routes queries to the right index
  - Optional SentenceTransformerRerank post-processor on the Facts Index
  - Metadata filtering support on the Facts Index

Run:
    pip install -r requirements.txt
    python app.py
"""

import io
import os
import sys

import chromadb
import gradio as gr
from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    SummaryIndex,
    VectorStoreIndex,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector
from llama_index.core.tools import QueryEngineTool
from llama_index.core.vector_stores import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.postprocessor.sentence_transformer_rerank import SentenceTransformerRerank
from llama_index.vector_stores.chroma import ChromaVectorStore

# ── Constants ──────────────────────────────────────────────────────────────────
CHROMA_PATH = "./chroma_router"
FACTS_COLLECTION = "facts_index"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = "llama3.2"
EMBED_MODEL = "nomic-embed-text"

FACTS_CHUNK_SIZE = 256
FACTS_CHUNK_OVERLAP = 25
SUMMARY_CHUNK_SIZE = 1024
SUMMARY_CHUNK_OVERLAP = 100

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-2-v2"

# Module-level state
_facts_index = None
_summaries_index = None
_router_engine = None
_reranker_enabled = False


# ── Configure Settings ─────────────────────────────────────────────────────────

def configure_settings() -> None:
    """Configure the global LlamaIndex Settings singleton."""
    Settings.llm = Ollama(
        model=LLM_MODEL,
        base_url=OLLAMA_BASE_URL,
        request_timeout=180.0,
        context_window=8192,
    )
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )
    # Facts Index default — small chunks for precise retrieval
    Settings.chunk_size = FACTS_CHUNK_SIZE
    Settings.chunk_overlap = FACTS_CHUNK_OVERLAP


# ── ChromaDB helpers ──────────────────────────────────────────────────────────

def get_facts_chroma_components() -> tuple:
    """Return (vector_store, collection, storage_context) for the Facts Index."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(FACTS_COLLECTION)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return vector_store, collection, storage_context


# ── Build Facts Index ─────────────────────────────────────────────────────────

def build_facts_index(files, category_tag: str) -> str:
    """Build or extend the Facts Index (VectorStoreIndex, small chunks, ChromaDB)."""
    global _facts_index, _router_engine

    if not files:
        return "Please upload at least one file for the Facts Index."

    file_paths = [f.name for f in files]

    try:
        documents = SimpleDirectoryReader(input_files=file_paths).load_data()
    except Exception as exc:
        return f"Error loading documents: {exc}"

    if not documents:
        return "No content extracted from uploaded files."

    # Inject category metadata for later filtering
    tag = (category_tag or "general").strip()
    for doc in documents:
        doc.metadata["category"] = tag

    vector_store, collection, storage_context = get_facts_chroma_components()

    _facts_index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )

    _router_engine = None  # invalidate cached router
    count = collection.count()
    return (
        f"Facts Index built. {len(documents)} document(s) indexed with "
        f"category='{tag}'. Collection now has {count} vectors."
    )


# ── Build Summaries Index ─────────────────────────────────────────────────────

def build_summaries_index(files) -> str:
    """Build the Summaries Index (SummaryIndex, large chunks, in-memory)."""
    global _summaries_index, _router_engine

    if not files:
        return "Please upload at least one file for the Summaries Index."

    file_paths = [f.name for f in files]

    try:
        documents = SimpleDirectoryReader(input_files=file_paths).load_data()
    except Exception as exc:
        return f"Error loading documents: {exc}"

    if not documents:
        return "No content extracted from uploaded files."

    # Use large chunks — the SummaryIndex sends all nodes to the LLM for synthesis
    splitter = SentenceSplitter(
        chunk_size=SUMMARY_CHUNK_SIZE,
        chunk_overlap=SUMMARY_CHUNK_OVERLAP,
    )
    nodes = splitter.get_nodes_from_documents(documents)

    # SummaryIndex takes a node list directly; no vector store needed
    _summaries_index = SummaryIndex(nodes)

    _router_engine = None  # invalidate cached router
    return (
        f"Summaries Index built. {len(documents)} document(s) split into "
        f"{len(nodes)} large-chunk nodes ({SUMMARY_CHUNK_SIZE} tokens each)."
    )


# ── Build Router Engine ───────────────────────────────────────────────────────

def build_router_engine(use_reranker: bool) -> tuple:
    """Assemble the RouterQueryEngine from the two indexes."""
    global _router_engine, _reranker_enabled

    if _facts_index is None:
        return (None, "Error: Facts Index is not built. Go to the Ingest tab first.")
    if _summaries_index is None:
        return (None, "Error: Summaries Index is not built. Go to the Ingest tab first.")

    # Facts query engine — optionally with re-ranker
    if use_reranker:
        reranker = SentenceTransformerRerank(
            model=RERANKER_MODEL,
            top_n=3,
        )
        facts_qe = _facts_index.as_query_engine(
            similarity_top_k=6,
            response_mode="compact",
            node_postprocessors=[reranker],
        )
        reranker_status = "enabled"
    else:
        facts_qe = _facts_index.as_query_engine(
            similarity_top_k=6,
            response_mode="compact",
        )
        reranker_status = "disabled"

    # Summaries query engine — tree_summarize for broad reasoning
    summary_qe = _summaries_index.as_query_engine(
        response_mode="tree_summarize",
    )

    # Tool descriptions are the router's only signal — write them precisely
    facts_tool = QueryEngineTool.from_defaults(
        query_engine=facts_qe,
        name="facts_index",
        description=(
            "Use for specific factual questions about named concepts, procedures, "
            "definitions, or details mentioned in the documents. "
            "Examples: 'What is X?', 'How does Y work?', 'What are the steps for Z?', "
            "'What does the configuration file contain?'"
        ),
    )

    summary_tool = QueryEngineTool.from_defaults(
        query_engine=summary_qe,
        name="summaries_index",
        description=(
            "Use for broad questions requiring a high-level overview or synthesis "
            "across many documents. "
            "Examples: 'Summarise everything', 'What are the main themes?', "
            "'Give me an overview of the key points', 'What topics are covered?'"
        ),
    )

    _router_engine = RouterQueryEngine(
        selector=LLMSingleSelector.from_defaults(),
        query_engine_tools=[facts_tool, summary_tool],
        verbose=True,
    )
    _reranker_enabled = use_reranker

    return (_router_engine, f"Router engine ready. Re-ranker: {reranker_status}.")


# ── Query through the router ──────────────────────────────────────────────────

def query_with_routing(question: str, category_filter: str) -> tuple:
    """
    Run a question through the router and capture the routing decision.

    If category_filter is set, bypass the router and query the Facts Index directly
    with a MetadataFilter applied.
    """
    if not question or not question.strip():
        return ("Please enter a question.", "")

    if _router_engine is None:
        return ("Router engine not built. Go to the Ingest tab and click 'Build Router Engine'.", "")

    question = question.strip()

    # Metadata-filtered path: bypass router, use Facts Index directly
    if category_filter and category_filter.strip():
        if _facts_index is None:
            return ("Facts Index not available.", "")

        cat = category_filter.strip()
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="category",
                    value=cat,
                    operator=FilterOperator.EQ,
                )
            ]
        )
        filtered_qe = _facts_index.as_query_engine(
            similarity_top_k=4,
            response_mode="compact",
            filters=filters,
        )
        try:
            response = filtered_qe.query(question)
        except Exception as exc:
            return (f"Query error: {exc}", "")

        routing_note = (
            f"Metadata filter active (category='{cat}').\n"
            "Router bypassed — Facts Index queried directly with filter."
        )
        return (str(response), routing_note)

    # Normal router path — capture verbose stdout to show routing decision
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        response = _router_engine.query(question)
    except Exception as exc:
        sys.stdout = old_stdout
        return (f"Query error: {exc}", "")
    finally:
        sys.stdout = old_stdout

    routing_text = buf.getvalue().strip() or "No routing output captured."
    return (str(response), routing_text)


# ── Compare all three paths ───────────────────────────────────────────────────

def compare_indexes(question: str) -> tuple:
    """Answer the same question via Facts Index, Summaries Index, and Router."""
    if not question or not question.strip():
        return ("Enter a question first.", "", "", "")

    missing = []
    if _facts_index is None:
        missing.append("Facts Index")
    if _summaries_index is None:
        missing.append("Summaries Index")
    if _router_engine is None:
        missing.append("Router Engine")

    if missing:
        msg = f"Not ready: {', '.join(missing)}. Build them in the Ingest tab first."
        return (msg, msg, msg, "")

    question = question.strip()

    # Query Facts Index directly
    try:
        facts_qe = _facts_index.as_query_engine(
            similarity_top_k=4,
            response_mode="compact",
        )
        facts_answer = str(facts_qe.query(question))
    except Exception as exc:
        facts_answer = f"Error: {exc}"

    # Query Summaries Index directly
    try:
        summary_qe = _summaries_index.as_query_engine(
            response_mode="tree_summarize",
        )
        summaries_answer = str(summary_qe.query(question))
    except Exception as exc:
        summaries_answer = f"Error: {exc}"

    # Query Router — capture routing decision
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        router_response = _router_engine.query(question)
        router_answer = str(router_response)
    except Exception as exc:
        router_answer = f"Error: {exc}"
    finally:
        sys.stdout = old_stdout

    routing_decision = buf.getvalue().strip() or "No routing output captured."
    return (facts_answer, summaries_answer, router_answer, routing_decision)


# ── Configuration display ─────────────────────────────────────────────────────

def get_config_text() -> str:
    """Return a markdown string describing current runtime configuration."""
    facts_status = "Not built"
    if _facts_index is not None:
        try:
            _, collection, _ = get_facts_chroma_components()
            facts_status = f"Loaded ({collection.count()} vectors in ChromaDB)"
        except Exception:
            facts_status = "Loaded (vector count unavailable)"

    summary_status = "Not built" if _summaries_index is None else "Loaded (in-memory)"
    router_status = "Not built" if _router_engine is None else "Ready"
    reranker_status = "Enabled" if _reranker_enabled else "Disabled"

    return f"""## Current Configuration

| Setting | Value |
|---|---|
| Ollama URL | `{OLLAMA_BASE_URL}` |
| LLM Model | `{LLM_MODEL}` |
| Embedding Model | `{EMBED_MODEL}` |
| Facts Index chunk size | `{FACTS_CHUNK_SIZE}` tokens |
| Facts Index chunk overlap | `{FACTS_CHUNK_OVERLAP}` tokens |
| Summaries Index chunk size | `{SUMMARY_CHUNK_SIZE}` tokens |
| Summaries Index chunk overlap | `{SUMMARY_CHUNK_OVERLAP}` tokens |
| Re-ranker model | `{RERANKER_MODEL}` |
| Re-ranker status | {reranker_status} |

## Index Status

| Index | Status |
|---|---|
| Facts Index | {facts_status} |
| Summaries Index | {summary_status} |
| Router Engine | {router_status} |
"""


# ── Build the Gradio UI ───────────────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    with gr.Blocks(title="LlamaIndex Router Assistant") as demo:
        gr.Markdown(
            "# LlamaIndex Multi-Index Routing Assistant\n"
            "Maintain two indexes with different strategies and let the router choose the right one."
        )

        with gr.Tabs():

            # ── Tab 1: Ingest ─────────────────────────────────────────────────
            with gr.Tab("Ingest Documents"):
                gr.Markdown(
                    "Build the Facts Index and Summaries Index separately, "
                    "then assemble the Router Engine."
                )

                with gr.Row():
                    with gr.Column():
                        gr.Markdown(
                            "#### Facts Index\n"
                            "VectorStoreIndex — small 256-token chunks, ChromaDB persistent.\n"
                            "Best for specific factual questions."
                        )
                        facts_files = gr.File(
                            label="Upload files (.txt, .md, .pdf)",
                            file_count="multiple",
                            file_types=[".txt", ".md", ".pdf"],
                        )
                        category_tag = gr.Textbox(
                            label="Category tag (injected into metadata)",
                            value="general",
                            placeholder="e.g. technical, legal, reference",
                        )
                        facts_btn = gr.Button("Build Facts Index", variant="primary")
                        facts_status = gr.Textbox(
                            label="Facts Index Status",
                            interactive=False,
                            lines=2,
                        )

                    with gr.Column():
                        gr.Markdown(
                            "#### Summaries Index\n"
                            "SummaryIndex — large 1024-token chunks, in-memory.\n"
                            "Best for broad overview questions."
                        )
                        summary_files = gr.File(
                            label="Upload files (.txt, .md, .pdf)",
                            file_count="multiple",
                            file_types=[".txt", ".md", ".pdf"],
                        )
                        summary_btn = gr.Button("Build Summaries Index", variant="primary")
                        summary_status = gr.Textbox(
                            label="Summaries Index Status",
                            interactive=False,
                            lines=2,
                        )

                gr.Markdown("---")
                with gr.Row():
                    use_reranker = gr.Checkbox(
                        label="Enable Re-ranker (SentenceTransformerRerank — downloads ~85 MB on first use)",
                        value=False,
                    )
                    router_btn = gr.Button("Build Router Engine", variant="primary")
                    router_status = gr.Textbox(
                        label="Router Status",
                        interactive=False,
                        lines=2,
                    )

                # Wire ingestion buttons
                facts_btn.click(
                    fn=build_facts_index,
                    inputs=[facts_files, category_tag],
                    outputs=[facts_status],
                )

                summary_btn.click(
                    fn=build_summaries_index,
                    inputs=[summary_files],
                    outputs=[summary_status],
                )

                router_btn.click(
                    fn=lambda use_r: build_router_engine(use_r)[1],
                    inputs=[use_reranker],
                    outputs=[router_status],
                )

            # ── Tab 2: Query Router ───────────────────────────────────────────
            with gr.Tab("Query Router"):
                gr.Markdown(
                    "### Ask the Router\n"
                    "The `LLMSingleSelector` reads your question and the tool descriptions "
                    "to decide which index to use. The routing decision appears below the answer."
                )

                q2 = gr.Textbox(
                    label="Question",
                    placeholder="Ask a specific question or a broad overview question...",
                    lines=2,
                )
                cat_filter = gr.Textbox(
                    label="Metadata Filter — category tag (leave blank to use the router)",
                    placeholder="e.g. technical  (must match the tag used during ingestion)",
                )
                ask_btn = gr.Button("Ask Router", variant="primary")

                answer_box2 = gr.Textbox(
                    label="Answer",
                    interactive=False,
                    lines=8,
                )
                routing_box = gr.Textbox(
                    label="Routing Decision (which index was selected and why)",
                    interactive=False,
                    lines=6,
                )

                ask_btn.click(
                    fn=query_with_routing,
                    inputs=[q2, cat_filter],
                    outputs=[answer_box2, routing_box],
                )

                q2.submit(
                    fn=query_with_routing,
                    inputs=[q2, cat_filter],
                    outputs=[answer_box2, routing_box],
                )

            # ── Tab 3: Compare Indexes ────────────────────────────────────────
            with gr.Tab("Compare Indexes"):
                gr.Markdown(
                    "### Side-by-Side Comparison\n"
                    "The same question is answered by all three paths: Facts Index directly, "
                    "Summaries Index directly, and via the Router. "
                    "Use this to verify that the router is choosing the right index."
                )

                q3 = gr.Textbox(
                    label="Question",
                    placeholder="Ask a question — try both specific and broad questions...",
                    lines=2,
                )
                compare_btn = gr.Button("Compare All Three Paths", variant="primary")

                with gr.Row():
                    facts_answer_box = gr.Textbox(
                        label="Facts Index (direct)",
                        interactive=False,
                        lines=10,
                    )
                    summary_answer_box = gr.Textbox(
                        label="Summaries Index (direct)",
                        interactive=False,
                        lines=10,
                    )
                    router_answer_box = gr.Textbox(
                        label="Router (auto-selected)",
                        interactive=False,
                        lines=10,
                    )

                routing_box3 = gr.Textbox(
                    label="Router's Routing Decision",
                    interactive=False,
                    lines=4,
                )

                compare_btn.click(
                    fn=compare_indexes,
                    inputs=[q3],
                    outputs=[facts_answer_box, summary_answer_box, router_answer_box, routing_box3],
                )

            # ── Tab 4: Configuration ──────────────────────────────────────────
            with gr.Tab("Configuration"):
                config_md = gr.Markdown(get_config_text())
                refresh_btn = gr.Button("Refresh Configuration")
                refresh_btn.click(
                    fn=get_config_text,
                    inputs=[],
                    outputs=[config_md],
                )

    return demo


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    configure_settings()

    # Attempt to load any existing Facts Index from ChromaDB
    try:
        vector_store, collection, storage_context = get_facts_chroma_components()
        if collection.count() > 0:
            _facts_index = VectorStoreIndex.from_vector_store(
                vector_store,
                storage_context=storage_context,
            )
            print(f"Loaded existing Facts Index from ChromaDB ({collection.count()} vectors).")
        else:
            print("No existing Facts Index found. Build one via the Ingest tab.")
    except Exception as exc:
        print(f"Could not load existing Facts Index: {exc}")

    print("Note: Summaries Index is in-memory and must be rebuilt each session.")

    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860)
