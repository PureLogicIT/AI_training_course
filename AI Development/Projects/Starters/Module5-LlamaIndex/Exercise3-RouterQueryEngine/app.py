"""
Exercise 3 — Multi-Index Routing Assistant with LlamaIndex RouterQueryEngine
=============================================================================
Starter project: complete every section marked with TODO.

Architecture:
  - Facts Index:    VectorStoreIndex, small chunks (256 tokens), ChromaDB backed
  - Summaries Index: SummaryIndex, large chunks (1024 tokens), in-memory
  - RouterQueryEngine with LLMSingleSelector routes queries to the right index
  - Optional SentenceTransformerRerank post-processor on the Facts Index
  - Metadata filtering support on the Facts Index

Gradio UI — four tabs:
  Tab 1: Ingest Documents  (separate ingestion for each index)
  Tab 2: Query Router      (route + show routing decision)
  Tab 3: Compare Indexes   (same query answered by all three paths)
  Tab 4: Configuration     (current settings display)

Run:
    pip install -r requirements.txt
    python app.py
"""

import io
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
    FilterCondition,
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
OLLAMA_BASE_URL = "http://localhost:11434"
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


# ── Step 1: Configure Settings ────────────────────────────────────────────────

def configure_settings() -> None:
    """
    Configure the global LlamaIndex Settings singleton.

    TODO:
        1. Set Settings.llm = Ollama(model=LLM_MODEL, base_url=OLLAMA_BASE_URL,
                                     request_timeout=180.0, context_window=8192)
        2. Set Settings.embed_model = OllamaEmbedding(model_name=EMBED_MODEL,
                                                       base_url=OLLAMA_BASE_URL)
        3. Set Settings.chunk_size = FACTS_CHUNK_SIZE  (default for Facts Index)
        4. Set Settings.chunk_overlap = FACTS_CHUNK_OVERLAP
    """
    # TODO: configure Settings
    pass


# ── Step 2: ChromaDB helpers for Facts Index ──────────────────────────────────

def get_facts_chroma_components() -> tuple:
    """
    Create ChromaDB components for the Facts Index.

    Returns:
        (vector_store: ChromaVectorStore,
         collection: chromadb.Collection,
         storage_context: StorageContext)

    TODO:
        1. Create chromadb.PersistentClient(path=CHROMA_PATH)
        2. client.get_or_create_collection(FACTS_COLLECTION)
        3. ChromaVectorStore(chroma_collection=collection)
        4. StorageContext.from_defaults(vector_store=vector_store)
        5. Return (vector_store, collection, storage_context)
    """
    # TODO: implement
    return None, None, None


# ── Step 3: Build Facts Index ─────────────────────────────────────────────────

def build_facts_index(files, category_tag: str) -> str:
    """
    Build or extend the Facts Index (VectorStoreIndex, small chunks, ChromaDB).

    Args:
        files:        list of Gradio file objects
        category_tag: string tag injected into every document's metadata["category"]

    Returns:
        Status message string.

    TODO:
        1. Validate files is not None/empty
        2. Extract file_paths = [f.name for f in files]
        3. Load documents with SimpleDirectoryReader(input_files=file_paths).load_data()
        4. Inject category_tag into each document's metadata:
               for doc in documents:
                   doc.metadata["category"] = category_tag or "general"
        5. Get ChromaDB components with get_facts_chroma_components()
        6. Index with VectorStoreIndex.from_documents(documents,
               storage_context=storage_context, show_progress=True)
        7. Update _facts_index and reset _router_engine = None
        8. Return status string with doc count and collection vector count
    """
    global _facts_index, _router_engine

    # TODO: implement
    return "TODO: implement build_facts_index"


# ── Step 4: Build Summaries Index ─────────────────────────────────────────────

def build_summaries_index(files) -> str:
    """
    Build the Summaries Index (SummaryIndex, large chunks, in-memory).

    Args:
        files: list of Gradio file objects

    Returns:
        Status message string.

    TODO:
        1. Validate files is not None/empty
        2. Extract file_paths and load documents
        3. Parse documents into large nodes using:
               splitter = SentenceSplitter(
                   chunk_size=SUMMARY_CHUNK_SIZE,
                   chunk_overlap=SUMMARY_CHUNK_OVERLAP
               )
               nodes = splitter.get_nodes_from_documents(documents)
        4. Build: SummaryIndex(nodes)
           Note: SummaryIndex takes a list of nodes directly (not from_documents)
        5. Update _summaries_index and reset _router_engine = None
        6. Return status with doc count and node count
    """
    global _summaries_index, _router_engine

    # TODO: implement
    return "TODO: implement build_summaries_index"


# ── Step 5: Build Router Engine ───────────────────────────────────────────────

