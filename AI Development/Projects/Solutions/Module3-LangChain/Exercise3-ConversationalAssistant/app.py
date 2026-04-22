"""
Exercise 3 - Multi-Turn Conversational Assistant with Session Management  (SOLUTION)
=====================================================================================
Full working solution demonstrating RunnableWithMessageHistory, trim_messages,
named session persistence, and LCEL chain graph inspection in a Gradio UI.

Run:  python app.py
Then open http://localhost:7860 in your browser.
"""

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path
from typing import Generator, Optional

import httpx
import gradio as gr
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import trim_messages, HumanMessage, AIMessage, SystemMessage
from langchain_community.chat_message_histories import ChatMessageHistory

from history_store import save_session, load_session


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "./sessions")
MAX_HISTORY_TOKENS = 2500

SYSTEM_PROMPT = (
    "You are a knowledgeable and patient assistant. "
    "Build on the conversation history when answering follow-up questions. "
    "Keep responses concise - under 200 words unless the question requires more detail."
)

Path(SESSIONS_DIR).mkdir(parents=True, exist_ok=True)

_session_store: dict[str, ChatMessageHistory] = {}

# Role -> class mapping for display
CLASS_TO_ROLE = {
    HumanMessage: "human",
    AIMessage: "ai",
    SystemMessage: "system",
}


# ---------------------------------------------------------------------------
# Helper: discover locally available Ollama models
# ---------------------------------------------------------------------------

def list_ollama_models() -> list[str]:
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().splitlines()
        names = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                names.append(parts[0].replace(":latest", ""))
        return names if names else ["llama3.2"]
    except Exception:
        return ["llama3.2"]


AVAILABLE_MODELS = list_ollama_models()


# ---------------------------------------------------------------------------
# TODO 2 - Build the base LCEL chain  (SOLUTION)
# ---------------------------------------------------------------------------

def build_chain(model_name: str):
    """Build ChatPromptTemplate | ChatOllama | StrOutputParser."""
    llm = ChatOllama(
        model=model_name,
        temperature=0.7,
        num_ctx=4096,
        base_url=OLLAMA_HOST,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])

    return prompt | llm | StrOutputParser()


# ---------------------------------------------------------------------------
# TODO 3 - History factory with token-based trimming  (SOLUTION)
# ---------------------------------------------------------------------------

def get_history_factory(model_name: str):
    """Return a closure that fetches and trims session history."""

    # Build a lightweight LLM instance purely for token counting
    llm_for_counting = ChatOllama(
        model=model_name,
        temperature=0.0,
        num_ctx=4096,
        base_url=OLLAMA_HOST,
    )

    def get_session_history(session_id: str) -> ChatMessageHistory:
        if session_id not in _session_store:
            _session_store[session_id] = ChatMessageHistory()

        history = _session_store[session_id]

        if history.messages:
            trimmed = trim_messages(
                history.messages,
                max_tokens=MAX_HISTORY_TOKENS,
                strategy="last",
                token_counter=llm_for_counting,
                include_system=True,
                allow_partial=False,
                start_on="human",
            )
            history.messages = trimmed

        return history

    return get_session_history


# ---------------------------------------------------------------------------
# TODO 4 - Streaming chat handler  (SOLUTION)
# ---------------------------------------------------------------------------

def chat(
    user_message: str,
    history_list: list,
    session_id: str,
    model_name: str,
) -> Generator[list, None, None]:
    """Build chain, stream response, yield updated history_list each chunk."""
    if not user_message.strip():
        return

    chain = build_chain(model_name)

    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_history_factory(model_name),
        input_messages_key="input",
        history_messages_key="history",
    )

    config = {"configurable": {"session_id": session_id}}

    # Start a new turn with an empty assistant slot
    history_list = history_list + [[user_message, ""]]

    for chunk in chain_with_history.stream({"input": user_message}, config=config):
        history_list[-1][1] += chunk
        yield history_list


# ---------------------------------------------------------------------------
# TODO 5 - History inspector  (SOLUTION)
# ---------------------------------------------------------------------------

