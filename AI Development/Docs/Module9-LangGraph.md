# Module 9: LangGraph — Stateful Agent Workflows
> Subject: AI Development | Difficulty: Advanced | Estimated Time: 300 minutes

## Objective

After completing this module, you will be able to explain why graph-based stateful workflows outperform simple linear chains and open-ended ReAct agents for complex tasks. You will design explicit state schemas using `TypedDict` and `Annotated` reducers, author node functions that read from and write to shared state, and wire those nodes into a `StateGraph` using fixed and conditional edges. You will implement a full ReAct loop from scratch — without any prebuilt helpers — so that every decision point in the agent loop is visible and modifiable. You will add checkpointing with `InMemorySaver` and `SqliteSaver` for multi-turn memory and fault recovery, wire `interrupt()` and `Command(resume=...)` into a node to create human-in-the-loop approval gates, and build a supervisor multi-agent graph where a routing node delegates to compiled subgraphs. All examples run exclusively against a local Ollama instance — no cloud API calls are required.

---

## Prerequisites

- Completed **Module 0: Setup and Local AI Stack** — Ollama is installed, running, and you can pull models
- Completed **Module 1: Working with Local Models** — comfortable with LLM inference and prompt construction
- Completed **Module 3: LangChain Fundamentals** — understands chains, runnables, and the `@tool` decorator
- Completed **Module 6: Agentic AI Theory** — understands the ReAct reasoning loop, tool use, and memory taxonomy
- Completed **Module 7: Agentic Workflow Patterns** — familiar with conditional branching, looping, checkpointing, and human-in-the-loop concepts at the design level
- Python 3.10 or later installed
- Comfortable reading and writing Python type annotations (`TypedDict`, `Annotated`, `Literal`)

---

## Key Concepts

### 1. Why LangGraph

#### The Limits of Linear Chains and Simple ReAct Agents

Modules 3 and 7 introduced LangChain's LCEL chains and the design-level concept of agentic workflows. Both approaches have practical ceilings that appear quickly in non-trivial systems.

**Linear chains (LCEL)** wire steps together with the pipe operator. Each step receives the previous step's output and passes its own output downstream. This is expressive for simple sequential logic, but:

- There is no native looping: if step 3 needs to retry based on the output of step 5, you must implement that logic outside the chain.
- Branching is handled by `RunnableBranch`, which is awkward to extend and difficult to test in isolation.
- There is no built-in state object that all steps share — you pass data through by transforming the output of one step into the input format expected by the next.
- There is no built-in checkpoint mechanism. If the process crashes mid-chain, you start over.

