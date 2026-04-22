# Module 3: LangChain Fundamentals
> Subject: AI Development | Difficulty: Intermediate | Estimated Time: 300 minutes

## Objective

After completing this module, you will be able to explain the problems LangChain solves and when to choose it over raw SDK calls. You will install and configure the LangChain ecosystem against a local Ollama backend. You will use the core abstractions — `ChatOllama`, prompt templates, output parsers, and chains — and compose them fluently using the LangChain Expression Language (LCEL) pipe operator. You will implement persistent multi-turn conversation history using `RunnableWithMessageHistory` and manage context window trimming. You will load documents and split them into chunks using LangChain's document loaders and text splitters. You will apply practical local-model patterns including streaming through chains, fallback handling, and debugging with `set_debug`. Finally, you will be able to make an informed choice between LangChain, LlamaIndex, Haystack, and DSPy for a given project.

## Prerequisites

- Completed **Module 0: Setup & Local AI Stack** — Ollama is installed, running, and at least one model is pulled
- Completed **Module 1: Working with Local Models** — familiar with `ollama.chat()`, streaming, the message format, and inference parameters
- Completed **Module 2: Hugging Face & Local Models** — comfortable with the concept of chat templates and the transformers ecosystem
- Python 3.10 or later with an active virtual environment
- At least one model pulled via Ollama: `ollama pull llama3.2` (3B, ~2 GB) is the default used throughout this module; `ollama pull phi4-mini` (3.8B, ~2.5 GB) is a good alternative
- Comfort with Python type hints, dataclasses, and basic `pydantic` usage

---

## Key Concepts

### 1. What LangChain Is and Why It Exists

When you worked with the raw `ollama` SDK in Module 1, you wrote all the scaffolding yourself: maintaining the message list, building prompt strings, parsing the response text, managing history across turns, and handling errors from the model server. For a single script, this is fine. For an application — something with multiple prompt stages, structured output requirements, document processing, and conversation memory — you end up re-writing the same boilerplate in every project.

**LangChain is a composability framework.** Its core value proposition is a set of standard interfaces that make every piece of the LLM pipeline — models, prompts, parsers, retrievers, memory stores — interchangeable and chainable. Change from one model to another by changing one line. Swap a JSON parser for a Pydantic parser without touching the rest of the chain. Add document retrieval to any chain without restructuring it.

The framework also solves a second problem: **provider abstraction**. Whether you are running a local Ollama model or (in production) using a cloud provider, the same chain code works with minimal changes. This makes local development against cheap, private, offline models a reliable path to a production-ready application.

**When LangChain is the right tool:**

- You are building a multi-stage pipeline where prompt, model, and parsing steps compose sequentially
- You need to swap model providers during development or across environments (local Ollama in dev, cloud in production)
- Your application requires conversation memory, document loading, or retrieval-augmented generation (RAG)
- You want structured output (JSON, Pydantic models) from the LLM in a repeatable way
- You are building agents that need tool-calling abstractions

**When to use raw SDK calls instead:**

- A single prompt call with no composition — the extra abstraction adds noise with no benefit
- You need maximum performance control that the LangChain layer cannot expose
- You are writing a quick one-off script and you know the model and task will not change
- Your use case is already served by a purpose-built library (e.g., a dedicated speech-to-text pipeline)

#### The LangChain Package Ecosystem

LangChain is not a monolith. As of 2026 it consists of several separately versioned packages:

| Package | PyPI Name | Current Version | Role |
|---|---|---|---|
| **Core** | `langchain-core` | 1.3.0 | Base Runnable interfaces, LCEL, prompt types, message types, output parsers. No LLM provider dependencies. |
| **Integrations** | `langchain-community` | 0.4.1 | Community-contributed integrations: document loaders, text splitters, many third-party model bindings. |
| **Ollama integration** | `langchain-ollama` | 1.1.0 | `ChatOllama` — the officially maintained Ollama integration. Separate package, not in `langchain-community`. |
| **Orchestration** | `langchain` | 1.2.15 | High-level agents, chains, and tools that compose the lower packages. |

The important architectural principle: **`langchain-core` defines what everything looks like; integration packages implement it.** A chain built against `langchain-core` abstractions can run with any provider that implements the same interface. This is why switching from `ChatOllama` to a cloud chat model requires changing only the model constructor.

> **Cloud alternatives (brief mention):** OpenAI (`langchain-openai`) and Anthropic (`langchain-anthropic`) are the most common cloud provider packages. They implement the same `BaseChatModel` interface as `ChatOllama`. This module uses `langchain-ollama` exclusively to keep all examples running offline and privately.

#### Ecosystem Alternatives to Know About

| Framework | Focus | When to Consider |
|---|---|---|
| **LlamaIndex** | Data-centric RAG — deep indexing, retrieval, and query engines | Complex document retrieval applications |
| **Haystack** | Production NLP pipelines and enterprise search | Enterprise RAG, semantic search, MLOps integration |
| **DSPy** | Programmatic LLM prompt optimisation | When you want to compile and optimise prompts automatically |

All three are covered in the comparison table in Section 7. No code examples are provided for alternatives — this module focuses on LangChain.

---

### 2. Installation and Setup

Install the four packages you need for this module:

```bash
pip install langchain langchain-community langchain-ollama
```

For PDF loading (used in Section 5):

```bash
pip install pypdf
```

For structured output with Pydantic and JSON parsing:

```bash
pip install pydantic
```

Verify the installation and Ollama connection in a Python REPL or script:

```python
# verify_setup.py

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

# Instantiate the model — this does NOT load weights; it configures a connection
llm = ChatOllama(model="llama3.2", temperature=0.0)

# A simple invoke call is the fastest connection test
try:
    response = llm.invoke([HumanMessage(content="Reply with the single word: ready")])
    print(f"Connection OK. Model replied: {response.content!r}")
except Exception as e:
    print(f"Connection failed: {e}")
    print("Ensure Ollama is running: ollama serve")
    print("Ensure the model is pulled: ollama pull llama3.2")
```

Run with: `python verify_setup.py`

Expected output: `Connection OK. Model replied: 'ready'` (exact wording varies by model).

**Connection troubleshooting:**

| Error | Cause | Fix |
|---|---|---|
| `Connection refused` | Ollama server is not running | Run `ollama serve` in a separate terminal |
| `404 model not found` | Model name is wrong or not pulled | Run `ollama pull llama3.2` |
| `ModuleNotFoundError: langchain_ollama` | Package not installed | Run `pip install langchain-ollama` |

