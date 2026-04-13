# Module 4: AI Agents and Agentic AI

**Subject:** AI Development
**Difficulty:** Intermediate to Advanced
**Estimated Time:** 330 minutes (including hands-on examples)
**Prerequisites:**
- Completed Module 1: Building a Basic AI Chatbot with No Framework — you must understand the messages array, the request-response cycle, and raw SDK calls
- Completed Module 2: The LangChain Framework — familiarity with LCEL chains, `ChatAnthropic`, and provider abstraction
- Completed Module 3: AI Workflows and LangGraph — understanding of `StateGraph`, nodes, edges, conditional routing, and the ReAct loop built in that module
- Python 3.10 or later
- An `ANTHROPIC_API_KEY` set in your environment (examples use the Anthropic SDK directly as well as LangGraph)

---

## Overview

The first three modules in this series covered the building blocks of working with language models: raw API calls, framework-level abstractions, and graph-based workflow orchestration. This module unifies those concepts under the broader paradigm that defines the frontier of applied AI in 2026: **agentic AI**.

An agent is not simply a better chatbot. It is an AI system that can set its own subtasks, choose its own tools, remember what it has done, and loop over its work until a goal is satisfied — without a human directing every step. Gartner estimates that 40% of enterprise applications will embed task-specific AI agents by the end of 2026, up from less than 5% in 2025. Understanding agents is no longer optional for any practitioner working in the AI space.

By the end of this module you will be able to:

- Explain what distinguishes an AI agent from a standard LLM call
- Identify and describe the five core properties of agentic systems: autonomy, tool use, memory, planning, and orchestration
- Understand the three main agent architectures: single-agent, multi-agent with a supervisor, and fully decentralised networks
- Implement a working tool-use loop against the Anthropic Claude API from scratch
- Implement a ReAct agent using LangGraph that performs multi-step reasoning
- Apply the three-layer guardrail model to make an agent production-safe
- Recognise the failure modes most likely to affect real agentic deployments

---

## Required Libraries and Packages

| Package | Version | Purpose | Install |
|---|---|---|---|
| `anthropic` | >= 0.89 | Anthropic Claude SDK for raw tool-use loop | `pip install anthropic` |
| `langgraph` | >= 1.1.6 | Graph-based agent orchestration (from Module 3) | `pip install langgraph` |
| `langchain-ollama` | >= 1.0.1 | Ollama chat model for LangGraph nodes (local, primary) | `pip install langchain-ollama` |
| `langchain-anthropic` | >= 1.0.0 | Claude chat model for LangGraph nodes (cloud, optional) | `pip install langchain-anthropic` |
| `langchain-core` | >= 1.2.26 | Tool definitions and message types | `pip install langchain-core` |
| `python-dotenv` | >= 1.0 | Load `.env` API keys | `pip install python-dotenv` |

Install everything at once:

```bash
# Pull local model first: ollama pull llama3.2
pip install anthropic langgraph langchain-ollama langchain-core python-dotenv
```

