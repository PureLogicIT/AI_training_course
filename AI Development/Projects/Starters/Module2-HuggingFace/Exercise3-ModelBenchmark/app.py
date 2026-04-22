"""
Exercise 3: Model Benchmark & Comparison
=========================================
A Gradio app for benchmarking multiple local Hugging Face models on a set of prompts.
Collects response text, generation time, tokens/sec, and peak RAM usage.

Your job: implement all TODO sections.
"""

import csv
import json
import tempfile

import gradio as gr
from benchmark_engine import AVAILABLE_MODELS, run_benchmark

# Default prompts shown in the UI on startup (loaded from JSON file)
DEFAULT_PROMPTS_JSON = json.dumps(
    [
        "Explain what a Python generator is and give a one-line example.",
        "What is the difference between a process and a thread?",
        "Write a haiku about running AI models on a laptop.",
    ],
    indent=2,
)

# Table column names for the results dataframe
RESULT_COLUMNS = [
    "model",
    "prompt_preview",
    "output_tokens",
    "gen_time_s",
    "tokens_per_sec",
    "peak_ram_mb",
]


# ---------------------------------------------------------------------------
# Step 2: Prompt loader
# ---------------------------------------------------------------------------

def load_prompts_from_json(json_text: str) -> list:
    """
    Parse a JSON string and return a list of prompt strings.

    Accepts two formats:
      - Array of strings:  ["prompt1", "prompt2"]
      - Array of objects:  [{"prompt": "prompt1"}, {"prompt": "prompt2"}]

    Args:
        json_text: A JSON string.

    Returns:
        List of prompt strings.

    Raises:
        ValueError: If json_text is not valid JSON or has an unexpected structure.

    TODO:
      1. json.loads(json_text) — wrap in try/except json.JSONDecodeError.
      2. If result is not a list, raise ValueError.
      3. If items are strings, return as-is.
      4. If items are dicts, extract item["prompt"] for each.
      5. Raise ValueError for any other item type.
    """
    # TODO: implement load_prompts_from_json
    raise NotImplementedError("load_prompts_from_json() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 4: CSV exporter
# ---------------------------------------------------------------------------

def save_results_csv(results: list) -> str:
    """
    Write benchmark results to a temporary CSV file and return the file path.

    Args:
        results: List of result dicts from run_benchmark().

    Returns:
        Absolute path to the written CSV file.

    TODO:
      1. Create a NamedTemporaryFile with suffix=".csv", delete=False, mode="w", newline="".
      2. Define fieldnames list (all keys you want in the CSV).
      3. Write header and rows with csv.DictWriter, using extrasaction="ignore".
      4. Close the file and return its name (the path string).
    """
    # TODO: implement save_results_csv
    raise NotImplementedError("save_results_csv() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 3: Gradio interface
# ---------------------------------------------------------------------------

def run_benchmark_ui(model_choices: list, max_new_tokens: int, prompts_json: str):
    """
    Generator function for the Run Benchmark button click.

    Yields (status_str, dataframe_rows, file_path) tuples.
    The first several yields update only the status textbox.
    The final yield populates all three outputs.

    TODO:
      1. Parse prompts with load_prompts_from_json(); on error yield an error status and return.
      2. Validate that model_choices is non-empty; yield error and return if empty.
      3. Yield ("Starting benchmark...", None, None) immediately.
      4. Collect status messages and results by either:
           a. Running run_benchmark() with a progress_callback that stores messages, OR
           b. Refactoring to iterate a generator version of run_benchmark().
         For each progress update, yield (status_msg, None, None).
      5. After all results are collected:
           a. Build dataframe_rows: list of lists matching RESULT_COLUMNS order.
           b. Call save_results_csv(results) to get the CSV file path.
           c. Yield (final_status, dataframe_rows, csv_path).
    """
    # TODO: implement run_benchmark_ui generator
    yield "Not implemented yet.", None, None
    raise NotImplementedError("run_benchmark_ui() is not implemented yet.")


def build_interface() -> gr.Blocks:
    """
    Build and return the Gradio Blocks interface.

    TODO:
      Section 1 — Configuration:
        - model_selector: gr.CheckboxGroup of AVAILABLE_MODELS.keys(), default first two
        - max_tokens_slider: gr.Slider(50, 500, value=150, step=50)
        - prompt_editor: gr.Code(language="json", value=DEFAULT_PROMPTS_JSON)
        - run_btn: gr.Button("Run Benchmark", variant="primary")

      Section 2 — Progress:
        - status_box: gr.Textbox(label="Status", interactive=False)

      Section 3 — Results:
        - results_table: gr.Dataframe(headers=RESULT_COLUMNS, interactive=False)
        - csv_download: gr.File(label="Download CSV")

      Wire run_btn.click() to run_benchmark_ui with:
        inputs=[model_selector, max_tokens_slider, prompt_editor]
        outputs=[status_box, results_table, csv_download]
    """
    model_ids = list(AVAILABLE_MODELS.keys())

    with gr.Blocks(title="Model Benchmark") as demo:
        gr.Markdown(
            "# Model Benchmark & Comparison\n"
            "Run a set of prompts through multiple local models and compare "
            "speed, throughput, and memory usage. All inference runs on CPU.\n\n"
            "> Warning: each model loads ~4–7 GB of RAM. Run one model at a time "
            "if your system has less than 16 GB of RAM."
        )

        # TODO: add all UI components and wire the button

        pass  # Remove when implementing

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo = build_interface()
    demo.launch(server_name="0.0.0.0", server_port=7860)
