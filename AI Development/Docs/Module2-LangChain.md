# Module 2: The LangChain Framework
> Subject: AI Development | Difficulty: Intermediate | Estimated Time: 240 minutes

## Objective

After completing this module you will be able to explain what LangChain is, how its packages fit together, and what problem it solves over the raw SDK approach from Module 1. You will understand the LCEL pipe operator and the Runnable interface, build a multi-turn chatbot with persistent memory using `RunnableWithMessageHistory`, swap between Anthropic, OpenAI, and Ollama providers by changing a single line of code, and articulate when LangChain is the right tool versus when the raw SDK is the better choice.

---

## Prerequisites

- Completed Module 1: Building a Basic AI Chatbot with No Framework — this module builds directly on the messages array, streaming, and raw SDK patterns covered there
- Python 3.10 or later (LangChain 1.x dropped support for older versions)
- At least one API key: Anthropic (`ANTHROPIC_API_KEY`) or OpenAI (`OPENAI_API_KEY`). Local-only examples use Ollama, which requires a running Ollama server
- Familiarity with Python type hints and Pydantic models (basic usage only — you do not need to be an expert)
- A virtual environment workflow — all packages below should be installed into an isolated environment, not system Python

---

## Key Concepts

### 1. What LangChain Is and the Problem It Solves

In Module 1 you wrote a multi-turn chatbot from scratch. You managed the messages array by hand, wrote retry logic around `anthropic.APIStatusError`, serialized history to JSON, and implemented a sliding-window trimmer. That is roughly 200 lines of boilerplate that every chatbot project re-implements, with slightly different bugs each time.

LangChain is an open-source framework — first released October 2022 by Harrison Chase — built to eliminate that boilerplate by providing a standardised set of composable primitives for working with LLMs. It is not a model itself; it is the plumbing between your application code and the models.

#### The Three Core Problems LangChain Solves

**1. Provider lock-in.** Every provider SDK (`anthropic`, `openai`, `ollama`) has a different API shape. Switching from Claude to GPT-4o in raw SDK code means rewriting your message-building logic, your streaming loop, your error handling, and your history management. In LangChain, `ChatAnthropic`, `ChatOpenAI`, and `ChatOllama` all implement the identical `BaseChatModel` interface — the same `.invoke()`, `.stream()`, and `.batch()` methods with the same signatures. Swapping providers is a one-line change.

**2. Composition boilerplate.** Building a prompt, calling the model, parsing the response, and feeding the output into the next step involves repetitive wiring code. LangChain's LCEL pipe operator (`|`) lets you declare that pipeline as a single expression:
```python
chain = prompt | model | output_parser
```
That one line creates an object that automatically supports streaming, batching, async, retries, and fallbacks — none of which you write yourself.

**3. Memory management.** Maintaining conversation history — appending messages, injecting them into the prompt, trimming when the context window fills — is the most tedious part of chatbot code. `RunnableWithMessageHistory` wraps any chain and handles all of it, including multi-session isolation, without changing the chain's code.

#### What LangChain Is NOT

- LangChain is not a model. It never does inference itself — every `.invoke()` call ultimately reaches an LLM API or a local model.
- LangChain is not magic. Every abstraction it provides maps directly to raw API calls. If something behaves unexpectedly, enabling debug logging (`langchain.debug = True`) reveals the exact messages sent and received.
- LangChain is not always the right choice. For a single-prompt, one-shot script, the raw SDK from Module 1 is simpler. Add LangChain when you need at least two of: memory, chaining, structured output parsing, or provider portability.

#### LangChain vs Raw SDK Decision Guide

| Situation | Recommendation |
|---|---|
| One-off script, single API call | Raw SDK (Module 1) |
| Multi-turn chatbot with memory | LangChain |
| Prototype where you will switch providers | LangChain |
| Simple production endpoint, one provider, no switching | Raw SDK |
| Structured output extraction pipeline | LangChain (`PydanticOutputParser`) |
| Strict latency budget, minimal dependencies | Raw SDK |
| Team project where multiple people write prompt logic | LangChain (standardised interface) |

