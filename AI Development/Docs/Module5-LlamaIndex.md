# Module 5: LlamaIndex — Data-First RAG and Structured Retrieval
> Subject: AI Development | Difficulty: Intermediate | Estimated Time: 405 minutes

## Objective

After completing this module, you will be able to explain LlamaIndex's architecture and articulate how its data-first design philosophy differs from LangChain's chain-first approach. You will configure the global `Settings` object to run entirely locally using `Ollama` as the LLM backend and `OllamaEmbedding` or `HuggingFaceEmbedding` for embeddings, with no cloud API calls. You will understand the `Document` and `TextNode` data model and how node relationships enable advanced retrieval. You will build and persist `VectorStoreIndex` objects from local documents using `SimpleDirectoryReader` and `IngestionPipeline`, query them through both query engines and chat engines, and back them with ChromaDB as a persistent vector store. You will implement three advanced retrieval patterns: `SubQuestionQueryEngine` for complex multi-part queries, `RouterQueryEngine` for directing traffic between specialized indexes, and metadata filtering for targeted retrieval. By the end of this module you will have three fully working local LlamaIndex RAG systems and a clear decision framework for choosing between LlamaIndex and LangChain for a given project.

## Prerequisites

- Completed **Module 0: Setup & Local AI Stack** — Ollama is installed, running, and at least one model is pulled
- Completed **Module 1: Working with Local Models** — familiar with `ollama.chat()`, streaming, and inference parameters
- Completed **Module 2: Hugging Face & Local Models** — comfortable with the `transformers` ecosystem and `sentence-transformers`
- Completed **Module 3: LangChain Fundamentals** — familiar with RAG concepts, document loaders, and the retrieval chain pattern
- Completed **Module 4: RAG with LangChain** — solid understanding of the index-retrieve-augment-generate pipeline, Chroma, chunking strategies, and embedding model selection
- Python 3.10 or later with an active virtual environment
- The following models pulled via Ollama (run these before starting):
  ```bash
  ollama pull llama3.2
  ollama pull nomic-embed-text
  ```
- At least 8 GB of RAM and 4 GB of free disk space for index storage
- Comfort with Python type hints and dataclasses

---

## Key Concepts

### 1. What LlamaIndex Is and How It Differs from LangChain

LlamaIndex (formerly GPT Index) is an open-source data framework for building LLM applications. Its central design goal is to make connecting your private data to an LLM as easy and high-quality as possible. Every abstraction in LlamaIndex — documents, nodes, indexes, retrievers, query engines — exists to answer one question: **how do I get the right data to the LLM at query time?**

This stands in contrast to LangChain, which was built around **composability of LLM calls**. LangChain's primary metaphor is the chain: a sequence of prompt, model, and parser steps connected by the pipe operator. RAG is one use case LangChain supports, but its design makes it equally suited to agent workflows, tool calling, structured extraction, and multi-step reasoning pipelines.

The distinction is not that one is better than the other — they have different centres of gravity:

| Dimension | LlamaIndex | LangChain |
|---|---|---|
| **Design centre** | Data ingestion and retrieval quality | Composing LLM calls and agents |
| **Core metaphor** | Index over your data | Chain of runnable steps |
| **RAG support** | Deep — purpose-built, many index types, retrieval modes, re-rankers | Broad — full-featured but one of many use cases |
| **Agent support** | Good, via `AgentWorkflow` | Excellent — the primary use case for advanced chains |
| **Data connectors** | 160+ built-in readers (LlamaHub) | Broad via `langchain-community` loaders |
| **Configuration** | Global `Settings` singleton | Per-component constructor arguments |
| **Learning curve** | Moderate — new vocabulary (Nodes, Index, QueryEngine) | Moderate — new vocabulary (Runnables, LCEL, Chains) |
| **Local model support** | Excellent — first-class Ollama integration | Excellent — first-class Ollama integration |

#### When to Choose LlamaIndex

Choose LlamaIndex when:

- Your primary challenge is **data quality and retrieval quality** — you are working with large or complex document corpora and need fine-grained control over chunking, node metadata, and retrieval strategy.
- You need **multiple index types** — routing between a vector index for specific lookups and a summary index for broad questions about the same data.
- You are building a **document understanding** application — PDFs, structured data, tables, knowledge graphs — where LlamaIndex's rich reader ecosystem saves significant plumbing work.
- You want a **data-centric mental model** — where your data structures (documents, nodes) are first-class citizens rather than inputs to a chain.

Choose LangChain when:

- Your application requires **complex agent behavior** — multi-tool calling, conditional branching, LLM-driven routing across many tasks that go beyond document retrieval.
- You need **tight integration with the broader LangChain ecosystem** — LangSmith tracing, LangGraph workflows, or an existing codebase built on LCEL.
- RAG is **one component among many** in a pipeline that also includes structured extraction, tool calling, and conversation management.
- Your team is already familiar with LangChain's patterns and the cost of switching frameworks is not justified by retrieval quality gains.

In practice, the two libraries are not mutually exclusive. LlamaIndex can serve as the retrieval engine inside a LangChain chain, and advanced applications sometimes use both.

#### LlamaIndex Package Architecture

LlamaIndex adopted a split-package architecture. The framework is no longer a single `llama_index` package. Instead, it consists of a core package and separately installable integration packages:

```
llama-index-core               # Core abstractions: Settings, Document, Node, Index,
                               # QueryEngine, Retriever, ResponseSynthesizer, Storage
llama-index-llms-ollama        # Ollama LLM integration
llama-index-embeddings-ollama  # OllamaEmbedding integration
llama-index-embeddings-huggingface  # HuggingFaceEmbedding integration
llama-index-vector-stores-chroma    # ChromaVectorStore integration
llama-index-readers-file            # File readers including PyMuPDFReader
```

The current stable release as of April 2026 is `llama-index-core==0.14.20`, which requires Python 3.10 or later. This split architecture means you install only what you need. A project using Ollama and Chroma will not pull in unnecessary OpenAI or Pinecone dependencies.

---

### 2. Installation and Local Model Setup

**Install the required packages:**

```bash
pip install llama-index-core \
            llama-index-llms-ollama \
            llama-index-embeddings-ollama \
            llama-index-embeddings-huggingface \
            llama-index-vector-stores-chroma \
            llama-index-readers-file \
            chromadb \
            sentence-transformers
```

Pull the local models via Ollama:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

#### The `Settings` Object

LlamaIndex uses a global configuration singleton called `Settings`. It replaces the older `ServiceContext` pattern from LlamaIndex 0.9.x and earlier. Any component you build — indexes, query engines, retrievers — reads its defaults from `Settings` unless you explicitly override them at the component level.

You must configure `Settings` **before** creating any indexes or query engines. Configuring it after the fact has no effect on objects already instantiated.

```python
from llama_index.core import Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

# Configure the LLM — all query engines will use this by default
Settings.llm = Ollama(
    model="llama3.2",
    base_url="http://localhost:11434",
    request_timeout=120.0,   # seconds — increase for slower hardware
    context_window=8192,     # must match or be within the model's actual context window
)

# Configure the embedding model — all indexes will use this for embedding
Settings.embed_model = OllamaEmbedding(
    model_name="nomic-embed-text",
    base_url="http://localhost:11434",
    embed_batch_size=10,     # number of texts embedded per Ollama API call
)

# Configure chunking defaults — applies to the default SentenceSplitter
# used by VectorStoreIndex.from_documents()
Settings.chunk_size = 512        # tokens (not characters — LlamaIndex uses token counts)
Settings.chunk_overlap = 50      # tokens shared between adjacent chunks
```

**Using HuggingFaceEmbedding instead of OllamaEmbedding:**

If you prefer fully offline embeddings that do not depend on the Ollama server, use `HuggingFaceEmbedding`. The model downloads from Hugging Face Hub on first use and is cached locally thereafter.

```python
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-base-en-v1.5",  # 768 dimensions, strong retrieval quality
    # Alternative: "all-MiniLM-L6-v2"    # 384 dimensions, very fast, smaller
)
```

> **Critical:** LlamaIndex's `chunk_size` and `chunk_overlap` are measured in **tokens**, not characters. This is different from LangChain's `RecursiveCharacterTextSplitter`, which operates in characters. A `chunk_size=512` in LlamaIndex is approximately 2000 characters for English prose — roughly four times larger than the same number in LangChain. Keep this in mind when translating settings between the two frameworks.

---

### 3. Core Concepts: Documents, Nodes, Indexes, and Query Engines

#### Documents and Nodes