def build_router_engine(use_reranker: bool) -> tuple:
    """
    Assemble the RouterQueryEngine from the two indexes.

    Args:
        use_reranker: if True, attach SentenceTransformerRerank to the facts engine

    Returns:
        (router_engine or None, status_message: str)

    TODO:
        1. Check _facts_index and _summaries_index are not None
           If either is None, return (None, "Error: build both indexes first.")
        2. Build facts query engine:
               facts_qe = _facts_index.as_query_engine(
                   similarity_top_k=6, response_mode="compact")
           If use_reranker:
               reranker = SentenceTransformerRerank(
                   model=RERANKER_MODEL, top_n=3)
               facts_qe = _facts_index.as_query_engine(
                   similarity_top_k=6, response_mode="compact",
                   node_postprocessors=[reranker])
        3. Build summaries query engine:
               summary_qe = _summaries_index.as_query_engine(
                   response_mode="tree_summarize")
        4. Wrap each in QueryEngineTool.from_defaults() with descriptive names:
               Facts tool description:
                   "Use for specific factual questions about named concepts, procedures,
                    definitions, or details in the documents. Examples: 'What is X?',
                    'How does Y work?', 'What are the steps for Z?'"
               Summaries tool description:
                   "Use for broad questions requiring a high-level overview or synthesis
                    across many documents. Examples: 'Summarise everything',
                    'What are the main themes?', 'Give me an overview.'"
        5. Create RouterQueryEngine(
               selector=LLMSingleSelector.from_defaults(),
               query_engine_tools=[facts_tool, summary_tool],
               verbose=True)
        6. Update _router_engine and _reranker_enabled
        7. Return (router_engine, "Router engine ready. Re-ranker: on/off")
    """
    global _router_engine, _reranker_enabled

    # TODO: implement
    return (None, "TODO: implement build_router_engine")


# ── Step 6: Query through the router ─────────────────────────────────────────

def query_with_routing(question: str, category_filter: str) -> tuple:
    """
    Run a question through the router engine and capture the routing decision.

    Args:
        question:        User's question string
        category_filter: If non-empty, apply MetadataFilter on category field
                         and bypass the router, using the Facts Index directly.

    Returns:
        (answer: str, routing_decision: str)

    TODO:
        1. Validate question is non-empty
        2. If _router_engine is None, return error tuple
        3. If category_filter is non-empty (stripped):
               a. Build MetadataFilters with FilterOperator.EQ on "category"
               b. Create a filtered facts query engine:
                      facts_qe = _facts_index.as_query_engine(
                          similarity_top_k=4,
                          filters=MetadataFilters(filters=[
                              MetadataFilter(key="category",
                                             value=category_filter.strip(),
                                             operator=FilterOperator.EQ)
                          ])
                      )
               c. Call facts_qe.query(question)
               d. Return (str(response),
                          f"Metadata filter active (category='{category_filter}').
                            Facts Index used directly.")
        4. Otherwise, capture stdout during the router call to grab verbose output:
               buf = io.StringIO()
               old_stdout = sys.stdout
               sys.stdout = buf
               try:
                   response = _router_engine.query(question)
               finally:
                   sys.stdout = old_stdout
               routing_text = buf.getvalue()
        5. Return (str(response), routing_text)
    """
    # TODO: implement
    return ("TODO: implement query_with_routing", "")


# ── Step 7: Compare all three paths ──────────────────────────────────────────

def compare_indexes(question: str) -> tuple:
    """
    Answer the same question using Facts Index, Summaries Index, and Router,
    and return all three answers plus the routing decision.

    Returns:
        (facts_answer: str, summaries_answer: str,
         router_answer: str, routing_decision: str)

    TODO:
        1. Validate question; check _facts_index, _summaries_index, _router_engine are not None
        2. Query Facts Index:
               facts_qe = _facts_index.as_query_engine(
                   similarity_top_k=4, response_mode="compact")
               facts_answer = str(facts_qe.query(question))
        3. Query Summaries Index:
               summary_qe = _summaries_index.as_query_engine(
                   response_mode="tree_summarize")
               summaries_answer = str(summary_qe.query(question))
        4. Query Router (capturing routing decision via stdout redirect):
               buf = io.StringIO()
               old_stdout = sys.stdout
               sys.stdout = buf
               try:
                   router_response = _router_engine.query(question)
               finally:
                   sys.stdout = old_stdout
               router_answer = str(router_response)
               routing_decision = buf.getvalue()
        5. Return (facts_answer, summaries_answer, router_answer, routing_decision)
    """
    # TODO: implement
    return (
        "TODO: implement compare_indexes",
        "TODO: implement compare_indexes",
        "TODO: implement compare_indexes",
        "",
    )


# ── Step 8: Configuration display ────────────────────────────────────────────

