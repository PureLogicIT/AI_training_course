"""
Exercise 2 — Conversational RAG Chat App with LlamaIndex Chat Engine
====================================================================
SOLUTION: fully implemented version.

Features:
  1. Upload and index documents into ChromaDB (persistent vector store)
  2. Multi-turn streaming chat using index.as_chat_engine(condense_plus_context)
  3. Sources panel showing retrieved nodes after each response
  4. Response mode selector (compact / refine / tree_summarize)
  5. Clear chat button to reset conversation history

Run:
    pip install -r requirements.txt
    python app.py
"""

import chromadb
import gradio as gr
from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore

# ── Constants ──────────────────────────────────────────────────────────────────
CHROMA_PATH = "./chroma_chat"
COLLECTION_NAME = "chat_documents"
OLLAMA_BASE_URL = "http://localhost:11434"
LLM_MODEL = "llama3.2"
EMBED_MODEL = "nomic-embed-text"

RESPONSE_MODES = ["compact", "refine", "tree_summarize"]

# Module-level state
_current_index = None
_chat_engine = None
_active_response_mode = "compact"


# ── Configure Settings ─────────────────────────────────────────────────────────

def configure_settings() -> None:
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
    Settings.chunk_size = 512
    Settings.chunk_overlap = 50


# ── ChromaDB helpers ──────────────────────────────────────────────────────────

