# Module 3: AI Workflows and LangGraph

> Subject: AI Development | Difficulty: Intermediate-Advanced | Estimated Time: 300 minutes

## Objective

After completing this module you will be able to explain why graph-based workflow engines are necessary when linear LCEL chains fall short, and you will know the full LangGraph mental model: `StateGraph`, typed state, nodes, edges, conditional routing, checkpointers, and streaming. You will build four working applications from scratch: a three-node linear pipeline, an intent-router that branches to specialist nodes, a ReAct agent loop with tool calling, and a human-in-the-loop content-approval workflow. You will also understand persistence with `InMemorySaver` and `SqliteSaver`, multi-session state via `thread_id`, and the three streaming modes (`values`, `updates`, `messages`).

---

## Prerequisites

- Completed Module 2: The LangChain Framework — this module builds directly on LCEL chains, `ChatAnthropic`/`ChatOllama`, `ChatPromptTemplate`, `StrOutputParser`, and the `Runnable` interface
- Python 3.10 or later (LangGraph 1.x requires Python 3.10+, and Python 3.13 is now supported)
- At least one API key: Anthropic (`ANTHROPIC_API_KEY`) or OpenAI (`OPENAI_API_KEY`). Local examples work with Ollama
- Comfortable reading Python type hints — `TypedDict`, `Annotated`, and `Literal` appear throughout this module
- A virtual environment workflow — install all packages in an isolated environment

---

## Key Concepts

### 1. Why Linear Chains Are Not Enough

In Module 2 you built LCEL chains with the pipe operator:

```python
chain = prompt | model | StrOutputParser()
```

This works beautifully when processing is strictly sequential and always follows the same path. But real applications need more:

- **Branching:** "If the model detected an error, send to the retry node; otherwise send to the formatting node."
- **Loops:** "Keep calling the tool node until the model decides it is done." LCEL has no native concept of a loop.
- **Human-in-the-loop:** "Pause here and wait for a human to approve this output before continuing."
- **Parallel execution:** "Call the research node and the summarization node at the same time, then merge their outputs."
- **State persistence:** "This workflow was interrupted mid-run; resume it from the exact node where it stopped."

None of these patterns are expressible with a linear `RunnableSequence`. They require a graph — a data structure with nodes, directed edges, and the ability to route conditionally between them.

#### From Chains to Graphs

| Concept | LCEL Chain | LangGraph |
|---|---|---|
| Structure | Linear sequence (`A → B → C`) | Directed graph (any topology) |
| Branching | Not supported natively | Conditional edges with router functions |
| Loops | Not supported | Cycles in the graph |
| State | Passed through `invoke()` input/output | Typed shared state dict that persists between nodes |
| Persistence | None built-in | Checkpointers (`InMemorySaver`, `SqliteSaver`) |
| Pause / resume | Not supported | `interrupt()`, `interrupt_before`, `interrupt_after` |
| Human input | Not supported | State update before resume |

LangGraph does not replace LCEL — each node in a LangGraph graph can itself be an LCEL chain. The two tools complement each other: LCEL handles the logic inside a node; LangGraph handles the orchestration between nodes.

---

### 2. LangGraph Core Concepts

#### What LangGraph Is

LangGraph is a low-level graph execution engine and runtime for building stateful, long-running AI workflows. It was built by the LangChain team but is architecturally independent — you can use LangGraph without using LangChain at all, or you can use LangChain components (like `ChatAnthropic` from Module 2) inside LangGraph nodes. The current stable version as of April 2026 is **1.1.6**.

#### StateGraph: The Central Abstraction

`StateGraph` is the class you interact with to build a graph. It takes a schema — a `TypedDict` subclass — and creates a typed state container that flows through every node.

```python
from langgraph.graph import StateGraph, START, END

class MyState(TypedDict):
    input_text: str
    processed: bool
    output: str

builder = StateGraph(MyState)
```

Every node in the graph receives the current state and returns a partial state update — a dict containing only the keys it wants to change. LangGraph merges the returned dict into the shared state before passing it to the next node.

#### Nodes

A node is any Python callable (a function or a class with `__call__`) that takes the current state and returns a dict of state updates.

```python
def my_node(state: MyState) -> dict:
    # Read from state
    text = state["input_text"]
    # Do work
    result = text.upper()
    # Return only the keys you are updating — not the full state
    return {"output": result, "processed": True}
```

Nodes are added to the graph with `add_node()`. The node name defaults to the function's `__name__` if you do not provide one:

```python
builder.add_node("my_node", my_node)   # explicit name
builder.add_node(my_node)              # name inferred as "my_node"
```

#### Edges

Edges define the flow between nodes. There are two kinds:

**Unconditional edges** always route from one specific node to another:

```python
builder.add_edge(START, "first_node")    # START is the built-in entry sentinel
builder.add_edge("first_node", "second_node")
builder.add_edge("second_node", END)     # END is the built-in termination sentinel
```

**Conditional edges** call a router function that inspects the current state and returns a string naming the next node:

```python
def route(state: MyState) -> str:
    if state["processed"]:
        return "output_node"
    return "retry_node"

builder.add_conditional_edges("my_node", route, ["output_node", "retry_node"])
```

The third argument to `add_conditional_edges` is the list of all possible destination node names. LangGraph validates at compile time that every string the router can return is in this list.

#### Entry Point and END

`START` and `END` are imported from `langgraph.graph`. `START` is the implicit source node that feeds into your first real node. You wire `START` to your entry node with `add_edge(START, "node_name")`. `END` is the implicit sink — routing to `END` terminates the graph run.

#### Compiling a Graph

`builder.compile()` validates the graph structure and returns a `CompiledGraph` object, which is itself a `Runnable` and therefore supports `.invoke()`, `.stream()`, `.batch()`, `.ainvoke()`, and `.astream()`:

