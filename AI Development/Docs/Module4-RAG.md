# Module 4: RAG — Retrieval-Augmented Generation
> Subject: AI Development | Difficulty: Intermediate | Estimated Time: 360 minutes

## Objective

After completing this module, you will be able to explain the RAG pipeline (index → retrieve → augment → generate) and articulate why it is often preferable to fine-tuning or prompt stuffing for adding private knowledge to an LLM. You will generate embeddings locally using `OllamaEmbeddings` (`nomic-embed-text`, `mxbai-embed-large`) and `HuggingFaceEmbeddings` from the `sentence-transformers` library, with no cloud API calls. You will build and query persistent vector stores using Chroma and FAISS, load and chunk documents with `TextLoader`, `PyPDFLoader`, and `DirectoryLoader`, and choose chunking parameters based on retrieval quality requirements. You will assemble end-to-end RAG chains using LangChain's `create_retrieval_chain`, `create_stuff_documents_chain`, and custom LCEL patterns, and apply advanced retrieval techniques including `MultiQueryRetriever` and `ContextualCompressionRetriever`. By the end of this module you will have three fully working local RAG systems you built yourself.

## Prerequisites

- Completed **Module 0: Setup & Local AI Stack** — Ollama is installed, running, and at least one model is pulled
- Completed **Module 1: Working with Local Models** — familiar with `ollama.chat()`, streaming, and inference parameters
- Completed **Module 2: Hugging Face & Local Models** — comfortable with the `transformers` ecosystem and the Hugging Face Hub
- Completed **Module 3: LangChain Fundamentals** — comfortable with `ChatOllama`, LCEL, `ChatPromptTemplate`, `StrOutputParser`, `RecursiveCharacterTextSplitter`, and `Document` objects
- Python 3.10 or later with an active virtual environment
- The following models pulled via Ollama (run these before starting):
  ```bash
  ollama pull llama3.2
  ollama pull nomic-embed-text
  ```
- At least 8 GB of RAM and 4 GB of free disk space for index storage
- Familiarity with Python list comprehensions and basic file I/O

---

## Key Concepts

### 1. What RAG Is and Why It Matters

Every LLM has a knowledge cutoff — a date after which it has seen no training data. It also has no access to your private files: your company wiki, your codebase, your customer documentation, or any other data that was not in its training corpus. When you ask a question about something the model was not trained on, it either refuses to answer or, more dangerously, produces a plausible-sounding but fabricated response.

**Retrieval-Augmented Generation (RAG)** solves this by treating the LLM as a reasoning engine rather than a knowledge store. Instead of relying on the model's internal weights to contain your information, you maintain a separate, searchable index of your documents. At query time, you find the documents most relevant to the question, paste their text into the prompt as context, and ask the model to answer using that context. The model's job is now to read and reason over supplied text — something it does extremely well — rather than to recall facts from training.

The core RAG pipeline has four stages:

```
User Question
      │
      ▼
┌─────────────┐
│   RETRIEVE  │  Search the vector store for the K most
│             │  relevant document chunks
└──────┬──────┘
       │ retrieved chunks
       ▼
┌─────────────┐
│   AUGMENT   │  Insert the chunks into a prompt template
│             │  as context alongside the user question
└──────┬──────┘
       │ augmented prompt
       ▼
┌─────────────┐
│  GENERATE   │  Send the augmented prompt to the LLM;
│             │  model produces a grounded answer
└──────┬──────┘
       │ answer
       ▼
  Final Response
```

The **index** stage happens separately, ahead of time: documents are loaded, split into chunks, converted into embedding vectors, and stored in a vector database. At query time only the last three stages run.

#### RAG vs Fine-Tuning vs Prompt Stuffing

These three approaches all add information to an LLM, but they differ in cost, latency, and suitability:

| Approach | How it works | Best when | Weakness |
|---|---|---|---|
| **Prompt stuffing** | Paste all documents directly into the system prompt | Corpus is small (< a few thousand tokens) and static | Context window limits; every call sends the full corpus; expensive |
| **RAG** | Index documents; retrieve only the relevant chunks at query time | Corpus is large (MBs to GBs) or frequently updated | Retrieval quality limits answer quality; extra infrastructure |
| **Fine-tuning** | Train the model weights on domain data | Teaching the model a new style or skill, not new facts | Expensive; does not update incrementally; can cause catastrophic forgetting |

For most private-knowledge use cases — documentation Q&A, codebase search, customer support — RAG is the right default. Fine-tuning is rarely needed unless you need to change how the model writes, not what it knows.

---

### 2. Embeddings for Local RAG

An **embedding** is a fixed-length vector of floating-point numbers that represents the semantic meaning of a piece of text. Two pieces of text that mean similar things produce vectors that are close together in high-dimensional space, regardless of whether they share the same words. This is what enables semantic search: you embed the query, embed each document chunk, and find the chunks closest to the query in vector space.

The distance measure used for this comparison is **cosine similarity** — the cosine of the angle between two vectors. A cosine similarity of 1.0 means the vectors point in the exact same direction (semantically identical); 0.0 means they are orthogonal (completely unrelated); -1.0 means they are opposite. In practice you will see scores in the 0.5–0.95 range for related texts.

```
embedding("Paris is the capital of France")  →  [0.12, -0.34, 0.91, ...]
embedding("France's capital city is Paris")  →  [0.11, -0.33, 0.90, ...]
  → cosine similarity ≈ 0.99  (nearly identical meaning)

embedding("The cat sat on the mat")          →  [0.72, 0.08, -0.21, ...]
  → cosine similarity ≈ 0.18  (unrelated)
```

#### Local Embedding Models

You have two routes for local embeddings — both work entirely offline after the initial model download.

**Option A: OllamaEmbeddings (via Ollama)**

This is the simplest path. Pull an embedding model with `ollama pull` and use it through LangChain's `OllamaEmbeddings` class. It hits your local Ollama server, so the same server that runs your LLM also runs your embeddings.

```python
from langchain_ollama import OllamaEmbeddings

# nomic-embed-text: 768 dimensions, fast, good general-purpose retrieval
embeddings = OllamaEmbeddings(model="nomic-embed-text")

# mxbai-embed-large: 1024 dimensions, stronger semantic understanding
# embeddings = OllamaEmbeddings(model="mxbai-embed-large")

# Embed a single query (returns a list of floats)
query_vector = embeddings.embed_query("What is retrieval-augmented generation?")
print(f"Embedding dimensions: {len(query_vector)}")  # 768 for nomic-embed-text

# Embed multiple documents at once (returns a list of lists)
doc_vectors = embeddings.embed_documents([
    "RAG combines retrieval with language model generation.",
    "Fine-tuning modifies model weights on domain data.",
    "Prompt stuffing inserts the full corpus into the context.",
])
print(f"Number of document vectors: {len(doc_vectors)}")  # 3
```

Pull the embedding models:

```bash
# 274 MB — fast, good quality, the default for this module
ollama pull nomic-embed-text

# 669 MB — stronger semantic understanding, slower
ollama pull mxbai-embed-large
```

**Option B: HuggingFaceEmbeddings (via sentence-transformers)**

For a completely Ollama-free setup — or when you need a specific `sentence-transformers` model — use `HuggingFaceEmbeddings` from the `langchain-huggingface` package. The model weights download from Hugging Face Hub on first use and are cached locally for offline use thereafter.

```bash
pip install langchain-huggingface sentence-transformers
```

