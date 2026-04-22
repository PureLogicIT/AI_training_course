"""
app.py — Multi-tab Gradio app for Exercise 3: Personal Knowledge Base.

The Gradio layout skeleton is provided. Implement the callback functions
marked with TODO.
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
# TODO 11 — Implement handle_add_files()
# ---------------------------------------------------------------------------
def handle_add_files(files):
    """
    Index uploaded files and return a status string.

    Args:
        files: List of Gradio file objects (each has .name path attribute).

    Returns:
        Tuple (status_string, updated_doc_dropdown, updated_manage_dropdown).
        The two dropdowns must be updated to reflect the new document list.

    Steps:
        1. Guard: if files is None or empty, return ("No files selected.", ..., ...).
        2. Loop over files. For each file, call index_documents(_vectorstore, f.name).
           Accumulate total_chunks.
        3. Get updated doc list: docs = list_indexed_documents(_vectorstore).
        4. Return:
               status = f"Added {len(files)} file(s) — {total_chunks} chunks indexed."
               (status,
                gr.Dropdown(choices=["(All documents)"] + docs, value="(All documents)"),
                gr.Dropdown(choices=docs, value=docs[0] if docs else None))
    """
    # TODO: implement this function
    return "Not yet implemented.", gr.Dropdown(), gr.Dropdown()


# ---------------------------------------------------------------------------
# TODO 12 — Implement handle_add_url()
# ---------------------------------------------------------------------------
def handle_add_url(url: str):
    """
    Index a web URL and return a status string plus updated dropdowns.

    Args:
        url: The URL string from the textbox.

    Returns:
        Tuple (status_string, updated_doc_dropdown, updated_manage_dropdown).

    Steps:
        1. Guard: if url.strip() is empty or does not start with "http",
           return ("Please enter a valid URL starting with http.", ..., ...).
        2. Call index_documents(_vectorstore, url.strip(), source_type="url").
        3. Get updated doc list and return the same tuple shape as handle_add_files.
    """
    # TODO: implement this function
    return "Not yet implemented.", gr.Dropdown(), gr.Dropdown()


# ---------------------------------------------------------------------------
# TODO 13 — Implement handle_ask()
# ---------------------------------------------------------------------------
def handle_ask(message: str, history: list, filter_choice: str):
    """
    Answer a question using MultiQueryRetriever with optional metadata filtering.

    Args:
        message:       The user's question.
        history:       Gradio chatbot history.
        filter_choice: Selected value from the document filter dropdown.

    Returns:
        Tuple (updated_history, sources_text, stats_text).

    Steps:
        1. Guard empty message: return (history, "", format_stats(get_stats(_vectorstore))).
        2. Build filter_metadata:
               if filter_choice != "(All documents)":
                   filter_metadata = {"doc_name": filter_choice}
               else:
                   filter_metadata = None
        3. chain = build_multi_query_chain(_vectorstore, filter_metadata=filter_metadata)
        4. result = chain.invoke({"input": message})
           answer = result["answer"]
           context_docs = result["context"]
        5. increment_queries()
        6. Append [message, answer] to history.
        7. Format sources_text: for each doc in context_docs, show:
               - doc.metadata.get("doc_name", "unknown")
               - Page: doc.metadata.get("page", "") — show only if present
               - First 200 chars of doc.page_content
        8. Return (history, sources_text, format_stats(get_stats(_vectorstore))).
    """
    # TODO: implement this function
    return history, "Not yet implemented.", format_stats(get_stats(_vectorstore))


# ---------------------------------------------------------------------------
# TODO 14 — Implement handle_delete()
# ---------------------------------------------------------------------------
def handle_delete(doc_name: str):
    """
    Delete a document from the index and return status + updated dropdowns.

    Args:
        doc_name: The document name selected in the manage dropdown.

    Returns:
        Tuple (status_string, updated_doc_dropdown, updated_manage_dropdown).

    Steps:
        1. Guard: if doc_name is None or empty, return ("No document selected.", ..., ...).
        2. Call delete_document(_vectorstore, doc_name). Get count of deleted chunks.
        3. Get updated doc list.
        4. Return:
               status = f"Deleted '{doc_name}' — {n} chunks removed."
               (status,
                gr.Dropdown(choices=["(All documents)"] + docs, value="(All documents)"),
                gr.Dropdown(choices=docs, value=docs[0] if docs else None))
    """
    # TODO: implement this function
    return "Not yet implemented.", gr.Dropdown(), gr.Dropdown()


# ---------------------------------------------------------------------------
# TODO 15 — Implement handle_refresh()
# ---------------------------------------------------------------------------
def handle_refresh():
    """
    Refresh the document list in both dropdowns.

    Returns:
        Tuple (updated_doc_dropdown, updated_manage_dropdown).

    Steps:
        1. docs = list_indexed_documents(_vectorstore)
        2. Return:
               (gr.Dropdown(choices=["(All documents)"] + docs, value="(All documents)"),
                gr.Dropdown(choices=docs, value=docs[0] if docs else None))
    """
    # TODO: implement this function
    return gr.Dropdown(), gr.Dropdown()


# ---------------------------------------------------------------------------
# Gradio layout — complete the wire-up (some outputs reference components
# defined further down; Gradio handles forward references inside with-blocks)
# ---------------------------------------------------------------------------
with gr.Blocks(title="Personal Knowledge Base") as demo:
    gr.Markdown("## Personal Knowledge Base\nIndex documents from files or URLs and query with advanced RAG.")

    # Shared dropdown components (referenced across tabs)
    # These are created once and updated by callbacks returning gr.Dropdown updates
    _initial_docs = list_indexed_documents(_vectorstore)

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
