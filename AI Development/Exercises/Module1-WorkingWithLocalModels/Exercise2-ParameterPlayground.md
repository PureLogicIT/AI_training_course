# Exercise 2: Model Parameter Tuning Playground

> Module: Module 1 — Working with Local Models | Difficulty: Medium | Estimated Time: 90–120 minutes

## Overview

You will build a **Gradio parameter tuning playground** that lets you fire the same prompt at a local model while freely adjusting every key inference parameter — temperature, top_p, top_k, num_ctx, repeat_penalty, and seed. The app displays the model output alongside a summary card that records the exact settings used, so you can compare runs side-by-side and build concrete intuition for what each knob does.

The app also supports **two inference backends** that you can toggle with a radio button: the Ollama Python SDK and `llama-cpp-python`. Implementing both backends deepens your understanding of how the same parameters map to each library's API.

## Learning Objectives

After completing this exercise you will be able to:

- Construct an `options` dict with all major Ollama inference parameters and pass it to `ollama.chat()`
- Map the same parameters to `llama-cpp-python`'s `create_chat_completion()` keyword arguments
- Explain the effect of each parameter (temperature, top_p, top_k, repeat_penalty, seed, num_ctx) and choose appropriate values for a given task
- Build a multi-input Gradio UI with sliders, number inputs, and radio buttons
- Switch between two backend implementations using a shared abstract interface

## Prerequisites

- Ollama installed and running with at least one model pulled
- Python 3.11 with `gradio`, `ollama`, and `llama-cpp-python` installed
- A GGUF model file on disk for the `llama-cpp-python` backend (e.g., `Llama-3.2-3B-Instruct-Q4_K_M.gguf`)
- Alternatively, Docker Desktop (Ollama backend only)

## Scenario

You are new to local LLM inference and want to build genuine intuition for how sampling parameters affect outputs. Rather than running one-off scripts, you want a persistent UI where you can run the same prompt ten times with different settings and watch the outputs change. The settings summary card next to each output makes it easy to recall exactly what parameters produced a given result.

---

## Directory Structure

