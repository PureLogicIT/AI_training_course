# Module 7: Model Context Protocol (MCP)

**Subject:** AI Development
**Difficulty:** Advanced
**Estimated Time:** 420 minutes (including hands-on examples)
**Prerequisites:**
- Completed Module 1: Building a Basic AI Chatbot with No Framework — you must understand raw SDK calls, the messages array, and the Anthropic API request/response cycle
- Completed Module 2: The LangChain Framework — familiarity with tool definitions and provider abstraction
- Completed Module 3: AI Workflows and LangGraph — understanding of graph-based orchestration is helpful context
- Completed Module 4: AI Agents and Agentic AI — solid grasp of tool-use loops, function calling, and the difference between tools and agents
- Completed Module 5: Retrieval-Augmented Generation — helpful for understanding the external-data access pattern MCP generalises
- Completed Module 6: Agentic Workflows — strong grasp of multi-step workflows, LangGraph, and multi-agent coordination; this module positions MCP as the standardised plug layer that makes tools in those workflows reusable and interoperable
- Python 3.10 or later
- An `ANTHROPIC_API_KEY` set in your environment

---

## Overview

Every agentic workflow you built in Module 6 had the same hidden weakness: its tools were hardwired to a single framework. A LangGraph agent could call a web-search tool, but only LangGraph knew how to wire it up. A CrewAI crew could query a database, but its tool definition was CrewAI-specific code that could not be reused in a different agent system without rewriting it. Multiply this across dozens of tools and half a dozen agent frameworks and you get what engineers call the **N×M connector problem**: N frameworks need to integrate with M data sources, producing N×M bespoke adapters to write, test, and maintain.

The **Model Context Protocol (MCP)** eliminates that problem. Introduced by Anthropic in November 2024 and donated to the Linux Foundation's Agentic AI Foundation in 2026, MCP is an open protocol that standardises how AI applications discover and interact with external tools, data sources, and services. It is, in the words of its designers, "the USB-C of AI integration": a single, well-specified plug that any AI host and any tool server can speak.

By the time you finish this module you will understand why the protocol was designed the way it was, how its four primitives map onto the agentic patterns you already know, and — most importantly — how to build fully functional MCP servers and clients in Python using the official `mcp` SDK.

By the end of this module you will be able to:

- Explain the N×M connector problem that MCP was designed to solve and why ad-hoc function calling does not scale
- Describe the three-tier MCP architecture: host, client, and server, and the role each plays in a session
- Identify and correctly use the four MCP primitives: Tools, Resources, Prompts, and Sampling
- Distinguish between the three transport options (stdio, SSE, and Streamable HTTP) and choose the right one for a given deployment
- Build a complete MCP server in Python using the `FastMCP` interface from the official `mcp` SDK
- Build an MCP client that connects to a server, lists its capabilities, and executes tools within a Claude-powered agent loop
- Integrate MCP servers into the LangGraph-based agentic workflows from Module 6
- Navigate the MCP ecosystem: find, evaluate, and use pre-built servers from the MCP registry
- Reason about MCP security: trust boundaries, OAuth 2.1 authentication, token validation, and prompt injection risks
- Make an informed choice between MCP, direct function calling, LangChain tools, and direct API calls

---

## Required Libraries and Packages

| Package | Version | Purpose | Install |
|---|---|---|---|
| `mcp[cli]` | >= 1.27.0 | Official MCP Python SDK (server, client, CLI inspector) | `pip install "mcp[cli]"` |
| `anthropic` | >= 0.89 | Anthropic Claude SDK for the client examples | `pip install anthropic` |
| `httpx` | >= 0.27 | Async HTTP client used in server examples | `pip install httpx` |
| `python-dotenv` | >= 1.0 | Load `.env` API keys | `pip install python-dotenv` |
| `pydantic` | >= 2.0 | Data validation for structured tool outputs | `pip install pydantic` |

Install everything at once:

```bash
pip install "mcp[cli]" anthropic httpx python-dotenv pydantic
```

Set your API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Or place it in a `.env` file at your project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Section 1 — The Problem MCP Solves

### 1.1 The N×M Connector Explosion

Before MCP, every AI team that wanted to give their agent access to, say, GitHub and a PostgreSQL database faced the same ceremony: read both APIs, write two bespoke integration modules, wire them to the agent framework of the week, and repeat for every new tool and every new project. If the team later switched from LangChain to LangGraph, or from Claude to GPT-4, the integrations needed to be rewritten.

This is the **N×M problem**:

```
N = number of AI applications / agent frameworks
M = number of tools / data sources

Without a standard: N × M adapters to build and maintain
With MCP:          N + M  (each side implements the protocol once)
```

At scale this difference is enormous. The MCP ecosystem had crossed 10,000 community-built servers by early 2025 — tools for filesystems, GitHub, Slack, Postgres, web search, Google Drive, and hundreds more — all reusable across every MCP-compatible host.

### 1.2 What Ad-Hoc Function Calling Gets Wrong

Function calling (tool use) as shipped by OpenAI, Anthropic, and others solves half the problem: it lets a model decide to call a function and generate the correct arguments. But it does not standardise:

- **Discovery**: how the host learns what tools exist at runtime
- **Transport**: how tool requests and responses are transmitted
- **Resources**: how the server exposes structured data (files, database rows, API results) that is not a function call at all
- **Lifecycle**: how capability negotiation, session management, and error handling work across frameworks
- **Reusability**: tool definitions are expressed as provider-specific JSON schemas tied to one SDK

