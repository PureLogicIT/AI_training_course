"""
Exercise 3: Model Benchmark & Comparison — SOLUTION
====================================================
A Gradio app for benchmarking multiple local Hugging Face models.
Collects response text, generation time, tokens/sec, and peak RAM usage.
"""

import csv
import json
import tempfile
from threading import Thread

import gradio as gr
from benchmark_engine import AVAILABLE_MODELS, run_benchmark

DEFAULT_PROMPTS_JSON = json.dumps(
    [
        "Explain what a Python generator is and give a one-line example.",
        "What is the difference between a process and a thread?",
        "Write a haiku about running AI models on a laptop.",
    ],
    indent=2,
)

RESULT_COLUMNS = [
    "model",
    "prompt_preview",
    "output_tokens",
    "gen_time_s",
    "tokens_per_sec",
    "peak_ram_mb",
]


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

def load_prompts_from_json(json_text: str) -> list:
    """Parse a JSON string and return a list of prompt strings."""
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    if not isinstance(data, list):
        raise ValueError("Expected a JSON array at the top level.")

    prompts = []
    for item in data:
        if isinstance(item, str):
            prompts.append(item)
        elif isinstance(item, dict):
            if "prompt" not in item:
                raise ValueError(
                    f"Object items must have a 'prompt' key. Got: {list(item.keys())}"
                )
            prompts.append(item["prompt"])
        else:
            raise ValueError(
                f"Each item must be a string or a dict with a 'prompt' key. Got: {type(item)}"
            )

    return prompts


# ---------------------------------------------------------------------------
# CSV exporter
# ---------------------------------------------------------------------------

def save_results_csv(results: list) -> str:
    """Write results to a temporary CSV file and return the path."""
    fieldnames = [
        "model_id", "model_short_name", "prompt_preview",
        "input_tokens", "output_tokens", "generation_time_s",
        "tokens_per_sec", "peak_ram_mb", "load_time_s", "load_ram_mb",
        "response_text",
    ]

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    )
    writer = csv.DictWriter(tmp, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(results)
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# Gradio generator handler
# ---------------------------------------------------------------------------

def run_benchmark_ui(model_choices: list, max_new_tokens: int, prompts_json: str):
    """
    Generator function wired to the Run Benchmark button.
    Yields (status_str, dataframe_rows_or_None, csv_path_or_None).
    """
    # Validate inputs
    if not model_choices:
        yield "Please select at least one model.", None, None
        return

    try:
        prompts = load_prompts_from_json(prompts_json)
    except ValueError as e:
        yield f"Prompt JSON error: {e}", None, None
        return

    if not prompts:
        yield "No prompts found. Please add at least one prompt.", None, None
        return

    yield (
        f"Starting benchmark: {len(model_choices)} model(s), {len(prompts)} prompt(s)...",
        None,
        None,
    )

    # Collect results using a thread + shared list so we can yield progress
    results = []
    status_messages = []
    benchmark_complete = [False]
    benchmark_error = [None]

    def _callback(msg: str) -> None:
        status_messages.append(msg)

    def _run() -> None:
        try:
            r = run_benchmark(
                model_ids=model_choices,
                prompts=prompts,
                max_new_tokens=max_new_tokens,
                progress_callback=_callback,
            )
            results.extend(r)
        except Exception as e:
            benchmark_error[0] = str(e)
        finally:
            benchmark_complete[0] = True

    thread = Thread(target=_run, daemon=True)
    thread.start()

    # Poll for status updates while the thread runs
    last_msg_index = 0
    import time
    while not benchmark_complete[0]:
        time.sleep(0.5)
        new_msgs = status_messages[last_msg_index:]
        if new_msgs:
            last_msg_index = len(status_messages)
            yield new_msgs[-1], None, None

    thread.join()

    if benchmark_error[0]:
        yield f"Benchmark failed: {benchmark_error[0]}", None, None
        return

    if not results:
        yield "Benchmark complete but no results were collected.", None, None
        return

    # Build dataframe rows
    dataframe_rows = [
        [
            r["model_short_name"],
            r["prompt_preview"],
            r["output_tokens"],
            r["generation_time_s"],
            r["tokens_per_sec"],
            r["peak_ram_mb"],
        ]
        for r in results
    ]

    csv_path = save_results_csv(results)

    yield (
        f"Benchmark complete! {len(results)} result(s). CSV saved.",
        dataframe_rows,
        csv_path,
    )


# ---------------------------------------------------------------------------
# Gradio interface
# ---------------------------------------------------------------------------

def build_interface() -> gr.Blocks:
    """Build and return the Gradio Blocks interface."""
    model_ids = list(AVAILABLE_MODELS.keys())

    with gr.Blocks(title="Model Benchmark") as demo:
        gr.Markdown(
            "# Model Benchmark & Comparison\n"
            "Run prompts through multiple local Hugging Face models and compare "
            "speed, throughput, and memory usage. All inference runs on CPU.\n\n"
            "> Each model requires 4–7 GB of RAM. Select one model at a time "
            "if you have less than 16 GB of available RAM."
        )

        gr.Markdown("## Configuration")

        with gr.Row():
            model_selector = gr.CheckboxGroup(
                choices=model_ids,
                value=model_ids[:1],  # default: only first model selected
                label="Models to Benchmark",
                info="Select which models to include in the benchmark run.",
            )

        with gr.Row():
            max_tokens_slider = gr.Slider(
                minimum=50,
                maximum=500,
                value=150,
                step=50,
                label="Max New Tokens",
                info="Maximum tokens to generate per prompt per model.",
            )

        prompt_editor = gr.Code(
            language="json",
            value=DEFAULT_PROMPTS_JSON,
            label='Test Prompts (JSON array of strings, or [{"prompt": "..."}, ...])',
        )

        run_btn = gr.Button("Run Benchmark", variant="primary", size="lg")

        gr.Markdown("## Progress")
        status_box = gr.Textbox(
            label="Status",
            interactive=False,
            lines=3,
        )

        gr.Markdown("## Results")
        results_table = gr.Dataframe(
            headers=RESULT_COLUMNS,
            label="Benchmark Results",
            interactive=False,
        )
        csv_download = gr.File(label="Download Full Results CSV")

        run_btn.click(
            fn=run_benchmark_ui,
            inputs=[model_selector, max_tokens_slider, prompt_editor],
            outputs=[status_box, results_table, csv_download],
        )

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo = build_interface()
    demo.launch(server_name="0.0.0.0", server_port=7860)