```python
from langchain_huggingface import HuggingFaceEmbeddings

# all-MiniLM-L6-v2: 384 dimensions, very small (80 MB), runs on CPU
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# all-mpnet-base-v2: 768 dimensions, better quality, ~420 MB
# embeddings = HuggingFaceEmbeddings(model_name="all-mpnet-base-v2")

query_vector = embeddings.embed_query("What is cosine similarity?")
print(f"Embedding dimensions: {len(query_vector)}")  # 384 for all-MiniLM-L6-v2
```

#### Dimensions and Their Practical Impact

| Model | Dimensions | Storage per chunk | Quality | Speed (CPU) |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | ~1.5 KB | Good | Very fast |
| `nomic-embed-text` | 768 | ~3 KB | Very good | Fast |
| `all-mpnet-base-v2` | 768 | ~3 KB | Very good | Moderate |
| `mxbai-embed-large` | 1024 | ~4 KB | Excellent | Slower |

For a corpus of 10,000 chunks at 768 dimensions, the raw vector data is approximately 30 MB — entirely manageable on any development machine. Dimension count matters more for query latency at scale than for local development.

> **Critical constraint:** You must use the same embedding model for indexing and querying. If you index with `nomic-embed-text` (768d), you must query with `nomic-embed-text`. Mixing models produces garbage retrieval because the vector spaces are incompatible.

---

### 3. Vector Stores

A vector store holds your embedded document chunks and provides similarity search: given a query vector, return the K most similar document vectors and their associated text. LangChain wraps multiple vector store backends behind a common interface, so you can swap between them by changing the import and constructor.

#### Chroma — Local Persistent Store

Chroma is a local-first vector database designed for development and small production deployments. Data is persisted to disk automatically and loads back on startup — no external service required.

```bash
pip install langchain-chroma chromadb
```

**Creating a Chroma store from documents:**

```python
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

embeddings = OllamaEmbeddings(model="nomic-embed-text")

# from_documents: embed a list of Document objects and store them
vectorstore = Chroma.from_documents(
    documents=chunks,               # list of Document objects
    embedding=embeddings,
    collection_name="my_docs",
    persist_directory="./chroma_db",  # omit for in-memory only
)
```

**Loading an existing Chroma store from disk:**

```python
vectorstore = Chroma(
    collection_name="my_docs",
    embedding_function=embeddings,
    persist_directory="./chroma_db",
)
```

**Querying:**

```python
# similarity_search — returns a list of Document objects
results = vectorstore.similarity_search("What is RAG?", k=4)
for doc in results:
    print(doc.page_content[:200])
    print(doc.metadata)

# similarity_search_with_score — returns (Document, score) tuples
# Lower score = more similar in Chroma's default L2 distance metric
results_with_scores = vectorstore.similarity_search_with_score("What is RAG?", k=4)
for doc, score in results_with_scores:
    print(f"Score: {score:.4f} | {doc.page_content[:100]}")
```

**Filtering by metadata:**

```python
# Only return chunks from a specific source file
results = vectorstore.similarity_search(
    "machine learning",
    k=3,
    filter={"source": "docs/intro.txt"},
)
```

#### FAISS — In-Memory with Optional Disk Persistence

FAISS (Facebook AI Similarity Search) is an optimized library for similarity search in dense vectors. LangChain's FAISS integration stores everything in memory during a session, with explicit save/load for persistence. It is faster than Chroma for large collections because it uses optimized C++ index structures.

```bash
pip install faiss-cpu langchain-community
# For GPU acceleration (optional): pip install faiss-gpu
```

**Creating a FAISS store from documents:**

```python
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings

embeddings = OllamaEmbeddings(model="nomic-embed-text")

vectorstore = FAISS.from_documents(
    documents=chunks,
    embedding=embeddings,
)

# Save to disk so you do not re-embed on every run
vectorstore.save_local("./faiss_index")
```

**Loading a saved FAISS index:**

```python
vectorstore = FAISS.load_local(
    "./faiss_index",
    embeddings,
    allow_dangerous_deserialization=True,  # required — FAISS uses pickle
)
```

**Querying:**

```python
results = vectorstore.similarity_search("What is a vector store?", k=3)
for doc in results:
    print(doc.page_content[:200])
```

#### Choosing Between Chroma and FAISS

| | Chroma | FAISS |
|---|---|---|
| **Persistence** | Automatic to disk via `persist_directory` | Manual: `save_local()` / `load_local()` |
| **In-memory option** | Yes (omit `persist_directory`) | Always in-memory; disk is a serialized snapshot |
| **Setup complexity** | `pip install langchain-chroma chromadb` | `pip install faiss-cpu langchain-community` |
| **Metadata filtering** | Native, flexible filter syntax | Supported via MongoDB-style operators |
| **Speed at scale** | Good | Excellent — optimized C++ backend |
| **Best for** | Development, persistent local Q&A apps | High-throughput apps, large corpora |

For the exercises in this module, either works. Chroma is the default because its automatic persistence eliminates a common error class (forgetting to save the index before the process exits).

---

### 4. Document Processing for RAG

Before documents reach the vector store, they pass through two stages: loading (converting files to LangChain `Document` objects) and chunking (splitting large documents into retrieval-sized pieces). Both were introduced in Module 3; this section focuses on the RAG-specific considerations.

#### Document Loaders

Each loader returns a list of `Document` objects, each with `page_content` (the text) and `metadata` (source, page, etc.). Metadata is preserved through the entire pipeline and appears in retrieval results — use it for filtering and for citing sources in answers.

```python
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    DirectoryLoader,
    WebBaseLoader,
)

# Single text file
loader = TextLoader("./docs/readme.txt", encoding="utf-8")
docs = loader.load()  # [Document(page_content="...", metadata={"source": "..."})]

# PDF — one Document per page, metadata includes page number
loader = PyPDFLoader("./docs/manual.pdf")
docs = loader.load()
# docs[0].metadata == {"source": "./docs/manual.pdf", "page": 0}

# All .txt and .md files in a directory tree
loader = DirectoryLoader(
    "./knowledge_base",
    glob="**/*.{txt,md}",
    loader_cls=TextLoader,
    show_progress=True,
)
docs = loader.load()

# Web page (downloads at load time — not offline)
loader = WebBaseLoader(web_paths=["https://example.com/docs"])
docs = loader.load()
```

> Install `pypdf` for PDF support: `pip install pypdf`

#### Chunking Strategies

Splitting documents into smaller chunks serves two purposes: it ensures individual chunks fit within the embedding model's context window, and it improves retrieval precision. A 3000-word chapter is rarely what you want to retrieve — a 150-word paragraph on the specific topic is far more relevant to a narrow query.

**`RecursiveCharacterTextSplitter` — the recommended default:**

This splitter tries separators in order: `\n\n` (paragraph), `\n` (line), `. ` (sentence), ` ` (word), then characters. It only falls back to a finer separator when the chunk would exceed `chunk_size`. This produces semantically coherent chunks.

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,       # characters per chunk (not tokens)
    chunk_overlap=50,     # characters shared between adjacent chunks
    length_function=len,
    is_separator_regex=False,
)

chunks = splitter.split_documents(docs)
print(f"Split {len(docs)} documents into {len(chunks)} chunks")
print(f"Sample chunk: {chunks[0].page_content[:200]}")
print(f"Sample metadata: {chunks[0].metadata}")
```

**Practical chunking guidelines:**

| Document type | Recommended chunk_size | Recommended chunk_overlap | Rationale |
|---|---|---|---|
| Short Q&A / FAQs | 200–300 chars | 20–30 chars | Answers are already compact |
| Prose documentation | 400–600 chars | 50–75 chars | One to two paragraphs per chunk |
| Technical manuals | 600–800 chars | 75–100 chars | Longer code examples need room |
| Legal / academic text | 300–500 chars | 50–75 chars | Dense information; tight chunks aid precision |

**Adding custom metadata to chunks:**

```python
from langchain_core.documents import Document