### 2. Package Architecture in LangChain 1.x

LangChain's package structure was reorganized when v0.3 shipped in September 2024 and again refined in v1.0 (November 2025). Understanding the split prevents confusing import errors.

| Package | Current Version | Purpose |
|---|---|---|
| `langchain-core` | 1.2.26 | Base abstractions: `Runnable`, message types, `BaseChatModel`, prompt templates, output parsers. No LLM calls happen here. |
| `langchain` | 1.2.15 | Chain helpers and higher-level utilities. Depends on `langchain-core`. |
| `langchain-openai` | 1.1.12 | `ChatOpenAI`. Official OpenAI integration. |
| `langchain-anthropic` | 1.0.0 | `ChatAnthropic`. Official Anthropic integration. |
| `langchain-ollama` | 1.0.1 | `ChatOllama`. Local model integration via Ollama. |
| `langchain-community` | 0.4.1 | Community-contributed integrations: loaders, tools, and third-party model providers. |
| `python-dotenv` | 1.0+ | Loads `.env` files into the environment at startup. |

The key mental model: `langchain-core` defines the interfaces; provider packages implement them; `langchain` and `langgraph` build higher-level workflows on top.

### 3. LCEL: The Pipe Operator and the Runnable Interface

LCEL (LangChain Expression Language) is the composition system that ships in `langchain-core`. Its central idea is that every component — prompt templates, models, parsers, custom functions — implements the `Runnable` interface.

The `Runnable` interface guarantees:

```
.invoke(input)          → single output (blocking)
.stream(input)          → iterator of output chunks
.batch([input1, ...])   → list of outputs run in parallel
.ainvoke(input)         → async version of invoke
.astream(input)         → async version of stream
```

The `|` operator wires two `Runnable` objects into a `RunnableSequence`. The output of the left side becomes the input to the right side:

```python
chain = prompt | model | parser
result = chain.invoke({"topic": "black holes"})
```

This is equivalent to `parser.invoke(model.invoke(prompt.invoke({"topic": "black holes"})))`, but `RunnableSequence` adds automatic streaming, error propagation, and LangSmith tracing throughout the entire pipeline.

**Comparison with Module 1 raw SDK equivalent:**

```python
# Module 1 raw SDK — three separate steps, no composability
formatted = f"Explain {topic} in two sentences."
response = client.messages.create(model="claude-haiku-4-5", max_tokens=256,
                                   messages=[{"role": "user", "content": formatted}])
text = response.content[0].text

# LangChain LCEL — same logic, composable and streaming-ready
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_anthropic import ChatAnthropic

prompt = ChatPromptTemplate.from_template("Explain {topic} in two sentences.")
model = ChatAnthropic(model="claude-haiku-4-5", max_tokens=256)
parser = StrOutputParser()

chain = prompt | model | parser
text = chain.invoke({"topic": "black holes"})
```

The LCEL version requires more setup but enables streaming, batching, and chaining with additional steps by appending more `|` segments.

### 4. Chat Models, Prompt Templates, and Output Parsers

These three types are the building blocks of every LCEL chain.

**Chat models** wrap the provider API. They accept a list of `BaseMessage` objects and return an `AIMessage`. All three major providers use the same interface:

```python
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

# Anthropic — reads ANTHROPIC_API_KEY from environment
model = ChatAnthropic(model="claude-haiku-4-5", max_tokens=1024, temperature=0.7)

# OpenAI — reads OPENAI_API_KEY from environment
model = ChatOpenAI(model="gpt-4o-mini", max_tokens=1024, temperature=0.7)

# Ollama — connects to local server at http://localhost:11434
model = ChatOllama(model="llama3.2", temperature=0.7)

# All three support the same call pattern:
from langchain_core.messages import HumanMessage, SystemMessage

response = model.invoke([
    SystemMessage(content="You are a concise assistant."),
    HumanMessage(content="What is the speed of light?"),
])
print(response.content)  # "The speed of light in a vacuum is approximately 299,792 km/s."
```

