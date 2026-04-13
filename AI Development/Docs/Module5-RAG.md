# Module 5: Retrieval-Augmented Generation (RAG)

**Subject:** AI Development
**Difficulty:** Intermediate to Advanced
**Estimated Time:** 375 minutes (including hands-on examples)
**Prerequisites:**
- Completed Module 1: Building a Basic AI Chatbot with No Framework — you must be comfortable with raw SDK calls, the messages array, and API key management
- Completed Module 2: The LangChain Framework — familiarity with LCEL chains, `ChatOllama` or `ChatAnthropic`, and provider abstraction
- Completed Module 3: AI Workflows and LangGraph — understanding of graph-based orchestration is helpful for the agentic RAG section
- Completed Module 4: AI Agents and Agentic AI — understanding of tool use, the ReAct loop, and agent memory; the agentic RAG section builds directly on this
- Python 3.10 or later
- Ollama installed locally with `llama3.2` and `nomic-embed-text` pulled (primary examples use local models; cloud API alternatives are noted throughout)

---

## Overview

Language models have a hard boundary on what they know: their training data has a cutoff date, they cannot access your organisation's private documents, and even within their knowledge they will sometimes hallucinate facts with high confidence. You could try to solve all three problems by continuously retraining a model — but that costs millions of dollars and takes months.

**Retrieval-Augmented Generation (RAG)** is the practical alternative. Rather than baking all knowledge into the model's weights, RAG retrieves relevant passages from an external knowledge base at query time and inserts them into the model's context window alongside the user's question. The model then generates a response grounded in that retrieved evidence. It reads the documents; it doesn't have to memorise them.

RAG is now the dominant architecture for production AI applications that require factual accuracy, fresh information, or access to proprietary data. Gartner cited RAG as the most commonly deployed enterprise AI pattern in 2025, and the tooling ecosystem around it has matured rapidly.

By the end of this module you will be able to:

- Explain what RAG is and precisely why it is necessary (knowledge cutoffs, hallucination, context limits)
- Walk through every stage of the full RAG pipeline: ingestion, chunking, embedding, storage, retrieval, augmentation, and generation
- Choose an appropriate embedding model for a given use case
- Select and configure a vector store (Chroma, FAISS, Pinecone, pgvector) based on requirements
- Apply chunking strategies correctly: fixed-size, sentence-based, semantic, and recursive
- Distinguish semantic search, keyword search, and hybrid search and know when each wins
- Implement baseline and advanced RAG patterns in Python using LangChain
- Integrate retrieval into an agent as a callable tool (agentic RAG)
- Evaluate a RAG system using the RAGAS framework across faithfulness, answer relevancy, context precision, and context recall

---

## Required Libraries and Packages

| Package | Version | Purpose | Install |
|---|---|---|---|
| `langchain` | >= 1.2.15 | Core orchestration and LCEL chain primitives | `pip install langchain` |
| `langchain-ollama` | >= 1.0.1 | Ollama chat model and embeddings (local, primary) | `pip install langchain-ollama` |
| `langchain-openai` | >= 1.1.12 | OpenAI chat model and embeddings (cloud, optional) | `pip install langchain-openai` |
| `langchain-community` | >= 0.4.1 | Document loaders, FAISS, community integrations | `pip install langchain-community` |
| `langchain-chroma` | >= 0.2 | Chroma vector store integration | `pip install langchain-chroma` |
| `chromadb` | >= 1.5.5 | Chroma vector database | `pip install chromadb` |
| `faiss-cpu` | >= 1.13.2 | Facebook AI Similarity Search (CPU build) | `pip install faiss-cpu` |
| `sentence-transformers` | >= 3.0 | Open-source embedding models | `pip install sentence-transformers` |
| `ragas` | >= 0.4.3 | RAG evaluation framework | `pip install ragas` |
| `pypdf` | >= 4.0 | PDF document loading | `pip install pypdf` |
| `tiktoken` | >= 0.7 | Token counting for chunk size estimation | `pip install tiktoken` |
| `python-dotenv` | >= 1.0 | Load `.env` API keys | `pip install python-dotenv` |

**Local-first install (no API key required):**

```bash
# Pull models first:
ollama pull llama3.2            # chat model
ollama pull nomic-embed-text    # embedding model

pip install langchain langchain-ollama langchain-community langchain-chroma \
            chromadb faiss-cpu sentence-transformers ragas pypdf tiktoken python-dotenv
```

**Optional: Add OpenAI for cloud API examples:**

```bash
pip install langchain-openai
```

Place your key in a `.env` file if using cloud examples:

```
OPENAI_API_KEY=sk-...
```

---

## Key Concepts

### 1. Why RAG Exists: Three Problems It Solves

Before writing a single line of code, you need to understand the specific failure modes that RAG addresses. This context makes every architectural decision that follows feel motivated rather than arbitrary.

#### Problem 1: Knowledge Cutoff

Every LLM is a snapshot. GPT-4o was trained on data through early 2024. Claude Sonnet 4.6 has a knowledge cutoff of August 2025. Ask either model about a product release, a regulation change, or a court ruling after that date and the model will either admit ignorance or — worse — confabulate a plausible-sounding answer based on older patterns.

RAG breaks this constraint. If you maintain a knowledge base of documents and re-index them whenever they change, every query your system answers will be grounded in current information without any model retraining.