---

### 3. Core Abstractions

#### 3.1 Chat Models — `ChatOllama`

`ChatOllama` is LangChain's interface to a locally running Ollama server. It extends `langchain-core`'s `BaseChatModel`, so every method and interface described here applies equally to any LangChain chat model — you are not learning Ollama specifics, you are learning the standard interface.

**Instantiation:**

```python
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="llama3.2",       # any model pulled with ollama pull
    temperature=0.7,        # 0.0 for deterministic output; 0.7 for general use
    num_ctx=4096,           # context window; Ollama default is 2048 — too small for chains
    num_predict=512,        # maximum tokens to generate
    top_k=40,
    top_p=0.9,
    repeat_penalty=1.1,
)
```

**The three invocation methods every `BaseChatModel` supports:**

```python
from langchain_core.messages import HumanMessage, SystemMessage

messages = [
    SystemMessage(content="You are a concise assistant."),
    HumanMessage(content="Name the three primary colours."),
]

# invoke() — synchronous, returns a single AIMessage
response = llm.invoke(messages)
print(response.content)
print(type(response))  # <class 'langchain_core.messages.ai.AIMessage'>

# stream() — synchronous generator that yields AIMessageChunk objects
for chunk in llm.stream(messages):
    print(chunk.content, end="", flush=True)
print()

# batch() — synchronous, processes a list of inputs and returns a list of responses
# Ollama does not run multiple requests in parallel, so this is sequential for local models
batch_results = llm.batch([messages, messages])
for result in batch_results:
    print(result.content[:60])
```

**The `BaseMessage` types:**

LangChain uses typed message classes instead of plain dicts. This gives you type safety and the ability to pass messages directly to any chain component.

| Class | Role | Equivalent raw dict |
|---|---|---|
| `SystemMessage` | System/persona prompt | `{"role": "system", "content": "..."}` |
| `HumanMessage` | User's input | `{"role": "user", "content": "..."}` |
| `AIMessage` | Model's reply | `{"role": "assistant", "content": "..."}` |
| `AIMessageChunk` | One streaming chunk | Fragment of an `AIMessage` |

All four are importable from `langchain_core.messages`.

**Switching models:**

Because the interface is standardised, swapping models is one line:

```python
# Development (local, free, private)
llm = ChatOllama(model="llama3.2", temperature=0.7)

# Alternative local model — change one line, chain code unchanged
llm = ChatOllama(model="phi4-mini", temperature=0.7)

# Cloud (if needed for production) — change one import and constructor
# from langchain_openai import ChatOpenAI
# llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
```

---

#### 3.2 Prompt Templates

Prompt templates separate the static structure of a prompt from the dynamic content that changes per call. They are the first component in almost every chain.

**`ChatPromptTemplate` — for chat models:**

```python
from langchain_core.prompts import ChatPromptTemplate

# The most common pattern: system + human message with placeholders
template = ChatPromptTemplate.from_messages([
    ("system", "You are an expert in {domain}. Answer concisely."),
    ("human", "{question}"),
])

# Rendering the template fills in the placeholders
messages = template.invoke({"domain": "Python", "question": "What is a decorator?"})
print(messages)
# ChatPromptValue with SystemMessage and HumanMessage
print(messages.to_messages())
# [SystemMessage(content='You are an expert in Python...'), HumanMessage(content='What is a decorator?')]
```

**`PromptTemplate` — for plain string templates (not chat messages):**

```python
from langchain_core.prompts import PromptTemplate

# Used when you need a single formatted string rather than a list of messages
summarise_prompt = PromptTemplate.from_template(
    "Summarise the following text in one sentence:\n\n{text}"
)

formatted = summarise_prompt.invoke({"text": "Python is a high-level programming language..."})
print(formatted.text)
```

**`MessagesPlaceholder` — for inserting a variable-length list of messages:**

This is essential for conversation history. Instead of hard-coding how many prior turns appear, you inject the full history list at the placeholder position.

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

conversational_template = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder(variable_name="history"),  # entire history injected here
    ("human", "{input}"),
])
```

The `variable_name` is the key you will pass when invoking the chain. `MessagesPlaceholder` accepts any Python list of `BaseMessage` objects.

**Partial templates — pre-filling some variables:**

```python
from langchain_core.prompts import ChatPromptTemplate

full_template = ChatPromptTemplate.from_messages([
    ("system", "You are an expert in {domain}. Be {style}."),
    ("human", "{question}"),
])

# Pre-fill domain — the resulting partial_template only needs style and question
python_expert = full_template.partial(domain="Python")

messages = python_expert.invoke({"style": "concise", "question": "What is a list comprehension?"})
```

Partial templates are useful when certain variables are fixed for a specific use case (e.g., domain is always "Python" for a Python assistant tool) but others vary per call.

---

#### 3.3 Output Parsers

After the model generates text, output parsers convert that text into a useful Python object. They are the last component in a chain.

**`StrOutputParser` — the simplest parser, returns plain text:**

```python
from langchain_core.output_parsers import StrOutputParser

parser = StrOutputParser()
# Accepts an AIMessage and returns its .content string
text = parser.invoke(response)  # response is an AIMessage
print(type(text))  # <class 'str'>
```

**`JsonOutputParser` — parses model output as JSON:**

```python
from langchain_core.output_parsers import JsonOutputParser

# Instructs the model to produce JSON and parses the result into a dict
parser = JsonOutputParser()

# The parser adds format instructions to the prompt automatically when used in a chain
# You must tell the model to produce JSON — add this to your system prompt:
# "Respond ONLY with valid JSON. Do not include any explanation."
```

**`PydanticOutputParser` — parses and validates against a Pydantic model:**

```python
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


class PersonInfo(BaseModel):
    name: str = Field(description="Full name of the person")
    age: int = Field(description="Age in years")
    occupation: str = Field(description="Current job or profession")


parser = PydanticOutputParser(pydantic_object=PersonInfo)

# The parser can generate format instructions for the prompt
print(parser.get_format_instructions())
# Output: "The output should be formatted as a JSON instance that conforms to the JSON schema..."
```

**`.with_structured_output()` — the cleanest structured output API:**

For models that support structured output natively (or through tool-calling), `.with_structured_output()` bypasses the parse-and-validate cycle:

```python
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama


class BookReview(BaseModel):
    title: str = Field(description="The book title")
    rating: int = Field(description="Rating from 1 to 5")
    summary: str = Field(description="One-sentence summary of the review")