**Simple ReAct agents** (via LangChain's `AgentExecutor` or similar) address looping and tool use, but they hand over control flow entirely to the LLM. The LLM decides whether to call a tool, which tool to call, and when to stop. In practice this means:

- Execution paths are invisible at the Python level — you cannot set a breakpoint at "the moment the agent decides to call the search tool."
- Adding a human approval step before a destructive action (send an email, write to a database) requires monkey-patching the executor or implementing a custom callback.
- Debugging a run that went wrong means parsing verbose logs from inside the LLM call chain.
- Running two specialized agents in sequence — a researcher and a writer — requires nesting executors in ways that are fragile and hard to trace.

#### LangGraph's Answer: Workflows as Explicit Graphs

LangGraph models your workflow as a **directed graph** of nodes connected by edges. Every concept that was implicit in a chain or hidden inside an agent executor becomes explicit Python code you write and control:

| Concern | LangChain LCEL | ReAct AgentExecutor | LangGraph |
|---|---|---|---|
| Control flow | Linear pipe | LLM decides | Explicit edges you define |
| Branching | `RunnableBranch` | LLM decides | `add_conditional_edges()` |
| Looping | Not native | Implicit in agent loop | Cycle edges with exit condition |
| Shared state | Passed through transforms | Scratchpad string | Typed `TypedDict` object |
| Checkpointing | Not built-in | Not built-in | Built-in after every node |
| Human-in-the-loop | Not built-in | Callback hooks | `interrupt()` + `Command(resume=...)` |
| Multi-agent | Manual nesting | Not designed for it | Compiled subgraphs as nodes |
| Debugging | Stream callbacks | Stream callbacks | `stream(mode="debug")`, state inspection |

#### How LangGraph Relates to LangChain

LangGraph is a separate package (`pip install langgraph`) maintained by the same team as LangChain. It lives in the same ecosystem and integrates naturally with LangChain's model wrappers (`ChatOllama`), tool decorators (`@tool`), and message types (`HumanMessage`, `AIMessage`), but it is a distinct abstraction layer. You do not need to use LangChain to use LangGraph — LangGraph can orchestrate any Python functions — but in practice the two work together seamlessly.

#### LangGraph Version Note

This module targets **LangGraph 1.1.x** (the stable release series as of April 2026; the latest patch at time of writing is 1.1.8). The API stabilized at major version 1.0. If you are on an older 0.x installation, upgrade before proceeding:

```bash
pip install -U langgraph langgraph-checkpoint-sqlite langchain-ollama
```

---

### 2. Core LangGraph Concepts

#### 2.1 State

The **state** is a typed Python dictionary that flows through your graph. Every node receives the current state as its sole input and returns a dictionary of updates to apply back to the state. The framework merges those updates for you.

You define the state as a `TypedDict`:

```python
from typing_extensions import TypedDict

class MyState(TypedDict):
    user_input: str       # Original user query
    draft:      str       # LLM draft output
    approved:   bool      # Human approval flag
```

Every node in your graph receives a `MyState` instance and returns a `dict` with only the keys it is updating — it does not need to return all keys.

**Reducers with `Annotated`**

By default, when two nodes return the same key, the second write overwrites the first. For list fields that should accumulate rather than overwrite — like a message history — you annotate the field with a reducer function:

```python
import operator
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # add_messages is LangGraph's built-in reducer: appends new messages
    # to the list instead of overwriting it. This is the standard pattern
    # for any message-based agent.
    messages: Annotated[list[BaseMessage], add_messages]

    # operator.add works the same way for plain lists of strings or ints:
    # each node's return value is appended to the existing list.
    tool_calls_made: Annotated[list[str], operator.add]

    # Fields WITHOUT a reducer are overwritten by the most recent write:
    iteration_count: int
    final_answer:    str
```

`add_messages` is the most important reducer in LangGraph. It is smart enough to deduplicate messages by `id` (so re-running a node does not add duplicate messages) and handles both `BaseMessage` objects and raw dictionaries. You should use it for any field that stores a conversation history.

**`MessagesState`: the convenient starting point**

Because the messages-list pattern is so common, LangGraph ships a prebuilt state class that gives you `messages: Annotated[list[BaseMessage], add_messages]` for free:

```python
from langgraph.graph import MessagesState

# MessagesState is equivalent to:
# class MessagesState(TypedDict):
#     messages: Annotated[list[BaseMessage], add_messages]

# You can extend it with additional fields:
class MyAgentState(MessagesState):
    iteration_count: int
    context_docs:    list[str]
```

#### State flow through the graph

```
   User calls graph.invoke({"messages": [HumanMessage("Hello")]})
                              |
                   Framework creates state snapshot
                              |
                    +---------v----------+
                    |    node_A(state)   |
                    |  returns: {        |
                    |    "messages": [   |
                    |      AIMessage(..) |
                    |    ]               |
                    |  }                 |
                    +-------------------+
                              |
               Framework applies reducer: new state =
               old_messages + [AIMessage(..)]
                              |
                    +---------v----------+
                    |    node_B(state)   |
                    | receives updated   |
                    | state with both    |
                    | messages in list   |
                    +--------------------+
```

#### 2.2 Nodes

A node is any Python function (or async function) that takes a state object and returns a dict of updates:

```python
def my_node(state: AgentState) -> dict:
    # Read from state
    last_message = state["messages"][-1]
    # Do work (call an LLM, run a tool, transform data)
    result = do_something(last_message.content)
    # Return only the fields you are updating
    return {"final_answer": result}
```

Key rules:

- Return only the fields you want to update — you do not need to return the whole state.
- Returning an empty dict `{}` is valid and leaves the state unchanged.
- For `Annotated` fields with reducers, return the *new items to add*, not the full accumulated list.
- Async nodes work identically — just use `async def` and `await`.

#### 2.3 Edges

Edges define which node executes after a given node completes.

**Fixed edges** always go to the same destination:

```python
graph.add_edge("node_a", "node_b")      # node_a always goes to node_b
graph.add_edge(START, "first_node")     # graph entry point
graph.add_edge("last_node", END)        # graph exit point
```

`START` and `END` are special sentinel constants imported from `langgraph.graph`. `START` is the source of the graph's first node. `END` signals that execution should stop and the final state should be returned to the caller.

**Conditional edges** call a router function after a node completes to decide where to go next:

```python
from typing import Literal

def route_after_llm(state: AgentState) -> Literal["tools", "end"]:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "end"

graph.add_conditional_edges(
    "llm_node",          # from this node
    route_after_llm,     # call this function to decide destination
    {
        "tools": "tool_node",   # if function returns "tools" -> go to tool_node
        "end":   END,           # if function returns "end"   -> go to END
    }
)
```

The dict mapping is optional — if omitted, LangGraph assumes the function returns the literal node name.

#### 2.4 StateGraph: Building and Compiling

```python
from langgraph.graph import StateGraph, START, END

# 1. Instantiate with your state schema
builder = StateGraph(AgentState)

# 2. Add nodes
builder.add_node("llm_node",  llm_node_function)
builder.add_node("tool_node", tool_node_function)

# 3. Add edges
builder.add_edge(START, "llm_node")
builder.add_conditional_edges("llm_node", route_after_llm, {"tools": "tool_node", "end": END})
builder.add_edge("tool_node", "llm_node")   # loop back to LLM

# 4. Compile into an executable graph
graph = builder.compile()

# 5. Invoke
result = graph.invoke({"messages": [HumanMessage("What is 17 * 34?")]})
```

The `compile()` call validates the graph (checks for unreachable nodes, missing edges), locks the structure, and returns a `CompiledStateGraph` that exposes `invoke()`, `stream()`, `ainvoke()`, and `astream()`.

**Visualizing the graph**

```python
# Print as Mermaid diagram (paste into mermaid.live to render)
print(graph.get_graph().draw_mermaid())

# Or print as ASCII (useful in terminals)
graph.get_graph().print_ascii()
```

#### 2.5 Checkpointing

A **checkpointer** automatically saves a snapshot of the graph state after every node completes. This enables:

1. **Multi-turn memory**: invoke the same graph twice with the same `thread_id` and the second invocation picks up where the first left off.
2. **Human-in-the-loop**: pause execution mid-graph, let a human review state, then resume.
3. **Fault recovery**: if the process crashes after node 3 of 7, resume from that checkpoint rather than restarting.
4. **Time-travel debugging**: replay any prior graph run from any checkpoint.

LangGraph ships two built-in checkpointers:

| Checkpointer | Package | Persistence | Best for |
|---|---|---|---|
| `InMemorySaver` | `langgraph` | RAM only, lost on restart | Development, unit tests |
| `SqliteSaver` | `langgraph-checkpoint-sqlite` | SQLite file on disk | Local dev, single-process production |

```python
# In-memory (development)
from langgraph.checkpoint.memory import InMemorySaver

memory = InMemorySaver()
graph = builder.compile(checkpointer=memory)

# SQLite (persistent, single-process)
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

conn = sqlite3.connect("workflow.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
graph = builder.compile(checkpointer=checkpointer)
```

**Using thread_id**

Every invocation that should share state must use the same `thread_id` in the config:

```python
config = {"configurable": {"thread_id": "user-session-42"}}

# First turn
graph.invoke({"messages": [HumanMessage("What is the capital of France?")]}, config)

# Second turn — graph remembers the previous messages
graph.invoke({"messages": [HumanMessage("What language do they speak there?")]}, config)
```

Without a checkpointer, `thread_id` is meaningless — each invocation starts fresh.

---

### 3. Building Your First LangGraph Agent

This section walks through the complete five-step process for building any LangGraph graph, then applies it to the smallest useful agent: a two-node graph that calls an LLM and executes tool calls in a loop.

**Step 1 — Define the state schema**

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

**Step 2 — Define the node functions**

```python
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

# Define a tool
@tool
def add_numbers(a: float, b: float) -> float:
    """Add two numbers and return the result."""
    return a + b

tools = [add_numbers]

# Set up the LLM with tool binding
llm = ChatOllama(model="llama3.1", temperature=0)
llm_with_tools = llm.bind_tools(tools)

def llm_node(state: AgentState) -> dict:
    """Call the LLM and return its response."""
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

# ToolNode is a prebuilt node that reads tool_calls from the last AIMessage,
# executes each tool, and returns the results as ToolMessages.
tool_node = ToolNode(tools)
```

**Step 3 — Build the graph**

```python
from langgraph.graph import StateGraph, START, END

builder = StateGraph(AgentState)
builder.add_node("llm",   llm_node)
builder.add_node("tools", tool_node)
```

**Step 4 — Add edges**

```python
from typing import Literal

def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "__end__"

builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", should_continue)
builder.add_edge("tools", "llm")  # always loop back to LLM after tool execution
```

**Step 5 — Compile and invoke**

```python
graph = builder.compile()

from langchain_core.messages import HumanMessage

result = graph.invoke({
    "messages": [HumanMessage("What is 1234.5 plus 9876.5?")]
})

print(result["messages"][-1].content)
```

The graph's structure looks like this:

```
    START
      |
      v
  [llm_node] <-----------+
      |                   |
  (has tool_calls?)       |
     / \                  |
   YES   NO               |
    |     |               |
    v     v               |
[tool_node] [END]         |
    |                     |
    +---------------------+
```

This is the explicit, inspectable equivalent of LangChain's `AgentExecutor`. Every transition is a Python function you wrote.

---

### 4. The Prebuilt ReAct Agent

For cases where you want a standard ReAct loop without writing the wiring manually, LangGraph ships a prebuilt factory function. This is useful for quick prototyping; the from-scratch approach in Section 3 is preferred when you need to customize behavior.

```python
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from langchain_core.tools import tool

llm = ChatOllama(model="qwen2.5", temperature=0)

@tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

@tool
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b

tools = [multiply, subtract]

# create_react_agent returns a compiled graph
agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt="You are a helpful math assistant. Use tools to perform calculations.",
)
```

**Invoking the prebuilt agent**

```python
from langchain_core.messages import HumanMessage

result = agent.invoke({
    "messages": [HumanMessage("What is 42 times 17, then subtract 100?")]
})
print(result["messages"][-1].content)
```

**Streaming events**

LangGraph supports several streaming modes. `messages` streams tokens as they are produced; `updates` streams the state delta after each node:

```python
for chunk in agent.stream(
    {"messages": [HumanMessage("What is 99 times 11?")]},
    stream_mode="messages"
):
    # chunk is a tuple: (message_chunk_or_metadata, metadata_dict)
    message_chunk, meta = chunk
    if hasattr(message_chunk, "content") and message_chunk.content:
        print(message_chunk.content, end="", flush=True)
```

**Adding multi-turn memory to the prebuilt agent**

```python
from langgraph.checkpoint.memory import InMemorySaver

memory = InMemorySaver()
agent_with_memory = create_react_agent(
    model=llm,
    tools=tools,
    checkpointer=memory,
)

config = {"configurable": {"thread_id": "math-session-1"}}

agent_with_memory.invoke(
    {"messages": [HumanMessage("My lucky number is 7. Remember that.")]},
    config
)

# Second call remembers the previous message
result = agent_with_memory.invoke(
    {"messages": [HumanMessage("Multiply my lucky number by 6.")]},
    config
)
print(result["messages"][-1].content)
```

**Difference from LangChain's `create_react_agent`**

LangChain's version (in `langchain.agents`) returns an `AgentExecutor`. LangGraph's version (in `langgraph.prebuilt`) returns a compiled `StateGraph` with full checkpointing and streaming support. They accept the same tool list and model argument, but the LangGraph version is the current recommended approach for all new development.

---

### 5. Conditional Edges and Branching

Conditional edges are the mechanism that gives your graph its decision-making structure. Understanding how to write good router functions is essential.

#### Writing a Router Function

A router function receives the full current state and returns either a node name or a special sentinel:

```python
from typing import Literal

def route_after_llm(state: AgentState) -> Literal["tools", "__end__"]:
    """Decide whether to call tools or finish, based on the last message."""
    last_message = state["messages"][-1]
    # AIMessage has a tool_calls attribute when the LLM wants to invoke a tool.
    # It is an empty list when the LLM produced a final answer.
    if last_message.tool_calls:
        return "tools"
    return "__end__"
```

Returning `"__end__"` (or the `END` constant) tells LangGraph to terminate. You can also return the string name of any node in the graph.

#### Wiring Conditional Edges

```python
builder.add_conditional_edges(
    "llm_node",          # source node
    route_after_llm,     # router function
    {
        "tools":    "tool_executor",  # "tools" -> go to tool_executor
        "__end__":  END,              # "__end__" -> terminate
    }
)
```

The dict argument maps the router's return values to actual node names (or `END`). If you omit the dict, LangGraph assumes the router returns node names directly.

#### The Tool-Calling Loop Pattern

The most common branching pattern in LangGraph is the tool-calling loop. The LLM node may call a tool zero or more times before producing a final answer:

```
   START
     |
     v
 [llm_node]  <---------+
     |                  |
 route_after_llm()      |
     |                  |
  "tools"? -------> [tool_node]
     |
  "__end__"? ------> END
```

The loop continues until the LLM produces a message with an empty `tool_calls` list, at which point the router returns `"__end__"` and execution terminates.

**A router that enforces an iteration limit**

```python
def route_with_limit(state: AgentState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    iteration = state.get("iteration_count", 0)
    # Hard stop after 10 tool calls to prevent infinite loops
    if iteration >= 10:
        return "__end__"
    if last_message.tool_calls:
        return "tools"
    return "__end__"
```

---

### 6. Human-in-the-Loop with LangGraph

LangGraph implements human-in-the-loop via two cooperating primitives:

- **`interrupt(value)`** — called from inside a node; pauses graph execution and returns `value` to the caller. The graph state is saved to the checkpointer. The process (or even the machine) can stop here.
- **`Command(resume=value)`** — passed to `graph.invoke()` or `graph.stream()` instead of an input dict to resume a previously interrupted graph. The `value` is injected as the return value of the `interrupt()` call.

**Important**: `interrupt()` requires a checkpointer. Without one, it raises an error immediately.

#### Implementing an Approval Gate

```python
from langgraph.types import interrupt, Command
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

class ReviewState(TypedDict):
    messages:       Annotated[list[BaseMessage], add_messages]
    proposed_action: str
    approved:       bool

def draft_action_node(state: ReviewState) -> dict:
    """LLM drafts an action to take."""
    last_msg = state["messages"][-1]
    # Simulate LLM drafting a proposed action
    action = f"Send email to all users: '{last_msg.content}'"
    return {
        "messages":       [AIMessage(f"Proposed action: {action}")],
        "proposed_action": action,
    }

def approval_gate_node(state: ReviewState) -> dict:
    """Pause and wait for a human to approve or reject the action."""
    # interrupt() saves state and returns control to the caller.
    # The string argument is the "question" shown to the human.
    human_decision = interrupt(
        f"Approve this action?\n  {state['proposed_action']}\n"
        f"Reply 'approve' to proceed or 'reject' to cancel."
    )
    approved = human_decision.strip().lower() == "approve"
    return {"approved": approved}

def execute_or_cancel_node(state: ReviewState) -> dict:
    if state["approved"]:
        return {"messages": [AIMessage("Action approved. Executing now.")]}
    else:
        return {"messages": [AIMessage("Action rejected. Cancelled.")]}

# Build the graph
builder = StateGraph(ReviewState)
builder.add_node("draft",    draft_action_node)
builder.add_node("approval", approval_gate_node)
builder.add_node("execute",  execute_or_cancel_node)

builder.add_edge(START,      "draft")
builder.add_edge("draft",    "approval")
builder.add_edge("approval", "execute")
builder.add_edge("execute",  END)

memory = InMemorySaver()
review_graph = builder.compile(checkpointer=memory)
```

**Running with the approval gate**

```python
config = {"configurable": {"thread_id": "approval-run-001"}}

# First invocation: runs until the interrupt, then pauses
for event in review_graph.stream(
    {"messages": [HumanMessage("Flash sale — 50% off everything")], "approved": False},
    config,
    stream_mode="values",
):
    last = event["messages"][-1]
    print(f"[Node output] {last.content}")

# At this point, execution is paused. In a real system you would:
# 1. Notify the human reviewer (email, Slack, UI)
# 2. Persist the thread_id
# 3. Wait for their response (minutes, hours, days)

# Human makes a decision. Resume with Command(resume=...):
print("\n--- Human approved ---\n")
for event in review_graph.stream(
    Command(resume="approve"),
    config,
    stream_mode="values",
):
    last = event["messages"][-1]
    print(f"[Node output] {last.content}")
```

**Key rules for `interrupt()`**:

- The graph must be compiled with a checkpointer.
- `interrupt()` can only be called from inside a node function — not from an edge router.
- After resuming, LangGraph re-enters the node that called `interrupt()` and the `interrupt()` call returns the resume value. The rest of the node function runs normally.
- You can call `interrupt()` multiple times in the same node to collect multiple pieces of human input sequentially.

---

### 7. Multi-Agent Graphs

LangGraph supports composing multiple graphs together. A compiled graph can be used as a node inside a parent graph. This is the mechanism behind the supervisor pattern.

#### Compiling and Calling a Subgraph

```python
# --- Subgraph: Researcher ---
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage

researcher_llm = ChatOllama(model="llama3.1", temperature=0)

def researcher_node(state: MessagesState) -> dict:
    """Subgraph LLM node: performs research."""
    response = researcher_llm.invoke(state["messages"])
    return {"messages": [response]}

researcher_builder = StateGraph(MessagesState)
researcher_builder.add_node("research", researcher_node)
researcher_builder.add_edge(START, "research")
researcher_builder.add_edge("research", END)
researcher_subgraph = researcher_builder.compile()

# --- Subgraph: Writer ---
writer_llm = ChatOllama(model="qwen2.5", temperature=0)

def writer_node(state: MessagesState) -> dict:
    """Subgraph LLM node: writes a report."""
    response = writer_llm.invoke(state["messages"])
    return {"messages": [response]}

writer_builder = StateGraph(MessagesState)
writer_builder.add_node("write", writer_node)
writer_builder.add_edge(START, "write")
writer_builder.add_edge("write", END)
writer_subgraph = writer_builder.compile()
```

**Important**: If your subgraph uses a different state schema than the parent graph, you must write wrapper nodes in the parent that translate state in and out. If both use `MessagesState`, they are compatible directly.

#### The Supervisor Pattern

The supervisor is a node (usually an LLM call) that reads the current state and decides which subgraph to invoke next. LangGraph routes to the subgraph by including the compiled graph as a node in the parent:

```python
from typing_extensions import TypedDict
from typing import Annotated, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class SupervisorState(TypedDict):
    messages:     Annotated[list[BaseMessage], add_messages]
    next_agent:   str
    task_complete: bool

supervisor_llm = ChatOllama(model="mistral-nemo", temperature=0)

SUPERVISOR_PROMPT = """You are a supervisor coordinating two agents:
- "researcher": gathers information and facts
- "writer": drafts reports and documents
- "FINISH": task is complete

Based on the conversation so far, decide which agent should act next.
Respond with ONLY one of: researcher, writer, FINISH"""

def supervisor_node(state: SupervisorState) -> dict:
    """Decide which subagent to call next."""
    from langchain_core.messages import SystemMessage
    messages = [SystemMessage(SUPERVISOR_PROMPT)] + state["messages"]
    response = supervisor_llm.invoke(messages)
    decision = response.content.strip().lower()

    if "finish" in decision:
        return {"next_agent": "FINISH", "task_complete": True}
    elif "writer" in decision:
        return {"next_agent": "writer"}
    else:
        return {"next_agent": "researcher"}

def route_supervisor(state: SupervisorState) -> Literal["researcher", "writer", "__end__"]:
    if state["task_complete"] or state.get("next_agent") == "FINISH":
        return "__end__"
    return state["next_agent"]

def researcher_wrapper(state: SupervisorState) -> dict:
    """Translate parent state -> subgraph, run subgraph, translate back."""
    sub_result = researcher_subgraph.invoke({"messages": state["messages"]})
    return {"messages": sub_result["messages"]}

def writer_wrapper(state: SupervisorState) -> dict:
    """Translate parent state -> subgraph, run subgraph, translate back."""
    sub_result = writer_subgraph.invoke({"messages": state["messages"]})
    return {"messages": sub_result["messages"]}

# Build the supervisor graph
sup_builder = StateGraph(SupervisorState)
sup_builder.add_node("supervisor",  supervisor_node)
sup_builder.add_node("researcher",  researcher_wrapper)
sup_builder.add_node("writer",      writer_wrapper)

sup_builder.add_edge(START, "supervisor")
sup_builder.add_conditional_edges("supervisor", route_supervisor, {
    "researcher": "researcher",
    "writer":     "writer",
    "__end__":    END,
})
sup_builder.add_edge("researcher", "supervisor")
sup_builder.add_edge("writer",     "supervisor")

supervisor_graph = sup_builder.compile()
```

```
    START
      |
      v
 [supervisor] <-----------+
      |                   |
 route_supervisor()        |
      |                   |
   "researcher"? ----> [researcher_wrapper]
      |                   |
   "writer"?     ----> [writer_wrapper]
      |                   |
   "__end__"? --> END     +----(loop back)
```

**Shared state vs. isolated subgraph state**

When you call `researcher_subgraph.invoke({"messages": ...})` inside a wrapper node, the subgraph runs with its own isolated state object. It does not read or write the parent graph's state directly. The wrapper node is responsible for extracting what the subgraph needs from parent state, running the subgraph, and writing whatever the subgraph produced back to parent state. This isolation is intentional — it prevents subgraphs from accidentally overwriting fields in the parent's state schema.

---

### 8. LangGraph with Local Models via Ollama

#### Installing the Required Package

```bash
pip install langchain-ollama
```

#### `ChatOllama` in LangGraph Nodes

`ChatOllama` from `langchain_ollama` is a standard LangChain chat model wrapper. It works anywhere a `BaseChatModel` is expected:

```python
from langchain_ollama import ChatOllama

# Temperature 0 is strongly recommended for tool-calling agents —
# lower temperature means more consistent tool call format.
llm = ChatOllama(model="llama3.1", temperature=0)

# Bind tools — llm_with_tools.invoke() returns an AIMessage that may
# contain a tool_calls list.
llm_with_tools = llm.bind_tools(tools)
```

**Model-specific considerations**

Not all Ollama models support structured tool calling equally well. The following models have been tested to produce reliably structured `tool_calls` output with `bind_tools()`:

| Model | Notes |
|---|---|
| `llama3.1` | Solid tool-calling support; use `temperature=0` |
| `qwen2.5` | Excellent instruction-following; good tool use |
| `mistral-nemo` | Good general-purpose model; reliable tool calls with structured prompts |
| `llama3.2` | Smaller; tool calls work but may need more explicit prompting |

If a model produces malformed tool calls or ignores the tool spec entirely, try:

1. Adding a system prompt that explicitly says "You have access to the following tools. Use them when appropriate."
2. Reducing temperature to 0.
3. Switching to a larger model (e.g., `llama3.1:70b` if your hardware supports it).

#### Handling Streaming Message Chunks in Nodes

When you call `llm.invoke()` inside a node, LangGraph receives the complete response before passing it to the next node. Streaming at the node level (using `llm.stream()` inside the node) is supported but less common — most implementations stream at the graph level using `graph.stream()`.

```python
# Streaming at the graph level — recommended approach
for chunk in graph.stream(
    {"messages": [HumanMessage("Explain recursion")]},
    stream_mode="messages"  # stream tokens as they are produced
):
    message_chunk, metadata = chunk
    if hasattr(message_chunk, "content") and message_chunk.content:
        print(message_chunk.content, end="", flush=True)
print()  # newline after streaming completes
```

#### Debugging with `stream(mode="debug")`

```python
for event in graph.stream(
    {"messages": [HumanMessage("What is 5 + 3?")]},
    stream_mode="debug"
):
    print(event)
    # Events include: node entry/exit, state snapshots after each node,
    # checkpoint events, and interrupt events.
```

---

### 9. Common Pitfalls

**Pitfall 1: Overwriting vs. appending — reducer mistakes**

If you intend to accumulate messages but forget the `Annotated[list, add_messages]` annotation, each node's return will overwrite the message list entirely:

```python
# WRONG — messages field has no reducer; each node overwrites the list
class BrokenState(TypedDict):
    messages: list[BaseMessage]   # no Annotated, no reducer

# CORRECT — add_messages reducer appends new messages to the existing list
class GoodState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

Similarly, if you use `operator.add` as a reducer for a messages field instead of `add_messages`, LangGraph will not deduplicate by message `id` and tool call results may appear multiple times on graph retries.

**Pitfall 2: Forgetting to compile**

`StateGraph` is a builder object. It has no `invoke()` or `stream()` method. You must call `.compile()` first:

```python
builder = StateGraph(MyState)
# ... add nodes and edges ...

# WRONG — builder is not executable
result = builder.invoke({"messages": [...]})   # AttributeError

# CORRECT
graph = builder.compile()
result = graph.invoke({"messages": [...]})
```

**Pitfall 3: Calling `interrupt()` without a checkpointer**

`interrupt()` requires the graph to be compiled with a checkpointer. Without one, LangGraph raises a runtime error the moment the interrupt is reached:

```python
# WRONG — no checkpointer, interrupt() will fail at runtime
graph = builder.compile()

# CORRECT
from langgraph.checkpoint.memory import InMemorySaver
graph = builder.compile(checkpointer=InMemorySaver())
```

**Pitfall 4: Tool binding vs. tool passing**

In LangGraph, you need to do two separate things with your tools:

1. **Bind** them to the LLM so the model knows their schemas: `llm.bind_tools(tools)`
2. **Pass** them to `ToolNode` so the executor knows how to call them: `ToolNode(tools)`

Forgetting to bind means the LLM never generates `tool_calls`. Forgetting to pass means `ToolNode` has no function to execute:

```python
# WRONG — tools bound to LLM but ToolNode has no tools to execute
llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode([])   # empty list — nothing to execute

# CORRECT
llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)   # same list in both places
```

**Pitfall 5: Missing `thread_id` when using a checkpointer**

If you compile with a checkpointer but invoke without a `thread_id` in the config, LangGraph cannot associate the run with any thread. Behavior is undefined and may raise an error:

```python
# WRONG — checkpointer present but no thread_id
graph = builder.compile(checkpointer=InMemorySaver())
graph.invoke({"messages": [...]})  # may raise or silently lose state