The fundamental data unit in LlamaIndex is the **Document** — a raw piece of content loaded from a source file, web page, or database. A `Document` object holds the text content and a metadata dictionary.

```python
from llama_index.core.schema import Document

# Create a document manually
doc = Document(
    text="LlamaIndex is a data framework for building LLM applications.",
    metadata={
        "source": "readme.md",
        "category": "technical",
        "version": "0.14",
    }
)

print(doc.doc_id)        # auto-generated UUID
print(doc.text)
print(doc.metadata)
```

After loading and chunking, documents become **Nodes** (`TextNode`). A node is a chunk of a document, and it maintains a relationship back to its source document and to adjacent nodes (previous, next). These relationships enable advanced retrieval patterns where you can expand retrieved nodes to include their neighbors for more context.

```python
from llama_index.core.schema import TextNode, NodeRelationship, RelatedNodeInfo

# A TextNode is what the index actually stores and retrieves
node = TextNode(
    text="LlamaIndex uses a global Settings object for configuration.",
    metadata={"source": "docs.md", "page": 3},
)

# Nodes store relationships: source document, previous node, next node
# These are set automatically by node parsers; shown here for illustration
node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
    node_id="parent-doc-uuid",
    metadata={"source": "docs.md"},
)

print(node.node_id)       # UUID
print(node.get_content())
print(node.metadata)
```

In practice, you rarely create nodes manually. Loaders and node parsers create them automatically during ingestion.

#### Index Types

An **index** in LlamaIndex is a data structure that organises nodes for efficient retrieval. There are three primary index types:

**`VectorStoreIndex`** — the most common index. Embeds each node into a vector and stores the vectors. At query time, the query is embedded and the k most similar nodes are retrieved. Best for: precise semantic lookup — "what does the documentation say about X?" — and all RAG applications where the answer is contained in a specific subset of documents.

**`SummaryIndex`** (formerly `ListIndex`) — stores nodes as a simple ordered list without embedding them. At query time, either all nodes are sent to the LLM (expensive) or a subset is selected. Best for: broad summarisation questions — "summarise this entire document" or "what are the main themes across all files?" — where you want the LLM to reason over the whole corpus rather than a retrieved subset.

**`KeywordTableIndex`** — builds a keyword-to-node mapping. At query time, keywords are extracted from the query and matched to nodes containing those keywords. Best for: exact keyword lookup, structured data sources where semantic similarity is less useful, or as a complementary index in a router setup.

```python
from llama_index.core import VectorStoreIndex, SummaryIndex, KeywordTableIndex
from llama_index.core.schema import Document

docs = [Document(text="Python is a high-level programming language.")]

# VectorStoreIndex — embeds nodes, enables semantic similarity search
vector_index = VectorStoreIndex.from_documents(docs)

# SummaryIndex — retains all nodes as a list for full-document reasoning
summary_index = SummaryIndex.from_documents(docs)

# KeywordTableIndex — builds keyword-to-node mapping
keyword_index = KeywordTableIndex.from_documents(docs)
```

#### Query Engines

A **query engine** is the interface for asking a one-off question to an index. It combines a retriever (to fetch relevant nodes) and a response synthesizer (to produce an answer from those nodes). The simplest way to create one is `index.as_query_engine()`.

```python
# Default query engine — retrieves top-2 nodes, synthesizes a response
query_engine = vector_index.as_query_engine()
response = query_engine.query("What is Python?")
print(str(response))
print(response.source_nodes)  # the retrieved TextNode objects that produced the answer
```

**Query engine parameters:**

```python
query_engine = vector_index.as_query_engine(
    similarity_top_k=4,           # number of nodes to retrieve
    response_mode="compact",      # response synthesizer mode (see Section 3.5)
    streaming=True,               # stream the response token by token
)

# With streaming, iterate over the response stream
streaming_response = query_engine.query("Explain chunking in LlamaIndex.")
for token in streaming_response.response_gen:
    print(token, end="", flush=True)
print()
```

#### Retrievers

A **retriever** separates the retrieval step from response synthesis. Use `index.as_retriever()` when you want to inspect or post-process the retrieved nodes before generating a response.

```python
retriever = vector_index.as_retriever(
    similarity_top_k=4,   # return the 4 most similar nodes
)

nodes = retriever.retrieve("How does chunking work?")
for node in nodes:
    print(f"Score: {node.score:.4f}")
    print(f"Text: {node.text[:120]}")
    print(f"Source: {node.metadata.get('source', 'unknown')}")
    print()
```

The returned objects are `NodeWithScore` — they carry both the `TextNode` and a similarity score. A score of 1.0 is a perfect match; scores below 0.5 are typically irrelevant.

#### Response Synthesizers

A **response synthesizer** takes a query and a list of retrieved nodes and uses the LLM to produce a final answer. The `response_mode` parameter controls the synthesis strategy:

| Mode | How it works | Best when |
|---|---|---|
| `compact` | Packs as many nodes as fit in the context window into one prompt. Falls back to refine if the content is too large. | Default — best balance of quality and latency for most RAG tasks. |
| `refine` | Generates an initial answer from the first node, then iteratively refines by passing the answer and next node to the LLM. Makes N LLM calls for N nodes. | Corpus is large and you need the answer to incorporate information from all nodes, not just the most similar one. |
| `tree_summarize` | Builds a tree of LLM calls — generates summaries of groups of nodes, then summarises those summaries recursively until one answer remains. | Broad summarisation questions where the answer must reflect the whole retrieved set, not just the first node. |
| `simple_summarize` | Concatenates all nodes into a single prompt and calls the LLM once. Fails if content exceeds context window. | Small retrievals (2–3 short nodes) where you want minimum latency. |
| `no_text` | Returns retrieved nodes without calling the LLM. | Debugging retrieval quality or building custom downstream processing. |

```python
from llama_index.core.response_synthesizers import ResponseMode

# Explicitly set the response mode
query_engine = vector_index.as_query_engine(
    similarity_top_k=4,
    response_mode=ResponseMode.COMPACT,   # or "compact" as a string
)
```

---

### 4. Data Ingestion

#### SimpleDirectoryReader

`SimpleDirectoryReader` is LlamaIndex's built-in file loader. It walks a directory and loads all supported files, returning a list of `Document` objects. Supported formats include `.txt`, `.md`, `.pdf`, `.docx`, `.pptx`, `.csv`, `.html`, `.epub`, and more. PDF loading requires the `pypdf` or `pymupdf` package.

```bash
pip install pypdf
```

```python
from llama_index.core import SimpleDirectoryReader

# Load all supported files from a directory (recursive)
documents = SimpleDirectoryReader(
    input_dir="./my_docs",
    recursive=True,                          # traverse subdirectories
    required_exts=[".txt", ".md", ".pdf"],   # only load these extensions
    filename_as_id=True,                     # use the filename as the Document ID
).load_data()

print(f"Loaded {len(documents)} documents")
for doc in documents[:3]:
    print(f"  Source: {doc.metadata.get('file_name')}")
    print(f"  Size: {len(doc.text)} characters")
```

**Automatic metadata extraction:** `SimpleDirectoryReader` populates metadata with `file_name`, `file_path`, `file_type`, `file_size`, and `creation_date` automatically. You can add custom metadata via a `file_metadata` callable:

```python
import os

def get_custom_metadata(filepath: str) -> dict:
    """Add custom metadata to every loaded document."""
    return {
        "category": "technical" if "docs" in filepath else "reference",
        "indexed_date": "2026-04-16",
    }

documents = SimpleDirectoryReader(
    input_dir="./my_docs",
    file_metadata=get_custom_metadata,
).load_data()
```

**Loading specific files instead of a directory:**

```python
documents = SimpleDirectoryReader(
    input_files=["./report.pdf", "./notes.md", "./faq.txt"]
).load_data()
```

#### Node Parsers: SentenceSplitter and TokenTextSplitter

Before nodes reach the index, documents are split by a **node parser**. The default is `SentenceSplitter`, which splits on sentence boundaries and respects `Settings.chunk_size` and `Settings.chunk_overlap`.

