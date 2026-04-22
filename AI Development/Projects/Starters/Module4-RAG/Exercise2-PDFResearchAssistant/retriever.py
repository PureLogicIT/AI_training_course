"""
retriever.py — Scored retrieval and RAG chain construction.

Implement the two functions below. Do not change the function signatures.
"""

import os
from typing import List, Tuple

from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# TODO 2 — Implement retrieve_with_scores()
# ---------------------------------------------------------------------------
def retrieve_with_scores(vectorstore, question: str, k: int = 5) -> List[Tuple[Document, float]]:
    """
    Return the top-k chunks most similar to `question`, with L2 distance scores.

    Args:
        vectorstore: A FAISS vectorstore instance.
        question:    The user's question string.
        k:           Number of results to return.

    Returns:
        A list of (Document, float) tuples ordered by ascending L2 distance.
        Lower L2 distance = more similar.

    Steps:
        1. Call vectorstore.similarity_search_with_score(question, k=k).
        2. Return the result directly — it is already a list of (Document, float).
    """
    # TODO: implement this function
    raise NotImplementedError("retrieve_with_scores() is not yet implemented.")


# ---------------------------------------------------------------------------
# TODO 3 — Implement build_rag_chain()
# ---------------------------------------------------------------------------
def build_rag_chain(vectorstore, k: int = 5):
    """
    Build a create_retrieval_chain RAG chain over a FAISS vectorstore.

    Args:
        vectorstore: A FAISS vectorstore instance.
        k:           Number of chunks to retrieve per question.

    Returns:
        A LangChain retrieval chain.

    Steps:
        1. Import ChatOllama from langchain_ollama.
           Read OLLAMA_BASE_URL from environment (default "http://localhost:11434").
           Create ChatOllama(model="llama3.2", temperature=0.0, num_ctx=8192,
                             base_url=...).

        2. Create a similarity retriever:
               vectorstore.as_retriever(search_kwargs={"k": k})

        3. Import ChatPromptTemplate from langchain_core.prompts.
           Write a system prompt that:
             - Instructs the model to answer from the provided excerpts only.
             - Asks the model to cite the page number from metadata when relevant.
             - Uses {context} for retrieved text and {input} for the question.

        4. Import create_stuff_documents_chain and create_retrieval_chain.
           Build and return the chain.
    """
    # TODO: implement this function
    raise NotImplementedError("build_rag_chain() is not yet implemented.")
