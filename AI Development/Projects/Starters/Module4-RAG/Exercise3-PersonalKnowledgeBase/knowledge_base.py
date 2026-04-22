"""
knowledge_base.py — Document loading, indexing, and retrieval for Exercise 3.

Implement all functions marked with TODO. Do not change any function signatures.
"""

import os
from typing import List, Optional, Dict, Any

from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# TODO 1 — Implement load_documents()
# ---------------------------------------------------------------------------
def load_documents(source: str, source_type: str) -> List[Document]:
    """
    Load documents from a file path or URL.

    Args:
        source:      File path (for pdf/txt/md) or URL string (for url).
        source_type: One of "pdf", "txt", "md", "url".

    Returns:
        List of Document objects with page_content and metadata.

    Steps:
        For "pdf":
            Import PyPDFLoader from langchain_community.document_loaders.
            docs = PyPDFLoader(source).load()
            Add doc_type="pdf" to each doc.metadata.

        For "txt" and "md":
            Import TextLoader from langchain_community.document_loaders.
            docs = TextLoader(source, encoding="utf-8").load()
            Add doc_type=source_type to each doc.metadata.

        For "url":
            Import WebBaseLoader from langchain_community.document_loaders.
            docs = WebBaseLoader(web_paths=[source]).load()
            Add doc_type="url" and source=source to each doc.metadata.

        Return docs in all cases.
    """
    # TODO: implement this function
    raise NotImplementedError("load_documents() is not yet implemented.")


# ---------------------------------------------------------------------------
# TODO 2 — Implement get_chroma_client()
# ---------------------------------------------------------------------------
def get_chroma_client():
    """
    Return a chromadb.HttpClient connected to the remote ChromaDB server.

    Read host from env var CHROMA_HOST (default "localhost").
    Read port from env var CHROMA_PORT (default 8000).

    Steps:
        import chromadb
        host = os.environ.get("CHROMA_HOST", "localhost")
        port = int(os.environ.get("CHROMA_PORT", "8000"))
        return chromadb.HttpClient(host=host, port=port)
    """
    # TODO: implement this function
    raise NotImplementedError("get_chroma_client() is not yet implemented.")


# ---------------------------------------------------------------------------
# TODO 3 — Implement get_vectorstore()
# ---------------------------------------------------------------------------
def get_vectorstore(chroma_client, embedding_function):
    """
    Return a LangChain Chroma vectorstore backed by the remote ChromaDB client.

    Args:
        chroma_client:      A chromadb.HttpClient instance.
        embedding_function: A LangChain embeddings object (OllamaEmbeddings).

    Returns:
        A langchain_chroma.Chroma vectorstore instance.

    Steps:
        from langchain_chroma import Chroma
        return Chroma(
            client=chroma_client,
            collection_name="personal_kb",
            embedding_function=embedding_function,
        )
    """
    # TODO: implement this function
    raise NotImplementedError("get_vectorstore() is not yet implemented.")


# ---------------------------------------------------------------------------
# TODO 4 — Implement get_embeddings()
# ---------------------------------------------------------------------------
def get_embeddings():
    """
    Return an OllamaEmbeddings instance using nomic-embed-text.

    Read OLLAMA_BASE_URL from environment (default "http://localhost:11434").

    Steps:
        from langchain_ollama import OllamaEmbeddings
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        return OllamaEmbeddings(model="nomic-embed-text", base_url=base_url)
    """
    # TODO: implement this function
    raise NotImplementedError("get_embeddings() is not yet implemented.")


