"""
Exercise 3 — Multi-Turn Conversational Assistant with Session Management  (STARTER)
=====================================================================================
Complete every TODO to build the full application.

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
from langchain_core.messages import trim_messages
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
    "Keep responses concise — under 200 words unless the question requires more detail."
)

# Ensure the sessions directory exists at startup
Path(SESSIONS_DIR).mkdir(parents=True, exist_ok=True)

# In-memory session store: maps session_id -> ChatMessageHistory
_session_store: dict[str, ChatMessageHistory] = {}


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
# TODO 2 — Build the base LCEL chain (without history wrapping)
# ---------------------------------------------------------------------------

def build_chain(model_name: str):
    """
    Build and return the LCEL chain:
        ChatPromptTemplate (with MessagesPlaceholder) | ChatOllama | StrOutputParser

    The prompt must include:
      - A system message using SYSTEM_PROMPT
      - MessagesPlaceholder(variable_name="history")
      - A human message with placeholder {input}

    Use temperature=0.7 and num_ctx=4096 for ChatOllama.
    Do NOT wrap with RunnableWithMessageHistory here.
    """
    # YOUR CODE HERE
    pass  # replace with your implementation


# ---------------------------------------------------------------------------
# TODO 3 — History factory with token-based trimming
# ---------------------------------------------------------------------------

def get_history_factory(model_name: str):
    """
    Return a closure (function) that accepts a session_id string and returns
    the ChatMessageHistory for that session, applying trim_messages() to keep
    the history within MAX_HISTORY_TOKENS.

    The returned function signature must be:
        def get_session_history(session_id: str) -> ChatMessageHistory

    Inside the closure:
    1. Look up or create the ChatMessageHistory in _session_store.
    2. If history.messages is non-empty, trim with trim_messages():
         - max_tokens=MAX_HISTORY_TOKENS
         - strategy="last"
         - token_counter=<ChatOllama instance using model_name>
         - include_system=True
         - allow_partial=False
         - start_on="human"
    3. Replace history.messages with the trimmed list.
    4. Return the history.

    Hint: The closure captures model_name and a ChatOllama instance for counting.
    """
    # YOUR CODE HERE
    pass  # replace with your implementation


# ---------------------------------------------------------------------------
# TODO 4 — Streaming chat handler
# ---------------------------------------------------------------------------

def chat(
    user_message: str,
    history_list: list,
    session_id: str,
    model_name: str,
) -> Generator[list, None, None]:
    """
    Handle a user message, stream the response, and yield the updated
    history_list after each token so Gradio's Chatbot updates incrementally.

    Steps:
    1. Build the LCEL chain with build_chain(model_name).
    2. Wrap it with RunnableWithMessageHistory, using get_history_factory(model_name)
       as the session history getter, input_messages_key="input",
       history_messages_key="history".
    3. Start a new chat turn: append [user_message, ""] to history_list.
    4. Stream with chain_with_history.stream(
           {"input": user_message},
           config={"configurable": {"session_id": session_id}}
       )
    5. After each chunk, append it to history_list[-1][1] and yield history_list.
    """
    if not user_message.strip():
        return

    # YOUR CODE HERE


# ---------------------------------------------------------------------------
# TODO 5 — History inspector
# ---------------------------------------------------------------------------

def get_history_json(session_id: str) -> str:
    """
    Return the current ChatMessageHistory for session_id as a pretty-printed
    JSON string (list of {"role": ..., "content": ...} dicts).

    If the session has no history, return "[]".

    Role mapping: HumanMessage -> "human", AIMessage -> "ai", SystemMessage -> "system"
    """
    # YOUR CODE HERE
    pass  # replace with your implementation


# ---------------------------------------------------------------------------
# TODO 6 — Save and load handlers
# ---------------------------------------------------------------------------

def handle_save(session_id: str) -> str:
    """
    Save the current session to disk using save_session() from history_store.
    Return a status string confirming success or describing the error.
    """
    # YOUR CODE HERE
    pass  # replace with your implementation


def handle_load(session_id: str, current_history: list) -> tuple[list, str]:
    """
    Load a session from disk using load_session() from history_store.

    If found:
      - Update _session_store[session_id] with the loaded ChatMessageHistory.
      - Reconstruct the history_list (list of [human_str, ai_str] pairs)
        from the loaded messages for the Gradio Chatbot component.
      - Return (reconstructed_history_list, "Session '{session_id}' loaded.").

    If not found:
      - Return (current_history, "Session '{session_id}' not found.").

    Hint: Iterate the loaded history.messages in pairs. HumanMessage comes first
    in each turn, then AIMessage. Use a simple index loop:
      for i in range(0, len(messages), 2):
          human_content = messages[i].content
          ai_content = messages[i+1].content if i+1 < len(messages) else ""
    """
    # YOUR CODE HERE
    pass  # replace with your implementation


# ---------------------------------------------------------------------------
# TODO 7 — Chain graph inspector
# ---------------------------------------------------------------------------

def get_chain_graph(model_name: str) -> str:
    """
    Build the chain and capture the ASCII graph from .get_graph().print_ascii().
    Return the captured string.

    Use io.StringIO and contextlib.redirect_stdout to capture printed output.
    """
    # YOUR CODE HERE
    pass  # replace with your implementation


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Conversational Assistant") as demo:
        gr.Markdown("## Multi-Turn Conversational Assistant")

        with gr.Tabs():

            # ----------------------------------------------------------------
            # Tab 1: Chat
            # ----------------------------------------------------------------
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

            # ----------------------------------------------------------------
            # Tab 2: Chain Inspector
            # ----------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # TODO 8 — Wire up all button and input events
        # ------------------------------------------------------------------
        # See the table in Exercise3-ConversationalAssistant.md Step 8 for
        # the full mapping. Key connections:
        #
        # submit_btn.click  -> chat       -> chatbot      (streaming)
        # msg_input.submit  -> chat       -> chatbot      (streaming)
        # chatbot.change    -> get_history_json -> history_json_box
        # save_btn.click    -> handle_save -> status_box
        # load_btn.click    -> handle_load -> [chatbot, status_box]
        # clear_btn.click   -> lambda []  -> [chatbot, history_json_box]
        # inspect_btn.click -> get_chain_graph -> chain_graph_box
        #
        # After submit_btn.click, chain a .then() to clear msg_input.
        # ------------------------------------------------------------------
        # YOUR CODE HERE
        # ------------------------------------------------------------------

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
