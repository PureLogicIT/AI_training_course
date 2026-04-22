"""
history_store.py — Session persistence helpers for Exercise 3.

Complete both TODOs to enable save/load of named conversation sessions.
"""

import json
from pathlib import Path
from typing import Optional

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Map role strings (used in JSON) to LangChain message classes
ROLE_TO_CLASS = {
    "human": HumanMessage,
    "ai": AIMessage,
    "system": SystemMessage,
}


# ---------------------------------------------------------------------------
# TODO A — Implement save_session
# ---------------------------------------------------------------------------

def save_session(
    session_id: str,
    history: ChatMessageHistory,
    sessions_dir: str,
) -> None:
    """
    Serialise `history` to a JSON file at `{sessions_dir}/{session_id}.json`.

    JSON format — a list of message dicts:
        [
            {"role": "human", "content": "..."},
            {"role": "ai",    "content": "..."},
            ...
        ]

    Role mapping:
        HumanMessage  -> "human"
        AIMessage     -> "ai"
        SystemMessage -> "system"

    Steps:
    1. Ensure sessions_dir exists (use pathlib.Path.mkdir with parents=True, exist_ok=True).
    2. Build a list of {"role": ..., "content": msg.content} dicts from history.messages.
       Hint: use isinstance(msg, HumanMessage) etc., or derive from type(msg).__name__.
    3. Write the list as JSON to the file path.
    """
    # YOUR CODE HERE
    pass


# ---------------------------------------------------------------------------
# TODO B — Implement load_session
# ---------------------------------------------------------------------------

def load_session(
    session_id: str,
    sessions_dir: str,
) -> Optional[ChatMessageHistory]:
    """
    Load and return a ChatMessageHistory from `{sessions_dir}/{session_id}.json`.
    Return None if the file does not exist.

    Steps:
    1. Check whether the file exists. If not, return None.
    2. Read the JSON file and parse the list of message dicts.
    3. For each dict, look up the class in ROLE_TO_CLASS and construct the message.
    4. Construct a new ChatMessageHistory and assign the message list to .messages.
    5. Return the history.
    """
    # YOUR CODE HERE
    pass
