# Exercise 1: Pipeline Playground

> **Module:** Module 2 — Hugging Face & Local Models
> **Difficulty:** Beginner
> **Estimated Time:** 60–90 minutes
> **Concepts Practiced:** `pipeline()` API, task selection, generation parameters (`max_new_tokens`, `temperature`), Gradio UI, local-only inference, Docker

---

## Scenario

You have joined a small engineering team that is evaluating whether Hugging Face's `transformers` library can replace their existing cloud-based NLP pipeline. Before committing to any specific model, the team wants an interactive sandbox where non-technical stakeholders can try three tasks — text generation, summarization, and question answering — against a locally running model, tune basic parameters, and see results immediately. Your job is to build that sandbox as a Gradio web app that runs entirely locally with no API calls.

---

## Learning Objectives

By completing this exercise you will be able to:

1. Instantiate a `transformers` `pipeline()` for three different NLP task types using appropriate models for each.
2. Pass `max_new_tokens` and `temperature` as runtime generation parameters through the `pipeline()` call.
3. Handle the structural differences in pipeline output between text-generation, summarization, and question-answering tasks.
4. Build a Gradio interface with dropdowns, sliders, and conditional input visibility.
5. Package the app in a Docker container that mounts a host-side Hugging Face model cache as a volume.

---

## Background

The `pipeline()` function is the fastest entry point into the `transformers` library. It handles tokenization, model loading, batching, and decoding transparently. However, different tasks use structurally different models and return results in different shapes:

- **`text-generation`** — causal LM (GPT-style); returns `[{"generated_text": "..."}]`
- **`summarization`** — encoder-decoder (T5/BART-style); returns `[{"summary_text": "..."}]`
- **`question-answering`** — extractive BERT-style; requires both a `question` and a `context`; returns `{"answer": "...", "score": ...}`

Your app must route to the right pipeline and extract the right output key for each task.

**Important CPU rules** (from the module):
- Always pass `device="cpu"` explicitly.
- Always pass `torch_dtype="float32"` — never `float16` or `"auto"` on CPU-only machines.
- Load each pipeline once at startup and reuse it; do not reload on every request.

---

## Recommended Models

These are small, Apache-2.0–licensed models suited for CPU inference. Download them before starting (or let the app download on first run — first run will be slow):

| Task | Model Hub ID | Approx. Download Size |
|---|---|---|
| `text-generation` | `HuggingFaceTB/SmolLM2-1.7B-Instruct` | ~3.4 GB (float16 safetensors) |
| `summarization` | `google/flan-t5-base` | ~1 GB |
| `question-answering` | `deepset/roberta-base-squad2` | ~500 MB |

To pre-download all three models to a local cache directory, run:

```bash
# From within the project directory with your venv active
python download_models.py
```

The `download_models.py` script is provided in the starter project.

---

## Project Structure

```
Exercise1-PipelinePlayground/
├── app.py                  # Main Gradio application (your primary task)
├── download_models.py      # One-time model downloader (provided)
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
└── README.md               # Run instructions
```

---

## Instructions

### Step 1: Understand the starter

Open `app.py` and read through all the TODO comments. The file is structured in four sections:

1. **Imports and constants** — model IDs and cache directory
2. **Model loading** — lazy-loaded pipeline cache (`_PIPELINES` dict)
3. **Inference functions** — one per task
4. **Gradio UI** — the interface definition

### Step 2: Implement `get_pipeline()`

This function takes a task name string and returns the matching loaded `pipeline` object. It must:

- Look up the correct model ID for the given task from the `MODEL_IDS` dict.
- Check if the pipeline is already cached in `_PIPELINES`; if so, return it (avoiding reload on every request).
- If not cached, create the pipeline with `device="cpu"` and `torch_dtype="float32"`, store it in `_PIPELINES`, and return it.

### Step 3: Implement `run_text_generation()`

This function receives `prompt`, `max_new_tokens`, and `temperature` from the UI and must:

- Call `get_pipeline("text-generation")`.
- Run the pipeline with `return_full_text=False`, `do_sample=True`, and the provided `max_new_tokens` and `temperature`.
- Return the string from `result[0]["generated_text"]`.

### Step 4: Implement `run_summarization()`

This function receives `text` and `max_new_tokens` and must:

- Call `get_pipeline("summarization")`.
- Run the pipeline with `max_new_tokens` as the `max_new_tokens` parameter.
- Return the string from `result[0]["summary_text"]`.

Note: the summarization pipeline uses an encoder-decoder model. The `temperature` and `do_sample` parameters are less relevant here — use `do_sample=False` for deterministic summaries.

### Step 5: Implement `run_question_answering()`

This function receives `question` and `context` and must:

- Call `get_pipeline("question-answering")`.
- Run the pipeline with the question and context. The `question-answering` pipeline signature is `pipe(question=..., context=...)`.
- Return a formatted string like: `Answer: {result['answer']}\nConfidence: {result['score']:.2%}`.

### Step 6: Wire up the Gradio interface

In the `build_interface()` function:

- Create a `gr.Dropdown` for task selection with choices `["text-generation", "summarization", "question-answering"]`.
- Show/hide the correct input fields based on the selected task:
  - `text-generation` and `summarization` share a single text input for the prompt/document.
  - `question-answering` needs two inputs: question and context.
- Show `max_new_tokens` slider for `text-generation` and `summarization`.
- Show `temperature` slider only for `text-generation` (range 0.1–2.0, default 0.7).
- Wire the Submit button to call the appropriate inference function based on the selected task.

Hint: use `gr.update(visible=...)` in a task-change handler to toggle component visibility.

### Step 7: Run locally

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Pre-download models
python download_models.py

# Start the app
python app.py
```

Open `http://localhost:7860` in your browser.

### Step 8: Run with Docker

```bash
# Build the image
docker build -t pipeline-playground:1.0 .

# Run with your local HF cache mounted as a volume
docker run -p 7860:7860 \
  -v "${HOME}/.cache/huggingface:/home/appuser/.cache/huggingface" \
  pipeline-playground:1.0
```

Open `http://localhost:7860` in your browser.

---

## Expected Outcome

When your implementation is complete, the following checklist must pass:

- [ ] Launching `python app.py` starts a Gradio server at `http://localhost:7860` with no import or runtime errors.
- [ ] Selecting "text-generation", entering a prompt, and clicking Submit returns generated text (not the prompt itself — `return_full_text=False` must be respected).
- [ ] Adjusting the `temperature` slider to 0.1 and running the same prompt twice produces near-identical outputs; adjusting to 1.5 produces visibly different outputs.
- [ ] Selecting "summarization", pasting a paragraph of text, and clicking Submit returns a shorter summary (not a continuation of the input).
- [ ] Selecting "question-answering", entering a question and a context passage, and clicking Submit returns an answer string extracted from the context plus a confidence score formatted as a percentage.
- [ ] Switching tasks a second time still returns correct results, confirming that pipelines are cached and not reloaded.
- [ ] `docker build -t pipeline-playground:1.0 .` completes without errors.
- [ ] `docker run -p 7860:7860 pipeline-playground:1.0` starts the container and the app is reachable at `http://localhost:7860`.
- [ ] Running `docker inspect pipeline-playground:1.0` shows a `Healthcheck` is configured.

---

## Hints

1. The `question-answering` pipeline is called differently from the other two — check the module's task table for its expected inputs and output shape before implementing.
2. If you see `RuntimeError: "addmm_impl_cpu_" not implemented for 'Half'`, you have passed `torch_dtype=torch.float16` somewhere — switch it to `torch.float32`.
3. To toggle Gradio component visibility based on a dropdown, return a list of `gr.update(visible=True/False)` values from a `.change()` handler — one `gr.update` per component being toggled.
4. The `_PIPELINES` dict is the simplest caching strategy: check `if task not in _PIPELINES` before building a new pipeline.
5. For the Docker volume mount to work, the container's `HF_HOME` environment variable must point to a path inside the container that you mount from the host.

---

## Bonus Challenges

- **Streaming output for text-generation:** Replace the `pipeline()` call in `run_text_generation()` with `AutoModelForCausalLM` + `TextIteratorStreamer` and wire the streamed output into a Gradio `gr.Textbox` using `yield` in the submit handler.
- **Model switcher:** Add a second dropdown that lets the user pick from two text-generation models (e.g., SmolLM2-1.7B-Instruct and Qwen2.5-1.5B-Instruct) and loads the selected model on demand.
- **Token count display:** After each inference call, display the number of input tokens and output tokens using `len(tokenizer.encode(text))`.
