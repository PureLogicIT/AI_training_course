"""
Exercise 3 — Multi-Turn Model Comparison App
=============================================
A Gradio app with three tabs:
  1. Chat       — multi-turn chat with model switching and token stats
  2. Save/Load  — persist conversation history to/from JSON
  3. Compare    — send the same prompt to two models concurrently

Complete every TODO. Each TODO maps to a numbered step in the exercise
instructions.
"""

from __future__ import annotations

import os
from typing import Generator

import gradio as gr
import ollama

from conversation import ConversationManager
from inference import stream_response, compare_responses

# ---------------------------------------------------------------------------
# Shared Ollama client
# ---------------------------------------------------------------------------

OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
client: ollama.Client = ollama.Client(host=OLLAMA_HOST)

SYSTEM_PROMPT = (
    "You are a helpful and knowledgeable assistant. "
    "Answer clearly and concisely."
)

DEFAULT_OPTIONS: dict = {"temperature": 0.7, "num_ctx": 4096}


def get_models() -> list[str]:
    """Return list of available Ollama model names."""
    try:
        return [m.model for m in client.list().models]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# TODO 3 — Chat tab: send_message()
# ---------------------------------------------------------------------------

def send_message(
    user_text: str,
    model: str,
    conv_manager: ConversationManager,
) -> Generator[tuple, None, None]:
    """Stream a response and yield Gradio updates incrementally.

    This is a generator function. On each iteration yield a tuple of:
        (gradio_history, stats_text, conv_manager)

    Args:
        user_text:    The user's input text.
        model:        The currently selected Ollama model name.
        conv_manager: The ConversationManager state object.

    Yields:
        Tuples of (list[list], str, ConversationManager) for Gradio outputs.
    """
    if not user_text.strip():
        return

    # TODO 3a: Add user message to conv_manager.

    # TODO 3b: Start the stream using stream_response() from inference.py.
    # Collect partial tokens into `partial` and yield updated history on each token.
    # When the done sentinel arrives, call conv_manager.add_assistant() and
    # yield the final state with the stats string.
    #
    # Yield format: (conv_manager.to_gradio_history(), stats_text, conv_manager)
    # During streaming, show partial text in the last pair's assistant slot.
    # Hint: build a temp history by appending [user_text, partial] to
    #       conv_manager.to_gradio_history() before the assistant turn is committed.

    partial: list[str] = []
    stats_text: str = "Generating…"

    yield (conv_manager.to_gradio_history(), stats_text, conv_manager)  # placeholder


# ---------------------------------------------------------------------------
# TODO 4 — Model switching
# ---------------------------------------------------------------------------

def switch_model(
    new_model: str,
    conv_manager: ConversationManager,
) -> tuple[list[list], ConversationManager]:
    """Insert a switch marker and return updated history + state.

    Args:
        new_model:    The newly selected model name.
        conv_manager: Current ConversationManager.

    Returns:
        (gradio_history, conv_manager)
    """
    # TODO 4: Add an assistant message like "[Switched to model: {new_model}]"
    # using conv_manager.add_assistant(), then return the updated history.
    raise NotImplementedError("TODO 4")


# ---------------------------------------------------------------------------
# TODO 5 — Save / Load helpers
# ---------------------------------------------------------------------------

def save_conversation(filepath: str, conv_manager: ConversationManager) -> str:
    """Save conversation to JSON and return a status message string."""
    # TODO 5a: Call conv_manager.save_to_json(filepath).
    # Return a success string or an error string if an exception is raised.
    raise NotImplementedError("TODO 5a")


def load_conversation(
    file_obj,
    conv_manager: ConversationManager,
) -> tuple[list[list], ConversationManager, str]:
    """Load conversation from an uploaded file.

    Args:
        file_obj:     Gradio file object (access path via file_obj.name).
        conv_manager: Current ConversationManager state.

    Returns:
        (gradio_history, conv_manager, status_message)
    """
    # TODO 5b: Call conv_manager.load_from_json(file_obj.name).
    # Return (conv_manager.to_gradio_history(), conv_manager, status_string).
    # Handle ValueError and IOError and return an error status string.
    raise NotImplementedError("TODO 5b")


