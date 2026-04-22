"""
stats.py — Simple in-memory usage statistics tracker (SOLUTION).
"""

from knowledge_base import list_indexed_documents

_query_count: int = 0


def increment_queries() -> None:
    """Increment the global query counter by 1."""
    global _query_count
    _query_count += 1


def get_stats(vectorstore) -> dict:
    """Return current usage statistics."""
    return {
        "queries_answered": _query_count,
        "total_chunks": vectorstore._collection.count(),
        "unique_documents": len(list_indexed_documents(vectorstore)),
    }


def format_stats(stats: dict) -> str:
    """Format a stats dict as a human-readable string."""
    return (
        f"Documents indexed: {stats['unique_documents']}\n"
        f"Total chunks:      {stats['total_chunks']}\n"
        f"Queries answered:  {stats['queries_answered']}"
    )