MCP standardises all of this. A tool defined once in an MCP server is immediately available to Claude Desktop, Claude Code, VS Code Copilot, Cursor, any LangGraph agent, and any other MCP-compatible host — with zero changes.

### 1.3 MCP in One Sentence

MCP is a **client-host-server protocol, built on JSON-RPC 2.0, that defines a standard lifecycle for AI applications to discover, connect to, and interact with external capabilities through four primitives: Tools, Resources, Prompts, and Sampling.**

---

## Section 2 — MCP Architecture

### 2.1 The Three Roles

MCP defines three distinct roles in every interaction:

**Host**
The application the user is actually running — Claude Desktop, VS Code with Copilot, a LangGraph agent process, or your own Python application. The host is responsible for:
- Creating and managing one or more `Client` instances
- Enforcing user consent and security policies
- Coordinating the LLM (model calls, context assembly)
- Deciding which servers to connect to and when to disconnect

**Client**
A connector managed by the host. Each client maintains exactly one stateful session with exactly one server. Clients:
- Negotiate capabilities with their server during initialisation
- Route JSON-RPC messages in both directions
- Keep servers isolated from one another (a server cannot see another server's context)

**Server**
A lightweight process that exposes a focused set of capabilities through MCP primitives. Servers can run as:
- A local subprocess (most common for developer tools)
- A remote HTTP service

The relationship is: one host creates many clients, each client talks to one server.

```
Host Application
├── Client 1 ──────────── Server A  (filesystem)
├── Client 2 ──────────── Server B  (GitHub API)
└── Client 3 ──────────── Server C  (PostgreSQL)
```

This architecture deliberately ensures **isolation**: Server A cannot read the conversation history, cannot call Server B's tools, and cannot see Server C's data. Only the host can aggregate information from multiple servers.

### 2.2 Connection Lifecycle

Every MCP session follows three phases:

**1. Initialisation**
The client sends an `initialize` request carrying its protocol version and a list of client capabilities (such as sampling support). The server responds with its own protocol version and server capabilities (tools, resources, prompts). Both sides MUST check that the negotiated version is compatible before proceeding.

**2. Operation**
During the operational phase the session handles:
- *Client-initiated requests*: list tools, call a tool, read a resource, get a prompt
- *Server-initiated requests*: sampling requests (the server asks the client to run an LLM call on its behalf)
- *Notifications*: resource-update events, progress reports, log messages

**3. Shutdown**
Either side can cleanly terminate the session. The client sends a `shutdown` notification, the server acknowledges, and the transport is closed.

### 2.3 Transport Options

MCP specifies three transport mechanisms. The protocol itself (JSON-RPC messages) is identical across all three; only the delivery channel changes.

**stdio (Standard Input/Output)**
The host launches the MCP server as a subprocess. JSON-RPC messages travel over stdin/stdout, newline-delimited. This is the default for local developer tools (Claude Desktop, VS Code, Claude Code).

- Best for: local servers, developer tooling, quick prototyping
- Important: never write to stdout inside a stdio server (it corrupts the message stream); use stderr or a file logger instead

**SSE — Server-Sent Events (Deprecated as of spec 2025-03-26)**
The client connects via HTTP; the server pushes events over a persistent SSE stream. Included here for awareness as many community servers were built with SSE transport before the deprecation. New servers should use Streamable HTTP instead.

**Streamable HTTP (Recommended for remote servers)**
Introduced in spec version 2025-03-26 as the replacement for SSE. Uses standard HTTP POST (client to server) and optional SSE streaming on the response (server to client). Supports stateless deployments, making horizontal scaling behind a load balancer straightforward.

- Best for: remote servers, multi-tenant SaaS, deployed services

### 2.4 The JSON-RPC Layer

All MCP messages are JSON-RPC 2.0 envelopes. You will rarely deal with them directly because the SDK handles serialisation, but it helps to see what is happening underneath:

```json
// Client sends: call the "get_weather" tool
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": { "city": "London" }
  }
}

// Server responds: tool result
{
  "jsonrpc": "2.0",
  "id": 42,
  "result": {
    "content": [
      { "type": "text", "text": "London: 14°C, partly cloudy." }
    ]
  }
}
```

---

## Section 3 — The Four MCP Primitives

MCP defines four primitives. Three are server-provided (Tools, Resources, Prompts); one is client-provided (Sampling).

### 3.1 Tools

Tools are **functions the model can call to take an action or compute a result**. They are the MCP equivalent of OpenAI function calling or Anthropic tool use, but defined once in a server and available to any host.

Key characteristics:
- Tools are discoverable via `tools/list`
- Tools are invoked via `tools/call`
- Each tool has a `name`, a `description`, and an `inputSchema` (JSON Schema)
- Tools may have side effects (write to a file, send an email, call an external API)
- The host SHOULD obtain user consent before invoking any tool

### 3.2 Resources

Resources are **read-only data objects the server exposes for the model to read**. They are analogous to GET endpoints: they deliver context without performing side effects.

Key characteristics:
- Resources have a URI (e.g., `file:///home/user/report.txt`, `db://customers/42`)
- Resources are discoverable via `resources/list`
- Resources are read via `resources/read`
- URI templates (`db://customers/{id}`) create parameterised resource families
- Servers can notify clients of resource updates via `resources/updated` notifications

Resources are the right primitive for: file contents, database rows, API responses that serve as context, configuration blobs, and any data the model should read but not modify.

### 3.3 Prompts

Prompts are **reusable message templates** the server provides to help users accomplish specific tasks. When a host retrieves a prompt, the server returns a list of fully formed messages (user and/or assistant turns) that the host can inject directly into a conversation.

Key characteristics:
- Prompts are discoverable via `prompts/list`
- Prompts are fetched via `prompts/get`
- Each prompt has a `name`, optional `description`, and a list of `arguments`
- The server fills in argument values when the prompt is fetched and returns ready-to-use message objects

Prompts are the right primitive for: slash commands, guided task templates, standardised system instructions, and multi-turn conversation starters that require server-side data to populate.

### 3.4 Sampling

Sampling is the **reverse flow**: instead of the client asking the server to do something, the **server asks the client to run an LLM inference call** on its behalf.

This is what enables servers to implement genuinely agentic behaviour — a server can receive a tool call, decide it needs to analyse some data with an LLM, send a `sampling/createMessage` request to the client, and use the model's response to continue processing.

Key security constraint: the host MUST present sampling requests to the user for approval. The specification explicitly requires human-in-the-loop oversight of server-initiated LLM calls. This keeps the user in control of which prompts reach the model and what the server can see of the response.

Sampling is currently supported by fewer hosts than Tools and Resources, but adoption is growing rapidly as agentic use cases mature.

---

## Section 4 — Building an MCP Server

The official Python SDK (`mcp`) includes a high-level interface called `FastMCP` that uses Python decorators to expose Tools, Resources, and Prompts without writing any JSON-RPC boilerplate.

### 4.1 Installation and Project Setup

```bash
pip install "mcp[cli]" httpx python-dotenv
```

The `[cli]` extra installs the `mcp` command-line tool, which includes the **MCP Inspector** — a browser-based UI for testing your server interactively.

### 4.2 A Minimal Tool Server

The following is a complete, runnable MCP server that exposes a single tool. Save it as `server_basic.py`.

```python
from mcp.server.fastmcp import FastMCP

# Create the server instance with a display name
mcp = FastMCP("demo-server")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers and return the result."""
    return a + b


@mcp.tool()
def greet(name: str, formal: bool = False) -> str:
    """Generate a greeting message.

    Args:
        name: The person's name.
        formal: If True, use a formal greeting style.
    """
    if formal:
        return f"Good day, {name}. How may I assist you?"
    return f"Hey {name}! Great to see you."


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

FastMCP reads the function signature and docstring to automatically generate the JSON Schema for each tool. The `name`, `description`, and `inputSchema` fields that MCP clients see are derived directly from the Python function.

Test this server immediately using the MCP Inspector:

```bash
mcp dev server_basic.py
```

The inspector opens in your browser and lets you call tools, read resources, and browse prompts without writing a client.

### 4.3 Adding Resources

Resources are declared with `@mcp.resource("uri://pattern")`. Curly-brace tokens in the URI pattern become function parameters.

```python
import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("notes-server")

# Simulated in-memory storage (replace with a real database in production)
NOTES: dict[str, str] = {
    "meeting-2026-04-01": "Discussed Q2 roadmap and MCP rollout timeline.",
    "idea-vector-db": "Evaluate pgvector as a replacement for Chroma in prod.",
}


@mcp.resource("notes://list")
def list_notes() -> str:
    """Return a JSON list of all available note IDs."""
    return json.dumps(list(NOTES.keys()))


@mcp.resource("notes://note/{note_id}")
def get_note(note_id: str) -> str:
    """Return the content of a specific note by ID.

    Args:
        note_id: The unique identifier of the note.
    """
    if note_id not in NOTES:
        return f"Note '{note_id}' not found."
    return NOTES[note_id]


@mcp.tool()
def create_note(note_id: str, content: str) -> str:
    """Create or overwrite a note.

    Args:
        note_id: The unique identifier for the note (slug format).
        content: The text content to store in the note.
    """
    NOTES[note_id] = content
    return f"Note '{note_id}' saved successfully."


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Notice the intentional split: `get_note` is a **resource** (read-only, no side effects) while `create_note` is a **tool** (writes data). This mirrors the REST GET/POST distinction and helps the model understand the nature of each operation.

### 4.4 Adding Prompts

Prompts return message objects the host can inject into a conversation.

```python
from mcp.server.fastmcp import FastMCP
from mcp.types import PromptMessage, TextContent

mcp = FastMCP("prompt-server")


@mcp.prompt()
def code_review_prompt(language: str, code_snippet: str) -> list[PromptMessage]:
    """Generate a structured code-review prompt for the given language and snippet.

    Args:
        language: The programming language (e.g., python, typescript).
        code_snippet: The source code to review.
    """
    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=(
                    f"Please review the following {language} code. "
                    "Focus on correctness, readability, performance, and security. "
                    "Suggest specific improvements with code examples.\n\n"
                    f"```{language}\n{code_snippet}\n```"
                ),
            ),
        )
    ]


@mcp.prompt()
def summarise_document_prompt(document_text: str, max_words: int = 150) -> list[PromptMessage]:
    """Generate a prompt that asks the model to summarise a document.

    Args:
        document_text: The full text of the document to summarise.
        max_words: The approximate word limit for the summary.
    """
    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=(
                    f"Summarise the following document in approximately {max_words} words. "
                    "Preserve the key facts, figures, and conclusions.\n\n"
                    f"{document_text}"
                ),
            ),
        )
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 4.5 A Complete Server: Research Assistant

The following example combines all three primitives into a single cohesive server. It exposes tools for saving research notes, resources for reading them back, and a prompt for generating a research summary request. Save it as `research_server.py`.

```python
import json
import sys
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from mcp.types import PromptMessage, TextContent

mcp = FastMCP("research-assistant")

# In-memory store — replace with SQLite or a real DB in production
RESEARCH_NOTES: dict[str, dict] = {}


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def save_research_note(topic: str, content: str, tags: list[str] | None = None) -> str:
    """Save a research note on a topic.

    Args:
        topic: A short identifier for the topic (used as the key).
        content: The body of the research note.
        tags: Optional list of keyword tags for later filtering.
    """
    RESEARCH_NOTES[topic] = {
        "content": content,
        "tags": tags or [],
        "created_at": datetime.utcnow().isoformat(),
    }
    return f"Note saved for topic '{topic}'."


@mcp.tool()
def search_notes_by_tag(tag: str) -> str:
    """Return all note topics that carry a specific tag.

    Args:
        tag: The tag string to filter by.
    """
    matches = [
        topic for topic, data in RESEARCH_NOTES.items() if tag in data["tags"]
    ]
    if not matches:
        return f"No notes found with tag '{tag}'."
    return json.dumps(matches)


@mcp.tool()
def delete_research_note(topic: str) -> str:
    """Delete a research note by topic key.

    Args:
        topic: The topic identifier of the note to delete.
    """
    if topic not in RESEARCH_NOTES:
        return f"No note found for topic '{topic}'."
    del RESEARCH_NOTES[topic]
    return f"Note for topic '{topic}' deleted."


# ── Resources ──────────────────────────────────────────────────────────────────

@mcp.resource("research://topics")
def list_topics() -> str:
    """Return a JSON list of all saved research topic keys."""
    return json.dumps(list(RESEARCH_NOTES.keys()))


@mcp.resource("research://note/{topic}")
def get_note_content(topic: str) -> str:
    """Return the full content of a saved research note.

    Args:
        topic: The topic identifier.
    """
    if topic not in RESEARCH_NOTES:
        return json.dumps({"error": f"Topic '{topic}' not found."})
    return json.dumps(RESEARCH_NOTES[topic])


# ── Prompts ────────────────────────────────────────────────────────────────────

@mcp.prompt()
def synthesise_research_prompt(topics: str) -> list[PromptMessage]:
    """Generate a prompt asking the model to synthesise notes on given topics.

    Args:
        topics: Comma-separated list of topic keys to include in the synthesis.
    """
    topic_list = [t.strip() for t in topics.split(",")]
    notes_text_parts = []
    for topic in topic_list:
        data = RESEARCH_NOTES.get(topic)
        if data:
            notes_text_parts.append(f"### {topic}\n{data['content']}")
        else:
            notes_text_parts.append(f"### {topic}\n(No note found)")

    combined = "\n\n".join(notes_text_parts)
    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=(
                    "You are a research analyst. Based on the notes below, write a "
                    "coherent synthesis that identifies common themes, contradictions, "
                    "and open questions.\n\n"
                    f"{combined}"
                ),
            ),
        )
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Run the inspector against it:

