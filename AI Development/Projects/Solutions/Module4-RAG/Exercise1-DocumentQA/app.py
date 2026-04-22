"""
app.py — Gradio UI for Exercise 1: Local Document Q&A (SOLUTION).
"""

import os
import gradio as gr

from rag_engine import index_documents, build_rag_chain, ask_question

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_vectorstore = None
_rag_chain = None


def handle_upload(files):
    """Index uploaded .txt / .md files and update module-level state."""
    global _vectorstore, _rag_chain

    if not files:
        return "No files uploaded."

    file_paths = [f.name for f in files]

    try:
        _vectorstore = index_documents(file_paths)
        _rag_chain = build_rag_chain(_vectorstore)
        chunk_count = _vectorstore._collection.count()
        return f"Indexed {len(file_paths)} file(s) — {chunk_count} chunks stored."
    except Exception as exc:
        return f"Indexing failed: {exc}"


def handle_question(question: str):
    """Answer a question using the current RAG chain."""
    if not question.strip():
        return "Please enter a question.", ""

    if _rag_chain is None:
        return "Please upload and index documents first.", ""

    try:
        answer, source_chunks = ask_question(_rag_chain, question)

        lines = []
        for i, doc in enumerate(source_chunks, 1):
            source = doc.metadata.get("source", "unknown")
            excerpt = doc.page_content[:300].strip()
            lines.append(f"[Chunk {i}]\nSource: {source}\n{excerpt}")

        sources_text = "\n\n".join(lines) if lines else "No sources retrieved."
        return answer, sources_text

    except Exception as exc:
        return f"Error: {exc}", ""


# ---------------------------------------------------------------------------
# Gradio interface
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