Set your API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # Linux / macOS
set ANTHROPIC_API_KEY=sk-ant-...        # Windows Command Prompt
```

Or place it in a `.env` file in your project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Key Concepts

### 1. What Makes Something an Agent?

In Module 1 you called an LLM, got a response, and returned it. That is a **single-turn inference call**: the model receives a prompt, produces one reply, and stops. In Module 2 you added memory, so the model could refer to earlier turns. In Module 3 you built a graph that could loop: the model could call a tool and then reason again based on the tool's result.

An AI **agent** is the extension of that last idea into a general architecture. An agent is a system where a language model is the decision-making core that:

1. Receives a goal (not just a prompt asking for a single answer)
2. Decomposes the goal into subtasks
3. Selects and invokes tools to accomplish each subtask
4. Observes the results and updates its plan
5. Decides when the goal has been met and stops

The critical distinction is **autonomy over a sequence of decisions**. A standard LLM call produces one output. An agent produces many outputs across many cycles and chooses when to stop.

#### Standard LLM Call vs. Agent — Side by Side

| Property | Standard LLM Call | AI Agent |
|---|---|---|
| Number of model calls | 1 | Many (until goal is met) |
| Decision authority | Human decides every step | Model decides what to do next |
| Tool use | Optional, single call | Central; model selects which tool and when |
| Memory | None (unless added manually) | Built-in; persists across steps |
| Goal representation | Single prompt | Persistent goal with sub-task tracking |
| Stopping condition | After one response | Model determines done vs. continue |
| Error handling | Caller handles failures | Agent can retry, replan, or escalate |

The phrase "agentic AI" describes systems built around this loop. It is not a specific technology — it is a design philosophy that treats the LLM as an autonomous reasoning engine rather than a stateless text transformer.

---

### 2. The Five Core Properties of Agentic Systems

Researchers and practitioners have converged on five properties that collectively define an agentic system. A system that has all five is fully agentic; a system with only two or three is partially agentic (and may be fine for your use case).

#### Property 1: Autonomy

Autonomy means the system can proceed from a goal to a completed result without a human directing each intermediate step. The degree of autonomy exists on a spectrum:

- **Level 0 — No autonomy:** Human writes every prompt, evaluates every output, and decides every next step.
- **Level 1 — Macro autonomy:** Human sets the goal; agent decides the subtasks. Human still approves each tool call.
- **Level 2 — Full autonomy:** Human sets the goal; agent executes everything and reports only the final result.

Production deployments in 2025 and 2026 mostly operate at Level 1. Full autonomy (Level 2) is technically achievable but introduces reliability and safety risks that are difficult to manage at scale. The right autonomy level depends on the stakes of a wrong decision.

#### Property 2: Tool Use

Tool use is the mechanism that allows an agent to interact with the world beyond its training data. Without tools, an agent is a very sophisticated text generator. With tools, it can:

- Fetch live data (web search, database queries)
- Write and execute code
- Call REST APIs (send emails, create calendar events, update records)
- Read and write files
- Invoke other agents

Tools are defined as JSON Schema objects that describe the function name, its purpose, and the parameters it accepts. The model does not execute tools — it outputs a structured **tool call** containing the function name and arguments, and your application code performs the actual execution, then feeds the result back to the model.

This separation is architecturally important: the model decides *what* to call and *with what arguments*; your code decides *how* to execute it and *what safety checks* to apply before doing so.

#### Property 3: Memory

Unlike a standard LLM call where every turn starts fresh, an agent must track what it has done and what it has learned. Memory in agentic systems is divided into four types that mirror human cognition:

| Memory Type | What It Stores | Typical Implementation |
|---|---|---|
| **Working memory** | The current conversation turns and in-progress reasoning | The model's context window (messages array) |
| **Episodic memory** | Past interactions and previous task outcomes | Vector database or event log with semantic search |
| **Semantic memory** | Factual knowledge: domain facts, user profiles, product specs | Structured database + vector embeddings |
| **Procedural memory** | How to perform tasks: workflow steps, decision trees | Workflow database, retrieved similar past plans |

In practice, working memory is always present (it is the context window). The other three types require external storage and a retrieval strategy. Retrieval-Augmented Generation (RAG), covered in the LLM subject, is the canonical pattern for episodic and semantic memory.

**Memory decay and forgetting** are real design concerns. A vector store that grows indefinitely will return low-quality results. Production memory systems prune stale facts, weight recent episodes more heavily, and distinguish between immutable facts (product SKUs) and mutable state (task status).

#### Property 4: Planning and Multi-Step Reasoning

Planning is the ability to decompose a complex goal into an ordered sequence of steps before taking any action. Without planning, an agent acts greedily — it takes the most obvious immediate action, which often leads to a dead end several steps later.

Key planning techniques include:

- **Chain-of-Thought (CoT):** The model is prompted (or trained) to write out intermediate reasoning before producing its answer. This dramatically reduces errors on multi-step tasks.
- **Task decomposition:** Given "Write a market research report on Company X," the agent explicitly breaks this into: (1) identify competitors, (2) gather financial data, (3) analyze product features, (4) synthesize findings, (5) write the report.
- **Tree of Thoughts (ToT):** Instead of one chain of reasoning, the model explores multiple reasoning paths in parallel and selects the best branch. Useful when the correct approach is not obvious upfront.
- **Plan-Execute-Reflect:** The agent generates a plan, executes each step, compares the result against the plan, and revises the plan if reality diverged from expectations.

#### Property 5: Orchestration

Orchestration is the coordination layer that routes tasks between agents, manages state across the whole workflow, and decides when to hand off from one agent to another. In a single-agent system, orchestration is implicit — the agent's internal loop is the only coordination needed. In multi-agent systems, orchestration becomes an explicit design concern.

---

### 3. The Perceive-Reason-Act Loop

Every agent — regardless of its architecture or framework — runs some variant of the Perceive-Reason-Act loop:

```
┌──────────────────────────────────────────────────┐
│                   Agent Loop                     │
│                                                  │
│   1. PERCEIVE   ──►  Observe the current state   │
│        │             (context window, tool       │
│        │              results, memory)           │
│        ▼                                         │
│   2. REASON    ──►  Decide what to do next       │
│        │             (which tool? which          │
│        │              subtask? done?)             │
│        ▼                                         │
│   3. ACT       ──►  Execute the decision         │
│        │             (call a tool, update        │
│        │              memory, produce output)    │
│        │                                         │
│        └──────────────────────────────►          │
│               Loop until goal is met             │
└──────────────────────────────────────────────────┘
```

The loop terminates when the model's reasoning step concludes that the goal has been satisfied, or when an external condition is met (a timeout, a human approval, an error threshold).

---

### 4. Tool Use in Practice: The Anthropic Tool-Use Lifecycle

The Anthropic Claude API implements tool use as a multi-turn protocol. Understanding each phase prevents the most common bugs.

#### Phase 1 — Define

You describe each tool as a JSON object with three required fields:

```json
{
  "name": "get_stock_price",
  "description": "Returns the current stock price for a given ticker symbol. Use this when the user asks about the price of a publicly traded company.",
  "input_schema": {
    "type": "object",
    "properties": {
      "ticker": {
        "type": "string",
        "description": "The stock ticker symbol, e.g. AAPL, MSFT, GOOG"
      },
      "currency": {
        "type": "string",
        "enum": ["USD", "EUR", "GBP"],
        "description": "The currency to return the price in. Defaults to USD."
      }
    },
    "required": ["ticker"]
  }
}
```

The `description` field is the most important part. The model reads descriptions — not your code — to decide whether and when to call a tool. Vague descriptions produce inconsistent tool selection.

#### Phase 2 — Call

You send the tool definitions and the user message to the API. If Claude decides to call a tool, the response arrives with `stop_reason: "tool_use"` and a `tool_use` block in the content:

```json
{
  "stop_reason": "tool_use",
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_01abc",
      "name": "get_stock_price",
      "input": { "ticker": "AAPL", "currency": "USD" }
    }
  ]
}
```

#### Phase 3 — Execute

Your application code reads the tool name and input, executes the actual function (in this case, calling a stock data API), and collects the result.

#### Phase 4 — Return

You append the assistant's response to the messages array, then append a `tool_result` message and send the whole conversation back to the model:

```python
messages.append({"role": "assistant", "content": response.content})
messages.append({
    "role": "user",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": "toolu_01abc",
            "content": '{"price": 213.45, "currency": "USD", "as_of": "2026-04-03T14:30:00Z"}'
        }
    ]
})
```

#### Phase 5 — Resume

The model now has the tool result in its context and generates a final response or decides to call another tool. The loop continues until `stop_reason` is `"end_turn"`.

---

### 5. The ReAct Pattern

ReAct (Reasoning + Acting) is the most widely deployed single-agent design pattern. It was introduced in the 2022 paper "ReAct: Synergizing Reasoning and Acting in Language Models" by Yao et al. and has since become the default loop used by LangGraph, AutoGen, and most production agent frameworks.

The pattern works by interleaving three alternating types of model output:

| Step | Label | Content |
|---|---|---|
| Thought | `Thought:` | The model explains its current understanding and what it plans to do next |
| Action | `Action:` | The tool name and arguments |
| Observation | `Observation:` | The tool result, injected by your application code |

This continues until the model outputs `Final Answer:` instead of another `Action:`.

**Why this beats raw tool calling:** In a plain tool-use loop the model's reasoning is invisible — you only see the tool calls and results. ReAct forces the reasoning to be explicit in the transcript, which makes the agent easier to debug, evaluate, and explain to stakeholders. It also improves accuracy: by articulating its reasoning before acting, the model catches errors in its own logic before they propagate.

**Example ReAct trace for "What is the market cap of the largest EV company?":**

```
Thought: The user wants the market cap of the largest EV company by market capitalisation.
         I should first find which company that is, then look up its current market cap.