```python
from llama_index.core.node_parser import SentenceSplitter, TokenTextSplitter
from llama_index.core import SimpleDirectoryReader

documents = SimpleDirectoryReader("./my_docs").load_data()

# SentenceSplitter — respects sentence boundaries, recommended default
splitter = SentenceSplitter(
    chunk_size=512,       # maximum tokens per chunk
    chunk_overlap=50,     # token overlap between consecutive chunks
    paragraph_separator="\n\n",   # how to detect paragraph breaks
)

nodes = splitter.get_nodes_from_documents(documents)
print(f"Split {len(documents)} documents into {len(nodes)} nodes")
print(f"Sample node text: {nodes[0].text[:200]}")

# TokenTextSplitter — hard token-count split without sentence awareness
# Useful when documents have no natural sentence structure (e.g., code, CSV rows)
token_splitter = TokenTextSplitter(
    chunk_size=512,
    chunk_overlap=50,
)
nodes = token_splitter.get_nodes_from_documents(documents)
```

#### IngestionPipeline

`IngestionPipeline` is a structured way to define a sequence of transformations applied to documents before they reach an index. It handles deduplication (will not re-process a document with the same hash), optional caching, and direct insertion into a vector store.

```python
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding

embed_model = OllamaEmbedding(
    model_name="nomic-embed-text",
    base_url="http://localhost:11434",
)

pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=512, chunk_overlap=50),
        embed_model,   # embeddings are computed as part of the pipeline
    ]
)

# Run the pipeline — returns a list of nodes with embeddings attached
nodes = pipeline.run(documents=documents)
print(f"Pipeline produced {len(nodes)} embedded nodes")

# Persist the pipeline cache to disk so re-runs skip already-processed documents
pipeline.persist("./pipeline_cache")

# On subsequent runs, load the cache to avoid re-embedding unchanged documents
pipeline_with_cache = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=512, chunk_overlap=50),
        embed_model,
    ],
)
pipeline_with_cache.load("./pipeline_cache")
```

---

### 5. Building RAG with LlamaIndex

#### Simple RAG: From Documents to Answers

The shortest path from a directory of files to a working Q&A system in LlamaIndex is three lines of meaningful code:

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

# 1. Configure Settings (must come before creating any index)
Settings.llm = Ollama(model="llama3.2", request_timeout=120.0, context_window=8192)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
Settings.chunk_size = 512
Settings.chunk_overlap = 50

# 2. Load documents
documents = SimpleDirectoryReader("./my_docs").load_data()

# 3. Build the index (splits, embeds, and stores nodes automatically)
index = VectorStoreIndex.from_documents(documents)

# 4. Query
query_engine = index.as_query_engine(similarity_top_k=4)
response = query_engine.query("What topics are covered in these documents?")
print(str(response))
```

`VectorStoreIndex.from_documents()` applies the `Settings.chunk_size` and `Settings.chunk_overlap` via the default `SentenceSplitter`, embeds each node with `Settings.embed_model`, and stores everything in an in-memory vector store. The `query()` call embeds the question, retrieves the top-4 nodes, and synthesizes an answer with `Settings.llm`.

#### Persisting and Loading Indexes

By default, `VectorStoreIndex.from_documents()` stores nodes in memory. When your process exits, the index is lost. Use `storage_context.persist()` to write the index to disk and `load_index_from_storage()` to reload it.

```python
import os
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    load_index_from_storage,
    Settings,
)
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

PERSIST_DIR = "./storage"

Settings.llm = Ollama(model="llama3.2", request_timeout=120.0, context_window=8192)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

if not os.path.exists(PERSIST_DIR):
    # First run: build the index from documents and persist it
    documents = SimpleDirectoryReader("./my_docs").load_data()
    index = VectorStoreIndex.from_documents(documents)
    index.storage_context.persist(persist_dir=PERSIST_DIR)
    print(f"Index built and saved to {PERSIST_DIR}")
else:
    # Subsequent runs: reload from disk — no re-embedding
    storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
    index = load_index_from_storage(storage_context)
    print(f"Index loaded from {PERSIST_DIR}")

query_engine = index.as_query_engine(similarity_top_k=4)
response = query_engine.query("What are the main topics covered?")
print(str(response))
```

> **Important:** The default `persist()` stores nodes, the vector index, and the document store in JSON files on disk. This format uses LlamaIndex's built-in `SimpleVectorStore`. For larger corpora or production use, replace the built-in store with ChromaDB (see below).

#### Using ChromaDB as the Vector Store Backend

Swapping the default in-memory vector store for ChromaDB gives you a persistent, query-efficient vector database backed by a proper storage layer. The storage context wires the `ChromaVectorStore` into the index.

```bash
pip install llama-index-vector-stores-chroma chromadb
```

```python
import chromadb
from llama_index.core import VectorStoreIndex, StorageContext, SimpleDirectoryReader, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
import os

CHROMA_PATH = "./chroma_llamaindex"
COLLECTION_NAME = "my_documents"

Settings.llm = Ollama(model="llama3.2", request_timeout=120.0, context_window=8192)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

# Create a persistent Chroma client and collection
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)

# Wrap the Chroma collection in LlamaIndex's ChromaVectorStore
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

# Build the storage context using the Chroma vector store
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# Check if the collection already has data to avoid re-indexing
if chroma_collection.count() == 0:
    print("Collection is empty — indexing documents...")
    documents = SimpleDirectoryReader("./my_docs").load_data()
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
    )
    print(f"Indexed {chroma_collection.count()} vectors")
else:
    print(f"Loading existing collection ({chroma_collection.count()} vectors)")
    index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )

query_engine = index.as_query_engine(similarity_top_k=4)
response = query_engine.query("What does this documentation cover?")
print(str(response))
```

#### Streaming Responses

To stream tokens to the terminal as they are generated, set `streaming=True` on the query engine and iterate over `response_gen`:

```python
query_engine = index.as_query_engine(
    similarity_top_k=4,
    streaming=True,
)

streaming_response = query_engine.query("Explain the key architecture decisions.")
print("Answer: ", end="", flush=True)
for token in streaming_response.response_gen:
    print(token, end="", flush=True)
print()
```

Alternatively, use the convenience method that handles the iteration for you:

```python
streaming_response = query_engine.query("What are the best practices described?")
streaming_response.print_response_stream()
```

#### Conversational RAG with the Chat Engine

`index.as_chat_engine()` wraps the index in a stateful chat interface. It maintains conversation history across turns and rewrites each new message to include prior context before retrieval — a pattern called **condense-and-query**.

```python
chat_engine = index.as_chat_engine(
    chat_mode="condense_question",  # rewrites follow-up questions using history
    verbose=True,                   # shows the rewritten query in the terminal
    similarity_top_k=4,
)

# First turn
response = chat_engine.chat("What is the main topic of these documents?")
print(f"Assistant: {str(response)}\n")

# Follow-up — the engine rewrites "Tell me more" using the prior exchange
response = chat_engine.chat("Tell me more about the second point.")
print(f"Assistant: {str(response)}\n")

# Reset conversation history
chat_engine.reset()

# Streaming chat
streaming_response = chat_engine.stream_chat("What are the key conclusions?")
print("Assistant: ", end="", flush=True)
for token in streaming_response.response_gen:
    print(token, end="", flush=True)
print()
```

**Chat modes available:**

| Mode | Behaviour |
|---|---|
| `condense_question` | Rewrites follow-up questions using history before retrieval. Single retrieval call per turn. |
| `context` | Retrieves context for every turn independently. Maintains history in the system prompt. |
| `condense_plus_context` | Combines both: rewrites the question and then retrieves fresh context. Best quality. |
| `simple` | No retrieval — pure conversational LLM with no document access. |
| `best` | Alias for `condense_plus_context`. |

---

### 6. Advanced LlamaIndex Features

#### Sub-Question Query Engine

The `SubQuestionQueryEngine` is designed for complex, multi-part questions that require information from different parts of a corpus. Instead of sending the original question directly to a retriever, it first asks the LLM to decompose the question into targeted sub-questions, sends each sub-question to the appropriate query engine, and then synthesizes all sub-answers into a final response.

This is valuable when a question like "How do the authentication and logging subsystems interact, and which one is more likely to cause performance issues?" requires retrieving from two semantically distinct parts of the codebase.

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.query_engine import SubQuestionQueryEngine
from llama_index.core.callbacks import CallbackManager, LlamaDebugHandler
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

Settings.llm = Ollama(model="llama3.2", request_timeout=120.0, context_window=8192)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

# Enable debug logging to see the generated sub-questions
llama_debug = LlamaDebugHandler(print_trace_on_end=True)
Settings.callback_manager = CallbackManager([llama_debug])

# Build two separate indexes for two documents/topics
docs_architecture = SimpleDirectoryReader(
    input_files=["./docs/architecture.md"]
).load_data()
docs_performance = SimpleDirectoryReader(
    input_files=["./docs/performance.md"]
).load_data()

arch_index = VectorStoreIndex.from_documents(docs_architecture)
perf_index = VectorStoreIndex.from_documents(docs_performance)

# Wrap each query engine as a named tool with a description
# The description is what the LLM reads to decide which tool to use
tools = [
    QueryEngineTool(
        query_engine=arch_index.as_query_engine(similarity_top_k=3),
        metadata=ToolMetadata(
            name="architecture_docs",
            description="Contains system architecture decisions, component design, "
                        "and module relationships for this application.",
        ),
    ),
    QueryEngineTool(
        query_engine=perf_index.as_query_engine(similarity_top_k=3),
        metadata=ToolMetadata(
            name="performance_docs",
            description="Contains performance benchmarks, profiling results, "
                        "and optimization recommendations.",
        ),
    ),
]

sub_question_engine = SubQuestionQueryEngine.from_defaults(
    query_engine_tools=tools,
    use_async=False,    # set True if running in an async context (e.g., FastAPI)
    verbose=True,       # print sub-questions and intermediate answers
)

response = sub_question_engine.query(
    "How does the authentication module affect overall system performance?"
)
print(str(response))
```

