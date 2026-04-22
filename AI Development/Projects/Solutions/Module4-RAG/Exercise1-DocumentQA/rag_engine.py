"""
rag_engine.py — Core indexing and RAG chain logic for Exercise 1 (SOLUTION).
"""

import os
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def index_documents(file_paths: List[str]) -> Chroma:
    """
    Load text/markdown files, chunk them, and build an in-memory Chroma store.
    """
    all_docs: List[Document] = []

    for path in file_paths:
        try:
            loader = TextLoader(path, encoding="utf-8")
            docs = loader.load()
            all_docs.extend(docs)
        except Exception as exc:
            print(f"Warning: could not load '{path}': {exc}")

    if not all_docs:
        raise ValueError("No documents could be loaded from the provided files.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )
    chunks = splitter.split_documents(all_docs)

    embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_BASE_URL)

    # No persist_directory — in-memory only for this session
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name="session_docs",
    )

    return vectorstore


def build_rag_chain(vectorstore: Chroma):
    """
    Build a create_retrieval_chain RAG chain over the given Chroma vectorstore.
    """
    llm = ChatOllama(
        model="llama3.2",
        temperature=0.0,
        num_ctx=8192,
        base_url=OLLAMA_BASE_URL,
    )

    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4, "fetch_k": 15},
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a helpful assistant. Answer the user's question using ONLY "
            "the information in the context provided below. "
            "If the answer is not present in the context, respond with exactly: "
            "'I don't have information about that in the uploaded documents.' "
            "Do not make up facts or use information outside the context.\n\n"
            "Context:\n{context}",
        ),
        ("human", "{input}"),
    ])

    combine_docs_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, combine_docs_chain)
    return rag_chain


def ask_question(rag_chain, question: str) -> Tuple[str, List[Document]]:
    """
    Run a single question through the RAG chain.
    """
    result = rag_chain.invoke({"input": question})
    answer = result["answer"]
    source_chunks = result["context"]
    return answer, source_chunks