Action: web_search
Action Input: {"query": "largest EV company by market cap 2026"}

Observation: Tesla (TSLA) holds the largest market cap among EV companies at approximately
             $800 billion as of early 2026, followed by BYD at approximately $120 billion.

Thought: Tesla is the largest EV company. Now I need its current market cap.

Action: get_stock_price
Action Input: {"ticker": "TSLA", "currency": "USD"}

Observation: {"price": 253.10, "shares_outstanding": 3190000000, "market_cap": 807387000000}

Thought: I now have all the information needed to answer the question.

Final Answer: As of April 2026, Tesla (TSLA) is the largest EV company by market
              capitalisation, with a market cap of approximately $807 billion.
```

---

### 6. The Reflection Pattern

The reflection pattern is a quality-improvement loop that runs after the agent produces an initial output. The agent acts as its own reviewer:

1. **Generate** — produce an initial output (a plan, a draft, a code snippet)
2. **Critique** — evaluate the output against criteria (correctness, completeness, style, safety)
3. **Revise** — produce an improved version based on the critique
4. **Accept or loop** — if the revised output meets the criteria, stop; otherwise, go back to step 2

The reflection step can be handled by the same model that generated the output (self-reflection) or by a separate model acting as a dedicated critic. Research by Shinn et al. (2023, "Reflexion") demonstrated that reflection loops consistently produce passing code and prose within two to three iterations without any gradient-based training.

Reflection is the right pattern when:
- Quality can be assessed programmatically (unit tests, schema validation) or by the LLM itself
- The initial generation has a meaningful error rate that reflection can reduce
- Latency allows for multiple model calls (reflection adds at least one additional call per iteration)

---

### 7. Agent Architecture Patterns

#### Pattern A: Single Agent with Tools

The simplest architecture. One model instance runs the Perceive-Reason-Act loop and has access to a set of tools. Everything happens in one context window.

```
User Goal
    │
    ▼
┌─────────────────────────┐
│       Agent             │
│  (LLM + Tool Selector)  │
│                         │
│  Tool 1: web_search     │
│  Tool 2: code_executor  │
│  Tool 3: send_email     │
└────────────┬────────────┘
             │
             ▼
        Final Result