```bash
mcp dev research_server.py
```

### 4.6 Logging in stdio Servers

In a stdio server, stdout is the message channel. Writing anything to stdout from your application code will corrupt the JSON-RPC stream. Use `sys.stderr` or the standard `logging` module (which defaults to stderr):

```python
import logging
import sys

# Safe: goes to stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Inside a tool:
@mcp.tool()
def my_tool(value: str) -> str:
    """A tool that logs safely."""
    logger.info("my_tool called with value=%s", value)  # safe
    # print(value)  # NEVER do this in a stdio server — corrupts the stream
    return f"Processed: {value}"
```

---

## Section 5 — Building an MCP Client

An MCP client connects to a server, negotiates capabilities, and makes requests on behalf of the host (typically an LLM-powered agent loop).

### 5.1 Listing Capabilities

The simplest possible client just connects and prints what the server offers. Save this as `client_inspect.py`.

```python
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def inspect_server(server_script: str) -> None:
    """Connect to an MCP server and print its capabilities."""
    server_params = StdioServerParameters(
        command="python",
        args=[server_script],
        env=None,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # List tools
            tools_response = await session.list_tools()
            print("=== TOOLS ===")
            for tool in tools_response.tools:
                print(f"  {tool.name}: {tool.description}")
                print(f"    Schema: {tool.inputSchema}")

            # List resources
            resources_response = await session.list_resources()
            print("\n=== RESOURCES ===")
            for resource in resources_response.resources:
                print(f"  {resource.uri}: {resource.description}")

            # List prompts
            prompts_response = await session.list_prompts()
            print("\n=== PROMPTS ===")
            for prompt in prompts_response.prompts:
                print(f"  {prompt.name}: {prompt.description}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python client_inspect.py <path_to_server_script>")
        sys.exit(1)
    asyncio.run(inspect_server(sys.argv[1]))
```

