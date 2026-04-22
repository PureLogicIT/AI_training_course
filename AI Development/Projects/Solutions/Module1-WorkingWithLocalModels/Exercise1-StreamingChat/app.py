"""
Exercise 1 — Streaming Chat App (SOLUTION)
==========================================
A Gradio chat interface that streams responses from a local Ollama server.
"""

from __future__ import annotations

import os
from typing import Generator

import gradio as gr
import ollama

# ---------------------------------------------------------------------------
# Step 1 — Connect to Ollama using a configurable host
# ---------------------------------------------------------------------------

OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
client: ollama.Client = ollama.Client(host=OLLAMA_HOST)


# ---------------------------------------------------------------------------
# Step 2 — List available models for the dropdown
# ---------------------------------------------------------------------------

def get_available_models() -> list[str]:
    """Return a list of model name strings available on the Ollama server."""
    try:
        result = client.list()
        return [m.model for m in result.models]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Step 3 — Build the message history from Gradio's chat history format
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a helpful and concise assistant. "
    "Answer clearly and directly. "
    "If you are unsure about something, say so."
)


def build_messages(history: list[list[str | None]], user_message: str) -> list[dict]:
    """Convert Gradio chat history to Ollama message format."""
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    for user_text, assistant_text in history:
        if user_text is not None:
            messages.append({"role": "user", "content": user_text})
        if assistant_text is not None:
            messages.append({"role": "assistant", "content": assistant_text})

    messages.append({"role": "user", "content": user_message})
    return messages


# ---------------------------------------------------------------------------
# Step 4 — Stream the response
# ---------------------------------------------------------------------------

def chat_stream(
    user_message: str,
    history: list[list[str | None]],
    model: str,
    temperature: float,
) -> Generator[str, None, None]:
    """Stream a chat response from Ollama, yielding cumulative partial text."""
    messages = build_messages(history, user_message)

    accumulated: list[str] = []
    stream = client.chat(
        model=model,
        messages=messages,
        options={"temperature": temperature},
        stream=True,
    )

    for chunk in stream:
        token: str = chunk["message"]["content"]
        accumulated.append(token)
        yield "".join(accumulated)


# ---------------------------------------------------------------------------
# Step 5 — Wire up the Gradio interface
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    """Build and return the Gradio Blocks application."""
    available_models = get_available_models()

    with gr.Blocks(title="Ollama Streaming Chat") as demo:
        gr.Markdown("## Ollama Streaming Chat")

        with gr.Row():
            model_dropdown = gr.Dropdown(
                choices=available_models,
                value=available_models[0] if available_models else None,
                label="Model",
                scale=3,
            )
            temperature_slider = gr.Slider(
                minimum=0.0,
                maximum=2.0,
                step=0.05,
                value=0.7,
                label="Temperature",
                scale=2,
            )

        gr.ChatInterface(
            fn=chat_stream,
            additional_inputs=[model_dropdown, temperature_slider],
            chatbot=gr.Chatbot(height=500),
            textbox=gr.Textbox(placeholder="Type your message here…", scale=7),
        )

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860)