#### RouterQueryEngine

`RouterQueryEngine` directs each incoming query to one of several query engines based on the query content. The **selector** is an LLM call that reads the query and tool descriptions and chooses the most appropriate engine.

This is the right pattern when you have fundamentally different data sources or index types — for example, a vector index for specific factual lookups and a summary index for broad document summarisation — and you want a single entry point that routes intelligently.

```python
from llama_index.core import VectorStoreIndex, SummaryIndex, SimpleDirectoryReader, Settings
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector
from llama_index.core.tools import QueryEngineTool
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

Settings.llm = Ollama(model="llama3.2", request_timeout=120.0, context_window=8192)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

documents = SimpleDirectoryReader("./my_docs").load_data()

# Build two indexes over the same documents — a vector index and a summary index
vector_index = VectorStoreIndex.from_documents(documents)
summary_index = SummaryIndex.from_documents(documents)

# Create QueryEngineTool wrappers with descriptive names
vector_tool = QueryEngineTool.from_defaults(
    query_engine=vector_index.as_query_engine(similarity_top_k=4),
    description=(
        "Useful for answering specific, factual questions about the documents. "
        "Use this when the query asks about a specific detail, definition, or procedure."
    ),
)

summary_tool = QueryEngineTool.from_defaults(
    query_engine=summary_index.as_query_engine(response_mode="tree_summarize"),
    description=(
        "Useful for summarising or providing a broad overview of the documents. "
        "Use this when the query asks for a summary, overview, or 'main points'."
    ),
)

# LLMSingleSelector: the LLM reads the descriptions and picks one tool
router_engine = RouterQueryEngine(
    selector=LLMSingleSelector.from_defaults(),
    query_engine_tools=[vector_tool, summary_tool],
    verbose=True,   # shows which tool was selected and why
)

# This specific question should route to the vector tool
response = router_engine.query("What does the configuration file contain?")
print(str(response))

# This broad question should route to the summary tool
response = router_engine.query("Give me a high-level summary of all the documents.")
print(str(response))
```

#### Metadata Filtering

Metadata filtering lets you scope retrieval to nodes that match specific metadata criteria, without changing the semantic similarity calculation. This is useful when your index contains documents from different sources, time periods, or categories and you want to restrict a query to a specific subset.

```python
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores import (
    MetadataFilter,
    MetadataFilters,
    FilterOperator,
    FilterCondition,
)
from llama_index.core.schema import TextNode

# Build an index with nodes that have metadata
nodes = [
    TextNode(
        text="Python 3.12 introduces a new type parameter syntax.",
        metadata={"category": "release_notes", "version": "3.12", "year": 2023},
    ),
    TextNode(
        text="The walrus operator := was introduced in Python 3.8.",
        metadata={"category": "language_features", "version": "3.8", "year": 2019},
    ),
    TextNode(
        text="Python 3.11 is significantly faster than 3.10.",
        metadata={"category": "release_notes", "version": "3.11", "year": 2022},
    ),
    TextNode(
        text="f-strings provide fast, readable string interpolation.",
        metadata={"category": "language_features", "version": "3.6", "year": 2016},
    ),
]

index = VectorStoreIndex(nodes)

# Filter: only retrieve nodes from the "release_notes" category
filters = MetadataFilters(
    filters=[
        MetadataFilter(
            key="category",
            value="release_notes",
            operator=FilterOperator.EQ,
        )
    ]
)

retriever = index.as_retriever(filters=filters, similarity_top_k=3)
results = retriever.retrieve("What changed in recent Python versions?")
for node in results:
    print(f"Version: {node.metadata['version']} | {node.text[:80]}")

# Compound filter: release notes from 2022 or later
recent_filters = MetadataFilters(
    filters=[
        MetadataFilter(key="category", value="release_notes", operator=FilterOperator.EQ),
        MetadataFilter(key="year", value=2021, operator=FilterOperator.GT),
    ],
    condition=FilterCondition.AND,
)

retriever = index.as_retriever(filters=recent_filters, similarity_top_k=3)
results = retriever.retrieve("What is new in Python?")
for node in results:
    print(f"Year {node.metadata['year']}: {node.text[:80]}")
```

**Available `FilterOperator` values:** `EQ` (equals), `NE` (not equals), `GT` (greater than), `GTE` (greater than or equal), `LT` (less than), `LTE` (less than or equal), `IN` (value in list), `NIN` (value not in list), `CONTAINS` (substring match).

#### Re-ranking

After retrieval, nodes can be re-ranked to improve the final ordering before synthesis. Re-ranking is useful when the initial embedding similarity scores are not fully reliable — for example, when the embedding model does not perfectly capture the semantics of the query for a specialised domain.

LlamaIndex provides `SentenceTransformerRerank` from the `llama-index-postprocessor-sentence-transformer-rerank` package:

```bash
pip install llama-index-postprocessor-sentence-transformer-rerank
```

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.postprocessor.sentence_transformer_rerank import SentenceTransformerRerank
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

Settings.llm = Ollama(model="llama3.2", request_timeout=120.0, context_window=8192)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

documents = SimpleDirectoryReader("./my_docs").load_data()
index = VectorStoreIndex.from_documents(documents)

# Fetch more candidates than needed (8), then re-rank and keep the best 3
reranker = SentenceTransformerRerank(
    model="cross-encoder/ms-marco-MiniLM-L-2-v2",  # local cross-encoder re-ranker
    top_n=3,   # keep the top 3 after re-ranking
)

query_engine = index.as_query_engine(
    similarity_top_k=8,               # initial retrieval: broad net
    node_postprocessors=[reranker],   # re-rank and filter to top 3
)

