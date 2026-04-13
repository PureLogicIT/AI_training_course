# Module 6: Agentic Workflows

**Subject:** AI Development
**Difficulty:** Advanced
**Estimated Time:** 390 minutes (including hands-on examples)
**Prerequisites:**
- Completed Module 1: Building a Basic AI Chatbot with No Framework — you must understand raw SDK calls, the messages array, and the request-response cycle
- Completed Module 2: The LangChain Framework — familiarity with LCEL chains, `ChatAnthropic`, and provider abstraction
- Completed Module 3: AI Workflows and LangGraph — you must understand `StateGraph`, nodes, edges, conditional routing, and the ReAct loop
- Completed Module 4: AI Agents and Agentic AI — solid grasp of tool-use loops, the five agentic properties, multi-agent architectures, and guardrail layers
- Completed Module 5: Retrieval-Augmented Generation — understanding of RAG pipelines is helpful context; the agentic RAG pattern is referenced in examples
- Python 3.10 or later
- An `ANTHROPIC_API_KEY` set in your environment (primary examples use LangGraph with Claude; CrewAI examples note the relevant provider variable)

---

## Overview

Module 4 showed you how a single agent reasons, picks tools, and loops until a goal is met. That is genuinely powerful — but a single autonomous agent has hard limits. When a task is long, involves concurrent subtasks, requires approval before taking irreversible actions, or must survive a crash and resume hours later, a solitary loop breaks down. The answer is not a smarter agent; it is a better-designed *workflow* around the agent.

**Agentic workflows** are multi-step pipelines in which one or more AI agents perform coordinated work under explicit control-flow rules. The "workflow" part provides the scaffolding — sequencing, parallelism, branching, checkpoints, error policies — while the "agentic" part allows nodes within that scaffolding to reason, use tools, and make decisions autonomously. Think of it as the difference between a single musician improvising and a full orchestra with a conductor: the individual musicians are still making creative decisions, but the conductor enforces structure that makes the whole greater than the sum of its parts.

In 2026, agentic workflows are the dominant production pattern for complex AI applications. Gartner projects that 40% of enterprise applications will embed task-specific AI agents by end-of-year, and the vast majority of those deployments rely on workflow infrastructure — LangGraph, CrewAI, AutoGen, or purpose-built orchestration — rather than bare agent loops. Understanding workflow design is the bridge between a working demo and a production-grade system.

By the end of this module you will be able to:

- Explain how agentic workflows differ from single-shot agent calls and standalone agent loops
- Identify and implement five core workflow patterns: sequential chains, parallel fan-out/fan-in, conditional branching, iterative loops, and human-in-the-loop
- Manage state across workflow steps: passing context forward, aggregating parallel results, and checkpointing for fault tolerance
- Build and run production workflows using LangGraph (graphs, nodes, edges, `Send` API, `interrupt`, `Command`)
- Build role-based multi-agent crews using CrewAI (agents, tasks, crews, sequential vs. hierarchical processes)
- Design reliable workflows: structured error handling, retry logic with backoff, fallback paths, and timeouts
- Implement human-in-the-loop checkpoints: pausing for approval, resuming from a checkpoint, and using `interrupt`/`Command(resume=...)`
- Reason about long-running workflows: persistence strategies, async execution, and resumability after failure
- Add observability to workflows with LangSmith tracing and OpenTelemetry
- Coordinate multiple agents: task hand-off patterns, shared state, and conflict avoidance

---

## Required Libraries and Packages

| Package | Version | Purpose | Install |
|---|---|---|---|
| `langgraph` | >= 1.1.6 | Graph-based workflow orchestration with state, nodes, edges, checkpointing | `pip install langgraph` |
| `langchain-ollama` | >= 1.0.1 | Ollama chat model for LangGraph nodes (local, primary) | `pip install langchain-ollama` |
| `langchain-anthropic` | >= 1.0.0 | Claude chat model integration for LangGraph nodes (cloud, optional) | `pip install langchain-anthropic` |
| `langchain-core` | >= 1.2.26 | Tool definitions, message types, runnable primitives | `pip install langchain-core` |
| `langchain-openai` | >= 1.1.12 | OpenAI models (used in CrewAI examples) | `pip install langchain-openai` |
| `crewai` | >= 1.13.0 | Role-based multi-agent crew orchestration | `pip install crewai` |
| `anthropic` | >= 0.89 | Anthropic Claude SDK | `pip install anthropic` |
| `python-dotenv` | >= 1.0 | Load `.env` API keys | `pip install python-dotenv` |
| `langsmith` | >= 0.2 | Tracing and observability for LangGraph workflows | `pip install langsmith` |

Install everything at once:

```bash
# Pull local model first: ollama pull llama3.2
pip install langgraph langchain-ollama langchain-core crewai anthropic python-dotenv langsmith
```

Set your API keys:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."           # required for CrewAI OpenAI examples
export LANGCHAIN_API_KEY="ls__..."       # required for LangSmith tracing
export LANGCHAIN_TRACING_V2="true"       # enables automatic LangSmith tracing
```

Or place them in a `.env` file at your project root:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=agentic-workflows-module6
```

---

## Key Concepts

### 1. Agentic Workflows vs. Single-Shot Calls vs. Standalone Agent Loops

It helps to see all three paradigms side by side before diving into workflow design.

| Dimension | Single-shot LLM call | Standalone agent loop | Agentic workflow |
|---|---|---|---|
| Control flow | None — one request/response | Loop controlled by the model ("should I continue?") | Explicit graph or pipeline — you define the structure |
| Number of agents | 1 | 1 | 1 to N |
| Parallelism | None | None (sequential tool calls) | Native — fan-out to multiple agents simultaneously |
| Human checkpoints | Never | Rarely, via ad-hoc `input()` | First-class — `interrupt()`, approval nodes |
| State persistence | None | In-memory only | Checkpointed to disk or database |
| Fault tolerance | None | Crash loses all progress | Resume from last checkpoint |
| Observability | Log lines | Log lines | Full trace graph in LangSmith / OTEL |
| Best for | Q&A, summarisation | Open-ended research, coding tasks | Multi-step production pipelines |

A single-shot call is correct when the task fits in one turn. A standalone agent loop is correct when the task is open-ended and a single agent can handle it alone. An agentic workflow is correct when you need any of: parallelism, multi-agent coordination, irreversible-action approval, fault tolerance, or runtime exceeding a few minutes.

---

