"""
benchmark_engine.py
===================
Core inference and measurement logic for Exercise 3: Model Benchmark & Comparison.

Provides:
  - load_model_and_tokenizer()  : load a model + tokenizer and record load time/RAM
  - run_single_inference()      : run one prompt and collect all six metrics
  - unload_model()              : release model memory between runs
  - run_benchmark()             : orchestrate the full benchmark loop

Complete all TODO sections. Do not change the function signatures.
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

# Supported models for benchmarking
AVAILABLE_MODELS = {
    "HuggingFaceTB/SmolLM2-1.7B-Instruct": "SmolLM2-1.7B",
    "Qwen/Qwen2.5-1.5B-Instruct":           "Qwen2.5-1.5B",
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0":   "TinyLlama-1.1B",
}


# ---------------------------------------------------------------------------
# Helper: current process RSS in MB
# ---------------------------------------------------------------------------

def _rss_mb() -> float:
    """Return the current process RSS (Resident Set Size) in megabytes."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 ** 2)


# ---------------------------------------------------------------------------
# Step 1a: Model loader
# ---------------------------------------------------------------------------

def load_model_and_tokenizer(model_id: str) -> tuple:
    """
    Load a model and tokenizer from the Hugging Face Hub (or local cache).

    Args:
        model_id: A Hub repo ID string (must be a key in AVAILABLE_MODELS).

    Returns:
        (model, tokenizer, load_time_s, load_ram_mb)
          - model:        Loaded AutoModelForCausalLM in eval mode.
          - tokenizer:    Loaded AutoTokenizer.
          - load_time_s:  Wall-clock seconds taken for from_pretrained() calls.
          - load_ram_mb:  Net RSS increase in MB during loading.

    TODO:
      1. Record mem_before = _rss_mb() and t_start = time.perf_counter().
      2. Load tokenizer: AutoTokenizer.from_pretrained(model_id).
      3. Load model: AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float32).
      4. Call model.eval().
      5. Record t_end = time.perf_counter() and mem_after = _rss_mb().
      6. Return (model, tokenizer, t_end - t_start, mem_after - mem_before).
    """
    # TODO: implement load_model_and_tokenizer
    raise NotImplementedError("load_model_and_tokenizer() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 1b: Single inference run
# ---------------------------------------------------------------------------

def run_single_inference(model, tokenizer, prompt_text: str,
                          max_new_tokens: int) -> dict:
    """
    Run one inference pass and collect all benchmark metrics.

    Args:
        model:          A loaded model in eval mode.
        tokenizer:      The matching tokenizer.
        prompt_text:    The raw user prompt string.
        max_new_tokens: Maximum tokens to generate.

    Returns:
        A dict with keys:
          "response_text"      : str   — decoded generated text
          "input_tokens"       : int   — token count of the formatted prompt
          "output_tokens"      : int   — token count of the generated response
          "generation_time_s"  : float — wall-clock seconds for model.generate()
          "tokens_per_sec"     : float — output_tokens / generation_time_s
          "peak_ram_mb"        : float — net RSS increase during generation (MB)

    TODO:
      1. Format the prompt with apply_chat_template():
           messages = [{"role": "user", "content": prompt_text}]
           input_ids = tokenizer.apply_chat_template(
               messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
           )
         If the tokenizer has no chat_template, fall back to:
           input_ids = tokenizer(
               f"User: {prompt_text}\nAssistant:", return_tensors="pt"
           )["input_ids"]

      2. Count input tokens: input_tokens = input_ids.shape[1]

      3. Record mem_before = _rss_mb() and t_start = time.perf_counter().

      4. Inside torch.no_grad(), call model.generate() with:
           - max_new_tokens=max_new_tokens
           - do_sample=False
           - pad_token_id=tokenizer.eos_token_id

      5. Record t_end = time.perf_counter() and mem_after = _rss_mb().

      6. Slice off input tokens from output:
           generated_ids = output_ids[0][input_tokens:]
         Decode: tokenizer.decode(generated_ids, skip_special_tokens=True)

      7. Count output_tokens = len(generated_ids)

      8. Return the dict with all six metrics.
    """
    # TODO: implement run_single_inference
    raise NotImplementedError("run_single_inference() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 1c: Model unloader
# ---------------------------------------------------------------------------

def unload_model(model, tokenizer) -> None:
    """
    Release model and tokenizer from memory.

    TODO:
      1. del model
      2. del tokenizer
      3. gc.collect()
      4. torch.cuda.empty_cache()   (no-op on CPU; safe to call)
    """
    # TODO: implement unload_model
    raise NotImplementedError("unload_model() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 1d: Benchmark orchestrator
# ---------------------------------------------------------------------------

def run_benchmark(model_ids: list, prompts: list, max_new_tokens: int,
                   progress_callback=None) -> list:
    """
    Run all prompts through all models and return a flat list of result dicts.

    Each result dict contains:
      "model_id"           : str
      "model_short_name"   : str   — from AVAILABLE_MODELS lookup
      "prompt_preview"     : str   — first 80 characters of the prompt
      "response_text"      : str
      "input_tokens"       : int
      "output_tokens"      : int
      "generation_time_s"  : float
      "tokens_per_sec"     : float
      "peak_ram_mb"        : float
      "load_time_s"        : float
      "load_ram_mb"        : float

    Args:
        model_ids:         List of Hub repo ID strings to benchmark.
        prompts:           List of prompt text strings.
        max_new_tokens:    Maximum tokens to generate per inference call.
        progress_callback: Optional callable(status_str: str) called before each prompt.

    TODO:
      1. Initialize results = [].
      2. For i, model_id in enumerate(model_ids):
           a. If progress_callback: call it with f"Loading model {i+1}/{len(model_ids)}: {model_id}"
           b. Call load_model_and_tokenizer(model_id).
           c. For j, prompt in enumerate(prompts):
                - If progress_callback: call it with
                    f"Model {i+1}/{len(model_ids)} — Prompt {j+1}/{len(prompts)}: {prompt[:40]}..."
                - Call run_single_inference(model, tokenizer, prompt, max_new_tokens).
                - Build the result dict by merging inference metrics with model metadata.
                - Append to results.
           d. Call unload_model(model, tokenizer).
      3. Return results.
    """
    # TODO: implement run_benchmark
    raise NotImplementedError("run_benchmark() is not implemented yet.")
