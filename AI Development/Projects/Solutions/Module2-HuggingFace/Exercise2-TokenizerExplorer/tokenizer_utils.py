"""
tokenizer_utils.py — SOLUTION
==============================
Helper module for loading and inspecting tokenizers from multiple model families.
"""

from transformers import AutoTokenizer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAMILY_TO_MODEL = {
    "smollm2":     "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    "llama3":      "meta-llama/Meta-Llama-3-8B-Instruct",
    "mistral":     "mistralai/Mistral-7B-Instruct-v0.1",
    "chatml_qwen": "Qwen/Qwen2.5-1.5B-Instruct",
}

_TOKENIZER_CACHE: dict = {}


# ---------------------------------------------------------------------------
# Tokenizer loader
# ---------------------------------------------------------------------------

def get_tokenizer(model_family: str) -> AutoTokenizer:
    """Load and cache a tokenizer for the given model family."""
    if model_family not in FAMILY_TO_MODEL:
        valid = list(FAMILY_TO_MODEL.keys())
        raise ValueError(
            f"Unknown model family: '{model_family}'. Valid choices: {valid}"
        )

    if model_family not in _TOKENIZER_CACHE:
        hub_id = FAMILY_TO_MODEL[model_family]
        print(f"Loading tokenizer: {hub_id} ...")
        _TOKENIZER_CACHE[model_family] = AutoTokenizer.from_pretrained(hub_id)
        print(f"Tokenizer cached for family '{model_family}'.")

    return _TOKENIZER_CACHE[model_family]


# ---------------------------------------------------------------------------
# Tokenize text
# ---------------------------------------------------------------------------

def tokenize_text(text: str, model_family: str) -> dict:
    """
    Encode text and return detailed tokenization information.

    Returns a dict with keys:
        token_ids, tokens, token_count, decoded, special_token_ids
    """
    tokenizer = get_tokenizer(model_family)

    token_ids = tokenizer.encode(text)
    tokens = tokenizer.convert_ids_to_tokens(token_ids)
    token_count = len(token_ids)
    decoded = tokenizer.decode(token_ids, skip_special_tokens=False)
    special_token_ids = set(tokenizer.all_special_ids)

    return {
        "token_ids": token_ids,
        "tokens": tokens,
        "token_count": token_count,
        "decoded": decoded,
        "special_token_ids": special_token_ids,
    }


# ---------------------------------------------------------------------------
# Chat template preview
# ---------------------------------------------------------------------------

def build_chat_template_preview(user_text: str, model_family: str,
                                  include_system: bool) -> str:
    """Apply the tokenizer's chat template and return the formatted string."""
    try:
        tokenizer = get_tokenizer(model_family)

        messages = []
        if include_system:
            messages.append({"role": "system", "content": "You are a helpful assistant."})
        messages.append({"role": "user", "content": user_text})

        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    except Exception as e:
        return f"[Error applying chat template: {e}]"