### 2. Core Workflow Patterns

Five patterns cover almost all production agentic workflows. Real systems combine them.

#### Pattern 1: Sequential Chain

The simplest pattern. Each step consumes the output of the prior step and produces input for the next. Think of it as an assembly line where each station adds value.

```
[Input] --> [Step A] --> [Step B] --> [Step C] --> [Output]
```

**When to use it:** The steps have a strict dependency order and no step can start until the prior one finishes. Example: `research_topic` -> `draft_report` -> `fact_check_report` -> `format_output`.

**Trade-off:** No parallelism means total latency equals the sum of all step latencies. For three 10-second LLM calls, you wait 30 seconds minimum.

#### Pattern 2: Parallel Fan-Out / Fan-In

A single upstream node dispatches work to multiple downstream nodes that run concurrently. A downstream aggregator node collects all their results (the "fan-in") before the workflow continues.

```
              /--> [Worker A] --\
[Dispatcher] ---> [Worker B] ----> [Aggregator] --> ...
              \--> [Worker C] --/
```

**When to use it:** Subtasks are independent of each other. Example: reviewing a pull request by running style, security, and performance checks simultaneously.

**Trade-off:** The aggregator must wait for the *slowest* worker ("straggler problem"). Design workers to time out rather than block indefinitely.

#### Pattern 3: Conditional Branching

A routing node evaluates the current state and selects one of several downstream paths. Only one branch executes.

```
              /--> [Path A: happy path]
[Router node] ---> [Path B: error path]
              \--> [Path C: escalation]
```

**When to use it:** Different outcomes require fundamentally different handling. Example: a classification agent routes customer queries to billing, technical support, or sales paths.

**Trade-off:** Branches can become tangled over time. Keep routing logic in a single, explicit routing function rather than spreading it across nodes.

#### Pattern 4: Iterative Loop

A node produces output that may not yet satisfy a quality criterion. A judge/evaluator node inspects the output and routes back to the generator node if revisions are needed. A loop counter or convergence check prevents infinite cycles.

```
[Generator] --> [Evaluator] --> (pass?) --> [Output]
      ^                |
      \--- (fail) -----/
```

**When to use it:** Output quality cannot be guaranteed in a single pass. Example: code generation where an executor runs the code and loops back if tests fail.

**Trade-off:** Unbounded loops are dangerous. Always include a `max_iterations` counter in state and a hard exit edge when it is exceeded.

#### Pattern 5: Human-in-the-Loop (HITL)

The workflow pauses at a defined checkpoint and waits for a human to review, approve, modify, or reject before proceeding. The checkpoint is a first-class workflow construct, not a `time.sleep()` hack.

```
[Agent action] --> [HITL checkpoint] --> (approved?) --> [Execute action]
                                   \--> (rejected?) --> [Revise plan]
```

**When to use it:** Actions are irreversible, high-stakes, or require legal/ethical sign-off. Example: deploying to production, sending a mass email, executing a financial transaction.

**Trade-off:** Human review time is the bottleneck. Minimise review burden by making the checkpoint surface exactly the information the reviewer needs, nothing more.

---

### 3. State Management Across Workflow Steps

State is the backbone of any multi-step workflow. Each node reads from and writes to a shared state object that flows through the entire graph. Getting state design right matters enormously for correctness and debuggability.

#### Designing Your State Schema

State in LangGraph is a `TypedDict`. Every key is a field that any node can read and write. Rules:

1. **Be explicit.** Every piece of information that flows between nodes must be a named field. Avoid storing opaque blobs.
2. **Use reducers for aggregated fields.** When multiple nodes write to the same field (e.g., parallel workers appending results), use a reducer so writes merge rather than overwrite. The standard reducer for lists is `operator.add` from Python's `typing.Annotated`.
3. **Keep state serialisable.** State gets checkpointed — it must be JSON-serialisable. Avoid storing objects that cannot be pickled.

```python
import operator
from typing import Annotated
from typing_extensions import TypedDict

class WorkflowState(TypedDict):
    # Plain fields — last write wins
    query: str
    final_answer: str
    error_message: str
    iteration_count: int

    # Aggregated fields — all writes are appended
    # Annotated[list, operator.add] means: when two nodes both write
    # to 'search_results', their lists are concatenated, not one overwriting the other.
    search_results: Annotated[list[str], operator.add]
    agent_logs: Annotated[list[str], operator.add]
```

#### Passing Context Forward

Each node receives the *full* current state and returns only the fields it wants to update. LangGraph merges the returned dict into the existing state using the reducers you defined.

```python
def research_node(state: WorkflowState) -> dict:
    # Read what you need
    query = state["query"]

    # Do work
    results = ["result 1", "result 2"]

    # Return only changed fields
    return {
        "search_results": results,          # appended via operator.add reducer
        "agent_logs": [f"research_node: found {len(results)} results"],
    }
```

#### Checkpointing

A **checkpointer** saves a complete snapshot of the state after every superstep (a superstep is one round of node executions in LangGraph). If the process crashes, you can reload the most recent checkpoint and continue from there rather than restarting.

LangGraph provides two checkpointer implementations:

| Checkpointer | Storage | Use case |
|---|---|---|
| `InMemorySaver` | RAM — lost on restart | Development, testing, short-lived workflows |
| `PostgresSaver` / `AsyncPostgresSaver` | PostgreSQL database | Production; survives crashes and restarts |

```python
from langgraph.checkpoint.memory import InMemorySaver

memory = InMemorySaver()
graph = builder.compile(checkpointer=memory)
```

Every workflow run is associated with a **thread ID**. The thread ID is how the checkpointer knows which checkpoint to load when a workflow pauses and resumes.

```python
config = {"configurable": {"thread_id": "order-processing-job-42"}}
result = graph.invoke(initial_state, config)
```

---

### 4. LangGraph Deep Dive

You used LangGraph in Module 3 to build a ReAct agent and in Module 4 to build multi-agent supervisor graphs. This section goes deeper on the constructs you need for production-grade workflow design.

#### Graph Construction Recap

```python
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

class State(TypedDict):
    message: str
    result: str

builder = StateGraph(State)

def step_one(state: State) -> dict:
    return {"result": f"processed: {state['message']}"}

builder.add_node("step_one", step_one)
builder.add_edge(START, "step_one")
builder.add_edge("step_one", END)

graph = builder.compile()
output = graph.invoke({"message": "hello", "result": ""})
```

#### Conditional Edges