# Add a custom field to existing metadata after loading
for doc in docs:
    doc.metadata["indexed_at"] = "2026-04-16"
    doc.metadata["category"] = "technical"

# Or filter by source during retrieval
results = vectorstore.similarity_search(
    "deployment steps",
    k=4,
    filter={"category": "technical"},
)
```

Overlap is critical for queries that reference information near a chunk boundary. A `chunk_overlap` of 10% of `chunk_size` is the minimum; 15% is safer for prose.

---

### 5. Building a RAG Chain with LangChain

With documents chunked, embedded, and stored, the retrieval and generation components can be assembled into a chain. LangChain provides two helper functions that cover the common case, plus the full flexibility of LCEL for custom pipelines.

#### The Retriever Interface

Any LangChain vector store can be converted to a retriever — an object that takes a string query and returns a list of `Document` objects — with `.as_retriever()`:

```python
# Basic similarity retriever — fetch 4 most similar chunks
retriever = vectorstore.as_retriever(
    search_type="similarity",      # default
    search_kwargs={"k": 4},
)

# MMR (Maximal Marginal Relevance) — balances relevance with diversity
# Avoids returning 4 nearly identical chunks when your docs have duplicates
retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 4, "fetch_k": 20, "lambda_mult": 0.5},
)

# Direct use
docs = retriever.invoke("What is the difference between RAG and fine-tuning?")
print(f"Retrieved {len(docs)} chunks")
```

`fetch_k` is the number of candidates fetched before MMR re-ranking; `lambda_mult` controls the diversity/relevance tradeoff (0.0 = maximum diversity, 1.0 = pure similarity).

#### `create_stuff_documents_chain` + `create_retrieval_chain`

The "stuff" pattern — shoving all retrieved chunks into the prompt as a single block — is the correct default for most RAG tasks with up to a dozen retrieved chunks.

```python
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

llm = ChatOllama(model="llama3.2", temperature=0.0, num_ctx=8192)

# Prompt template — {context} receives the formatted retrieved chunks
# {input} receives the user's question
rag_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a helpful assistant that answers questions based only on the "
        "provided context. If the answer is not in the context, say so clearly. "
        "Do not make up information.\n\n"
        "Context:\n{context}",
    ),
    ("human", "{input}"),
])

# Step 1: chain that takes (context docs + input) → answer string
combine_docs_chain = create_stuff_documents_chain(llm, rag_prompt)

# Step 2: wrap with retrieval — takes {input} → retrieves docs → feeds combine_docs_chain
rag_chain = create_retrieval_chain(retriever, combine_docs_chain)

# Invoke — returns a dict with "input", "context", and "answer" keys
result = rag_chain.invoke({"input": "What is the return value of similarity_search?"})

print(result["answer"])
# The retrieved chunks that produced the answer:
for doc in result["context"]:
    print(f"  Source: {doc.metadata.get('source', 'unknown')}")
    print(f"  Content: {doc.page_content[:100]}")
```

#### Custom LCEL RAG Chain

For full control over the prompt format, document formatting, or streaming behaviour, build the chain manually with LCEL:

```python
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama


def format_docs(docs: list) -> str:
    """Concatenate retrieved chunks into a single context string."""
    formatted = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        formatted.append(f"[Chunk {i} | Source: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(formatted)


llm = ChatOllama(model="llama3.2", temperature=0.0, num_ctx=8192)

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Answer the question using only the context below. "
        "If the context does not contain the answer, say 'I don't know based on the provided documents.'\n\n"
        "Context:\n{context}",
    ),
    ("human", "{question}"),
])

# Build the LCEL chain
rag_chain = (
    {
        "context": retriever | RunnableLambda(format_docs),
        "question": RunnablePassthrough(),
    }
    | prompt
    | llm
    | StrOutputParser()
)

# Streaming works with the LCEL chain
print("Answer: ", end="", flush=True)
for chunk in rag_chain.stream("Explain the difference between Chroma and FAISS."):
    print(chunk, end="", flush=True)
print()
```

The key pattern is the dict step `{"context": retriever | format_docs, "question": RunnablePassthrough()}`. The retriever is invoked with the user's question (passed through by `RunnablePassthrough`), its output is formatted by `format_docs`, and both values are injected into the prompt template.

---

### 6. RAG Quality and Evaluation

A RAG system can fail in several distinct ways, and knowing which layer is failing determines how to fix it.

#### Common Failure Modes

**Retrieval failure:** The correct chunks are not in the top K results. The model receives no relevant context and hallucinates or says "I don't know." Diagnosis: inspect `result["context"]` — are the returned chunks relevant to the question?

**Context overflow:** Too many chunks retrieved (large K) combined with large chunks fills the model's context window. The model starts ignoring context, producing lower-quality answers. Diagnosis: count tokens in your formatted context string.

**Hallucination despite retrieval:** The model receives relevant chunks but ignores them and generates an answer from its training data instead. More common with higher temperatures and with models smaller than 7B. Fix: lower temperature to 0.0, add explicit grounding instructions to the system prompt.

**Chunk boundary truncation:** A fact is split across two chunks, and only one chunk is retrieved. The answer is incomplete or misleading. Fix: increase `chunk_overlap`.

**Wrong granularity:** Chunks are too large — the retrieved chunk contains the answer but also a lot of noise, diluting relevance. Or chunks are too small — each chunk lacks enough context for the model to construct an answer. Fix: experiment with `chunk_size` (see Section 4 guidelines).

#### Retrieval Tuning

```python
# Increasing k retrieves more candidates — better recall, but more context noise
retriever = vectorstore.as_retriever(search_kwargs={"k": 8})

# Score threshold filtering — only return chunks above a similarity threshold
# Note: this is Chroma-specific; FAISS requires manual filtering
retriever = vectorstore.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"score_threshold": 0.7},
)

# MMR for diverse results — reduces redundancy when your corpus has duplicated content
retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 4, "fetch_k": 15, "lambda_mult": 0.6},
)
```

#### Simple Manual Evaluation

Before adding automated evaluation, manually inspect the retrieval output for 10–20 representative queries:

```python
def evaluate_retrieval(retriever, questions: list[str]) -> None:
    """Print retrieved chunks for each question for manual inspection."""
    for question in questions:
        print(f"\nQuestion: {question}")
        docs = retriever.invoke(question)
        print(f"Retrieved {len(docs)} chunks:")
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "unknown")
            print(f"  [{i}] {source}: {doc.page_content[:120].strip()}")

test_questions = [
    "What is the difference between Chroma and FAISS?",
    "How do I set chunk overlap?",
    "What embedding model should I use for production?",
]

evaluate_retrieval(retriever, test_questions)
```

Look for: Are the top 1–2 chunks the ones you would have manually selected? If not, try adjusting `k`, `chunk_size`, or the embedding model.

---

### 7. Advanced Retrieval Patterns

The basic similarity retriever works well for precise, unambiguous questions. For ambiguous queries, noisy corpora, or large documents, these advanced patterns significantly improve recall and answer quality.

#### MultiQueryRetriever

A single query may miss relevant chunks because the exact wording does not match the embedding space of those chunks. `MultiQueryRetriever` uses the LLM to generate multiple phrasings of the original question, runs all of them through the retriever, and unions the results (deduplicated by document content).

```python
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain_ollama import ChatOllama