**Prompt templates** format input variables into a structured message list. `ChatPromptTemplate.from_messages()` is the most flexible constructor:

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert in {domain}. Answer concisely."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])
```

`MessagesPlaceholder` reserves a slot in the message list that will be filled with a list of messages at invoke time — used for conversation history.

**Output parsers** transform the `AIMessage` returned by the model into a more useful Python type. Three parsers cover most use cases:

```python
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

# StrOutputParser — extracts .content as a plain string
str_parser = StrOutputParser()

# JsonOutputParser — instructs the model to emit JSON and parses it to dict
json_parser = JsonOutputParser()

# PydanticOutputParser — validates the JSON against a Pydantic schema
class BookReview(BaseModel):
    title: str = Field(description="Book title")
    rating: int = Field(description="Rating from 1 to 5")
    summary: str = Field(description="One-sentence summary")

pydantic_parser = PydanticOutputParser(pydantic_object=BookReview)

# PydanticOutputParser injects format instructions into the prompt
print(pydantic_parser.get_format_instructions())
```

### 5. Memory and Conversation History

In Module 1 you maintained conversation history as a Python list and passed it explicitly to every API call. LangChain's memory system automates this with `RunnableWithMessageHistory`.

The pattern requires three pieces:

1. A **session store** — a dictionary mapping session IDs to `InMemoryChatMessageHistory` objects.
2. A **factory function** that takes a session ID string and returns the history for that session.
3. A **`RunnableWithMessageHistory` wrapper** that knows which input key carries the user's message and which prompt slot expects the history.

```python
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

store: dict[str, InMemoryChatMessageHistory] = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]
```

Wrapping a chain:

```python
chain_with_history = RunnableWithMessageHistory(
    chain,                          # any LCEL chain
    get_session_history,            # factory function
    input_messages_key="input",     # key in the invoke() dict that holds user text
    history_messages_key="history", # MessagesPlaceholder variable_name in the prompt
)

config = {"configurable": {"session_id": "user-abc"}}
response = chain_with_history.invoke({"input": "Hello, my name is Alice."}, config=config)
```

Every call automatically reads existing history from the store, injects it into the prompt, runs the chain, and appends both the user message and the AI response back to the store. Different session IDs maintain completely separate histories — important for multi-user applications.

**Trimming history** prevents context overflow using `trim_messages`:

```python
from langchain_core.messages import trim_messages