# CORRECT
config = {"configurable": {"thread_id": "my-session-1"}}
graph.invoke({"messages": [...]}, config)
```

**Pitfall 6: Node function returns the full list instead of new items for Annotated fields**

```python
# WRONG — returning the full accumulated list when you should return only new items
def my_node(state: AgentState) -> dict:
    new_msg = AIMessage("Hello")
    # This doubles the list on every call because add_messages appends
    return {"messages": state["messages"] + [new_msg]}

# CORRECT — return only the new items; the reducer handles accumulation
def my_node(state: AgentState) -> dict:
    new_msg = AIMessage("Hello")
    return {"messages": [new_msg]}
```

---

## Best Practices

**Use `temperature=0` for tool-calling nodes.** LLMs with higher temperature produce inconsistent tool call formats. Set temperature to 0 for any node that is expected to generate structured tool calls.

**Keep node functions small and single-purpose.** A node that calls an LLM and also post-processes the result and also validates the format is three functions duct-taped together. Split them. Narrow nodes are easier to unit-test (mock the state, call the function, assert on the returned dict).

**Give each graph run a meaningful `thread_id`.** Use a format that encodes context — `"user-{user_id}-session-{session_id}"` — so you can look up runs by user or session in the checkpoint store.

**Cap your loops.** Any edge cycle is a potential infinite loop. Add an `iteration_count` field to state, increment it in the looping node, and check it in the router:

```python
def route(state) -> Literal["continue", "__end__"]:
    if state["iteration_count"] >= 10:
        return "__end__"
    # ... rest of routing logic
