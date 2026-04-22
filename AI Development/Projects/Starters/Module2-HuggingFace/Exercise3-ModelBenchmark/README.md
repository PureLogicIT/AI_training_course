# Exercise 3: Model Benchmark & Comparison — Starter

A Gradio app that benchmarks multiple local Hugging Face models, collecting
response text, generation time, tokens/sec, and peak RAM for each (model, prompt) pair.

## Prerequisites

- Python 3.11+
- At least 8 GB of RAM (16 GB recommended for multi-model runs)
- At least 20 GB of free disk space (models are 4–7 GB each in float32)

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows PowerShell

pip install -r requirements.txt
python app.py
```

Open: http://localhost:7860

**Tip:** Start with a single model and a single short prompt to verify your implementation
before running the full benchmark (which can take 15–30 minutes on CPU).

## Running with Docker

```bash
docker build -t model-benchmark:1.0 .
docker run -p 7860:7860 \
  -v "${HOME}/.cache/huggingface:/home/appuser/.cache/huggingface" \
  model-benchmark:1.0
```

Open: http://localhost:7860

## Prompt JSON format

The prompt editor accepts two formats:

```json
["Prompt one text", "Prompt two text"]
```

or

```json
[{"prompt": "Prompt one text"}, {"prompt": "Prompt two text"}]
```

## Memory management

The benchmark loads one model at a time, runs all prompts, then calls `unload_model()`
before loading the next. If you see the system start to swap heavily (fan noise, sluggish response),
stop the process — the model is too large for available RAM.
