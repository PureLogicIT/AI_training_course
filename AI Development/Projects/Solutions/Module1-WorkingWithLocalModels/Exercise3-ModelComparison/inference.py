"""
inference.py — Streaming helpers (SOLUTION)
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
    """Stream a chat response, yielding tokens then a final stats sentinel."""
    stream = client.chat(
        model=model,
        messages=messages,
        options=options or {},
        stream=True,
    )

    for chunk in stream:
        token: str = chunk["message"]["content"]
        if token:
            yield token

        if chunk.get("done"):
            eval_count: int = chunk.get("eval_count", 0) or 0
            eval_duration: int = chunk.get("eval_duration", 1) or 1
            tokens_per_sec: float = eval_count / max(eval_duration, 1) * 1e9
            yield {
                "done": True,
                "stats": {
                    "total_tokens": eval_count,
                    "tokens_per_sec": tokens_per_sec,
                },
            }


def compare_responses(
    client: ollama.Client,
    model_a: str,
    model_b: str,
    messages: list[dict],
    options: dict | None = None,
) -> tuple[tuple[str, dict], tuple[str, dict]]:
    """Run two models concurrently (non-streaming) and return both results."""

    def _call_model(model: str) -> tuple[str, dict]:
        try:
            response = client.chat(
                model=model,
                messages=messages,
                options=options or {},
                stream=False,
            )
            text: str = response.message.content
            total_tokens: int = getattr(response, "eval_count", 0) or 0
            eval_duration: int = getattr(response, "eval_duration", 1) or 1
            tokens_per_sec: float = total_tokens / max(eval_duration, 1) * 1e9
            stats = {"total_tokens": total_tokens, "tokens_per_sec": tokens_per_sec}
            return text, stats
        except Exception as exc:
            return f"Error: {exc}", {"total_tokens": 0, "tokens_per_sec": 0.0}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(_call_model, model_a)
        future_b = executor.submit(_call_model, model_b)
        result_a = future_a.result()
        result_b = future_b.result()

    return result_a, result_b