A conditional edge calls a routing function that returns the name of the next node (or `END`). This is how you implement branching and loops.

```python
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

class ReviewState(TypedDict):
    draft: str
    score: int
    iterations: int
    final: str

def generate_draft(state: ReviewState) -> dict:
    # Simulated generation
    draft = f"Draft version {state['iterations'] + 1}"
    return {"draft": draft, "iterations": state["iterations"] + 1}

def evaluate_draft(state: ReviewState) -> dict:
    # Simulated evaluation — score improves with each iteration
    score = min(state["iterations"] * 30, 100)
    return {"score": score}

def route_after_evaluation(state: ReviewState) -> str:
    """Routing function: returns the name of the next node."""
    if state["score"] >= 80:
        return "publish"
    elif state["iterations"] >= 4:
        return "publish"   # Hard exit: never loop more than 4 times
    else:
        return "generate_draft"   # Loop back for revision

def publish(state: ReviewState) -> dict:
    return {"final": state["draft"]}

builder = StateGraph(ReviewState)
builder.add_node("generate_draft", generate_draft)
builder.add_node("evaluate_draft", evaluate_draft)
builder.add_node("publish", publish)

builder.add_edge(START, "generate_draft")
builder.add_edge("generate_draft", "evaluate_draft")
builder.add_conditional_edges(
    "evaluate_draft",
    route_after_evaluation,
    {
        "generate_draft": "generate_draft",
        "publish": "publish",
    }
)
builder.add_edge("publish", END)

graph = builder.compile()
result = graph.invoke({"draft": "", "score": 0, "iterations": 0, "final": ""})
print(result["final"])
```

#### Parallel Fan-Out and Fan-In

When multiple edges leave the same node, LangGraph executes all destination nodes in parallel within a single superstep. The `Annotated[list, operator.add]` reducer safely merges the concurrent writes.

```python
import operator
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class ReviewState(TypedDict):
    code_diff: str
    review_comments: Annotated[list[str], operator.add]
    approved: bool

def style_checker(state: ReviewState) -> dict:
    return {"review_comments": ["Style: variable names follow snake_case."]}

def security_checker(state: ReviewState) -> dict:
    return {"review_comments": ["Security: no hardcoded credentials found."]}

def performance_checker(state: ReviewState) -> dict:
    return {"review_comments": ["Performance: no N+1 query patterns detected."]}

def final_decision(state: ReviewState) -> dict:
    approved = len(state["review_comments"]) > 0
    return {"approved": approved}

builder = StateGraph(ReviewState)
builder.add_node("style_checker", style_checker)
builder.add_node("security_checker", security_checker)
builder.add_node("performance_checker", performance_checker)
builder.add_node("final_decision", final_decision)

# Fan-out: START goes to all three checkers simultaneously
builder.add_edge(START, "style_checker")
builder.add_edge(START, "security_checker")
builder.add_edge(START, "performance_checker")

# Fan-in: all three checkers feed into final_decision
builder.add_edge("style_checker", "final_decision")
builder.add_edge("security_checker", "final_decision")
builder.add_edge("performance_checker", "final_decision")

builder.add_edge("final_decision", END)

graph = builder.compile()
result = graph.invoke({
    "code_diff": "def get_user(id): return db.query(id)",
    "review_comments": [],
    "approved": False,
})
print(result["review_comments"])
print(result["approved"])
```

#### Dynamic Fan-Out with the Send API

Static fan-out requires you to know the number of parallel branches at graph-construction time. The `Send` API handles the case where the number of parallel workers is determined at runtime — for example, processing a list of items whose length varies per invocation.

`Send(node_name, state_dict)` tells LangGraph: "create a new instance of this node, initialised with this state."

```python
import operator
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

class ResearchState(TypedDict):
    topic: str
    subtopics: list[str]
    # Each parallel summariser appends its result; operator.add merges them safely
    summaries: Annotated[list[str], operator.add]
    final_report: str

def plan_research(state: ResearchState) -> dict:
    """Decompose the main topic into subtopics to research in parallel."""
    subtopics = [
        f"{state['topic']} history",
        f"{state['topic']} current state",
        f"{state['topic']} future outlook",
    ]
    return {"subtopics": subtopics}

def summarise_subtopic(state: dict) -> dict:
    """Each parallel worker receives its own subtopic via Send."""
    subtopic = state["subtopic"]
    # In a real workflow, this node would call an LLM
    summary = f"Summary of '{subtopic}': [placeholder content]"
    return {"summaries": [summary]}

def compile_report(state: ResearchState) -> dict:
    report = "\n\n".join(state["summaries"])
    return {"final_report": report}

def dispatch_subtopics(state: ResearchState) -> list:
    """
    Return a list of Send objects — one per subtopic.
    LangGraph will create a parallel instance of 'summarise_subtopic' for each.
    """
    return [
        Send("summarise_subtopic", {"subtopic": s})
        for s in state["subtopics"]
    ]

builder = StateGraph(ResearchState)
builder.add_node("plan_research", plan_research)
builder.add_node("summarise_subtopic", summarise_subtopic)
builder.add_node("compile_report", compile_report)

builder.add_edge(START, "plan_research")
# Conditional edge calls dispatch_subtopics; its Send list creates parallel workers
builder.add_conditional_edges(
    "plan_research",
    dispatch_subtopics,
    ["summarise_subtopic"],
)
builder.add_edge("summarise_subtopic", "compile_report")
builder.add_edge("compile_report", END)

graph = builder.compile()
result = graph.invoke({
    "topic": "quantum computing",
    "subtopics": [],
    "summaries": [],
    "final_report": "",
})
print(result["final_report"])
```

#### Human-in-the-Loop with interrupt() and Command

`interrupt()` pauses execution at a specific node and surfaces a value to the caller. The caller reviews whatever the interrupt surfaces, then resumes by calling `graph.stream(Command(resume=decision), config)`.

Resuming works because the checkpointer saved the full state before the interrupt — the workflow picks up exactly where it paused, with the human's decision injected into state.

