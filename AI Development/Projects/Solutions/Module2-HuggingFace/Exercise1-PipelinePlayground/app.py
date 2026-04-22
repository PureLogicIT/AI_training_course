"""
Exercise 1: Pipeline Playground — SOLUTION
==========================================
A Gradio app that demonstrates the Hugging Face `pipeline()` API across three NLP tasks:
  - text-generation
  - summarization
  - question-answering

All inference runs locally on CPU. No API keys or cloud services are used.
"""

import gradio as gr
from transformers import pipeline

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_IDS = {
    "text-generation": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    "summarization": "google/flan-t5-base",
    "question-answering": "deepset/roberta-base-squad2",
}

# Pipeline cache: keyed by task string to avoid reloading on every request.
_PIPELINES: dict = {}


# ---------------------------------------------------------------------------
# Pipeline loader
# ---------------------------------------------------------------------------

def get_pipeline(task: str):
    """
    Return the loaded `pipeline` object for the given task.
    Pipelines are cached after first load to avoid reloading on every request.
    """
    if task not in _PIPELINES:
        model_id = MODEL_IDS[task]
        print(f"Loading pipeline for task='{task}' with model='{model_id}'...")
        _PIPELINES[task] = pipeline(
            task=task,
            model=model_id,
            device="cpu",
            torch_dtype="float32",
        )
        print(f"Pipeline for '{task}' loaded and cached.")
    return _PIPELINES[task]


# ---------------------------------------------------------------------------
# Inference functions
# ---------------------------------------------------------------------------

def run_text_generation(prompt: str, max_new_tokens: int, temperature: float) -> str:
    """Run text-generation and return the generated text (prompt excluded)."""
    if not prompt.strip():
        return "Please enter a prompt."

    pipe = get_pipeline("text-generation")
    result = pipe(
        prompt,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=temperature,
        return_full_text=False,
    )
    return result[0]["generated_text"]


def run_summarization(text: str, max_new_tokens: int) -> str:
    """Run summarization and return the summary string."""
    if not text.strip():
        return "Please enter text to summarise."

    pipe = get_pipeline("summarization")
    result = pipe(
        text,
        max_new_tokens=max_new_tokens,
        do_sample=False,
    )
    return result[0]["summary_text"]


def run_question_answering(question: str, context: str) -> str:
    """Run extractive QA and return a formatted answer + confidence string."""
    if not question.strip() or not context.strip():
        return "Please enter both a question and a context passage."

    pipe = get_pipeline("question-answering")
    result = pipe(question=question, context=context)
    return f"Answer: {result['answer']}\nConfidence: {result['score']:.2%}"


# ---------------------------------------------------------------------------
# Gradio interface helpers
# ---------------------------------------------------------------------------

def update_visibility(task: str):
    """
    Return gr.update() objects to show/hide components based on selected task.

    Order matches the outputs list in the .change() wire-up:
      [prompt_input, question_input, context_input, max_tokens_slider, temperature_slider]
    """
    is_gen = task == "text-generation"
    is_sum = task == "summarization"
    is_qa = task == "question-answering"

    return [
        gr.update(visible=is_gen or is_sum),   # prompt_input
        gr.update(visible=is_qa),               # question_input
        gr.update(visible=is_qa),               # context_input
        gr.update(visible=is_gen or is_sum),    # max_tokens_slider
        gr.update(visible=is_gen),              # temperature_slider
    ]


def run_inference(task: str, prompt: str, question: str, context: str,
                  max_new_tokens: int, temperature: float) -> str:
    """Route to the correct inference function based on the selected task."""
    if task == "text-generation":
        return run_text_generation(prompt, max_new_tokens, temperature)
    elif task == "summarization":
        return run_summarization(prompt, max_new_tokens)
    elif task == "question-answering":
        return run_question_answering(question, context)
    else:
        return f"Unknown task: {task}"


# ---------------------------------------------------------------------------
# Gradio interface
# ---------------------------------------------------------------------------

def build_interface() -> gr.Blocks:
    """Build and return the Gradio Blocks interface."""
    with gr.Blocks(title="Pipeline Playground") as demo:
        gr.Markdown(
            "# Pipeline Playground\n"
            "Run local NLP inference with the Hugging Face `pipeline()` API. "
            "All models run on CPU — no cloud API calls.\n\n"
            "> First run for each task is slow (30–120 s) while the model loads. "
            "Subsequent runs reuse the cached pipeline."
        )

        with gr.Row():
            task_dropdown = gr.Dropdown(
                choices=["text-generation", "summarization", "question-answering"],
                value="text-generation",
                label="Task",
                info="Select the NLP task to run.",
            )

        # Shared input for text-generation and summarization
        prompt_input = gr.Textbox(
            label="Prompt / Document",
            placeholder="Enter your prompt or the text to process...",
            lines=5,
            visible=True,
        )

        # Inputs visible only for question-answering
        question_input = gr.Textbox(
            label="Question",
            placeholder="e.g. What is the capital of France?",
            visible=False,
        )
        context_input = gr.Textbox(
            label="Context Passage",
            placeholder="Paste the passage that contains the answer...",
            lines=5,
            visible=False,
        )

        with gr.Row():
            max_tokens_slider = gr.Slider(
                minimum=50,
                maximum=500,
                value=150,
                step=50,
                label="Max New Tokens",
                visible=True,
            )
            temperature_slider = gr.Slider(
                minimum=0.1,
                maximum=2.0,
                value=0.7,
                step=0.1,
                label="Temperature",
                info="Lower = more focused, Higher = more random. Only used for text-generation.",
                visible=True,
            )

        submit_btn = gr.Button("Submit", variant="primary")
        output_box = gr.Textbox(label="Output", lines=8, interactive=False)

        # Wire task dropdown change to show/hide components
        task_dropdown.change(
            fn=update_visibility,
            inputs=[task_dropdown],
            outputs=[prompt_input, question_input, context_input,
                     max_tokens_slider, temperature_slider],
        )

        # Wire submit button to inference
        submit_btn.click(
            fn=run_inference,
            inputs=[task_dropdown, prompt_input, question_input, context_input,
                    max_tokens_slider, temperature_slider],
            outputs=[output_box],
        )

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo = build_interface()
    demo.launch(server_name="0.0.0.0", server_port=7860)