```

**Prefer `InMemorySaver` for development and `SqliteSaver` for local production.** Do not use `InMemorySaver` in production — all state is lost when the process restarts. Switch to `SqliteSaver` as soon as you need persistence across restarts.

**Use `stream(mode="updates")` during development.** This mode prints the state delta after each node — the fastest way to see what each node is contributing to state:

```python
for event in graph.stream(input_data, config, stream_mode="updates"):
    for node_name, state_delta in event.items():
        print(f"[{node_name}] wrote: {state_delta}")
```

**Visualize before you run.** Print `graph.get_graph().draw_mermaid()` and paste it into [mermaid.live](https://mermaid.live) before running the graph for the first time. It takes 10 seconds and immediately reveals missing edges and unreachable nodes.

---

## Hands-On Examples

### Example 1: Custom ReAct Agent from Scratch

This example builds the complete ReAct loop without using any prebuilt helpers. Every component — state, LLM node, tool node, router — is explicit.

```python
"""
example1_custom_react_agent.py

A custom ReAct agent built from scratch with LangGraph.
Tools: DuckDuckGo web search and a basic calculator.
Model: llama3.1 via Ollama.

Requirements:
    pip install langgraph langchain-ollama duckduckgo-search
    ollama pull llama3.1
"""

import json
import operator
from typing import Annotated, Literal
from typing_extensions import TypedDict

