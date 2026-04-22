"""
rag_engine.py — Core indexing and RAG chain logic for Exercise 1.

This module is imported by app.py. Your job is to implement the three
functions below. Do not modify the function signatures.
"""

import os
from typing import List, Tuple

from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# TODO 1 — Implement index_documents()
# ---------------------------------------------------------------------------
def index_documents(file_paths: List[str]):
    """
    Load text/markdown files, chunk them, and build an in-memory Chroma store.

    Args:
        file_paths: List of absolute file paths to .txt or .md files.

    Returns:
        A Chroma vectorstore instance (in-memory, no persist_directory).

    Steps:
        1. Import TextLoader from langchain_community.document_loaders.
        2. Loop over file_paths. For each path, load with TextLoader(path, encoding="utf-8").
           Catch exceptions, print a warning, and skip files that fail.
           Collect all Document objects into a single list called `all_docs`.
        3. Import RecursiveCharacterTextSplitter from langchain_text_splitters.
           Split with chunk_size=500, chunk_overlap=50.
        4. Import OllamaEmbeddings from langchain_ollama.
           Read OLLAMA_BASE_URL from the environment (default: "http://localhost:11434").
           Create OllamaEmbeddings(model="nomic-embed-text", base_url=...).
        5. Import Chroma from langchain_chroma.
           Call Chroma.from_documents(chunks, embeddings, collection_name="session_docs").
           Do NOT set persist_directory — this keeps the store in-memory only.
        6. Return the Chroma vectorstore.
    """
    # TODO: implement this function
    raise NotImplementedError("index_documents() is not yet implemented.")


# ---------------------------------------------------------------------------
# TODO 2 — Implement build_rag_chain()
# ---------------------------------------------------------------------------
def build_rag_chain(vectorstore):
    """
    Build a create_retrieval_chain RAG chain over the given Chroma vectorstore.

    Args:
        vectorstore: A Chroma vectorstore returned by index_documents().

    Returns:
        A LangChain retrieval chain (the result of create_retrieval_chain()).

    Steps:
        1. Import ChatOllama from langchain_ollama.
           Read OLLAMA_BASE_URL from the environment (default: "http://localhost:11434").
           Create ChatOllama(model="llama3.2", temperature=0.0, num_ctx=8192,
                             base_url=...).
        2. Create a retriever from the vectorstore using MMR search:
               vectorstore.as_retriever(
                   search_type="mmr",
                   search_kwargs={"k": 4, "fetch_k": 15},
               )
        3. Import ChatPromptTemplate from langchain_core.prompts.
           Write a prompt with a system message instructing the LLM to answer only
           from the context. The system message must use the placeholder {context}.
           The human turn must use {input}.
           If the answer is not in the context the model should say:
               "I don't have information about that in the uploaded documents."
        4. Import create_stuff_documents_chain from langchain.chains.combine_documents.
           Import create_retrieval_chain from langchain.chains.retrieval.
           Build combine_docs_chain = create_stuff_documents_chain(llm, prompt).
           Build rag_chain = create_retrieval_chain(retriever, combine_docs_chain).
        5. Return rag_chain.
    """
    # TODO: implement this function
    raise NotImplementedError("build_rag_chain() is not yet implemented.")


# ---------------------------------------------------------------------------
# TODO 3 — Implement ask_question()
# ---------------------------------------------------------------------------
def ask_question(rag_chain, question: str) -> Tuple[str, List[Document]]:
    """
    Run a single question through the RAG chain.

    Args:
        rag_chain: The chain returned by build_rag_chain().
        question:  The user's question string.

    Returns:
        A tuple (answer, source_chunks) where:
            - answer       is the string answer from the LLM.
            - source_chunks is the list of Document objects from result["context"].

    Steps:
        1. Call rag_chain.invoke({"input": question}).
        2. Extract result["answer"] as the answer string.
        3. Extract result["context"] as the list of source Document objects.
        4. Return (answer, source_chunks).
    """
    # TODO: implement this function
    raise NotImplementedError("ask_question() is not yet implemented.")
