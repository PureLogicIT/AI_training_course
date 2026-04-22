"""
backends.py — Backend abstraction for Exercise 2
=================================================
Defines a lightweight protocol and two concrete backend classes:
  - OllamaBackend   : uses the ollama Python SDK
  - LlamaCppBackend : uses llama-cpp-python

Complete every TODO. The `generate()` method signature must remain unchanged
because app.py calls it without knowing which backend is active.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

SYSTEM_PROMPT = (
    "You are a helpful assistant. "
    "Answer the user's question clearly and concisely."
)


@runtime_checkable
class BackendProtocol(Protocol):
    """Structural interface that both backends must satisfy."""

    @property
    def name(self) -> str:
        """Human-readable backend name (e.g. 'Ollama')."""
        ...

    def generate(self, prompt: str, params: dict) -> str:
        """Run a single-turn inference and return the response text.

        Args:
            prompt: The user's prompt string.
            params: Dict of inference parameters. Keys match Ollama's options
                    dict names: temperature, top_p, top_k, repeat_penalty,
                    num_ctx, seed (seed may be absent — treat as random).

        Returns:
            The model's response as a plain string.
        """
        ...


# ---------------------------------------------------------------------------
# TODO 1 — Implement OllamaBackend
# ---------------------------------------------------------------------------

class OllamaBackend:
    """Calls a local Ollama server via the ollama Python SDK."""

    def __init__(self, model: str, host: str = "http://localhost:11434") -> None:
        # TODO 1a: Import ollama and create a client bound to `host`.
        # Store the model name and client as instance attributes.
        raise NotImplementedError("TODO 1a: create ollama.Client")

    @property
    def name(self) -> str:
        # TODO 1b: Return "Ollama"
        raise NotImplementedError("TODO 1b")

    def generate(self, prompt: str, params: dict) -> str:
        # TODO 1c: Build a messages list with SYSTEM_PROMPT + user prompt.
        # Call client.chat() with stream=False and options=params.
        # Return response.message.content (or response["message"]["content"]).
        raise NotImplementedError("TODO 1c")


# ---------------------------------------------------------------------------
# TODO 2 — Implement LlamaCppBackend
# ---------------------------------------------------------------------------

class LlamaCppBackend:
    """Loads a GGUF model file directly using llama-cpp-python."""

    def __init__(self, model_path: str, n_threads: int = 4) -> None:
        # TODO 2a: Import Llama from llama_cpp.
        # Load the model with:
        #   model_path=model_path
        #   n_ctx=8192      (generous max; UI num_ctx controls the budget)
        #   n_threads=n_threads
        #   verbose=False
        # Store as self._llm.
        raise NotImplementedError("TODO 2a: load Llama model")

    @property
    def name(self) -> str:
        # TODO 2b: Return "llama-cpp-python"
        raise NotImplementedError("TODO 2b")

    def generate(self, prompt: str, params: dict) -> str:
        # TODO 2c: Call self._llm.create_chat_completion() with:
        #   messages = [system dict, user dict]
        #   temperature = params.get("temperature", 0.7)
        #   top_p       = params.get("top_p", 0.9)
        #   top_k       = params.get("top_k", 40)
        #   repeat_penalty = params.get("repeat_penalty", 1.1)
        #   seed        = params.get("seed", -1)
        #   max_tokens  = 512
        # Return response["choices"][0]["message"]["content"].
        raise NotImplementedError("TODO 2c")