llm = ChatOllama(model="llama3.2", temperature=0.3, num_ctx=4096)

multi_retriever = MultiQueryRetriever.from_llm(
    retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
    llm=llm,
)

# Enable logging to see the generated alternative queries
import logging
logging.basicConfig()
logging.getLogger("langchain.retrievers.multi_query").setLevel(logging.INFO)

docs = multi_retriever.invoke("How do I make my RAG system more accurate?")
print(f"Total unique chunks retrieved: {len(docs)}")
```

The log output will show the three alternative queries the LLM generated. For example, the question "How do I make my RAG system more accurate?" might generate:
- "What are techniques to improve RAG retrieval quality?"
- "How can I tune chunk size for better RAG results?"
- "What embedding models work best for retrieval-augmented generation?"

Each query is sent to the base retriever, and the results are merged and deduplicated. Expect to retrieve more chunks overall — adjust your prompt accordingly.

#### ContextualCompressionRetriever

After retrieval, each chunk may contain sections irrelevant to the query. `ContextualCompressionRetriever` wraps a base retriever and passes each retrieved chunk through a compressor — an LLM that extracts only the sentences relevant to the query — before returning it.

```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain_ollama import ChatOllama

llm = ChatOllama(model="llama3.2", temperature=0.0, num_ctx=4096)

compressor = LLMChainExtractor.from_llm(llm)

compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=vectorstore.as_retriever(search_kwargs={"k": 4}),
)

compressed_docs = compression_retriever.invoke("What is the MMR search type used for?")
for doc in compressed_docs:
    print(f"Compressed chunk ({len(doc.page_content)} chars): {doc.page_content}")
```

The tradeoff: compression adds an extra LLM call per retrieved chunk. With 4 chunks, that is 4 extra inference calls. Use this pattern when your chunks are large and noisy, not as a default.

#### Parent Document Retriever (Pattern Overview)

Small chunks retrieve better (more precise matching) but provide less context to the LLM. The parent document retriever pattern addresses this: index small chunks (e.g., 200 characters) for retrieval, but when a small chunk matches, return its larger parent chunk (e.g., 1500 characters) to the LLM.

LangChain implements this with `ParentDocumentRetriever` from `langchain.retrievers`. It requires an in-memory or database-backed docstore to hold the parent documents. The `langchain-community` package provides `InMemoryStore` for development:

```python
from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import InMemoryStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

# Small chunks for retrieval precision
child_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)

# Larger chunks for model context quality
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

embeddings = OllamaEmbeddings(model="nomic-embed-text")
vectorstore = Chroma(collection_name="children", embedding_function=embeddings)
docstore = InMemoryStore()

retriever = ParentDocumentRetriever(
    vectorstore=vectorstore,
    docstore=docstore,
    child_splitter=child_splitter,
    parent_splitter=parent_splitter,
)

retriever.add_documents(docs)  # indexes both child and parent chunks

# Returns parent-sized documents, not child chunks
results = retriever.invoke("What is MMR?")
print(f"Returned {len(results)} parent chunks")
print(f"Parent chunk size: ~{len(results[0].page_content)} chars")
```

#### Hybrid Search (Brief Note)

Hybrid search combines dense vector similarity (semantic) with sparse keyword search (BM25). This is valuable when users search by exact product names, error codes, or other terms that semantic search may miss. LangChain's `EnsembleRetriever` merges results from two retrievers with configurable weights. For local development, `BM25Retriever` from `langchain-community` provides keyword search without any external service. Full coverage of hybrid search is beyond this module's scope but is a natural next step after mastering the retrieval patterns above.

---

## Best Practices

1. **Always use the same embedding model for indexing and querying.** Vector spaces are model-specific. Indexing with `nomic-embed-text` and querying with `all-MiniLM-L6-v2` produces meaningless results with no error message — this is the single most common and hardest-to-debug RAG error.

2. **Set `num_ctx` high enough to hold your retrieved context on `ChatOllama`.** With `k=4` and `chunk_size=500`, retrieved context is roughly 2000 characters (~500 tokens). Add the prompt template, system message, and generated answer, and you need at least 4096 tokens of context window — set `num_ctx=8192` as a safe default for RAG chains.

3. **Start with `chunk_size=500`, `chunk_overlap=50`, and `k=4`, then tune.** These are conservative, effective defaults. Measure retrieval quality before changing anything — premature tuning without measurement is the leading cause of RAG regressions.

4. **Rebuild the vector store when you change the embedding model or chunk settings.** The index is not model-agnostic. If you change `chunk_size` from 500 to 300, or switch from `nomic-embed-text` to `mxbai-embed-large`, delete the old index directory and re-embed from scratch.

5. **Use `temperature=0.0` for grounded RAG answers.** RAG's value proposition is grounded, factual responses. High temperature reintroduces randomness and encourages the model to deviate from the provided context. Use `temperature=0.7` for creative tasks; use `0.0` for RAG.

6. **Inspect `result["context"]` before debugging generation quality.** When a RAG chain gives a wrong answer, determine first whether retrieval failed (wrong chunks returned) or generation failed (correct chunks, wrong answer). They require different fixes.

7. **Use MMR retrieval when your corpus contains duplicate or near-duplicate content.** Fetching 4 nearly identical chunks wastes context window tokens and produces worse answers than 4 diverse chunks. Set `search_type="mmr"` as a default when you cannot guarantee corpus uniqueness.

8. **Store metadata that enables filtering.** At index time, add `source`, `date`, `category`, or `version` fields to chunk metadata. Filtering at retrieval time is always faster and cheaper than post-retrieval filtering in the LLM prompt.

9. **Use `save_local()` immediately after building a FAISS index.** FAISS is in-memory — if your process exits without calling `save_local()`, all embedding work is lost. Call it immediately after `from_documents()` completes.

10. **Do not embed the same documents twice.** Check whether the index already exists before calling `from_documents()`. Re-embedding is slow and wastes compute — especially with Ollama where each embedding call goes through the local server.

---

## Use Cases

### Use Case 1: Internal Documentation Q&A

**Problem:** A software team has 200 markdown files of internal documentation — architecture decisions, runbooks, API references. New engineers spend days finding answers that are already documented. Searching by keyword misses documents that use different terminology.

**Concepts applied:** `DirectoryLoader` to load all markdown files, `RecursiveCharacterTextSplitter` to chunk them, `OllamaEmbeddings` with `nomic-embed-text` for embeddings, Chroma with `persist_directory` for persistent storage, `create_retrieval_chain` for the Q&A interface.

**Expected outcome:** A CLI or web tool where engineers ask natural-language questions and receive answers with source citations, grounded in the actual documentation content. Queries like "What is the retry policy for the payment service?" return the relevant runbook section even if the document says "exponential backoff" rather than "retry policy."

### Use Case 2: Local PDF Research Assistant

**Problem:** A researcher has a library of 50 academic PDFs (each 20–40 pages). They want to query across all documents — "Which papers discuss cosine similarity for retrieval?" — without manually reading each one or sending proprietary research to a cloud service.

**Concepts applied:** `PyPDFLoader` for each PDF, `RecursiveCharacterTextSplitter` at ~600 char chunks, `HuggingFaceEmbeddings` with `all-mpnet-base-v2` for fully offline embeddings (no Ollama dependency), FAISS with `save_local()` for fast in-memory retrieval with disk persistence, LCEL RAG chain for flexible answer formatting.

**Expected outcome:** A script that indexes all PDFs once (taking several minutes) and then answers cross-document queries in seconds, with answers citing the source PDF and page number from chunk metadata.

### Use Case 3: Codebase-Aware Assistant

**Problem:** A development team wants an assistant that can answer questions about their codebase: "Where is authentication handled?", "What does the `parse_response` function do?" Standard LLMs have no knowledge of internal code.

**Concepts applied:** `DirectoryLoader` with glob `**/*.py` and `TextLoader`, small chunks (`chunk_size=300`) to match function-level granularity, `MultiQueryRetriever` to handle ambiguous questions (e.g., "authentication" may appear as "auth", "login", "token validation"), metadata with filename and line range for precise citations.

**Expected outcome:** An assistant that returns relevant code snippets with filenames and supports natural-language queries about implementation details, reducing the time spent navigating an unfamiliar codebase.

### Use Case 4: Customer Support Knowledge Base

**Problem:** A support team has 1000 FAQ entries and product manual pages. Support agents spend time searching manually; customers using the chat widget get generic LLM responses rather than product-specific answers.

**Concepts applied:** `ContextualCompressionRetriever` to return only the relevant portion of each FAQ entry, metadata filtering by `product_version` to scope retrieval, `similarity_score_threshold` to return "I don't have information about that" when no chunk is sufficiently relevant, `RunnableWithMessageHistory` (from Module 3) to maintain multi-turn conversation context.

**Expected outcome:** A support chatbot grounded in actual product documentation, with measurably lower hallucination rates than a generic LLM, and automatic escalation when the retrieved context score falls below the threshold.

---

## Hands-On Examples

### Example 1: Local Document Q&A with Chroma and `nomic-embed-text`

This example indexes a folder of text and markdown files using Chroma and `nomic-embed-text`, then builds a Q&A system with `create_retrieval_chain`. The index persists to disk so it only needs to be built once.

**Setup:** Create a folder `./knowledge_base/` and add a few `.txt` or `.md` files with content you want to query. You can use documentation you have locally, notes, or even copy-paste text into text files. The example works with any plain text content.

**Step 1: Install dependencies**

```bash
pip install langchain langchain-community langchain-ollama langchain-chroma chromadb langchain-text-splitters
ollama pull nomic-embed-text
ollama pull llama3.2
```

**Step 2: Create the indexing and Q&A script**

```python
# example1_chroma_qa.py

"""
Local document Q&A system using Chroma + nomic-embed-text + llama3.2.
Run once to build the index, then query interactively.
No cloud API calls. All processing is local.

Usage:
    python example1_chroma_qa.py --index    # build the index from ./knowledge_base/
    python example1_chroma_qa.py            # query an existing index
"""

import argparse
import os
import sys

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate

# ── Configuration ─────────────────────────────────────────────────────────────
DOCS_DIR = "./knowledge_base"
CHROMA_DIR = "./chroma_db_example1"
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3.2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
RETRIEVAL_K = 4


def build_index() -> Chroma:
    """Load documents from DOCS_DIR, chunk them, embed, and persist to Chroma."""
    print(f"Loading documents from: {DOCS_DIR}")

    if not os.path.isdir(DOCS_DIR):
        print(f"ERROR: Directory '{DOCS_DIR}' does not exist.")
        print("Create it and add .txt or .md files before indexing.")
        sys.exit(1)

    loader = DirectoryLoader(
        DOCS_DIR,
        glob="**/*.{txt,md}",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True,
    )
    docs = loader.load()

    if not docs:
        print(f"ERROR: No .txt or .md files found in '{DOCS_DIR}'.")
        sys.exit(1)

    print(f"Loaded {len(docs)} documents")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(docs)
    print(f"Split into {len(chunks)} chunks (chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")

    print(f"Embedding with {EMBED_MODEL} — this may take a minute...")
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name="knowledge_base",
        persist_directory=CHROMA_DIR,
    )

    print(f"Index built and persisted to: {CHROMA_DIR}")
    print(f"Total vectors stored: {vectorstore._collection.count()}")
    return vectorstore


