"""
history_store.py - Session persistence helpers for Exercise 3  (SOLUTION)
"""

import json
from pathlib import Path
from typing import Optional

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

ROLE_TO_CLASS = {
    "human": HumanMessage,
    "ai": AIMessage,
    "system": SystemMessage,
}

# Reverse map: message class -> role string
CLASS_TO_ROLE = {
    HumanMessage: "human",
    AIMessage: "ai",
    SystemMessage: "system",
}


def save_session(
    session_id: str,
    history: ChatMessageHistory,
    sessions_dir: str,
) -> None:
    """Serialise history to {sessions_dir}/{session_id}.json."""
    Path(sessions_dir).mkdir(parents=True, exist_ok=True)
    file_path = Path(sessions_dir) / f"{session_id}.json"

    messages_data = []
    for msg in history.messages:
        role = CLASS_TO_ROLE.get(type(msg), "unknown")
        messages_data.append({"role": role, "content": msg.content})

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(messages_data, f, indent=2, ensure_ascii=False)


def load_session(
    session_id: str,
    sessions_dir: str,
) -> Optional[ChatMessageHistory]:
    """Load and return ChatMessageHistory from disk, or None if not found."""
    file_path = Path(sessions_dir) / f"{session_id}.json"

    if not file_path.exists():
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        messages_data = json.load(f)

    history = ChatMessageHistory()
    messages = []
    for item in messages_data:
        msg_class = ROLE_TO_CLASS.get(item["role"])
        if msg_class is not None:
            messages.append(msg_class(content=item["content"]))
    history.messages = messages
    return history