from langchain_core.messages import (
    AIMessage, BaseMessage, HumanMessage, ToolMessage, SystemMessage
)
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# ── 1. State Schema ────────────────────────────────────────────────────────────

class ReactState(TypedDict):
    messages:        Annotated[list[BaseMessage], add_messages]
    iteration_count: int   # no reducer — each write overwrites

# ── 2. Tools ───────────────────────────────────────────────────────────────────

@tool
def web_search(query: str) -> str:
    """Search the web using DuckDuckGo and return the top results.

    Args:
        query: The search query string.

    Returns:
        A string containing the top search results.
    """
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if not results:
            return "No results found."
        formatted = []
        for r in results:
            formatted.append(f"Title: {r.get('title', 'N/A')}\n"
                             f"URL:   {r.get('href',  'N/A')}\n"
                             f"Body:  {r.get('body',  'N/A')}\n")
        return "\n---\n".join(formatted)
    except Exception as e:
        return f"Search error: {e}"

@tool
def calculate(expression: str) -> str:
    """Evaluate a safe mathematical expression and return the result.

    Only supports: +, -, *, /, **, (, ), and numeric literals.
    Do NOT pass variables or function calls.

    Args:
        expression: A mathematical expression string, e.g. '(17 * 34) + 100'.

    Returns:
        The numeric result as a string, or an error message.
    """
    import ast
    allowed_nodes = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd,
    )
    try:
        tree = ast.parse(expression, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, allowed_nodes):
                return f"Unsafe expression rejected: {type(node).__name__}"
        result = eval(compile(tree, "<string>", "eval"))
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"

tools = [web_search, calculate]

# Build a lookup dict for the tool executor
tool_map = {t.name: t for t in tools}

# ── 3. LLM Setup ───────────────────────────────────────────────────────────────

llm = ChatOllama(model="llama3.1", temperature=0)
llm_with_tools = llm.bind_tools(tools)

SYSTEM_PROMPT = SystemMessage(
    "You are a helpful research assistant. You have access to a web search "
    "tool and a calculator. Use them when needed to answer the user's question "
    "accurately. When you have enough information to answer, provide a clear, "
    "concise final answer without calling any more tools."
)

# ── 4. Node Functions ──────────────────────────────────────────────────────────

def llm_node(state: ReactState) -> dict:
    """Call the LLM with the current message history."""
    messages = [SYSTEM_PROMPT] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {
        "messages":        [response],
        "iteration_count": state.get("iteration_count", 0) + 1,
    }

def tool_node(state: ReactState) -> dict:
    """Execute all tool calls requested by the last AIMessage."""
    last_message = state["messages"][-1]
    tool_results = []

    for tc in last_message.tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_id   = tc["id"]

        if tool_name not in tool_map:
            result_content = f"Error: tool '{tool_name}' not found."
        else:
            try:
                result_content = tool_map[tool_name].invoke(tool_args)
            except Exception as e:
                result_content = f"Tool error: {e}"

        tool_results.append(
            ToolMessage(content=str(result_content), tool_call_id=tool_id)
        )

    return {"messages": tool_results}

# ── 5. Router ──────────────────────────────────────────────────────────────────

MAX_ITERATIONS = 10

def should_continue(state: ReactState) -> Literal["tools", "__end__"]:
    """Decide: call tools again, or produce final answer?"""
    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        return "__end__"
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "__end__"

# ── 6. Build Graph ─────────────────────────────────────────────────────────────

builder = StateGraph(ReactState)
builder.add_node("llm",   llm_node)
builder.add_node("tools", tool_node)

builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", should_continue, {
    "tools":    "tools",
    "__end__":  END,
})
builder.add_edge("tools", "llm")

graph = builder.compile()

