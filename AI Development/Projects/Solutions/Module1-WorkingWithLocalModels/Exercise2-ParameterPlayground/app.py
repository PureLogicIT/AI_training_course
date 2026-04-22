"""
Exercise 2 — Parameter Tuning Playground (SOLUTION)
====================================================
"""

from __future__ import annotations

import os

import gradio as gr

from backends import OllamaBackend, LlamaCppBackend

OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "llama3.2")


# ---------------------------------------------------------------------------
# Step 3 — Parameter controls
# ---------------------------------------------------------------------------

def build_parameter_controls() -> dict[str, gr.components.Component]:
    """Create and return a dict of Gradio parameter control components."""
    return {
        "temperature": gr.Slider(
            minimum=0.0, maximum=2.0, step=0.05, value=0.7, label="Temperature"
        ),
        "top_p": gr.Slider(
            minimum=0.0, maximum=1.0, step=0.05, value=0.9, label="Top-P"
        ),
        "top_k": gr.Slider(
            minimum=1, maximum=200, step=1, value=40, label="Top-K"
        ),
        "repeat_penalty": gr.Slider(
            minimum=1.0, maximum=2.0, step=0.05, value=1.1, label="Repeat Penalty"
        ),
        "num_ctx": gr.Slider(
            minimum=512, maximum=16384, step=512, value=4096, label="Context Window (num_ctx)"
        ),
        "seed": gr.Number(
            value=-1, precision=0, label="Seed (-1 = random)"
        ),
    }


# ---------------------------------------------------------------------------
# Step 4 — run_inference()
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
    """Run inference and return (response_text, settings_summary_markdown)."""
    if not prompt.strip():
        return "Please enter a prompt.", ""

    # Build params dict — omit seed if -1 (random)
    params: dict = {
        "temperature": temperature,
        "top_p": top_p,
        "top_k": int(top_k),
        "repeat_penalty": repeat_penalty,
        "num_ctx": int(num_ctx),
    }
    if int(seed) != -1:
        params["seed"] = int(seed)

    # Instantiate backend
    try:
        if backend_choice == "llama-cpp-python":
            if not gguf_path.strip():
                return "Please enter the path to your GGUF model file.", ""
            backend = LlamaCppBackend(model_path=gguf_path.strip())
        else:
            backend = OllamaBackend(model=OLLAMA_MODEL, host=OLLAMA_HOST)

        result_text = backend.generate(prompt, params)
    except Exception as exc:
        return f"Error: {exc}", ""

    # Build settings summary
    seed_display = str(int(seed)) if int(seed) != -1 else "random"
    summary_rows = "\n".join(
        f"| `{k}` | `{v}` |" for k, v in params.items()
    )
    settings_summary = (
        f"### Settings Used\n"
        f"**Backend:** {backend.name}\n\n"
        f"| Parameter | Value |\n"
        f"|---|---|\n"
        f"{summary_rows}\n"
        f"| `seed` | `{seed_display}` |"
    )

    return result_text, settings_summary


# ---------------------------------------------------------------------------
# Step 5 — Full UI
# ---------------------------------------------------------------------------

def _toggle_gguf_visibility(choice: str) -> gr.update:
    return gr.update(visible=(choice == "llama-cpp-python"))


def build_ui() -> gr.Blocks:
    """Assemble and return the complete Gradio Blocks UI."""
    controls = build_parameter_controls()

    with gr.Blocks(title="Parameter Playground") as demo:
        gr.Markdown("## Model Parameter Tuning Playground")
        gr.Markdown(
            "Adjust inference parameters, enter a prompt, and click **Run** "
            "to see how each setting shapes the model's output."
        )

        with gr.Row():
            backend_radio = gr.Radio(
                choices=["Ollama", "llama-cpp-python"],
                value="Ollama",
                label="Backend",
                scale=2,
            )
            gguf_path_box = gr.Textbox(
                label="GGUF Model Path",
                placeholder="/path/to/model.Q4_K_M.gguf",
                visible=False,
                scale=3,
            )

        backend_radio.change(
            fn=_toggle_gguf_visibility,
            inputs=[backend_radio],
            outputs=[gguf_path_box],
        )

        prompt_box = gr.Textbox(
            label="Prompt",
            placeholder="Enter your prompt here…",
            lines=4,
        )

        with gr.Row():
            with gr.Column():
                controls["temperature"].render()
                controls["top_p"].render()
                controls["top_k"].render()
            with gr.Column():
                controls["repeat_penalty"].render()
                controls["num_ctx"].render()
                controls["seed"].render()

        run_btn = gr.Button("Run", variant="primary")

        with gr.Row():
            output_text = gr.Textbox(
                label="Model Output",
                lines=12,
                interactive=False,
                scale=3,
            )
            output_summary = gr.Markdown(
                label="Settings Used",
                value="*Run a prompt to see the settings summary.*",
            )

        run_btn.click(
            fn=run_inference,
            inputs=[
                prompt_box,
                backend_radio,
                gguf_path_box,
                controls["temperature"],
                controls["top_p"],
                controls["top_k"],
                controls["repeat_penalty"],
                controls["num_ctx"],
                controls["seed"],
            ],
            outputs=[output_text, output_summary],
        )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860)