response = query_engine.query("What are the most important configuration options?")
print(str(response))
```

The re-ranker uses a cross-encoder model that directly scores each (query, node) pair — a more accurate but slower scoring method than the bi-encoder embeddings used for initial retrieval. Fetching 8 candidates and re-ranking to 3 is a common production pattern: the initial retrieval is fast, and the re-ranker does precision work on a small set.

---

### 7. LlamaIndex vs LangChain for RAG — Detailed Comparison

The following table is a detailed side-by-side comparison for RAG-specific tasks. Both frameworks are capable; the right choice depends on which capabilities your project prioritises.

| Capability | LlamaIndex | LangChain |
|---|---|---|
| **Ingestion pipeline** | `IngestionPipeline` with transformations, built-in deduplication, pipeline caching | Manual chain: loader → splitter → embedder → store; no built-in deduplication |
| **Index types** | `VectorStoreIndex`, `SummaryIndex`, `KeywordTableIndex`, `PropertyGraphIndex` | Single index type per vector store (all use `similarity_search`); no summary or keyword index |
| **Retrieval modes** | Similarity, MMR (via vector store), metadata filter, auto-retrieval | Similarity, MMR, similarity threshold, metadata filter |
| **Response synthesis** | Built-in `compact`, `refine`, `tree_summarize`, `simple_summarize`, `no_text` | Equivalent: `create_stuff_documents_chain` (compact), `create_refine_documents_chain` (refine); no tree summarize |
| **Routing** | `RouterQueryEngine` with `LLMSingleSelector`, `PydanticSingleSelector`, `PydanticMultiSelector` | `EnsembleRetriever` for hybrid retrieval; no native routing across index types |
| **Sub-question decomposition** | `SubQuestionQueryEngine` built-in | Not built-in; requires custom LCEL + agent logic |
| **Streaming** | `streaming=True` on `as_query_engine()` or `stream_chat()` on chat engine | LCEL `.stream()` on any chain; `ChatOllama` streams natively |
| **Chat engine** | `index.as_chat_engine()` with built-in history management and condense modes | `RunnableWithMessageHistory` wrapping a RAG chain; more setup required |
| **Re-ranking** | `node_postprocessors=[SentenceTransformerRerank(...)]` | `ContextualCompressionRetriever` with `LLMChainExtractor`; no cross-encoder re-ranker built-in |
| **Persistence (default)** | `index.storage_context.persist(dir)` / `load_index_from_storage(context)` | `Chroma(persist_directory=...)` auto-persists; `FAISS.save_local()` / `load_local()` |
| **ChromaDB integration** | `ChromaVectorStore(chroma_collection=...)` → `StorageContext` | `Chroma.from_documents(...)` or `Chroma(collection_name=..., persist_directory=...)` |
| **Local model support** | Excellent — `llama-index-llms-ollama`, `llama-index-embeddings-ollama` | Excellent — `langchain-ollama` package |
| **Agent support** | `AgentWorkflow` (newer), `ReActAgent` — good but secondary to retrieval | LangGraph, LCEL agents — primary use case, more mature tooling |
| **Data readers** | 160+ built-in readers (PDF, web, SQL, Notion, Slack, GitHub, etc.) via LlamaHub | `langchain-community` loaders — broad coverage, community-maintained |
| **Learning curve** | Moderate — new vocabulary (Nodes, StorageContext, ResponseSynthesizer) | Moderate — new vocabulary (Runnables, LCEL, invoke/stream/batch) |
| **Observability** | `LlamaDebugHandler`, `CallbackManager`; integrates with LlamaTrace | LangSmith — more mature; LangFuse for open-source option |

**Practical decision guidance:**

Use **LlamaIndex** when:
- Data ingestion quality and retrieval precision are the primary challenge
- You need multiple index types (vector + summary) or routing between them
- You want built-in sub-question decomposition or tree summarisation
- Your team thinks in terms of data structures (documents, nodes, metadata) rather than chains

Use **LangChain** when:
- You need complex agent behavior with tool calling, branching, and multi-step reasoning
- Your application is already built on LangChain and LangSmith tracing is integrated
- RAG is one component in a larger pipeline that includes structured extraction, tool use, or dynamic workflows
- You need LangGraph for stateful multi-agent workflows

---

## Best Practices

1. **Configure `Settings` before creating any indexes.** `Settings` is read at index construction time, not at query time. If you configure `Settings.embed_model` after calling `VectorStoreIndex.from_documents()`, the index was built with a default (OpenAI) embedding model — likely causing an import error if the OpenAI package is not installed, or silently producing wrong embeddings.

2. **Use the same embedding model for both indexing and querying, always.** This is the single most common and hardest-to-debug error in any RAG system. If you build an index with `nomic-embed-text` (768 dimensions) and load it with `HuggingFaceEmbedding("all-MiniLM-L6-v2")` (384 dimensions), every query returns meaningless results with no error message. Store the embedding model name alongside your index in a config file.

3. **Use `chromadb.PersistentClient` instead of the default `SimpleVectorStore` for any corpus larger than a few hundred documents.** The default JSON-based persistence is not designed for large corpora — it loads everything into memory and serializes slowly. ChromaDB scales to millions of vectors with efficient on-disk storage.

4. **Match `chunk_size` to your LLM's context window.** LlamaIndex's `chunk_size` is in tokens. With `similarity_top_k=4` and `chunk_size=512`, you are using ~2048 tokens of context before the question and answer overhead. A `context_window=8192` on the Ollama LLM gives you headroom. If you raise `chunk_size` to 1024 with `top_k=8`, you need `context_window=16384` — or a model that supports it.

5. **Use `response_mode="compact"` as your default.** It packs as many retrieved nodes into a single LLM call as the context window allows, falling back to iterative refinement only when necessary. It is the best trade-off between quality, latency, and token usage.

6. **Set `request_timeout` appropriately for your hardware.** The default Ollama timeout is 30 seconds. On machines generating 5–10 tokens/second with a large context window, a single query can take 60–120 seconds. Set `Ollama(request_timeout=120.0)` at minimum, and higher for slower hardware or complex queries.

7. **Use `IngestionPipeline` for production indexing workflows.** It provides document-level deduplication by content hash — re-running the pipeline on an updated corpus only processes changed documents, saving significant embedding time. The `pipeline.persist()` / `pipeline.load()` pattern makes incremental indexing straightforward.

8. **Inspect `response.source_nodes` to debug retrieval quality.** When a query produces a wrong or incomplete answer, check `response.source_nodes` to determine whether retrieval failed (wrong nodes returned) or synthesis failed (correct nodes, wrong answer). They require different fixes: retrieval failure calls for tuning `similarity_top_k`, `chunk_size`, or the embedding model; synthesis failure calls for tuning the response mode or LLM temperature.

9. **Use `verbose=True` on `RouterQueryEngine` and `SubQuestionQueryEngine` during development.** These engines make LLM calls internally to decide routing and decomposition. `verbose=True` logs those intermediate decisions to the terminal, making it easy to verify the engine is routing correctly and generating reasonable sub-questions.

10. **For `as_chat_engine()`, prefer `chat_mode="condense_plus_context"` over `"condense_question"` for best quality.** The `condense_question` mode rewrites the question but only retrieves context once. `condense_plus_context` rewrites the question and retrieves fresh context on every turn, producing more accurate follow-up responses at the cost of one additional retrieval call per turn.

---

## Hands-On Examples

### Example 1: Local Document Q&A with Persistence and ChromaDB

This example builds a fully persistent local document Q&A system using `SimpleDirectoryReader`, `VectorStoreIndex`, ChromaDB, and Ollama. The index is built once and reloaded on subsequent runs — no re-embedding.

**Step 1: Install dependencies and pull models**

```bash
pip install llama-index-core llama-index-llms-ollama llama-index-embeddings-ollama \
            llama-index-vector-stores-chroma chromadb
ollama pull llama3.2
ollama pull nomic-embed-text
```

**Step 2: Create a `./my_docs` directory** with a few `.txt` or `.md` files containing text you want to query.

**Step 3: Create the script**

```python
# example1_local_qa.py

"""
Local document Q&A using LlamaIndex + ChromaDB + Ollama.
Builds the index once and reloads from ChromaDB on subsequent runs.
No cloud API calls. All processing is local.

Usage:
    python example1_local_qa.py --build     # (re)build the index
    python example1_local_qa.py             # query an existing index
"""

import argparse
import sys

import chromadb
from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore

# ── Configuration ─────────────────────────────────────────────────────────────
DOCS_DIR = "./my_docs"
CHROMA_PATH = "./chroma_example1"
COLLECTION_NAME = "local_docs"
LLM_MODEL = "llama3.2"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
TOP_K = 4


def configure_settings() -> None:
    """Set global LlamaIndex Settings before building or loading any index."""
    Settings.llm = Ollama(
        model=LLM_MODEL,
        base_url="http://localhost:11434",
        request_timeout=120.0,
        context_window=8192,
    )
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url="http://localhost:11434",
    )
    Settings.chunk_size = CHUNK_SIZE
    Settings.chunk_overlap = CHUNK_OVERLAP


def get_chroma_store() -> tuple:
    """Return (ChromaVectorStore, chroma_collection, StorageContext)."""
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return vector_store, chroma_collection, storage_context


def build_index() -> VectorStoreIndex:
    """Load documents from DOCS_DIR, index them into ChromaDB, return the index."""
    import os
    if not os.path.isdir(DOCS_DIR):
        print(f"ERROR: Directory '{DOCS_DIR}' does not exist.")
        print("Create it and add .txt or .md files before indexing.")
        sys.exit(1)

    print(f"Loading documents from {DOCS_DIR}...")
    documents = SimpleDirectoryReader(
        input_dir=DOCS_DIR,
        recursive=True,
        required_exts=[".txt", ".md"],
    ).load_data()

    if not documents:
        print(f"ERROR: No .txt or .md files found in '{DOCS_DIR}'.")
        sys.exit(1)

    print(f"Loaded {len(documents)} documents")

    vector_store, chroma_collection, storage_context = get_chroma_store()

    print(f"Building index with {EMBED_MODEL} embeddings — this may take a minute...")
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )

    count = chroma_collection.count()
    print(f"Index complete. {count} vectors stored in ChromaDB at {CHROMA_PATH}")
    return index


