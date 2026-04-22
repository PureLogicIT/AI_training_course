"""
Exercise 1 — Local Document Q&A with LlamaIndex and Gradio
===========================================================
SOLUTION: fully implemented version.

The app allows users to:
  1. Upload .txt / .md / .pdf files via the Gradio UI
  2. Index them into a VectorStoreIndex (persisted to disk with JSON storage)
  3. Ask questions and receive answers with source passage attribution

Run:
    pip install -r requirements.txt
    python app.py
"""

import os
import shutil

import gradio as gr
from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

# ── Constants ──────────────────────────────────────────────────────────────────
PERSIST_DIR = "./index_storage"
OLLAMA_BASE_URL = "http://localhost:11434"
LLM_MODEL = "llama3.2"
EMBED_MODEL = "nomic-embed-text"

# Module-level index variable — stores the loaded/built index between UI calls
_current_index = None


# ── Step 1: Configure Settings ────────────────────────────────────────────────

def configure_settings() -> None:
    """
    Configure the global LlamaIndex Settings singleton.

    Must be called before any VectorStoreIndex is created or loaded.
    """
    Settings.llm = Ollama(
        model=LLM_MODEL,
        base_url=OLLAMA_BASE_URL,
        request_timeout=120.0,
        context_window=8192,
    )
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )
    Settings.chunk_size = 512
    Settings.chunk_overlap = 50


# ── Step 2: Build index from uploaded files ───────────────────────────────────

def build_index(files) -> tuple:
    """
    Load documents from the uploaded file list, build a VectorStoreIndex,
    and persist it to PERSIST_DIR.

    Returns:
        (status_message: str, index_state: object)
    """
    global _current_index

    if not files:
        return ("Please upload at least one file.", None)

    # Extract the temp file paths that Gradio wrote for us
    file_paths = [f.name for f in files]

    try:
        documents = SimpleDirectoryReader(input_files=file_paths).load_data()
    except Exception as exc:
        return (f"Error loading documents: {exc}", None)

    if not documents:
        return ("No text content could be extracted from the uploaded files.", None)

    # Build the index — Settings.llm and Settings.embed_model are read here
    index = VectorStoreIndex.from_documents(documents, show_progress=True)

    # Persist to disk so the index survives app restarts
    os.makedirs(PERSIST_DIR, exist_ok=True)
    index.storage_context.persist(persist_dir=PERSIST_DIR)

    _current_index = index
    status = (
        f"Indexed {len(documents)} document(s). "
        f"Index saved to '{PERSIST_DIR}'."
    )
    return (status, index)


# ── Step 3: Load existing index from disk ────────────────────────────────────

def load_or_none():
    """
    Attempt to load a previously persisted index from PERSIST_DIR.

    Returns the VectorStoreIndex if found, otherwise None.
    """
    global _current_index

    if not os.path.exists(PERSIST_DIR):
        return None

    try:
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        index = load_index_from_storage(storage_context)
        _current_index = index
        return index
    except Exception as exc:
        print(f"Warning: could not load persisted index — {exc}")
        return None


# ── Step 4: Answer a question using the index ─────────────────────────────────

def answer_question(question: str, index_state) -> tuple:
    """
    Query the index and return the answer plus retrieved source passages.

    Returns:
        (answer: str, sources: str)
    """
    global _current_index

    if _current_index is None:
        return ("No index loaded. Please upload and index documents first.", "")

    if not question or not question.strip():
        return ("Please enter a question.", "")

    query_engine = _current_index.as_query_engine(
        similarity_top_k=3,
        response_mode="compact",
    )

    response = query_engine.query(question.strip())
    answer_text = str(response)

    # Build human-readable source attribution
    sources_parts = []
    for i, node_with_score in enumerate(response.source_nodes, start=1):
        file_name = node_with_score.node.metadata.get("file_name", "unknown")
        score = node_with_score.score
        passage = node_with_score.node.get_content()[:400]
        sources_parts.append(
            f"[{i}] {file_name}  (score: {score:.3f})\n{passage}"
        )

    sources_text = ("\n" + "─" * 60 + "\n").join(sources_parts) if sources_parts else "No sources returned."

    return (answer_text, sources_text)


# ── Step 5: Clear the persisted index ────────────────────────────────────────

def clear_index() -> tuple:
    """
    Delete the persisted index from disk and reset _current_index.
    """
    global _current_index

    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)

    _current_index = None
    return ("Index cleared. Upload new documents to re-index.", None)


# ── Step 6: Build the Gradio UI ───────────────────────────────────────────────

def build_ui(initial_index) -> gr.Blocks:
    """
    Construct and return the Gradio Blocks interface.
    """
    with gr.Blocks(title="LlamaIndex Document Q&A") as demo:
        gr.Markdown(
            "# LlamaIndex Document Q&A\n"
            "Upload `.txt`, `.md`, or `.pdf` files, index them, then ask questions.\n"
            "The index persists between sessions — you only need to re-index when files change."
        )

        # gr.State holds the index so Gradio's reactive graph can wire callbacks
        index_state = gr.State(value=initial_index)

        with gr.Row():
            # ── Left column: upload and indexing ──────────────────────────────
            with gr.Column(scale=1):
                gr.Markdown("### 1. Upload & Index Documents")

                file_upload = gr.File(
                    label="Upload files (.txt, .md, .pdf)",
                    file_count="multiple",
                    file_types=[".txt", ".md", ".pdf"],
                )

                with gr.Row():
                    index_btn = gr.Button("Index Documents", variant="primary")
                    clear_btn = gr.Button("Clear Index", variant="secondary")

                status_box = gr.Textbox(
                    label="Status",
                    interactive=False,
                    lines=3,
                    value="Ready. Upload documents to begin." if initial_index is None
                          else f"Existing index loaded from '{PERSIST_DIR}'.",
                )

            # ── Right column: querying ─────────────────────────────────────────
            with gr.Column(scale=2):
                gr.Markdown("### 2. Ask a Question")

                question_box = gr.Textbox(
                    label="Question",
                    placeholder="Type your question about the uploaded documents...",
                    lines=2,
                )

                ask_btn = gr.Button("Ask", variant="primary")

                answer_box = gr.Textbox(
                    label="Answer",
                    interactive=False,
                    lines=6,
                )

                sources_box = gr.Textbox(
                    label="Retrieved Sources (top 3 passages used to generate the answer)",
                    interactive=False,
                    lines=10,
                )

        # ── Event wiring ──────────────────────────────────────────────────────

        index_btn.click(
            fn=build_index,
            inputs=[file_upload],
            outputs=[status_box, index_state],
        )

        clear_btn.click(
            fn=clear_index,
            inputs=[],
            outputs=[status_box, index_state],
        )

        ask_btn.click(
            fn=answer_question,
            inputs=[question_box, index_state],
            outputs=[answer_box, sources_box],
        )

        # Also allow pressing Enter in the question box to submit
        question_box.submit(
            fn=answer_question,
            inputs=[question_box, index_state],
            outputs=[answer_box, sources_box],
        )

    return demo


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Configure Settings FIRST — before any index is created or loaded
    configure_settings()

    # Try to load a previously persisted index
    initial_index = load_or_none()
    if initial_index is not None:
        print(f"Loaded existing index from '{PERSIST_DIR}'")
    else:
        print(f"No existing index at '{PERSIST_DIR}'. Upload documents via the UI.")

    demo = build_ui(initial_index)
    demo.launch(server_name="0.0.0.0", server_port=7860)