> **Knowledge cutoffs (April 2026):** Claude Haiku 4.5 has a training data cutoff of July 2025; Claude Sonnet 4.6 has a training data cutoff of January 2026. Local models (llama3.2, mistral) typically have cutoffs from late 2024. Any event, document, or fact after those dates is invisible to the model without RAG.

#### Problem 2: Hallucination

LLMs are next-token predictors. They generate text that is statistically coherent with their training distribution. When asked about something outside that distribution — an obscure regulation, a specific internal policy, a niche API — the model may generate text that *sounds* correct but is factually wrong.

RAG combats hallucination by providing explicit source material. The model is asked to answer *from the retrieved documents*, not from memory. This gives you a mechanism to audit answers: if the model's claim isn't traceable to a retrieved chunk, you can flag it.

#### Problem 3: Context Window Limits

Even today's largest context windows (GPT-4o at 128k tokens, Gemini 1.5 at 1M tokens) cannot hold an entire enterprise knowledge base. A legal team's document repository may contain millions of tokens. An engineering wiki might be comparable in size.

Stuffing everything into a context window is also expensive — you pay per input token. Retrieving only the top-5 most relevant passages for each query and sending those is orders of magnitude cheaper and often *more accurate*, because the model is not distracted by irrelevant content.

---

### 2. The Full RAG Pipeline

RAG has two clearly distinct phases that operate at different times.

**Indexing (offline / batch):** Documents are processed once (or re-processed when they change) and stored in a form that supports fast similarity search.

**Retrieval and Generation (online / per-query):** When a user submits a question, the system retrieves relevant passages and hands them to the model.

```
INDEXING PIPELINE
─────────────────
Raw Documents
    │
    ▼
Document Loader      ← PDF, HTML, DOCX, Markdown, web pages, databases
    │
    ▼
Text Splitter        ← Chunking strategy + size + overlap
    │
    ▼
Embedding Model      ← Each chunk → dense vector (e.g., 1536 floats)
    │
    ▼
Vector Store         ← FAISS / Chroma / Pinecone / pgvector


QUERY PIPELINE
──────────────
User Question
    │
    ▼
Embedding Model      ← Question → dense vector (same model as indexing!)
    │
    ▼
Vector Store         ← Similarity search → top-K chunks
    │
    ▼
Prompt Assembly      ← System prompt + retrieved chunks + user question
    │
    ▼
LLM                  ← Generates answer grounded in retrieved context
    │
    ▼
Response (+ sources)
```

Each stage has important decisions. The rest of this section covers them in order.

---

### 3. Document Loaders

Before you can index anything, you need to get your documents into memory as plain text. LangChain ships loaders for most common formats:

| Format | LangChain Loader | Notes |
|---|---|---|
| PDF | `PyPDFLoader` | Extracts text page by page; use `pypdf` |
| Web pages | `WebBaseLoader` | Scrapes HTML and strips tags |
| Plain text | `TextLoader` | Fastest, no dependencies |
| DOCX | `Docx2txtLoader` | Requires `docx2txt` |
| CSV | `CSVLoader` | Each row becomes a document |
| Markdown | `UnstructuredMarkdownLoader` | Preserves headings |
| Directory | `DirectoryLoader` | Recursively loads a folder |

All loaders return a list of `Document` objects, each with a `page_content` string and a `metadata` dictionary. Metadata (file name, page number, URL, creation date) travels with the chunk all the way through to retrieval — preserve it, because it enables citation and filtering.

---

### 4. Chunking Strategies

A "chunk" is the unit of text that gets embedded and stored. Getting chunking right is one of the highest-leverage decisions in RAG design. A chunk that is too small loses context; one that is too large dilutes relevance and wastes tokens.

#### Fixed-Size (Character) Chunking

Split every N characters regardless of sentence or paragraph boundaries. Fast, simple, and terrible for production — it routinely cuts sentences in half and fragments concepts. Use it only for rapid prototyping.

#### Recursive Character Chunking (Recommended Default)

LangChain's `RecursiveCharacterTextSplitter` tries to split on paragraphs (`\n\n`) first, then sentences (`\n`), then words (` `), and finally characters — whichever keeps the chunk under the target size. This respects natural language boundaries as much as possible while guaranteeing a size limit.

**Recommended starting parameters:**
- `chunk_size`: 400–512 tokens for factoid queries; 1024 tokens for analytical queries
- `chunk_overlap`: 10–20% of `chunk_size` (e.g., 50–100 tokens for a 512-token chunk)

The overlap ensures that information sitting at a chunk boundary is represented in at least one complete chunk.

#### Sentence-Based Chunking

Use a sentence boundary detector (e.g., spaCy or NLTK) to split on complete sentences. Produces variable-length chunks, which complicates batch processing, but ensures no sentence is split mid-thought. Best for conversational content and Q&A datasets.

#### Semantic Chunking

Embed every sentence, then group sentences that are semantically similar (measured by cosine distance) into the same chunk. Splits occur where topic shifts happen, not at fixed positions. Achieves 91–92% recall versus 85–90% for recursive splitting in benchmarks, but requires embedding every sentence during indexing (expensive). Reserve this for high-value, dense technical content where retrieval accuracy matters most.

#### Chunking Strategy Decision Table

| Strategy | Recall | Cost | Complexity | Best For |
|---|---|---|---|---|
| Fixed-size | Low | Very low | Minimal | Prototypes only |
| Recursive character | High | Low | Low | General purpose — start here |
| Sentence-based | High | Low | Medium | Conversational / Q&A content |
| Semantic | Highest | High | High | Dense technical documents |
| Page-level | High | Low | Low | PDFs and paginated reports |