# ── 7. Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    query = "What is the current population of Tokyo, and what is that number divided by 1000?"
    print(f"Query: {query}\n")
    print("=" * 60)

    result = graph.invoke({
        "messages":        [HumanMessage(query)],
        "iteration_count": 0,
    })

    # Print each message in the conversation
    for msg in result["messages"]:
        if isinstance(msg, HumanMessage):
            print(f"[Human]  {msg.content}")
        elif isinstance(msg, AIMessage):
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"[LLM]    Calling tool: {tc['name']}({tc['args']})")
            else:
                print(f"[LLM]    {msg.content}")
        elif isinstance(msg, ToolMessage):
            preview = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            print(f"[Tool]   {preview}")
    print("=" * 60)
```

---

### Example 2: Document Review Workflow with Human Approval

This example demonstrates a sequential graph with checkpointing and a human-in-the-loop approval interrupt.

```python
"""
example2_document_review.py

A document review workflow with human approval gate.
Stages: load & chunk -> LLM analysis -> human approval -> save output.
Model: qwen2.5 via Ollama.

Requirements:
    pip install langgraph langchain-ollama langgraph-checkpoint-sqlite
    ollama pull qwen2.5
"""

import sqlite3
import textwrap
from pathlib import Path
from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command

# ── 1. State Schema ────────────────────────────────────────────────────────────

class ReviewState(TypedDict):
    messages:        Annotated[list[BaseMessage], add_messages]
    document_text:   str    # raw document content
    chunks:          list[str]  # paragraphs or sections
    analysis:        str    # LLM's analysis output
    approved:        bool   # human decision
    output_path:     str    # where to save the approved output

# ── 2. LLM Setup ───────────────────────────────────────────────────────────────

llm = ChatOllama(model="qwen2.5", temperature=0)

# ── 3. Node Functions ──────────────────────────────────────────────────────────

def load_and_chunk_node(state: ReviewState) -> dict:
    """Load the document from state and split into chunks."""
    text = state["document_text"]
    # Simple chunking: split on double newlines (paragraphs)
    raw_chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
    print(f"[load_and_chunk] Split document into {len(raw_chunks)} chunk(s).")
    return {
        "chunks": raw_chunks,
        "messages": [HumanMessage(f"Document loaded: {len(raw_chunks)} chunk(s) ready for analysis.")],
    }

def llm_analysis_node(state: ReviewState) -> dict:
    """Run LLM analysis on each chunk and produce a consolidated analysis."""
    chunks = state["chunks"]
    analyses = []

    for i, chunk in enumerate(chunks, start=1):
        messages = [
            SystemMessage(
                "You are a thorough document analyst. Analyze the provided "
                "text chunk for key themes, facts, and any issues. "
                "Be concise — 2 to 4 sentences."
            ),
            HumanMessage(f"Chunk {i} of {len(chunks)}:\n\n{chunk}"),
        ]
        response = llm.invoke(messages)
        analyses.append(f"[Chunk {i}] {response.content}")
        print(f"[llm_analysis] Analysed chunk {i}/{len(chunks)}.")

    consolidated = "\n\n".join(analyses)
    summary_messages = [
        SystemMessage(
            "Consolidate the following per-chunk analyses into a single "
            "coherent document analysis summary (4 to 6 sentences)."
        ),
        HumanMessage(consolidated),
    ]
    summary_response = llm.invoke(summary_messages)
    analysis_text = summary_response.content

    return {
        "analysis": analysis_text,
        "messages": [AIMessage(f"Analysis complete:\n\n{analysis_text}")],
    }

def human_approval_node(state: ReviewState) -> dict:
    """Pause and wait for human approval of the analysis."""
    print("\n" + "=" * 60)
    print("HUMAN APPROVAL REQUIRED")
    print("=" * 60)
    print(f"Analysis output:\n{state['analysis']}")
    print("=" * 60)

    decision = interrupt(
        "Review the analysis above. "
        "Type 'approve' to save the output, or 'reject' to discard it."
    )

    approved = decision.strip().lower() == "approve"
    msg = "Approved by reviewer." if approved else "Rejected by reviewer."
    return {
        "approved": approved,
        "messages": [AIMessage(msg)],
    }

def save_output_node(state: ReviewState) -> dict:
    """Save the approved analysis to disk, or log the rejection."""
    if state["approved"]:
        output_path = state.get("output_path", "analysis_output.txt")
        Path(output_path).write_text(state["analysis"], encoding="utf-8")
        result_msg = f"Analysis saved to '{output_path}'."
        print(f"[save_output] {result_msg}")
    else:
        result_msg = "Analysis was rejected. No file written."
        print(f"[save_output] {result_msg}")

    return {"messages": [AIMessage(result_msg)]}

# ── 4. Build Graph ─────────────────────────────────────────────────────────────

builder = StateGraph(ReviewState)
builder.add_node("load_and_chunk",  load_and_chunk_node)
builder.add_node("llm_analysis",    llm_analysis_node)
builder.add_node("human_approval",  human_approval_node)
builder.add_node("save_output",     save_output_node)

builder.add_edge(START,             "load_and_chunk")
builder.add_edge("load_and_chunk",  "llm_analysis")
builder.add_edge("llm_analysis",    "human_approval")
builder.add_edge("human_approval",  "save_output")
builder.add_edge("save_output",     END)

# SqliteSaver for persistence across restarts
conn = sqlite3.connect("review_workflow.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
review_graph = builder.compile(checkpointer=checkpointer)

# ── 5. Run ─────────────────────────────────────────────────────────────────────

SAMPLE_DOCUMENT = textwrap.dedent("""
    The Industrial Revolution began in Britain during the late 18th century.
    It marked a transition from hand production to machine manufacturing,
    fundamentally changing the economic and social structure of society.

    Steam power was central to this transformation. The steam engine,
    improved by James Watt in the 1760s and 1770s, enabled factories to be
    built away from rivers and powered large-scale production.

    Working conditions in early factories were often harsh. Workers, including
    children, faced long hours, low wages, and dangerous environments.
    This led to the rise of labor movements and eventually to protective
    legislation in the 19th century.
""").strip()

if __name__ == "__main__":
    config = {"configurable": {"thread_id": "review-session-001"}}
    initial_state = {
        "messages":      [],
        "document_text": SAMPLE_DOCUMENT,
        "chunks":        [],
        "analysis":      "",
        "approved":      False,
        "output_path":   "industrial_revolution_analysis.txt",
    }

    print("Phase 1: Running graph until approval interrupt...\n")
    for event in review_graph.stream(initial_state, config, stream_mode="values"):
        if event.get("messages"):
            last = event["messages"][-1]
            print(f"  [State] Last message: {last.content[:100]}...")

    # ── Simulating human decision ──────────────────────────────────────────────
    # In a real system this would come from a UI, email reply, or API call.
    human_decision = "approve"
    print(f"\nPhase 2: Human decision received: '{human_decision}'. Resuming graph...\n")

    for event in review_graph.stream(
        Command(resume=human_decision),
        config,
        stream_mode="values",
    ):
        if event.get("messages"):
            last = event["messages"][-1]
            print(f"  [State] Last message: {last.content}")

    print("\nWorkflow complete.")
```

---

### Example 3: Supervisor Multi-Agent Graph

This example builds the full supervisor pattern: a supervisor node that routes between a researcher subgraph and a writer subgraph, with a final review step.

```python
"""
example3_supervisor_multi_agent.py

Supervisor multi-agent graph.
  - Supervisor: decides whether to call researcher, writer, or finish
  - Researcher subgraph: searches for information using DuckDuckGo
  - Writer subgraph: drafts a report from gathered research
Models: llama3.1 (researcher), qwen2.5 (writer), mistral-nemo (supervisor).

Requirements:
    pip install langgraph langchain-ollama duckduckgo-search
    ollama pull llama3.1
    ollama pull qwen2.5
    ollama pull mistral-nemo
"""

from typing import Annotated, Literal
from typing_extensions import TypedDict

from langchain_core.messages import (
    AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
)
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages

# ── 1. Tools ───────────────────────────────────────────────────────────────────

@tool
def web_search(query: str) -> str:
    """Search the web for current information about the given query.

    Args:
        query: Search query string.

    Returns:
        Top search results as formatted text.
    """
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4))
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(
                f"Title: {r.get('title', 'N/A')}\n"
                f"URL:   {r.get('href',  'N/A')}\n"
                f"Body:  {r.get('body',  'N/A')}\n"
            )
        return "\n---\n".join(lines)
    except Exception as e:
        return f"Search failed: {e}"