```python
from typing_extensions import TypedDict
from langgraph.types import interrupt, Command
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

class DeploymentState(TypedDict):
    service_name: str
    version: str
    human_decision: str
    deployment_status: str

def prepare_deployment(state: DeploymentState) -> dict:
    print(f"Preparing deployment of {state['service_name']} v{state['version']}")
    return {}

def request_approval(state: DeploymentState) -> dict:
    """
    interrupt() pauses the graph here.
    The string passed to interrupt() is shown to the operator reviewing the pause.
    Execution resumes only after Command(resume=...) is received.
    """
    decision = interrupt(
        f"Deploy {state['service_name']} v{state['version']} to production?\n"
        f"Type 'approve' to proceed or 'reject' to abort."
    )
    return {"human_decision": decision}

def route_on_decision(state: DeploymentState) -> str:
    if state["human_decision"].strip().lower() == "approve":
        return "execute_deployment"
    return "abort_deployment"

def execute_deployment(state: DeploymentState) -> dict:
    print(f"Deploying {state['service_name']} v{state['version']}...")
    return {"deployment_status": "deployed"}

def abort_deployment(state: DeploymentState) -> dict:
    print("Deployment aborted by operator.")
    return {"deployment_status": "aborted"}

memory = InMemorySaver()
builder = StateGraph(DeploymentState)

builder.add_node("prepare_deployment", prepare_deployment)
builder.add_node("request_approval", request_approval)
builder.add_node("execute_deployment", execute_deployment)
builder.add_node("abort_deployment", abort_deployment)

builder.add_edge(START, "prepare_deployment")
builder.add_edge("prepare_deployment", "request_approval")
builder.add_conditional_edges(
    "request_approval",
    route_on_decision,
    {
        "execute_deployment": "execute_deployment",
        "abort_deployment": "abort_deployment",
    }
)
builder.add_edge("execute_deployment", END)
builder.add_edge("abort_deployment", END)

graph = builder.compile(checkpointer=memory)

# --- Step 1: Start the workflow.  It will pause at request_approval. ---
config = {"configurable": {"thread_id": "deploy-job-001"}}
initial_state = {
    "service_name": "payment-api",
    "version": "2.4.1",
    "human_decision": "",
    "deployment_status": "",
}

print("=== Starting workflow ===")
for event in graph.stream(initial_state, config, stream_mode="values"):
    print(event)

# The graph is now paused.  In a real system you would:
# - Send the interrupt message to a Slack channel, web UI, or email
# - Wait for the operator to respond (could be minutes or hours later)
# - Resume with their decision

# --- Step 2: Resume with an approval decision. ---
print("\n=== Operator approves; resuming ===")
for event in graph.stream(Command(resume="approve"), config, stream_mode="values"):
    print(event)
```

---

### 5. CrewAI Deep Dive

CrewAI takes a different approach to multi-agent coordination: rather than modelling workflows as explicit graphs, it models them as **role-based teams**. Each agent has a job title, a goal, and a backstory that shape how the LLM inside that agent behaves. Tasks define units of work. Crews are the teams. Flows are the top-level orchestrators.

This higher-level abstraction is faster to prototype and maps intuitively to real-world team structures, but gives you less direct control over execution paths than LangGraph does.

#### Core Abstractions

| Abstraction | Equivalent concept | What it defines |
|---|---|---|
| `Agent` | Team member | Role, goal, backstory, LLM, available tools, memory flag |
| `Task` | Work ticket | Description, expected output, which agent handles it |
| `Crew` | Project team | Which agents, which tasks, execution process |
| `Process` | Work style | `Process.sequential` or `Process.hierarchical` |
| `Flow` | Programme | Event-driven orchestrator that routes between Crews |

#### Building a Research and Writing Crew

```python
from crewai import Agent, Crew, Process, Task
from crewai_tools import SerperDevTool
from dotenv import load_dotenv
import os

load_dotenv()

# --- Define agents ---

researcher = Agent(
    role="Senior Research Analyst",
    goal="Uncover the latest developments in {topic} and synthesise them into key findings",
    backstory=(
        "You are a meticulous researcher with 15 years of experience distilling "
        "complex information into clear, evidence-based summaries. You never fabricate "
        "citations and always distinguish established fact from speculation."
    ),
    tools=[SerperDevTool()],   # web search tool
    verbose=True,
    max_iter=5,               # maximum reasoning iterations before forced stop
)

writer = Agent(
    role="Technical Content Writer",
    goal="Transform research findings into a polished, structured report on {topic}",
    backstory=(
        "You are an expert technical writer who produces clear, well-structured reports "
        "for a developer audience. You never introduce facts not present in the research "
        "you are given, and you always include proper attribution."
    ),
    verbose=True,
)

# --- Define tasks ---

research_task = Task(
    description=(
        "Conduct a comprehensive analysis of {topic}. "
        "Identify the top five recent developments, key players, and open challenges. "
        "Cite at least three authoritative sources."
    ),
    expected_output=(
        "A structured research brief with: an executive summary (2–3 sentences), "
        "five numbered findings, and a list of cited sources."
    ),
    agent=researcher,
)

writing_task = Task(
    description=(
        "Using the research brief provided, write a 600-word technical report on {topic} "
        "suitable for publication on a developer blog. "
        "Include a title, introduction, body sections for each key finding, and a conclusion."
    ),
    expected_output=(
        "A complete Markdown-formatted report with title, introduction, "
        "at least three body sections, conclusion, and references."
    ),
    agent=writer,
    # context=[research_task] tells CrewAI to pass research_task's output as context
    context=[research_task],
)

# --- Assemble the crew ---

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,   # research completes before writing starts
    verbose=True,
)

# --- Run ---

result = crew.kickoff(inputs={"topic": "LangGraph 2026"})
print(result.raw)
```

#### Hierarchical Process

In `Process.hierarchical`, CrewAI automatically creates a **manager agent** (backed by a more capable model) that delegates tasks to worker agents and reviews their outputs before passing them forward. You do not write the manager yourself — CrewAI creates it from your `manager_llm` parameter.

```python
from crewai import Agent, Crew, Process, Task
from langchain_openai import ChatOpenAI

worker_agent = Agent(
    role="Data Analyst",
    goal="Analyse the provided dataset and identify anomalies",
    backstory="A detail-oriented analyst skilled in statistical pattern recognition.",
    verbose=True,
)

analysis_task = Task(
    description="Analyse the sales dataset for Q1 2026 and flag any anomalous rows.",
    expected_output="A list of anomalous row IDs with brief explanations.",
    agent=worker_agent,
)

crew = Crew(
    agents=[worker_agent],
    tasks=[analysis_task],
    process=Process.hierarchical,
    manager_llm=ChatOpenAI(model="gpt-4o"),   # manager uses a more capable model
    verbose=True,
)

result = crew.kickoff()
print(result.raw)
```

---

