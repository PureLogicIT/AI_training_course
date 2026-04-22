"""
Exercise 1: Pipeline Playground
================================
A Gradio app that demonstrates the Hugging Face `pipeline()` API across three NLP tasks:
  - text-generation
  - summarization
  - question-answering

All inference runs locally on CPU using the `transformers` library.
No API keys or cloud services are used.

Your job: implement all sections marked with TODO.
"""

import gradio as gr
from transformers import pipeline

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Map task identifiers to their recommended small model Hub IDs.
# These models are pre-downloaded by download_models.py.
MODEL_IDS = {
    "text-generation": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    "summarization": "google/flan-t5-base",
    "question-answering": "deepset/roberta-base-squad2",
}

# Pipeline cache: keyed by task string to avoid reloading on every request.
_PIPELINES: dict = {}


# ---------------------------------------------------------------------------
# Step 2: Pipeline loader
# ---------------------------------------------------------------------------

def get_pipeline(task: str):
    """
    Return the loaded `pipeline` object for the given task.

    TODO:
      1. Look up the correct model ID for `task` from MODEL_IDS.
      2. If the pipeline is already cached in _PIPELINES, return it.
      3. Otherwise, create it with:
             pipeline(
                 task=task,
                 model=<model_id>,
                 device="cpu",
                 torch_dtype="float32",
             )
      4. Store the new pipeline in _PIPELINES[task].
      5. Return the pipeline.
    """
    # TODO: implement pipeline caching and loading
    raise NotImplementedError("get_pipeline() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 3: Text generation
# ---------------------------------------------------------------------------

def run_text_generation(prompt: str, max_new_tokens: int, temperature: float) -> str:
    """
    Run text-generation inference and return the generated text string.

    Args:
        prompt:         The user-supplied input text.
        max_new_tokens: Maximum number of tokens to generate.
        temperature:    Sampling temperature (0.1 = focused, 2.0 = random).

    Returns:
        The generated text (excluding the input prompt).

    TODO:
      1. Call get_pipeline("text-generation").
      2. Run the pipeline with:
             return_full_text=False,
             do_sample=True,
             max_new_tokens=max_new_tokens,
             temperature=temperature,
      3. Return result[0]["generated_text"].
    """
    if not prompt.strip():
        return "Please enter a prompt."

    # TODO: implement text generation
    raise NotImplementedError("run_text_generation() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 4: Summarization
# ---------------------------------------------------------------------------

def run_summarization(text: str, max_new_tokens: int) -> str:
    """
    Run summarization inference and return the summary string.

    Args:
        text:           The document or passage to summarise.
        max_new_tokens: Maximum length of the generated summary.

    Returns:
        The summary text.

    TODO:
      1. Call get_pipeline("summarization").
      2. Run the pipeline with max_new_tokens=max_new_tokens and do_sample=False.
      3. Return result[0]["summary_text"].
    """
    if not text.strip():
        return "Please enter text to summarise."

    # TODO: implement summarization
    raise NotImplementedError("run_summarization() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 5: Question answering
# ---------------------------------------------------------------------------

def run_question_answering(question: str, context: str) -> str:
    """
    Run extractive question-answering and return a formatted result string.

    Args:
        question: The question to answer.
        context:  The passage of text from which to extract the answer.

    Returns:
        A string like: "Answer: <answer>\\nConfidence: <score as percentage>"

    TODO:
      1. Call get_pipeline("question-answering").
      2. Run the pipeline: pipe(question=question, context=context).
         Note: this pipeline signature differs from text-generation and summarization.
      3. Return a string formatted as:
             f"Answer: {result['answer']}\\nConfidence: {result['score']:.2%}"
    """
    if not question.strip() or not context.strip():
        return "Please enter both a question and a context passage."

    # TODO: implement question answering
    raise NotImplementedError("run_question_answering() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 6: Gradio interface
# ---------------------------------------------------------------------------

def update_visibility(task: str):
    """
    Return gr.update() objects that show/hide components based on the selected task.

    Components to control:
      - prompt_input:       visible for text-generation and summarization
      - question_input:     visible only for question-answering
      - context_input:      visible only for question-answering
      - max_tokens_slider:  visible for text-generation and summarization
      - temperature_slider: visible only for text-generation

    TODO:
      Return a list of 5 gr.update() calls in this order:
        [prompt_input, question_input, context_input, max_tokens_slider, temperature_slider]
    """
    # TODO: implement visibility logic
    raise NotImplementedError("update_visibility() is not implemented yet.")


def run_inference(task: str, prompt: str, question: str, context: str,
                  max_new_tokens: int, temperature: float) -> str:
    """
    Route to the correct inference function based on the selected task.

    TODO:
      Use an if/elif block on `task` to call:
        - run_text_generation(prompt, max_new_tokens, temperature)
        - run_summarization(prompt, max_new_tokens)
        - run_question_answering(question, context)
      Return the result string.
    """
    # TODO: implement task routing
    raise NotImplementedError("run_inference() is not implemented yet.")


def build_interface() -> gr.Blocks:
    """
    Build and return the Gradio Blocks interface.

    TODO:
      1. Create a gr.Dropdown for task selection with choices:
             ["text-generation", "summarization", "question-answering"]
         Default: "text-generation".

      2. Create the following input components (some hidden by default):
           - prompt_input:       gr.Textbox, multi-line, visible=True
           - question_input:     gr.Textbox, single-line, visible=False
           - context_input:      gr.Textbox, multi-line, visible=False
           - max_tokens_slider:  gr.Slider(50, 500, value=150, step=50), visible=True
           - temperature_slider: gr.Slider(0.1, 2.0, value=0.7, step=0.1), visible=True

      3. Create a Submit button and an output gr.Textbox.

      4. Wire task_dropdown.change() to update_visibility() and update all 5 components.

      5. Wire submit_btn.click() to run_inference() with inputs:
             [task_dropdown, prompt_input, question_input, context_input,
              max_tokens_slider, temperature_slider]
         and output: [output_box].

      6. Return the gr.Blocks object (do NOT call .launch() here).
    """
    with gr.Blocks(title="Pipeline Playground") as demo:
        gr.Markdown("# Pipeline Playground\nRun local NLP inference with the Hugging Face `pipeline()` API.")

        # TODO: add all components and wire them up

        pass  # Remove this line when implementing

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo = build_interface()
    demo.launch(server_name="0.0.0.0", server_port=7860)