search_tool_map = {"web_search": web_search}

# ── 2. Researcher Subgraph ─────────────────────────────────────────────────────

researcher_llm = ChatOllama(model="llama3.1", temperature=0)
researcher_llm_with_tools = researcher_llm.bind_tools([web_search])

RESEARCHER_SYSTEM = SystemMessage(
    "You are a research assistant. Your job is to gather accurate, "
    "up-to-date information using the web_search tool. Search for relevant "
    "facts and summarize the key findings. When you have enough information, "
    "provide a clear research summary without calling more tools."
)

def researcher_llm_node(state: MessagesState) -> dict:
    messages = [RESEARCHER_SYSTEM] + state["messages"]
    response = researcher_llm_with_tools.invoke(messages)
    return {"messages": [response]}

def researcher_tool_node(state: MessagesState) -> dict:
    last = state["messages"][-1]
    results = []
    for tc in last.tool_calls:
        name = tc["name"]
        args = tc["args"]
        tid  = tc["id"]
        if name in search_tool_map:
            try:
                content = search_tool_map[name].invoke(args)
            except Exception as e:
                content = f"Error: {e}"
        else:
            content = f"Unknown tool: {name}"
        results.append(ToolMessage(content=str(content), tool_call_id=tid))
    return {"messages": results}