# Bind the schema to the model — it will return a BookReview instance directly
structured_llm = llm.with_structured_output(BookReview)

result = structured_llm.invoke(
    "Review: 'The Pragmatic Programmer' is a must-read classic on software craftsmanship. 5/5 stars."
)
print(type(result))   # <class '__main__.BookReview'>
print(result.title)   # The Pragmatic Programmer
print(result.rating)  # 5
```

> **Note:** `.with_structured_output()` requires the model to support tool-calling or JSON mode. Not all Ollama models support this. `llama3.2`, `phi4-mini`, `qwen2.5:7b`, and `gemma3:4b` support it as of 2026. If it fails with your model, use `PydanticOutputParser` instead.

---

#### 3.4 Chains with LCEL — LangChain Expression Language

LCEL is the composition system that connects LangChain components. Its central concept is the **pipe operator** (`|`): chain components by connecting output to input, just like shell pipes. Any two objects where the output type of the left matches the accepted input type of the right can be connected.

**The minimal chain:**

```python
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOllama(model="llama3.2", temperature=0.7)

chain = (
    ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("human", "{question}"),
    ])
    | llm
    | StrOutputParser()
)

# invoke() runs the chain and returns a string
result = chain.invoke({"question": "What is the Python GIL?"})
print(result)

# stream() runs the chain and yields string chunks
for chunk in chain.stream({"question": "Explain async/await in Python."}):
    print(chunk, end="", flush=True)
print()
```

The chain's execution is: dict → `ChatPromptTemplate` renders messages → `ChatOllama` generates `AIMessage` → `StrOutputParser` extracts `.content` string.

**`RunnablePassthrough` — passing data through unchanged:**

```python
from langchain_core.runnables import RunnablePassthrough

# Useful for threading values through a chain without modification
# Common pattern: pass the original question alongside retrieved context
pass_through = RunnablePassthrough()
result = pass_through.invoke({"question": "test", "context": "some docs"})
# Returns: {"question": "test", "context": "some docs"} unchanged
```

**`RunnableLambda` — wrapping any Python callable as a chain step:**

```python
from langchain_core.runnables import RunnableLambda

def format_docs(docs: list) -> str:
    """Combine a list of documents into a single string."""
    return "\n\n".join(doc.page_content for doc in docs)

# Wrap any function as a Runnable so it can be composed with |
format_step = RunnableLambda(format_docs)
```

**`RunnableParallel` — running multiple chains on the same input:**

```python
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOllama(model="llama3.2", temperature=0.7)

# Both chains run on the same input dict; results are merged into one output dict
parallel_chain = RunnableParallel(
    summary=ChatPromptTemplate.from_messages([
        ("system", "Summarise the following text in one sentence."),
        ("human", "{text}"),
    ]) | llm | StrOutputParser(),

    keywords=ChatPromptTemplate.from_messages([
        ("system", "Extract five keywords from the following text. Return them comma-separated."),
        ("human", "{text}"),
    ]) | llm | StrOutputParser(),

    original=RunnablePassthrough(),  # also pass the original input through
)

result = parallel_chain.invoke({"text": "Python is a high-level, interpreted programming language..."})
print(result["summary"])    # one-sentence summary
print(result["keywords"])   # comma-separated keywords
print(result["original"])   # the original input dict
```

**Inspecting a chain with `.get_graph()`:**

```python
chain = (
    ChatPromptTemplate.from_messages([("system", "Be helpful."), ("human", "{q}")])
    | llm
    | StrOutputParser()
)

# Print an ASCII representation of the chain's execution graph
chain.get_graph().print_ascii()
```

Example output:

```
           +---------------------------------+
           | ChatPromptTemplate              |
           +---------------------------------+
                            |
                            |
                            v
           +---------------------------------+
           | ChatOllama                      |
           +---------------------------------+
                            |
                            |
                            v
           +---------------------------------+
           | StrOutputParser                 |
           +---------------------------------+
```

---

### 4. Memory and Conversation History

In Module 1 you managed conversation history manually by appending messages to a Python list. LangChain formalises this with `ChatMessageHistory` and `RunnableWithMessageHistory`.

**`ChatMessageHistory` — an in-memory store for one conversation:**

```python
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

history = ChatMessageHistory()
history.add_user_message("What is Python?")
history.add_ai_message("Python is a high-level, interpreted programming language.")
history.add_user_message("What is it used for?")

print(history.messages)
# [HumanMessage(content='What is Python?'), AIMessage(content='...'), HumanMessage(content='What is it used for?')]
```

**`RunnableWithMessageHistory` — wiring history into a chain:**

`RunnableWithMessageHistory` wraps any chain and automatically: (1) fetches history for the current session before each call, (2) inserts it into the chain at the `MessagesPlaceholder`, and (3) saves the new human and AI messages back to history after each call.

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser

llm = ChatOllama(model="llama3.2", temperature=0.7, num_ctx=4096)

# The chain itself — note MessagesPlaceholder for history injection
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

chain = prompt | llm | StrOutputParser()

# Session store — maps session_id -> ChatMessageHistory
session_store: dict[str, ChatMessageHistory] = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    """Return the history for a session, creating it if it does not exist."""
    if session_id not in session_store:
        session_store[session_id] = ChatMessageHistory()
    return session_store[session_id]

# Wrap the chain with history management
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

# The session_id is passed in the config dict
config = {"configurable": {"session_id": "alice-session-1"}}

reply1 = chain_with_history.invoke({"input": "What is a Python decorator?"}, config=config)
print(reply1)

reply2 = chain_with_history.invoke({"input": "Can you give me a simple example?"}, config=config)
print(reply2)
# reply2 has full context: the model knows reply1 asked about decorators
```

**Managing history size — trimming to fit context windows:**

As conversations grow, the history list can exceed the model's context window. LangChain provides `trim_messages()` to reduce it:

```python
from langchain_core.messages import trim_messages, SystemMessage

def get_trimmed_history(session_id: str) -> ChatMessageHistory:
    """Return history trimmed to fit within 3000 tokens."""
    if session_id not in session_store:
        session_store[session_id] = ChatMessageHistory()

    raw_history = session_store[session_id]

    # trim_messages reduces the message list to stay within token_counter limit
    trimmed = trim_messages(
        raw_history.messages,
        max_tokens=3000,
        strategy="last",              # keep the most recent messages
        token_counter=llm,            # use the model to count tokens
        include_system=True,          # always keep the system message
        allow_partial=False,          # never cut a message in half
        start_on="human",             # ensure the trimmed history starts with a human turn
    )

    trimmed_history = ChatMessageHistory()
    trimmed_history.messages = trimmed
    return trimmed_history
```

