# Exercise 2: Tokenizer Explorer

> **Module:** Module 2 — Hugging Face & Local Models
> **Difficulty:** Intermediate
> **Estimated Time:** 90–120 minutes
> **Concepts Practiced:** `AutoTokenizer`, `encode()` / `decode()` / `convert_ids_to_tokens()`, special tokens, `apply_chat_template()`, chat template differences across model families, Gradio UI, Docker

---

## Scenario

Your team keeps getting surprised by how differently models respond to the same input. After digging in, you realize the root cause is chat template mismatches — developers are manually constructing prompt strings for Llama 3 models using Mistral's `[INST]` format, or forgetting to include the `<|im_start|>` tokens that Qwen models expect. You have been asked to build an internal tool that lets anyone on the team paste in some text and immediately see exactly how a given model family tokenizes it and what the full formatted prompt looks like after `apply_chat_template()` is applied. The tool should make token boundaries visible and call out special tokens so developers can debug prompt formatting issues at a glance.

---

## Learning Objectives

By completing this exercise you will be able to:

1. Use `AutoTokenizer.from_pretrained()` to load tokenizers for multiple model families.
2. Use `encode()`, `convert_ids_to_tokens()`, and `decode()` to inspect tokenization at each stage.
3. Identify and display special tokens (`bos_token`, `eos_token`, `pad_token`) and their IDs.
4. Apply `apply_chat_template()` with `tokenize=False` to render the formatted prompt string for a given model family.
5. Explain why the same message content produces different token sequences across Llama 3, Mistral, and ChatML/Qwen model families.
6. Build a multi-tab Gradio interface that renders HTML for rich visual output.

---

## Background

### Why tokenization differs across model families

Each model family trains its tokenizer on different data with a different vocabulary size, and its instruction-tuned variants are fine-tuned on data formatted with specific special tokens that mark turn boundaries:

| Family | Vocab Size | User turn marker | Assistant turn marker |
|---|---|---|---|
| Llama 3.x | 128,000 | `<\|start_header_id\|>user<\|end_header_id\|>` | `<\|start_header_id\|>assistant<\|end_header_id\|>` |
| Mistral v0.1 | 32,000 | `[INST]` | `[/INST]` |
| ChatML (Qwen, Phi, many fine-tunes) | 151,936 (Qwen2.5) | `<\|im_start\|>user` | `<\|im_start\|>assistant` |

Because these are baked into the tokenizer's `chat_template` attribute, `apply_chat_template()` always produces the correct format — you never need to memorize the templates manually.

### Tokenizer models used in this exercise

To keep downloads small, you will load **tokenizers only** — not the full model weights. Tokenizers are a few megabytes at most and download instantly.

| Family represented | Tokenizer Hub ID | Download size |
|---|---|---|
| Llama 3 | `meta-llama/Meta-Llama-3-8B-Instruct` | ~2 MB (tokenizer files only) |
| Mistral | `mistralai/Mistral-7B-Instruct-v0.1` | ~2 MB |
| ChatML / Qwen | `Qwen/Qwen2.5-1.5B-Instruct` | ~7 MB |
| SmolLM2 (default) | `HuggingFaceTB/SmolLM2-1.7B-Instruct` | ~2 MB |

> **Note on gated models:** `meta-llama/Meta-Llama-3-8B-Instruct` is a gated repository. You must accept the license at `https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct` and run `huggingface-cli login` before it will download. If you do not have Hub access, use `HuggingFaceTB/SmolLM2-1.7B-Instruct` for the Llama-family slot — it uses the same Llama-3 chat template format and is not gated.

---

## Project Structure

```
Exercise2-TokenizerExplorer/
├── app.py                  # Main Gradio application (your primary task)
├── tokenizer_utils.py      # Helper functions for tokenization (your secondary task)
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
└── README.md               # Run instructions
```

---

## Instructions

### Step 1: Implement `tokenizer_utils.py`

This module contains the tokenizer cache and the three core analysis functions. Implement each function as described by its TODO comment.

#### `get_tokenizer(model_family: str) -> AutoTokenizer`

- Map `model_family` string (`"llama3"`, `"mistral"`, `"chatml_qwen"`, `"smollm2"`) to the correct Hub ID.
- Use a module-level dict `_TOKENIZER_CACHE` to avoid reloading on every call.
- Load with `AutoTokenizer.from_pretrained(hub_id)`.
- Return the tokenizer.

#### `tokenize_text(text: str, model_family: str) -> dict`

Returns a dict with these keys:
- `"token_ids"` — list of ints from `tokenizer.encode(text)`
- `"tokens"` — list of strings from `tokenizer.convert_ids_to_tokens(token_ids)`
- `"token_count"` — int, length of `token_ids`
- `"decoded"` — str, `tokenizer.decode(token_ids, skip_special_tokens=False)`
- `"special_token_ids"` — set of ints: the union of all special token IDs defined on the tokenizer (use `tokenizer.all_special_ids`)

#### `build_chat_template_preview(user_text: str, model_family: str, include_system: bool) -> str`

- Build a messages list. If `include_system` is True, prepend `{"role": "system", "content": "You are a helpful assistant."}`.
- Add `{"role": "user", "content": user_text}`.
- Call `tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)`.
- Return the resulting string.

### Step 2: Implement the token visualization helper in `app.py`

Implement `render_tokens_as_html(tokens: list[str], token_ids: list[int], special_ids: set[int]) -> str`.