Run it against the research server:

```bash
python client_inspect.py research_server.py
```

### 5.2 Calling a Tool Directly

```python
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def call_tool_example(server_script: str) -> None:
    """Demonstrate calling a specific tool on an MCP server."""
    server_params = StdioServerParameters(
        command="python",
        args=[server_script],
        env=None,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Call the save_research_note tool
            result = await session.call_tool(
                "save_research_note",
                {
                    "topic": "mcp-architecture",
                    "content": "MCP uses a host-client-server model built on JSON-RPC 2.0.",
                    "tags": ["mcp", "architecture", "protocol"],
                },
            )
            print("Tool result:", result.content)

            # Read the saved note back as a resource
            read_result = await session.read_resource("research://note/mcp-architecture")
            print("Resource content:", read_result.contents[0].text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python client_call.py <path_to_server_script>")
        sys.exit(1)
    asyncio.run(call_tool_example(sys.argv[1]))
```

### 5.3 A Full Claude-Powered MCP Client

This is the complete pattern for an LLM agent that uses MCP tools. The client fetches the tool list from the MCP server, passes them to Claude as tool definitions, executes any tool calls Claude requests, and loops until Claude produces a final text response. Save as `client_agent.py`.

```python
import asyncio
import os
import sys
from contextlib import AsyncExitStack
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()


class MCPAgent:
    """An LLM-powered agent that uses tools exposed by an MCP server."""

    def __init__(self) -> None:
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect(self, server_script: str) -> None:
        """Launch the MCP server as a subprocess and establish a session."""
        server_params = StdioServerParameters(
            command="python",
            args=[server_script],
            env=None,
        )
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()

        tools_resp = await self.session.list_tools()
        print(f"Connected. Available tools: {[t.name for t in tools_resp.tools]}")

    async def run_query(self, user_query: str) -> str:
        """Run a user query through Claude, executing MCP tool calls as needed."""
        if self.session is None:
            raise RuntimeError("Not connected to an MCP server. Call connect() first.")

        # Fetch tool definitions from the MCP server
        tools_resp = await self.session.list_tools()
        anthropic_tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in tools_resp.tools
        ]

        messages = [{"role": "user", "content": user_query}]
        response_parts: list[str] = []

        while True:
            response = self.anthropic.messages.create(
                model="claude-sonnet-4-6",   # current model as of April 2026
                max_tokens=4096,
                messages=messages,
                tools=anthropic_tools,
            )

            # Collect text content from this response turn
            for block in response.content:
                if block.type == "text":
                    response_parts.append(block.text)

            # If Claude did not request any tool calls, we are done
            if response.stop_reason != "tool_use":
                break

            # Execute all requested tool calls via the MCP session
            assistant_content = response.content
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    tool_result = await self.session.call_tool(
                        block.name, block.input
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result.content,
                        }
                    )
                    response_parts.append(
                        f"[Tool '{block.name}' called with {block.input}]"
                    )

            # Append assistant turn and tool results to the message history
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

        return "\n".join(response_parts)

    async def cleanup(self) -> None:
        """Close all open connections and clean up resources."""
        await self.exit_stack.aclose()


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python client_agent.py <path_to_server_script>")
        sys.exit(1)

    agent = MCPAgent()
    try:
        await agent.connect(sys.argv[1])
        print("MCP Agent ready. Type 'quit' to exit.\n")

        while True:
            query = input("Query: ").strip()
            if query.lower() in {"quit", "exit"}:
                break
            if not query:
                continue
            result = await agent.run_query(query)
            print(f"\n{result}\n")
    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
```