The `strategy="last"` option preserves the most recent conversation turns and discards older ones when the limit is exceeded — the right default for most chatbots. The `start_on="human"` guard ensures the trimmed window never begins with an AI message, which could confuse the model.

> **Persistence note:** `ChatMessageHistory` is in-memory only — it is lost when your Python process exits. For persistent history across sessions, `langchain-community` provides database-backed history classes (`SQLChatMessageHistory`, `RedisChatMessageHistory`). These are covered in Module 5.

---

### 5. Document Loaders and Text Splitters

Before documents can be used with a language model — for summarisation, Q&A, or RAG — they must be loaded into LangChain's `Document` format and split into chunks that fit within the model's context window. This section covers the loading and splitting steps. Vector storage and retrieval are covered in Module 4.

#### 5.1 The `Document` Object

All loaders return a list of `Document` objects. Each `Document` has two fields:

```python
from langchain_core.documents import Document

doc = Document(
    page_content="This is the text content of the document.",
    metadata={"source": "my_file.txt", "page": 0},
)
```

The `metadata` dict is populated automatically by loaders with source, page number, and other relevant fields.

#### 5.2 Document Loaders

**`TextLoader` — load a plain text file:**

```python
from langchain_community.document_loaders import TextLoader

loader = TextLoader("./data/my_notes.txt", encoding="utf-8")
docs = loader.load()
# Returns a list with one Document per file
print(len(docs))         # 1
print(docs[0].metadata)  # {'source': './data/my_notes.txt'}
```

**`DirectoryLoader` — load all files matching a glob pattern:**

```python
from langchain_community.document_loaders import DirectoryLoader, TextLoader

# Load all .txt files in a directory tree
loader = DirectoryLoader(
    "./data/docs",
    glob="**/*.txt",          # recursive glob pattern
    loader_cls=TextLoader,    # which loader class to use per file
    show_progress=True,       # print a progress bar
    use_multithreading=True,  # load files in parallel
)
docs = loader.load()
print(f"Loaded {len(docs)} documents")
```

**`PyPDFLoader` — load a PDF file (requires `pip install pypdf`):**

```python
from langchain_community.document_loaders import PyPDFLoader

loader = PyPDFLoader("./data/report.pdf")
docs = loader.load()
# Returns one Document per page
print(len(docs))         # number of pages
print(docs[0].metadata)  # {'source': './data/report.pdf', 'page': 0}
```

**`WebBaseLoader` — load a web page (requires `pip install beautifulsoup4`):**

```python
from langchain_community.document_loaders import WebBaseLoader

loader = WebBaseLoader(
    web_paths=["https://python.org/about/"],
    bs_kwargs={"parse_only": None},  # BeautifulSoup parsing options
)
docs = loader.load()
print(docs[0].page_content[:200])
```

> `WebBaseLoader` makes HTTP requests at load time. If you need offline operation, download the pages first and use `TextLoader` instead.

#### 5.3 Text Splitters — Why Chunking Matters

Even a single PDF page may contain more tokens than a model's context window allows. And for RAG, smaller chunks produce more precise retrieval: a 200-token chunk about a specific topic is more relevant to a narrow query than a 2000-token page that covers many topics.

**`RecursiveCharacterTextSplitter` — the recommended default:**

This splitter tries to split on semantic boundaries in order: paragraphs (`\n\n`), lines (`\n`), sentences (`. `), then individual characters. It falls back to the next separator only when the chunk would exceed `chunk_size`. This preserves as much semantic coherence as possible.

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,      # maximum characters per chunk
    chunk_overlap=50,    # characters shared between adjacent chunks
    length_function=len, # how to measure length (can be replaced with a token counter)
    is_separator_regex=False,
)

# Split a list of Documents — returns a new list of (smaller) Documents
chunks = splitter.split_documents(docs)
print(f"{len(docs)} documents split into {len(chunks)} chunks")

# Or split raw text
text = "Long text string here..." * 50
chunks_from_text = splitter.create_documents([text])
```

**Key parameter guidance:**

| Parameter | Recommended value | Rationale |
|---|---|---|
| `chunk_size` | 300–600 characters | Roughly 75–150 tokens. Small enough for precise retrieval; large enough to contain meaningful context. |
| `chunk_overlap` | 10–15% of chunk_size | Ensures sentences that span chunk boundaries are not lost from either chunk. |

Embeddings and vector stores — the next step after chunking — are covered in Module 4.

---

### 6. LangChain with Local Models — Practical Patterns

#### 6.1 Switching Between Local Models

Because all `ChatOllama` instances share the same interface, you can parameterise the model name and switch with a config change:

```python
import os
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Read model name from an environment variable — default to llama3.2
MODEL_NAME = os.getenv("LANGCHAIN_MODEL", "llama3.2")

llm = ChatOllama(model=MODEL_NAME, temperature=0.7, num_ctx=4096)

chain = (
    ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("human", "{question}"),
    ])
    | llm
    | StrOutputParser()
)

print(f"Using model: {MODEL_NAME}")
result = chain.invoke({"question": "What is LCEL?"})
print(result)
```

Switch models without changing code: `LANGCHAIN_MODEL=phi4-mini python your_script.py`

#### 6.2 Streaming Responses Through a Chain

The `stream()` method propagates token-by-token through any chain that ends with a string-producing parser:

```python
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOllama(model="llama3.2", temperature=0.7, num_ctx=4096)

chain = (
    ChatPromptTemplate.from_messages([
        ("system", "You are a concise technical writer."),
        ("human", "Explain {topic} in three bullet points."),
    ])
    | llm
    | StrOutputParser()
)

print("Response: ", end="", flush=True)
for chunk in chain.stream({"topic": "Python generators"}):
    print(chunk, end="", flush=True)
print()
```

> When using `PydanticOutputParser` or `JsonOutputParser`, streaming emits partial JSON strings — useful only for progress indication, not for incremental parsing. Use `.invoke()` when you need a complete structured object.

#### 6.3 Fallback Chains for Model Errors

`.with_fallbacks()` catches errors from a primary runnable and retries with an alternative:

```python
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser

# Primary model — may be slow or unavailable on some machines
primary_llm = ChatOllama(model="phi4", temperature=0.7)  # larger model

# Fallback — smaller, always available
fallback_llm = ChatOllama(model="llama3.2", temperature=0.7)

