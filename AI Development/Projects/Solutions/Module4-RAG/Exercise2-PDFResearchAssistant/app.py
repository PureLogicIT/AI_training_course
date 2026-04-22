"""
app.py — Gradio interface for Exercise 2: PDF Research Assistant (SOLUTION).
"""

import os
import gradio as gr

from indexer import build_index
from retriever import retrieve_with_scores, build_rag_chain

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_vectorstore = None
_rag_chain = None
_current_chunks = []


def handle_upload_and_index(files, chunk_size: int, chunk_overlap: int) -> str:
    global _vectorstore, _rag_chain, _current_chunks

    if not files:
        return "No files uploaded."

    pdf_paths = [f.name for f in files]

    try:
        _vectorstore, _current_chunks = build_index(
            pdf_paths, int(chunk_size), int(chunk_overlap)
        )
        _rag_chain = build_rag_chain(_vectorstore, k=5)
        return (
            f"Indexed {len(pdf_paths)} PDF(s) — {len(_current_chunks)} total chunks "
            f"(chunk_size={int(chunk_size)}, overlap={int(chunk_overlap)})."
        )
    except Exception as exc:
        return f"Indexing failed: {exc}"


def handle_chat(message: str, history: list, debug_mode: bool, k_value: int):
    global _vectorstore, _rag_chain

    if not message.strip():
        return history, ""

    if _vectorstore is None:
        history = history + [[message, "Please upload and index PDFs first."]]
        return history, ""

    try:
        # Rebuild chain with current k so slider changes take effect
        _rag_chain = build_rag_chain(_vectorstore, k=int(k_value))

        scored_chunks = retrieve_with_scores(_vectorstore, message, k=int(k_value))
        result = _rag_chain.invoke({"input": message})
        answer = result["answer"]

        history = history + [[message, answer]]

        lines = []
        for i, (doc, score) in enumerate(scored_chunks, 1):
            file_name = os.path.basename(doc.metadata.get("source", "unknown"))
            page_raw = doc.metadata.get("page", None)
            page_str = f"Page {page_raw + 1}" if page_raw is not None else "Page N/A"
            excerpt = doc.page_content[:250].strip()

            entry = f"[{i}] {file_name} — {page_str}\n{excerpt}"
            if debug_mode:
                entry += f"\n  L2 distance: {score:.4f}"
            lines.append(entry)

        sources_text = "\n\n".join(lines) if lines else "No sources retrieved."
        return history, sources_text

    except Exception as exc:
        history = history + [[message, f"Error: {exc}"]]
        return history, ""


def handle_reindex(files, chunk_size: int, chunk_overlap: int):
    status = handle_upload_and_index(files, chunk_size, chunk_overlap)
    return status, [], ""


# ---------------------------------------------------------------------------
# Gradio layout
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
                debug_check = gr.Checkbox(
                    label="Debug mode (show similarity scores)", value=False
                )
                k_slider = gr.Slider(
                    minimum=1, maximum=10, step=1, value=5, label="K (chunks retrieved)"
                )
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
