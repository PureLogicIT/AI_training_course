# Exercise 3: Model Benchmark & Comparison

> **Module:** Module 2 — Hugging Face & Local Models
> **Difficulty:** Hard
> **Estimated Time:** 150–210 minutes
> **Concepts Practiced:** `pipeline()` with multiple models, `AutoModelForCausalLM` / `AutoTokenizer`, `apply_chat_template()`, generation parameter control, timing and throughput measurement, peak memory tracking (`tracemalloc` / `psutil`), Gradio data visualization, CSV export, Docker

---

## Scenario

Your team is choosing a small local model to embed in a desktop application that needs to run on end-user machines with 8–16 GB of RAM and no GPU. You have shortlisted three candidates. Before making a final decision, you need hard numbers: how long does each model take to respond to a representative set of prompts, how many tokens per second does each produce, and how much RAM does each consume at peak? You have been asked to build a benchmarking tool that accepts a set of test prompts through a Gradio UI, runs each prompt through each selected model, and produces a comparison table that can be exported to CSV for stakeholder review.

---

## Learning Objectives

By completing this exercise you will be able to:

1. Load multiple `transformers` models sequentially, measuring and reporting peak memory for each.
2. Use `time.perf_counter()` to measure wall-clock generation time and calculate tokens-per-second throughput.
3. Use `tracemalloc` or `psutil` to track peak RSS memory during model inference.
4. Apply `apply_chat_template()` consistently across models with different tokenizers.
5. Build a Gradio interface that accepts JSON prompt input, displays live benchmark progress, and renders results in a `gr.Dataframe`.
6. Export benchmark results to a CSV file for download.
7. Explain the performance and memory tradeoffs between different model sizes based on observed benchmark data.

---

## Background

### Models to benchmark

All three models are Apache 2.0 licensed and suitable for 8–16 GB RAM machines. You will select 2 or 3 of them in the UI.

| Model | Hub ID | Float32 RAM estimate | Typical CPU tokens/sec |
|---|---|---|---|
| SmolLM2-1.7B-Instruct | `HuggingFaceTB/SmolLM2-1.7B-Instruct` | ~6.8 GB | 3–6 tok/s |
| Qwen2.5-1.5B-Instruct | `Qwen/Qwen2.5-1.5B-Instruct` | ~6.0 GB | 4–7 tok/s |
| TinyLlama-1.1B-Chat | `TinyLlama/TinyLlama-1.1B-Chat-v1.0` | ~4.4 GB | 6–10 tok/s |

> **Memory warning:** Running all three models sequentially in a single process can use 15–20 GB of RAM if models are kept loaded simultaneously. The benchmark should **load one model, run all prompts, record results, then unload** before loading the next. Implement this pattern using `del model`, `del tokenizer`, and `gc.collect()` between models.

### Metrics to collect

For each (model, prompt) pair, collect:

| Metric | How to measure |
|---|---|
| `response_text` | The decoded generated string |
| `input_tokens` | `len(tokenizer.encode(prompt_text))` (after chat template) |
| `output_tokens` | `len(tokenizer.encode(response_text))` |
| `generation_time_s` | `time.perf_counter()` stop minus start, in seconds |
| `tokens_per_sec` | `output_tokens / generation_time_s` |
| `peak_ram_mb` | Peak RSS in MB during generation (see Step 4) |

### Memory measurement

Use `psutil` to measure peak RSS (Resident Set Size) before and after generation:

```python
import psutil
import os

process = psutil.Process(os.getpid())
mem_before = process.memory_info().rss / (1024 ** 2)  # MB
# ... run generation ...
mem_after = process.memory_info().rss / (1024 ** 2)   # MB
peak_ram_mb = mem_after - mem_before
```

This measures the net increase in RAM for the generation call, not the total process RSS. For total model memory footprint, measure before and after `from_pretrained()` during model loading.

---

## Project Structure

```
Exercise3-ModelBenchmark/
├── app.py                  # Main Gradio application (your primary task)
├── benchmark_engine.py     # Model loading, inference, and metric collection (your task)
├── sample_prompts.json     # Default test prompts (provided)
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
└── README.md               # Run instructions
```

---