```

**When to use:** Tasks that fit within one context window, do not require specialisation, and do not benefit from parallelism. Most production agents start here.

**Limitations:** Context window overload on long tasks; generalised model may perform worse than a specialist model on domain-specific subtasks; no parallelism — steps are strictly sequential.

#### Pattern B: Orchestrator with Subagents (Supervisor Pattern)

A higher-level orchestrator agent decomposes the goal into subtasks and delegates each subtask to a specialised subagent. Subagents report results back to the orchestrator, which synthesises the final output.

```
User Goal
    │
    ▼
┌─────────────────────────────────────────────┐
│              Orchestrator Agent              │
│   (decomposes goal, assigns tasks, merges)  │
└───────────────────┬─────────────────────────┘
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Research │  │  Analyst │  │  Writer  │
│  Agent   │  │  Agent   │  │  Agent   │
└──────────┘  └──────────┘  └──────────┘
```

**When to use:** Tasks that can be decomposed into logically independent subtasks; workflows where specialist performance matters; scenarios where parallelism would meaningfully reduce latency.

**Key design decisions:**
- How does the orchestrator communicate subtask requirements to subagents? (structured prompts, shared state schema)
- How do results flow back? (direct return, shared memory store, event bus)
- What happens if a subagent fails? (retry logic in the orchestrator, fallback agent, escalation to human)

#### Pattern C: Fully Decentralised Agent Network

Agents communicate peer-to-peer without a central orchestrator. Any agent can route a task to any other agent based on capability discovery.

**When to use:** Systems where the orchestration logic itself is too complex to encode in a single supervisor; scenarios requiring dynamic, emergent task routing; research and experimental systems.

**In practice:** Decentralised networks are considerably harder to debug and reason about than supervisor patterns. Most production teams opt for the supervisor pattern even when it requires a more sophisticated orchestrator, because the centralised control point makes observability and incident response much more tractable.

#### Architecture Selection Guide

| Factor | Single Agent | Orchestrator + Subagents | Decentralised Network |
|---|---|---|---|
| Task fits in one context window | Always | Not required | Not required |
| Subtasks are independent | N/A | Required | Optional |
| Parallel execution needed | No | Yes | Yes |
| Specialist model required per domain | No | Yes | Yes |
| Observability requirements | Simple | Moderate | Complex |
| Team experience with distributed systems | Not needed | Moderate | High |

---

### 8. Context Management

Context management is one of the most consequential engineering decisions in agent design. The context window is finite; every token spent on history, tool definitions, and intermediate reasoning is a token unavailable for the task itself.

**Strategies for managing context in long-running agents:**

| Strategy | Description | Trade-off |
|---|---|---|
| Sliding window | Keep only the N most recent messages | Loses distant context; cheap to implement |
| Summarisation | Periodically compress history into a summary | Preserves gist; summary may lose key details |
| Selective retention | Keep only messages tagged as important | Requires a classification step per message |
| External memory with retrieval | Store all history externally; retrieve relevant chunks | Handles unlimited history; adds retrieval latency |

The correct strategy depends on task duration, the importance of early context, and latency constraints. A short task (< 20 tool calls) usually fits with a sliding window. A multi-session task (spanning hours or days) requires external memory with retrieval.

---

### 9. Agent Safety and Guardrails

Agents that act autonomously on real-world systems — calling APIs, writing to databases, sending emails — carry real consequences when they go wrong. A badly specified tool description, an ambiguous goal, or a model hallucination can cascade into damage that is difficult to reverse. The following framework is used by production teams in 2025 and 2026 to bound that risk.

#### The Three-Layer Guardrail Model

Production guardrails are applied at three layers with different latency profiles:

**Layer 1 — Rule-Based Validators (sub-10ms)**
Deterministic checks applied before any model call and before any tool execution:
- Input validation: reject malformed requests, enforce field types and length limits
- PII detection: block inputs that contain personal data if the agent is not authorised to process it
- Keyword blocklists: reject inputs containing terms that fall outside the agent's authorised domain
- Output schema enforcement: reject model outputs that do not conform to the expected JSON structure

**Layer 2 — ML Classifiers (50–200ms)**
Lightweight classification models that catch issues rule-based validators miss:
- Intent classification: verify the model's planned action is within the agent's authorised scope
- Toxicity and bias detection
- Anomaly detection: flag tool call sequences that are statistically unusual compared to normal operation

**Layer 3 — LLM Semantic Validation (300ms–2s)**
A second LLM call that verifies correctness before a high-stakes action is executed:
- Groundedness checking: does the agent's planned action follow logically from the context?
- Policy alignment: does the action comply with the rules stated in the system prompt?
- Factual consistency: for agents generating content, does the output contradict the sources it retrieved?

Not every action requires all three layers. A risk-based routing policy applies only the appropriate layer(s) based on the action's potential impact:

```
Low-impact action  → Layer 1 only (e.g., read-only database query)
Medium-impact      → Layers 1 + 2 (e.g., drafting an email before human review)
High-impact        → Layers 1 + 2 + 3 (e.g., sending an email, updating a financial record)
Irreversible       → Layers 1 + 2 + 3 + human approval
```

#### Human-in-the-Loop Checkpoints

For any action that is difficult to reverse, build in a pause-and-confirm step. LangGraph's `interrupt()` mechanism (from Module 3) is the standard way to implement this: the graph pauses at a defined node, surfaces the pending action to a human reviewer, and resumes only after approval is granted.

Human-in-the-loop checkpoints should be applied to:
- Any action that modifies external state (writes to a database, sends a message, deploys code)
- Any decision that affects a third party without their direct involvement
- Any output that will be published publicly without further editorial review

#### Common Agent Failure Modes

| Failure Mode | Description | Mitigation |
|---|---|---|
| **Hallucinated tool calls** | Model invents tool names or parameters that do not exist | Use `strict: true` in tool definitions; validate tool names before execution |
| **Goal misgeneralisation** | Agent pursues a proxy goal that differs from the intended goal | Write precise, measurable goal specifications; use reflection to verify alignment |
| **Runaway loops** | Agent loops indefinitely without reaching a stopping condition | Set a maximum iteration count; enforce timeouts per tool call |
| **Permission creep** | Agent requests or uses permissions beyond what the task requires | Apply the principle of least privilege: provide only the tools actually needed for the task |
| **Cascading errors** | An error in step 3 of a 10-step plan corrupts all subsequent steps | Validate tool results before incorporating them into the next step's context |
| **Context poisoning** | Malicious input in a retrieved document instructs the agent to change its behaviour | Sanitise and isolate externally retrieved content; treat external data as untrusted |

---

### 10. Agentic Frameworks in 2026

Several frameworks have matured to production-readiness for building agentic systems. You have already used LangGraph in Module 3. Here is how the major options compare:

| Framework | Maintainer | Key Strengths | Best For |
|---|---|---|---|
| **LangGraph** | LangChain | First-class state management, human-in-the-loop, streaming, production-ready checkpointing (v1.1.6 as of April 2026) | Production agents requiring persistence, branching, and auditability |
| **AutoGen** | Microsoft | Multi-agent conversation protocols, built-in role assignment, easy supervisor/subagent setup | Multi-agent systems, research experimentation |
| **CrewAI** | CrewAI Inc. | Role-based agent definitions, declarative crew configuration, easy onboarding | Team-structured task workflows, quick prototyping |
| **Anthropic Agent SDK** | Anthropic | Native Claude integration, built-in tool execution, MCP support | Claude-first applications, tight integration with Anthropic's tool ecosystem |
| **Raw SDK** | Anthropic / OpenAI | Zero abstraction overhead, maximum control | Simple agents, custom loops, learning purposes |

The framework you choose should be driven by:
1. **Production requirements** — do you need persistence, checkpointing, human-in-the-loop? (LangGraph)
2. **Multi-agent complexity** — do you need structured agent-to-agent communication? (AutoGen, CrewAI)
3. **Provider lock-in tolerance** — are you comfortable with Claude-only? (Anthropic Agent SDK)
4. **Team familiarity** — what does your team already know from prior modules?

---

## Hands-On Examples

### Example 1: Raw Tool-Use Loop with the Anthropic SDK

This example implements a minimal but complete agent loop from scratch — no frameworks. It is the best way to understand exactly what happens inside a tool-use cycle before working with higher-level abstractions.

The agent has two tools: `get_current_time` and `calculate`. It receives a goal, loops until the model signals it is done, and executes each tool call your application code handles.

```python
import anthropic
import json
import math
from datetime import datetime, timezone