# If primary_llm raises any Exception, fallback_llm is tried automatically
robust_llm = primary_llm.with_fallbacks([fallback_llm])

chain = robust_llm | StrOutputParser()

result = chain.invoke("What is a Python list comprehension?")
print(result)
```

This pattern is useful when:
- You want to try a larger local model and automatically fall back to a smaller one
- You are developing against a model that may not be pulled on all machines

#### 6.4 Debugging with `set_debug` and `set_verbose`

```python
from langchain.globals import set_debug, set_verbose

# set_verbose(True) — prints chain inputs and outputs at each step
# Useful for understanding what is flowing through your chain
set_verbose(True)

# set_debug(True) — prints verbose internal state including full prompts sent to the model
# Useful when output is wrong and you need to see exactly what the model received
set_debug(True)

# Usage: set either before calling your chain
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOllama(model="llama3.2", temperature=0.0)
chain = (
    ChatPromptTemplate.from_messages([("human", "{q}")])
    | llm
    | StrOutputParser()
)

result = chain.invoke({"q": "test"})

# Turn off after debugging — these produce a lot of output in production
set_debug(False)
set_verbose(False)
```

`set_verbose(True)` is the right first step when a chain produces unexpected output. `set_debug(True)` is the nuclear option — it prints every internal callback event, full prompt text, and token-level detail. Both are global flags; always disable them before committing code.

---

### 7. Framework Comparison

The following table provides a factual comparison of LangChain, LlamaIndex, Haystack, and DSPy. No code examples are included for the alternatives — this is an awareness table to help you choose the right tool for future projects.

| | **LangChain** | **LlamaIndex** | **Haystack** | **DSPy** |
|---|---|---|---|---|
| **Learning curve** | Moderate — many concepts but consistent patterns | Moderate — data-centric abstractions require new mental model | Moderate — pipeline-oriented; strong CLI tooling | Steep — programmatic prompt optimisation is a new paradigm |
| **RAG support** | Good — document loaders, splitters, retrievers, vector stores all included | Excellent — built specifically for RAG; advanced indexing and query engines | Excellent — enterprise-grade semantic search and retrieval pipelines | Good — RAG pipelines supported but less first-class than retrieval |
| **Agent support** | Excellent — extensive agent frameworks including LangGraph for stateful agents | Good — ReAct agents and tool use; LlamaIndex agents are improving | Fair — agents are supported but less mature than LangChain | Different — DSPy "programs" are compiled, not imperative agents |
| **Local model support** | Excellent — `ChatOllama`, `langchain-community` integrations for all major local runtimes | Good — Ollama integration available; slightly more effort to configure | Good — Ollama and HuggingFace integrations available | Good — supports Ollama via local LM backends |
| **Community size** | Largest — most Stack Overflow answers, tutorials, and third-party integrations | Large — strong in the enterprise RAG community | Medium — strong in European enterprise and NLP research contexts | Growing — Stanford academic community; smaller practitioner base |
| **Best use case** | General-purpose LLM application framework; agents; multi-step chains; prototyping | Data-heavy RAG applications; complex document indexing and structured retrieval | Production NLP pipelines; enterprise search; MLOps-integrated deployments | Research and production where prompt quality must be systematically optimised |

---

### 8. Common Pitfalls

#### Pitfall 1: Ollama Not Running — `Connection refused` on Chain Invoke

**Description:** Calling `chain.invoke()` raises a `ConnectionRefusedError` or `httpx.ConnectError` immediately.

**Why it happens:** `ChatOllama` connects to the Ollama server at `http://localhost:11434` on each call. If the server is not running, the TCP connection is refused.

**Incorrect pattern:**
```python
# Running chain.invoke() without first verifying Ollama is up
from langchain_ollama import ChatOllama
llm = ChatOllama(model="llama3.2")
result = llm.invoke("hello")  # ConnectionRefusedError if Ollama is not running
```

**Correct pattern:**
```python
import subprocess
import sys
from langchain_ollama import ChatOllama

def check_ollama() -> None:
    """Raise a clear error if Ollama is not reachable."""
    import httpx
    try:
        httpx.get("http://localhost:11434", timeout=2.0)
    except httpx.ConnectError:
        print("ERROR: Ollama is not running.")
        print("Start it with: ollama serve")
        sys.exit(1)

check_ollama()
llm = ChatOllama(model="llama3.2")
```

---

#### Pitfall 2: LCEL Debugging — Silent Chain Failures

**Description:** A chain returns empty strings, `None`, or unexpected values with no error message.

**Why it happens:** LCEL chains swallow certain non-fatal issues silently. Common causes: a `RunnableLambda` function returns `None`; a prompt template variable name does not match the input dict key; the model returns an empty response.

**Diagnosis:**
```python
from langchain.globals import set_debug
set_debug(True)

# Now run your chain — look for the "Entering Chain" / "Finished Chain" log lines
# and check the inputs and outputs at each step
result = chain.invoke({"question": "test"})

set_debug(False)
```

Also check variable names carefully — `{input}` in the template must match `"input"` in the dict passed to `.invoke()`. A mismatch raises `KeyError` which can be confused with a model failure.

---

#### Pitfall 3: Context Window Overflow in Conversational Chains

**Description:** The model's responses become incoherent or it repeats itself after many turns. No error is raised.

**Why it happens:** `RunnableWithMessageHistory` inserts the full message history at `MessagesPlaceholder`. As history grows, the total prompt length can exceed `num_ctx`. Ollama silently truncates older tokens, and the model loses the beginning of the conversation.

**Incorrect pattern:**
```python
# Running a long conversation without any trimming
chain_with_history = RunnableWithMessageHistory(chain, get_session_history, ...)
# After 20+ turns, early context is silently lost
```

**Correct pattern:**
```python
# Use trim_messages in get_session_history (see Section 4)
# Or add a manual warning based on message count
def get_session_history(session_id: str) -> ChatMessageHistory:
    history = session_store.setdefault(session_id, ChatMessageHistory())
    if len(history.messages) > 30:
        print(f"[Warning] Session {session_id} has {len(history.messages)} messages. "
              "Consider trimming history.")
    return history
```

---

#### Pitfall 4: Output Parser Failures

**Description:** `PydanticOutputParser` or `JsonOutputParser` raises `OutputParserException` because the model did not produce valid JSON.

**Why it happens:** Local models, especially smaller ones (3B–7B), do not always reliably produce well-formed JSON, particularly for complex schemas. The model may add explanatory text before or after the JSON, or produce malformed syntax.