### 6. Building Reliable Workflows: Errors, Retries, and Fallbacks

A workflow that works on the happy path is not production-ready. Real workflows fail — the LLM returns malformed JSON, a third-party API times out, a tool raises an exception, or the model hallucinates an invalid function call. You need explicit error-handling policies at every layer.

#### Layer 1: Node-Level Try/Except

Wrap each node's core logic in a try/except block. On failure, write a structured error into state rather than crashing the graph. A downstream routing node can then decide whether to retry, escalate, or fall back to a simpler strategy.

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class PipelineState(TypedDict):
    query: str
    api_result: str
    error: str
    retry_count: int

def call_external_api(state: PipelineState) -> dict:
    """Calls an external API; handles errors gracefully."""
    import urllib.request
    import json

    try:
        # Simulated API call — replace with your real endpoint
        url = f"https://api.example.com/search?q={state['query']}"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        return {"api_result": data.get("answer", ""), "error": ""}
    except TimeoutError:
        return {"error": "timeout", "retry_count": state["retry_count"] + 1}
    except Exception as exc:
        return {"error": str(exc), "retry_count": state["retry_count"] + 1}

def route_after_api(state: PipelineState) -> str:
    if state["error"] == "" :
        return "process_result"
    elif state["error"] == "timeout" and state["retry_count"] < 3:
        return "call_external_api"      # retry
    elif state["retry_count"] >= 3:
        return "fallback_handler"       # give up and degrade gracefully
    else:
        return "error_handler"

def process_result(state: PipelineState) -> dict:
    return {"api_result": f"Processed: {state['api_result']}"}

def fallback_handler(state: PipelineState) -> dict:
    # Return a degraded but useful response rather than crashing
    return {"api_result": "Service temporarily unavailable. Try again shortly."}

def error_handler(state: PipelineState) -> dict:
    print(f"Unrecoverable error: {state['error']}")
    return {"api_result": "An error occurred."}

builder = StateGraph(PipelineState)
builder.add_node("call_external_api", call_external_api)
builder.add_node("process_result", process_result)
builder.add_node("fallback_handler", fallback_handler)
builder.add_node("error_handler", error_handler)

builder.add_edge(START, "call_external_api")
builder.add_conditional_edges(
    "call_external_api",
    route_after_api,
    {
        "process_result": "process_result",
        "call_external_api": "call_external_api",
        "fallback_handler": "fallback_handler",
        "error_handler": "error_handler",
    }
)
builder.add_edge("process_result", END)
builder.add_edge("fallback_handler", END)
builder.add_edge("error_handler", END)

graph = builder.compile()
```

#### Layer 2: Exponential Backoff for Transient Failures

When retrying, do not hammer the failing service at full speed. Use exponential backoff with jitter: wait 2^attempt seconds plus a small random offset.

```python
import time
import random

def retry_with_backoff(func, max_attempts: int = 3):
    """
    Calls func(); if it raises, waits with exponential backoff and retries.
    Returns the result of func() on success, or re-raises the final exception.
    """
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as exc:
            if attempt == max_attempts - 1:
                raise
            wait_seconds = (2 ** attempt) + random.uniform(0, 1)
            print(f"Attempt {attempt + 1} failed: {exc}. Retrying in {wait_seconds:.1f}s...")
            time.sleep(wait_seconds)
```

Use this inside a node:

```python
def resilient_llm_node(state: WorkflowState) -> dict:
    def call_llm():
        # LOCAL (primary): ollama pull llama3.2
        from langchain_ollama import ChatOllama
        model = ChatOllama(model="llama3.2")
        # --- Optional: Cloud API alternative ---
        # from langchain_anthropic import ChatAnthropic
        # model = ChatAnthropic(model="claude-haiku-4-5", max_tokens=512)
        response = model.invoke(state["query"])
        return response.content

    result = retry_with_backoff(call_llm, max_attempts=3)
    return {"result": result}
```

#### Layer 3: Circuit Breaker

A circuit breaker tracks consecutive failures for a specific service. After a threshold is exceeded, it "opens" the circuit — all further calls fail fast (without actually trying) until a cool-down period passes. This protects downstream services from being overwhelmed and prevents your workflow from wasting time on calls that will certainly fail.

```python
import time
from dataclasses import dataclass, field

@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout: float = 30.0   # seconds
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _open: bool = field(default=False, init=False)

    def call(self, func):
        if self._open:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._open = False     # attempt recovery (half-open state)
            else:
                raise RuntimeError("Circuit breaker is open — call blocked.")

        try:
            result = func()
            self._failure_count = 0   # reset on success
            return result
        except Exception:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._open = True
            raise

# Usage: create one breaker per external service, reuse across calls
api_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
```

---

### 7. Observability: Tracing and Debugging Agentic Workflows

A multi-node workflow where each node calls an LLM, invokes tools, or spawns sub-agents is genuinely hard to debug with `print()` statements. You need structured, queryable traces that capture every decision, every tool call, every state transition, and every latency.

#### LangSmith

LangSmith is LangChain's observability platform for LangGraph and LangChain workflows. When `LANGCHAIN_TRACING_V2=true` is set in your environment, every LangGraph invocation is automatically traced — no code changes required.

What LangSmith captures for each workflow run:
- The complete graph execution path (which nodes ran, in which order)
- Input and output state for every node
- LLM calls: prompt, response, token count, latency, model name
- Tool calls: tool name, inputs, outputs, success/failure
- Total run latency and cost estimate

You can also add custom spans for sections of your own code:

```python
from langsmith import traceable

@traceable(name="custom-preprocessing-step")
def preprocess_documents(docs: list[str]) -> list[str]:
    """Any function decorated with @traceable becomes a named span in LangSmith."""
    return [doc.strip().lower() for doc in docs]
```

To inspect a paused workflow's state (useful for debugging HITL pauses):

```python
# Retrieve the current state snapshot for a thread
snapshot = graph.get_state(config)
print(snapshot.values)          # current state dict
print(snapshot.next)            # which node will run next when resumed
print(snapshot.tasks)           # pending tasks (if any)
```

#### OpenTelemetry Integration

LangSmith now supports full OpenTelemetry (OTEL) export. If your organisation already has an OTEL-compatible observability stack (Datadog, Grafana Tempo, Elastic, Honeycomb), you can route LangSmith traces into it alongside your existing application telemetry.

```bash
# Install the OTEL exporter package
pip install opentelemetry-exporter-otlp
```

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure OTEL exporter pointing at your collector
provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317")
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# From this point, LangSmith automatically populates OTEL spans
# alongside its own trace storage
```