def get_history_json(session_id: str) -> str:
    """Return the current session history as pretty-printed JSON."""
    history = _session_store.get(session_id)
    if not history or not history.messages:
        return "[]"

    messages_data = []
    for msg in history.messages:
        role = CLASS_TO_ROLE.get(type(msg), "unknown")
        messages_data.append({"role": role, "content": msg.content})

    return json.dumps(messages_data, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# TODO 6 - Save and load handlers  (SOLUTION)
# ---------------------------------------------------------------------------

def handle_save(session_id: str) -> str:
    """Save the current session to disk."""
    history = _session_store.get(session_id)
    if not history or not history.messages:
        return f"Nothing to save for session '{session_id}'."
    try:
        save_session(session_id, history, SESSIONS_DIR)
        return f"Session '{session_id}' saved."
    except Exception as exc:
        return f"Save failed: {exc}"


def handle_load(session_id: str, current_history: list) -> tuple[list, str]:
    """Load a session from disk and restore the Chatbot history list."""
    loaded = load_session(session_id, SESSIONS_DIR)
    if loaded is None:
        return current_history, f"Session '{session_id}' not found."

    _session_store[session_id] = loaded

    # Reconstruct the [human, ai] pairs for the Gradio Chatbot
    messages = loaded.messages
    history_list = []
    i = 0
    while i < len(messages):
        if isinstance(messages[i], HumanMessage):
            human_text = messages[i].content
            ai_text = ""
            if i + 1 < len(messages) and isinstance(messages[i + 1], AIMessage):
                ai_text = messages[i + 1].content
                i += 2
            else:
                i += 1
            history_list.append([human_text, ai_text])
        else:
            # Skip system or unexpected messages at the top level
            i += 1

    return history_list, f"Session '{session_id}' loaded ({len(history_list)} turns)."


# ---------------------------------------------------------------------------
# TODO 7 - Chain graph inspector  (SOLUTION)
# ---------------------------------------------------------------------------

def get_chain_graph(model_name: str) -> str:
    """Capture and return the LCEL chain ASCII graph as a string."""
    chain = build_chain(model_name)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        chain.get_graph().print_ascii()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Conversational Assistant") as demo:
        gr.Markdown("## Multi-Turn Conversational Assistant")

        with gr.Tabs():

            with gr.TabItem("Chat"):
                with gr.Row():
                    with gr.Column(scale=2):
                        chatbot = gr.Chatbot(
                            label="Conversation",
                            height=500,
                            bubble_full_width=False,
                        )
                        with gr.Row():
                            msg_input = gr.Textbox(
                                label="Your Message",
                                placeholder="Type your message and press Enter or click Send...",
                                scale=4,
                                container=False,
                            )
                            submit_btn = gr.Button("Send", variant="primary", scale=1)

                    with gr.Column(scale=1):
                        gr.Markdown("### Session")
                        session_id_box = gr.Textbox(
                            label="Session ID",
                            value="default-session",
                            placeholder="Enter a session name...",
                        )
                        model_dropdown = gr.Dropdown(
                            label="Model",
                            choices=AVAILABLE_MODELS,
                            value=AVAILABLE_MODELS[0],
                        )
                        with gr.Row():
                            save_btn = gr.Button("Save Session")
                            load_btn = gr.Button("Load Session")
                        clear_btn = gr.Button("Clear Conversation", variant="stop")
                        status_box = gr.Textbox(
                            label="Status",
                            interactive=False,
                            placeholder="Save/load status appears here...",
                        )
                        gr.Markdown("### History Inspector")
                        history_json_box = gr.Code(
                            label="Raw Message History (JSON)",
                            language="json",
                            lines=12,
                            interactive=False,
                        )

            with gr.TabItem("Chain Inspector"):
                gr.Markdown(
                    "Click **Inspect Chain** to view the LCEL chain graph. "
                    "The model selector on the Chat tab controls which model is shown."
                )
                inspect_btn = gr.Button("Inspect Chain", variant="primary")
                chain_graph_box = gr.Code(
                    label="LCEL Chain Graph",
                    language=None,
                    lines=20,
                    interactive=False,
                )

        # TODO 8 - Wire up events  (SOLUTION)
        submit_btn.click(
            fn=chat,
            inputs=[msg_input, chatbot, session_id_box, model_dropdown],
            outputs=[chatbot],
        ).then(fn=lambda: "", outputs=[msg_input])

        msg_input.submit(
            fn=chat,
            inputs=[msg_input, chatbot, session_id_box, model_dropdown],
            outputs=[chatbot],
        ).then(fn=lambda: "", outputs=[msg_input])

        chatbot.change(
            fn=get_history_json,
            inputs=[session_id_box],
            outputs=[history_json_box],
        )

        save_btn.click(
            fn=handle_save,
            inputs=[session_id_box],
            outputs=[status_box],
        )

        load_btn.click(
            fn=handle_load,
            inputs=[session_id_box, chatbot],
            outputs=[chatbot, status_box],
        )

        clear_btn.click(
            fn=lambda: ([], "[]"),
            inputs=[],
            outputs=[chatbot, history_json_box],
        )

        inspect_btn.click(
            fn=get_chain_graph,
            inputs=[model_dropdown],
            outputs=[chain_graph_box],
        )

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        httpx.get(OLLAMA_HOST, timeout=3.0)
    except httpx.ConnectError:
        print(f"ERROR: Cannot reach Ollama at {OLLAMA_HOST}")
        print("Start Ollama with:  ollama serve")
        raise SystemExit(1)

    app = build_ui()
    app.launch(server_name="0.0.0.0", server_port=7860)