trimmer = trim_messages(
    max_tokens=2000,
    strategy="last",          # keep the most recent messages
    token_counter=model,      # uses the model's own tokenizer
    include_system=True,      # always keep the system message
    allow_partial=False,
    start_on="human",         # the trimmed window must start with a human turn
)
```

`trim_messages` is itself a `Runnable`, so it can be inserted into an LCEL chain:

```python
chain = (
    RunnablePassthrough.assign(history=lambda x: trimmer.invoke(x["history"]))
    | prompt
    | model
    | StrOutputParser()
)
```

---

## Best Practices

1. **Install only the provider package you need.** `langchain-community` pulls in dozens of optional dependencies; installing the entire ecosystem for one provider wastes space and risks version conflicts. Use `langchain-anthropic` or `langchain-openai` directly.

2. **Keep `langchain-core` and your provider package versions aligned.** `langchain-core` releases frequently; a version mismatch between it and `langchain-anthropic` causes cryptic `AttributeError` failures on common methods like `.invoke()`.

3. **Avoid deprecated chain classes entirely.** `LLMChain` and `ConversationChain` live in the legacy `langchain-classic` package. Do not use them in new code — they receive no bug fixes and will be removed in v2.

4. **Never put raw API keys in source code.** Use `python-dotenv` to load a `.env` file that is excluded from version control via `.gitignore`. LangChain provider packages read standard environment variable names (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) automatically.

5. **Use `session_id` in `RunnableWithMessageHistory` to isolate users.** If two users share the same session ID their conversation histories will be merged, producing confusing context contamination in production.

6. **Test chains in isolation before composing them.** Call `prompt.invoke({"input": "test"})` and `model.invoke(messages)` separately before wiring them together with `|`. This makes it trivial to identify which stage of a chain is producing unexpected output.

7. **Pin all LangChain package versions in `requirements.txt`.** LangChain releases frequently, and minor versions sometimes change default behavior. Unpinned installs across environments cause hard-to-reproduce bugs.

---

## Use Cases

### Customer Support Chatbot with Persistent Sessions

A SaaS product needs a support chatbot that remembers context within a support session — for example, the user already said they are on the Pro plan and use Windows. Without memory, the user has to repeat this context on every message.

`RunnableWithMessageHistory` with a unique `session_id` per support ticket handles the persistence. The chain prompt includes a `MessagesPlaceholder` for history, and `trim_messages` ensures the context window does not grow unbounded across very long support threads. The provider-agnostic chat model interface means the team can start with `ChatOpenAI` and switch to `ChatAnthropic` later with a one-line change.

### Structured Data Extraction Pipeline

A data pipeline ingests unstructured product review text and needs to produce structured JSON records with fields for `product_name`, `rating` (1–5), and `sentiment` ("positive"/"negative"/"neutral").

An LCEL chain with a `PydanticOutputParser` and a `ChatPromptTemplate` that includes `get_format_instructions()` in the system message reliably extracts structured output. The chain runs in `.batch()` mode across thousands of reviews concurrently, which is not available in the Module 1 raw SDK pattern without writing explicit thread pool code.

---

## Hands-on Examples

### Example 1: Multi-Turn Chatbot with Memory (Ollama — Local First)

This example builds the same multi-turn chatbot from Module 1, but using LCEL and `RunnableWithMessageHistory`. It uses a local Ollama model so no API key is required. Compare the structure to Module 1's raw SDK version to see what the framework is handling for you.

**Step 1.** Install Ollama and pull the model. Then install dependencies.

```bash
# Install Ollama first: https://ollama.com/download
ollama pull llama3.2

mkdir langchain-chatbot && cd langchain-chatbot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install langchain langchain-core langchain-ollama python-dotenv
```

**Step 2.** Create `chatbot.py`.

```python
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

# Pull model first: ollama pull llama3.2
model = ChatOllama(model="llama3.2", temperature=0.7)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Be concise and friendly."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

chain = prompt | model | StrOutputParser()

store: dict[str, InMemoryChatMessageHistory] = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

config = {"configurable": {"session_id": "demo-session"}}

print("Chatbot ready (Ollama / llama3.2). Type 'quit' to exit.")
while True:
    user_input = input("You: ").strip()
    if user_input.lower() == "quit":
        break
    if not user_input:
        continue
    response = chain_with_history.invoke({"input": user_input}, config=config)
    print(f"Assistant: {response}")
```

**Step 3.** Run the chatbot and test memory.

```bash
python chatbot.py
```

Expected interaction:

```
Chatbot ready (Ollama / llama3.2). Type 'quit' to exit.
You: My name is Jordan.
Assistant: Hi Jordan! Nice to meet you. How can I help you today?
You: What is my name?
Assistant: Your name is Jordan!
You: quit
```

The key difference from Module 1: you wrote zero code to maintain the messages list. `RunnableWithMessageHistory` handles appending user messages, injecting history into the prompt, and appending assistant responses.

---

#### Cloud API Alternative (Optional)

If you prefer to run the same chatbot against Anthropic Claude instead of a local model, only the model initialisation line changes. The chain, memory, and conversation loop are completely unchanged — this is provider portability in action.

```bash
pip install langchain-anthropic python-dotenv
```

Create a `.env` file:
```
ANTHROPIC_API_KEY=your-key-here
```

Replace the model line in `chatbot.py`:

```python
# --- Optional: Cloud API alternative (Anthropic) ---
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