## Instructions

### Step 1: Implement `benchmark_engine.py`

#### `load_model_and_tokenizer(model_id: str) -> tuple`

- Load using `AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float32)`.
- Load tokenizer with `AutoTokenizer.from_pretrained(model_id)`.
- Call `model.eval()`.
- Measure and return `(model, tokenizer, load_time_s, load_ram_mb)`:
  - `load_time_s`: time to load using `time.perf_counter()`.
  - `load_ram_mb`: net RSS increase during `from_pretrained()` using `psutil`.

#### `run_single_inference(model, tokenizer, prompt_text: str, max_new_tokens: int) -> dict`

This is the core inference function. It must:

1. Format the prompt using `apply_chat_template()`:
   ```python
   messages = [{"role": "user", "content": prompt_text}]
   input_ids = tokenizer.apply_chat_template(
       messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
   )
   ```
2. Record `mem_before` using `psutil`.
3. Record `t_start` using `time.perf_counter()`.
4. Call `model.generate()` inside `torch.no_grad()` with:
   - `max_new_tokens=max_new_tokens`
   - `do_sample=False` (greedy decoding for reproducibility across runs)
   - `pad_token_id=tokenizer.eos_token_id`
5. Record `t_end` and `mem_after`.
6. Decode only the generated tokens (slice off input length).
7. Return a dict with all six metrics listed in the Background section.

#### `unload_model(model, tokenizer) -> None`

- `del model`, `del tokenizer`.
- `import gc; gc.collect()`.
- `import torch; torch.cuda.empty_cache()` (no-op on CPU but safe to call).

#### `run_benchmark(model_ids: list[str], prompts: list[str], max_new_tokens: int, progress_callback=None) -> list[dict]`

- Iterate over `model_ids`. For each:
  - Call `load_model_and_tokenizer()`.
  - Iterate over `prompts`. For each:
    - Call `run_single_inference()`.
    - Append a result dict that includes `model_id`, `prompt` (first 80 chars), all six metrics.
    - If `progress_callback` is not None, call it with a status string like `"Model 1/2: SmolLM2 — Prompt 2/3"`.
  - Call `unload_model()`.
- Return the flat list of all result dicts.

### Step 2: Implement the prompt loader in `app.py`

#### `load_prompts_from_json(json_text: str) -> list[str]`

- Parse `json_text` as JSON.
- Accept either a JSON array of strings `["prompt1", "prompt2"]` or a JSON array of objects `[{"prompt": "...", ...}]`.
- In the object case, extract the `"prompt"` key.
- Return a list of strings.
- On parse error, raise a `ValueError` with a descriptive message.

### Step 3: Build the Gradio interface in `app.py`

The interface has three sections:

#### Section 1 — Configuration

- `gr.CheckboxGroup` — model selection; choices: the three model Hub IDs above; default: first two selected.
- `gr.Slider` — `max_new_tokens` (range 50–500, default 150, step 50).
- `gr.Code` — prompt editor (language `"json"`, default value: the contents of `sample_prompts.json`).
- `gr.Button` — "Run Benchmark".

#### Section 2 — Progress

- `gr.Textbox` — live status updates (read-only). Update this during the benchmark run.

#### Section 3 — Results

- `gr.Dataframe` — benchmark results table. Columns: `["model", "prompt_preview", "output_tokens", "gen_time_s", "tokens_per_sec", "peak_ram_mb"]`.
- `gr.File` — downloadable CSV export. The file should be generated automatically after the benchmark completes.

#### Wiring the Run Benchmark button

Because the benchmark can take several minutes, use a generator function for the click handler that `yield`s intermediate status updates to the status textbox, then yields the final dataframe and file path at the end.

```python
def run_benchmark_ui(model_choices, max_new_tokens, prompts_json):
    prompts = load_prompts_from_json(prompts_json)
    results = []

    def progress_cb(msg):
        nonlocal results
        # yield is not possible inside a callback — collect updates differently
        pass

    # TODO: implement the generator pattern with status yields
    yield "Starting benchmark...", None, None
    # ... run benchmark, yield progress, yield final results ...
```

