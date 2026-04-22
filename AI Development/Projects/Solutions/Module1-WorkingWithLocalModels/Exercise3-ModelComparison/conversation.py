"""
conversation.py — ConversationManager (SOLUTION)
"""

from __future__ import annotations

import json
from pathlib import Path


class ConversationManager:
    """Manages a multi-turn conversation history with save/load support."""

    def __init__(self, system_prompt: str = "") -> None:
        self._system_prompt = system_prompt
        self._messages: list[dict] = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})

    # ------------------------------------------------------------------
    # Mutation methods
    # ------------------------------------------------------------------

    def add_user(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})

    def add_assistant(self, text: str, model_name: str = "") -> None:
        self._messages.append({"role": "assistant", "content": text, "model": model_name})

    def clear(self, keep_system: bool = True) -> None:
        self._messages = []
        if keep_system and self._system_prompt:
            self._messages.append({"role": "system", "content": self._system_prompt})

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_ollama_messages(self) -> list[dict]:
        """Return messages with the non-standard 'model' key stripped."""
        result = []
        for msg in self._messages:
            clean = {k: v for k, v in msg.items() if k != "model"}
            result.append(clean)
        return result

    def to_gradio_history(self) -> list[list[str | None]]:
        """Convert to [[user_text, assistant_text], ...] for Gradio Chatbot."""
        history: list[list[str | None]] = []
        non_system = [m for m in self._messages if m["role"] != "system"]

        i = 0
        while i < len(non_system):
            msg = non_system[i]
            if msg["role"] == "user":
                user_text = msg["content"]
                # Look ahead for an assistant message
                if i + 1 < len(non_system) and non_system[i + 1]["role"] == "assistant":
                    assistant_text: str | None = non_system[i + 1]["content"]
                    i += 2
                else:
                    assistant_text = None
                    i += 1
                history.append([user_text, assistant_text])
            else:
                # Orphan assistant message (e.g. switch marker without preceding user)
                i += 1

        return history

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self._messages if m["role"] == "user")

    # ------------------------------------------------------------------
    # Persistence methods
    # ------------------------------------------------------------------

    def save_to_json(self, filepath: str) -> None:
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self._messages, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            raise IOError(f"Could not write conversation to '{filepath}': {exc}") from exc

    def load_from_json(self, filepath: str) -> None:
        try:
            raw = Path(filepath).read_text(encoding="utf-8")
        except Exception as exc:
            raise IOError(f"Could not read file '{filepath}': {exc}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"File is not valid JSON: {exc}") from exc

        if not isinstance(data, list):
            raise ValueError("Conversation file must contain a JSON array.")

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(f"Entry {i} is not a JSON object.")
            if "role" not in item or "content" not in item:
                raise ValueError(
                    f"Entry {i} is missing required keys 'role' and/or 'content'."
                )

        self._messages = data