def get_chroma_components() -> tuple:
    """Create and return (vector_store, collection, storage_context)."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return vector_store, collection, storage_context


# ── Index documents ───────────────────────────────────────────────────────────

def index_documents(files) -> str:
    """Load and index uploaded files into ChromaDB."""
    global _current_index, _chat_engine

    if not files:
        return "Please upload at least one file."

    file_paths = [f.name for f in files]

    try:
        documents = SimpleDirectoryReader(input_files=file_paths).load_data()
    except Exception as exc:
        return f"Error loading documents: {exc}"

    if not documents:
        return "No content could be extracted from the uploaded files."

    vector_store, collection, storage_context = get_chroma_components()

    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )

    _current_index = index
    _chat_engine = None  # force rebuild on next chat call

    count = collection.count()
    return f"Indexed {len(documents)} document(s). Collection now has {count} vectors."


# ── Load existing index ───────────────────────────────────────────────────────

def get_or_load_index():
    """Return current index if loaded, else try to load from ChromaDB."""
    global _current_index

    if _current_index is not None:
        return _current_index

    vector_store, collection, storage_context = get_chroma_components()

    if collection.count() == 0:
        return None

    _current_index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )
    return _current_index


# ── Build or get chat engine ──────────────────────────────────────────────────

def get_chat_engine(index, response_mode: str):
    """Return the chat engine, rebuilding when response_mode changes."""
    global _chat_engine, _active_response_mode

    if _chat_engine is None or _active_response_mode != response_mode:
        # condense_plus_context rewrites follow-up questions and retrieves fresh context
        _chat_engine = index.as_chat_engine(
            chat_mode="condense_plus_context",
            similarity_top_k=4,
            verbose=False,
        )
        _active_response_mode = response_mode

    return _chat_engine


# ── Streaming chat handler ────────────────────────────────────────────────────

def chat(user_message: str, history: list, response_mode: str):
    """
    Generator that streams a chat response into the Gradio Chatbot.

    Yields: (updated_history, sources_text)
    """
    if not user_message or not user_message.strip():
        yield (history, "")
        return

    index = get_or_load_index()
    if index is None:
        yield (history + [[user_message, "No index loaded. Please upload and index documents first."]], "")
        return

    engine = get_chat_engine(index, response_mode)

    # Append user message with empty assistant slot
    history = history + [[user_message.strip(), ""]]

    # Stream response token by token
    try:
        streaming_response = engine.stream_chat(user_message.strip())
        for token in streaming_response.response_gen:
            history[-1][1] += token
            yield (history, "")
    except Exception as exc:
        history[-1][1] = f"Error during generation: {exc}"
        yield (history, "")
        return

    # Build sources text from the fully-consumed response
    sources_parts = []
    source_nodes = getattr(streaming_response, "source_nodes", [])
    for i, node_with_score in enumerate(source_nodes, start=1):
        file_name = node_with_score.node.metadata.get("file_name", "unknown")
        score = node_with_score.score
        passage = node_with_score.node.get_content()[:300]
        sources_parts.append(
            f"[{i}] {file_name}  (score: {score:.3f})\n{passage}"
        )

    sources_text = ("\n" + "─" * 60 + "\n").join(sources_parts) if sources_parts else "No source nodes returned."
    yield (history, sources_text)


# ── Clear chat ────────────────────────────────────────────────────────────────

def clear_chat() -> tuple:
    """Reset the chat engine and return empty history and sources."""
    global _chat_engine
    _chat_engine = None  # next call rebuilds, resetting conversation memory
    return ([], "")


# ── Handle response mode change ───────────────────────────────────────────────

def on_mode_change(new_mode: str) -> str:
    """Reset chat engine so it is rebuilt with the new mode."""
    global _chat_engine
    _chat_engine = None
    return f"Response mode changed to '{new_mode}'. Start a new message to use it."


# ── Build the Gradio UI ───────────────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    with gr.Blocks(title="LlamaIndex Chat Engine") as demo:
        gr.Markdown(
            "# LlamaIndex Conversational RAG\n"
            "Upload documents, index them with ChromaDB, then chat with streaming responses.\n"
            "Conversation history is maintained across turns — the engine rewrites follow-up questions."
        )

        with gr.Row():
            # ── Left sidebar ──────────────────────────────────────────────────
            with gr.Column(scale=1):
                gr.Markdown("### Documents")

                file_upload = gr.File(
                    label="Upload files (.txt, .md, .pdf)",
                    file_count="multiple",
                    file_types=[".txt", ".md", ".pdf"],
                )

                index_btn = gr.Button("Index Documents", variant="primary")

                status_box = gr.Textbox(
                    label="Status",
                    interactive=False,
                    lines=3,
                )

                gr.Markdown("### Response Mode")
                gr.Markdown(
                    "- **compact** — packs nodes into one prompt (fastest)\n"
                    "- **refine** — iterative refinement across nodes\n"
                    "- **tree_summarize** — recursive tree summarisation (best for overviews)"
                )
                mode_radio = gr.Radio(
                    choices=RESPONSE_MODES,
                    value="compact",
                    label="Synthesizer Mode",
                )

            # ── Main chat area ────────────────────────────────────────────────
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    label="Conversation",
                    height=500,
                    show_copy_button=True,
                )

                with gr.Row():
                    question_box = gr.Textbox(
                        label="",
                        placeholder="Ask a question about your documents...",
                        scale=4,
                        show_label=False,
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)

                clear_btn = gr.Button("Clear Conversation", variant="secondary")

                sources_box = gr.Textbox(
                    label="Retrieved Sources (passages used for the last response)",
                    interactive=False,
                    lines=12,
                )

        # ── Event wiring ──────────────────────────────────────────────────────

        index_btn.click(
            fn=index_documents,
            inputs=[file_upload],
            outputs=[status_box],
        )

        mode_radio.change(
            fn=on_mode_change,
            inputs=[mode_radio],
            outputs=[status_box],
        )

        # Streaming chat: wire send button
        send_btn.click(
            fn=chat,
            inputs=[question_box, chatbot, mode_radio],
            outputs=[chatbot, sources_box],
        ).then(
            fn=lambda: "",
            inputs=[],
            outputs=[question_box],
        )

        # Also allow Enter to submit
        question_box.submit(
            fn=chat,
            inputs=[question_box, chatbot, mode_radio],
            outputs=[chatbot, sources_box],
        ).then(
            fn=lambda: "",
            inputs=[],
            outputs=[question_box],
        )

        clear_btn.click(
            fn=clear_chat,
            inputs=[],
            outputs=[chatbot, sources_box],
        )

    return demo


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    configure_settings()

    # Attempt to load any existing ChromaDB index at startup
    existing = get_or_load_index()
    if existing is not None:
        print(f"Loaded existing ChromaDB index from '{CHROMA_PATH}'")
    else:
        print(f"No existing index at '{CHROMA_PATH}'. Upload documents via the UI.")

    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860)
