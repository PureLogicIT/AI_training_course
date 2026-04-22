# Exercise 3: Model Benchmark & Comparison — Solution

This is the reference solution for Exercise 3. See the starter project for the exercise instructions.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open: http://localhost:7860

Start with one model and one short prompt to verify the benchmark works before running all three.

## Docker

```bash
docker build -t model-benchmark:1.0 .
docker run -p 7860:7860 \
  -v "${HOME}/.cache/huggingface:/home/appuser/.cache/huggingface" \
  model-benchmark:1.0
```

## Key implementation notes

- Models are loaded sequentially and unloaded between runs (`del model; gc.collect()`).
  This keeps peak RAM to one model at a time.
- The Gradio generator pattern (`yield`) allows status updates during the long-running benchmark.
  The benchmark itself runs in a background thread; the main thread polls for status messages.
- `apply_chat_template()` is used when `tokenizer.chat_template is not None`; otherwise a
  plain `"User: ...\nAssistant:"` format is used as a fallback (relevant for TinyLlama).
- `pad_token_id=tokenizer.eos_token_id` is required for models without a defined pad token.
- `do_sample=False` (greedy decoding) ensures reproducible results for fair comparison.
- The CSV is written to a `tempfile.NamedTemporaryFile(delete=False)` so it persists for download.
- `peak_ram_mb` measures net RSS increase during `model.generate()`, not total model footprint.
  Total footprint is captured by `load_ram_mb` during the load phase.