#### Structured Logging Inside Nodes

Even without LangSmith, structured JSON logging dramatically improves debuggability over plain print statements. Use Python's `logging` module with a JSON formatter in every node:

```python
import logging
import json
from datetime import datetime

def make_log_entry(node_name: str, event: str, data: dict) -> str:
    return json.dumps({
        "timestamp": datetime.utcnow().isoformat(),
        "node": node_name,
        "event": event,
        **data,
    })

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workflow")

def my_node(state: WorkflowState) -> dict:
    logger.info(make_log_entry("my_node", "start", {"query": state["query"]}))
    result = "..."   # do work
    logger.info(make_log_entry("my_node", "complete", {"result_length": len(result)}))
    return {"result": result}
```

---

### 8. Multi-Agent Coordination Patterns

When a workflow involves multiple agents, you need explicit conventions for how they hand off tasks, share context, and avoid stepping on each other's work.

#### Supervisor Pattern

One agent acts as an orchestrator. It receives the top-level goal, decomposes it into subtasks, assigns each subtask to a specialist agent, collects results, and produces the final answer. Specialist agents do not communicate directly with each other — all communication flows through the supervisor.

```
User goal
    |
    v
[Supervisor Agent]
    |           |           |
    v           v           v
[Researcher] [Writer] [Fact-Checker]
    |           |           |
    v           v           v
  result      result      result
    |           |           |
    +-----+-----+-----------+
          |
          v
   [Supervisor Agent] (aggregates results)
          |
          v
     Final answer
```

This pattern appears in Module 4 in the multi-agent supervisor section. LangGraph implements it cleanly: the supervisor node reads all specialist outputs from state and produces a synthesised result.

#### Blackboard Pattern

All agents read from and write to a shared state object (the "blackboard"). No direct agent-to-agent communication occurs. Agents check the blackboard for available work, claim it, execute it, and post results back. A coordinator agent monitors the blackboard and declares completion when all tasks are done.

This pattern naturally avoids conflicts because state updates flow through LangGraph's reducer system — parallel writes to list fields are merged, not overwritten.

#### Hand-Off via Command

The `Command` object in LangGraph allows an agent node to explicitly route to a different agent node while simultaneously updating state. This is how agents "hand off" work without a central supervisor.

```python
from langgraph.types import Command
from typing import Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class AgentState(TypedDict):
    task: str
    draft: str
    status: str

def research_agent(state: AgentState) -> Command[Literal["writing_agent"]]:
    """Research agent hands off to writing agent when research is done."""
    research_findings = f"Research findings for: {state['task']}"
    return Command(
        update={"draft": research_findings, "status": "research_complete"},
        goto="writing_agent",
    )

def writing_agent(state: AgentState) -> Command[Literal["__end__"]]:
    """Writing agent takes the research draft and produces the final output."""
    final = f"Final report based on: {state['draft']}"
    return Command(
        update={"draft": final, "status": "complete"},
        goto=END,
    )

builder = StateGraph(AgentState)
builder.add_node("research_agent", research_agent)
builder.add_node("writing_agent", writing_agent)
builder.add_edge(START, "research_agent")

graph = builder.compile()
result = graph.invoke({"task": "quantum computing trends", "draft": "", "status": ""})
print(result["draft"])
```

---

### 9. Long-Running Workflows: Persistence and Async Execution

Some workflows take minutes, hours, or days. A deployment pipeline might wait for CI tests to pass. A research workflow might crawl dozens of web pages. An approval workflow might wait for a human reviewer who is in a different timezone.

#### Persistence with PostgreSQL

Switch from `InMemorySaver` to `PostgresSaver` for any workflow that must survive process restarts:

```python
# pip install langgraph-checkpoint-postgres psycopg
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://user:password@localhost:5432/workflows"

with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()   # creates checkpoint tables if they do not exist
    graph = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "long-job-12345"}}
    result = graph.invoke(initial_state, config)
```

If the process crashes mid-run, restart it and call `graph.invoke(None, config)` — passing `None` as the initial state tells LangGraph to load from the checkpoint and resume.

#### Async Execution

For I/O-bound workflows (web fetches, database queries, LLM calls), use LangGraph's async API to avoid blocking the event loop. Define nodes as `async def` functions and call `await graph.ainvoke(...)`.

```python
import asyncio
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

class AsyncState(TypedDict):
    url: str
    content: str

async def fetch_page(state: AsyncState) -> dict:
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(state["url"], timeout=aiohttp.ClientTimeout(total=30)) as resp:
            content = await resp.text()
    return {"content": content[:500]}   # first 500 chars for demo

builder = StateGraph(AsyncState)
builder.add_node("fetch_page", fetch_page)
builder.add_edge(START, "fetch_page")
builder.add_edge("fetch_page", END)

graph = builder.compile()

async def main():
    result = await graph.ainvoke({"url": "https://example.com", "content": ""})
    print(result["content"])

asyncio.run(main())
```

---

### 10. Putting It Together: A Complete Production Workflow

The following example builds a complete content-creation pipeline that demonstrates: sequential steps, parallel quality checks, a human approval checkpoint, error handling, and LangSmith tracing.