def load_index() -> VectorStoreIndex:
    """Load an existing index from ChromaDB."""
    vector_store, chroma_collection, storage_context = get_chroma_store()

    count = chroma_collection.count()
    if count == 0:
        print("ERROR: ChromaDB collection is empty.")
        print("Run with --build to index your documents first.")
        sys.exit(1)

    print(f"Loaded existing index from {CHROMA_PATH} ({count} vectors)")
    return VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )


def query_loop(index: VectorStoreIndex) -> None:
    """Interactive query loop with source attribution."""
    query_engine = index.as_query_engine(
        similarity_top_k=TOP_K,
        response_mode="compact",
    )

    print("\nDocument Q&A ready. Type your question (or 'quit' to exit).\n")

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

        response = query_engine.query(question)
        print(f"\nAnswer: {str(response)}\n")

        print("Sources used:")
        seen_sources = set()
        for node_with_score in response.source_nodes:
            source = node_with_score.node.metadata.get("file_name", "unknown")
            score = node_with_score.score
            if source not in seen_sources:
                print(f"  - {source} (similarity: {score:.3f})")
                seen_sources.add(source)
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local Document Q&A with LlamaIndex + ChromaDB")
    parser.add_argument("--build", action="store_true", help="Build/rebuild the index")
    args = parser.parse_args()

    configure_settings()  # must come before any index construction

    if args.build:
        index = build_index()
    else:
        index = load_index()

    query_loop(index)
```

**Step 4: Run the example**

Build the index (first run or when documents change):
```bash
python example1_local_qa.py --build
```

Expected output:
```
Loading documents from ./my_docs...
Loaded 6 documents
Building index with nomic-embed-text embeddings — this may take a minute...
Index complete. 34 vectors stored in ChromaDB at ./chroma_example1
```

Run the Q&A loop:
```bash
python example1_local_qa.py
```

Expected output:
```
Loaded existing index from ./chroma_example1 (34 vectors)

Document Q&A ready. Type your question (or 'quit' to exit).

Question: What are the main configuration options?

Answer: The main configuration options include chunk_size, chunk_overlap, and
embed_model, all set through the global Settings object before creating an index...

Sources used:
  - settings-guide.md (similarity: 0.874)
  - configuration.md (similarity: 0.851)
```

---

### Example 2: Conversational PDF RAG with Streaming

This example builds a multi-turn chat system over a folder of PDF documents using `as_chat_engine()` with streaming output. It demonstrates the `condense_plus_context` chat mode, which rewrites follow-up questions using history and retrieves fresh context on every turn.

**Step 1: Install dependencies**

```bash
pip install llama-index-core llama-index-llms-ollama llama-index-embeddings-ollama \
            llama-index-vector-stores-chroma llama-index-readers-file chromadb pypdf
ollama pull llama3.2
ollama pull nomic-embed-text
```

**Step 2: Create the script**

```python
# example2_pdf_chat.py

"""
Conversational RAG chat engine over a PDF collection.
Uses as_chat_engine() with condense_plus_context mode and streaming.
Maintains conversation history across turns.

Usage:
    python example2_pdf_chat.py --pdf-dir ./pdfs --build    # index PDFs
    python example2_pdf_chat.py --pdf-dir ./pdfs            # start chat
"""

import argparse
import sys

import chromadb
from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore

# ── Configuration ─────────────────────────────────────────────────────────────
CHROMA_PATH = "./chroma_example2"
COLLECTION_NAME = "pdf_collection"
LLM_MODEL = "llama3.2"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 75
TOP_K = 5


def configure_settings() -> None:
    Settings.llm = Ollama(
        model=LLM_MODEL,
        base_url="http://localhost:11434",
        request_timeout=180.0,
        context_window=8192,
    )
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url="http://localhost:11434",
    )
    Settings.chunk_size = CHUNK_SIZE
    Settings.chunk_overlap = CHUNK_OVERLAP


def get_chroma_components() -> tuple:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return vector_store, collection, storage_context


def build_index(pdf_dir: str) -> VectorStoreIndex:
    import os
    if not os.path.isdir(pdf_dir):
        print(f"ERROR: PDF directory '{pdf_dir}' does not exist.")
        sys.exit(1)

    print(f"Loading PDFs from {pdf_dir}...")
    documents = SimpleDirectoryReader(
        input_dir=pdf_dir,
        recursive=True,
        required_exts=[".pdf"],
    ).load_data()

    if not documents:
        print(f"ERROR: No PDF files found in '{pdf_dir}'.")
        sys.exit(1)

    print(f"Loaded {len(documents)} PDF pages across all documents")

    vector_store, collection, storage_context = get_chroma_components()

    print("Embedding documents (this may take several minutes for large PDFs)...")
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )

    count = collection.count()
    print(f"Index complete. {count} vectors stored at {CHROMA_PATH}")
    return index


def load_index() -> VectorStoreIndex:
    vector_store, collection, storage_context = get_chroma_components()
    count = collection.count()
    if count == 0:
        print("ERROR: No indexed documents found. Run with --build first.")
        sys.exit(1)
    print(f"Loaded PDF index ({count} vectors) from {CHROMA_PATH}")
    return VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )


def chat_loop(index: VectorStoreIndex) -> None:
    """Multi-turn streaming chat with conversation history."""
    chat_engine = index.as_chat_engine(
        chat_mode="condense_plus_context",
        similarity_top_k=TOP_K,
        verbose=False,
    )

    print("\nPDF Chat ready. Ask questions about your documents.")
    print("Type 'reset' to clear conversation history, 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye.")
            break
        if user_input.lower() == "reset":
            chat_engine.reset()
            print("[Conversation history cleared]\n")
            continue

        print("Assistant: ", end="", flush=True)
        streaming_response = chat_engine.stream_chat(user_input)
        for token in streaming_response.response_gen:
            print(token, end="", flush=True)
        print("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Conversational PDF RAG with LlamaIndex")
    parser.add_argument("--pdf-dir", required=True, help="Directory containing PDF files")
    parser.add_argument("--build", action="store_true", help="Build/rebuild the index")
    args = parser.parse_args()

    configure_settings()

    if args.build:
        index = build_index(args.pdf_dir)
    else:
        index = load_index()

    chat_loop(index)
```

**Step 3: Run the example**

```bash
# Index a directory of PDFs
python example2_pdf_chat.py --pdf-dir ./pdfs --build

# Start the conversational chat
python example2_pdf_chat.py --pdf-dir ./pdfs
```

Expected conversation output:
```
Loaded PDF index (127 vectors) from ./chroma_example2

PDF Chat ready. Ask questions about your documents.
Type 'reset' to clear conversation history, 'quit' to exit.

You: What are the main topics covered in these documents?
Assistant: The documents cover three main areas: system architecture,
configuration management, and deployment procedures...

You: Tell me more about the deployment procedures.
Assistant: Building on what I found earlier, the deployment procedures section
describes a three-stage rollout process: staging validation, canary deployment
to 5% of traffic, and full production rollout...

You: reset
[Conversation history cleared]
```

The follow-up question "Tell me more about the deployment procedures" is answered correctly because `condense_plus_context` mode rewrites it as a standalone question using the prior exchange before retrieving fresh context.

---

### Example 3: RouterQueryEngine — Routing Between a Facts Index and a Summaries Index

This example builds a `RouterQueryEngine` that routes incoming queries to either a `VectorStoreIndex` (for specific factual lookups) or a `SummaryIndex` (for broad summaries). The router uses an LLM call to decide which index is most appropriate based on the query text and the tool descriptions.

```python
# example3_router_query_engine.py

"""
RouterQueryEngine routing between a VectorStoreIndex (specific facts)
and a SummaryIndex (broad summaries) over the same document set.
Uses LLMSingleSelector to choose the appropriate index at query time.

Usage:
    python example3_router_query_engine.py
    python example3_router_query_engine.py --demo
    (Requires ./my_docs to contain .txt or .md files)
"""

import sys

from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    SummaryIndex,
    VectorStoreIndex,
)
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector
from llama_index.core.tools import QueryEngineTool
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

# ── Configuration ─────────────────────────────────────────────────────────────
DOCS_DIR = "./my_docs"
LLM_MODEL = "llama3.2"
EMBED_MODEL = "nomic-embed-text"


def configure_settings() -> None:
    Settings.llm = Ollama(
        model=LLM_MODEL,
        base_url="http://localhost:11434",
        request_timeout=120.0,
        context_window=8192,
    )
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url="http://localhost:11434",
    )
    Settings.chunk_size = 512
    Settings.chunk_overlap = 50


