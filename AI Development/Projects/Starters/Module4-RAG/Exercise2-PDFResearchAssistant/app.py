"""
app.py — Gradio interface for Exercise 2: PDF Research Assistant.

Implement the three callback functions below, then verify the Gradio layout
at the bottom is correctly wired to them.
"""

import os
import gradio as gr

from indexer import build_index
from retriever import retrieve_with_scores, build_rag_chain

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_vectorstore = None   # FAISS vectorstore; set after indexing
_rag_chain = None     # RAG chain; rebuilt when index changes or k changes


# ---------------------------------------------------------------------------
# TODO 4 — Implement handle_upload_and_index()
# ---------------------------------------------------------------------------
def handle_upload_and_index(files, chunk_size: int, chunk_overlap: int) -> str:
    """
    Index the uploaded PDFs and update module-level state.

    Args:
        files:        List of Gradio file objects (each has a .name path attribute).
        chunk_size:   Current slider value.
        chunk_overlap: Current slider value.

    Returns:
        A status string for the status textbox.

    Steps:
        1. Guard: if files is None or empty, return "No files uploaded."
        2. Extract pdf_paths = [f.name for f in files].
        3. Call build_index(pdf_paths, int(chunk_size), int(chunk_overlap)).
           Store vectorstore and chunks in globals.
        4. Rebuild the RAG chain with build_rag_chain(_vectorstore, k=5).
        5. Return a status string:
               "Indexed N PDF(s) — M total chunks (chunk_size=X, overlap=Y)."
           Use len(files) for N and len(chunks) for M.
    """
    global _vectorstore, _rag_chain
    # TODO: implement this function
    return "Not yet implemented."


# ---------------------------------------------------------------------------
# TODO 5 — Implement handle_chat()
# ---------------------------------------------------------------------------
def handle_chat(message: str, history: list, debug_mode: bool, k_value: int):
    """
    Process a chat message and return the updated history and sources panel.

    Args:
        message:    The user's question string.
        history:    Current Gradio chatbot history (list of [user, bot] pairs).
        debug_mode: If True, show L2 distance scores in the sources panel.
        k_value:    Number of chunks to retrieve (from the K slider).

    Returns:
        Tuple (updated_history, sources_text).

    Steps:
        1. If message.strip() is empty, return (history, "").
        2. If _vectorstore is None, append a warning to history and return.
        3. Rebuild the RAG chain with build_rag_chain(_vectorstore, k=int(k_value)).
        4. Call retrieve_with_scores(_vectorstore, message, k=int(k_value)).
           Store as scored_chunks — a list of (Document, float).
        5. Call the RAG chain: result = _rag_chain.invoke({"input": message}).
           Extract answer = result["answer"].
        6. Append [message, answer] to history.
        7. Format sources_text. For each (doc, score) in scored_chunks:
               - File name: os.path.basename(doc.metadata.get("source", "unknown"))
               - Page: doc.metadata.get("page", "?") + 1  (convert to 1-indexed)
               - Excerpt: first 250 chars of doc.page_content
               - If debug_mode is True, also show: f"  L2 distance: {score:.4f}"
           Separate each chunk entry with a blank line.
        8. Return (history, sources_text).
    """
    # TODO: implement this function
    return history, "Not yet implemented."


# ---------------------------------------------------------------------------
# TODO 6 — Implement handle_reindex()
# ---------------------------------------------------------------------------
def handle_reindex(files, chunk_size: int, chunk_overlap: int):
    """
    Re-index PDFs with new chunking parameters and reset the conversation.

    Returns:
        Tuple (status_string, empty_history, empty_sources).

    Steps:
        1. Call handle_upload_and_index(files, chunk_size, chunk_overlap).
        2. Return (status, [], "").
    """
    # TODO: implement this function
    return "Not yet implemented.", [], ""


# ---------------------------------------------------------------------------
# Gradio layout — do not modify below this line
# ---------------------------------------------------------------------------
with gr.Blocks(title="PDF Research Assistant") as demo:
    gr.Markdown("## PDF Research Assistant\nUpload PDFs, ask questions, inspect sources.")

    with gr.Row():
        with gr.Column(scale=1):
            pdf_upload = gr.File(
                label="Upload PDF(s)",
                file_count="multiple",
                file_types=[".pdf"],
            )
            chunk_size_slider = gr.Slider(
                minimum=100, maximum=1500, step=50, value=600,
                label="Chunk size (characters)",
            )
            overlap_slider = gr.Slider(
                minimum=0, maximum=300, step=25, value=75,
                label="Chunk overlap (characters)",
            )
            index_btn = gr.Button("Index PDFs", variant="primary")
            reindex_btn = gr.Button("Re-index with new settings")
            status_box = gr.Textbox(label="Status", interactive=False, lines=3)

        with gr.Column(scale=2):
            chatbot = gr.Chatbot(label="Conversation", height=400)
            with gr.Row():
                msg_box = gr.Textbox(
                    label="Your question",
                    placeholder="Ask about the uploaded PDFs...",
                    scale=4,
                )
                send_btn = gr.Button("Send", variant="primary", scale=1)
            with gr.Row():
                debug_check = gr.Checkbox(label="Debug mode (show similarity scores)", value=False)
                k_slider = gr.Slider(minimum=1, maximum=10, step=1, value=5, label="K (chunks retrieved)")
            sources_box = gr.Textbox(label="Sources", interactive=False, lines=15)

    index_btn.click(
        fn=handle_upload_and_index,
        inputs=[pdf_upload, chunk_size_slider, overlap_slider],
        outputs=status_box,
    )
    reindex_btn.click(
        fn=handle_reindex,
        inputs=[pdf_upload, chunk_size_slider, overlap_slider],
        outputs=[status_box, chatbot, sources_box],
    )
    send_btn.click(
        fn=handle_chat,
        inputs=[msg_box, chatbot, debug_check, k_slider],
        outputs=[chatbot, sources_box],
    )
    msg_box.submit(
        fn=handle_chat,
        inputs=[msg_box, chatbot, debug_check, k_slider],
        outputs=[chatbot, sources_box],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
