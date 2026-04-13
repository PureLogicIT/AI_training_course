"""
devlog.py — Developer work-log tool.

Usage:
    python3 devlog.py                    # Interactive prompt: log a new entry
    python3 devlog.py --list             # Print all log entries
    python3 devlog.py --search <keyword> # Search entries containing keyword
    python3 devlog.py --delete <id>      # Delete an entry by ID number
"""

import sys
from datetime import date
from config import LOG_FILE, DATE_FORMAT, MAX_ENTRIES


def log_entry(message: str) -> dict:
    """
    Create a new log entry dictionary with today's date and a sequential ID.

    Determines the next ID by counting existing lines in LOG_FILE.

    Args:
        message: The text content of the log entry.

    Returns:
        A dict with keys 'id', 'date', and 'message'.
    """
    existing = list_entries()
    next_id = len(existing) + 1
    today = date.today().strftime(DATE_FORMAT)
    entry = {"id": next_id, "date": today, "message": message}

    with open(LOG_FILE, "a") as f:
        f.write(f"{next_id}|{today}|{message}\n")

    print("Entry saved.")
    return entry


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


# --- search feature ---
def search_entries(keyword: str) -> list:
    """Return all log entries containing keyword (case-insensitive)."""
    entries = list_entries()
    keyword_lower = keyword.lower()
    return [e for e in entries if keyword_lower in e.lower()]


# --- delete feature ---
def delete_entry(entry_id: int) -> bool:
    """
    Remove the log entry with the given ID from LOG_FILE.

    Returns True if an entry was found and removed, False otherwise.
    """
    entries = list_entries()
    original_count = len(entries)
    remaining = [e for e in entries if not e.startswith(f"{entry_id}|")]

    if len(remaining) == original_count:
        return False

    with open(LOG_FILE, "w") as f:
        for entry in remaining:
            f.write(entry + "\n")
    return True


def run():
    """
    Main entry point. Parse sys.argv and dispatch to the appropriate function.
    """
    if "--list" in sys.argv:
        entries = list_entries()
        if not entries:
            print("No entries found.")
        for entry in entries[:MAX_ENTRIES]:
            print(entry)

    elif "--search" in sys.argv:
        idx = sys.argv.index("--search")
        if idx + 1 >= len(sys.argv):
            print("Usage: python3 devlog.py --search <keyword>")
            sys.exit(1)
        keyword = sys.argv[idx + 1]
        results = search_entries(keyword)
        if not results:
            print(f"No entries found matching '{keyword}'.")
        for entry in results:
            print(entry)

    elif "--delete" in sys.argv:
        idx = sys.argv.index("--delete")
        if idx + 1 >= len(sys.argv):
            print("Usage: python3 devlog.py --delete <id>")
            sys.exit(1)
        try:
            entry_id = int(sys.argv[idx + 1])
        except ValueError:
            print("Error: ID must be an integer.")
            sys.exit(1)
        removed = delete_entry(entry_id)
        if removed:
            print(f"Entry {entry_id} deleted.")
        else:
            print(f"No entry found with ID {entry_id}.")

    else:
        message = input("Log entry: ").strip()
        if message:
            entry = log_entry(message)
            print(f"Recorded: {entry}")
        else:
            print("No message provided. Entry not saved.")


if __name__ == "__main__":
    run()