Usage:

```bash
python client_agent.py research_server.py
```

Example interaction:

```
Connected. Available tools: ['save_research_note', 'search_notes_by_tag', 'delete_research_note']
MCP Agent ready. Type 'quit' to exit.

Query: Save a note about transformer attention under the topic "attention-mechanism" with tags ml and transformers.

[Tool 'save_research_note' called with {'topic': 'attention-mechanism', 'content': '...', 'tags': ['ml', 'transformers']}]
Done! I saved a note on the topic "attention-mechanism" covering the key ideas of the transformer self-attention mechanism.
```

---

## Section 6 — MCP in Agentic Workflows

### 6.1 MCP as the Tool Layer for LangGraph

In Module 6, every LangGraph tool was defined inline as a Python function decorated with `@tool`. That works for a single project but does not scale: the tool logic is tied to the agent code, cannot be reused by a different agent, and cannot be updated without redeploying the agent.

MCP solves this by externalising the tool layer. The agent connects to one or more MCP servers at startup, fetches their tool lists, and uses those tools exactly as it would use locally-defined tools. The MCP server can be updated, replaced, or shared across projects without touching the agent code.

The following example wraps an MCP server's tools so they are usable inside a LangGraph `ToolNode`.

```python
import asyncio
from typing import Any
from langchain_core.tools import tool as langchain_tool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def load_mcp_tools_as_langchain(server_script: str) -> list[Any]:
    """
    Connect to an MCP server, fetch its tool list, and return each tool
    wrapped as a LangChain-compatible callable.

    The returned tools can be passed directly to a LangGraph ToolNode.
    """
    server_params = StdioServerParameters(
        command="python",
        args=[server_script],
        env=None,
    )

    mcp_tools: list[Any] = []

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_resp = await session.list_tools()

            for mcp_tool in tools_resp.tools:
                # Capture the tool name and session in the closure
                tool_name = mcp_tool.name
                tool_description = mcp_tool.description or ""

                # We must call the tool through a persistent session,
                # so in a real LangGraph integration you would hold the session
                # open for the lifetime of the graph run. This snippet shows
                # the wrapping pattern; see the note below.
                async def _invoke(inputs: dict, _name: str = tool_name) -> str:
                    # In production, reuse the long-lived session rather than
                    # opening a new connection on every call.
                    async with stdio_client(server_params) as (r2, w2):
                        async with ClientSession(r2, w2) as sess2:
                            await sess2.initialize()
                            result = await sess2.call_tool(_name, inputs)
                            return str(result.content[0].text if result.content else "")

                wrapped = langchain_tool(_invoke, name=tool_name, description=tool_description)
                mcp_tools.append(wrapped)

    return mcp_tools
```

