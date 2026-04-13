"""
devlog.py — Developer work-log tool.

Usage:
    python3 devlog.py              # Interactive prompt
    python3 devlog.py --list       # Print all log entries
    python3 devlog.py --search     # (stub) Search entries by keyword
    python3 devlog.py --delete     # (stub) Delete an entry by ID
"""

import sys
from datetime import date
from config import LOG_FILE, DATE_FORMAT


def log_entry(message: str) -> dict:
    """
    Create a new log entry dictionary with today's date.

    Args:
        message: The text content of the log entry.

    Returns:
        A dict with keys 'id', 'date', and 'message'.

    # TODO (Exercise 1, Part B): Replace this stub with a real implementation.
    # The function should return a dict, e.g.:
    #   {"id": 1, "date": "2026-03-29", "message": message}
    """
    pass


def list_entries() -> list:
    """
    Read and return all entries from LOG_FILE.
    Returns an empty list if the file does not exist.
    """
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
        return [line.strip() for line in lines if line.strip()]
    except FileNotFoundError:
        return []


def run():
    """
    Main entry point. Parse sys.argv and dispatch to the appropriate function.

    Supported flags:
        --list    Print all stored entries.
        (no flag) Prompt the user for a new log message and save it.

    # TODO (Exercise 2, feature/search branch):
    #   Add: if "--search" in sys.argv: call search_entries(keyword)
    # TODO (Exercise 2, feature/delete branch):
    #   Add: if "--delete" in sys.argv: call delete_entry(entry_id)
    """
    if "--list" in sys.argv:
        entries = list_entries()
        if not entries:
            print("No entries found.")
        for entry in entries:
            print(entry)
    else:
        message = input("Log entry: ").strip()
        if message:
            entry = log_entry(message)
            print(f"Saved: {entry}")
        else:
            print("No message provided. Entry not saved.")


if __name__ == "__main__":
    run()