```python
graph = builder.compile()

# Same interface as any LangChain Runnable from Module 2
result = graph.invoke({"input_text": "hello", "processed": False, "output": ""})
```

Compiling validates that every node referenced in an edge exists, that `START` has an outgoing edge, and that every node has a path to `END`. Errors surface at compile time, not at runtime.

#### Checkpointers: Persisting State Across Invocations

A checkpointer saves a complete snapshot of the graph state after every node execution. This enables three critical capabilities: resuming an interrupted run, supporting human-in-the-loop pauses, and multi-turn conversations where each invocation builds on the last.

LangGraph ships with two checkpointers out of the box:

**`InMemorySaver`** — stores checkpoints in a Python dict. Resets when the process restarts. Use it during development and in automated tests.

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
```

**`SqliteSaver`** — stores checkpoints in a SQLite file on disk. Survives process restarts. Use it for local production-grade persistence. Requires the separate `langgraph-checkpoint-sqlite` package.

```python
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
graph = builder.compile(checkpointer=checkpointer)
```

---

### 3. Building Blocks

#### Defining State with TypedDict and Annotated

The state schema is a `TypedDict`. Each field has a type annotation and an optional **reducer** — a function that tells LangGraph how to merge a new value into the existing value for that field.

Without a reducer, LangGraph replaces the old value with the new one:

```python
from typing_extensions import TypedDict

class SimpleState(TypedDict):
    count: int    # New value from a node replaces the old value
    name: str     # New value replaces old value
```

With a reducer via `Annotated`, you can instead accumulate:

```python
from typing import Annotated
from typing_extensions import TypedDict
import operator

class AccumulatingState(TypedDict):
    count: Annotated[int, operator.add]       # New value is ADDED to existing
    names: Annotated[list, operator.add]      # New list is CONCATENATED to existing
```

#### The `add_messages` Reducer

For conversational workflows, LangGraph ships a special reducer called `add_messages`. It appends new messages to the list and also handles message deduplication by `id` (updating an existing message if you send a new one with the same id):

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class MessagesState(TypedDict):
    messages: Annotated[list, add_messages]
```

Because this pattern is so common, LangGraph also provides a built-in `MessagesState` class that you can subclass or use directly:

```python
from langgraph.graph import MessagesState   # pre-built equivalent of the above
```

When a node returns `{"messages": [new_message]}`, `add_messages` appends `new_message` to the existing list rather than replacing the list. This is how multi-turn conversation state accumulates automatically without any manual list management.

#### Writing Node Functions

Node functions follow one strict rule: they receive the full state dict and return a dict containing only the keys they want to update. They must not mutate the state dict directly.

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage

model = ChatAnthropic(model="claude-haiku-4-5", max_tokens=1024)

def call_llm(state: MessagesState) -> dict:
    response: AIMessage = model.invoke(state["messages"])
    return {"messages": [response]}   # add_messages will append this
```

#### Conditional Edges with Router Functions

A router function takes the current state and returns a string. That string is matched against the list of possible next nodes you declared in `add_conditional_edges`:

```python
from typing import Literal

def should_use_tools(state: MessagesState) -> Literal["tool_node", "__end__"]:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tool_node"
    return "__end__"   # END is also reachable as the string "__end__"

builder.add_conditional_edges("call_llm", should_use_tools, ["tool_node", END])
```

#### `RunnableConfig` and `thread_id` for Multi-Session State

When a graph is compiled with a checkpointer, every invocation must include a `config` dict with a `thread_id`. LangGraph uses the `thread_id` to load the correct checkpoint before the run and save a new checkpoint after it. Two invocations with the same `thread_id` share state; two invocations with different `thread_id` values are completely isolated sessions.

```python
from langchain_core.runnables import RunnableConfig

config: RunnableConfig = {"configurable": {"thread_id": "user-session-42"}}

result = graph.invoke({"messages": [HumanMessage(content="Hello")]}, config=config)