**Important note on session lifecycle**: The pattern above opens a new subprocess per tool call for simplicity. In production you MUST hold a single `ClientSession` open for the duration of a workflow run and share it across all tool invocations. Opening a subprocess per call is prohibitively expensive and loses any server-side state. Use an `AsyncExitStack` scoped to your graph's lifespan context.

### 6.2 Runtime Server Discovery

A key strength of MCP is that hosts can discover server capabilities at runtime rather than having them hardcoded at compile time. This enables patterns like:

- **Dynamic tool selection**: An orchestrating agent fetches tool lists from multiple servers and lets the LLM choose which server to delegate to based on the user's request.
- **Plugin architecture**: Users can install new MCP servers (via the registry or manually) and the host agent picks them up on the next restart without any code changes.
- **Tool search**: Anthropic's Tool Search feature (released March 2026) allows Claude to search thousands of tools at inference time without loading all tool schemas into the context window — a direct consequence of MCP's standardised discovery protocol.

---

## Section 7 — The MCP Ecosystem

### 7.1 Pre-Built Servers

The `modelcontextprotocol/servers` GitHub repository maintains official reference implementations. As of early 2026 these include:

| Server | Capability |
|---|---|
| `filesystem` | Secure file read/write with configurable root directory restrictions |
| `git` | Read, search, and manipulate Git repositories |
| `github` | GitHub Issues, PRs, file content, repo search |
| `postgres` | Read-only Postgres querying with schema introspection |
| `sqlite` | SQLite read/write with schema tools |
| `brave-search` | Web and news search via the Brave Search API |
| `fetch` | Fetch any URL and convert HTML to Markdown |
| `memory` | Graph-based persistent memory across conversations |
| `slack` | Post messages, read channels, manage workspace data |
| `google-drive` | Search and read files from Google Drive |
| `puppeteer` | Browser automation and screenshot capture |
| `everart` | AI image generation |

Community-built servers number in the tens of thousands. The GitHub MCP Registry (launched September 2025, API freeze reached October 2025) provides a searchable catalogue of published servers.

### 7.2 The MCP Registry

The GitHub MCP Registry at `github.com/modelcontextprotocol/registry` is the canonical public index for MCP servers. It provides:

- A searchable web UI and REST API
- One-click install buttons for VS Code and Claude Desktop
- README previews and metadata (author, version, transport type)
- Community ratings and usage statistics

To find a server programmatically you can query the registry API:

```bash
# Search for servers related to databases
curl "https://registry.modelcontextprotocol.io/api/v0/servers?q=database" \
  -H "Accept: application/json"
```

### 7.3 Installing a Pre-Built Server

Claude Desktop uses a JSON configuration file to register MCP servers. On macOS/Linux the file is at `~/Library/Application Support/Claude/claude_desktop_config.json`; on Windows it is at `%APPDATA%\Claude\claude_desktop_config.json`.

To register the official filesystem server:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/yourname/Documents"
      ]
    }
  }
}
```

For a Python server managed by `uv`:

```json
{
  "mcpServers": {
    "research-assistant": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/your/project",
        "run",
        "research_server.py"
      ]
    }
  }
}
```

---

## Section 8 — Security Considerations

### 8.1 The Trust Model

MCP's security model is built on the principle that **the host is the trust anchor**. Every piece of data and every action flows through the host, which is responsible for:

- Obtaining user consent before connecting to any server
- Obtaining user consent before invoking any tool
- Presenting sampling requests for user approval before forwarding to the LLM
- Validating server responses before acting on them

Servers are considered **untrusted by default**. A malicious or compromised server could include adversarial content in tool descriptions (prompt injection), return falsified data, or craft sampling requests designed to exfiltrate conversation content.

### 8.2 Authentication for Remote Servers

The MCP specification (June 2025 update) formalised that MCP servers acting as OAuth 2.0 Resource Servers MUST:

1. Serve a `.well-known/oauth-protected-resource` discovery document
2. Validate access tokens on every request
3. Require the `resource` parameter in token requests to prevent confused-deputy attacks
4. Reject tokens not explicitly issued for the MCP server (token passthrough is explicitly forbidden)

For local stdio servers (developer tooling), authentication is typically handled by the OS process isolation — only the user who launched the server subprocess can communicate with it.

**Short-lived tokens**: Prefer short-lived, scoped OAuth tokens over long-lived API keys. A stolen short-lived token has a limited blast radius; a stolen long-lived key does not expire.

### 8.3 Prompt Injection via Tool Descriptions

A subtle attack vector: a malicious MCP server can put adversarial instructions inside a tool's `description` field. When the host loads the tool list and includes it in the model's context, the attacker's instructions reach the model.

Defences:
- Only connect to servers you trust (vetted registry entries, or servers you control)
- Review tool descriptions before exposing them to the model
- Implement a host-side allow-list of approved servers
- Use sandboxed subprocess environments for third-party servers

### 8.4 Principle of Least Privilege for Servers

Each MCP server should have the minimum permissions required for its stated purpose:

```python
# GOOD: the filesystem server is scoped to a specific directory
mcp = FastMCP("file-reader")

