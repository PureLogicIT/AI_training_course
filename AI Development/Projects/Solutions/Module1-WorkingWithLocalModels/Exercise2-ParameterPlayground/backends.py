"""
backends.py — Backend abstraction for Exercise 2 (SOLUTION)
============================================================
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

SYSTEM_PROMPT = (
    "You are a helpful assistant. "
    "Answer the user's question clearly and concisely."
)


@runtime_checkable
class BackendProtocol(Protocol):
    @property
    def name(self) -> str: ...

    def generate(self, prompt: str, params: dict) -> str: ...


class OllamaBackend:
    """Calls a local Ollama server via the ollama Python SDK."""

    def __init__(self, model: str, host: str = "http://localhost:11434") -> None:
        import ollama
        self._model = model
        self._client = ollama.Client(host=host)

    @property
    def name(self) -> str:
        return "Ollama"

    def generate(self, prompt: str, params: dict) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = self._client.chat(
            model=self._model,
            messages=messages,
            options=params,
            stream=False,
        )
        return response.message.content


class LlamaCppBackend:
    """Loads a GGUF model file directly using llama-cpp-python."""

    def __init__(self, model_path: str, n_threads: int = 4) -> None:
        from llama_cpp import Llama
        self._llm = Llama(
            model_path=model_path,
            n_ctx=8192,
            n_threads=n_threads,
            verbose=False,
        )

    @property
    def name(self) -> str:
        return "llama-cpp-python"

    def generate(self, prompt: str, params: dict) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = self._llm.create_chat_completion(
            messages=messages,
            temperature=params.get("temperature", 0.7),
            top_p=params.get("top_p", 0.9),
            top_k=int(params.get("top_k", 40)),
            repeat_penalty=params.get("repeat_penalty", 1.1),
            seed=int(params.get("seed", -1)),
            max_tokens=512,
        )
        return response["choices"][0]["message"]["content"]