**Incorrect pattern:**
```python
# Relying on the model to produce JSON without explicit instructions
parser = PydanticOutputParser(pydantic_object=PersonInfo)
chain = prompt | llm | parser
# If the model adds "Here is the JSON:" before the JSON block, parsing fails
```

**Correct pattern:**
```python
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

parser = PydanticOutputParser(pydantic_object=PersonInfo)

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a data extraction assistant. "
        "Extract structured data from text. "
        "Respond ONLY with valid JSON. Do not include any explanation, preamble, or markdown. "
        "{format_instructions}",
    ),
    ("human", "{text}"),
]).partial(format_instructions=parser.get_format_instructions())

chain = prompt | llm | parser

# If parsing still fails, add .with_retry() to the parser:
# chain = prompt | llm | parser.with_retry(stop_after_attempt=3)
```

Also use a low temperature (`temperature=0.0`) when structured output is required — this significantly reduces the rate of malformed JSON.

---

#### Pitfall 5: `langchain_community.ChatOllama` is Deprecated

**Description:** Importing `ChatOllama` from `langchain_community` triggers a deprecation warning.

**Why it happens:** The Ollama integration was moved from `langchain-community` to the dedicated `langchain-ollama` package as of `langchain-community` v0.3.1.

**Incorrect pattern:**
```python
# Old import — deprecated, will be removed in langchain-community 1.0.0
from langchain_community.chat_models import ChatOllama
```

**Correct pattern:**
```python
# Correct import — from the dedicated package
from langchain_ollama import ChatOllama
```

---

## Best Practices

1. **Always set `num_ctx` explicitly on `ChatOllama`.** The Ollama default of `2048` tokens is too small for chains that include conversation history, document context, or multi-step prompts. Use `num_ctx=4096` as a starting default and increase to `8192` only when your task requires it.

2. **Use `temperature=0.0` for structured output tasks.** When using `PydanticOutputParser`, `JsonOutputParser`, or `.with_structured_output()`, lower temperature dramatically reduces malformed responses. Set `temperature=0.0` and only raise it after confirming the parser works reliably.

3. **Name prompt template variables consistently.** The variable names in `ChatPromptTemplate.from_messages([..., ("human", "{input}")])` must exactly match the keys in the dict you pass to `.invoke()`. Use a single naming convention (e.g., always use `"input"` for the current user message and `"history"` for the history placeholder) across all chains in a project.

4. **Keep `set_debug` and `set_verbose` out of committed code.** These are development-only tools. Add them to a local debugging script, not to the main application. In production, use Python's `logging` module with LangChain's callback system instead.

5. **Use `RunnableWithMessageHistory` for all conversational chains — do not manage history manually.** The automatic save-and-load cycle eliminates a common class of bugs (forgetting to append the AI reply, incorrect key names) and makes it trivial to swap the history backend from in-memory to a database.

6. **Chunk documents before storing them — do not pass raw documents to the model.** A `PyPDFLoader` may return pages with 2000+ tokens each. Even if this fits in the context window, it wastes tokens on irrelevant content. Always split with `RecursiveCharacterTextSplitter` before any downstream use.

7. **Pin your LangChain package versions in requirements.txt.** `langchain`, `langchain-core`, and `langchain-ollama` release frequently. Interface changes between minor versions are possible in `langchain-community` (which does not follow strict semver). Pin versions for reproducible environments: `langchain==1.2.15`, `langchain-core==1.3.0`, `langchain-ollama==1.1.0`.

8. **Use `.get_graph().print_ascii()` when a chain produces unexpected results.** Before reaching for `set_debug`, inspect the chain graph first — sometimes the problem is that the chain is not structured the way you think.

---

## Hands-On Examples

### Example 1: Simple Q&A Chain with Streaming

A complete `ChatPromptTemplate` → `ChatOllama` → `StrOutputParser` chain with live streaming output. Before running, ensure Ollama is running and `llama3.2` is pulled.

```python
# example1_qa_chain.py

"""
A simple Q&A chain built with LCEL.
Demonstrates: ChatPromptTemplate, ChatOllama, StrOutputParser,
              invoke(), stream(), and batch().
"""

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ── Configuration ────────────────────────────────────────────────────────────
MODEL = "llama3.2"   # change to any model pulled with: ollama pull <model>

# ── Build the chain ───────────────────────────────────────────────────────────
llm = ChatOllama(
    model=MODEL,
    temperature=0.7,
    num_ctx=4096,
    num_predict=400,
)

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a knowledgeable Python educator. "
        "Answer clearly and concisely. "
        "Use a code example when it adds clarity.",
    ),
    ("human", "{question}"),
])

parser = StrOutputParser()

chain = prompt | llm | parser

# ── Part A: invoke() — blocking, returns full string ─────────────────────────
def demo_invoke() -> None:
    print("=== Part A: invoke() ===")
    result = chain.invoke({"question": "What is a Python context manager?"})
    print(result)
    print()


# ── Part B: stream() — non-blocking token stream ─────────────────────────────
def demo_stream() -> None:
    print("=== Part B: stream() ===")
    print("Answer: ", end="", flush=True)
    for chunk in chain.stream({"question": "Explain the difference between a list and a tuple."}):
        print(chunk, end="", flush=True)
    print("\n")


# ── Part C: batch() — multiple questions sequentially ────────────────────────
def demo_batch() -> None:
    print("=== Part C: batch() ===")
    questions = [
        {"question": "What does the 'yield' keyword do?"},
        {"question": "What is the difference between == and is?"},
    ]
    results = chain.batch(questions)
    for q, r in zip(questions, results):
        print(f"Q: {q['question']}")
        print(f"A: {r[:120]}...")
        print()


# ── Part D: inspect the chain graph ──────────────────────────────────────────
def demo_graph() -> None:
    print("=== Part D: chain graph ===")
    chain.get_graph().print_ascii()
    print()


if __name__ == "__main__":
    demo_invoke()
    demo_stream()
    demo_batch()
    demo_graph()
```

To run: `python example1_qa_chain.py`

The streaming part (Part B) prints tokens as they arrive from Ollama — the first token typically appears within one second even on CPU. Contrast this with Part A, where the full response waits until generation is complete before printing.

---

### Example 2: Structured Data Extraction with `PydanticOutputParser`

A chain that extracts structured fields from unstructured text using `PydanticOutputParser`. The example also shows how to handle parser failures gracefully.

