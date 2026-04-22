# Exercise 1: Pipeline Playground — Starter

A Gradio web app that runs three NLP task types locally using Hugging Face `transformers`.

## Prerequisites

- Python 3.11+
- At least 12 GB of free RAM (models load into memory)
- At least 6 GB of free disk space

## Local Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows PowerShell

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional but recommended) Pre-download models
python download_models.py

# 4. Launch the app
python app.py
```

Open your browser at: http://localhost:7860

> The first model load will be slow (30–120 seconds) if models are not pre-downloaded.
> Subsequent calls reuse the cached pipeline — much faster.

## Running with Docker

```bash
# Build the image
docker build -t pipeline-playground:1.0 .

# Run, mounting your local HF model cache to avoid re-downloading inside the container
docker run -p 7860:7860 \
  -v "${HOME}/.cache/huggingface:/home/appuser/.cache/huggingface" \
  pipeline-playground:1.0
```

Open your browser at: http://localhost:7860

### Custom cache location

If you store your models in a custom directory, set `HF_HOME` before running:

```bash
docker run -p 7860:7860 \
  -e HF_HOME=/home/appuser/.cache/huggingface \
  -v "/path/to/your/model/cache:/home/appuser/.cache/huggingface" \
  pipeline-playground:1.0
```

## Task Guide

| Task | What to enter | Expected output |
|---|---|---|
| text-generation | Any prompt text | Continuation of the prompt |
| summarization | A long passage of text | A shorter summary |
| question-answering | A question + a context passage | The answer extracted from the context, with confidence |

## Troubleshooting

- **`RuntimeError: "addmm_impl_cpu_" not implemented for 'Half'`** — you have `float16` somewhere. Change it to `float32`.
- **Out of memory / system freezes** — the model is too large. Use `htop` to monitor RAM. Stop the process and try a smaller model.
- **First run is very slow** — expected. Run `python download_models.py` in advance to pre-cache models.
