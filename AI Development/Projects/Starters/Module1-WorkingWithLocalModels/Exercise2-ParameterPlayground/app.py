"""
Exercise 2 — Parameter Tuning Playground
=========================================
A Gradio app for experimenting with Ollama / llama-cpp-python inference
parameters in real time.

Complete every TODO in order. Each TODO maps to a numbered step in the
exercise instructions.
"""

from __future__ import annotations

import os

import gradio as gr

from backends import OllamaBackend, LlamaCppBackend

OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "llama3.2")


# ---------------------------------------------------------------------------
# TODO 3 — Build the parameter controls
# ---------------------------------------------------------------------------

def build_parameter_controls() -> dict[str, gr.components.Component]:
    """Create and return a dict of Gradio parameter control components.

    Keys must be: "temperature", "top_p", "top_k", "repeat_penalty",
                  "num_ctx", "seed"

    See the exercise instructions for the required range, step, and default
    value for each control.
    """
    # TODO 3: Replace each None with the appropriate gr.Slider or gr.Number.
    return {
        "temperature": None,   # gr.Slider(0.0, 2.0, step=0.05, value=0.7, ...)
        "top_p":       None,   # gr.Slider(0.0, 1.0, step=0.05, value=0.9, ...)
        "top_k":       None,   # gr.Slider(1, 200, step=1, value=40, ...)
        "repeat_penalty": None,# gr.Slider(1.0, 2.0, step=0.05, value=1.1, ...)
        "num_ctx":     None,   # gr.Slider(512, 16384, step=512, value=4096, ...)
        "seed":        None,   # gr.Number(value=-1, precision=0, ...)
    }


# ---------------------------------------------------------------------------
# TODO 4 — Implement run_inference()
# ---------------------------------------------------------------------------

def run_inference(
    prompt: str,
    backend_choice: str,
    gguf_path: str,
    temperature: float,
    top_p: float,
    top_k: int,
    repeat_penalty: float,
    num_ctx: int,
    seed: int,
) -> tuple[str, str]:
    """Run inference with the selected backend and return output + summary.

    Args:
        prompt:         The user's prompt text.
        backend_choice: "Ollama" or "llama-cpp-python".
        gguf_path:      Path to the GGUF file (used only for llama-cpp-python).
        temperature:    Sampling temperature.
        top_p:          Nucleus sampling threshold.
        top_k:          Top-k sampling limit.
        repeat_penalty: Repetition penalty multiplier.
        num_ctx:        Context window size in tokens.
        seed:           RNG seed (-1 means random, omit from params dict).

    Returns:
        A tuple of (response_text, settings_summary_markdown).
    """
    # TODO 4a: Build the params dict from the parameter arguments.
    #          Omit "seed" from the dict if seed == -1.
    params: dict = {}

    # TODO 4b: Instantiate the correct backend based on backend_choice.
    #          Use OLLAMA_HOST and OLLAMA_MODEL for OllamaBackend.
    backend = None

    # TODO 4c: Call backend.generate(prompt, params) and capture result_text.
    result_text = ""

    # TODO 4d: Build a Markdown settings summary string.
    #          Include: backend name, all param names + values.
    settings_summary = ""

    return result_text, settings_summary


# ---------------------------------------------------------------------------
# TODO 5 — Wire up the full Gradio layout
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    """Assemble and return the complete Gradio Blocks UI."""
    controls = build_parameter_controls()

    with gr.Blocks(title="Parameter Playground") as demo:
        gr.Markdown("## Model Parameter Tuning Playground")

        with gr.Row():
            # TODO 5a: Add a gr.Radio for backend selection
            # Choices: ["Ollama", "llama-cpp-python"], default "Ollama"
            backend_radio = None  # replace with gr.Radio(...)

            # TODO 5b: Add a gr.Textbox for the GGUF file path
            # Start with visible=False; show only when llama-cpp-python is selected
            gguf_path_box = None  # replace with gr.Textbox(visible=False, ...)

        # TODO 5c: Add a .change() handler on backend_radio that toggles
        # gguf_path_box visibility. When choice is "llama-cpp-python" return
        # gr.update(visible=True), otherwise gr.update(visible=False).

        # TODO 5d: Add a multiline prompt textbox (lines=4)
        prompt_box = None  # replace with gr.Textbox(...)

        # TODO 5e: Place the six parameter controls in two columns
        with gr.Row():
            with gr.Column():
                pass  # place temperature, top_p, top_k here
            with gr.Column():
                pass  # place repeat_penalty, num_ctx, seed here

        # TODO 5f: Add a Run button
        run_btn = None  # replace with gr.Button(...)

        with gr.Row():
            # TODO 5g: Add output components side by side
            output_text = None    # gr.Textbox(label="Model Output", ...)
            output_summary = None # gr.Markdown(label="Settings Used")

        # TODO 5h: Wire run_btn.click() to run_inference()
        # inputs: [prompt_box, backend_radio, gguf_path_box,
        #          controls["temperature"], controls["top_p"], controls["top_k"],
        #          controls["repeat_penalty"], controls["num_ctx"], controls["seed"]]
        # outputs: [output_text, output_summary]

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860)