def build_router_engine() -> RouterQueryEngine:
    import os
    if not os.path.isdir(DOCS_DIR):
        print(f"ERROR: Directory '{DOCS_DIR}' does not exist. Add .txt or .md files.")
        sys.exit(1)

    print(f"Loading documents from {DOCS_DIR}...")
    documents = SimpleDirectoryReader(
        input_dir=DOCS_DIR,
        recursive=True,
        required_exts=[".txt", ".md"],
    ).load_data()

    if not documents:
        print("ERROR: No .txt or .md files found.")
        sys.exit(1)

    print(f"Loaded {len(documents)} documents. Building both indexes...")

    # Build a VectorStoreIndex for precise semantic retrieval
    vector_index = VectorStoreIndex.from_documents(documents, show_progress=False)

    # Build a SummaryIndex for full-corpus summarisation
    summary_index = SummaryIndex.from_documents(documents, show_progress=False)

    print("Both indexes built.")

    # The descriptions are critical — the LLM selector reads them to decide routing
    vector_tool = QueryEngineTool.from_defaults(
        query_engine=vector_index.as_query_engine(
            similarity_top_k=4,
            response_mode="compact",
        ),
        description=(
            "Use this tool for specific, factual questions that ask about a particular "
            "detail, definition, procedure, or named concept in the documents. "
            "Examples: 'What does X mean?', 'How do I configure Y?', 'What is the "
            "syntax for Z?'"
        ),
    )

    summary_tool = QueryEngineTool.from_defaults(
        query_engine=summary_index.as_query_engine(
            response_mode="tree_summarize",
        ),
        description=(
            "Use this tool for broad, high-level questions that require synthesising "
            "information across many parts of the documents. "
            "Examples: 'Summarise these documents', 'What are the main themes?', "
            "'Give me an overview of the key points'."
        ),
    )

    router_engine = RouterQueryEngine(
        selector=LLMSingleSelector.from_defaults(),
        query_engine_tools=[vector_tool, summary_tool],
        verbose=True,   # logs which tool was selected and the selector's reasoning
    )

    return router_engine


def run_demo(router_engine: RouterQueryEngine) -> None:
    """Run a set of queries designed to exercise both routing paths."""
    test_queries = [
        # These should route to the vector (facts) tool
        ("SPECIFIC", "What is the chunk_overlap parameter used for?"),
        ("SPECIFIC", "How do I persist a LlamaIndex index to disk?"),
        # These should route to the summary tool
        ("SUMMARY", "Give me a high-level overview of all the documents."),
        ("SUMMARY", "What are the most important concepts covered across these files?"),
    ]

    for expected_route, query in test_queries:
        print(f"\n{'='*65}")
        print(f"Query (expected: {expected_route}): {query}")
        print("="*65)

        response = router_engine.query(query)
        print(f"\nAnswer:\n{str(response)}")


def interactive_loop(router_engine: RouterQueryEngine) -> None:
    print("\nRouter Q&A ready. Type your question (or 'quit' to exit).")
    print("Tip: ask specific questions ('What is X?') and broad questions ('Summarise') "
          "to see routing in action.\n")

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

        response = router_engine.query(question)
        print(f"\nAnswer: {str(response)}\n")


if __name__ == "__main__":
    configure_settings()
    router_engine = build_router_engine()

    if "--demo" in sys.argv:
        run_demo(router_engine)
    else:
        interactive_loop(router_engine)
```

**Run the example:**

```bash
# Interactive mode
python example3_router_query_engine.py

# Run the preset demo queries to see routing in action
python example3_router_query_engine.py --demo
```

With `verbose=True`, you will see output like:

```
=================================================================
Query (expected: SPECIFIC): What is the chunk_overlap parameter used for?
=================================================================
Selecting query engine 0: Useful for specific, factual questions...

Answer: The chunk_overlap parameter specifies how many tokens are shared between
adjacent chunks during document splitting. Its purpose is to prevent information
from being lost at chunk boundaries...

=================================================================
Query (expected: SUMMARY): Give me a high-level overview of all the documents.
=================================================================
Selecting query engine 1: Useful for broad, high-level questions...

Answer: These documents collectively cover the LlamaIndex framework, focusing on
three main areas: data ingestion pipelines, index construction and persistence,
and query engine configuration...
```

The tool descriptions are the router's only signal — write them carefully. Vague descriptions produce unreliable routing.

---

## Common Pitfalls

### Pitfall 1: Configuring `Settings` After Creating the Index

**Description:** The query engine uses OpenAI embeddings (or raises an import error about `openai`) even though `Settings.embed_model` was set to a local model.

**Why it happens:** `VectorStoreIndex.from_documents()` reads `Settings` at construction time. If you set `Settings.embed_model` after calling `from_documents()`, the index was already built with the default model — which is `text-embedding-ada-002` from OpenAI unless overridden beforehand.

**Incorrect pattern:**
```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.embeddings.ollama import OllamaEmbedding

documents = SimpleDirectoryReader("./docs").load_data()
index = VectorStoreIndex.from_documents(documents)  # reads Settings HERE — embed_model not set yet

# Too late — the index was already built with OpenAI embeddings
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
```

**Correct pattern:**
```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

# Configure Settings FIRST, before any index construction
Settings.llm = Ollama(model="llama3.2", request_timeout=120.0)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
Settings.chunk_size = 512

# Now create the index — it will use the local models
documents = SimpleDirectoryReader("./docs").load_data()
index = VectorStoreIndex.from_documents(documents)
```

---

### Pitfall 2: Embedding Model Mismatch Between Build and Query Time

**Description:** All retrieved nodes have very low similarity scores (e.g., 0.1–0.3) and the answers are wrong or generic. No error is raised.

**Why it happens:** The vector space is specific to the embedding model. Nodes embedded with `nomic-embed-text` (768d) are incompatible with queries embedded by `HuggingFaceEmbedding("all-MiniLM-L6-v2")` (384d). When you load an existing index from ChromaDB or disk storage with a different `Settings.embed_model` than was used at index time, every query is searching in the wrong space.

**Incorrect pattern:**
```python
# First run: indexed with nomic-embed-text
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)

# Second run: loaded with a different embedding model
Settings.embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")
index = VectorStoreIndex.from_vector_store(vector_store)  # wrong — mismatch
query_engine = index.as_query_engine()
response = query_engine.query("...")   # meaningless results
```

**Correct pattern:**
```python
# Store the model name alongside the index
EMBED_MODEL = "nomic-embed-text"   # defined once, used in both build and load paths

# Build
Settings.embed_model = OllamaEmbedding(model_name=EMBED_MODEL)
index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)