def load_index() -> Chroma:
    """Load an existing Chroma index from disk."""
    if not os.path.isdir(CHROMA_DIR):
        print(f"ERROR: No index found at '{CHROMA_DIR}'.")
        print("Run with --index first to build the index.")
        sys.exit(1)

    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    vectorstore = Chroma(
        collection_name="knowledge_base",
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )
    count = vectorstore._collection.count()
    print(f"Loaded existing index from {CHROMA_DIR} ({count} vectors)")
    return vectorstore


def build_rag_chain(vectorstore: Chroma):
    """Build a create_retrieval_chain RAG chain over the given vector store."""
    llm = ChatOllama(model=LLM_MODEL, temperature=0.0, num_ctx=8192, num_predict=512)

    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": RETRIEVAL_K, "fetch_k": 15},
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a helpful assistant that answers questions using only the "
            "provided context. If the answer is not in the context, say "
            "'I don't have information about that in the provided documents.' "
            "Do not make up facts.\n\nContext:\n{context}",
        ),
        ("human", "{input}"),
    ])

    combine_docs_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, combine_docs_chain)
    return rag_chain


def query_loop(rag_chain) -> None:
    """Interactive query loop."""
    print("\nRAG Q&A ready. Type your question (or 'quit' to exit).\n")

    while True:
        try:
            question = input("Question: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            print("Goodbye.")
            break

        result = rag_chain.invoke({"input": question})
        print(f"\nAnswer: {result['answer']}")

        print("\nSources used:")
        seen = set()
        for doc in result["context"]:
            source = doc.metadata.get("source", "unknown")
            if source not in seen:
                print(f"  - {source}")
                seen.add(source)
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local RAG Q&A with Chroma")
    parser.add_argument("--index", action="store_true", help="Build/rebuild the index")
    args = parser.parse_args()

    if args.index:
        vectorstore = build_index()
    else:
        vectorstore = load_index()

    rag_chain = build_rag_chain(vectorstore)
    query_loop(rag_chain)
```

**Step 3: Run the example**

Build the index (do this once, or whenever your documents change):
```bash
python example1_chroma_qa.py --index
```

Expected output:
```
Loading documents from: ./knowledge_base
Loaded 8 documents
Split into 47 chunks (chunk_size=500, overlap=50)
Embedding with nomic-embed-text — this may take a minute...
Index built and persisted to: ./chroma_db_example1
Total vectors stored: 47
```

Run the Q&A loop:
```bash
python example1_chroma_qa.py
```

Expected output:
```
Loaded existing index from ./chroma_db_example1 (47 vectors)

RAG Q&A ready. Type your question (or 'quit' to exit).

Question: What is the difference between Chroma and FAISS?
Answer: Chroma automatically persists data to disk using the persist_directory
parameter, while FAISS is an in-memory store that requires explicit save_local()
calls for persistence...

Sources used:
  - ./knowledge_base/vector-stores.md
```

---

### Example 2: PDF Q&A with FAISS and `sentence-transformers` (Custom LCEL Chain)

This example indexes a PDF using FAISS and `sentence-transformers` for fully offline embeddings (no Ollama server dependency for the embedding step), then builds a custom LCEL RAG chain with streaming output.

**Step 1: Install dependencies**

```bash
pip install langchain langchain-community langchain-ollama langchain-huggingface sentence-transformers faiss-cpu pypdf langchain-text-splitters
ollama pull llama3.2
```

**Step 2: Create a sample PDF**

If you do not have a PDF, create a simple one for testing. Any PDF with text content works — a documentation page, a report, or a research paper.

**Step 3: Create the script**

```python
# example2_faiss_pdf_rag.py

"""
PDF Q&A using FAISS + sentence-transformers (fully offline embeddings) + llama3.2.
Uses a custom LCEL chain with streaming output.

Usage:
    python example2_faiss_pdf_rag.py --pdf ./your_document.pdf --index   # build index
    python example2_faiss_pdf_rag.py --pdf ./your_document.pdf           # query
"""

import argparse
import os
import sys

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

# ── Configuration ─────────────────────────────────────────────────────────────
FAISS_DIR = "./faiss_index_example2"
EMBED_MODEL = "all-MiniLM-L6-v2"  # 80 MB, runs fully offline after first download
LLM_MODEL = "llama3.2"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 75
RETRIEVAL_K = 5


def format_docs(docs: list) -> str:
    """Format retrieved documents into a single context string with citations."""
    parts = []
    for i, doc in enumerate(docs, 1):
        page = doc.metadata.get("page", "?")
        source = os.path.basename(doc.metadata.get("source", "unknown"))
        parts.append(f"[Excerpt {i} | {source}, page {page}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def build_index(pdf_path: str) -> FAISS:
    """Load and chunk a PDF, embed it with sentence-transformers, save as FAISS index."""
    if not os.path.isfile(pdf_path):
        print(f"ERROR: PDF not found at '{pdf_path}'")
        sys.exit(1)

    print(f"Loading PDF: {pdf_path}")
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    print(f"Loaded {len(docs)} pages")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(docs)
    print(f"Split into {len(chunks)} chunks")

    print(f"Embedding with {EMBED_MODEL} (downloads on first use, then cached)...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

    vectorstore = FAISS.from_documents(documents=chunks, embedding=embeddings)

    vectorstore.save_local(FAISS_DIR)
    print(f"Index saved to: {FAISS_DIR}")
    return vectorstore


def load_index() -> FAISS:
    """Load a saved FAISS index from disk."""
    if not os.path.isdir(FAISS_DIR):
        print(f"ERROR: No FAISS index found at '{FAISS_DIR}'.")
        print("Run with --index to build it first.")
        sys.exit(1)

    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vectorstore = FAISS.load_local(
        FAISS_DIR,
        embeddings,
        allow_dangerous_deserialization=True,  # required for FAISS pickle format
    )
    print(f"Loaded FAISS index from {FAISS_DIR}")
    return vectorstore


def build_rag_chain(vectorstore: FAISS):
    """Build a streaming LCEL RAG chain."""
    llm = ChatOllama(model=LLM_MODEL, temperature=0.0, num_ctx=8192, num_predict=600)

    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": RETRIEVAL_K},
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert research assistant. Answer the question using only "
            "the document excerpts provided below. Quote or paraphrase specific "
            "excerpts to support your answer. If the answer is not present in the "
            "excerpts, say so explicitly.\n\nDocument excerpts:\n{context}",
        ),
        ("human", "{question}"),
    ])

    rag_chain = (
        {
            "context": retriever | RunnableLambda(format_docs),
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain, retriever


def query_with_streaming(rag_chain, retriever, question: str) -> None:
    """Run a single query with streaming output and show source pages."""
    # First, retrieve the docs so we can display sources
    docs = retriever.invoke(question)

    print(f"\nQuestion: {question}")
    print(f"Retrieved {len(docs)} chunks from pages: "
          f"{sorted({doc.metadata.get('page', '?') for doc in docs})}")
    print("\nAnswer: ", end="", flush=True)

    for chunk in rag_chain.stream(question):
        print(chunk, end="", flush=True)
    print("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF RAG with FAISS + sentence-transformers")
    parser.add_argument("--pdf", required=True, help="Path to the PDF file")
    parser.add_argument("--index", action="store_true", help="Build/rebuild the index")
    parser.add_argument("--question", help="Single question to ask (non-interactive)")
    args = parser.parse_args()

    if args.index:
        vectorstore = build_index(args.pdf)
    else:
        vectorstore = load_index()

    rag_chain, retriever = build_rag_chain(vectorstore)

    if args.question:
        query_with_streaming(rag_chain, retriever, args.question)
    else:
        print("\nPDF RAG ready. Enter your question (or 'quit' to exit).\n")
        while True:
            try:
                question = input("Question: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye.")
                break
            if not question:
                continue
            if question.lower() in {"quit", "exit", "q"}:
                print("Goodbye.")
                break
            query_with_streaming(rag_chain, retriever, question)
```

**Step 4: Run the example**

```bash
# Build the index from a PDF
python example2_faiss_pdf_rag.py --pdf ./your_document.pdf --index

# Ask a single question
python example2_faiss_pdf_rag.py --pdf ./your_document.pdf --question "What are the main topics covered?"

# Interactive mode
python example2_faiss_pdf_rag.py --pdf ./your_document.pdf
```

Expected output for the indexing step:
```
Loading PDF: ./your_document.pdf
Loaded 12 pages
Split into 58 chunks
Embedding with all-MiniLM-L6-v2 (downloads on first use, then cached)...
Index saved to: ./faiss_index_example2
```

Expected output for a question (streaming):
```
Question: What are the main topics covered?
Retrieved 5 chunks from pages: [0, 1, 2, 5, 8]

Answer: Based on the document excerpts, the main topics covered are...
[tokens stream to the terminal as they are generated]
```

---

### Example 3: Multi-Query RAG for Ambiguous Questions

This example demonstrates `MultiQueryRetriever` — particularly useful when users phrase questions differently from how the documents are written. It builds on the Chroma index from Example 1 but can work with any vector store.

**Step 1: Ensure the Example 1 index exists**

```bash
python example1_chroma_qa.py --index
```

**Step 2: Create the multi-query script**

```python
# example3_multi_query_rag.py

"""
Multi-query RAG using MultiQueryRetriever to improve recall on ambiguous questions.
Requires the Chroma index built by example1_chroma_qa.py.

Demonstrates:
  - MultiQueryRetriever.from_llm()
  - Logging the generated alternative queries
  - Comparing single-query vs multi-query retrieval results
  - Full RAG chain with multi-query retriever
"""

import logging

from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate

# ── Enable logging to see the generated alternative queries ───────────────────
logging.basicConfig(level=logging.WARNING)  # suppress other loggers
multi_query_logger = logging.getLogger("langchain.retrievers.multi_query")
multi_query_logger.setLevel(logging.INFO)

# ── Configuration ─────────────────────────────────────────────────────────────
CHROMA_DIR = "./chroma_db_example1"   # index built by example1_chroma_qa.py
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3.2"
RETRIEVAL_K = 3   # per query — with 3 queries, up to 9 unique chunks may be returned


def load_vectorstore() -> Chroma:
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    return Chroma(
        collection_name="knowledge_base",
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )


def build_multi_query_rag_chain(vectorstore: Chroma):
    """Build a RAG chain with MultiQueryRetriever."""
    # The LLM used to generate alternative queries
    # Use moderate temperature so the generated queries are varied
    query_llm = ChatOllama(model=LLM_MODEL, temperature=0.4, num_ctx=2048, num_predict=200)

    # The LLM used to generate the final answer — deterministic
    answer_llm = ChatOllama(model=LLM_MODEL, temperature=0.0, num_ctx=8192, num_predict=512)

    base_retriever = vectorstore.as_retriever(search_kwargs={"k": RETRIEVAL_K})

    # MultiQueryRetriever generates N alternative phrasings of the user question
    # and unions the retrieval results (deduplicated)
    multi_retriever = MultiQueryRetriever.from_llm(
        retriever=base_retriever,
        llm=query_llm,
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Answer the question based only on the provided context. "
            "Be concise and cite the source documents where possible. "
            "If the context does not contain the answer, say so.\n\nContext:\n{context}",
        ),
        ("human", "{input}"),
    ])

    combine_docs_chain = create_stuff_documents_chain(answer_llm, prompt)
    rag_chain = create_retrieval_chain(multi_retriever, combine_docs_chain)
    return rag_chain