# Second call resumes from the same thread's checkpoint
result2 = graph.invoke({"messages": [HumanMessage(content="Remember me?")]}, config=config)
```

---

### 4. Common Workflow Patterns

#### Pattern 1: Linear Workflow

The simplest pattern — every input flows through the same nodes in the same order every time:

```
START → validate → process → format → END
```

Use this when your pipeline has no branching and no loops. This is the LangGraph equivalent of an LCEL chain, but with explicit state and the ability to add branching later without restructuring the whole system.

#### Pattern 2: Router / Classifier

A classifier node inspects the input and routes it to one of several specialist nodes. Each specialist handles a different type of request:

```
START → classify → [coding_node | creative_node | factual_node] → END
```

The conditional edge after `classify` uses a router function that reads a `category` field from the state.

#### Pattern 3: ReAct Agent Loop

The canonical agentic loop: the model reasons, decides whether to call a tool, calls the tool if needed, observes the result, and repeats until it is done:

```
START → agent_node → [tool_node (loops back to agent_node) | END]
```

The conditional edge after `agent_node` checks whether the last message has `tool_calls`. If yes, route to `tool_node` and loop back. If no, route to `END`.

#### Pattern 4: Human-in-the-Loop

Pause graph execution at a defined point, surface the pending state to a human operator, wait for their input, then resume:

```
START → generate_content → [PAUSE for human] → review_node → [publish | regenerate] → END
```

The pause is implemented with an `interrupt()` call inside a node or via `interrupt_before` at compile time.

#### Pattern 5: Parallel Fan-Out / Fan-In

Multiple independent nodes run concurrently, then a merge node combines their outputs. This is expressed by adding edges from a single source node to multiple destination nodes:

```
START → fan_out → [branch_a AND branch_b AND branch_c] → merge → END
```

LangGraph executes all branches in the same step. The merge node receives a state where all three branches have already written their outputs.

#### Pattern 6: Subgraphs

A compiled `StateGraph` is itself a `Runnable`. You can add a compiled subgraph as a node inside a parent graph:

```python
sub_graph = sub_builder.compile()
parent_builder.add_node("sub_workflow", sub_graph)
```

This allows you to build modular, reusable workflow components that are tested independently and composed into larger systems.

---

### 5. Building a ReAct Agent from Scratch

LangGraph ships a `create_react_agent` helper in `langgraph.prebuilt`. Building the agent yourself teaches you exactly what that helper does, which makes debugging it far easier.

A ReAct agent has four components:

1. **State** — a `MessagesState` holding the conversation.
2. **Agent node** — calls the LLM with tools bound. Returns the model's response (which may include `tool_calls`).
3. **Tool node** — iterates over `tool_calls` in the last message, executes each tool, and appends `ToolMessage` results.
4. **Conditional edge** — checks whether the last message has `tool_calls`. Yes → go to tool node. No → go to `END`.

The loop terminates when the model produces a final answer with no tool calls.

---

### 6. Persistence and Multi-Turn State

A graph compiled **without** a checkpointer is stateless — each `invoke()` starts fresh. A graph compiled **with** a checkpointer automatically:

1. Loads the checkpoint for the given `thread_id` before execution starts.
2. Saves a new checkpoint after every node completes.
3. Allows you to resume from the exact point where execution stopped (whether that was a crash, an interrupt, or a normal run that you want to continue).

For multi-turn conversations the pattern is identical to Module 2's `RunnableWithMessageHistory`, but implemented at the graph level rather than the chain level: each user turn is a new `invoke()` call on the same `thread_id`, and the state (including the full message history) is automatically loaded and saved by the checkpointer.

**`InMemorySaver`** vs **`SqliteSaver`**:

| Property | `InMemorySaver` | `SqliteSaver` |
|---|---|---|
| Package | `langgraph` (built-in) | `langgraph-checkpoint-sqlite` |
| Storage | Python dict | SQLite file on disk |
| Survives restart | No | Yes |
| Use case | Development, testing | Local production |
| Thread-safe | Yes | Requires `check_same_thread=False` on the connection |

---

### 7. Streaming

Streaming lets you process partial results as they are produced rather than waiting for the full graph run to complete.

`graph.stream()` is the synchronous streaming interface; `graph.astream()` is the async equivalent. Both accept a `stream_mode` argument.

#### Stream Mode: `"values"` (default)

Emits the complete state snapshot after each node finishes:

```python
for chunk in graph.stream(inputs, config, stream_mode="values"):
    print(chunk)   # full state dict after each node
```

Use this when you need to display the evolving state of a long pipeline in a UI.

#### Stream Mode: `"updates"`

Emits only the dict returned by each node — the state delta:

```python
for chunk in graph.stream(inputs, config, stream_mode="updates"):
    for node_name, update in chunk.items():
        print(f"Node '{node_name}' returned: {update}")
```

Use this for progress dashboards where you want to know which node just ran and what it changed.

#### Stream Mode: `"messages"` (token-level)

Emits individual LLM output tokens as they are generated, plus metadata identifying which node produced them:

```python
for chunk in graph.stream(inputs, config, stream_mode="messages", version="v2"):
    if chunk["type"] == "messages":
        message_chunk, metadata = chunk["data"]
        if message_chunk.content:
            print(message_chunk.content, end="", flush=True)
```

The `version="v2"` argument selects the unified `StreamPart` format introduced in LangGraph 1.1. To filter to a specific node:

```python
for chunk in graph.stream(inputs, config, stream_mode="messages", version="v2"):
    if chunk["type"] == "messages":
        msg, metadata = chunk["data"]
        if msg.content and metadata["langgraph_node"] == "call_llm":
            print(msg.content, end="", flush=True)
```

---

### 8. Human-in-the-Loop

#### Two Interrupt Styles

**Static interrupts at compile time:**

```python
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["review_node"],   # pause before entering review_node
)
```

The graph pauses automatically every time it is about to enter `review_node`. Resume by invoking again with the same `thread_id` (and `None` as input, or a `Command`):

```python
graph.invoke(None, config=config)   # resumes from the saved checkpoint
```

**Dynamic interrupts inside a node:**

```python
from langgraph.types import interrupt

def review_node(state: State) -> dict:
    human_decision = interrupt("Please review and approve: " + state["draft"])
    return {"approved": human_decision, "final": state["draft"]}
```

`interrupt()` pauses graph execution, surfaces its argument as the interrupt payload, and suspends the thread. When you resume with `Command(resume=value)`, that `value` becomes the return value of the `interrupt()` call inside the node:

```python
from langgraph.types import Command