@mcp.resource("file://{filename}")
def read_file(filename: str) -> str:
    """Read a file from the allowed notes directory only."""
    import pathlib
    # Restrict access to a specific safe directory
    safe_dir = pathlib.Path("/home/user/notes").resolve()
    target = (safe_dir / filename).resolve()
    # Prevent path traversal attacks
    if not str(target).startswith(str(safe_dir)):
        return "Access denied: path outside allowed directory."
    if not target.exists():
        return f"File not found: {filename}"
    return target.read_text()
```

### 8.5 Key Security Checklist

| Concern | Mitigation |
|---|---|
| Prompt injection via tool descriptions | Only connect to trusted, vetted servers |
| Token theft (remote servers) | Use short-lived OAuth tokens; validate audience claim |
| Token passthrough attacks | Never forward client tokens to downstream APIs without re-issuing |
| Path traversal in file servers | Resolve and validate paths against an allow-listed root |
| Excessive permissions | Scope each server to the minimum resources it needs |
| Sampling request abuse | Host must present all sampling requests for user approval |
| Server impersonation | Verify server identity; use TLS for all Streamable HTTP connections |

---

## Section 9 — MCP vs. Other Integration Approaches

### 9.1 Comparison Table

| Approach | Standardised | Reusable Across Frameworks | Resources Primitive | Prompts Primitive | Sampling | Transport |
|---|---|---|---|---|---|---|
| **MCP** | Yes (open spec) | Yes | Yes | Yes | Yes | stdio, HTTP |
| **OpenAI Function Calling** | Partial (OpenAI-specific) | No | No | No | No | In-process |
| **Anthropic Tool Use** | Partial (Anthropic-specific) | No | No | No | No | In-process |
| **LangChain Tools** | No (library-specific) | LangChain ecosystem only | No | No | No | In-process |
| **Direct API Calls** | No | No | No | No | No | HTTP |

### 9.2 When to Use Each

**Use MCP when:**
- You want tools to be reusable across multiple agent frameworks or applications
- You are building tools that other developers or teams will consume
- You need the Resources primitive (structured data access, not just function calls)
- You want to leverage the existing ecosystem of pre-built servers
- You are building a production system where the tool layer and agent layer should be independently deployable and versioned

**Use direct Anthropic tool use (or OpenAI function calling) when:**
- You are building a single, self-contained application with no plans to share tools
- The overhead of running a separate server process is not acceptable (e.g., embedded edge deployments)
- You need the absolute minimum latency and the inter-process communication of MCP is a bottleneck

**Use LangChain tools when:**
- You are already deeply inside the LangChain/LangGraph ecosystem
- Your tools are simple Python functions and you do not need cross-framework portability
- You are prototyping and want to iterate quickly without the server/client split

**Use direct API calls when:**
- You are calling a simple external API and do not need LLM-mediated tool selection
- The integration is a one-off pipeline step, not a reusable agent capability

### 9.3 MCP and LangChain Are Not Competitors

A common misconception is that MCP replaces LangChain or LangGraph. It does not. MCP operates at the **tool-exposure layer** (how tools are defined and served), while LangChain/LangGraph operate at the **orchestration layer** (how agents reason, plan, and coordinate). A production system might use LangGraph for workflow orchestration while sourcing all its tools from MCP servers — the two work together.

---

## Section 10 — Common Pitfalls and Best Practices

### Pitfall 1: Writing to stdout in a stdio server

Any `print()` statement, `logging.StreamHandler` to stdout, or third-party library that writes to stdout will corrupt the JSON-RPC message stream and cause silent, hard-to-debug failures.

```python
# BAD
print("Server started")

# GOOD
import sys
print("Server started", file=sys.stderr)

# ALSO GOOD
import logging
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
```

### Pitfall 2: Opening a new subprocess per tool call

The `ClientSession` handshake has non-trivial overhead. Opening a new connection for every tool invocation is slow and, for stdio servers, expensive (it spawns a new process each time).

**Solution**: Keep one `ClientSession` alive for the duration of a workflow run using `AsyncExitStack`, as shown in `client_agent.py`.

### Pitfall 3: Forgetting to call `session.initialize()`

The MCP session lifecycle requires a capability-negotiation handshake before any other request is valid. If you skip `await session.initialize()`, all subsequent calls will fail with protocol errors.

### Pitfall 4: Using SSE transport for new servers

SSE was deprecated in the March 2025 spec update. New remote servers should use Streamable HTTP. SSE-based servers will continue to work with existing clients but will not be compatible with the latest spec-compliant hosts.

### Pitfall 5: Hardcoding server paths in client code

Use environment variables or a configuration file to specify server script paths. This makes it easy to swap servers, move projects, or test against different server versions:

```python
import os
server_path = os.environ.get("MCP_SERVER_PATH", "research_server.py")
await agent.connect(server_path)
```

### Best Practice: Use the MCP Inspector for development

The `mcp dev <server_script>` command starts a browser-based UI that lets you call tools, read resources, and get prompts interactively. Use it as your first testing step before writing a client.

### Best Practice: Validate tool inputs with Pydantic

FastMCP integrates with Pydantic. Annotating parameters with Pydantic types gives you automatic input validation and richer JSON Schema generation:

```python
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("validated-server")