def compare_retrieval(vectorstore: Chroma, question: str) -> None:
    """Compare single-query vs multi-query retrieval for a given question."""
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    query_llm = ChatOllama(model=LLM_MODEL, temperature=0.4, num_ctx=2048, num_predict=200)

    single_retriever = vectorstore.as_retriever(search_kwargs={"k": RETRIEVAL_K})
    multi_retriever = MultiQueryRetriever.from_llm(
        retriever=single_retriever,
        llm=query_llm,
    )

    print(f"\nQuestion: {question}")

    single_docs = single_retriever.invoke(question)
    print(f"\nSingle-query retrieval: {len(single_docs)} chunks")
    for doc in single_docs:
        print(f"  - {doc.metadata.get('source', 'unknown')}: {doc.page_content[:80].strip()}")

    print("\n[MultiQueryRetriever is now generating alternative queries — see log output]")
    multi_docs = multi_retriever.invoke(question)
    print(f"\nMulti-query retrieval: {len(multi_docs)} unique chunks")
    for doc in multi_docs:
        print(f"  - {doc.metadata.get('source', 'unknown')}: {doc.page_content[:80].strip()}")


def run_demo(rag_chain) -> None:
    """Run a set of demo questions that benefit from multi-query retrieval."""
    # These questions are deliberately phrased differently from how the
    # information is likely written in the knowledge base docs
    demo_questions = [
        "How do I make retrieval better?",      # docs may say "improve" or "tune" or "optimize"
        "What are the storage options?",         # docs may say "vector store" or "index" or "database"
        "How does the search work internally?",  # docs may say "embedding" or "similarity" or "cosine"
    ]

    for question in demo_questions:
        print(f"\n{'='*60}")
        print(f"Question: {question}")
        print(f"{'='*60}")
        result = rag_chain.invoke({"input": question})
        print(f"Answer:\n{result['answer']}")
        print(f"\nChunks retrieved: {len(result['context'])}")


