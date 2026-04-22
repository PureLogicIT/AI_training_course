# Exercise 1: Pipeline Playground — Solution

This is the reference solution for Exercise 1. See the starter project for the exercise instructions.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python download_models.py   # pre-download models (recommended)
python app.py
```

Open: http://localhost:7860

## Docker

```bash
docker build -t pipeline-playground:1.0 .
docker run -p 7860:7860 \
  -v "${HOME}/.cache/huggingface:/home/appuser/.cache/huggingface" \
  pipeline-playground:1.0
```

## Key implementation notes

- `get_pipeline()` uses `_PIPELINES` dict as a cache — pipelines are loaded once per process lifetime.
- All pipelines use `device="cpu"` and `torch_dtype="float32"` as required for CPU-only PyTorch.
- The `question-answering` pipeline uses `pipe(question=..., context=...)` keyword syntax, not positional.
- `update_visibility()` returns a list of 5 `gr.update()` objects; order must match the `outputs=` list in `.change()`.
- `return_full_text=False` ensures the generated text does not include the input prompt repeated back.
