"""
stats.py — Simple in-memory usage statistics tracker.

Implement the three functions below.
"""

from knowledge_base import list_indexed_documents

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_query_count: int = 0


# ---------------------------------------------------------------------------
# TODO 9 — Implement increment_queries()
# ---------------------------------------------------------------------------
def increment_queries() -> None:
    """
    Increment the global query counter by 1.

    Steps:
        global _query_count
        _query_count += 1
    """
    # TODO: implement this function
    pass


# ---------------------------------------------------------------------------
# TODO 10 — Implement get_stats()
# ---------------------------------------------------------------------------
def get_stats(vectorstore) -> dict:
    """
    Return a dict with current usage statistics.

    Args:
        vectorstore: A Chroma vectorstore instance.

    Returns:
        Dict with keys:
            "queries_answered"  — int, current value of _query_count
            "total_chunks"      — int, vectorstore._collection.count()
            "unique_documents"  — int, len(list_indexed_documents(vectorstore))

    Steps:
        Return the dict with those three keys populated.
    """
    # TODO: implement this function
    return {"queries_answered": 0, "total_chunks": 0, "unique_documents": 0}


def format_stats(stats: dict) -> str:
    """Format a stats dict as a human-readable string."""
    return (
        f"Documents indexed: {stats['unique_documents']}\n"
        f"Total chunks:      {stats['total_chunks']}\n"
        f"Queries answered:  {stats['queries_answered']}"
    )
