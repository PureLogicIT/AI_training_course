"""
Exercise 1 — LangChain LCEL Q&A Chain with Gradio
===================================================
Starter file: complete every TODO to make the application work.

Run:  python app.py
Then open http://localhost:7860 in your browser.
"""

import os
import subprocess
from typing import Generator

import httpx
import gradio as gr
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Allow the Ollama server URL to be overridden via environment variable.
# This is important when running inside Docker (see README).
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

DEFAULT_SYSTEM_PROMPT = (
    "You are a knowledgeable and concise assistant. "
    "Answer the user's question clearly and directly."
)


# ---------------------------------------------------------------------------
# Helper: discover locally available Ollama models
# ---------------------------------------------------------------------------

def list_ollama_models() -> list[str]:
    """
    Return the names of models currently pulled in Ollama.
    Falls back to ["llama3.2"] if the Ollama CLI is unavailable.
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = result.stdout.strip().splitlines()
        # First line is a header ("NAME   ID   SIZE   MODIFIED")
        model_names: list[str] = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                # Strip the ":latest" tag that Ollama appends by default
                name = parts[0].replace(":latest", "")
                model_names.append(name)
        return model_names if model_names else ["llama3.2"]
    except Exception:
        return ["llama3.2"]


AVAILABLE_MODELS = list_ollama_models()


# ---------------------------------------------------------------------------
# Core handler — wires the LCEL chain and streams the response
# ---------------------------------------------------------------------------

def answer_question(
    system_prompt: str,
    user_message: str,
    model_name: str,
) -> Generator[str, None, None]:
    """
    Build an LCEL chain and stream its response into the Gradio output box.

    Parameters
    ----------
    system_prompt : str
        The system-role text entered by the user in the UI.
    user_message : str
        The question typed by the user.
    model_name : str
        The Ollama model selected in the dropdown.

    Yields
    ------
    str
        Accumulated response text after each streamed token.
    """
    if not user_message.strip():
        yield "Please enter a question."
        return

    # ------------------------------------------------------------------
    # TODO 1 — Instantiate ChatOllama
    # ------------------------------------------------------------------
    # Create a ChatOllama instance using:
    #   - model=model_name          (from the dropdown)
    #   - temperature=0.7
    #   - num_ctx=4096
    #   - base_url=OLLAMA_HOST      (so Docker can reach the host)
    #
    # Store it in a variable called `llm`.
    # ------------------------------------------------------------------
    # YOUR CODE HERE
    llm = None  # replace this line
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # TODO 2 — Build the LCEL chain
    # ------------------------------------------------------------------
    # Compose the three-step chain using the pipe operator:
    #
    #   ChatPromptTemplate.from_messages([
    #       ("system", system_prompt),
    #       ("human", "{question}"),
    #   ]) | llm | StrOutputParser()
    #
    # Store the result in a variable called `chain`.
    # ------------------------------------------------------------------
    # YOUR CODE HERE
    chain = None  # replace this line
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # TODO 3 — Stream the response
    # ------------------------------------------------------------------
    # Use chain.stream({"question": user_message}) to get a token
    # generator, accumulate each chunk into a string, and yield the
    # growing string so Gradio updates the output box incrementally.
    #
    # Pattern:
    #   accumulated = ""
    #   for chunk in chain.stream(...):
    #       accumulated += chunk
    #       yield accumulated
    # ------------------------------------------------------------------
    # YOUR CODE HERE
    # ------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Gradio UI definition
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    with gr.Blocks(title="LangChain LCEL Q&A") as demo:
        gr.Markdown("## LangChain LCEL Q&A Chain")
        gr.Markdown(
            "Enter a system prompt, choose a model, type your question, "
            "and click **Submit** to stream a response."
        )

        with gr.Row():
            with gr.Column(scale=1):
                system_prompt_box = gr.Textbox(
                    label="System Prompt",
                    value=DEFAULT_SYSTEM_PROMPT,
                    lines=4,
                    placeholder="Describe the assistant's persona and behaviour...",
                )
                model_dropdown = gr.Dropdown(
                    label="Model",
                    choices=AVAILABLE_MODELS,
                    value=AVAILABLE_MODELS[0],
                )
                with gr.Row():
                    submit_btn = gr.Button("Submit", variant="primary")
                    clear_btn = gr.Button("Clear")

            with gr.Column(scale=2):
                user_input_box = gr.Textbox(
                    label="Your Question",
                    lines=3,
                    placeholder="Type your question here...",
                )
                output_box = gr.Textbox(
                    label="Response",
                    lines=15,
                    interactive=False,
                    placeholder="The model's response will appear here...",
                )

        # ------------------------------------------------------------------
        # TODO 4 — Wire up the button click events
        # ------------------------------------------------------------------
        # Connect submit_btn.click to answer_question with:
        #   inputs  = [system_prompt_box, user_input_box, model_dropdown]
        #   outputs = [output_box]
        #
        # Connect clear_btn.click to a lambda that returns ("", "")
        # with outputs = [user_input_box, output_box]
        # ------------------------------------------------------------------
        # YOUR CODE HERE
        # ------------------------------------------------------------------

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Quick reachability check — fail early with a clear message.
    try:
        httpx.get(OLLAMA_HOST, timeout=3.0)
    except httpx.ConnectError:
        print(f"ERROR: Cannot reach Ollama at {OLLAMA_HOST}")
        print("Start Ollama with:  ollama serve")
        raise SystemExit(1)

    app = build_ui()
    app.launch(server_name="0.0.0.0", server_port=7860)
