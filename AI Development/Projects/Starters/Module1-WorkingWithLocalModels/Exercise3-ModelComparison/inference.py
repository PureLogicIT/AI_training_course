"""
inference.py — Streaming helpers for Exercise 3
================================================
Provides streaming and concurrent inference utilities.

Complete every TODO.
"""

from __future__ import annotations

import concurrent.futures
from typing import Generator, Any

import ollama


def stream_response(
    client: ollama.Client,
    model: str,
    messages: list[dict],
    options: dict | None = None,
) -> Generator[str | dict, None, None]:
    """Stream a chat response, yielding tokens then a final stats sentinel.

    Yields:
        str: Each token chunk as it arrives.
        dict: A final sentinel {"done": True, "stats": {"total_tokens": int,
              "tokens_per_sec": float}} after the stream ends.

    Args:
        client:   An ollama.Client instance.
        model:    Model name string.
        messages: Full conversation in Ollama message format.
        options:  Optional dict of inference parameters.
    """
    # TODO 2a: Call client.chat() with stream=True.
    # Iterate over chunks. For each chunk:
    #   - Yield chunk["message"]["content"] (the token text).
    #   - If chunk.get("done") is True, capture eval_count and eval_duration
    #     from the chunk to compute tokens_per_sec, then yield the stats sentinel.
    #
    # tokens_per_sec formula:
    #   eval_count / eval_duration * 1e9  (Ollama reports duration in nanoseconds)
    #   Guard against eval_duration == 0 with: max(eval_duration, 1)
    raise NotImplementedError("TODO 2a")


def compare_responses(
    client: ollama.Client,
    model_a: str,
    model_b: str,
    messages: list[dict],
    options: dict | None = None,
) -> tuple[tuple[str, dict], tuple[str, dict]]:
    """Run two models concurrently (non-streaming) and return both results.

    Returns:
        ((text_a, stats_a), (text_b, stats_b))
        Each stats dict has keys: "total_tokens" (int), "tokens_per_sec" (float).
        On error, text is an error message string and stats values are 0.

    Args:
        client:   An ollama.Client instance.
        model_a:  Name of the first model.
        model_b:  Name of the second model.
        messages: Shared messages list (both models receive identical input).
        options:  Optional inference parameters applied to both models.
    """
    def _call_model(model: str) -> tuple[str, dict]:
        # TODO 2b: Call client.chat() with stream=False for `model`.
        # Extract text from response.message.content.
        # Build stats from response fields:
        #   total_tokens = getattr(response, "eval_count", 0) or 0
        #   eval_duration = getattr(response, "eval_duration", 1) or 1
        #   tokens_per_sec = total_tokens / eval_duration * 1e9
        # Return (text, {"total_tokens": ..., "tokens_per_sec": ...}).
        # Wrap in try/except — return (f"Error: {exc}", {"total_tokens": 0, ...})
        raise NotImplementedError("TODO 2b")

    # TODO 2c: Use ThreadPoolExecutor to submit _call_model for both models
    # concurrently. Collect and return both results as ((text_a, stats_a), (text_b, stats_b)).
    raise NotImplementedError("TODO 2c")