```python
# example2_structured_extraction.py

"""
Extract structured data from unstructured text using PydanticOutputParser.
Demonstrates: PydanticOutputParser, get_format_instructions(),
              partial templates, and temperature=0.0 for reliability.
"""

from typing import Optional
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException


# ── Define the target schema ──────────────────────────────────────────────────
class JobPosting(BaseModel):
    """Structured representation of a job posting."""

    job_title: str = Field(description="The job title or role name")
    company: str = Field(description="Company or organisation name")
    location: str = Field(description="City and country, or 'Remote'")
    salary_range: Optional[str] = Field(
        default=None,
        description="Salary range as a string (e.g., '$80,000 - $100,000'), or null if not stated",
    )
    required_skills: list[str] = Field(
        description="List of required technical skills or technologies"
    )
    experience_years: Optional[int] = Field(
        default=None,
        description="Minimum years of experience required, or null if not stated",
    )


# ── Build the chain ───────────────────────────────────────────────────────────
llm = ChatOllama(
    model="llama3.2",
    temperature=0.0,    # critical: low temperature for reliable JSON output
    num_ctx=4096,
    num_predict=512,
)

parser = PydanticOutputParser(pydantic_object=JobPosting)

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a data extraction assistant. "
        "Extract the requested fields from the job posting text. "
        "Respond ONLY with valid JSON that matches the schema exactly. "
        "Do not add any explanation, preamble, or markdown code fences. "
        "\n\n{format_instructions}",
    ),
    ("human", "Extract information from this job posting:\n\n{text}"),
]).partial(format_instructions=parser.get_format_instructions())

chain = prompt | llm | parser


# ── Helper: run with graceful error handling ──────────────────────────────────
def extract_job_info(text: str) -> Optional[JobPosting]:
    """Run the extraction chain; return None and print the error on failure."""
    try:
        return chain.invoke({"text": text})
    except OutputParserException as e:
        print(f"[Parser error] The model did not produce valid JSON.\nDetails: {e}")
        return None
    except Exception as e:
        print(f"[Chain error] {e}")
        return None


# ── Test postings ─────────────────────────────────────────────────────────────
POSTING_1 = """
Senior Python Developer — Acme Corp (Berlin, Germany)

We are looking for an experienced Python developer to join our platform team.
You will build and maintain high-throughput data pipelines and REST APIs.

Requirements:
- 5+ years of Python experience
- Strong knowledge of FastAPI, SQLAlchemy, and PostgreSQL
- Experience with Docker and Kubernetes
- Familiarity with AWS (S3, Lambda, RDS)

Salary: €90,000 – €115,000 per year
Remote-friendly: hybrid (2 days in office per week)
"""

POSTING_2 = """
Junior ML Engineer — Startup (Remote)

Join our small AI team to help build the next generation of recommendation systems.
No experience required — we will train you.

Tech stack: Python, PyTorch, scikit-learn, Pandas, Git
"""

if __name__ == "__main__":
    for i, posting_text in enumerate([POSTING_1, POSTING_2], start=1):
        print(f"=== Posting {i} ===")
        result = extract_job_info(posting_text)
        if result is not None:
            print(f"Title:     {result.job_title}")
            print(f"Company:   {result.company}")
            print(f"Location:  {result.location}")
            print(f"Salary:    {result.salary_range or 'Not specified'}")
            print(f"Skills:    {', '.join(result.required_skills)}")
            print(f"Min years: {result.experience_years or 'Not specified'}")
        print()
```

To run: `python example2_structured_extraction.py`

The `format_instructions` are embedded in the system prompt via `.partial()`. This tells the model exactly what JSON schema to produce. Setting `temperature=0.0` is the single most effective change for reliable structured output from local models.

---

### Example 3: Multi-Turn Conversational Chain with History and Trimming

A complete conversational chain using `RunnableWithMessageHistory` with history trimming to prevent context window overflow.

```python
# example3_conversational_chain.py

"""
A multi-turn conversational chain with persistent (in-memory) history
and automatic history trimming to prevent context window overflow.

Demonstrates: RunnableWithMessageHistory, ChatMessageHistory,
              MessagesPlaceholder, trim_messages(), and interactive chat loop.
"""

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import trim_messages
from langchain_community.chat_message_histories import ChatMessageHistory


# ── Configuration ────────────────────────────────────────────────────────────
MODEL = "llama3.2"
MAX_HISTORY_TOKENS = 2500   # conservative limit within a 4096-token context window
SYSTEM_PROMPT = (
    "You are a knowledgeable and patient Python tutor. "
    "Build on previous answers in the conversation. "
    "Keep responses focused and under 200 words."
)

# ── Model and chain ───────────────────────────────────────────────────────────
llm = ChatOllama(model=MODEL, temperature=0.7, num_ctx=4096, num_predict=300)

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

chain = prompt | llm | StrOutputParser()

# ── History store ─────────────────────────────────────────────────────────────
_store: dict[str, ChatMessageHistory] = {}


def get_session_history(session_id: str) -> ChatMessageHistory:
    """
    Return the message history for a session, creating it if needed.
    Applies token-based trimming to keep the history within MAX_HISTORY_TOKENS.
    """
    if session_id not in _store:
        _store[session_id] = ChatMessageHistory()

    history = _store[session_id]

    # Only trim if there are messages to trim
    if history.messages:
        trimmed_messages = trim_messages(
            history.messages,
            max_tokens=MAX_HISTORY_TOKENS,
            strategy="last",          # keep the most recent turns
            token_counter=llm,        # use the model's token counting
            include_system=True,      # never drop the system message
            allow_partial=False,      # never split a message in half
            start_on="human",         # trimmed window must start with a human turn
        )
        # Replace the stored messages with the trimmed version
        history.messages = trimmed_messages

    return history


# ── Chain with history management ────────────────────────────────────────────
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)


# ── Non-interactive demo: scripted conversation ───────────────────────────────
def run_scripted_demo(session_id: str) -> None:
    """Run a scripted three-turn conversation to demonstrate history tracking."""
    config = {"configurable": {"session_id": session_id}}

    turns = [
        "What is a Python generator?",
        "Can you show me a simple example that yields the first five square numbers?",
        "How is that different from just returning a list of squares?",
    ]

    print(f"--- Scripted demo (session: {session_id}) ---\n")
    for question in turns:
        print(f"User: {question}")
        print("Assistant: ", end="", flush=True)

        # stream() works with RunnableWithMessageHistory
        for chunk in chain_with_history.stream({"input": question}, config=config):
            print(chunk, end="", flush=True)
        print("\n")

    # Show how many messages are in history after the session
    history = _store.get(session_id)
    if history:
        print(f"[History contains {len(history.messages)} messages after 3 turns]")


# ── Interactive REPL ──────────────────────────────────────────────────────────
def run_interactive(session_id: str) -> None:
    """Run an interactive chat loop with history tracking."""
    config = {"configurable": {"session_id": session_id}}
    print(f"Chat session: {session_id}")
    print("Type 'quit' or press Ctrl+C to exit.\n")

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

        print("Assistant: ", end="", flush=True)
        try:
            for chunk in chain_with_history.stream({"input": user_input}, config=config):
                print(chunk, end="", flush=True)
        except KeyboardInterrupt:
            print("\n[Generation interrupted]")
        print("\n")

        # Show current history depth
        history = _store.get(session_id)
        if history:
            print(f"  [History depth: {len(history.messages)} messages]\n")


if __name__ == "__main__":
    import sys

    if "--interactive" in sys.argv:
        run_interactive(session_id="interactive-session-1")
    else:
        run_scripted_demo(session_id="demo-session-1")
        print("\nRun with --interactive for a live chat session:")
        print("  python example3_conversational_chain.py --interactive")
```