graph.invoke(Command(resume=True), config=config)   # resumes, approved=True
```

#### `update_state`: Modifying State Before Resuming

You can modify the graph's saved state before resuming to inject human corrections:

```python
graph.update_state(config, {"draft": "Corrected content here."})
graph.invoke(None, config=config)   # continues with corrected state
```

#### Use Cases

- Content moderation: generate → pause → human reviews → publish or reject
- Tool call approval: agent wants to run a destructive tool → pause → human approves → execute
- Clarification requests: agent is uncertain → pause → human provides missing info → continue

---

## Best Practices

1. **Return only the keys you are changing from a node.** Returning the full state dict is not wrong, but it is wasteful and obscures intent. Return `{"output": result}` rather than `{**state, "output": result}`.

2. **Keep nodes small and single-purpose.** A node that does three things is harder to test and debug than three nodes that each do one thing. Conditional edges are cheap — use them freely.

3. **Use `InMemorySaver` during development, `SqliteSaver` for anything that needs to survive restarts.** Never write persistence logic before you have confirmed the graph logic is correct with the in-memory checkpointer.

4. **Always validate the full state schema before the first node.** If your graph expects `messages` to be a list and it receives `None`, the error will appear inside a node rather than at the call site. Add an input validation node as the first node after `START` in production graphs.

5. **Name nodes after what they do, not what they are.** `call_llm` is less informative than `classify_intent` or `generate_draft`. Node names appear in streaming output and LangSmith traces — make them readable.

6. **Do not mutate state inside a node — always return a new dict.** LangGraph uses the returned dict for checkpointing and reducer merging. Mutating `state` in place bypasses both mechanisms and causes subtle bugs.

7. **Pin `langgraph` and `langgraph-checkpoint-sqlite` versions together.** Like `langchain-core` and its provider packages, these packages must be version-compatible. Add them both to `requirements.txt` with explicit versions.

8. **Make operations inside a node idempotent when using interrupts.** When an interrupted node is resumed, LangGraph re-runs the node from the beginning. Any side effects (API calls, database writes) before the `interrupt()` call will execute again on resume.

---

## Use Cases

### Automated Research and Reporting Pipeline

A business needs to generate weekly competitive intelligence reports. The workflow: fetch data from several sources in parallel (fan-out), summarize each source independently, merge the summaries, draft the report, pause for a human editor to review and annotate, then publish. This maps directly to the fan-out/fan-in pattern followed by a human-in-the-loop pause. The `SqliteSaver` checkpointer means an overnight interruption does not lose the research already gathered.

### Customer Support Triage Agent

An incoming support ticket is classified by intent (billing, technical, refund) and routed to a specialist prompt. Each specialist can call tools (look up account info, query a knowledge base, or escalate to human). The loop continues until the agent has a complete answer or decides to escalate. This is the router pattern composed with the ReAct loop.

---

## Hands-on Examples

### Example 1: Three-Node Linear Workflow

A simple pipeline that validates input, calls an LLM to process it, and formats the output. This demonstrates the core `StateGraph` mechanics without any branching.

**Step 1.** Install Ollama, pull the model, then install dependencies.

```bash
# Install Ollama first: https://ollama.com/download
ollama pull llama3.2

mkdir langgraph-examples && cd langgraph-examples
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install langgraph langchain langchain-ollama python-dotenv
```

**Step 2.** Create `linear_workflow.py`.

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama

# LOCAL (primary): Pull model first with: ollama pull llama3.2
model = ChatOllama(model="llama3.2")

# --- Optional: Cloud API alternative ---
# from dotenv import load_dotenv
# from langchain_anthropic import ChatAnthropic
# load_dotenv()  # requires ANTHROPIC_API_KEY in .env
# model = ChatAnthropic(model="claude-haiku-4-5", max_tokens=512)

# --- State ---

class WorkflowState(TypedDict):
    raw_input: str
    validated: bool
    validation_error: str
    messages: Annotated[list, add_messages]
    formatted_output: str


# --- Nodes ---

def validate_input(state: WorkflowState) -> dict:
    """Node 1: Check that the input is non-empty and under 500 characters."""
    text = state["raw_input"].strip()
    if not text:
        return {"validated": False, "validation_error": "Input is empty."}
    if len(text) > 500:
        return {
            "validated": False,
            "validation_error": f"Input too long ({len(text)} chars). Max 500.",
        }
    return {"validated": True, "validation_error": ""}


def llm_process(state: WorkflowState) -> dict:
    """Node 2: Summarise the validated input using the LLM."""
    if not state["validated"]:
        # Skip LLM call — nothing to process
        return {"messages": [AIMessage(content="(skipped — validation failed)")]}

    system = SystemMessage(content="You are a concise summariser. Summarise the user text in one sentence.")
    human = HumanMessage(content=state["raw_input"])
    response = model.invoke([system, human])
    return {"messages": [response]}


def format_output(state: WorkflowState) -> dict:
    """Node 3: Format the final output string."""
    if not state["validated"]:
        return {"formatted_output": f"ERROR: {state['validation_error']}"}

    last_ai_message = state["messages"][-1]
    return {"formatted_output": f"Summary: {last_ai_message.content}"}


# --- Build Graph ---

builder = StateGraph(WorkflowState)
builder.add_node("validate", validate_input)
builder.add_node("process", llm_process)
builder.add_node("format", format_output)

builder.add_edge(START, "validate")
builder.add_edge("validate", "process")
builder.add_edge("process", "format")
builder.add_edge("format", END)

graph = builder.compile()


# --- Run ---

if __name__ == "__main__":
    test_cases = [
        "The Apollo program was a series of NASA space missions that landed humans on the Moon between 1969 and 1972. Neil Armstrong and Buzz Aldrin were the first humans to walk on the lunar surface.",
        "",   # empty — should fail validation
        "A" * 600,   # too long — should fail validation
    ]

    for text in test_cases:
        initial_state: WorkflowState = {
            "raw_input": text,
            "validated": False,
            "validation_error": "",
            "messages": [],
            "formatted_output": "",
        }
        result = graph.invoke(initial_state)
        print(result["formatted_output"])
        print("-" * 60)
```

**Step 4.** Run the workflow.

```bash
python linear_workflow.py
```

Expected output (the LLM summary will vary slightly):

```
Summary: The Apollo program was a landmark NASA initiative that successfully landed astronauts on the Moon six times between 1969 and 1972.
------------------------------------------------------------
ERROR: Input is empty.
------------------------------------------------------------
ERROR: Input too long (600 chars). Max 500.
------------------------------------------------------------
```

The key lesson: the `messages` field uses the `add_messages` reducer, so `llm_process` appends to the list rather than replacing it. The `formatted_output` field has no reducer, so `format_output` replaces it directly.

---

### Example 2: Router Workflow — Intent Classification

This example classifies a user's message into one of three categories and routes it to a specialist node. Each specialist uses a different system prompt.

**Create `router_workflow.py`.**