# ---------------------------------------------------------------------------
# TODO 5 — Implement index_documents()
# ---------------------------------------------------------------------------
def index_documents(vectorstore, source: str, source_type: Optional[str] = None) -> int:
    """
    Detect source type, load, chunk, tag metadata, and add to the vectorstore.

    Args:
        vectorstore:  A Chroma vectorstore instance.
        source:       File path or URL string.
        source_type:  Override auto-detection if provided.

    Returns:
        Number of chunks added to the vectorstore.

    Steps:
        1. If source_type is None, auto-detect:
               if source.lower().endswith(".pdf")       → "pdf"
               elif source.lower().endswith(".md")      → "md"
               elif source.lower().startswith("http")   → "url"
               else                                      → "txt"

        2. Call load_documents(source, source_type) → raw docs.

        3. Set doc_name on each doc's metadata:
               - For files: os.path.basename(source)
               - For URLs:  source (the full URL string)

        4. Import RecursiveCharacterTextSplitter from langchain_text_splitters.
           Split with chunk_size=500, chunk_overlap=50.

        5. Call vectorstore.add_documents(chunks).

        6. Return len(chunks).
    """
    # TODO: implement this function
    raise NotImplementedError("index_documents() is not yet implemented.")


# ---------------------------------------------------------------------------
# TODO 6 — Implement build_multi_query_chain()
# ---------------------------------------------------------------------------
def build_multi_query_chain(vectorstore, filter_metadata: Optional[Dict] = None):
    """
    Build a RAG chain using MultiQueryRetriever for improved recall.

    Args:
        vectorstore:     A Chroma vectorstore instance.
        filter_metadata: Optional dict for metadata filtering, e.g. {"doc_name": "foo.pdf"}.

    Returns:
        A LangChain retrieval chain.

    Steps:
        1. Import ChatOllama from langchain_ollama.
           Read OLLAMA_BASE_URL from env.
           query_llm  = ChatOllama(model="llama3.2", temperature=0.3, num_ctx=2048, base_url=...)
           answer_llm = ChatOllama(model="llama3.2", temperature=0.0, num_ctx=8192, base_url=...)

        2. Build base_retriever:
               if filter_metadata:
                   vectorstore.as_retriever(
                       search_kwargs={"k": 4, "filter": filter_metadata}
                   )
               else:
                   vectorstore.as_retriever(search_kwargs={"k": 4})

        3. Import MultiQueryRetriever from langchain.retrievers.multi_query.
           multi_retriever = MultiQueryRetriever.from_llm(
               retriever=base_retriever,
               llm=query_llm,
           )

        4. Import ChatPromptTemplate from langchain_core.prompts.
           Write a system prompt that instructs the model to answer from context only,
           mentions citing doc_name and page when available, and uses {context}/{input}.

        5. Build and return a create_retrieval_chain chain using answer_llm.
    """
    # TODO: implement this function
    raise NotImplementedError("build_multi_query_chain() is not yet implemented.")


# ---------------------------------------------------------------------------
# TODO 7 — Implement list_indexed_documents()
# ---------------------------------------------------------------------------
def list_indexed_documents(vectorstore) -> List[str]:
    """
    Return a sorted list of unique doc_name values in the vectorstore.

    Steps:
        1. Call vectorstore.get(include=["metadatas"]).
           This returns a dict; extract the "metadatas" list.
        2. Collect unique values of metadata.get("doc_name") for each metadata dict.
           Skip entries where doc_name is None.
        3. Return sorted(unique_names).
    """
    # TODO: implement this function
    raise NotImplementedError("list_indexed_documents() is not yet implemented.")


# ---------------------------------------------------------------------------
# TODO 8 — Implement delete_document()
# ---------------------------------------------------------------------------
def delete_document(vectorstore, doc_name: str) -> int:
    """
    Delete all chunks belonging to a document from the vectorstore.

    Args:
        vectorstore: A Chroma vectorstore instance.
        doc_name:    The doc_name metadata value to delete.

    Returns:
        Number of chunks deleted.

    Steps:
        1. Get the internal Chroma collection:
               collection = vectorstore._collection
        2. Query for IDs matching doc_name:
               results = collection.get(where={"doc_name": doc_name})
               ids_to_delete = results["ids"]
        3. If ids_to_delete is empty, return 0.
        4. Call collection.delete(ids=ids_to_delete).
        5. Return len(ids_to_delete).
    """
    # TODO: implement this function
    raise NotImplementedError("delete_document() is not yet implemented.")
