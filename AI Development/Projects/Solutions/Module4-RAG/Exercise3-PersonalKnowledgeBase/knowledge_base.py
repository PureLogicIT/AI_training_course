"""
knowledge_base.py — Document loading, indexing, and retrieval (SOLUTION).
"""

import os
from typing import List, Optional, Dict

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    WebBaseLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
import chromadb


def load_documents(source: str, source_type: str) -> List[Document]:
    """Load documents from a file path or URL."""
    if source_type == "pdf":
        docs = PyPDFLoader(source).load()
        for doc in docs:
            doc.metadata["doc_type"] = "pdf"

    elif source_type in ("txt", "md"):
        docs = TextLoader(source, encoding="utf-8").load()
        for doc in docs:
            doc.metadata["doc_type"] = source_type

    elif source_type == "url":
        docs = WebBaseLoader(web_paths=[source]).load()
        for doc in docs:
            doc.metadata["doc_type"] = "url"
            doc.metadata["source"] = source

    else:
        raise ValueError(f"Unknown source_type: {source_type!r}")

    return docs


def get_chroma_client():
    """Return a chromadb.HttpClient connected to the remote ChromaDB server."""
    host = os.environ.get("CHROMA_HOST", "localhost")
    port = int(os.environ.get("CHROMA_PORT", "8000"))
    return chromadb.HttpClient(host=host, port=port)


def get_vectorstore(chroma_client, embedding_function) -> Chroma:
    """Return a LangChain Chroma vectorstore backed by the remote ChromaDB client."""
    return Chroma(
        client=chroma_client,
        collection_name="personal_kb",
        embedding_function=embedding_function,
    )


def get_embeddings() -> OllamaEmbeddings:
    """Return an OllamaEmbeddings instance using nomic-embed-text."""
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    return OllamaEmbeddings(model="nomic-embed-text", base_url=base_url)


def index_documents(
    vectorstore: Chroma,
    source: str,
    source_type: Optional[str] = None,
) -> int:
    """Detect source type, load, chunk, tag metadata, and add to the vectorstore."""
    if source_type is None:
        lower = source.lower()
        if lower.endswith(".pdf"):
            source_type = "pdf"
        elif lower.endswith(".md"):
            source_type = "md"
        elif lower.startswith("http"):
            source_type = "url"
        else:
            source_type = "txt"

    docs = load_documents(source, source_type)

    doc_name = source if source_type == "url" else os.path.basename(source)
    for doc in docs:
        doc.metadata["doc_name"] = doc_name

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    vectorstore.add_documents(chunks)
    return len(chunks)


def build_multi_query_chain(
    vectorstore: Chroma,
    filter_metadata: Optional[Dict] = None,
):
    """Build a RAG chain using MultiQueryRetriever for improved recall."""
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    query_llm = ChatOllama(
        model="llama3.2",
        temperature=0.3,
        num_ctx=2048,
        base_url=base_url,
    )
    answer_llm = ChatOllama(
        model="llama3.2",
        temperature=0.0,
        num_ctx=8192,
        base_url=base_url,
    )

    if filter_metadata:
        base_retriever = vectorstore.as_retriever(
            search_kwargs={"k": 4, "filter": filter_metadata}
        )
    else:
        base_retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    multi_retriever = MultiQueryRetriever.from_llm(
        retriever=base_retriever,
        llm=query_llm,
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a helpful personal knowledge base assistant. "
            "Answer the user's question using ONLY the provided context. "
            "When possible, cite the document name (doc_name) and page number. "
            "If the answer is not in the context, say so clearly — do not fabricate.\n\n"
            "Context:\n{context}",
        ),
        ("human", "{input}"),
    ])

    combine_docs_chain = create_stuff_documents_chain(answer_llm, prompt)
    rag_chain = create_retrieval_chain(multi_retriever, combine_docs_chain)
    return rag_chain


def list_indexed_documents(vectorstore: Chroma) -> List[str]:
    """Return a sorted list of unique doc_name values in the vectorstore."""
    result = vectorstore.get(include=["metadatas"])
    metadatas = result.get("metadatas", [])
    unique_names = set()
    for meta in metadatas:
        if meta and meta.get("doc_name"):
            unique_names.add(meta["doc_name"])
    return sorted(unique_names)


def delete_document(vectorstore: Chroma, doc_name: str) -> int:
    """Delete all chunks belonging to a document from the vectorstore."""
    collection = vectorstore._collection
    results = collection.get(where={"doc_name": doc_name})
    ids_to_delete = results["ids"]
    if not ids_to_delete:
        return 0
    collection.delete(ids=ids_to_delete)
    return len(ids_to_delete)