This function must return an HTML string where each token is rendered as a small colored badge:
- **Special tokens** (where `token_id` is in `special_ids`): use a distinct background color (e.g., orange or red).
- **Regular tokens**: use a neutral background color (e.g., light blue or light grey).

Each badge should display the token text. Spaces within tokens (often represented as `▁` in SentencePiece or `Ġ` in BPE tokenizers) should be displayed as `·` for readability, or rendered with a visible space character.

Example output structure (exact styling is up to you):

```html
<div style="font-family: monospace; line-height: 2.5;">
  <span style="background:#f97316; color:white; padding:2px 6px; border-radius:4px; margin:2px;">▁Hello</span>
  <span style="background:#bfdbfe; padding:2px 6px; border-radius:4px; margin:2px;">▁world</span>
  ...
</div>
```

### Step 3: Build the Gradio interface in `app.py`

The interface must have **three tabs**:

#### Tab 1 — Token Inspector

Inputs:
- `gr.Textbox` — text to tokenize (multi-line, placeholder: "Enter any text to tokenize...")
- `gr.Dropdown` — model family selector: `["smollm2", "llama3", "mistral", "chatml_qwen"]`

Outputs:
- `gr.HTML` — the colored token badge visualization (call `render_tokens_as_html()`)
- `gr.Textbox` — token IDs as a comma-separated string
- `gr.Number` — token count

#### Tab 2 — Special Tokens Reference

Inputs:
- `gr.Dropdown` — model family selector (same choices as Tab 1)
- `gr.Button` — "Load Special Tokens"

Output:
- `gr.Dataframe` — a table with columns: `["Token Name", "Token String", "Token ID"]`, showing BOS, EOS, PAD, UNK, and any additional entries from `tokenizer.additional_special_tokens[:10]`.

#### Tab 3 — Chat Template Preview

Inputs:
- `gr.Textbox` — user message text
- `gr.Dropdown` — model family selector
- `gr.Checkbox` — "Include system prompt" (default: True)

Output:
- `gr.Code` — the raw formatted template string (use `language="text"` to get monospace display without syntax highlighting)

### Step 4: Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:7860`.

### Step 5: Run with Docker

```bash
docker build -t tokenizer-explorer:1.0 .
docker run -p 7860:7860 \
  -v "${HOME}/.cache/huggingface:/home/appuser/.cache/huggingface" \
  tokenizer-explorer:1.0
```

---

## Expected Outcome

- [ ] Launching `python app.py` starts the Gradio server with no errors.
- [ ] Tab 1: entering `"Hello, world!"` with `smollm2` selected and clicking Tokenize produces a colored HTML token display showing individual token badges, a list of token IDs, and a token count greater than 0.
- [ ] Tab 1: switching the model family dropdown changes the token count for the same input (demonstrating that different vocabularies produce different tokenizations).
- [ ] Tab 1: special tokens (if any appear in the encoded sequence) are rendered in a visually distinct color from regular tokens.
- [ ] Tab 2: clicking "Load Special Tokens" for any model family fills the dataframe with at least BOS, EOS rows (or shows "None" where undefined).
- [ ] Tab 3: entering `"What is a transformer?"` and selecting `llama3` produces a formatted string containing `<|start_header_id|>`, `<|end_header_id|>`, and `<|eot_id|>` tokens.
- [ ] Tab 3: the same input with `mistral` selected shows `[INST]` and `[/INST]` markers.
- [ ] Tab 3: the same input with `chatml_qwen` selected shows `<|im_start|>` and `<|im_end|>` markers.
- [ ] Tab 3: toggling "Include system prompt" adds or removes a system turn from the preview.
- [ ] `docker build -t tokenizer-explorer:1.0 .` completes without errors.
- [ ] `docker run -p 7860:7860 tokenizer-explorer:1.0` starts the container and the app is reachable.

---

## Hints

1. To load only the tokenizer (not the model weights), `AutoTokenizer.from_pretrained()` already downloads only the tokenizer files — it does not download model weights unless you also call `AutoModelForCausalLM.from_pretrained()`. Tokenizer-only loads are fast.
2. `tokenizer.all_special_ids` returns a list of all special token IDs. Convert it to a `set` for O(1) lookup when rendering each token badge.
3. For the Llama 3 tokenizer specifically: the special tokens `<|begin_of_text|>`, `<|start_header_id|>`, `<|end_header_id|>`, and `<|eot_id|>` are all in `all_special_ids`. When you encode a plain string (not a chat template), you may only see `<|begin_of_text|>` — the header tokens appear only in chat-formatted inputs.
4. `tokenizer.apply_chat_template()` raises a `TemplateError` if the tokenizer has no chat template defined. Wrap the call in a try/except and return a descriptive error message in that case.
5. The Gradio `gr.HTML` component renders raw HTML strings directly — you do not need `gr.Markdown` or any escaping beyond ensuring your badge text is HTML-safe (use `html.escape()` on token strings before inserting them into the HTML).

---

## Bonus Challenges

- **Side-by-side comparison:** Add a fourth tab where the user enters one piece of text and sees the tokenization and token count from all four model families simultaneously in a 2x2 grid.
- **Encode/decode round-trip:** In Tab 1, add a section that shows `tokenizer.decode(token_ids, skip_special_tokens=False)` vs. `skip_special_tokens=True` side by side, so learners can see what special tokens look like when included in the decoded output.
- **Vocabulary search:** Add a `gr.Textbox` input where users can type a word or subword and see its token ID if it exists in the tokenizer's vocabulary, using `tokenizer.convert_tokens_to_ids([word])`.
