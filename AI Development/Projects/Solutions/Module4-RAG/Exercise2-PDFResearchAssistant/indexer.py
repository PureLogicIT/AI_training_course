"""
indexer.py — PDF loading, chunking, and FAISS index construction (SOLUTION).
"""

from typing import List, Tuple

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


def build_index(
    pdf_paths: List[str],
    chunk_size: int,
    chunk_overlap: int,
):
    """
    Load one or more PDFs, chunk them, embed with sentence-transformers, and
    return a FAISS vectorstore plus the flat chunk list.
    """
    all_docs: List[Document] = []

    for path in pdf_paths:
        loader = PyPDFLoader(path)
        pages = loader.load()
        all_docs.extend(pages)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(all_docs)

    # Downloads ~80 MB on first run; cached in ~/.cache/huggingface/ thereafter
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    vectorstore = FAISS.from_documents(documents=chunks, embedding=embeddings)

    return vectorstore, chunks