# --- Tool implementations (your code, not the model's) ---

def get_current_time() -> dict:
    """Return the current UTC time."""
    now = datetime.now(timezone.utc)
    return {
        "utc_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unix_timestamp": int(now.timestamp()),
    }

def calculate(expression: str) -> dict:
    """
    Evaluate a safe mathematical expression.
    Supports: +, -, *, /, **, sqrt, abs, round, int, float.
    """
    allowed_names = {
        "sqrt": math.sqrt,
        "abs": abs,
        "round": round,
        "int": int,
        "float": float,
    }
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return {"result": result, "expression": expression}
    except Exception as e:
        return {"error": str(e), "expression": expression}

# --- Tool definitions (what the model sees) ---

TOOLS = [
    {
        "name": "get_current_time",
        "description": (
            "Returns the current UTC time as an ISO 8601 string and as a Unix timestamp. "
            "Use this when the user asks what time it is or needs the current date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "calculate",
        "description": (
            "Evaluates a mathematical expression and returns the numeric result. "
            "Use this for arithmetic, square roots, powers, or rounding. "
            "Expression must be a valid Python math expression as a string."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A Python math expression, e.g. '(3 + 4) * 2' or 'sqrt(144)'",
                }
            },
            "required": ["expression"],
        },
    },
]

# --- Tool dispatcher ---

