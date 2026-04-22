"""
Exercise 2 — Structured Data Extraction with PydanticOutputParser  (STARTER)
=============================================================================
Complete every TODO to make the application work.

Run:  python app.py
Then open http://localhost:7860 in your browser.
"""

import json
import os
import subprocess
from typing import Any, Optional

import httpx
import gradio as gr
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import RunnableParallel
from langchain.output_parsers import OutputFixingParser

from schemas import JobPosting, ProductDescription, EventAnnouncement


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Maps the UI radio label to the Pydantic class
SCHEMA_MAP: dict[str, type] = {
    "Job Posting": JobPosting,
    "Product Description": ProductDescription,
    "Event Announcement": EventAnnouncement,
}

EXTRACTION_SYSTEM_PROMPT = (
    "You are a data extraction assistant. "
    "Extract the requested fields from the provided text. "
    "Respond ONLY with valid JSON that matches the schema exactly. "
    "Do not add any explanation, preamble, or markdown code fences.\n\n"
    "{format_instructions}"
)


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
# TODO 2 — Build the extraction chain for a given schema and model
# ---------------------------------------------------------------------------

def build_extraction_chain(schema_name: str, model_name: str):
    """
    Return a RunnableParallel chain that produces:
        {"raw": <str>, "parsed": <PydanticModel instance>}

    Steps to implement:
    1. Select the Pydantic class from SCHEMA_MAP using schema_name.
    2. Create a PydanticOutputParser for the selected class.
    3. Wrap it with OutputFixingParser.from_llm(parser=base_parser, llm=llm).
    4. Build the ChatPromptTemplate and call .partial(format_instructions=...).
    5. Build pre_parse_chain = prompt | llm
    6. Return pre_parse_chain | RunnableParallel(
           raw=StrOutputParser(),
           parsed=fixing_parser,
       )

    Use temperature=0.0 and num_ctx=4096 for the ChatOllama instance.
    """
    # YOUR CODE HERE
    pass  # replace with your implementation


# ---------------------------------------------------------------------------
# TODO 3 — Run extraction and return (raw_str, parsed_object_or_None)
# ---------------------------------------------------------------------------

def run_extraction(
    text: str,
    schema_name: str,
    model_name: str,
) -> tuple[str, Optional[Any]]:
    """
    Invoke the extraction chain and return a tuple:
        (raw_model_output: str, parsed_object or None)

    If parsing fails after the OutputFixingParser's retry, catch the
    exception and return (raw_output, None).

    Hint: The chain returns a dict with keys "raw" and "parsed".
    """
    if not text.strip():
        return ("Please paste some text to extract from.", None)

    # YOUR CODE HERE
    pass  # replace with your implementation


# ---------------------------------------------------------------------------
# TODO 4 — Format the parsed Pydantic object for display
# ---------------------------------------------------------------------------

def format_parsed(parsed_object: Optional[Any]) -> str:
    """
    Convert a Pydantic model instance to an indented JSON string.
    If parsed_object is None, return a clear error message string.

    Use: json.dumps(parsed_object.model_dump(), indent=2, ensure_ascii=False)
    """
    # YOUR CODE HERE
    pass  # replace with your implementation


# ---------------------------------------------------------------------------
# Gradio event handler (glue between UI and extraction logic)
# ---------------------------------------------------------------------------

def handle_extract(text: str, schema_name: str, model_name: str) -> tuple[str, str]:
    """Called by the Gradio Submit button."""
    raw, parsed_obj = run_extraction(text, schema_name, model_name)
    formatted = format_parsed(parsed_obj)
    return raw, formatted


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Structured Data Extractor") as demo:
        gr.Markdown("## Structured Data Extraction")
        gr.Markdown(
            "Paste unstructured text, choose the extraction schema, "
            "and click **Extract** to see the raw model output and parsed result."
        )

        with gr.Row():
            with gr.Column(scale=1):
                schema_radio = gr.Radio(
                    label="Extraction Schema",
                    choices=list(SCHEMA_MAP.keys()),
                    value="Job Posting",
                )
                model_dropdown = gr.Dropdown(
                    label="Model",
                    choices=AVAILABLE_MODELS,
                    value=AVAILABLE_MODELS[0],
                )
                with gr.Row():
                    extract_btn = gr.Button("Extract", variant="primary")
                    clear_btn = gr.Button("Clear")

            with gr.Column(scale=2):
                input_text = gr.Textbox(
                    label="Input Text",
                    lines=10,
                    placeholder="Paste a job posting, product description, or event announcement here...",
                )

        with gr.Row():
            raw_output_box = gr.Textbox(
                label="Raw Model Output",
                lines=12,
                interactive=False,
                placeholder="The model's exact response will appear here...",
            )
            parsed_output_box = gr.Code(
                label="Parsed Result (JSON)",
                language="json",
                lines=12,
                interactive=False,
            )

        # ------------------------------------------------------------------
        # TODO 5 — Wire up the button click events
        # ------------------------------------------------------------------
        # Connect extract_btn.click to handle_extract:
        #   inputs  = [input_text, schema_radio, model_dropdown]
        #   outputs = [raw_output_box, parsed_output_box]
        #
        # Connect clear_btn.click to reset input_text, raw_output_box,
        # and parsed_output_box to empty strings.
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