```python
import operator
from typing import Annotated
from typing_extensions import TypedDict
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver

# LOCAL (primary): Pull model first with: ollama pull llama3.2
llm = ChatOllama(model="llama3.2")

# --- Optional: Cloud API alternative ---
# from dotenv import load_dotenv
# from langchain_anthropic import ChatAnthropic
# load_dotenv()
# llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=2048)

# ── State ──────────────────────────────────────────────────────────────────────

class ContentState(TypedDict):
    topic: str
    outline: str
    draft: str
    quality_issues: Annotated[list[str], operator.add]   # parallel checkers append here
    human_decision: str
    final_content: str
    error: str

# ── Node definitions ───────────────────────────────────────────────────────────

def create_outline(state: ContentState) -> dict:
    """Step 1: Generate a structured outline."""
    try:
        prompt = f"Create a 5-point outline for a technical blog post about: {state['topic']}"
        response = llm.invoke(prompt)
        return {"outline": response.content, "error": ""}
    except Exception as exc:
        return {"error": f"outline_failed: {exc}"}

def write_draft(state: ContentState) -> dict:
    """Step 2: Write a full draft from the outline."""
    if state["error"]:
        return {}
    try:
        prompt = (
            f"Write a 400-word technical blog post following this outline:\n\n{state['outline']}"
        )
        response = llm.invoke(prompt)
        return {"draft": response.content, "error": ""}
    except Exception as exc:
        return {"error": f"draft_failed: {exc}"}

def check_factual_accuracy(state: ContentState) -> dict:
    """Parallel quality check 1: factual accuracy."""
    issues = []
    if len(state["draft"]) < 100:
        issues.append("Draft is suspiciously short — possible truncation.")
    return {"quality_issues": issues}

def check_tone(state: ContentState) -> dict:
    """Parallel quality check 2: tone and style."""
    issues = []
    if "i think" in state["draft"].lower() or "i believe" in state["draft"].lower():
        issues.append("Draft uses first-person hedging; prefer assertive technical voice.")
    return {"quality_issues": issues}

def check_structure(state: ContentState) -> dict:
    """Parallel quality check 3: document structure."""
    issues = []
    if "##" not in state["draft"] and "#" not in state["draft"]:
        issues.append("Draft appears to lack markdown headings.")
    return {"quality_issues": issues}

def editorial_review(state: ContentState) -> dict:
    """
    Human-in-the-loop checkpoint.
    The workflow pauses here until a human provides a decision.
    """
    summary = (
        f"Topic: {state['topic']}\n"
        f"Quality issues found: {len(state['quality_issues'])}\n"
    )
    if state["quality_issues"]:
        summary += "\n".join(f"  - {i}" for i in state["quality_issues"])
    else:
        summary += "  (none)"

    decision = interrupt(
        f"Editorial review required.\n\n{summary}\n\n"
        f"Type 'approve' to publish, 'reject' to discard."
    )
    return {"human_decision": decision}

def route_editorial(state: ContentState) -> str:
    if state["human_decision"].strip().lower() == "approve":
        return "publish"
    return "discard"

def route_after_draft(state: ContentState) -> str:
    if state["error"]:
        return "error_node"
    return "check_factual_accuracy"

def publish(state: ContentState) -> dict:
    return {"final_content": state["draft"]}

def discard(state: ContentState) -> dict:
    return {"final_content": "[Discarded by editor]"}

def error_node(state: ContentState) -> dict:
    print(f"Workflow error: {state['error']}")
    return {"final_content": f"Failed: {state['error']}"}

# ── Graph construction ─────────────────────────────────────────────────────────

memory = InMemorySaver()
builder = StateGraph(ContentState)

builder.add_node("create_outline", create_outline)
builder.add_node("write_draft", write_draft)
builder.add_node("check_factual_accuracy", check_factual_accuracy)
builder.add_node("check_tone", check_tone)
builder.add_node("check_structure", check_structure)
builder.add_node("editorial_review", editorial_review)
builder.add_node("publish", publish)
builder.add_node("discard", discard)
builder.add_node("error_node", error_node)

# Sequential: outline -> draft
builder.add_edge(START, "create_outline")
builder.add_edge("create_outline", "write_draft")

# Conditional after draft: error path or parallel quality checks
builder.add_conditional_edges(
    "write_draft",
    route_after_draft,
    {
        "error_node": "error_node",
        "check_factual_accuracy": "check_factual_accuracy",
    }
)

# Fan-out: write_draft also feeds the other two quality checkers in parallel
builder.add_edge("write_draft", "check_tone")
builder.add_edge("write_draft", "check_structure")

# Fan-in: all three quality checkers feed into editorial_review
builder.add_edge("check_factual_accuracy", "editorial_review")
builder.add_edge("check_tone", "editorial_review")
builder.add_edge("check_structure", "editorial_review")

# Human decision routing
builder.add_conditional_edges(
    "editorial_review",
    route_editorial,
    {"publish": "publish", "discard": "discard"}
)

builder.add_edge("publish", END)
builder.add_edge("discard", END)
builder.add_edge("error_node", END)

graph = builder.compile(checkpointer=memory)

# ── Execution ──────────────────────────────────────────────────────────────────

config = {"configurable": {"thread_id": "content-pipeline-001"}}
initial_state: ContentState = {
    "topic": "LangGraph agentic workflows in 2026",
    "outline": "",
    "draft": "",
    "quality_issues": [],
    "human_decision": "",
    "final_content": "",
    "error": "",
}

print("=== Phase 1: Running until human approval is needed ===")
for event in graph.stream(initial_state, config, stream_mode="values"):
    if event.get("draft"):
        print(f"Draft length: {len(event['draft'])} chars")
    if event.get("quality_issues"):
        print(f"Quality issues so far: {event['quality_issues']}")

print("\n=== Phase 2: Simulating operator approval ===")
for event in graph.stream(Command(resume="approve"), config, stream_mode="values"):
    if event.get("final_content"):
        print(f"Final content:\n{event['final_content'][:200]}...")
```

**What this workflow demonstrates:**

- `create_outline` -> `write_draft`: sequential dependency
- `write_draft` fans out to all three quality checkers simultaneously
- All three checkers fan in at `editorial_review`
- `interrupt()` pauses the graph at `editorial_review` and waits for a human
- `Command(resume="approve")` resumes execution with the human's decision
- `InMemorySaver` checkpoints state so the resume works correctly
- `error_node` handles draft generation failures gracefully

---

## Common Pitfalls and How to Avoid Them

**Pitfall 1: Unbounded loops without an exit counter.**
A loop that retries until the LLM produces "good enough" output can run forever if the quality criterion is ambiguous. Always add an `iteration_count` field to state, increment it in the loop node, and add a hard exit edge when it exceeds a maximum (typically 3–5 iterations).

**Pitfall 2: Mutable shared state causing race conditions in parallel nodes.**
When two parallel nodes both write to the same state key without a reducer, the last write wins and the first result is silently lost. Use `Annotated[list, operator.add]` for any field that parallel nodes write to. Design write patterns so each parallel worker appends to a list rather than overwriting a scalar.

**Pitfall 3: Forgetting to attach a checkpointer for HITL workflows.**
`interrupt()` requires a checkpointer to save state before pausing. If you call `builder.compile()` without `checkpointer=memory`, an interrupt will raise a `GraphInterrupt` exception that cannot be resumed. Always compile with a checkpointer when your graph contains `interrupt()`.