def dispatch_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool by name and return the result as a JSON string."""
    if tool_name == "get_current_time":
        result = get_current_time()
    elif tool_name == "calculate":
        result = calculate(tool_input["expression"])
    else:
        result = {"error": f"Unknown tool: {tool_name}"}
    return json.dumps(result)

# --- Agent loop ---

def run_agent(goal: str, max_iterations: int = 10) -> str:
    """
    Run a tool-use agent loop until the model signals end_turn or
    max_iterations is reached (a safety guardrail against runaway loops).
    """
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": goal}]

    for iteration in range(max_iterations):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )

        print(f"\n--- Iteration {iteration + 1} | stop_reason: {response.stop_reason} ---")

        # Append assistant's full response to the conversation
        messages.append({"role": "assistant", "content": response.content})

        # If the model is done, extract and return the final text
        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    return block.text
            return "Agent completed without a text response."

        # If the model wants to call tools, execute all of them
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  Tool call: {block.name}({json.dumps(block.input)})")
                    result_str = dispatch_tool(block.name, block.input)
                    print(f"  Tool result: {result_str}")
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        }
                    )
            # Return all tool results in a single user message
            messages.append({"role": "user", "content": tool_results})

    return "Agent reached maximum iteration limit without completing the goal."

# --- Run it ---

if __name__ == "__main__":
    goal = (
        "What is the current UTC time? "
        "Also, if I have a right triangle with legs of length 9 and 40, "
        "what is the length of the hypotenuse?"
    )
    print(f"Goal: {goal}\n")
    final_answer = run_agent(goal)
    print(f"\nFinal answer:\n{final_answer}")
```

**What to observe when you run this:**

- The first iteration will produce two `tool_use` blocks (one for `get_current_time`, one for `calculate`).
- Your application code executes both, collects the results, and sends them back.
- The second iteration will produce `stop_reason: end_turn` with a text block containing the synthesised answer.
- The `max_iterations` parameter is the guardrail that prevents runaway loops.

---

### Example 2: ReAct Agent with LangGraph

This example builds a ReAct agent using LangGraph's `create_react_agent` helper, which implements the full Thought-Action-Observation loop. It extends what you built in Module 3 with a cleaner API and demonstrates how frameworks abstract the raw loop from Example 1.

```python
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# LOCAL (primary): Pull model first with: ollama pull llama3.2
# Tool calling requires a model that supports it.
# llama3.2, qwen2.5:7b, and mistral all support tool use via Ollama.
llm = ChatOllama(model="llama3.2", temperature=0)

# --- Optional: Cloud API alternative ---
# from dotenv import load_dotenv
# from langchain_anthropic import ChatAnthropic
# load_dotenv()
# llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)

# --- Define tools using LangChain's @tool decorator ---

@tool
def word_count(text: str) -> int:
    """Count the number of words in a given text string."""
    return len(text.split())

@tool
def reverse_string(text: str) -> str:
    """Reverse the characters in a given string."""
    return text[::-1]

@tool
def character_frequency(text: str, character: str) -> int:
    """
    Count how many times a specific character appears in the given text.
    The character argument must be a single character string.
    """
    if len(character) != 1:
        return -1
    return text.count(character)

# --- Assemble the agent ---

tools = [word_count, reverse_string, character_frequency]

agent = create_react_agent(llm, tools)

# --- Run with a multi-step goal ---

def run_react_agent(goal: str) -> None:
    print(f"Goal: {goal}\n")
    inputs = {"messages": [("user", goal)]}

    for chunk in agent.stream(inputs, stream_mode="values"):
        last_message = chunk["messages"][-1]
        last_message.pretty_print()

if __name__ == "__main__":
    goal = (
        "Take the sentence 'The quick brown fox jumps over the lazy dog'. "
        "First, count how many words it contains. "
        "Then, count how many times the letter 'o' appears. "
        "Finally, reverse the entire sentence and report all three results together."
    )
    run_react_agent(goal)
```

**What to observe:**

- `create_react_agent` handles the Thought-Action-Observation loop without any manual message management.
- The `stream_mode="values"` call lets you observe the full state at each step, including intermediate tool calls.
- The agent will make three tool calls (one per subtask) before generating the final summary.
- LangGraph's prebuilt agent already includes a default iteration limit. For production, override it with `recursion_limit` in the config.

---

### Example 3: Orchestrator and Subagent Pattern

This example demonstrates the supervisor pattern using pure Python and the Anthropic SDK. An orchestrator agent decomposes a research goal into subtasks and delegates each to a specialist subagent.

```python
import anthropic
import json

client = anthropic.Anthropic()

# --- Subagent: Research Specialist ---

def research_subagent(topic: str) -> str:
    """
    A specialist subagent that returns a brief factual summary on a topic.
    In a real system this agent would use web_search and retrieval tools.
    Here it uses the model's knowledge for demonstration purposes.
    """
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=(
            "You are a research specialist. When given a topic, produce a concise "
            "factual summary in 3 to 5 sentences. Include only verifiable facts. "
            "Do not editorialize."
        ),
        messages=[{"role": "user", "content": f"Summarize the key facts about: {topic}"}],
    )
    return response.content[0].text

# --- Subagent: Analyst ---

def analyst_subagent(data_points: list[str]) -> str:
    """
    A specialist subagent that identifies patterns across multiple data points.
    """
    joined = "\n".join(f"- {p}" for p in data_points)
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=(
            "You are a data analyst. When given a list of facts or observations, "
            "identify the two or three most significant patterns or insights. "
            "Be direct and concise."
        ),
        messages=[{"role": "user", "content": f"Identify key patterns in these findings:\n{joined}"}],
    )
    return response.content[0].text

# --- Orchestrator ---

def orchestrator(goal: str) -> str:
    """
    An orchestrator that uses Claude to decompose the goal into subtasks,
    delegates each to a subagent, then synthesises the final answer.
    """
    print(f"Orchestrator received goal: {goal}\n")

    # Step 1: Decompose the goal into research topics
    decompose_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=(
            "You are a planning agent. When given a research goal, identify exactly "
            "three specific sub-topics that need to be researched to answer the goal. "
            "Respond with a JSON object with a single key 'topics' containing a list "
            "of three strings."
        ),
        messages=[{"role": "user", "content": goal}],
    )

    raw = decompose_response.content[0].text
    topics_data = json.loads(raw)
    topics = topics_data["topics"]
    print(f"Decomposed into topics: {topics}\n")

    # Step 2: Delegate each topic to the research subagent
    research_results = []
    for topic in topics:
        print(f"Research subagent working on: {topic}")
        summary = research_subagent(topic)
        research_results.append(summary)
        print(f"  Result: {summary[:120]}...\n")

    # Step 3: Delegate analysis to the analyst subagent
    print("Analyst subagent synthesising findings...")
    analysis = analyst_subagent(research_results)
    print(f"Analysis: {analysis[:200]}...\n")

    # Step 4: Orchestrator synthesises the final report
    synthesis_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=(
            "You are a report writer. You will receive research summaries and an "
            "analysis of their key patterns. Write a clear, well-structured answer "
            "to the original goal in two to three paragraphs."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Original goal: {goal}\n\n"
                    f"Research summaries:\n"
                    + "\n\n".join(research_results)
                    + f"\n\nKey analysis:\n{analysis}"
                ),
            }
        ],
    )

    return synthesis_response.content[0].text

# --- Run ---

if __name__ == "__main__":
    goal = "How do electric vehicle battery technologies differ in terms of energy density, lifespan, and environmental impact?"
    result = orchestrator(goal)
    print("=== Final Report ===")
    print(result)
```

**What to observe:**

- The orchestrator uses a more powerful model (`claude-sonnet-4-6`) for planning and synthesis; subagents use a faster, cheaper model (`claude-haiku-4-5`) for specialised tasks.
- Each agent call is independent: subagents have no knowledge of each other. All coordination is done by the orchestrator.
- The decomposition step (producing a JSON list of topics) is a structured output task — this is where `strict: true` or a Pydantic schema validation would be added in production code.
- In a production system, Steps 2a, 2b, and 2c (the three research subagent calls) would run in parallel using `asyncio.gather` to reduce end-to-end latency.

---

## Common Mistakes and Pitfalls

**1. Writing vague tool descriptions.**
The model uses descriptions to decide which tool to call and with what arguments. A description like "Gets data" will produce inconsistent behaviour. A good description answers: what does this tool do, when should it be used, and what format does the input take?

**2. Forgetting to append the assistant's response before tool results.**
The Anthropic tool-use protocol requires the conversation to reflect the full exchange: user message → assistant message (containing the `tool_use` blocks) → user message (containing the `tool_result` blocks). Skipping the assistant message append causes a 400 error on the next API call.

**3. No iteration limit.**
An agent that has no maximum step count will loop forever if the model enters a reasoning cycle that never reaches a conclusion. Always set `max_iterations` or `recursion_limit` and handle the case where it is reached gracefully.

**4. Over-tooling.**
Providing an agent with 30 tools increases token cost (tool definitions consume input tokens), confuses the model's tool selection, and widens the attack surface. Start with the minimum set of tools the task requires. Add more only when you observe specific capability gaps.

**5. Treating tool results as trusted.**
If a tool retrieves content from the web or from user-provided files, that content may contain adversarial instructions (prompt injection). Sanitise and isolate externally retrieved content before incorporating it into the model's context.

**6. No human-in-the-loop for irreversible actions.**
Any action that cannot be undone — sending an email, deleting a record, deploying code to production — must have a human approval checkpoint. Build this into the graph from the start; retrofitting it later is much harder.

**7. Confusing single-agent loops with multi-agent systems.**
If your "multi-agent system" is just two sequential LLM calls where the second call receives the first call's output, that is a two-step chain, not a multi-agent system. True multi-agent systems involve agents with distinct roles, separate context windows, and a coordination mechanism between them.

---

## Real-World Use Cases

| Domain | Agent Type | What It Does |
|---|---|---|
| Software engineering | Single agent + code tools | Reads a GitHub issue, writes a fix, runs tests, opens a pull request (e.g., Devin, SWE-agent) |
| Customer support | Single agent + CRM tools | Interprets a support ticket, looks up customer history, drafts a resolution, escalates if needed |
| Financial analysis | Orchestrator + subagents | Orchestrator assigns research, data retrieval, and risk analysis to specialist subagents; synthesises a report |
| Data pipeline monitoring | Single agent + observability tools | Detects anomalies in pipeline metrics, diagnoses root causes, applies a remediation playbook |
| Content production | Reflection loop | Drafts an article, critiques it for factual accuracy and style, revises until quality threshold is met |
| Legal document review | Multi-agent | One agent extracts clauses; another flags risk; a supervisor produces a structured risk summary |
| Code review | Reflection loop + tools | Reads a diff, runs static analysis tools, critiques the code quality, produces review comments |

---

## Summary

| Concept | Key Takeaway |
|---|---|
| Agent vs. LLM call | An agent runs many model calls in a loop; a standard call runs exactly one |
| Five core properties | Autonomy, tool use, memory, planning, orchestration — all five define a fully agentic system |
| Tool use lifecycle | Define → Call → Execute (your code) → Return (tool_result) → Resume |
| ReAct pattern | Interleaved Thought-Action-Observation makes reasoning explicit and auditable |
| Reflection pattern | Generate → Critique → Revise → Accept; improves quality in 2–3 iterations |
| Single-agent limit | Context window overload and lack of parallelism are the main scaling constraints |
| Supervisor pattern | Orchestrator decomposes goal; specialist subagents execute in parallel |
| Three-layer guardrails | Rule-based (fast) → ML classifiers (medium) → LLM semantic validation (slow) |
| Context management | Sliding window or external memory + retrieval depending on task length |
| Human-in-the-loop | Mandatory for irreversible actions; use LangGraph `interrupt()` |

---

## Further Reading

1. **[Anthropic Tool Use Documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)** — The official reference for defining tools, handling tool calls, client vs. server tools, and strict schema enforcement for Claude. Start here before building any production tool-use loop.

2. **[LangGraph Agent Orchestration Framework](https://www.langchain.com/langgraph)** — The official LangGraph site covering its design philosophy, production runtime, and how it handles persistence, streaming, and human-in-the-loop. Directly extends the graph concepts from Module 3.

3. **[What is a ReAct Agent? — IBM Think](https://www.ibm.com/think/topics/react-agent)** — A clear conceptual explanation of the ReAct pattern, its Thought-Action-Observation cycle, and its advantages over plain tool calling for multi-step reasoning tasks.

4. **[State of AI Agent Memory 2026 — mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026)** — A practitioner survey of the four memory types (working, episodic, semantic, procedural), how vector and graph stores implement them, and the open engineering challenges in memory for long-running agents.

5. **[AI Agent Guardrails Production Guide 2026 — Authority Partners](https://authoritypartners.com/insights/ai-agent-guardrails-production-guide-for-2026/)** — A detailed walkthrough of the three-layer guardrail model (rule-based, ML classifiers, LLM semantic validation), risk-based routing, and accuracy-first optimisation strategies for production agent deployments.

6. **[LangGraph vs CrewAI vs AutoGen: Framework Comparison 2026](https://www.meta-intelligence.tech/en/insight-ai-agent-frameworks)** — A side-by-side comparison of the major agentic frameworks, covering architecture, use case fit, production maturity, and observability support as of early 2026.

7. **[Agentic AI Design Patterns 2026 — SitePoint](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/)** — A comprehensive survey of agentic design patterns including Planning, Tool Calling, Reflection, Collaboration, and Memory, with code examples and guidance on combining patterns for complex systems.

8. **[AI Agent Memory: Types, Architecture and Implementation — Redis](https://redis.io/blog/ai-agent-memory-stateful-systems/)** — A technical deep-dive into implementing short-term and long-term memory for AI agents, with architecture diagrams and practical guidance on when to use in-memory caches versus vector databases versus structured stores.

---

Sources:
- [Agentic LLMs in 2025: How AI Is Becoming Self-Directed — Data Science Dojo](https://datasciencedojo.com/blog/agentic-llm-in-2025/)
- [What Is Agentic AI? Characteristics, Use Cases & Setup in 2026 — Atlan](https://atlan.com/know/what-is-agentic-ai/)
- [Tool use with Claude — Anthropic Documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [What is a ReAct Agent? — IBM](https://www.ibm.com/think/topics/react-agent)
- [AI Agent Guardrails: Production Guide for 2026 — Authority Partners](https://authoritypartners.com/insights/ai-agent-guardrails-production-guide-for-2026/)
- [Agentic Design Patterns: The 2026 Guide — SitePoint](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/)
- [Multi-Agent Systems and AI Orchestration Guide 2026 — Codebridge](https://www.codebridge.tech/articles/mastering-multi-agent-orchestration-coordination-is-the-new-scale-frontier)
- [State of AI Agent Memory 2026 — mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026)
- [AI Agent Memory: Types, Architecture and Implementation — Redis](https://redis.io/blog/ai-agent-memory-stateful-systems/)
- [LangGraph vs CrewAI vs AutoGen: Framework Comparison 2026 — Meta Intelligence](https://www.meta-intelligence.tech/en/insight-ai-agent-frameworks)
