# Exercise 2: Tokenizer Explorer — Starter

A three-tab Gradio app for inspecting tokenization, special tokens, and chat templates
across multiple Hugging Face model families.

## Prerequisites

- Python 3.11+
- Internet connection for the first run (tokenizer files download automatically, ~2–7 MB each)
- For the Llama 3 tokenizer: a Hugging Face account with the Meta Llama 3 license accepted,
  and `huggingface-cli login` run before starting the app.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows PowerShell

pip install -r requirements.txt
python app.py
```

Open: http://localhost:7860

## Running with Docker

```bash
docker build -t tokenizer-explorer:1.0 .
docker run -p 7860:7860 \
  -v "${HOME}/.cache/huggingface:/home/appuser/.cache/huggingface" \
  tokenizer-explorer:1.0
```

Open: http://localhost:7860

## Notes on the Llama 3 tokenizer

The `meta-llama/Meta-Llama-3-8B-Instruct` tokenizer is in a gated repository.
To use it:

1. Visit https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct and accept the license.
2. Generate a read token at https://huggingface.co/settings/tokens.
3. Run `huggingface-cli login` and paste your token.

If you skip this, use `smollm2` for the Llama-family slot — it uses the same
Llama-3 chat template format and is freely accessible.
