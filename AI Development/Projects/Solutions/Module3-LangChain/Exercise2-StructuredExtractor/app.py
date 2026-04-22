"""
Exercise 2 — Structured Data Extraction with PydanticOutputParser  (SOLUTION)
==============================================================================
A Gradio application that extracts structured data from unstructured text using
PydanticOutputParser and OutputFixingParser, showing the raw and parsed output
side by side.

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
# TODO 2 — Build the extraction chain (SOLUTION)
# ---------------------------------------------------------------------------

def build_extraction_chain(schema_name: str, model_name: str):
    """
    Return a RunnableParallel chain that produces:
        {"raw": <str>, "parsed": <PydanticModel instance>}
    """
    pydantic_class = SCHEMA_MAP[schema_name]

    llm = ChatOllama(
        model=model_name,
        temperature=0.0,
        num_ctx=4096,
        base_url=OLLAMA_HOST,
    )

    # Base parser generates format instructions and validates parsed JSON
    base_parser = PydanticOutputParser(pydantic_object=pydantic_class)

    # OutputFixingParser: on parse failure, asks the model to repair the JSON
    fixing_parser = OutputFixingParser.from_llm(parser=base_parser, llm=llm)

    prompt = ChatPromptTemplate.from_messages([
        ("system", EXTRACTION_SYSTEM_PROMPT),
        ("human", "Extract information from this text:\n\n{text}"),
    ]).partial(format_instructions=base_parser.get_format_instructions())

    # Run the chain up to (but not including) the parser so we can capture raw output
    pre_parse_chain = prompt | llm

    # Run both the str parser and the fixing parser on the same AIMessage
    dual_chain = pre_parse_chain | RunnableParallel(
        raw=StrOutputParser(),
        parsed=fixing_parser,
    )

    return dual_chain


# ---------------------------------------------------------------------------
# TODO 3 — Run extraction (SOLUTION)
# ---------------------------------------------------------------------------

def run_extraction(
    text: str,
    schema_name: str,
    model_name: str,
) -> tuple[str, Optional[Any]]:
    """Invoke the extraction chain; return (raw_str, parsed_object_or_None)."""
    if not text.strip():
        return ("Please paste some text to extract from.", None)

    try:
        chain = build_extraction_chain(schema_name, model_name)
        result = chain.invoke({"text": text})
        return result["raw"], result["parsed"]
    except Exception as exc:
        # OutputFixingParser exhausted its retries — return raw if available
        raw_fallback = str(exc)
        return raw_fallback, None


# ---------------------------------------------------------------------------
# TODO 4 — Format the parsed object for display (SOLUTION)
# ---------------------------------------------------------------------------

def format_parsed(parsed_object: Optional[Any]) -> str:
    """Convert a Pydantic model instance to an indented JSON string."""
    if parsed_object is None:
        return "[Parser failed — see raw output for the model's response]"
    return json.dumps(parsed_object.model_dump(), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Gradio event handler
# ---------------------------------------------------------------------------

def handle_extract(text: str, schema_name: str, model_name: str) -> tuple[str, str]:
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

        # TODO 5 — Wire up events (SOLUTION)
        extract_btn.click(
            fn=handle_extract,
            inputs=[input_text, schema_radio, model_dropdown],
            outputs=[raw_output_box, parsed_output_box],
        )

        clear_btn.click(
            fn=lambda: ("", "", ""),
            inputs=[],
            outputs=[input_text, raw_output_box, parsed_output_box],
        )

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
