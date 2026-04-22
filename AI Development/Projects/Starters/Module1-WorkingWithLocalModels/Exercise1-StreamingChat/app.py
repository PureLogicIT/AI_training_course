"""
Exercise 1 — Streaming Chat App
================================
A Gradio chat interface that streams responses from a local Ollama server.

Complete every TODO in order. Each TODO corresponds to a numbered step in the
exercise instructions.
"""

from __future__ import annotations

import os
from typing import Generator

import gradio as gr
import ollama

# ---------------------------------------------------------------------------
# TODO 1 — Connect to Ollama using a configurable host
#
# Read the OLLAMA_HOST environment variable (default: "http://localhost:11434")
# and create an ollama.Client instance bound to that host.
# Store the client in the module-level variable `client`.
# ---------------------------------------------------------------------------

OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# TODO 1: Replace `None` with an ollama.Client instance using OLLAMA_HOST
client: ollama.Client = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# TODO 2 — List available models for the dropdown
# ---------------------------------------------------------------------------

def get_available_models() -> list[str]:
    """Return a list of model name strings available on the Ollama server.

    Call client.list() and extract the model names. Return an empty list if
    the server is unreachable so the app still starts.

    Expected return value example: ["llama3.2:latest", "mistral:7b"]
    """
    # TODO 2: Call client.list(), extract model names, and return them.
    # Wrap in a try/except so a connection error returns [] gracefully.
    return []


# ---------------------------------------------------------------------------
# TODO 3 — Build the message history from Gradio's chat history format
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a helpful and concise assistant. "
    "Answer clearly and directly. "
    "If you are unsure about something, say so."
)


def build_messages(history: list[list[str | None]], user_message: str) -> list[dict]:
    """Convert Gradio chat history to Ollama message format.

    Gradio passes history as a list of [user_text, assistant_text] pairs where
    assistant_text may be None for the in-progress turn. Build and return a
    list of {"role": ..., "content": ...} dicts suitable for ollama.chat().

    Always place SYSTEM_PROMPT as the first message.

    Args:
        history: List of [user_text, assistant_text] pairs from Gradio.
        user_message: The current (new) user message not yet in history.

    Returns:
        A list of role/content dicts in chronological order.
    """
    # TODO 3: Build and return the messages list.
    # 1. Start with the system prompt dict.
    # 2. Iterate over history pairs and append user then assistant dicts.
    #    Skip the assistant dict if assistant_text is None.
    # 3. Append the new user_message at the end.
    messages: list[dict] = []
    return messages


# ---------------------------------------------------------------------------
# TODO 4 — Stream the response
# ---------------------------------------------------------------------------

def chat_stream(
    user_message: str,
    history: list[list[str | None]],
    model: str,
    temperature: float,
) -> Generator[str, None, None]:
    """Stream a chat response from Ollama, yielding cumulative partial text.

    This function is called by Gradio's ChatInterface on every user submission.
    It must be a generator — yield the growing response string after each chunk
    so Gradio can update the UI incrementally.

    Args:
        user_message: The text the user just submitted.
        history: Previous turns as [[user, assistant], ...] pairs.
        model: The Ollama model name selected in the dropdown.
        temperature: Sampling temperature from the slider.

    Yields:
        Cumulative response text after each token chunk.
    """
    # TODO 4: Implement streaming.
    # 1. Call build_messages(history, user_message).
    # 2. Call client.chat() with stream=True, the chosen model, and
    #    options={"temperature": temperature}.
    # 3. Accumulate tokens and yield "".join(accumulated) after each chunk.
    accumulated: list[str] = []
    yield ""  # placeholder — remove this line when you implement the TODO


# ---------------------------------------------------------------------------
# TODO 5 — Wire up the Gradio interface
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    """Build and return the Gradio Blocks application.

    Layout requirements:
    - gr.Dropdown: model selector, choices from get_available_models()
    - gr.Slider: temperature, range 0.0–2.0, step 0.05, default 0.7
    - gr.ChatInterface: calls chat_stream, passes dropdown + slider as
      additional_inputs

    The app must listen on 0.0.0.0:7860.
    """
    # TODO 5: Build the gr.Blocks layout and return the `demo` object.
    # Do NOT call demo.launch() here — that happens in the __main__ block below.
    available_models = get_available_models()

    with gr.Blocks(title="Ollama Streaming Chat") as demo:
        gr.Markdown("## Ollama Streaming Chat")

        # TODO 5a: Add a gr.Dropdown for model selection
        model_dropdown = None  # replace with gr.Dropdown(...)

        # TODO 5b: Add a gr.Slider for temperature
        temperature_slider = None  # replace with gr.Slider(...)

        # TODO 5c: Add a gr.ChatInterface that uses chat_stream as its fn
        #          and passes [model_dropdown, temperature_slider] as additional_inputs
        pass

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860)