# Replace the ChatOllama line with:
model = ChatAnthropic(model="claude-haiku-4-5", max_tokens=1024, temperature=0.7)
```

No other lines change. Run `python chatbot.py` — the conversation loop works identically, but inference runs on Anthropic's servers and consumes API credits.

---

### Example 2: Provider Portability Demonstrated

This example shows all three providers side by side in a single file, making it explicit that swapping providers is a one-line change. It requires `llama3.2` pulled locally and (optionally) API keys for cloud providers.

**Step 1.** Install all providers.

```bash
ollama pull llama3.2
pip install langchain langchain-core langchain-ollama langchain-anthropic langchain-openai python-dotenv
```

**Step 2.** Create `provider_comparison.py`.

```python
import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

load_dotenv()

# ── LOCAL (primary — no API key needed) ──────────────────────────────────────
# Pull model first: ollama pull llama3.2
local_model = ChatOllama(model="llama3.2", temperature=0.7)

# ── CLOUD API ALTERNATIVES (optional) ────────────────────────────────────────
# Uncomment whichever you want to test; comment out local_model above.

# from langchain_anthropic import ChatAnthropic
# cloud_model = ChatAnthropic(model="claude-haiku-4-5", max_tokens=1024, temperature=0.7)

# from langchain_openai import ChatOpenAI
# cloud_model = ChatOpenAI(model="gpt-4o-mini", max_tokens=1024, temperature=0.7)

# Active model — change this single line to switch providers
active_model = local_model   # swap to cloud_model to use a cloud API

# ── CHAIN (identical regardless of provider) ─────────────────────────────────
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Be concise and friendly."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

chain = prompt | active_model | StrOutputParser()

store: dict[str, InMemoryChatMessageHistory] = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

config = {"configurable": {"session_id": "demo-session"}}

print("Chatbot ready. Type 'quit' to exit.")
while True:
    user_input = input("You: ").strip()
    if user_input.lower() == "quit":
        break
    if not user_input:
        continue
    response = chain_with_history.invoke({"input": user_input}, config=config)
    print(f"Assistant: {response}")
```

Response speed with `llama3.2` (3B parameter model) on a modern laptop CPU: roughly 5–20 tokens per second. On GPU hardware or with a 1B model (`llama3.2:1b`) it is noticeably faster.

---

## Common Pitfalls

### Pitfall 1: Using Legacy Chain Classes

**Mistake:** Following older tutorials that use `LLMChain` or `ConversationChain`.

**Why it happens:** A large portion of LangChain tutorials on the web were written before v0.3 and have not been updated. Search results for "LangChain chatbot tutorial" often return pre-2024 content.

**Incorrect:**
```python
from langchain.chains import LLMChain, ConversationChain
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory()
chain = ConversationChain(llm=model, memory=memory)
```

**Correct:**
```python
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory

chain_with_history = RunnableWithMessageHistory(chain, get_session_history, ...)
```

### Pitfall 2: Missing `MessagesPlaceholder` in the Prompt

**Mistake:** Using `RunnableWithMessageHistory` without a `MessagesPlaceholder` in the prompt template.

**Why it happens:** The wrapper tries to inject history into the prompt by substituting the `history_messages_key` slot, but if no slot exists, the injection silently fails and the model receives no history.

**Incorrect:**
```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are helpful."),
    ("human", "{input}"),
])
# History will not appear in the prompt — the model has no memory
```

**Correct:**
```python
from langchain_core.prompts import MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are helpful."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])
```

### Pitfall 3: Version Mismatch Between `langchain-core` and Provider Packages

**Mistake:** Running `pip install langchain-anthropic` without pinning versions, then updating `langchain-core` separately.

**Why it happens:** `pip` resolves packages independently. A newer `langchain-core` can introduce interface changes that a not-yet-updated `langchain-anthropic` does not implement, causing `AttributeError` on `.invoke()` or `.stream()`.

**Incorrect (unpinned):**
```bash
pip install langchain-core
pip install langchain-anthropic
```

**Correct (pinned in requirements.txt):**
```
langchain-core==1.2.26
langchain-anthropic==1.0.0
langchain==1.2.15
```

### Pitfall 4: Not Including Format Instructions in the Prompt When Using `PydanticOutputParser`

**Mistake:** Creating a `PydanticOutputParser` and using it in a chain without calling `get_format_instructions()` in the prompt.

**Why it happens:** The parser validates the model output against a schema, but unless the prompt tells the model what JSON format to emit, it will respond in natural language and the parser will raise a `ValidationError`.

**Incorrect:**
```python
parser = PydanticOutputParser(pydantic_object=BookReview)
prompt = ChatPromptTemplate.from_template("Review this book: {book_title}")
chain = prompt | model | parser  # model has no idea it should emit JSON
```

**Correct:**
```python
parser = PydanticOutputParser(pydantic_object=BookReview)
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a book critic. {format_instructions}"),
    ("human", "Review this book: {book_title}"),
]).partial(format_instructions=parser.get_format_instructions())
chain = prompt | model | parser
```

### Pitfall 5: Calling `.invoke()` on a `RunnableWithMessageHistory` Without a `config`

**Mistake:** Invoking the history-wrapped chain without passing the `config` dict containing `session_id`.

**Why it happens:** The `session_id` parameter is not a positional argument — it is passed through `config`. Forgetting it raises a `KeyError` inside the factory function or silently creates a default session that all calls share.

**Incorrect:**
```python
response = chain_with_history.invoke({"input": "Hello"})  # missing config
```

**Correct:**
```python
config = {"configurable": {"session_id": "user-123"}}
response = chain_with_history.invoke({"input": "Hello"}, config=config)
```

---

## Summary

- LangChain abstracts the messages array management, provider differences, and boilerplate retry logic that you implemented manually in Module 1, at the cost of a larger dependency surface and additional indirection during debugging.
- LCEL's pipe operator composes any `Runnable` objects — prompt templates, models, output parsers, or custom functions — into a `RunnableSequence` that supports `.invoke()`, `.stream()`, and `.batch()` without extra code.
- `RunnableWithMessageHistory` replaces manual conversation history management from Module 1 by automatically injecting session history into the prompt and appending new turns to the session store.
- Switching between Anthropic, OpenAI, and local Ollama is a single line change — the chain and memory logic stays identical across all three providers.
- Use LangChain when you need provider portability, memory, or output parsing. Use the raw SDK from Module 1 when you need a single provider, a single prompt call, and minimal dependencies.

---

## Further Reading

- [LangChain Python Documentation](https://docs.langchain.com/) — The official docs covering all current abstractions, how-to guides, and tutorials; start here for any concept not covered in this module.
- [Announcing LangChain v0.3](https://blog.langchain.com/announcing-langchain-v0-3/) — The official blog post detailing the Pydantic v2 migration, package restructuring, and LCEL improvements that define the current architecture.
- [LangChain Expression Language (LCEL) Conceptual Guide](https://python.langchain.com/docs/concepts/lcel/) — Deep dive into the `Runnable` interface, `RunnableParallel`, `RunnableLambda`, streaming behavior, and the full composition model.
- [langchain-core PyPI page](https://pypi.org/project/langchain-core/) — Authoritative version history and release notes; check here when diagnosing compatibility issues between `langchain-core` and provider packages.
- [langchain-anthropic PyPI page](https://pypi.org/project/langchain-anthropic/) — Version history and changelog for the Anthropic integration package, including when new Claude models are added.
- [How to trim messages](https://python.langchain.com/docs/how_to/trim_messages/) — Official guide to `trim_messages` including strategy options, token counting configuration, and integration patterns with `RunnableWithMessageHistory`.