# Load — use the same EMBED_MODEL constant
Settings.embed_model = OllamaEmbedding(model_name=EMBED_MODEL)
index = VectorStoreIndex.from_vector_store(vector_store)
```

---

### Pitfall 3: Storage Context Errors When Combining ChromaDB with `persist()`

**Description:** Calling `index.storage_context.persist(persist_dir=...)` on an index backed by ChromaDB raises an error or silently produces an empty or corrupt state when you try to reload it with `load_index_from_storage()`.

**Why it happens:** ChromaDB persists its data independently via `PersistentClient`. When you use ChromaDB as the vector store, the vectors are already on disk. Calling `index.storage_context.persist()` writes the document store and index metadata to JSON — but `load_index_from_storage()` expects the vectors to be in those JSON files too, not in a separate ChromaDB path.

**Incorrect pattern:**
```python
# Mixed persistence: ChromaDB for vectors, persist() for everything else
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("docs")
vector_store = ChromaVectorStore(chroma_collection=collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
index.storage_context.persist(persist_dir="./storage")  # do not do this with Chroma

# This will fail — the storage JSON does not contain the vector data
storage_ctx = StorageContext.from_defaults(persist_dir="./storage")
index = load_index_from_storage(storage_ctx)  # error or empty results
```

**Correct pattern for ChromaDB:**
```python
# ChromaDB is self-managing — use PersistentClient and from_vector_store for reloading
chroma_client = chromadb.PersistentClient(path="./chroma_db")  # auto-persists to disk
collection = chroma_client.get_or_create_collection("docs")
vector_store = ChromaVectorStore(chroma_collection=collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# Build (first run)
index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
# No extra persist() call needed — ChromaDB already saved to ./chroma_db

# Reload (subsequent runs) — reconnect to the same PersistentClient path
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("docs")
vector_store = ChromaVectorStore(chroma_collection=collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
```

**Correct pattern for the built-in file storage (no ChromaDB):**
```python
# When NOT using ChromaDB, the default SimpleVectorStore is in-memory — persist() saves it
index = VectorStoreIndex.from_documents(documents)
index.storage_context.persist(persist_dir="./storage")  # correct: saves to JSON

storage_ctx = StorageContext.from_defaults(persist_dir="./storage")
index = load_index_from_storage(storage_ctx)  # correct: loads from JSON
```

---

### Pitfall 4: `chunk_size` Is Tokens, Not Characters

**Description:** Chunks are much larger than expected when migrating from LangChain's `RecursiveCharacterTextSplitter`, causing context window overflow or poor retrieval precision.

**Why it happens:** LangChain's splitter measures in **characters**. LlamaIndex's `SentenceSplitter` and `Settings.chunk_size` measure in **tokens**. English prose averages about 4 characters per token. A `chunk_size=512` in LangChain produces ~512-character chunks (~128 tokens). A `chunk_size=512` in LlamaIndex produces ~512-token chunks (~2048 characters) — four times larger.

**Incorrect mental model:**
```python
# Expecting LangChain-style 500-character chunks
Settings.chunk_size = 500  # This is 500 TOKENS — approximately 2000 characters
```

**Correct approach — verify chunk sizes after setting them:**
```python
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import Settings, SimpleDirectoryReader

Settings.chunk_size = 256   # 256 tokens ≈ 1000 characters — closer to LangChain's 500-char chunks

documents = SimpleDirectoryReader("./my_docs").load_data()

# Verify empirically
splitter = SentenceSplitter(chunk_size=256, chunk_overlap=25)
nodes = splitter.get_nodes_from_documents(documents)

for node in nodes[:3]:
    token_estimate = len(node.text.split())   # rough word count as proxy for tokens
    print(f"Node chars: {len(node.text):>5} | Words (approx tokens): {token_estimate:>4}")
    print(f"  {node.text[:80]}...")
```

As a practical conversion guide: LangChain `chunk_size=500` (characters) ≈ LlamaIndex `chunk_size=128` (tokens). LangChain `chunk_size=1000` ≈ LlamaIndex `chunk_size=256`.

---

### Pitfall 5: Forgetting `request_timeout` on Slow Hardware

**Description:** Queries raise `httpx.ReadTimeout` or `ollama.ResponseError: timeout` before the LLM finishes generating.

**Why it happens:** The default Ollama request timeout used by `llama-index-llms-ollama` is 30 seconds. On hardware generating 5–10 tokens/second, a response requiring 150 tokens takes 15–30 seconds — right at the edge of the default timeout. On slower hardware or with larger context windows, it exceeds it.

**Incorrect pattern:**
```python
# Uses default 30-second timeout — will fail on slow hardware with long responses
Settings.llm = Ollama(model="llama3.2")
```

**Correct pattern:**
```python
# Set a generous timeout — 120 seconds accommodates most local hardware
Settings.llm = Ollama(
    model="llama3.2",
    request_timeout=120.0,   # seconds
    context_window=8192,
)
```

If you are using the `SubQuestionQueryEngine`, multiply by the number of sub-questions — each one is a separate LLM call. For a query that generates 4 sub-questions plus a final synthesis, the total LLM time could be 5 times the per-query time.

---

## Summary

- LlamaIndex is a data-first framework for connecting private document corpora to LLMs. Its design centre is retrieval quality; LangChain's design centre is chain composition. Both support RAG, but LlamaIndex is the better default when retrieval precision and data pipeline control are the primary concern.
- The `Settings` singleton must be configured — with local `Ollama` LLM and `OllamaEmbedding` or `HuggingFaceEmbedding` — before any index is created. It provides global defaults for `llm`, `embed_model`, `chunk_size`, and `chunk_overlap`.
- `Document` objects (raw loaded content) are split into `TextNode` objects (indexed chunks with metadata and relationships) by node parsers such as `SentenceSplitter`. `chunk_size` and `chunk_overlap` are measured in tokens, not characters.
- `VectorStoreIndex` is the workhorse index for semantic retrieval. `SummaryIndex` supports full-corpus summarisation. `RouterQueryEngine` routes queries between them intelligently using an LLM selector.
- Index persistence: use `chromadb.PersistentClient` for production — ChromaDB manages its own on-disk storage, and the correct reload pattern is `VectorStoreIndex.from_vector_store()`. The built-in `persist()` / `load_index_from_storage()` pattern works for the default `SimpleVectorStore` but should not be mixed with ChromaDB.
- `as_chat_engine(chat_mode="condense_plus_context")` provides multi-turn conversational RAG with history management. `SubQuestionQueryEngine` decomposes complex queries into targeted sub-questions. Both patterns are built in and require no custom chain logic.

---

## Further Reading

- [LlamaIndex Official Documentation](https://developers.llamaindex.ai/python/framework/) — The primary reference for all LlamaIndex Python components. Covers `Settings`, `VectorStoreIndex`, `SimpleDirectoryReader`, `IngestionPipeline`, query engines, and chat engines with complete API documentation and worked examples. Start here for any component not covered in this module.

- [LlamaIndex Local LLM Starter Tutorial](https://developers.llamaindex.ai/python/framework/getting_started/starter_example_local/) — The official quickstart for running LlamaIndex entirely with local models using Ollama and HuggingFace embeddings. Covers `Settings` configuration, `VectorStoreIndex.from_documents()`, and index persistence in a minimal working example. The best first code to run after this module.

- [Ollama Embeddings — LlamaIndex Integration Docs](https://developers.llamaindex.ai/python/framework/integrations/embeddings/ollama_embedding/) — Official documentation for `OllamaEmbedding` from `llama-index-embeddings-ollama`, including all constructor parameters (`model_name`, `base_url`, `embed_batch_size`), how to set it in `Settings`, and worked examples with `VectorStoreIndex`.

- [Ollama LLM Integration — LlamaIndex Docs](https://developers.llamaindex.ai/python/framework/integrations/llm/ollama/) — Reference page for the `Ollama` LLM class from `llama-index-llms-ollama`, covering `model`, `request_timeout`, `context_window`, streaming (`stream_complete`, `stream_chat`), and structured outputs with Pydantic.

- [Persisting and Loading Data — LlamaIndex Docs](https://developers.llamaindex.ai/python/framework/module_guides/storing/save_load/) — Complete documentation for the `persist()` and `load_index_from_storage()` patterns, with code examples for the default `SimpleVectorStore`, remote S3 backends, and guidance on when to use `from_vector_store()` instead with external vector stores like ChromaDB.

- [Response Synthesis Modes — LlamaIndex Docs](https://docs.llamaindex.ai/en/stable/module_guides/querying/response_synthesizers/response_synthesizers/) — Complete documentation for all response synthesizer modes: `compact`, `refine`, `tree_summarize`, `simple_summarize`, `accumulate`, and `no_text`. Includes explanations of when to use each mode and how they differ in the number of LLM calls they make.

- [Router Query Engine — LlamaIndex Example](https://developers.llamaindex.ai/python/examples/cookbooks/oreilly_course_cookbooks/module-6/router_and_subquestion_queryengine/) — A worked example demonstrating both `RouterQueryEngine` and `SubQuestionQueryEngine` with `QueryEngineTool`, `ToolMetadata`, `LLMSingleSelector`, and full end-to-end code. Essential reference for building the routing and sub-question patterns from this module.

- [IngestionPipeline — LlamaIndex Docs](https://docs.llamaindex.ai/en/stable/module_guides/loading/ingestion_pipeline/) — Full documentation for `IngestionPipeline` including how to define transformation sequences, enable document-level deduplication, persist and load the pipeline cache, and integrate directly with vector stores. Describes how the pipeline eliminates re-processing of unchanged documents.

- [Storing and Customizing Storage — LlamaIndex Docs](https://developers.llamaindex.ai/python/framework/module_guides/storing/customization/) — Covers the full storage layer: `StorageContext`, `ChromaVectorStore`, and how to connect external vector stores so that persistence is managed by the external system rather than LlamaIndex's JSON files. Required reading before deploying any LlamaIndex application with ChromaDB.

- [llama-index-core on PyPI](https://pypi.org/project/llama-index-core/) — The official PyPI page for `llama-index-core`. Check this for the current stable version number, Python version requirements, and release history. At the time of writing the current release is `0.14.20` (April 2026), requiring Python 3.10+.
