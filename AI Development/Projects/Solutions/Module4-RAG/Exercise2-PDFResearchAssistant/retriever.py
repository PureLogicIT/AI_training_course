"""
retriever.py — Scored retrieval and RAG chain construction (SOLUTION).
"""

import os
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def retrieve_with_scores(
    vectorstore,
    question: str,
    k: int = 5,
) -> List[Tuple[Document, float]]:
    """
    Return top-k chunks with L2 distance scores (lower = more similar).
    """
    return vectorstore.similarity_search_with_score(question, k=k)


def build_rag_chain(vectorstore, k: int = 5):
    """
    Build a create_retrieval_chain RAG chain over a FAISS vectorstore.
    """
    llm = ChatOllama(
        model="llama3.2",
        temperature=0.0,
        num_ctx=8192,
        base_url=OLLAMA_BASE_URL,
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": k})

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert research assistant. Answer the user's question "
            "using ONLY the document excerpts provided in the context. "
            "When possible, cite the page number from the excerpt metadata. "
            "If the answer is not found in the excerpts, say so explicitly — "
            "do not fabricate information.\n\nContext:\n{context}",
        ),
        ("human", "{input}"),
    ])

    combine_docs_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, combine_docs_chain)
    return rag_chain
