"""
Exercise 2 — Conversational RAG Chat App with LlamaIndex Chat Engine
====================================================================
Starter project: complete every section marked with TODO.

Features to implement:
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

# Module-level state (avoids Gradio serialisation issues with complex objects)
_current_index = None
_chat_engine = None
_active_response_mode = "compact"


# ── Step 1: Configure Settings ────────────────────────────────────────────────

def configure_settings() -> None:
    """
    Configure the global LlamaIndex Settings singleton.
    Must be called before any index construction.

    TODO:
        1. Set Settings.llm = Ollama(model=LLM_MODEL, base_url=OLLAMA_BASE_URL,
                                     request_timeout=180.0, context_window=8192)
        2. Set Settings.embed_model = OllamaEmbedding(model_name=EMBED_MODEL,
                                                       base_url=OLLAMA_BASE_URL)
        3. Set Settings.chunk_size = 512
        4. Set Settings.chunk_overlap = 50
    """
    # TODO: configure Settings
    pass


# ── Step 2: ChromaDB helpers ──────────────────────────────────────────────────

def get_chroma_components() -> tuple:
    """
    Create and return ChromaDB components for the vector store.

    Returns:
        (vector_store: ChromaVectorStore,
         collection: chromadb.Collection,
         storage_context: StorageContext)

    TODO:
        1. Create chromadb.PersistentClient(path=CHROMA_PATH)
        2. Call client.get_or_create_collection(COLLECTION_NAME)
        3. Create ChromaVectorStore(chroma_collection=collection)
        4. Create StorageContext.from_defaults(vector_store=vector_store)
        5. Return (vector_store, collection, storage_context)
    """
    # TODO: implement ChromaDB component setup
    return None, None, None


# ── Step 3: Index documents ───────────────────────────────────────────────────

def index_documents(files) -> str:
    """
    Load documents from uploaded files and index them into ChromaDB.

    Args:
        files: list of Gradio file objects (each has a .name temp path)

    Returns:
        Status message string.

    TODO:
        1. Validate files is not None/empty
        2. Extract file paths: [f.name for f in files]
        3. Load with SimpleDirectoryReader(input_files=paths).load_data()
        4. Call get_chroma_components() to get (vector_store, collection, storage_context)
        5. Index with VectorStoreIndex.from_documents(documents,
               storage_context=storage_context, show_progress=True)
        6. Update _current_index and reset _chat_engine to None
           (the new index needs a fresh chat engine)
        7. Return "Indexed N documents. Collection now has M vectors."
           where M = collection.count()
    """
    global _current_index, _chat_engine

    # TODO: implement document indexing
    return "TODO: implement index_documents"


# ── Step 4: Load existing index ───────────────────────────────────────────────

def get_or_load_index():
    """
    Return _current_index if already loaded, otherwise load from ChromaDB.

    Returns:
        VectorStoreIndex or None if no vectors are stored.

    TODO:
        1. If _current_index is not None, return it directly
        2. Call get_chroma_components()
        3. If collection.count() == 0, return None (no data yet)
        4. Load with VectorStoreIndex.from_vector_store(
               vector_store, storage_context=storage_context)
        5. Store in _current_index and return it
    """
    global _current_index

    # TODO: implement lazy index loading
    return None


# ── Step 5: Build or get chat engine ─────────────────────────────────────────

def get_chat_engine(index, response_mode: str):
    """
    Return the active chat engine, rebuilding if the response_mode changed.

    The chat engine wraps a condense_plus_context chat mode with the given
    response_mode for the underlying query synthesizer.

    Args:
        index:         VectorStoreIndex
        response_mode: one of "compact", "refine", "tree_summarize"

    Returns:
        A LlamaIndex chat engine instance.

    TODO:
        1. Check if _chat_engine is None or _active_response_mode != response_mode
        2. If rebuild needed:
               a. Create query_engine = index.as_query_engine(
                      similarity_top_k=4, response_mode=response_mode)
               b. Create chat_engine = index.as_chat_engine(
                      chat_mode="condense_plus_context",
                      similarity_top_k=4,
                      verbose=False)
               c. Update _chat_engine and _active_response_mode
        3. Return _chat_engine

    Note: LlamaIndex's condense_plus_context mode does not directly expose
    response_mode in as_chat_engine(). A pragmatic approach is to always
    rebuild the chat engine when the mode changes — the user will see a
    clear conversation boundary. The response_mode mainly affects synthesis
    quality for multi-node answers.
    """
    global _chat_engine, _active_response_mode

    # TODO: implement chat engine construction and caching
    return None


# ── Step 6: Streaming chat handler ───────────────────────────────────────────

def chat(user_message: str, history: list, response_mode: str):
    """
    Generator that streams a chat response token-by-token into the Gradio Chatbot.

    Args:
        user_message:  The user's new message
        history:       Gradio chatbot history: list of [user_str, assistant_str] pairs
        response_mode: Selected response synthesizer mode

    Yields:
        (updated_history: list, sources_text: str)

    TODO:
        1. Validate user_message is non-empty
        2. Call get_or_load_index(). If None, yield error and return.
        3. Call get_chat_engine(index, response_mode). If None, yield error and return.
        4. Append [user_message, ""] to history (empty assistant slot)
        5. Call streaming_response = chat_engine.stream_chat(user_message)
        6. Iterate over streaming_response.response_gen:
               - Append each token to history[-1][1]
               - Yield (history, "")   (sources panel empty while streaming)
        7. After the loop completes, build sources_text from
               streaming_response.source_nodes (same format as Exercise 1)
        8. Yield (history, sources_text) as the final yield
    """
    if not user_message or not user_message.strip():
        yield (history, "")
        return

    index = get_or_load_index()
    if index is None:
        history = history + [[user_message, "No index loaded. Please upload documents first."]]
        yield (history, "")
        return

    engine = get_chat_engine(index, response_mode)
    if engine is None:
        history = history + [[user_message, "Failed to build chat engine."]]
        yield (history, "")
        return

    # TODO: append user message to history with empty assistant slot
    history = history + [[user_message, ""]]

    # TODO: stream tokens from chat engine
    streaming_response = None  # TODO: call engine.stream_chat(user_message)

    # TODO: iterate over streaming_response.response_gen and yield incrementally
    # for token in streaming_response.response_gen:
    #     history[-1][1] += token
    #     yield (history, "")

    # TODO: after streaming completes, build and yield sources text
    sources_text = "TODO: build sources from streaming_response.source_nodes"
    yield (history, sources_text)


# ── Step 7: Clear chat ───────────────────────────────────────────────────────

def clear_chat() -> tuple:
    """
    Reset the chat engine (clears conversation history) and return empty state.

    Returns:
        (empty_history: list, empty_sources: str)

    TODO:
        1. Set _chat_engine = None so get_chat_engine() rebuilds on next call
           (rebuilding resets conversation memory)
        2. Return ([], "")
    """
    global _chat_engine

    # TODO: reset chat engine and return empty state
    return ([], "")


# ── Step 8: Handle response mode change ──────────────────────────────────────

def on_mode_change(new_mode: str) -> str:
    """
    Called when the user changes the response mode dropdown.
    Resets the chat engine so it is rebuilt with the new mode on next message.

    Returns:
        Status message string.

    TODO:
        1. Set _chat_engine = None
        2. Return f"Response mode changed to '{new_mode}'. Conversation reset."
    """
    global _chat_engine

    # TODO: reset chat engine and return status
    return f"TODO: handle mode change to {new_mode}"


# ── Step 9: Build the Gradio UI ───────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    """
    Construct the Gradio Blocks chat interface.

    Layout:
        Left sidebar:
            - File upload (multiple, .txt/.md/.pdf)
            - "Index Documents" button
            - Status textbox
            - Response Mode radio (compact / refine / tree_summarize)
        Main area:
            - gr.Chatbot (height=500)
            - User input textbox
            - Send button
            - Clear Chat button
            - Sources textbox (lines=12)

    TODO:
        1. Wire file_upload + index_btn to index_documents() → status_box
        2. Wire mode_radio change to on_mode_change() → status_box
        3. Wire send_btn click AND question_box submit to chat() generator
           Inputs: [question_box, chatbot, mode_radio]
           Outputs: [chatbot, sources_box]
           Use: fn=chat, inputs=[...], outputs=[...] — Gradio handles generators
        4. Wire clear_btn to clear_chat()
           Outputs: [chatbot, sources_box]
        5. After send, clear the question_box by chaining a .then() that sets it to ""
    """
    with gr.Blocks(title="LlamaIndex Chat Engine") as demo:
        gr.Markdown(
            "# LlamaIndex Conversational RAG\n"
            "Upload documents, index them with ChromaDB, then chat with streaming responses."
        )

        with gr.Row():
            # ── Left sidebar ──────────────────────────────────────────────────
            with gr.Column(scale=1):
                gr.Markdown("### Documents")

                # TODO: add file upload
                file_upload = gr.File(label="Upload files")  # placeholder

                # TODO: add Index Documents button
                index_btn = gr.Button("Index Documents", variant="primary")

                # TODO: add status textbox
                status_box = gr.Textbox(label="Status", interactive=False, lines=2)

                gr.Markdown("### Response Mode")

                # TODO: add response mode radio
                mode_radio = gr.Radio(
                    choices=RESPONSE_MODES,
                    value="compact",
                    label="Synthesizer Mode",
                )

            # ── Main chat area ────────────────────────────────────────────────
            with gr.Column(scale=3):
                # TODO: add Chatbot component
                chatbot = gr.Chatbot(label="Chat", height=500)

                with gr.Row():
                    # TODO: add question input
                    question_box = gr.Textbox(
                        label="Message",
                        placeholder="Ask a question about your documents...",
                        scale=4,
                    )
                    # TODO: add Send button
                    send_btn = gr.Button("Send", variant="primary", scale=1)

                # TODO: add Clear Chat button
                clear_btn = gr.Button("Clear Chat", variant="secondary")

                # TODO: add sources textbox
                sources_box = gr.Textbox(
                    label="Retrieved Sources",
                    interactive=False,
                    lines=12,
                )

        # TODO: wire event handlers

    return demo


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    configure_settings()
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860)
