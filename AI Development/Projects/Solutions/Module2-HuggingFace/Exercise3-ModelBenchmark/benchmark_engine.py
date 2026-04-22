"""
benchmark_engine.py — SOLUTION
================================
Core inference and measurement logic for Exercise 3: Model Benchmark & Comparison.
"""

import gc
import os
import time

import psutil
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AVAILABLE_MODELS = {
    "HuggingFaceTB/SmolLM2-1.7B-Instruct": "SmolLM2-1.7B",
    "Qwen/Qwen2.5-1.5B-Instruct":           "Qwen2.5-1.5B",
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0":   "TinyLlama-1.1B",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _rss_mb() -> float:
    """Return the current process RSS in megabytes."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 ** 2)


# ---------------------------------------------------------------------------
# Model loader
# ---------------------------------------------------------------------------

def load_model_and_tokenizer(model_id: str) -> tuple:
    """
    Load a model and tokenizer from Hub (or cache) and measure load time and RAM.

    Returns:
        (model, tokenizer, load_time_s, load_ram_mb)
    """
    mem_before = _rss_mb()
    t_start = time.perf_counter()

    print(f"Loading tokenizer: {model_id}")
    tokenizer = AutoTokenizer.from_pretrained(model_id)

    print(f"Loading model: {model_id} (torch_dtype=float32, CPU)")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float32,
    )
    model.eval()

    t_end = time.perf_counter()
    mem_after = _rss_mb()

    load_time_s = t_end - t_start
    load_ram_mb = max(0.0, mem_after - mem_before)

    print(f"Loaded {model_id} in {load_time_s:.1f}s, +{load_ram_mb:.0f} MB RAM")
    return model, tokenizer, load_time_s, load_ram_mb


# ---------------------------------------------------------------------------
# Single inference
# ---------------------------------------------------------------------------

def run_single_inference(model, tokenizer, prompt_text: str,
                          max_new_tokens: int) -> dict:
    """
    Run one inference pass and collect all benchmark metrics.

    Returns a dict with: response_text, input_tokens, output_tokens,
    generation_time_s, tokens_per_sec, peak_ram_mb.
    """
    # Format prompt using chat template if available, else plain format
    if tokenizer.chat_template is not None:
        messages = [{"role": "user", "content": prompt_text}]
        input_ids = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        )
    else:
        formatted = f"User: {prompt_text}\nAssistant:"
        input_ids = tokenizer(formatted, return_tensors="pt")["input_ids"]

    input_tokens = input_ids.shape[1]

    # Measure generation time and RAM
    mem_before = _rss_mb()
    t_start = time.perf_counter()

    with torch.no_grad():
        output_ids = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    t_end = time.perf_counter()
    mem_after = _rss_mb()

    generation_time_s = t_end - t_start
    peak_ram_mb = max(0.0, mem_after - mem_before)

    # Decode only the generated portion
    generated_ids = output_ids[0][input_tokens:]
    response_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
    output_tokens = len(generated_ids)

    tokens_per_sec = output_tokens / generation_time_s if generation_time_s > 0 else 0.0

    return {
        "response_text":     response_text,
        "input_tokens":      input_tokens,
        "output_tokens":     output_tokens,
        "generation_time_s": round(generation_time_s, 2),
        "tokens_per_sec":    round(tokens_per_sec, 2),
        "peak_ram_mb":       round(peak_ram_mb, 1),
    }


# ---------------------------------------------------------------------------
# Model unloader
# ---------------------------------------------------------------------------

def unload_model(model, tokenizer) -> None:
    """Release model and tokenizer from memory and run garbage collection."""
    del model
    del tokenizer
    gc.collect()
    torch.cuda.empty_cache()  # no-op on CPU; safe to call


# ---------------------------------------------------------------------------
# Benchmark orchestrator
# ---------------------------------------------------------------------------

def run_benchmark(model_ids: list, prompts: list, max_new_tokens: int,
                   progress_callback=None) -> list:
    """
    Run all prompts through all models sequentially.

    Loads each model, runs all prompts, unloads, then moves to the next model.
    Returns a flat list of result dicts.
    """
    results = []
    total_models = len(model_ids)

    for i, model_id in enumerate(model_ids):
        short_name = AVAILABLE_MODELS.get(model_id, model_id.split("/")[-1])

        if progress_callback:
            progress_callback(
                f"Loading model {i + 1}/{total_models}: {short_name}..."
            )

        model, tokenizer, load_time_s, load_ram_mb = load_model_and_tokenizer(model_id)

        for j, prompt in enumerate(prompts):
            if progress_callback:
                progress_callback(
                    f"Model {i + 1}/{total_models} ({short_name}) — "
                    f"Prompt {j + 1}/{len(prompts)}: {prompt[:40]}..."
                )

            metrics = run_single_inference(model, tokenizer, prompt, max_new_tokens)

            result = {
                "model_id":          model_id,
                "model_short_name":  short_name,
                "prompt_preview":    prompt[:80],
                "load_time_s":       round(load_time_s, 1),
                "load_ram_mb":       round(load_ram_mb, 0),
                **metrics,
            }
            results.append(result)

        if progress_callback:
            progress_callback(f"Unloading {short_name}...")
        unload_model(model, tokenizer)

    return results