---

### 5. Embedding Models

An embedding model converts a piece of text into a dense vector — a list of floating-point numbers — where semantic similarity between texts corresponds to geometric proximity between vectors. The cosine similarity between two vectors tells you how related their source texts are.

The embedding model you choose during indexing **must** be the same model you use at query time. Mixing models produces nonsensical similarity scores.

#### OpenAI Embedding Models

| Model | Dimensions | MTEB Score | Cost (per 1M tokens) | Notes |
|---|---|---|---|---|
| `text-embedding-3-small` | 1536 (truncatable to 512) | ~62 | $0.02 | Best cost/performance ratio; recommended default |
| `text-embedding-3-large` | 3072 (truncatable to 256) | ~64.6 | $0.13 | Highest accuracy; use when quality is critical |
| `text-embedding-ada-002` | 1536 | ~61 | $0.10 | Legacy; prefer `text-embedding-3-small` |

OpenAI's `text-embedding-3` series supports **Matryoshka Representation Learning** — you can truncate vectors to fewer dimensions (e.g., 256 instead of 1536) with only minor quality loss. This can reduce storage and search cost by 6x.

#### Open-Source / Self-Hosted Embedding Models

| Model | Dimensions | MTEB Score | Speed | Notes |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | ~56 | 14.7 ms / 1K tokens | Fastest; best for high-volume or latency-sensitive pipelines |
| `BAAI/bge-base-en-v1.5` | 768 | ~64.2 | ~80 ms / 1K tokens | Strong accuracy; free; instruction-tuned |
| `BAAI/bge-m3` | 1024 | ~63.0 | ~90 ms / 1K tokens | Best open-source multilingual (100+ languages) |
| `intfloat/e5-large-v2` | 1024 | ~64.0 | ~82 ms / 1K tokens | Strong general-purpose; prefix queries with `query:` |

**How to choose:**
- Start with `text-embedding-3-small` if you are already paying for OpenAI and want zero operational overhead.
- Choose `all-MiniLM-L6-v2` when latency or per-token cost is a hard constraint.
- Choose `BAAI/bge-m3` when you need multilingual support or want to avoid vendor lock-in.
- MTEB scores are a useful signal but benchmark on your own data before committing — domain-specific content often produces different rankings than the MTEB general benchmark.

---

### 6. Vector Stores

A vector store is a database optimised for approximate nearest-neighbour (ANN) search over high-dimensional vectors. When you query with an embedded question, the store returns the K vectors (and their associated documents) whose embeddings are closest to the query vector.

#### FAISS

**What it is:** A library from Meta Research for efficient similarity search. Not a database — a library you embed in your application.

**Strengths:** Extremely fast; GPU-accelerated variants available; free; no external service required.

**Weaknesses:** No built-in persistence (you save/load index files manually), no metadata filtering, no REST API, not designed for concurrent writes. Essentially read-only at query time.

**Use when:** You have a static or rarely-changing knowledge base; you are running offline or in a compute-constrained environment; you need maximum search speed and are willing to manage infrastructure yourself.

#### Chroma

**What it is:** An open-source, developer-friendly vector database designed for RAG prototyping. Runs embedded in your process (no external server required) or as a standalone server.

**Strengths:** Simplest API in the ecosystem; automatic persistence; basic metadata filtering; zero configuration for local use.

**Weaknesses:** Not optimised for datasets above a few million vectors; limited horizontal scalability.

**Use when:** You are building a prototype, a demo, or a small-to-medium production system. The go-to choice for learning and for applications where operational simplicity beats raw performance.

#### Pinecone

**What it is:** A fully managed, cloud-hosted vector database. You provision an index, insert vectors via API, and query via API — the infrastructure is invisible.

**Strengths:** Zero operations; automatic sharding and replication; handles billions of vectors; strong metadata filtering; production SLA.

**Weaknesses:** Cost (serverless plans start affordable but scale up quickly); cloud-only (data leaves your infrastructure); vendor lock-in.

**Use when:** You are building a production system that needs to scale and your team does not want to operate databases. Also appropriate when your organisation already uses cloud-managed services and consistency of operational model matters.

#### pgvector

**What it is:** A PostgreSQL extension that adds a `vector` column type and ANN index operators (`ivfflat`, `hnsw`) to standard PostgreSQL.

**Strengths:** Your documents, metadata, and vectors live in one relational database; full SQL for filtering; ACID transactions; familiar tooling; free.

**Weaknesses:** Not as fast as dedicated vector databases for very large datasets (hundreds of millions of vectors); requires PostgreSQL administration.

**Use when:** Your application already uses PostgreSQL and you want to avoid adding another service to your stack. Excellent for applications where vector search is one feature among many relational features.

#### Vector Store Decision Matrix

| Requirement | FAISS | Chroma | Pinecone | pgvector |
|---|---|---|---|---|
| Zero infrastructure | No | Yes (embedded) | Yes (managed) | No |
| Persistence out of the box | No | Yes | Yes | Yes |
| Rich metadata filtering | No | Basic | Yes | Full SQL |
| Scalability to billions of vectors | Yes (with effort) | No | Yes | No |
| Cost | Free | Free | $$ | Free |
| Best team profile | Research / ML | Prototyping | Product / no-ops | Full-stack / existing Postgres |