```python
from typing import Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

# LOCAL (primary): Pull model first with: ollama pull llama3.2
model = ChatOllama(model="llama3.2")

# --- Optional: Cloud API alternative ---
# from dotenv import load_dotenv
# from langchain_anthropic import ChatAnthropic
# load_dotenv()
# model = ChatAnthropic(model="claude-haiku-4-5", max_tokens=1024)

# --- State ---

class RouterState(TypedDict):
    user_input: str
    category: str          # "coding" | "creative" | "factual"
    response: str


# --- Nodes ---

def classify_intent(state: RouterState) -> dict:
    """Classify the user input into one of three categories."""
    system = SystemMessage(content=(
        "Classify the user's message into exactly one of these categories: "
        "coding, creative, factual. "
        "Respond with only the single word category — nothing else."
    ))
    human = HumanMessage(content=state["user_input"])
    response = model.invoke([system, human])
    raw = response.content.strip().lower()
    # Normalise — default to factual if the model goes off-script
    if raw not in ("coding", "creative", "factual"):
        raw = "factual"
    return {"category": raw}


def coding_specialist(state: RouterState) -> dict:
    """Handle coding questions with a developer-focused persona."""
    system = SystemMessage(content=(
        "You are an expert software engineer. Answer the question clearly with "
        "code examples where appropriate. Be concise."
    ))
    human = HumanMessage(content=state["user_input"])
    response = model.invoke([system, human])
    return {"response": response.content}


def creative_specialist(state: RouterState) -> dict:
    """Handle creative writing requests with a literary persona."""
    system = SystemMessage(content=(
        "You are a creative writing assistant with a vivid imagination. "
        "Respond to the user's request with engaging, original content."
    ))
    human = HumanMessage(content=state["user_input"])
    response = model.invoke([system, human])
    return {"response": response.content}


def factual_specialist(state: RouterState) -> dict:
    """Handle factual questions with a concise, accurate persona."""
    system = SystemMessage(content=(
        "You are a knowledgeable assistant. Answer the question accurately "
        "and concisely, citing key facts."
    ))
    human = HumanMessage(content=state["user_input"])
    response = model.invoke([system, human])
    return {"response": response.content}


# --- Router Function ---

def route_by_category(state: RouterState) -> Literal["coding_specialist", "creative_specialist", "factual_specialist"]:
    category = state["category"]
    if category == "coding":
        return "coding_specialist"
    elif category == "creative":
        return "creative_specialist"
    return "factual_specialist"


# --- Build Graph ---

builder = StateGraph(RouterState)
builder.add_node("classify_intent", classify_intent)
builder.add_node("coding_specialist", coding_specialist)
builder.add_node("creative_specialist", creative_specialist)
builder.add_node("factual_specialist", factual_specialist)

builder.add_edge(START, "classify_intent")
builder.add_conditional_edges(
    "classify_intent",
    route_by_category,
    ["coding_specialist", "creative_specialist", "factual_specialist"],
)
# All three specialists route to END
builder.add_edge("coding_specialist", END)
builder.add_edge("creative_specialist", END)
builder.add_edge("factual_specialist", END)

graph = builder.compile()


# --- Run ---

if __name__ == "__main__":
    questions = [
        "How do I reverse a list in Python?",
        "Write a short poem about autumn rain.",
        "What is the boiling point of water at high altitude?",
    ]

    for q in questions:
        result = graph.invoke({"user_input": q, "category": "", "response": ""})
        print(f"Input    : {q}")
        print(f"Category : {result['category']}")
        print(f"Response : {result['response'][:200]}...")
        print("-" * 60)
```

**Run the router.**

```bash
python router_workflow.py
```

The graph runs two nodes for every input: `classify_intent` followed by exactly one specialist. The conditional edge after `classify_intent` reads the `category` field from state — a field that did not exist when the graph started. This is the critical difference from LCEL: intermediate nodes can write new fields that subsequent routing decisions depend on.

---

### Example 3: ReAct Agent Built from Scratch

This example builds a full ReAct agent loop with two tools: a calculator and a simulated web search. It uses `InMemorySaver` for multi-turn conversation memory via `thread_id`.

**Install additional dependency (optional — only needed for disk-persistent checkpoints).**

```bash
pip install langgraph-checkpoint-sqlite
```

The `InMemorySaver` used in this example is built into `langgraph` — no extra package needed.

**Create `react_agent.py`.**

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

# LOCAL (primary): Pull model first with: ollama pull llama3.2
# Note: tool calling requires a model that supports it.
# llama3.2 supports tool use. Alternatively use qwen2.5:7b or mistral.
base_model = ChatOllama(model="llama3.2")

# --- Optional: Cloud API alternative ---
# from dotenv import load_dotenv
# from langchain_anthropic import ChatAnthropic
# load_dotenv()
# base_model = ChatAnthropic(model="claude-haiku-4-5", max_tokens=1024)

# --- Tools ---

