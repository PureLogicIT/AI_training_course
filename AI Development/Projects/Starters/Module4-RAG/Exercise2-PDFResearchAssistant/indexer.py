"""
indexer.py — PDF loading, chunking, and FAISS index construction.

Implement build_index() below. Do not change the function signature.
"""

from typing import List, Tuple


# ---------------------------------------------------------------------------
# TODO 1 — Implement build_index()
# ---------------------------------------------------------------------------
def build_index(pdf_paths: List[str], chunk_size: int, chunk_overlap: int):
    """
    Load one or more PDFs, chunk them, embed with sentence-transformers, and
    return a FAISS vectorstore.

    Args:
        pdf_paths:     List of absolute file paths to PDF files.
        chunk_size:    Target character count per chunk.
        chunk_overlap: Character overlap between adjacent chunks.

    Returns:
        Tuple (vectorstore, chunks) where:
            - vectorstore is a FAISS instance ready for similarity search.
            - chunks      is the flat list of all Document objects that were indexed.

    Steps:
        1. Import PyPDFLoader from langchain_community.document_loaders.
           Loop over pdf_paths. For each, call PyPDFLoader(path).load() and extend
           a master list `all_docs`. Each page is one Document; metadata contains
           "source" (full path) and "page" (0-indexed int).

        2. Import RecursiveCharacterTextSplitter from langchain_text_splitters.
           Split all_docs with the supplied chunk_size and chunk_overlap.
           Store the result in `chunks`.

        3. Import HuggingFaceEmbeddings from langchain_huggingface.
           Create HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2").
           (The model downloads ~80 MB on first run and is cached locally.)

        4. Import FAISS from langchain_community.vectorstores.
           Call FAISS.from_documents(chunks, embeddings).
           Store in `vectorstore`.

        5. Return (vectorstore, chunks).
    """
    # TODO: implement this function
    raise NotImplementedError("build_index() is not yet implemented.")
