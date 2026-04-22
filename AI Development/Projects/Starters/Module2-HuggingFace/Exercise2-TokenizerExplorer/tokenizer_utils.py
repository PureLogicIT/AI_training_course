"""
tokenizer_utils.py
==================
Helper module for loading and inspecting tokenizers from multiple model families.

This module provides three functions used by app.py:
  - get_tokenizer()              : load and cache a tokenizer by family name
  - tokenize_text()              : encode text and return detailed tokenization info
  - build_chat_template_preview(): apply a chat template and return the formatted string

Complete all TODO sections. Do not change the function signatures.
"""

from transformers import AutoTokenizer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Map friendly family names to Hugging Face Hub model IDs.
# We only load the tokenizer files (no model weights) — fast download.
FAMILY_TO_MODEL = {
    "smollm2":    "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    "llama3":     "meta-llama/Meta-Llama-3-8B-Instruct",   # gated — needs HF login
    "mistral":    "mistralai/Mistral-7B-Instruct-v0.1",
    "chatml_qwen": "Qwen/Qwen2.5-1.5B-Instruct",
}

# Tokenizer cache: avoids re-downloading on every call.
_TOKENIZER_CACHE: dict = {}


# ---------------------------------------------------------------------------
# Step 1a: Tokenizer loader
# ---------------------------------------------------------------------------

def get_tokenizer(model_family: str) -> AutoTokenizer:
    """
    Load and cache a tokenizer for the given model family.

    Args:
        model_family: One of "smollm2", "llama3", "mistral", "chatml_qwen".

    Returns:
        A loaded AutoTokenizer instance.

    Raises:
        ValueError: if model_family is not in FAMILY_TO_MODEL.

    TODO:
      1. Check if model_family is in FAMILY_TO_MODEL; raise ValueError if not.
      2. If the tokenizer is already in _TOKENIZER_CACHE, return it immediately.
      3. Otherwise, load with AutoTokenizer.from_pretrained(hub_id).
      4. Store in _TOKENIZER_CACHE[model_family] and return it.
    """
    # TODO: implement tokenizer caching and loading
    raise NotImplementedError("get_tokenizer() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 1b: Tokenize text
# ---------------------------------------------------------------------------

def tokenize_text(text: str, model_family: str) -> dict:
    """
    Encode text and return detailed tokenization information.

    Args:
        text:         The raw text string to tokenize.
        model_family: One of the keys in FAMILY_TO_MODEL.

    Returns:
        A dict with these keys:
          "token_ids"        : list[int]  — raw integer token IDs
          "tokens"           : list[str]  — decoded token strings (e.g. "▁Hello")
          "token_count"      : int        — number of tokens
          "decoded"          : str        — full decoded string (skip_special_tokens=False)
          "special_token_ids": set[int]   — set of all special token IDs for this tokenizer

    TODO:
      1. Call get_tokenizer(model_family).
      2. Encode: token_ids = tokenizer.encode(text)
      3. Tokens: tokenizer.convert_ids_to_tokens(token_ids)
      4. Token count: len(token_ids)
      5. Decoded: tokenizer.decode(token_ids, skip_special_tokens=False)
      6. Special token IDs: set(tokenizer.all_special_ids)
      7. Return the dict.
    """
    # TODO: implement tokenize_text
    raise NotImplementedError("tokenize_text() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 1c: Chat template preview
# ---------------------------------------------------------------------------

def build_chat_template_preview(user_text: str, model_family: str,
                                  include_system: bool) -> str:
    """
    Apply the tokenizer's chat template and return the formatted prompt string.

    Args:
        user_text:      The user's message content.
        model_family:   One of the keys in FAMILY_TO_MODEL.
        include_system: If True, prepend a system turn before the user turn.

    Returns:
        The formatted prompt string as it will be seen by the model.
        On error (e.g. no chat template defined), returns a descriptive error string.

    TODO:
      1. Call get_tokenizer(model_family).
      2. Build messages list:
           - If include_system is True, start with:
               {"role": "system", "content": "You are a helpful assistant."}
           - Always append: {"role": "user", "content": user_text}
      3. Call:
           tokenizer.apply_chat_template(
               messages,
               tokenize=False,
               add_generation_prompt=True,
           )
      4. Return the resulting string.
      5. Wrap in try/except Exception and return f"[Error: {e}]" on failure.
    """
    # TODO: implement build_chat_template_preview
    raise NotImplementedError("build_chat_template_preview() is not implemented yet.")
