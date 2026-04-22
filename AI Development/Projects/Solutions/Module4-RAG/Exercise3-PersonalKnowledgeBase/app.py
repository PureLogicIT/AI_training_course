"""
app.py — Multi-tab Gradio app for Exercise 3: Personal Knowledge Base (SOLUTION).
"""

import os
import gradio as gr

from knowledge_base import (
    get_chroma_client,
    get_vectorstore,
    get_embeddings,
    index_documents,
    build_multi_query_chain,
    list_indexed_documents,
    delete_document,
)
from stats import increment_queries, get_stats, format_stats

# ---------------------------------------------------------------------------
# Initialise shared resources at startup
# ---------------------------------------------------------------------------
_embeddings = get_embeddings()
_chroma_client = get_chroma_client()
_vectorstore = get_vectorstore(_chroma_client, _embeddings)


# ---------------------------------------------------------------------------
# Helper — build updated dropdown values
# ---------------------------------------------------------------------------
def _doc_dropdowns():
    docs = list_indexed_documents(_vectorstore)
    return (
        gr.Dropdown(choices=["(All documents)"] + docs, value="(All documents)"),
        gr.Dropdown(choices=docs, value=docs[0] if docs else None),
    )


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
def handle_add_files(files):
    if not files:
        d1, d2 = _doc_dropdowns()
        return "No files selected.", d1, d2

    total_chunks = 0
    for f in files:
        try:
            total_chunks += index_documents(_vectorstore, f.name)
        except Exception as exc:
            print(f"Warning: could not index '{f.name}': {exc}")

    d1, d2 = _doc_dropdowns()
    status = f"Added {len(files)} file(s) — {total_chunks} chunks indexed."
    return status, d1, d2


def handle_add_url(url: str):
    stripped = url.strip()
    if not stripped or not stripped.startswith("http"):
        d1, d2 = _doc_dropdowns()
        return "Please enter a valid URL starting with http.", d1, d2

    try:
        n = index_documents(_vectorstore, stripped, source_type="url")
    except Exception as exc:
        d1, d2 = _doc_dropdowns()
        return f"Failed to load URL: {exc}", d1, d2

    d1, d2 = _doc_dropdowns()
    return f"Added URL — {n} chunks indexed.", d1, d2


def handle_ask(message: str, history: list, filter_choice: str):
    stats_text = format_stats(get_stats(_vectorstore))

    if not message.strip():
        return history, "", stats_text

    filter_metadata = None
    if filter_choice and filter_choice != "(All documents)":
        filter_metadata = {"doc_name": filter_choice}

    try:
        chain = build_multi_query_chain(_vectorstore, filter_metadata=filter_metadata)
        result = chain.invoke({"input": message})
        answer = result["answer"]
        context_docs = result["context"]
    except Exception as exc:
        history = history + [[message, f"Error: {exc}"]]
        return history, "", format_stats(get_stats(_vectorstore))

    increment_queries()
    history = history + [[message, answer]]

    lines = []
    for i, doc in enumerate(context_docs, 1):
        doc_name = doc.metadata.get("doc_name", "unknown")
        page_raw = doc.metadata.get("page", None)
        page_str = f" — Page {page_raw + 1}" if page_raw is not None else ""
        excerpt = doc.page_content[:200].strip()
        lines.append(f"[{i}] {doc_name}{page_str}\n{excerpt}")

    sources_text = "\n\n".join(lines) if lines else "No sources retrieved."
    return history, sources_text, format_stats(get_stats(_vectorstore))


def handle_delete(doc_name: str):
    if not doc_name:
        d1, d2 = _doc_dropdowns()
        return "No document selected.", d1, d2

    try:
        n = delete_document(_vectorstore, doc_name)
    except Exception as exc:
        d1, d2 = _doc_dropdowns()
        return f"Delete failed: {exc}", d1, d2

    d1, d2 = _doc_dropdowns()
    return f"Deleted '{doc_name}' — {n} chunks removed.", d1, d2


def handle_refresh():
    return _doc_dropdowns()


# ---------------------------------------------------------------------------
# Gradio layout
# ---------------------------------------------------------------------------
_initial_docs = list_indexed_documents(_vectorstore)

with gr.Blocks(title="Personal Knowledge Base") as demo:
    gr.Markdown(
        "## Personal Knowledge Base\n"
        "Index documents from files or URLs and query with advanced RAG."
    )

    with gr.Tabs():

        # ── Tab 1: Add Documents ──────────────────────────────────────────
        with gr.Tab("Add Documents"):
            file_input = gr.File(
                label="Upload files (.pdf, .txt, .md)",
                file_count="multiple",
                file_types=[".pdf", ".txt", ".md"],
            )
            add_files_btn = gr.Button("Add Files", variant="primary")
            gr.Markdown("---")
            url_input = gr.Textbox(
                label="Or enter a web URL",
                placeholder="https://example.com/docs/intro",
            )
            add_url_btn = gr.Button("Add URL", variant="primary")
            add_status = gr.Textbox(label="Status", interactive=False, lines=2)

        # ── Tab 2: Ask Questions ──────────────────────────────────────────
        with gr.Tab("Ask Questions"):
            doc_filter = gr.Dropdown(
                label="Filter by document",
                choices=["(All documents)"] + _initial_docs,
                value="(All documents)",
                interactive=True,
            )
            chatbot = gr.Chatbot(label="Conversation", height=400)
            with gr.Row():
                msg_input = gr.Textbox(
                    label="Your question",
                    placeholder="Ask anything about your knowledge base...",
                    scale=4,
                )
                ask_btn = gr.Button("Ask", variant="primary", scale=1)
            sources_box = gr.Textbox(label="Sources", interactive=False, lines=12)
            stats_box = gr.Textbox(
                label="Usage stats",
                interactive=False,
                lines=3,
                value=format_stats(get_stats(_vectorstore)),
            )

        # ── Tab 3: Manage Index ───────────────────────────────────────────
        with gr.Tab("Manage Index"):
            manage_dropdown = gr.Dropdown(
                label="Select document to delete",
                choices=_initial_docs,
                value=_initial_docs[0] if _initial_docs else None,
                interactive=True,
            )
            with gr.Row():
                delete_btn = gr.Button("Delete Document", variant="stop")
                refresh_btn = gr.Button("Refresh document list")
            manage_status = gr.Textbox(label="Result", interactive=False, lines=2)

    # ── Wire callbacks ────────────────────────────────────────────────────
    add_files_btn.click(
        fn=handle_add_files,
        inputs=file_input,
        outputs=[add_status, doc_filter, manage_dropdown],
    )
    add_url_btn.click(
        fn=handle_add_url,
        inputs=url_input,
        outputs=[add_status, doc_filter, manage_dropdown],
    )
    ask_btn.click(
        fn=handle_ask,
        inputs=[msg_input, chatbot, doc_filter],
        outputs=[chatbot, sources_box, stats_box],
    )
    msg_input.submit(
        fn=handle_ask,
        inputs=[msg_input, chatbot, doc_filter],
        outputs=[chatbot, sources_box, stats_box],
    )
    delete_btn.click(
        fn=handle_delete,
        inputs=manage_dropdown,
        outputs=[manage_status, doc_filter, manage_dropdown],
    )
    refresh_btn.click(
        fn=handle_refresh,
        inputs=None,
        outputs=[doc_filter, manage_dropdown],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