@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression. Input must be a valid Python expression
    containing only numbers and operators (+, -, *, /, **, //, %). Example: '3 + 4 * 2'."""
    allowed_chars = set("0123456789+-*/(). ")
    if not all(c in allowed_chars for c in expression):
        return "Error: expression contains disallowed characters."
    try:
        result = eval(expression, {"__builtins__": {}})  # restricted eval for demo
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@tool
def web_search(query: str) -> str:
    """Simulate a web search and return a brief factual result. In a real agent,
    this would call a search API. Here it returns a canned response for demonstration."""
    simulated_results = {
        "capital of france": "The capital of France is Paris.",
        "speed of light": "The speed of light in a vacuum is approximately 299,792 km/s.",
        "python creator": "Python was created by Guido van Rossum and first released in 1991.",
        "langgraph version": "The current stable version of LangGraph is 1.1.6 (April 2026).",
    }
    lower_query = query.lower()
    for key, value in simulated_results.items():
        if key in lower_query:
            return value
    return f"No results found for: {query}"


# --- State ---

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# --- Model with tools bound ---

tools = [calculator, web_search]
tools_by_name = {t.name: t for t in tools}
model_with_tools = base_model.bind_tools(tools)


# --- Nodes ---

SYSTEM_PROMPT = SystemMessage(content=(
    "You are a helpful assistant with access to a calculator and a web search tool. "
    "Use the tools when you need to compute something or look up a fact. "
    "When you have a final answer, respond directly without calling any tools."
))


def agent_node(state: AgentState) -> dict:
    """Call the LLM. It may respond with tool_calls or with a final answer."""
    response = model_with_tools.invoke([SYSTEM_PROMPT] + state["messages"])
    return {"messages": [response]}


def tool_node(state: AgentState) -> dict:
    """Execute every tool call in the last message and return ToolMessage results."""
    last_message = state["messages"][-1]
    tool_results = []
    for tool_call in last_message.tool_calls:
        tool_fn = tools_by_name[tool_call["name"]]
        result = tool_fn.invoke(tool_call["args"])
        tool_results.append(
            ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
            )
        )
    return {"messages": tool_results}


# --- Router ---

