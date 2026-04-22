"""
conversation.py — ConversationManager for Exercise 3
=====================================================
Owns the message history for a single chat session.

Complete every TODO. The public method signatures must not change.
"""

from __future__ import annotations

import json
from pathlib import Path


class ConversationManager:
    """Manages a multi-turn conversation history with save/load support."""

    def __init__(self, system_prompt: str = "") -> None:
        # TODO 1a: Initialise self._messages as an empty list.
        # If system_prompt is non-empty, append the system message dict.
        self._system_prompt = system_prompt
        self._messages: list[dict] = []
        raise NotImplementedError("TODO 1a")

    # ------------------------------------------------------------------
    # Mutation methods
    # ------------------------------------------------------------------

    def add_user(self, text: str) -> None:
        """Append a user message to the history."""
        # TODO 1b: Append {"role": "user", "content": text}
        raise NotImplementedError("TODO 1b")

    def add_assistant(self, text: str, model_name: str = "") -> None:
        """Append an assistant message, optionally tagging it with a model name."""
        # TODO 1c: Append {"role": "assistant", "content": text, "model": model_name}
        raise NotImplementedError("TODO 1c")

    def clear(self, keep_system: bool = True) -> None:
        """Reset history. Keeps the system message if keep_system is True."""
        # TODO 1d: Reset self._messages.
        # If keep_system and self._system_prompt, re-add the system message.
        raise NotImplementedError("TODO 1d")

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_ollama_messages(self) -> list[dict]:
        """Return messages stripped of the non-standard 'model' key."""
        # TODO 1e: Return a copy of self._messages where each dict has the
        # 'model' key removed if present. Do not modify self._messages.
        raise NotImplementedError("TODO 1e")

    def to_gradio_history(self) -> list[list[str | None]]:
        """Convert messages to [[user_text, assistant_text], ...] format.

        Rules:
        - Skip system messages.
        - Pair each user message with the next assistant message.
        - If a user message has no following assistant message, pair with None.
        """
        # TODO 1f: Build and return the Gradio history list.
        raise NotImplementedError("TODO 1f")

    @property
    def turn_count(self) -> int:
        """Return the number of user turns in the history."""
        # TODO 1g: Count messages where role == "user"
        raise NotImplementedError("TODO 1g")

    # ------------------------------------------------------------------
    # Persistence methods
    # ------------------------------------------------------------------

    def save_to_json(self, filepath: str) -> None:
        """Write the full message history to a JSON file.

        Raises:
            IOError: If the file cannot be written.
        """
        # TODO 1h: Write self._messages to filepath using json.dumps with indent=2.
        # Wrap in try/except and raise IOError with a descriptive message on failure.
        raise NotImplementedError("TODO 1h")

    def load_from_json(self, filepath: str) -> None:
        """Load message history from a JSON file, replacing the current history.

        Validation rules:
        - The file must contain a JSON array.
        - Each element must be a dict with at least "role" and "content" keys.

        Raises:
            ValueError: If the file content fails validation.
            IOError: If the file cannot be read.
        """
        # TODO 1i: Read the file, parse JSON, validate, and replace self._messages.
        raise NotImplementedError("TODO 1i")