Hint: since `progress_callback` cannot `yield` directly, run the benchmark in a thread and poll for status updates. Alternatively, restructure `run_benchmark()` to be a generator itself that `yield`s `(status_str, partial_results)` tuples, and iterate over it in the UI handler.

### Step 4: CSV export

After benchmark completion, write results to a temporary CSV file using Python's `csv` module or `pandas` (if installed):

```python
import csv, tempfile, os

def save_results_csv(results: list[dict]) -> str:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    )
    fieldnames = ["model_id", "prompt_preview", "input_tokens", "output_tokens",
                  "generation_time_s", "tokens_per_sec", "peak_ram_mb", "response_text"]
    writer = csv.DictWriter(tmp, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(results)
    tmp.close()
    return tmp.name
```

Return the file path; assign it to the `gr.File` component so users can download it.

### Step 5: Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:7860`. Select one model and one short prompt for a quick test before running the full benchmark.

### Step 6: Run with Docker

```bash
docker build -t model-benchmark:1.0 .
docker run -p 7860:7860 \
  -v "${HOME}/.cache/huggingface:/home/appuser/.cache/huggingface" \
  model-benchmark:1.0
```

---

## Expected Outcome

- [ ] Launching `python app.py` starts the Gradio server with no errors.
- [ ] Selecting one model, entering a valid JSON prompt list, and clicking "Run Benchmark" runs inference and populates the results table within a reasonable time (allow 5+ minutes per model on CPU).
- [ ] The status textbox updates at least once per prompt during the run (not just at the end).
- [ ] The results dataframe shows one row per (model, prompt) combination.
- [ ] `tokens_per_sec` values in the table are positive numbers; verify they are in the expected range for the model (TinyLlama should be fastest; SmolLM2 should be slower).
- [ ] `peak_ram_mb` values are positive numbers; verify TinyLlama uses less RAM than SmolLM2.
- [ ] After benchmark completes, a CSV file download link appears; downloading it produces a valid CSV with headers and data rows.
- [ ] Running the benchmark with two models selected in sequence does not cause an OOM error (confirm the unload pattern works by observing that memory returns near baseline between models using `htop` or Task Manager).
- [ ] `docker build -t model-benchmark:1.0 .` completes without errors.
- [ ] `docker run -p 7860:7860 model-benchmark:1.0` starts the container and the app is reachable.

---

## Hints

1. The trickiest part of this exercise is the generator-based progress reporting in Gradio. The simplest pattern: make `run_benchmark()` a regular function but collect results in a list, then `yield` status strings from the UI handler by polling. A cleaner approach: refactor `run_benchmark()` as a Python generator that `yield`s `(status, partial_results_list)` tuples, then iterate over it inside the Gradio click handler.
2. The `pad_token_id=tokenizer.eos_token_id` argument to `model.generate()` is required for models that do not define a pad token (TinyLlama is one such model). Without it, you will get a `UserWarning` and potentially incorrect output lengths.
3. To slice off the input tokens from generated output: `generated_ids = output_ids[0][input_ids.shape[1]:]`, then `tokenizer.decode(generated_ids, skip_special_tokens=True)`.
4. If a model's tokenizer does not have a chat template (`tokenizer.chat_template is None`), fall back to a simple string format: `f"User: {prompt}\nAssistant:"`.
5. For the `gr.File` download to work, the file must exist on disk when you assign its path to the component. Use `tempfile.NamedTemporaryFile(delete=False)` so the file persists after the function returns.

---

## Bonus Challenges

- **Parallel prompt execution:** Instead of running prompts sequentially for each model, use Python `ThreadPoolExecutor` to run multiple prompts concurrently for the same model. Measure whether throughput improves or degrades on CPU (it typically degrades due to GIL and memory bandwidth contention — document your findings).
- **Comparative bar chart:** Use Gradio's `gr.BarPlot` to render a `tokens_per_sec` comparison chart grouped by model.
- **Warm-up run:** Add a single warm-up inference before the timed runs for each model (the first inference is always slower due to cache effects). Report both warm-up time and the mean of subsequent runs separately.
- **Export to Markdown:** Add a second export button that formats the results as a Markdown table suitable for pasting into a GitHub issue or internal wiki.