# ---------------------------------------------------------------------------
# TODO 6 — Compare mode
# ---------------------------------------------------------------------------

def run_compare(
    prompt: str,
    model_a: str,
    model_b: str,
) -> tuple[str, str, str, str]:
    """Run prompt through two models concurrently and return results.

    Returns:
        (text_a, text_b, stats_a_markdown, stats_b_markdown)
    """
    if not prompt.strip():
        return "Please enter a prompt.", "", "", ""

    # TODO 6: Build a minimal messages list (system + user prompt).
    # Call compare_responses() from inference.py.
    # Format stats as: "**{total_tokens} tokens | {tokens_per_sec:.1f} tok/s**"
    # Return (text_a, text_b, stats_a_str, stats_b_str).
    raise NotImplementedError("TODO 6")


# ---------------------------------------------------------------------------
# TODO 7 — Full UI assembly
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    """Build and return the complete Gradio Blocks application."""
    models = get_models()
    default_model = models[0] if models else ""

    with gr.Blocks(title="Multi-Model Chat") as demo:
        gr.Markdown("# Multi-Turn Model Comparison App")

        # Shared state — one ConversationManager per browser session
        conv_state = gr.State(lambda: ConversationManager(system_prompt=SYSTEM_PROMPT))

        with gr.Tabs():

            # ----------------------------------------------------------------
            # Tab 1 — Chat
            # ----------------------------------------------------------------
            with gr.Tab("Chat"):
                # TODO 7a: Add a gr.Dropdown for model selection (choices=models)
                model_dd = None  # replace

                # TODO 7b: Add a gr.Chatbot (height=500)
                chatbot = None  # replace

                # TODO 7c: Add a stats display (gr.Markdown)
                stats_display = None  # replace

                # TODO 7d: Add a message input textbox
                msg_box = None  # replace

                # TODO 7e: Wire msg_box submit / a Send button to send_message()
                # Outputs: [chatbot, stats_display, conv_state]

                # TODO 7f: Wire model_dd .change() to switch_model()
                # Outputs: [chatbot, conv_state]

            # ----------------------------------------------------------------
            # Tab 2 — Save / Load
            # ----------------------------------------------------------------
            with gr.Tab("Save / Load"):
                # TODO 7g: Add save path textbox, Save button, status display
                save_path_box = None  # replace
                save_btn = None       # replace
                save_status = None    # replace

                # TODO 7h: Wire Save button to save_conversation()
                # Inputs: [save_path_box, conv_state]
                # Outputs: [save_status]

                # TODO 7i: Add gr.File upload and Load button
                load_file = None  # replace
                load_btn = None   # replace
                load_status = None  # replace

                # TODO 7j: Wire Load button to load_conversation()
                # Inputs: [load_file, conv_state]
                # Outputs: [chatbot, conv_state, load_status]

            # ----------------------------------------------------------------
            # Tab 3 — Compare
            # ----------------------------------------------------------------
            with gr.Tab("Compare"):
                with gr.Row():
                    # TODO 7k: Add two dropdowns (Model A, Model B)
                    compare_model_a = None  # replace
                    compare_model_b = None  # replace

                compare_prompt = None  # replace with gr.Textbox(lines=3, ...)
                compare_btn = None     # replace with gr.Button(...)

                with gr.Row():
                    # TODO 7l: Add two output textboxes side by side
                    output_a = None  # replace
                    output_b = None  # replace

                with gr.Row():
                    # TODO 7m: Add two stats markdown displays
                    stats_a = None  # replace
                    stats_b = None  # replace

                # TODO 7n: Wire compare_btn.click() to run_compare()
                # Inputs: [compare_prompt, compare_model_a, compare_model_b]
                # Outputs: [output_a, output_b, stats_a, stats_b]

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860)