---

### 7. Semantic Search vs. Keyword Search vs. Hybrid Search

#### Semantic Search (Dense Retrieval)

Converts both query and documents into dense vectors and retrieves the documents closest in vector space. Captures *meaning*, not literal words. Works well when the user's vocabulary differs from the document's vocabulary ("what are the CEO's pay details" retrieves documents that say "executive compensation").

**Weakness:** Can miss exact matches (a specific product code, a legal citation, a person's name) if the model treats those tokens as low-information.

#### Keyword Search (Sparse Retrieval / BM25)

Classic full-text search. Ranks documents by term frequency and inverse document frequency. Deterministic, fast, no model required. Excellent for exact matches and rare proper nouns.

**Weakness:** Fails on synonyms and paraphrase. "Car" and "automobile" are unrelated from BM25's perspective.

#### Hybrid Search

Combines dense and sparse scores — typically with a weighted sum or by running both retrievers and merging result lists. Most production RAG systems use hybrid search because it inherits the strengths of both approaches.

LangChain's `EnsembleRetriever` provides hybrid search by combining any two retrievers. Reciprocal Rank Fusion (RRF) is the standard score-merging algorithm and is implemented by `EnsembleRetriever` by default.

**Rule of thumb:** If your documents contain lots of technical identifiers, code, or exact-match queries, lean toward hybrid. If your documents are rich prose and your queries are natural-language questions, dense-only is often sufficient.

---

## Hands-On Example 1: Building a Baseline RAG Pipeline (Ollama — Local First)

This example builds a complete RAG system from scratch using only local models: load a document, split it into chunks, embed with `nomic-embed-text` via Ollama, store in Chroma, then answer questions using `llama3.2`. No API key required.

**Setup:**

```bash
# Pull models first:
ollama pull llama3.2
ollama pull nomic-embed-text
```

```python
# baseline_rag.py
# LOCAL FIRST: Uses Ollama for both embeddings and generation.
# No API key required.
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# ── 1. LOAD ──────────────────────────────────────────────────────────────────
# In production, replace TextLoader with PyPDFLoader, WebBaseLoader, etc.
loader = TextLoader("knowledge_base.txt", encoding="utf-8")
documents = loader.load()
print(f"Loaded {len(documents)} document(s)")

# ── 2. CHUNK ─────────────────────────────────────────────────────────────────
splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=64,          # ~12% overlap
    length_function=len,       # character-based; swap for token-based below
    separators=["\n\n", "\n", ". ", " ", ""],
)
chunks = splitter.split_documents(documents)
print(f"Split into {len(chunks)} chunks")

# ── 3. EMBED AND STORE ───────────────────────────────────────────────────────
# nomic-embed-text is a high-quality local embedding model.
# Pull it first: ollama pull nomic-embed-text
embeddings = OllamaEmbeddings(model="nomic-embed-text")
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="./chroma_db_local",   # persists to disk automatically
)
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5},            # return top 5 chunks per query
)

# ── 4. ASSEMBLE THE RAG CHAIN ────────────────────────────────────────────────
RAG_PROMPT = """\
You are a helpful assistant. Answer the question using ONLY the context below.
If the answer is not in the context, say "I don't have enough information to answer that."
Always cite which part of the context supports your answer.

Context:
{context}

Question: {question}
"""

prompt = ChatPromptTemplate.from_template(RAG_PROMPT)

# Pull model first: ollama pull llama3.2
llm = ChatOllama(model="llama3.2", temperature=0)

def format_docs(docs):
    return "\n\n---\n\n".join(
        f"[Source: {d.metadata.get('source', 'unknown')}]\n{d.page_content}"
        for d in docs
    )

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# ── 5. QUERY ─────────────────────────────────────────────────────────────────
question = "What are the main topics covered in the document?"
answer = rag_chain.invoke(question)
print(f"\nQ: {question}\nA: {answer}")
```

To run this example, create a `knowledge_base.txt` file in the same directory with any text content, then run:

```bash
python baseline_rag.py
```

The `./chroma_db_local` directory will be created and persisted. On subsequent runs, load the existing store to avoid re-indexing:

```python
# Load existing Chroma store without re-indexing
vectorstore = Chroma(
    persist_directory="./chroma_db_local",
    embedding_function=embeddings,
)
```

#### Cloud API Alternative (Optional)

To use OpenAI embeddings and GPT-4o instead, replace the embeddings and LLM lines:

```python
# --- Optional: Cloud API alternative ---
import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

load_dotenv()  # requires OPENAI_API_KEY in .env

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
llm = ChatOpenAI(model="gpt-4o", temperature=0)
# All other code stays identical.
```

OpenAI's `text-embedding-3-small` produces 1536-dimensional vectors versus `nomic-embed-text`'s 768-dimensional vectors. For most RAG use cases, local quality is sufficient.

---

## Hands-On Example 2: Using Open-Source Embeddings with FAISS (Cloud API Optional)

This example demonstrates a mostly local pipeline using `sentence-transformers` for embeddings and FAISS for storage — no API key required for the embedding step. The LLM call uses OpenAI; see the note below to swap it for a local Ollama model.

```python
# local_rag_faiss.py
import os
import pickle
from dotenv import load_dotenv
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

FAISS_INDEX_PATH = "./faiss_index"

# ── 1. LOAD AND CHUNK ────────────────────────────────────────────────────────
loader = TextLoader("knowledge_base.txt", encoding="utf-8")
documents = loader.load()

splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)
chunks = splitter.split_documents(documents)

# ── 2. EMBED WITH SENTENCE-TRANSFORMERS ──────────────────────────────────────
# Model downloads on first run (~90MB); cached locally afterward.
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

# ── 3. BUILD OR LOAD FAISS INDEX ─────────────────────────────────────────────
if os.path.exists(FAISS_INDEX_PATH):
    vectorstore = FAISS.load_local(
        FAISS_INDEX_PATH,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    print("Loaded existing FAISS index from disk")
else:
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(FAISS_INDEX_PATH)
    print(f"Built and saved FAISS index ({len(chunks)} chunks)")

retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

# ── 4. RAG CHAIN ─────────────────────────────────────────────────────────────
# LOCAL (primary for LLM): Pull model first with: ollama pull llama3.2
# from langchain_ollama import ChatOllama
# llm = ChatOllama(model="llama3.2", temperature=0)

# --- Cloud API alternative (requires OPENAI_API_KEY) ---
# from dotenv import load_dotenv; load_dotenv()
# from langchain_openai import ChatOpenAI
# llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Using cloud here for illustration; swap to ChatOllama above for fully local:
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

RAG_PROMPT = """\
Answer the following question using only the provided context.
If you cannot find the answer in the context, say so explicitly.

Context:
{context}

Question: {question}

Answer:"""

prompt = ChatPromptTemplate.from_template(RAG_PROMPT)

rag_chain = (
    {"context": retriever | (lambda docs: "\n\n".join(d.page_content for d in docs)),
     "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

question = "Summarise the key points from the document."
answer = rag_chain.invoke(question)
print(f"\nQ: {question}\nA: {answer}")
```

---

## Advanced RAG Patterns

> **Local model note:** All advanced pattern examples below use OpenAI for brevity. Every example can be run with local Ollama models by replacing the embeddings and LLM lines with the equivalents from Example 1 above:
> ```python
> from langchain_ollama import OllamaEmbeddings, ChatOllama
> embeddings = OllamaEmbeddings(model="nomic-embed-text")   # replaces OpenAIEmbeddings
> llm = ChatOllama(model="llama3.2", temperature=0)         # replaces ChatOpenAI
> ```
> The vector store, retriever, chain, and prompt logic are identical for both local and cloud models.

Baseline RAG performs well on clean, well-structured documents with clear questions. Real-world deployments face harder cases: ambiguous queries, multi-part questions, vocabulary mismatch between user and document, or documents where a single retrieved chunk lacks enough context. The patterns below address these systematically.

### 8. HyDE — Hypothetical Document Embeddings

**The problem it solves:** A user's question ("what's wrong with my connection timeout?") lives in a different part of the embedding space than the relevant documentation ("configuring connection pool parameters"). The gap reduces retrieval recall.

**How it works:** Instead of embedding the raw question, you ask the LLM to generate a *hypothetical answer* — a short paragraph that describes what a good answer would look like. You then embed that hypothetical answer and use it as the retrieval query. The hypothesis lives in the same part of embedding space as real documents.

```python
# hyde_rag.py
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

load_dotenv()

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Step 1: Generate a hypothetical answer
HYDE_PROMPT = """\
Write a short, detailed passage (2-4 sentences) that would directly answer
the following question. Do not say you don't know — write the most plausible
answer as if you were an expert. This passage will be used for document retrieval.

Question: {question}

Hypothetical passage:"""

hyde_chain = ChatPromptTemplate.from_template(HYDE_PROMPT) | llm | StrOutputParser()

# Step 2: Embed the hypothesis and retrieve
def hyde_retrieve(question: str, k: int = 5):
    hypothesis = hyde_chain.invoke({"question": question})
    # Embed the hypothesis, not the original question
    hypothesis_vector = embeddings.embed_query(hypothesis)
    docs = vectorstore.similarity_search_by_vector(hypothesis_vector, k=k)
    return docs

# Step 3: Generate the final answer from retrieved docs
ANSWER_PROMPT = """\
Answer the question using only the context below.

Context:
{context}

Question: {question}

Answer:"""

answer_prompt = ChatPromptTemplate.from_template(ANSWER_PROMPT)

def format_docs(docs):
    return "\n\n".join(d.page_content for d in docs)

def full_hyde_pipeline(question: str) -> str:
    docs = hyde_retrieve(question)
    context = format_docs(docs)
    response = (answer_prompt | llm | StrOutputParser()).invoke(
        {"context": context, "question": question}
    )
    return response

answer = full_hyde_pipeline("How do I configure connection pool timeouts?")
print(answer)
```

**When to use HyDE:** When your baseline retrieval has poor recall on natural-language questions against technical documentation. Run an A/B comparison — HyDE adds one LLM call per query, so only adopt it if the recall improvement justifies the cost.

---

### 9. Multi-Query Retrieval

**The problem it solves:** A single query may be expressed in a way that misses relevant documents phrased differently. Multi-query generates several paraphrases of the question and deduplicates the combined result set.

```python
# multi_query_rag.py
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.retrievers import MultiQueryRetriever
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
import logging

load_dotenv()

# Optionally enable logging to see generated queries
logging.basicConfig()
logging.getLogger("langchain.retrievers.multi_query").setLevel(logging.INFO)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
llm = ChatOpenAI(model="gpt-4o", temperature=0.3)  # slight temperature for variety

# MultiQueryRetriever wraps any base retriever
base_retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
multi_retriever = MultiQueryRetriever.from_llm(
    retriever=base_retriever,
    llm=llm,
)

RAG_PROMPT = """\
Answer the question using only the context below.

Context:
{context}

Question: {question}

Answer:"""

prompt = ChatPromptTemplate.from_template(RAG_PROMPT)

rag_chain = (
    {
        "context": multi_retriever | (lambda docs: "\n\n".join(d.page_content for d in docs)),
        "question": RunnablePassthrough(),
    }
    | prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke("What are the performance implications of large context windows?")
print(answer)
```

By default `MultiQueryRetriever` generates three query variants and deduplicates results by document ID. It logs the generated queries when logging is enabled — useful for debugging.

---

### 10. Re-Ranking with Cross-Encoders

**The problem it solves:** Dense retrieval (bi-encoder) embeds query and documents independently and compares vectors. This is fast but imprecise because the query and document never "see" each other during scoring. A cross-encoder processes the query and each candidate document *together* through the transformer, producing a much more accurate relevance score — but is too slow to run over an entire corpus.

The standard pattern is a two-stage pipeline: retrieve a large candidate set cheaply (e.g., top 20 with a bi-encoder), then re-rank those 20 with the cross-encoder to extract the top 5.

```python
# reranking_rag.py
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

load_dotenv()

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Stage 1: retrieve top 20 candidates with the bi-encoder
base_retriever = vectorstore.as_retriever(search_kwargs={"k": 20})

# Stage 2: re-rank with a cross-encoder model (downloads ~270MB on first run)
cross_encoder = HuggingFaceCrossEncoder(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
reranker = CrossEncoderReranker(model=cross_encoder, top_n=5)

# ContextualCompressionRetriever handles the two-stage flow
reranking_retriever = ContextualCompressionRetriever(
    base_compressor=reranker,
    base_retriever=base_retriever,
)

RAG_PROMPT = """\
Answer using only the context below. Cite specific passages where possible.

Context:
{context}

Question: {question}

Answer:"""

prompt = ChatPromptTemplate.from_template(RAG_PROMPT)

rag_chain = (
    {
        "context": reranking_retriever | (lambda docs: "\n\n".join(d.page_content for d in docs)),
        "question": RunnablePassthrough(),
    }
    | prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke("What chunking strategy should I use for technical documentation?")
print(answer)
```

**Cross-encoder model options:**
- `cross-encoder/ms-marco-MiniLM-L-6-v2` — fast, good general-purpose re-ranker (~270MB)
- `cross-encoder/ms-marco-MiniLM-L-12-v2` — slower, more accurate (~540MB)
- Cohere Rerank API — managed, no local GPU required; requires `langchain-cohere` and a Cohere API key

---

### 11. Hybrid Search with EnsembleRetriever

```python
# hybrid_search_rag.py
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.retrievers import EnsembleRetriever, BM25Retriever
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

load_dotenv()

# Load and split documents
loader = TextLoader("knowledge_base.txt", encoding="utf-8")
documents = loader.load()
splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)
chunks = splitter.split_documents(documents)

# Dense retriever (semantic)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma.from_documents(chunks, embeddings)
dense_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# Sparse retriever (keyword / BM25)
# BM25Retriever requires: pip install rank_bm25
bm25_retriever = BM25Retriever.from_documents(chunks)
bm25_retriever.k = 5

# Combine with equal weight; adjust weights to bias toward one or the other
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, dense_retriever],
    weights=[0.4, 0.6],  # 40% BM25, 60% dense — tune for your data
)

llm = ChatOpenAI(model="gpt-4o", temperature=0)
RAG_PROMPT = """\
Answer the question using only the context provided.

Context:
{context}

Question: {question}

Answer:"""

prompt = ChatPromptTemplate.from_template(RAG_PROMPT)

rag_chain = (
    {
        "context": ensemble_retriever | (lambda docs: "\n\n".join(d.page_content for d in docs)),
        "question": RunnablePassthrough(),
    }
    | prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke("What is the recommended chunk_overlap for a 512-token chunk?")
print(answer)
```

Note: `BM25Retriever` requires `pip install rank_bm25`.

---

### 12. Agentic RAG — Retrieval as a Tool

In Modules 3 and 4 you built agents that call tools in a loop. Retrieval is just another tool. Treating it as one unlocks capabilities that a linear RAG pipeline cannot provide:

- The agent can choose *whether* to retrieve at all (sometimes the answer is already in its training data or a prior turn)
- The agent can retrieve multiple times with different queries to triangulate an answer
- The agent can combine retrieval with other tools (calculators, web search, database queries)
- The agent can verify that retrieved content is sufficient before answering

```python
# agentic_rag.py
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.tools.retriever import create_retriever_tool
from langchain import hub
from langgraph.prebuilt import create_react_agent

load_dotenv()

# ── 1. BUILD THE RETRIEVER ────────────────────────────────────────────────────
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# ── 2. WRAP RETRIEVER AS A TOOL ───────────────────────────────────────────────
# The description is what the agent uses to decide when to call this tool.
retrieval_tool = create_retriever_tool(
    retriever=retriever,
    name="search_knowledge_base",
    description=(
        "Search the knowledge base for information relevant to the user's question. "
        "Use this tool whenever you need factual information that you are not certain about. "
        "Input should be a search query string."
    ),
)

# ── 3. CONFIGURE THE AGENT ───────────────────────────────────────────────────
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# create_react_agent from langgraph builds a ReAct loop automatically
agent = create_react_agent(
    model=llm,
    tools=[retrieval_tool],
    prompt=(
        "You are a helpful assistant with access to a knowledge base. "
        "Always use the search_knowledge_base tool when you need specific factual information. "
        "If the retrieved information does not answer the question, say so rather than guessing."
    ),
)

# ── 4. INVOKE ─────────────────────────────────────────────────────────────────
response = agent.invoke({
    "messages": [{"role": "user", "content": "What chunking strategy works best for PDF documents?"}]
})
print(response["messages"][-1].content)
```

The agent will decide whether to invoke `search_knowledge_base`, how many times, and with what queries. If the question is clearly covered by training data (e.g., "what is Python?"), it may not retrieve at all, saving latency and cost.

**Extending agentic RAG:** Add more tools alongside retrieval — a `web_search` tool for current events, a `sql_query` tool for structured data, a `calculator` for numeric reasoning. The agent orchestrates all of them.

---

## Evaluating RAG Quality

You cannot improve what you cannot measure. RAG introduces two independent failure modes that must be measured separately: retrieval failure (the right documents were not returned) and generation failure (the right documents were returned but the LLM still got the answer wrong or hallucinated).

### 13. RAGAS: The Standard RAG Evaluation Framework

RAGAS (Retrieval Augmented Generation Assessment) provides a suite of reference-free metrics that use an LLM-as-judge approach. It can evaluate your system without requiring a hand-labelled ground-truth corpus (though having one improves precision).

#### Core Metrics

| Metric | What It Measures | Range | Failure Mode It Catches |
|---|---|---|---|
| **Faithfulness** | Proportion of response claims that are supported by the retrieved context | 0–1 | LLM hallucinating beyond retrieved context |
| **Answer Relevancy** | How directly the response addresses the user's question | 0–1 | LLM producing off-topic or over-broad answers |
| **Context Precision** | Whether the *most* relevant chunks are ranked first in the retrieved set | 0–1 | Retriever returning relevant docs but burying them |
| **Context Recall** | Whether retrieved context contains all the information needed for the correct answer | 0–1 | Retriever missing relevant documents entirely |

**Faithfulness** is the most critical metric for production safety. A faithfulness score below 0.8 typically means the LLM is augmenting or contradicting the context rather than summarising it — the defining symptom of hallucination in a RAG context.

#### Running RAGAS

```python
# evaluate_rag.py
from dotenv import load_dotenv
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

load_dotenv()

# Build an evaluation dataset.
# In production, collect these from real user queries + your pipeline's outputs.
samples = [
    SingleTurnSample(
        user_input="What is the recommended chunk size for factoid queries?",
        retrieved_contexts=[
            "For factoid queries (specific names, dates, short facts), "
            "chunk sizes of 256-512 tokens work best. "
            "Smaller chunks improve precision but increase the number of retrievals needed.",
            "Chunk overlap of 10-20% of the chunk size is recommended to prevent "
            "information loss at boundaries.",
        ],
        response=(
            "For factoid queries, a chunk size of 256-512 tokens is recommended. "
            "This size balances retrieval precision with sufficient context."
        ),
        reference=(
            "The recommended chunk size for factoid queries is 256-512 tokens."
        ),
    ),
    SingleTurnSample(
        user_input="Which vector store should I use for a startup with no ops team?",
        retrieved_contexts=[
            "Pinecone is a fully managed cloud vector database. "
            "It requires zero operational overhead and scales automatically.",
            "Chroma is an open-source vector database ideal for prototyping. "
            "It has a simple API but limited scalability.",
        ],
        response=(
            "For a startup without a dedicated ops team, Pinecone is the best choice "
            "because it is fully managed and requires no infrastructure work. "
            "Chroma is an alternative for prototypes."
        ),
        reference=(
            "Pinecone is recommended for startups without ops teams due to its "
            "fully managed nature and zero operational overhead."
        ),
    ),
]

dataset = EvaluationDataset(samples=samples)

# RAGAS uses an LLM internally to judge responses
results = evaluate(
    dataset=dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=ChatOpenAI(model="gpt-4o"),
    embeddings=OpenAIEmbeddings(model="text-embedding-3-small"),
)

print(results)
# Output: DataFrame with per-sample and aggregate scores for each metric
```

#### Interpreting Results and Acting on Them

| Low Score On | Root Cause | Fix |
|---|---|---|
| Faithfulness | LLM generating beyond context | Tighten the system prompt; increase temperature constraint; add a verification step |
| Answer Relevancy | LLM padding or going off-topic | Improve the RAG prompt; reduce temperature |
| Context Precision | Relevant chunks ranked too low | Add re-ranking (Section 10); tune retriever weights |
| Context Recall | Missing relevant documents | Increase `k`; try hybrid search; review chunking strategy |

---

## Common Pitfalls and How to Avoid Them

### Using different embedding models at index and query time

The vector space produced by `text-embedding-3-small` is completely different from `all-MiniLM-L6-v2`. If you index with one and query with the other, similarity scores are meaningless. Always store the model name alongside your index and assert it matches at query time.

### Chunk size mismatch with retrieval k

If your chunks are 2048 tokens each and you retrieve `k=5`, you are injecting 10,000 tokens into the context window. GPT-4o's 128k window can handle this, but GPT-4o-mini's 128k window will too — however, retrieval accuracy degrades with very large individual chunks. Keep chunks small (512 tokens) and retrieve more of them (`k=6–8`) rather than retrieving fewer large chunks.

### Not preserving metadata

When you load a PDF with `PyPDFLoader`, each page's `Document` carries `{"source": "report.pdf", "page": 3}`. If you strip metadata during custom processing, you lose the ability to cite sources and to apply metadata filters (e.g., "only search documents from Q4 2025"). Never drop metadata.

### Over-retrieval without re-ranking

Fetching `k=20` and passing all 20 chunks to the LLM floods the context with irrelevant text. Either apply re-ranking to cut to the top 5, or use `ContextualCompressionRetriever` to extract only the relevant sentences from each retrieved chunk.

### Embedding entire documents as single chunks

A 50-page document embedded as one vector will have very low cosine similarity to any specific question about its content — the embedding averages over all the document's topics. Always chunk before embedding.

### Evaluating only with toy examples

RAG systems often perform well on clean, simple test cases but fail on edge cases: short queries ("cost?"), multi-hop questions ("what changed between version 2 and version 3?"), and adversarial queries that don't match any document. Build a diverse evaluation set from real or realistic user queries before declaring a system production-ready.

---

## Putting It Together: Choosing the Right Configuration

| Scenario | Recommended Configuration |
|---|---|
| Proof of concept, solo developer | Recursive chunking (512 tokens) + `text-embedding-3-small` + Chroma (local) + GPT-4o-mini |
| Production, small team, no infra preference | Recursive chunking + `text-embedding-3-small` + Pinecone + GPT-4o |
| Production, existing PostgreSQL | Recursive chunking + `text-embedding-3-small` + pgvector + GPT-4o |
| High recall requirement on dense technical docs | Semantic chunking + `bge-base-en-v1.5` + Chroma + re-ranking + GPT-4o |
| Zero external API dependency | Recursive chunking + `all-MiniLM-L6-v2` + FAISS + local LLM (Ollama) |
| Multi-document, agentic, complex queries | Hybrid search + re-ranking + agentic RAG (retrieval as tool) + GPT-4o |

---

## Summary

RAG exists because LLMs cannot know everything and must not be trusted to guess. By separating *knowledge storage* (vector store) from *reasoning* (LLM), you get a system that is updatable without retraining, auditable by source, and far more accurate than a prompt-stuffed model.

The pipeline has seven stages — load, chunk, embed, store, retrieve, augment, generate — and meaningful decisions at each one. Chunking strategy and embedding model choice have the highest leverage on retrieval quality. Vector store choice is primarily a deployment and scaling decision. Advanced patterns (HyDE, multi-query, re-ranking, hybrid search) layer on top of a working baseline and should be adopted one at a time, measured with RAGAS after each change.

In Module 6, this RAG foundation will be extended into more complex agentic pipelines where retrieval combines with structured data access, long-term memory, and multi-agent coordination.

---

## Further Reading

1. **[Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks (Lewis et al., 2020)](https://arxiv.org/abs/2005.11401)** — The original RAG paper from Meta AI that introduced the architecture and showed dense passage retrieval outperforms parametric knowledge on open-domain QA.

2. **[RAGAS: Automated Evaluation of Retrieval Augmented Generation (Es et al., 2023)](https://arxiv.org/abs/2309.15217)** — The paper introducing the RAGAS evaluation framework; explains the mathematical formulation of faithfulness, answer relevancy, and context metrics.

3. **[LangChain RAG How-To Guides (Official Docs)](https://python.langchain.com/docs/how_to/#qa-with-rag)** — The canonical reference for LangChain's RAG components: document loaders, text splitters, retrievers, and LCEL chain composition patterns.

4. **[Best Chunking Strategies for RAG in 2025 (Firecrawl Blog)](https://www.firecrawl.dev/blog/best-chunking-strategies-rag)** — Practical benchmarks comparing seven chunking strategies across recall, cost, and complexity, with concrete size and overlap recommendations.

5. **[Vector Database Comparison: Pinecone vs Weaviate vs Qdrant vs FAISS vs Milvus vs Chroma (LiquidMetal AI)](https://liquidmetal.ai/casesAndBlogs/vector-comparison/)** — Side-by-side comparison of six vector stores covering persistence, scalability, cost, metadata filtering, and ideal team profiles.

6. **[Advanced RAG Techniques (Neo4j Blog)](https://neo4j.com/blog/genai/advanced-rag-techniques/)** — Covers 15 advanced RAG patterns including HyDE, CRAG, GraphRAG, re-ranking, and multi-step reasoning with discussion of when each is warranted.

7. **[Enhancing Retrieval-Augmented Generation: A Study of Best Practices (arXiv 2501.07391)](https://arxiv.org/abs/2501.07391)** — 2025 academic survey systematically evaluating the effect of chunk size, embedding model, retrieval strategy, and LLM choice on RAG pipeline quality.

8. **[MTEB Leaderboard — Massive Text Embedding Benchmark (Hugging Face)](https://huggingface.co/spaces/mteb/leaderboard)** — Live leaderboard ranking embedding models across retrieval, classification, clustering, and semantic textual similarity tasks; the standard reference for choosing an embedding model.
