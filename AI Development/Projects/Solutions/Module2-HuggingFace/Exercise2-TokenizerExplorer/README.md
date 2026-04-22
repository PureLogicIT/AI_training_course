# Exercise 2: Tokenizer Explorer — Solution

This is the reference solution for Exercise 2. See the starter project for the exercise instructions.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open: http://localhost:7860

## Docker

```bash
docker build -t tokenizer-explorer:1.0 .
docker run -p 7860:7860 \
  -v "${HOME}/.cache/huggingface:/home/appuser/.cache/huggingface" \
  tokenizer-explorer:1.0
```

## Key implementation notes

- `get_tokenizer()` downloads only tokenizer files (config JSONs + vocab files), not model weights.
- `tokenizer.all_special_ids` returns every special token ID defined on the tokenizer — convert to a `set` for O(1) badge color lookup.
- `html.escape()` must be applied to token strings before inserting into HTML to prevent XSS from unusual token content.
- `apply_chat_template(tokenize=False, add_generation_prompt=True)` returns a plain string showing exactly how the model sees the conversation.
- Special token IDs differ across families: Llama 3 uses 128000-range IDs for header tokens; Qwen uses `<|im_start|>` / `<|im_end|>` which appear in `additional_special_tokens`.
