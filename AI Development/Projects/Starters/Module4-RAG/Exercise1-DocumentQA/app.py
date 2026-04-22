"""
app.py — Gradio UI for Exercise 1: Local Document Q&A.

The two callback functions below are the only things you need to implement.
The Gradio layout is already built for you at the bottom of this file.
"""

import os
import gradio as gr

# Import your engine functions (implement them in rag_engine.py first)
from rag_engine import index_documents, build_rag_chain, ask_question

# ---------------------------------------------------------------------------
# Module-level state — shared across Gradio callbacks
# ---------------------------------------------------------------------------
_vectorstore = None   # set by handle_upload
_rag_chain = None     # set by handle_upload


# ---------------------------------------------------------------------------
# TODO 4 — Implement handle_upload()
# ---------------------------------------------------------------------------
def handle_upload(files):
    """
    Called when the user clicks "Index Files".

    Args:
        files: List of file objects from gr.File. Each has a .name attribute
               that is the temporary path to the uploaded file on disk.

    Returns:
        A status string displayed in the status textbox.

    Steps:
        1. Guard: if `files` is None or empty, return "No files uploaded."
        2. Extract the file path strings: [f.name for f in files].
        3. Call index_documents(file_paths) and store the result in the
           global `_vectorstore`.
        4. Call build_rag_chain(_vectorstore) and store the result in
           the global `_rag_chain`.
        5. Count total chunks: _vectorstore._collection.count()
        6. Return a status string, e.g.:
               "Indexed 3 file(s) — 47 chunks stored."
    """
    global _vectorstore, _rag_chain
    # TODO: implement this function
    return "Not yet implemented."


# ---------------------------------------------------------------------------
# TODO 5 — Implement handle_question()
# ---------------------------------------------------------------------------
def handle_question(question: str):
    """
    Called when the user clicks "Ask".

    Args:
        question: The text typed by the user.

    Returns:
        A tuple (answer_text, sources_text) — two strings for the two output
        textboxes in the UI.

    Steps:
        1. If question.strip() is empty, return ("Please enter a question.", "")
        2. If _rag_chain is None, return ("Please upload and index documents first.", "")
        3. Call ask_question(_rag_chain, question) → (answer, source_chunks)
        4. Format sources_text: for each Document in source_chunks, include:
               - doc.metadata.get("source", "unknown")
               - The first 300 characters of doc.page_content
           Separate each chunk's entry with a blank line.
        5. Return (answer, sources_text)
    """
    # TODO: implement this function
    return "Not yet implemented.", ""


# ---------------------------------------------------------------------------
# Gradio interface — do not modify below this line
# ---------------------------------------------------------------------------
with gr.Blocks(title="Local Document Q&A") as demo:
    gr.Markdown("## Local Document Q&A\nUpload `.txt` or `.md` files, then ask questions.")

    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(
                label="Upload documents (.txt / .md)",
                file_count="multiple",
                file_types=[".txt", ".md"],
            )
            index_btn = gr.Button("Index Files", variant="primary")
            status_box = gr.Textbox(label="Status", interactive=False, lines=2)

        with gr.Column(scale=2):
            question_box = gr.Textbox(
                label="Your question",
                placeholder="Ask something about your documents...",
                lines=2,
            )
            ask_btn = gr.Button("Ask", variant="primary")
            answer_box = gr.Textbox(label="Answer", interactive=False, lines=6)
            sources_box = gr.Textbox(label="Sources", interactive=False, lines=10)

    index_btn.click(fn=handle_upload, inputs=file_input, outputs=status_box)
    ask_btn.click(fn=handle_question, inputs=question_box, outputs=[answer_box, sources_box])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