def researcher_router(state: MessagesState) -> Literal["researcher_tools", "__end__"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "researcher_tools"
    return "__end__"

researcher_builder = StateGraph(MessagesState)
researcher_builder.add_node("researcher_llm",   researcher_llm_node)
researcher_builder.add_node("researcher_tools", researcher_tool_node)
researcher_builder.add_edge(START, "researcher_llm")
researcher_builder.add_conditional_edges("researcher_llm", researcher_router, {
    "researcher_tools": "researcher_tools",
    "__end__":          END,
})
researcher_builder.add_edge("researcher_tools", "researcher_llm")
researcher_subgraph = researcher_builder.compile()

# ── 3. Writer Subgraph ─────────────────────────────────────────────────────────

writer_llm = ChatOllama(model="qwen2.5", temperature=0)

WRITER_SYSTEM = SystemMessage(
    "You are a professional report writer. Given research findings in the "
    "conversation, write a clear, well-structured report. Use headings, "
    "bullet points where appropriate, and cite sources when available. "
    "Write in a professional, neutral tone. Aim for 300 to 500 words."
)

def writer_llm_node(state: MessagesState) -> dict:
    messages = [WRITER_SYSTEM] + state["messages"]
    response = writer_llm.invoke(messages)
    return {"messages": [response]}

writer_builder = StateGraph(MessagesState)
writer_builder.add_node("writer_llm", writer_llm_node)
writer_builder.add_edge(START, "writer_llm")
writer_builder.add_edge("writer_llm", END)
writer_subgraph = writer_builder.compile()

# ── 4. Supervisor Graph ────────────────────────────────────────────────────────

class SupervisorState(TypedDict):
    messages:      Annotated[list[BaseMessage], add_messages]
    next_agent:    str
    research_done: bool
    report_done:   bool

supervisor_llm = ChatOllama(model="mistral-nemo", temperature=0)

SUPERVISOR_SYSTEM = """You are a supervisor coordinating a research and writing team.

Available agents:
  - researcher: Searches the web and gathers factual information
  - writer:     Writes a structured report based on research findings
  - FINISH:     Use this when both research and a report are complete

Decision rules:
  - If no research has been done yet, choose: researcher
  - If research is done but no report has been written, choose: writer
  - If a report exists in the conversation, choose: FINISH

Respond with ONLY one word: researcher, writer, or FINISH"""

def supervisor_node(state: SupervisorState) -> dict:
    messages = [SystemMessage(SUPERVISOR_SYSTEM)] + state["messages"]
    response = supervisor_llm.invoke(messages)
    decision = response.content.strip().lower()

    if "finish" in decision:
        return {"next_agent": "FINISH"}
    elif "writer" in decision:
        return {"next_agent": "writer"}
    else:
        return {"next_agent": "researcher"}

def route_supervisor(state: SupervisorState) -> Literal["researcher_wrapper", "writer_wrapper", "__end__"]:
    agent = state.get("next_agent", "researcher")
    if agent == "FINISH":
        return "__end__"
    elif agent == "writer":
        return "writer_wrapper"
    else:
        return "researcher_wrapper"

def researcher_wrapper(state: SupervisorState) -> dict:
    """Run the researcher subgraph and merge its messages into parent state."""
    sub_result = researcher_subgraph.invoke({"messages": state["messages"]})
    # Return only messages added by the researcher
    new_messages = sub_result["messages"][len(state["messages"]):]
    return {"messages": new_messages, "research_done": True}

def writer_wrapper(state: SupervisorState) -> dict:
    """Run the writer subgraph and merge its messages into parent state."""
    sub_result = writer_subgraph.invoke({"messages": state["messages"]})
    new_messages = sub_result["messages"][len(state["messages"]):]
    return {"messages": new_messages, "report_done": True}

# Build the supervisor graph
sup_builder = StateGraph(SupervisorState)
sup_builder.add_node("supervisor",          supervisor_node)
sup_builder.add_node("researcher_wrapper",  researcher_wrapper)
sup_builder.add_node("writer_wrapper",      writer_wrapper)

sup_builder.add_edge(START, "supervisor")
sup_builder.add_conditional_edges("supervisor", route_supervisor, {
    "researcher_wrapper": "researcher_wrapper",
    "writer_wrapper":     "writer_wrapper",
    "__end__":            END,
})
sup_builder.add_edge("researcher_wrapper", "supervisor")
sup_builder.add_edge("writer_wrapper",     "supervisor")

supervisor_graph = sup_builder.compile()

# ── 5. Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    topic = "the recent advances in quantum computing and their practical applications"
    print(f"Topic: {topic}\n{'=' * 60}")

    initial_state = {
        "messages":      [HumanMessage(f"Research and write a report on: {topic}")],
        "next_agent":    "researcher",
        "research_done": False,
        "report_done":   False,
    }

    for event in supervisor_graph.stream(initial_state, stream_mode="updates"):
        for node_name, delta in event.items():
            if "messages" in delta and delta["messages"]:
                last = delta["messages"][-1]
                preview = last.content[:200] + "..." if len(last.content) > 200 else last.content
                print(f"\n[{node_name}] {preview}")
            elif "next_agent" in delta:
                print(f"\n[{node_name}] Supervisor decided: {delta['next_agent']}")

    print(f"\n{'=' * 60}\nWorkflow complete.")

    # Print the final report
    result = supervisor_graph.invoke(initial_state)
    final_messages = result["messages"]
    for msg in reversed(final_messages):
        if isinstance(msg, AIMessage) and len(msg.content) > 100:
            print(f"\nFinal Report:\n{msg.content}")
            break
```

---

## Key Terminology

**`add_messages`** — A LangGraph reducer function for the `messages` state field. When a node returns a list of messages, `add_messages` appends them to the existing list (deduplicating by `id`) rather than overwriting it.

**Annotated** — A Python type hint construct from `typing`. In LangGraph, `Annotated[list[T], reducer_fn]` tells the framework to apply `reducer_fn` when merging state updates for that field.

**Checkpointer** — A backend that persists graph state after every node. LangGraph ships `InMemorySaver` (RAM-only) and `SqliteSaver` (SQLite file). Required for multi-turn memory, human-in-the-loop, and fault recovery.

**`Command(resume=value)`** — Passed to `graph.invoke()` or `graph.stream()` instead of an input dict to resume a graph that was paused at an `interrupt()` call. `value` is returned from the `interrupt()` call in the node.

**Compiled graph** — The result of calling `builder.compile()` on a `StateGraph`. A compiled graph is executable — it exposes `invoke()`, `stream()`, `ainvoke()`, and `astream()`. The builder itself is not.

**Conditional edge** — An edge from one node to multiple possible destination nodes, governed by a router function that reads the current state and returns which destination to use.

**Fixed edge** — An edge that always routes to the same destination node, added with `add_edge(source, destination)`.

**`interrupt(value)`** — Called from inside a node function to pause graph execution and return `value` to the caller. Requires a checkpointer. Execution resumes from the same node when `Command(resume=...)` is passed to the graph.

**Node** — A Python function (sync or async) that receives the current state and returns a dict of state updates. The core unit of computation in a LangGraph graph.

**Reducer** — A function that defines how to merge a new value for a state field with the existing value. Used in `Annotated[type, reducer_fn]`. Common reducers: `add_messages` (for message lists), `operator.add` (for numeric or string concatenation).

**`StateGraph`** — The main builder class in LangGraph. You add nodes and edges to it, then call `.compile()` to get an executable graph.

**Subgraph** — A compiled LangGraph graph that is used as a node inside a parent graph. The subgraph has its own isolated state; wrapper nodes in the parent graph translate state in and out.

**Supervisor** — A multi-agent pattern in which a supervisor node (usually an LLM call) reads the current state and decides which specialized subgraph to invoke next. The supervisor continues routing until the task is complete.

**Thread ID** — A unique string identifying a specific workflow session. When a checkpointer is present, all invocations with the same `thread_id` share the same accumulated state.

**`ToolNode`** — A prebuilt LangGraph node that reads `tool_calls` from the last `AIMessage` in state, executes each tool, and returns the results as `ToolMessage` objects. Import: `from langgraph.prebuilt import ToolNode`.

---

## Summary

- **LangGraph** models agentic workflows as directed graphs of nodes (Python functions) connected by edges (fixed or conditional transitions). Every concept that is implicit in a LangChain chain or hidden inside an `AgentExecutor` — state, branching, looping, checkpointing, human approval — becomes explicit code you control.
- **State** is a typed `TypedDict` shared by all nodes. Fields annotated with reducers (`add_messages`, `operator.add`) accumulate values across nodes rather than overwriting them.
- **Nodes** receive the full current state and return a dict of updates. Only return the fields you are changing.
- **Fixed edges** (`add_edge`) always go to the same destination. **Conditional edges** (`add_conditional_edges`) call a router function after a node completes to choose the next destination.
- **`graph.compile()`** locks the graph structure and returns an executable `CompiledStateGraph`. The builder itself cannot be invoked.
- **Checkpointers** (`InMemorySaver`, `SqliteSaver`) automatically persist state after every node. They are required for multi-turn memory, `interrupt()`, and fault recovery.
- **`interrupt()` + `Command(resume=...)`** implements human-in-the-loop approval gates: the graph pauses mid-execution, the human makes a decision, and execution resumes from the same node.
- **Subgraphs** are compiled graphs used as nodes inside a parent graph. Wrapper nodes in the parent translate state in and out of the subgraph's isolated state schema.
- **`ChatOllama`** with `.bind_tools()` is the local-model equivalent of any cloud LLM in all LangGraph patterns. Use `temperature=0` for tool-calling nodes.
- Common pitfalls: forgetting reducers on list fields (overwrites instead of appends), forgetting to compile, calling `interrupt()` without a checkpointer, mismatching tool binding and `ToolNode` tool lists, and returning the full accumulated list instead of new items for `Annotated` fields.

---

## Further Reading

- [LangGraph Official Documentation — langchain-ai.github.io](https://langchain-ai.github.io/langgraph/) — The canonical reference for LangGraph. Covers the full API: `StateGraph`, `MessagesState`, `ToolNode`, `interrupt`, `Command`, prebuilt agents, checkpointers, streaming modes, and the LangGraph Platform (cloud deployment). Start here when the module examples do not cover your use case.

- [LangGraph Graph API Overview — docs.langchain.com](https://docs.langchain.com/oss/python/langgraph/use-graph-api) — The official how-to guide for the graph API, with runnable code examples for state schemas, reducers, conditional branching, parallel execution, loops, and the `Send` API for map-reduce workflows. Directly complements this module.

- [LangGraph Interrupts and Human-in-the-Loop — docs.langchain.com](https://docs.langchain.com/oss/python/langgraph/interrupts) — The official reference for `interrupt()`, `Command(resume=...)`, and multi-interrupt workflows. Explains exactly how the framework re-enters paused nodes and how to handle both synchronous and asynchronous human review patterns.

- [LangGraph Persistence and Checkpointing — docs.langchain.com](https://docs.langchain.com/oss/python/langgraph/persistence) — Detailed documentation for `InMemorySaver`, `SqliteSaver`, `thread_id`, checkpoint retrieval, state inspection, and time-travel debugging. Read this when you need to resume failed runs, implement audit trails, or debug production workflows.

- [Hierarchical Agent Teams — LangGraph Tutorials](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/) — The official LangGraph tutorial for building supervisor-style multi-agent systems with subgraphs. Shows a working example with a research team and a document writing team coordinated by a supervisor, directly applicable to Example 3 in this module.

- [LangGraph PyPI Page — pypi.org/project/langgraph](https://pypi.org/project/langgraph/) — The package page with the current stable version, release history, Python version requirements, and changelog. Check here before upgrading to confirm breaking changes between versions.

- [Integrating LangGraph with Ollama — Medium (Aleksandr Lifanov)](https://medium.com/@lifanov.a.v/integrating-langgraph-with-ollama-for-advanced-llm-applications-d6c10262dafa) — A practitioner walkthrough of connecting `ChatOllama` to LangGraph graphs, including model selection, tool binding quirks, and working examples with local models. Particularly useful for troubleshooting tool calling with smaller Ollama models.

- [Mastering LangGraph State Management in 2025 — SparkCo AI Blog](https://sparkco.ai/blog/mastering-langgraph-state-management-in-2025) — A deep dive into LangGraph's state system: `TypedDict` vs. Pydantic models, all built-in reducers, schema versioning for long-running workflows, and patterns for isolating step-specific state. Essential reading before designing production state schemas.

- [Building Human-In-The-Loop Agentic Workflows — Towards Data Science](https://towardsdatascience.com/building-human-in-the-loop-agentic-workflows/) — A detailed walkthrough implementing approval gates and feedback loops with LangGraph's `interrupt()` and `Command(resume=...)`, including SQLite checkpointing, thread ID management, and async approval via a web endpoint. Directly extends the concepts in Section 6 of this module.

- [LangGraph 201: Adding Human Oversight to a Deep Research Agent — Towards Data Science](https://towardsdatascience.com/langgraph-201-adding-human-oversight-to-your-deep-research-agent/) — An intermediate-to-advanced tutorial building on the prebuilt ReAct agent and adding human oversight steps, streaming partial results during long research tasks, and structuring the graph so reviewers see intermediate findings before the final report is generated.