**Pitfall 4: Using one thread ID for all runs.**
Thread IDs namespace checkpoint state. If you reuse the same `thread_id` for multiple unrelated runs, each new run will load the prior run's state and behave unexpectedly. Generate a unique thread ID per workflow execution: `import uuid; thread_id = str(uuid.uuid4())`.

**Pitfall 5: Storing non-serialisable objects in state.**
Checkpointers serialise state to JSON or a binary format. Storing LangChain `Runnable` objects, open file handles, database connections, or any other non-serialisable value in state will cause checkpoint failures. Store serialisable primitives (strings, dicts, lists, numbers) in state; instantiate heavy objects inside nodes as local variables.

**Pitfall 6: Designing nodes that do too much.**
A node that fetches data, transforms it, calls an LLM, parses the response, and writes results to a database is almost impossible to debug and cannot be retried at a granular level. Keep each node focused on a single responsibility. This matches software engineering's Single Responsibility Principle and directly maps to observability: one span per meaningful operation.

**Pitfall 7: Inadequate human-in-the-loop context.**
A human reviewer who sees only "approve or reject?" without understanding what they are approving will either always approve (rubber-stamping) or escalate everything. Surface precisely the information needed for the decision: the proposed action, its expected consequences, and any relevant quality signals from automated checks.

---

## Hands-On Exercises

**Exercise 1 — Sequential pipeline (30 minutes):**
Build a three-node sequential workflow: `extract_keywords` -> `generate_summary` -> `format_output`. Each node should use Claude to process text. Run it against a short paragraph and print the final formatted output.

**Exercise 2 — Parallel quality checks (45 minutes):**
Extend Exercise 1 to add two parallel nodes after `generate_summary`: `check_length` (verify the summary is between 50 and 150 words) and `check_readability` (call an LLM to rate the summary on a 1–10 readability scale). Use an `Annotated[list, operator.add]` field to collect both results, then print them in a final aggregation node.

**Exercise 3 — Iterative refinement loop (45 minutes):**
Build a loop workflow: `generate_code` -> `run_tests` -> (pass? -> `done`) -> (fail? -> `generate_code`). Simulate `run_tests` by checking whether the generated code contains a specific string (e.g., `"def main"`). Add a `max_iterations: int` guard and verify it exits after 3 failed attempts.

**Exercise 4 — Human-in-the-loop approval (60 minutes):**
Build a workflow that generates a social media post about a given topic, runs a sentiment check (does the post contain negative words?), then pauses for human approval using `interrupt()`. Test both the approve and reject paths. Verify that after the interrupt the state is correctly restored by printing `graph.get_state(config).values`.

**Exercise 5 — CrewAI research crew (60 minutes):**
Using CrewAI, build a two-agent crew: a `MarketResearcher` and a `ReportWriter`. The researcher should use the `SerperDevTool` to look up recent news about a topic of your choice. The writer should take the researcher's findings and produce a 300-word structured report. Run with `Process.sequential` and print the final result.

**Exercise 6 — Full pipeline with error handling (90 minutes):**
Extend the complete production workflow from Section 10 to add PostgreSQL persistence instead of `InMemorySaver`. You will need to install `psycopg` and `langgraph-checkpoint-postgres`. Simulate a workflow crash by raising an exception mid-run, then restart the process and resume from the checkpoint.

---

## Summary

Agentic workflows transform individual AI agents into coordinated, production-grade pipelines. The five core patterns — sequential, parallel fan-out/fan-in, conditional branching, iterative loops, and human-in-the-loop — can be combined to model almost any real-world business process.

LangGraph provides the low-level primitives: `StateGraph`, nodes, edges, reducers, the `Send` API for dynamic parallelism, `interrupt()` for HITL pauses, and pluggable checkpointers for persistence. CrewAI provides a higher-level role-based abstraction that maps naturally to team structures and is faster to prototype.

Reliability comes from three layers: node-level try/except with structured error fields in state, exponential backoff for transient failures, and circuit breakers for persistent service outages. Observability comes from LangSmith's automatic tracing — which requires only two environment variables — and from structured JSON logging within nodes.

The patterns in this module are the foundation for everything that follows in the AI Development series. Module 7 will apply them to a specific high-value domain: building and deploying production AI assistants with tool use, long-term memory, and enterprise-grade safety guardrails.

---

## Further Reading

- [LangGraph Documentation — Workflows and Agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents): Official LangChain docs covering the full LangGraph API including graph construction, state management, and deployment options; the canonical reference for everything covered in Sections 4 and 8.
- [LangGraph Use Graph API — Parallel Execution and Send](https://docs.langchain.com/oss/python/langgraph/use-graph-api): Official documentation for parallel fan-out edges, the `Send` API for dynamic map-reduce, state reducers with `Annotated` and `operator.add`, and subgraph composition patterns.
- [CrewAI Documentation — Introduction](https://docs.crewai.com/en/introduction): Official CrewAI docs explaining the Agent/Task/Crew/Flow hierarchy, sequential vs. hierarchical process types, and the recommended production architecture using Flows as the top-level orchestrator.
- [LangSmith Observability](https://www.langchain.com/langsmith/observability): Overview of LangSmith's tracing capabilities for LangGraph workflows, including automatic span capture for LLM calls, tool calls, and node transitions, plus dashboards for cost and latency monitoring.
- [Introducing End-to-End OpenTelemetry Support in LangSmith](https://blog.langchain.com/end-to-end-opentelemetry-langsmith/): LangChain engineering blog post on integrating LangSmith traces with OpenTelemetry-compatible observability stacks (Datadog, Grafana, Elastic); essential reading for teams that already run OTEL infrastructure.
- [Agentic Workflows in 2026: Emerging Architectures and Design Patterns](https://vellum.ai/blog/agentic-workflows-emerging-architectures-and-design-patterns): Vellum AI's comprehensive survey of workflow architectures including ReAct, Self-Refine, Reflexion, and multi-agent topologies, with analysis of when each pattern outperforms simpler alternatives.
- [Building Human-in-the-Loop Agentic Workflows](https://towardsdatascience.com/building-human-in-the-loop-agentic-workflows/): Towards Data Science article with practical implementation guidance for HITL checkpoints, covering approval UIs, audit logging, and escalation policies for irreversible actions.
- [Mastering LangGraph Checkpointing: Best Practices for 2025](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025): Detailed guide to LangGraph's checkpointing system, covering `InMemorySaver`, `PostgresSaver`, thread IDs, state snapshots, and the time-travel debugging feature that lets you replay a workflow from any prior checkpoint.