To run the scripted demo: `python example3_conversational_chain.py`
To run the interactive chat: `python example3_conversational_chain.py --interactive`

The scripted demo's third question ("How is that different from just returning a list?") can only be answered coherently if the model has the full prior context from turns one and two. The history management in `get_session_history` guarantees this while automatically trimming old turns when `MAX_HISTORY_TOKENS` would be exceeded.

---

## Summary

- LangChain is a composability framework that standardises the interfaces between model providers, prompt templates, parsers, memory stores, and document loaders. Its primary value is letting you swap components without rewriting the surrounding code.
- The ecosystem is split across four packages: `langchain-core` (base interfaces and LCEL), `langchain-community` (community integrations including document loaders), `langchain-ollama` (the official Ollama integration), and `langchain` (high-level agents and orchestration). Current versions as of April 2026: `langchain==1.2.15`, `langchain-core==1.3.0`, `langchain-ollama==1.1.0`.
- LCEL (LangChain Expression Language) uses the `|` pipe operator to compose `Runnable` objects sequentially. Every `BaseChatModel`, `BasePromptTemplate`, and `BaseOutputParser` is a `Runnable`. Additional utilities — `RunnablePassthrough`, `RunnableLambda`, `RunnableParallel` — cover branching, custom functions, and passthrough patterns.
- `ChatOllama` exposes `.invoke()`, `.stream()`, and `.batch()` against a local Ollama server. Because it implements `BaseChatModel`, any chain built against this interface works unchanged with any other LangChain chat model — switching to a different local model or a cloud provider is a single-line change.
- Conversation history is managed by `RunnableWithMessageHistory` + `ChatMessageHistory`. The wrapper handles history fetch, injection at `MessagesPlaceholder`, and save after each call. Use `trim_messages()` inside the history factory function to prevent context window overflow in long sessions.
- Document loaders (`TextLoader`, `DirectoryLoader`, `PyPDFLoader`, `WebBaseLoader`) return `Document` objects; `RecursiveCharacterTextSplitter` breaks them into chunks for downstream use. Chunk size of 300–600 characters with 10–15% overlap is a practical starting point.
- For debugging chains: use `.get_graph().print_ascii()` to verify chain structure, `set_verbose(True)` to see inputs and outputs at each step, and `set_debug(True)` to inspect full prompt text. Never commit code with these enabled.
- For structured output from local models: set `temperature=0.0`, embed `parser.get_format_instructions()` in the system prompt, wrap the parser step in a try/except for `OutputParserException`, and prefer `PydanticOutputParser` over manual JSON parsing.

---

## Further Reading

- [LangChain Python Documentation — Overview](https://docs.langchain.com/oss/python/langchain/overview) — The authoritative reference for the `langchain` package (v1.2.x). Covers LCEL, agents, chains, memory, and all core abstractions. The primary reference for any API question not answered in this module.
- [langchain-ollama PyPI page](https://pypi.org/project/langchain-ollama/) — Official distribution page for `langchain-ollama` (current: v1.1.0, released April 7, 2026). Contains the package description, dependencies, and links to the source repository. Check here to confirm you are on the latest version.
- [ChatOllama Integration Reference](https://reference.langchain.com/python/langchain-ollama/chat_models/ChatOllama) — Full API reference for the `ChatOllama` class: all constructor parameters, methods, and return types. The authoritative source for `ChatOllama` configuration options beyond what is covered in this module.
- [LangChain Expression Language (LCEL) — Conceptual Guide](https://www.aurelio.ai/learn/langchain-lcel) — A practical walkthrough of LCEL composition patterns with working code examples: pipe operator, `RunnablePassthrough`, `RunnableParallel`, and common debugging patterns. Recommended reading after completing this module.
- [LangChain — How to Add Message History](https://docs.langchain.com/oss/python/langchain/how-tos/message-history) — Official how-to guide for `RunnableWithMessageHistory`, covering session management, different history backends (in-memory, database), and the `configurable` pattern for multi-user applications.
- [RecursiveCharacterTextSplitter API Reference](https://python.langchain.com/api_reference/text_splitters/character/langchain_text_splitters.character.RecursiveCharacterTextSplitter.html) — Full parameter reference for `RecursiveCharacterTextSplitter`: `chunk_size`, `chunk_overlap`, `separators`, `length_function`, and all methods including `split_documents()` and `create_documents()`.
- [LangChain and LangGraph Agent Frameworks Reach v1.0](https://www.langchain.com/blog/langchain-langgraph-1dot0) — The official announcement of LangChain's v1.0 milestone, explaining the architectural shift from monolithic Chains to the Runnable interface and the stability commitment (no breaking changes until v2.0).
- [DSPy — Programmatic Prompt Optimisation (Stanford)](https://dspy.ai) — The project site for DSPy, the programmatic prompt optimisation framework listed in the comparison table. Provides the authoritative explanation of what makes DSPy architecturally different from LangChain and when its compile-and-optimise model is the right choice.
- [LlamaIndex Documentation](https://docs.llamaindex.ai) — The official documentation for LlamaIndex, the primary alternative to LangChain for data-heavy RAG applications. Skimming the "Getting Started" section gives a concrete feel for how its data-centric abstractions (indexes, query engines) differ from LangChain's chain-centric model.
