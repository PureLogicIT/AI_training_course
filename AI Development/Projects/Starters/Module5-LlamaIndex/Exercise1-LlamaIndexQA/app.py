"""
Exercise 1 — Local Document Q&A with LlamaIndex and Gradio
===========================================================
Starter project: complete every section marked with TODO.

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

    This function MUST be called before any VectorStoreIndex is created or loaded.
    Setting Settings.llm and Settings.embed_model after index construction has no effect.

    TODO:
        1. Set Settings.llm to an Ollama instance with:
               model=LLM_MODEL, base_url=OLLAMA_BASE_URL,
               request_timeout=120.0, context_window=8192
        2. Set Settings.embed_model to an OllamaEmbedding instance with:
               model_name=EMBED_MODEL, base_url=OLLAMA_BASE_URL
        3. Set Settings.chunk_size = 512
        4. Set Settings.chunk_overlap = 50
    """
    # TODO: set Settings.llm
    pass

    # TODO: set Settings.embed_model
    pass

    # TODO: set Settings.chunk_size and Settings.chunk_overlap
    pass


# ── Step 2: Build index from uploaded files ───────────────────────────────────

def build_index(files) -> tuple:
    """
    Load documents from the uploaded file list, build a VectorStoreIndex,
    and persist it to PERSIST_DIR.

    Args:
        files: list of Gradio file objects (each has a .name attribute with the temp path)

    Returns:
        (status_message: str, index_state: object)
        The second element is passed through gr.State to update the shared index.

    TODO:
        1. If files is None or empty, return ("Please upload at least one file.", None)
        2. Extract file paths: [f.name for f in files]
        3. Call SimpleDirectoryReader(input_files=file_paths).load_data()
        4. Call VectorStoreIndex.from_documents(documents, show_progress=True)
        5. Persist with index.storage_context.persist(persist_dir=PERSIST_DIR)
        6. Update the module-level _current_index variable
        7. Return ("Indexed N documents. M nodes stored in PERSIST_DIR.", index)
           Hint: after calling from_documents(), the number of nodes can be inferred
           from len(documents) since each document may produce multiple nodes —
           use len(documents) in the status message for simplicity.
    """
    global _current_index

    # TODO: validate input
    pass

    # TODO: extract file paths from Gradio file objects
    file_paths = []

    # TODO: load documents
    documents = []

    # TODO: build and persist the index
    index = None

    # TODO: update _current_index and return status
    return ("TODO: implement this function", None)


# ── Step 3: Load existing index from disk ────────────────────────────────────

def load_or_none():
    """
    Attempt to load a previously persisted index from PERSIST_DIR.

    Returns:
        The loaded VectorStoreIndex if PERSIST_DIR exists, otherwise None.

    TODO:
        1. Check if PERSIST_DIR exists using os.path.exists()
        2. If it does:
               a. Create StorageContext.from_defaults(persist_dir=PERSIST_DIR)
               b. Call load_index_from_storage(storage_context)
               c. Store in _current_index and return the index
        3. If it does not exist, return None
    """
    global _current_index

    # TODO: check for persisted index and load it
    pass

    return None


# ── Step 4: Answer a question using the index ─────────────────────────────────

def answer_question(question: str, index_state) -> tuple:
    """
    Query the index and return the answer plus retrieved source passages.

    Args:
        question:    The user's question string
        index_state: Unused (kept for Gradio State wiring) — use _current_index directly

    Returns:
        (answer: str, sources: str)

    TODO:
        1. If _current_index is None, return ("No index loaded. Upload files first.", "")
        2. If question is empty, return ("Please enter a question.", "")
        3. Create query_engine = _current_index.as_query_engine(
               similarity_top_k=3, response_mode="compact"
           )
        4. Call response = query_engine.query(question)
        5. Build sources_text:
               For each node in response.source_nodes:
                   - file_name = node.node.metadata.get("file_name", "unknown")
                   - score = node.score  (float, format to 3 decimal places)
                   - passage = node.node.get_content()[:400]
               Separate each source entry with "\n" + "─" * 60 + "\n"
        6. Return (str(response), sources_text)
    """
    global _current_index

    # TODO: guard against missing index
    pass

    # TODO: guard against empty question
    pass

    # TODO: create query engine, run query
    query_engine = None
    response = None

    # TODO: build sources text
    sources_text = ""

    # TODO: return (answer, sources)
    return ("TODO: implement answer_question", "")