if __name__ == "__main__":
    import sys

    vectorstore = load_vectorstore()

    if "--compare" in sys.argv:
        # Show the difference between single and multi-query retrieval
        compare_retrieval(vectorstore, "How can I improve retrieval accuracy?")
    else:
        rag_chain = build_multi_query_rag_chain(vectorstore)
        run_demo(rag_chain)
        print("\nRun with --compare to see single vs multi-query retrieval side-by-side:")
        print("  python example3_multi_query_rag.py --compare")
```

**Step 3: Run the example**

```bash
# Run the demo questions
python example3_multi_query_rag.py

# Compare single-query vs multi-query retrieval side-by-side
python example3_multi_query_rag.py --compare
```

Expected log output from `MultiQueryRetriever` (INFO level):
```
INFO:langchain.retrievers.multi_query:Generated queries: [
  'What techniques can improve retrieval accuracy in RAG?',
  'How to optimize chunk retrieval for better results?',
  'What are best practices for improving search precision?'
]
```

Expected comparison output (`--compare`):
```
Question: How can I improve retrieval accuracy?

Single-query retrieval: 3 chunks
  - ./knowledge_base/retrieval.md: Use MMR search type to avoid returning...
  - ./knowledge_base/chunking.md: Chunk size affects retrieval precision...
  - ./knowledge_base/embeddings.md: The embedding model determines...

[MultiQueryRetriever is now generating alternative queries — see log output]

Multi-query retrieval: 7 unique chunks
  - ./knowledge_base/retrieval.md: Use MMR search type to avoid returning...
  - ./knowledge_base/chunking.md: Chunk size affects retrieval precision...
  - ./knowledge_base/embeddings.md: The embedding model determines...
  - ./knowledge_base/tuning.md: Setting k=4 is a good starting point...
  - ./knowledge_base/retrieval.md: Score thresholds filter out low-confidence...
  - ./knowledge_base/advanced.md: MultiQueryRetriever generates alternative...
  - ./knowledge_base/evaluation.md: Manual inspection of retrieved chunks...
```

The multi-query approach retrieved 4 additional unique chunks by covering different phrasings of the same concept. For ambiguous or broad questions, this meaningfully improves recall.

---

## Common Pitfalls

### Pitfall 1: Mixing Embedding Models Between Index and Query

**Description:** The vector store returns irrelevant or nonsensical chunks for every query, or all retrieved docs have nearly identical, very low similarity scores.

**Why it happens:** Each embedding model defines its own high-dimensional vector space. Embeddings from `nomic-embed-text` are incompatible with embeddings from `all-MiniLM-L6-v2` — they are in different spaces. Querying with the wrong model is mathematically equivalent to searching with random noise.

**Incorrect pattern:**
```python
# Indexed with nomic-embed-text...
embed_a = OllamaEmbeddings(model="nomic-embed-text")
vectorstore = Chroma.from_documents(chunks, embed_a, persist_directory="./db")

# ...but queried with all-MiniLM-L6-v2
embed_b = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = Chroma(embedding_function=embed_b, persist_directory="./db")
results = vectorstore.similarity_search("anything")  # results are meaningless
```

**Correct pattern:**
```python
# Use the same model object (or same model name) for both index and query
EMBED_MODEL = "nomic-embed-text"
embeddings = OllamaEmbeddings(model=EMBED_MODEL)

# Index
vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory="./db")

# Query — same embeddings object or same model name
vectorstore = Chroma(embedding_function=OllamaEmbeddings(model=EMBED_MODEL), persist_directory="./db")
```

Store the embedding model name alongside the index as a config file or README so future developers know which model to use.

---

### Pitfall 2: Stale Vector Store After Changing Chunking Parameters

**Description:** After changing `chunk_size` or `chunk_overlap`, retrieval quality seems unchanged or worse, even though you expected an improvement.

**Why it happens:** Chroma's `persist_directory` and FAISS's `save_local()` directory contain embeddings of the old chunks. Changing Python parameters does not update the stored vectors — you must delete the old index and rebuild.

**Incorrect pattern:**
```python
# Changed chunk_size from 500 to 300 in the code, but did not delete old index
splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
chunks = splitter.split_documents(docs)

# This ADDS the new chunks to the existing old-chunk index — mixing two chunk sizes
vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory="./chroma_db")
```

**Correct pattern:**
```python
import shutil

CHROMA_DIR = "./chroma_db"

# Delete the old index before rebuilding with new parameters
if os.path.isdir(CHROMA_DIR):
    shutil.rmtree(CHROMA_DIR)
    print(f"Deleted old index at {CHROMA_DIR}")

splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
chunks = splitter.split_documents(docs)
vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory=CHROMA_DIR)
```

---

### Pitfall 3: Context Window Overflow with Large K

**Description:** The model's answers become repetitive, incoherent, or it says "I don't have enough information" despite relevant chunks being retrieved. No error is raised.

**Why it happens:** With `k=10` and `chunk_size=600`, you are injecting ~6000 characters (~1500 tokens) of context before the question and answer tokens. If this exceeds `num_ctx`, Ollama silently truncates the beginning of the prompt — typically the system message and early context — and the model receives a malformed prompt.

**Incorrect pattern:**
```python
llm = ChatOllama(model="llama3.2", num_ctx=2048)  # Ollama default — too small for RAG
retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
# 10 chunks * 600 chars each = ~6000 chars of context alone; far exceeds 2048 tokens
```

**Correct pattern:**
```python
# Budget: context window (8192) - answer tokens (512) - prompt overhead (200) = ~7480 tokens
# At ~4 chars/token: 7480 * 4 = ~29,920 chars of context budget
# With chunk_size=500 and k=4: 4 * 500 = 2000 chars — well within budget
llm = ChatOllama(model="llama3.2", num_ctx=8192, num_predict=512)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
```

---

### Pitfall 4: Forgetting `allow_dangerous_deserialization=True` for FAISS

**Description:** `FAISS.load_local()` raises an error like `ValueError: The de-serialization relies on pickle, which can be dangerous.`

**Why it happens:** FAISS serializes its index using Python's `pickle` module. LangChain requires you to explicitly acknowledge this security consideration when loading — arbitrary pickle files can execute code. The flag is a deliberate safety gate.

**Incorrect pattern:**
```python
# This raises ValueError
vectorstore = FAISS.load_local("./faiss_index", embeddings)
```

**Correct pattern:**
```python
# Only use this flag when loading FAISS indexes you built yourself
vectorstore = FAISS.load_local(
    "./faiss_index",
    embeddings,
    allow_dangerous_deserialization=True,
)
```

Never load a FAISS index from an untrusted source with `allow_dangerous_deserialization=True`. Treat FAISS index files with the same care as executable code.

---

### Pitfall 5: Chunk Size Too Large — Retrieval Returns Whole Documents

**Description:** Retrieval returns large chunks that each cover many topics, causing the model to receive noisy context and produce vague or off-topic answers.

**Why it happens:** With `chunk_size=3000`, each chunk is nearly an entire document. The similarity score between the query and the chunk is averaged over all the topics in the chunk, not focused on the relevant section. A chunk about "vector stores, chunking, and embeddings" will match queries about any of those topics at medium similarity — rather than matching queries about one topic at high similarity.

**Incorrect pattern:**
```python
# chunk_size=3000 is almost the entire document for many use cases
splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=100)
chunks = splitter.split_documents(docs)
# Result: 5 chunks instead of 50; each chunk covers many topics; retrieval is imprecise
```

**Correct pattern:**
```python
# Start with 500 characters (~125 tokens) — one to two focused paragraphs per chunk
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(docs)
# Inspect a sample chunk to verify it contains one coherent topic
print(chunks[5].page_content)
```

If the sample chunk cuts a sentence mid-thought or seems disjointed, increase `chunk_overlap`. If it contains too many unrelated topics, decrease `chunk_size`.

---

### Pitfall 6: Re-Embedding Documents on Every Script Run

**Description:** Each time the script runs, it calls `from_documents()` and spends 30–120 seconds re-embedding documents that were already indexed.

**Why it happens:** `from_documents()` always embeds and stores documents — it does not check whether they already exist in the index. Without a conditional check, indexing happens every run.

**Incorrect pattern:**
```python
# Re-indexes every time, even when nothing changed
vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory="./chroma_db")
```

**Correct pattern:**
```python
import os

CHROMA_DIR = "./chroma_db"

if os.path.isdir(CHROMA_DIR) and os.listdir(CHROMA_DIR):
    # Index already exists — load it
    vectorstore = Chroma(
        collection_name="my_docs",
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )
    print("Loaded existing index")
else:
    # Index does not exist — build it
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name="my_docs",
        persist_directory=CHROMA_DIR,
    )
    print("Built new index")
```

---

## Summary

- RAG (Retrieval-Augmented Generation) solves the knowledge cutoff and private data problems by indexing your documents into a searchable vector store and injecting only the relevant chunks into the LLM prompt at query time — without modifying model weights.
- Local embeddings are generated with `OllamaEmbeddings` (using `nomic-embed-text` or `mxbai-embed-large` via the Ollama server) or `HuggingFaceEmbeddings` (using `sentence-transformers` models like `all-MiniLM-L6-v2` for fully offline operation); the same model must be used for both indexing and querying.
- Chroma persists vectors automatically to disk via `persist_directory`, making it the easiest choice for local development; FAISS is faster for large corpora and requires explicit `save_local()` / `load_local()` calls.
- RAG chains are assembled with `create_retrieval_chain` + `create_stuff_documents_chain` for the common case, or with a custom LCEL `{context: retriever | format_docs, question: RunnablePassthrough()} | prompt | llm | parser` pattern for full control including streaming.
- `MultiQueryRetriever` improves recall on ambiguous questions by generating alternative phrasings of the query; `ContextualCompressionRetriever` improves precision by extracting only the relevant sentences from each retrieved chunk; the parent document retriever pattern balances retrieval precision with answer context quality.

---

## Further Reading

- [LangChain — Chroma Integration Documentation](https://docs.langchain.com/oss/python/integrations/vectorstores/chroma) — The official LangChain documentation for the `langchain-chroma` package, covering installation, constructor parameters, `from_documents()`, `similarity_search_with_score()`, metadata filtering, and `as_retriever()` with all `search_type` options.

- [LangChain — FAISS Integration Documentation](https://docs.langchain.com/oss/python/integrations/vectorstores/faiss) — The official LangChain documentation for the FAISS integration, covering `from_documents()`, `save_local()`, `load_local()` (including the `allow_dangerous_deserialization` parameter), metadata filtering with MongoDB-style operators, and merging multiple indexes with `merge_from()`.

- [LangChain — Sentence Transformers Embeddings Integration](https://docs.langchain.com/oss/python/integrations/text_embedding/sentence_transformers) — Official documentation for `HuggingFaceEmbeddings` from the `langchain-huggingface` package, including installation, model selection, and the note that sentence-transformers runs locally on CPU after the first model download with no network dependency.

- [Ollama Embedding Models — Official Blog](https://ollama.com/blog/embedding-models) — Ollama's announcement post for embedding model support, explaining how to pull and use `nomic-embed-text` and `mxbai-embed-large`, with benchmarks comparing them against commercial models like `text-embedding-ada-002` and guidance on choosing between them.

- [nomic-embed-text on Ollama Library](https://ollama.com/library/nomic-embed-text) — The official Ollama model page for `nomic-embed-text`, including the pull command, model size (274 MB), embedding dimensions (768), and context window size. The primary reference when you need the exact model identifier or want to check for newer versions.

- [LangChain — How to Build a RAG Application](https://docs.langchain.com/oss/python/langchain/rag) — The official LangChain tutorial for building a complete RAG application, covering `create_retrieval_chain`, `create_stuff_documents_chain`, the retriever interface, and LCEL RAG patterns with worked code examples.

- [MTEB Leaderboard — Massive Text Embedding Benchmark](https://huggingface.co/spaces/mteb/leaderboard) — The authoritative benchmark for comparing embedding models across retrieval, classification, and clustering tasks. Use this when selecting an embedding model for production — filter by model size and task type (`Retrieval`) to find the best model for your hardware constraints.

- [LangChain MultiQueryRetriever API Reference](https://python.langchain.com/api_reference/langchain/retrievers/langchain.retrievers.multi_query.MultiQueryRetriever.html) — Full API reference for `MultiQueryRetriever`, including `from_llm()` parameters, how to supply a custom prompt for query generation, and configuration for the number of alternative queries to generate.