```
Exercise2-ParameterPlayground/
├── app.py            # Main Gradio application
├── backends.py       # Backend abstraction (OllamaBackend + LlamaCppBackend)
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Instructions

### Step 1 — Implement OllamaBackend in `backends.py`

`backends.py` defines a `BackendProtocol` (structural interface) and two classes. Implement the `OllamaBackend` class:

- Constructor: accept `model` (str), `host` (str, default `"http://localhost:11434"`) and create an `ollama.Client`.
- `generate(prompt, params)` method: build a single-turn message list (`system` + `user`) and call `client.chat()` with `stream=False` and the `params` dict as the `options` argument. Return the response text string.
- `name` property: return `"Ollama"`.

> Hint: `response.message.content` (or `response["message"]["content"]`) holds the text. The `params` dict maps directly to Ollama's `options`.

### Step 2 — Implement LlamaCppBackend in `backends.py`

Implement the `LlamaCppBackend` class:

- Constructor: accept `model_path` (str), `n_threads` (int, default 4). Load the model with `Llama(model_path=..., verbose=False, n_ctx=...)`. Because `n_ctx` is a per-run parameter, load the model with the maximum reasonable context (8192) and note that `num_ctx` from the UI controls the prompt's context budget, not the loaded size.
- `generate(prompt, params)` method: call `llm.create_chat_completion()` passing the messages list and mapping UI parameter names to the library's argument names (see the mapping table below). Return the generated text.
- `name` property: return `"llama-cpp-python"`.

**Parameter name mapping** (UI name → `create_chat_completion` kwarg):

| UI / Ollama name | llama-cpp-python argument |
|---|---|
| `temperature` | `temperature` |
| `top_p` | `top_p` |
| `top_k` | `top_k` |
| `repeat_penalty` | `repeat_penalty` |
| `seed` | `seed` |
| `num_ctx` | not applicable (set at load time) |
| (fixed) | `max_tokens=512` |

> Hint: Use `response["choices"][0]["message"]["content"]` to extract the text.

### Step 3 — Build the parameter controls in `app.py`

Implement `build_parameter_controls()`. This function should return a dictionary of Gradio components using `gr.Slider` and `gr.Number`:

| Parameter | Component | Range / Step | Default |
|---|---|---|---|
| `temperature` | `gr.Slider` | 0.0 – 2.0, step 0.05 | 0.7 |
| `top_p` | `gr.Slider` | 0.0 – 1.0, step 0.05 | 0.9 |
| `top_k` | `gr.Slider` | 1 – 200, step 1 | 40 |
| `repeat_penalty` | `gr.Slider` | 1.0 – 2.0, step 0.05 | 1.1 |
| `num_ctx` | `gr.Slider` | 512 – 16384, step 512 | 4096 |
| `seed` | `gr.Number` | integer | -1 (random) |

> Hint: `gr.Number(value=-1, precision=0, label="Seed (-1 = random)")`.

### Step 4 — Implement the `run_inference()` function in `app.py`

`run_inference()` is the function called when the user clicks **Run**. It receives the prompt text, the backend radio value, the GGUF path (for the llama-cpp backend), and all six parameter values. It must:

1. Select the correct backend class based on the radio value.
2. Instantiate the backend (use the `OLLAMA_HOST` environment variable for the Ollama backend host).
3. Build a `params` dict from the six parameter values. If `seed` is -1, omit the `seed` key (so the model uses a fresh random seed each run).
4. Call `backend.generate(prompt, params)` and capture the result text.
5. Build a **settings summary** string in Markdown format listing every parameter name and value used.
6. Return `(result_text, settings_summary)`.

> Hint: The settings summary can be a simple markdown table or a code block. Including `backend.name` in the header is a nice touch.

### Step 5 — Wire up the full Gradio layout in `app.py`

Implement `build_ui()`. The layout should contain:

- A `gr.Radio` to choose `"Ollama"` or `"llama-cpp-python"` (default `"Ollama"`)
- A `gr.Textbox` for the GGUF model path (visible only when `llama-cpp-python` is selected — use `gr.Textbox(..., visible=False)` and a `.change()` handler on the radio to toggle visibility)
- A `gr.Textbox` for the prompt (multiline, at least 4 lines tall)
- The six parameter controls from Step 3 arranged in two columns
- A **Run** button
- Two output areas side-by-side: `gr.Textbox` for the model output and `gr.Markdown` for the settings summary

Wire the **Run** button's `.click()` to `run_inference()`, passing all inputs and pointing outputs at the two output components.

---

## Expected Outcome

- [ ] Opening the app shows all six parameter sliders and the prompt input
- [ ] Entering a prompt and clicking **Run** with the Ollama backend returns a response
- [ ] The settings summary panel shows the exact parameter values used for that run
- [ ] Running the same prompt twice with `seed=-1` produces different outputs; running it twice with a fixed seed and `temperature > 0` may still vary slightly but demonstrates seed's effect
- [ ] Setting `temperature=0.0` produces highly consistent (deterministic) output across multiple runs
- [ ] Switching to `llama-cpp-python` and providing a valid GGUF path returns a response using that backend
- [ ] `docker build -t parameter-playground .` completes successfully (Ollama backend only in Docker)
- [ ] The GGUF path field hides when "Ollama" is selected and shows when "llama-cpp-python" is selected

---

## Bonus Challenges

1. Add a **history panel** (`gr.Dataframe` or `gr.HTML`) that logs every run's prompt, backend, key parameters, and first 100 characters of output — so you can scroll back through your experiments.
2. Add a **"Run 3× and compare"** button that runs the same prompt three times with the current settings and displays all three outputs in a `gr.Row` — useful for visualising temperature variance.
3. Add a `min_p` slider (range 0.0–0.5, step 0.01, default 0.0) and include it in both backends where supported.