# ── Step 5: Clear the persisted index ────────────────────────────────────────

def clear_index() -> tuple:
    """
    Delete the persisted index from disk and reset _current_index.

    Returns:
        (status_message: str, None)

    TODO:
        1. If PERSIST_DIR exists, delete it with shutil.rmtree(PERSIST_DIR)
        2. Set _current_index = None
        3. Return ("Index cleared. Upload new documents to re-index.", None)
    """
    global _current_index

    # TODO: delete PERSIST_DIR if it exists
    pass

    # TODO: reset _current_index and return status
    return ("TODO: implement clear_index", None)


# ── Step 6: Build the Gradio UI ───────────────────────────────────────────────

def build_ui(initial_index) -> gr.Blocks:
    """
    Construct and return the Gradio Blocks interface.

    Layout:
        - File upload component (accepts .txt, .md, .pdf)
        - "Index Documents" button → status textbox
        - "Clear Index" button → status textbox (reuse same status textbox)
        - Question textbox
        - "Ask" button
        - Answer textbox (output)
        - Sources textbox (output, lines=10)

    gr.State holds the index reference so button callbacks can update it.

    TODO:
        1. Create a gr.State(value=initial_index) to track the index object
        2. Wire the "Index Documents" button click to build_index()
           Inputs: [file_upload, index_state]   Outputs: [status_box, index_state]
        3. Wire the "Clear Index" button click to clear_index()
           Inputs: []   Outputs: [status_box, index_state]
        4. Wire the "Ask" button click (and textbox submit) to answer_question()
           Inputs: [question_box, index_state]   Outputs: [answer_box, sources_box]
        5. Return the gr.Blocks object (do not call .launch() here)
    """
    with gr.Blocks(title="LlamaIndex Document Q&A") as demo:
        gr.Markdown("# LlamaIndex Document Q&A\nUpload documents, index them, then ask questions.")

        # TODO: add gr.State for index tracking
        index_state = gr.State(value=initial_index)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 1. Upload & Index Documents")

                # TODO: add gr.File component for document upload
                file_upload = gr.File(label="Upload files")  # placeholder

                # TODO: add Index Documents button
                index_btn = gr.Button("Index Documents", variant="primary")

                # TODO: add Clear Index button
                clear_btn = gr.Button("Clear Index", variant="secondary")

                # TODO: add status textbox
                status_box = gr.Textbox(label="Status", interactive=False, lines=2)

            with gr.Column(scale=2):
                gr.Markdown("### 2. Ask a Question")

                # TODO: add question input textbox
                question_box = gr.Textbox(
                    label="Question",
                    placeholder="Type your question here...",
                    lines=2,
                )

                # TODO: add Ask button
                ask_btn = gr.Button("Ask", variant="primary")

                # TODO: add answer output textbox
                answer_box = gr.Textbox(label="Answer", interactive=False, lines=6)

                # TODO: add sources output textbox
                sources_box = gr.Textbox(
                    label="Retrieved Sources",
                    interactive=False,
                    lines=10,
                )

        # TODO: wire up button click events

    return demo


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Configure Settings FIRST — before any index is created or loaded
    configure_settings()

    # Try to load a previously persisted index
    initial_index = load_or_none()
    if initial_index is not None:
        print(f"Loaded existing index from {PERSIST_DIR}")
    else:
        print(f"No existing index found at {PERSIST_DIR}. Upload documents to create one.")

    demo = build_ui(initial_index)
    demo.launch(server_name="0.0.0.0", server_port=7860)