class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="The search query string.")
    max_results: int = Field(default=10, ge=1, le=100, description="Maximum number of results to return.")


@mcp.tool()
def search(params: SearchQuery) -> str:
    """Search the knowledge base with validated input."""
    return f"Searching for '{params.query}' (max {params.max_results} results)..."
```

### Best Practice: Document tools thoroughly

The model reads your tool descriptions to decide which tool to call and how to use it. Vague or missing descriptions lead to incorrect tool selection and malformed arguments.

```python
@mcp.tool()
def create_calendar_event(
    title: str,
    date: str,
    duration_minutes: int = 60,
    attendees: list[str] | None = None,
) -> str:
    """Create a calendar event.

    Args:
        title: The event title. Keep it concise (e.g., 'Team standup', 'Q2 planning').
        date: The event date and start time in ISO 8601 format (e.g., '2026-04-15T14:00:00').
        duration_minutes: Event duration in minutes. Defaults to 60.
        attendees: Optional list of attendee email addresses.

    Returns:
        A confirmation string with the event ID and scheduled time.
    """
    # implementation here
    return f"Event '{title}' created for {date}."
```

---

## Section 11 — Quick Reference

### MCP Session Lifecycle

```
Client                          Server
  │                               │
  │──── initialize ──────────────>│  (client capabilities)
  │<─── initialized ──────────────│  (server capabilities)
  │                               │
  │──── tools/list ─────────────>│
  │<─── [tool definitions] ───────│
  │                               │
  │──── tools/call ─────────────>│
  │<─── tool result ──────────────│
  │                               │
  │──── resources/list ─────────>│
  │<─── [resource list] ──────────│
  │                               │
  │──── resources/read ─────────>│
  │<─── resource content ─────────│
  │                               │
  │  <── sampling/createMessage ──│  (server requests LLM call)
  │─── sampling result ─────────>│
  │                               │
  │──── shutdown ───────────────>│
```

### FastMCP Decorator Summary

| Decorator | Primitive | Use case |
|---|---|---|
| `@mcp.tool()` | Tool | Action with potential side effects; model can invoke it |
| `@mcp.resource("uri://path")` | Resource | Read-only data; loaded into context |
| `@mcp.resource("uri://{param}")` | Resource template | Parameterised read-only data |
| `@mcp.prompt()` | Prompt | Reusable message template; host fetches and injects |

### Transport Decision Guide

| Transport | Use When |
|---|---|
| `stdio` | Local server, developer tools, Claude Desktop, VS Code |
| `streamable-http` | Remote server, multi-tenant service, horizontal scaling needed |
| `sse` | Legacy only — do not use for new servers |

---

## Summary

MCP resolves the N×M connector problem by introducing a single, open, versioned protocol that any AI host and any tool server can implement independently. Its three-tier architecture (host, client, server) enforces clean security boundaries while enabling composability. Its four primitives — Tools for actions, Resources for data, Prompts for templates, and Sampling for server-initiated LLM calls — cover the full range of integration patterns that agentic systems require.

The official Python SDK's `FastMCP` interface makes building a server a matter of decorating Python functions. The client API's `ClientSession` provides clean async primitives for connecting, discovering capabilities, and invoking tools. Together, they make it practical to build the tool layer of an agentic system as a collection of small, focused, independently deployable servers rather than a monolithic pile of framework-specific glue code.

The ecosystem has matured rapidly: 97 million installs by March 2026, adoption by every major AI host, and governance transferred to the Linux Foundation's Agentic AI Foundation. MCP is now the infrastructure layer on which production agentic AI is built.

---

## Further Reading

- [Model Context Protocol Official Documentation](https://modelcontextprotocol.io) — The primary reference: architecture overview, specification, tutorials for building servers and clients, and the concepts guide for all primitives.
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) — The authoritative protocol specification, covering the JSON-RPC message format, capability negotiation, all primitives, and the normative security requirements.
- [MCP Python SDK on GitHub](https://github.com/modelcontextprotocol/python-sdk) — Source code, README, and examples for the official Python SDK; the PyPI package is `mcp`.
- [MCP Pre-built Servers Repository](https://github.com/modelcontextprotocol/servers) — Official reference implementations for filesystem, Git, GitHub, Postgres, SQLite, web search, and more, maintained by the MCP team.
- [GitHub MCP Registry](https://github.com/modelcontextprotocol/registry) — The community-driven, searchable index of published MCP servers; includes REST API and one-click install buttons for VS Code and Claude Desktop.
- [MCP Security Best Practices — Official Spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices) — The normative security guidance from the MCP specification, covering user consent, data privacy, tool safety, and LLM sampling controls.
- [Transports — MCP Specification](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports) — Full specification for stdio, Streamable HTTP, and SSE transports, including the deprecation notice for SSE and the requirements for Streamable HTTP servers.
- [Anthropic — Donating MCP to the Agentic AI Foundation](https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation) — Announcement of the governance transition and the founding of the Agentic AI Foundation under the Linux Foundation.
- [Build an MCP Client — Real Python](https://realpython.com/python-mcp-client/) — A detailed, step-by-step tutorial on building an MCP client from scratch in Python, with coverage of session management and tool invocation patterns.
- [MCP vs. Function Calling — Descope](https://www.descope.com/blog/post/mcp-vs-function-calling) — A practitioner-focused comparison of MCP and native function calling, with clear guidance on when each approach is the right choice.