def get_config_text() -> str:
    """
    Return a markdown string describing current runtime configuration.

    TODO:
        Build and return a string that includes:
            - Ollama base URL
            - LLM model name
            - Embedding model name
            - Facts Index chunk size and overlap
            - Summaries Index chunk size and overlap
            - Re-ranker model name and status (enabled/disabled)
            - Whether Facts Index is loaded (yes/no + vector count if yes)
            - Whether Summaries Index is loaded (yes/no)
    """
    # TODO: implement
    return "TODO: implement get_config_text"


# ── Step 9: Build the Gradio UI ───────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    """
    Four-tab Gradio interface.

    Tab 1 — Ingest Documents:
        Left column (Facts Index):
            - gr.File (multiple, .txt/.md/.pdf)
            - gr.Textbox for category_tag (default "general")
            - "Build Facts Index" button
            - status textbox
        Right column (Summaries Index):
            - gr.File (multiple)
            - "Build Summaries Index" button
            - status textbox
        Bottom row:
            - gr.Checkbox "Enable Re-ranker"
            - "Build Router Engine" button
            - router status textbox

    Tab 2 — Query Router:
        - gr.Textbox for question
        - gr.Textbox for category_filter (optional)
        - "Ask Router" button
        - answer textbox (lines=8)
        - routing decision textbox (lines=6)

    Tab 3 — Compare Indexes:
        - gr.Textbox for question
        - "Compare All" button
        - Three answer textboxes side by side
        - routing decision textbox

    Tab 4 — Configuration:
        - gr.Markdown showing current config (refreshed on tab click)

    TODO: implement the full layout and wire all event handlers.
    Each button click should call the corresponding function defined above.
    """
    with gr.Blocks(title="LlamaIndex Router Assistant") as demo:
        gr.Markdown("# LlamaIndex Multi-Index Routing Assistant")

        with gr.Tabs():
            # ── Tab 1: Ingest ─────────────────────────────────────────────────
            with gr.Tab("Ingest Documents"):
                gr.Markdown("### Build the two indexes separately, then assemble the router.")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("#### Facts Index (VectorStoreIndex, 256-token chunks)")
                        # TODO: add file upload, category_tag textbox, button, status
                        facts_files = gr.File(label="Upload files for Facts Index")
                        category_tag = gr.Textbox(label="Category tag", value="general")
                        facts_btn = gr.Button("Build Facts Index", variant="primary")
                        facts_status = gr.Textbox(label="Facts Index Status", interactive=False, lines=2)

                    with gr.Column():
                        gr.Markdown("#### Summaries Index (SummaryIndex, 1024-token chunks)")
                        # TODO: add file upload, button, status
                        summary_files = gr.File(label="Upload files for Summaries Index")
                        summary_btn = gr.Button("Build Summaries Index", variant="primary")
                        summary_status = gr.Textbox(label="Summaries Index Status", interactive=False, lines=2)

                with gr.Row():
                    use_reranker = gr.Checkbox(label="Enable Re-ranker (SentenceTransformerRerank)", value=False)
                    router_btn = gr.Button("Build Router Engine", variant="primary")
                    router_status = gr.Textbox(label="Router Status", interactive=False, lines=2)

                # TODO: wire facts_btn, summary_btn, router_btn

            # ── Tab 2: Query Router ───────────────────────────────────────────
            with gr.Tab("Query Router"):
                gr.Markdown("### Ask the router. It selects the best index automatically.")

                q2 = gr.Textbox(label="Question", placeholder="Ask a question...", lines=2)
                cat_filter = gr.Textbox(
                    label="Metadata Filter — category (leave blank to disable)",
                    placeholder="e.g. technical",
                )
                ask_btn = gr.Button("Ask Router", variant="primary")
                answer_box2 = gr.Textbox(label="Answer", interactive=False, lines=8)
                routing_box = gr.Textbox(label="Routing Decision", interactive=False, lines=6)

                # TODO: wire ask_btn

            # ── Tab 3: Compare Indexes ────────────────────────────────────────
            with gr.Tab("Compare Indexes"):
                gr.Markdown("### Same question answered by all three paths side by side.")

                q3 = gr.Textbox(label="Question", placeholder="Ask a question...", lines=2)
                compare_btn = gr.Button("Compare All", variant="primary")

                with gr.Row():
                    facts_answer_box = gr.Textbox(label="Facts Index Answer", interactive=False, lines=10)
                    summary_answer_box = gr.Textbox(label="Summaries Index Answer", interactive=False, lines=10)
                    router_answer_box = gr.Textbox(label="Router Answer", interactive=False, lines=10)

                routing_box3 = gr.Textbox(label="Routing Decision", interactive=False, lines=4)

                # TODO: wire compare_btn

            # ── Tab 4: Configuration ──────────────────────────────────────────
            with gr.Tab("Configuration"):
                config_md = gr.Markdown(get_config_text())
                refresh_btn = gr.Button("Refresh")
                # TODO: wire refresh_btn to get_config_text

    return demo


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    configure_settings()
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860)