def should_continue(state: AgentState) -> str:
    """If the last message has tool_calls, go to the tool node. Otherwise finish."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tool_node"
    return "__end__"


# --- Build Graph ---

builder = StateGraph(AgentState)
builder.add_node("agent_node", agent_node)
builder.add_node("tool_node", tool_node)

builder.add_edge(START, "agent_node")
builder.add_conditional_edges("agent_node", should_continue, ["tool_node", END])
builder.add_edge("tool_node", "agent_node")   # Loop: tool results go back to the agent

# Compile with InMemorySaver for multi-turn memory
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)


# --- Run with streaming to watch the loop ---

if __name__ == "__main__":
    config = {"configurable": {"thread_id": "react-demo-1"}}

    print("=== Turn 1 ===")
    inputs = {"messages": [HumanMessage(content="What is 17 multiplied by 23, and who created Python?")]}
    for chunk in graph.stream(inputs, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if "messages" in update:
                last_msg = update["messages"][-1]
                if isinstance(last_msg, AIMessage) and not last_msg.tool_calls:
                    print(f"[{node_name}] Final answer: {last_msg.content}")
                elif isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                    for tc in last_msg.tool_calls:
                        print(f"[{node_name}] Calling tool: {tc['name']}({tc['args']})")
                elif isinstance(last_msg, ToolMessage):
                    print(f"[{node_name}] Tool result: {last_msg.content}")

    print("\n=== Turn 2 (same thread — agent remembers context) ===")
    followup = {"messages": [HumanMessage(content="What is that result divided by 3?")]}
    for chunk in graph.stream(followup, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if "messages" in update:
                last_msg = update["messages"][-1]
                if isinstance(last_msg, AIMessage) and not last_msg.tool_calls:
                    print(f"[{node_name}] Final answer: {last_msg.content}")
                elif isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                    for tc in last_msg.tool_calls:
                        print(f"[{node_name}] Calling tool: {tc['name']}({tc['args']})")
                elif isinstance(last_msg, ToolMessage):
                    print(f"[{node_name}] Tool result: {last_msg.content}")
```

**Run the ReAct agent.**

```bash
python react_agent.py
```

Expected output (tool invocation order and exact wording will vary):

```
=== Turn 1 ===
[agent_node] Calling tool: calculator({'expression': '17 * 23'})
[tool_node] Tool result: 391
[agent_node] Calling tool: web_search({'query': 'Python creator'})
[tool_node] Tool result: Python was created by Guido van Rossum and first released in 1991.
[agent_node] Final answer: 17 multiplied by 23 is 391. Python was created by Guido van Rossum and first released in 1991.

=== Turn 2 (same thread — agent remembers context) ===
[agent_node] Calling tool: calculator({'expression': '391 / 3'})
[tool_node] Tool result: 130.33333333333334
[agent_node] Final answer: 391 divided by 3 is approximately 130.33.
```

In Turn 2 the agent remembered that 391 was the result from Turn 1. That context came from the `InMemorySaver` checkpoint, not from you — the second `invoke()` call loaded the full message history for `thread_id="react-demo-1"` before running.

---

### Example 4: Human-in-the-Loop Content Approval Workflow

This example generates a short marketing blurb, pauses for human review, and then either publishes it or regenerates it based on the human's decision.

**Create `hitl_workflow.py`.**

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

# LOCAL (primary): Pull model first with: ollama pull llama3.2
model = ChatOllama(model="llama3.2")

# --- Optional: Cloud API alternative ---
# from dotenv import load_dotenv
# from langchain_anthropic import ChatAnthropic
# load_dotenv()
# model = ChatAnthropic(model="claude-haiku-4-5", max_tokens=512)

# --- State ---

class ContentState(TypedDict):
    topic: str
    draft: str
    approved: bool
    final_content: str
    revision_notes: str
    attempt: int


# --- Nodes ---

def generate_content(state: ContentState) -> dict:
    """Generate a marketing blurb for the given topic."""
    attempt = state.get("attempt", 0) + 1
    revision_context = ""
    if state.get("revision_notes"):
        revision_context = f" The previous draft was rejected. Revision notes: {state['revision_notes']}. Please improve accordingly."

    system = SystemMessage(content=(
        "You are a marketing copywriter. Write a punchy two-sentence product description. "
        "Be enthusiastic but not hyperbolic." + revision_context
    ))
    human = HumanMessage(content=f"Topic: {state['topic']}")
    response = model.invoke([system, human])
    return {"draft": response.content, "attempt": attempt}


def human_review(state: ContentState) -> dict:
    """Pause and wait for a human to approve or reject the draft."""
    decision = interrupt({
        "message": "Please review the draft below and respond with approve=True or approve=False.",
        "draft": state["draft"],
        "attempt": state["attempt"],
    })
    # decision is whatever the caller passes via Command(resume=...)
    approved = bool(decision.get("approved", False))
    notes = decision.get("notes", "")
    return {"approved": approved, "revision_notes": notes}


def publish(state: ContentState) -> dict:
    """Mark the content as published."""
    return {"final_content": f"[PUBLISHED — attempt {state['attempt']}] {state['draft']}"}


def request_revision(state: ContentState) -> dict:
    """Log the revision request. The graph will loop back to generate_content."""
    print(f"  Revision requested (attempt {state['attempt']}): {state['revision_notes']}")
    return {}   # no state change — generate_content will re-read revision_notes


# --- Router ---

def route_after_review(state: ContentState) -> str:
    if state["approved"]:
        return "publish"
    if state["attempt"] >= 3:
        # Force-approve after 3 attempts to prevent infinite loops
        return "publish"
    return "request_revision"


# --- Build Graph ---

builder = StateGraph(ContentState)
builder.add_node("generate_content", generate_content)
builder.add_node("human_review", human_review)
builder.add_node("publish", publish)
builder.add_node("request_revision", request_revision)

builder.add_edge(START, "generate_content")
builder.add_edge("generate_content", "human_review")
builder.add_conditional_edges(
    "human_review",
    route_after_review,
    ["publish", "request_revision"],
)
builder.add_edge("request_revision", "generate_content")   # loop back
builder.add_edge("publish", END)

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)


# --- Simulate the human-in-the-loop interaction ---

if __name__ == "__main__":
    config = {"configurable": {"thread_id": "content-approval-1"}}

    print("=== Starting content generation ===")
    initial_state: ContentState = {
        "topic": "AI-powered project management software",
        "draft": "",
        "approved": False,
        "final_content": "",
        "revision_notes": "",
        "attempt": 0,
    }

    # Run until the first interrupt
    result = graph.invoke(initial_state, config=config)
    interrupt_data = result.get("__interrupt__", [{}])
    if interrupt_data:
        payload = interrupt_data[0].get("value", {})
        print(f"\nDraft (attempt {payload.get('attempt', 1)}):")
        print(f"  {payload.get('draft', '')}")

    # Simulate human rejecting the first draft with notes
    print("\n[Human]: Rejecting. Please make it more technical.")
    result = graph.invoke(
        Command(resume={"approved": False, "notes": "Too vague. Emphasise the AI scheduling feature."}),
        config=config,
    )
    interrupt_data = result.get("__interrupt__", [{}])
    if interrupt_data:
        payload = interrupt_data[0].get("value", {})
        print(f"\nRevised draft (attempt {payload.get('attempt', 1)}):")
        print(f"  {payload.get('draft', '')}")

    # Simulate human approving the second draft
    print("\n[Human]: Approving.")
    result = graph.invoke(Command(resume={"approved": True, "notes": ""}), config=config)

    print(f"\n=== Result ===")
    print(result["final_content"])
```

**Run the HITL workflow.**

```bash
python hitl_workflow.py
```

Expected output (exact draft text will vary):

```
=== Starting content generation ===

Draft (attempt 1):
  Transform your team's productivity with our AI-powered project manager! Streamline deadlines and automate task assignments so your projects always finish on time.

[Human]: Rejecting. Please make it more technical.

Revised draft (attempt 2):
  Harness cutting-edge AI scheduling algorithms to auto-prioritise tasks based on resource availability and critical path analysis. Our ML-driven platform reduces project overruns by predicting blockers before they occur.

[Human]: Approving.

=== Result ===
[PUBLISHED — attempt 2] Harness cutting-edge AI scheduling algorithms to auto-prioritise tasks based on resource availability and critical path analysis. Our ML-driven platform reduces project overruns by predicting blockers before they occur.
```

The graph paused at `human_review` twice. Each pause persisted the full graph state via `InMemorySaver`. The `Command(resume=...)` call resumed execution from exactly the `interrupt()` call inside `human_review` — earlier nodes were not re-executed. The loop (`request_revision → generate_content → human_review`) ran once before the human approved, and the safety limit of three attempts would have forced publication if the human kept rejecting.

---

## Common Pitfalls

### Pitfall 1: Forgetting the Checkpointer When Using Interrupts

**Mistake:** Compiling the graph without a checkpointer and then calling `interrupt()` or using `interrupt_before`.

**Why it happens:** Interrupts require persisted state to resume from. Without a checkpointer there is nowhere to save the graph state when execution pauses.

**Symptom:** `ValueError: No checkpointer found. Interrupts require a checkpointer.`

**Incorrect:**
```python
graph = builder.compile()   # no checkpointer
```

**Correct:**
```python
from langgraph.checkpoint.memory import InMemorySaver

graph = builder.compile(checkpointer=InMemorySaver())
```

---

### Pitfall 2: Omitting `thread_id` When Invoking a Graph with a Checkpointer

**Mistake:** Calling `graph.invoke()` without a `config` dict containing `thread_id`.

**Why it happens:** The `thread_id` is passed through the `config` dict, not as a direct argument. It is easy to forget, especially if you are used to LCEL's simpler invoke pattern.

**Symptom:** `KeyError: 'thread_id'` or all invocations silently share the same default thread.

**Incorrect:**
```python
result = graph.invoke({"messages": [HumanMessage("hello")]})
```

**Correct:**
```python
config = {"configurable": {"thread_id": "my-session-id"}}
result = graph.invoke({"messages": [HumanMessage("hello")]}, config=config)
```

---

### Pitfall 3: Returning the Full State from a Node Instead of a Partial Update

**Mistake:** Returning `{**state, "output": result}` from a node, which passes every state key back through all reducers.

**Why it happens:** Developers accustomed to immutable patterns copy the full state before modifying it. In LangGraph this is wrong: every key you return is processed by its reducer. Returning a list field with `add_messages` as its reducer will append the entire existing list to itself.

**Incorrect:**
```python
def my_node(state: MessagesState) -> dict:
    new_message = AIMessage(content="hello")
    return {**state, "messages": [new_message]}   # add_messages appends — duplicates all old messages!
```

**Correct:**
```python
def my_node(state: MessagesState) -> dict:
    new_message = AIMessage(content="hello")
    return {"messages": [new_message]}   # add_messages appends only the new message
```

---

### Pitfall 4: Using `__end__` and `END` Interchangeably in the Wrong Context

**Mistake:** Passing `END` (the imported sentinel object) as the return value of a router function, or passing the string `"__end__"` to `add_edge()`.

**Why it happens:** In `add_edge()` and `add_conditional_edges()` the destination argument is the imported `END` object. But router functions return strings — and the string that maps to `END` is `"__end__"`. The two contexts use different representations.

**Incorrect:**
```python
from langgraph.graph import END

def router(state) -> str:
    return END   # Wrong: returning the sentinel object, not a string
```

**Correct:**
```python
def router(state) -> str:
    return "__end__"   # Correct: the string that maps to END

# Or use a Literal type annotation to make both options explicit:
from typing import Literal
from langgraph.graph import END

def router(state) -> Literal["my_node", "__end__"]:
    if condition:
        return "my_node"
    return "__end__"

builder.add_conditional_edges("source_node", router, ["my_node", END])
```

---

### Pitfall 5: Expecting Side Effects Before `interrupt()` Not to Re-Run on Resume

**Mistake:** Performing a write operation (database insert, API call) before calling `interrupt()` in a node, then assuming it will not run again on resume.

**Why it happens:** When a graph is resumed after an interrupt, LangGraph re-runs the interrupted node from its beginning. Any code before the `interrupt()` call executes again.

**Incorrect — sends an email twice:**
```python
def review_node(state: State) -> dict:
    send_notification_email(state["draft"])   # runs on first call AND on resume
    approval = interrupt("Approve this draft?")
    return {"approved": approval}
```

**Correct — guard the side effect or move it to a separate node:**
```python
def notify_node(state: State) -> dict:
    send_notification_email(state["draft"])   # runs exactly once, before interrupt node
    return {}

def review_node(state: State) -> dict:
    approval = interrupt("Approve this draft?")   # only the interrupt runs here
    return {"approved": approval}
```

---

## Summary

- LangGraph extends LCEL chains with graph topology: nodes, directed edges, conditional routing, cycles, and persistent shared state. Use it when your workflow requires branching, loops, persistence, or human-in-the-loop pauses that a linear `RunnableSequence` cannot express.
- `StateGraph` holds a typed `TypedDict` state that every node reads and partially updates. Reducers declared with `Annotated` (such as `add_messages`) control how partial updates are merged.
- Nodes are Python functions that receive state and return only the keys they want to change. They must not mutate the state dict in place.
- Unconditional edges always route to a fixed next node. Conditional edges call a router function that returns a string naming the next node.
- `InMemorySaver` enables state persistence and multi-session isolation during development. `SqliteSaver` (from `langgraph-checkpoint-sqlite`) persists checkpoints to disk for production use.
- `thread_id` in the config dict is how LangGraph identifies which session's checkpoint to load and save — it is the LangGraph equivalent of `session_id` in Module 2's `RunnableWithMessageHistory`.
- The three streaming modes serve different needs: `"values"` for full state snapshots, `"updates"` for node-level deltas, and `"messages"` for token-level LLM streaming.
- Human-in-the-loop workflows use `interrupt()` inside a node or `interrupt_before` at compile time to pause execution. Resuming with `Command(resume=value)` passes the human's response back as the return value of the `interrupt()` call.

---

## Further Reading

- [LangGraph Overview — Official Docs](https://docs.langchain.com/oss/python/langgraph/overview) — The canonical starting point for LangGraph documentation; covers the core mental model, architecture, and links to all concept and how-to guides.
- [LangGraph Persistence — Official Docs](https://docs.langchain.com/oss/python/langgraph/persistence) — Complete reference for `InMemorySaver`, `SqliteSaver`, `PostgresSaver`, `thread_id`, checkpoint retrieval, and state history; essential reading before deploying to production.
- [LangGraph Interrupts — Official Docs](https://docs.langchain.com/oss/python/langgraph/interrupts) — Authoritative documentation for static `interrupt_before`/`interrupt_after`, dynamic `interrupt()`, `Command(resume=...)`, and `update_state`; covers the exact behavior of node re-execution on resume.
- [LangGraph Streaming — Official Docs](https://docs.langchain.com/oss/python/langgraph/streaming) — Full reference for all five stream modes (`values`, `updates`, `messages`, `custom`, `debug`) with code examples; includes the `version="v2"` unified `StreamPart` format introduced in LangGraph 1.1.
- [LangGraph GitHub Repository](https://github.com/langchain-ai/langgraph) — Source code, release notes, open issues, and the canonical examples directory; the releases page is the authoritative source for version numbers and breaking changes.
- [Making It Easier to Build Human-in-the-Loop Agents with interrupt — LangChain Blog](https://blog.langchain.com/making-it-easier-to-build-human-in-the-loop-agents-with-interrupt/) — The official blog post announcing the `interrupt()` function; explains the design rationale behind replacing `interrupt_before` with dynamic interrupts and provides motivating examples.
- [LangGraph on PyPI](https://pypi.org/project/langgraph/) — Version history, dependency requirements, and Python version compatibility; use this to verify the current stable release before pinning your requirements.
- [langgraph-checkpoint-sqlite on PyPI](https://pypi.org/project/langgraph-checkpoint-sqlite/) — The separate package required for `SqliteSaver`; check here for its version compatibility with the main `langgraph` package before upgrading.
