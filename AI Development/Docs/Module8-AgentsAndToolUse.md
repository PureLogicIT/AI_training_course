# Module 8: Agents & Tool Use — From Theory to Working Code
> Subject: AI Development | Difficulty: Intermediate-Advanced | Estimated Time: 330 minutes

## Objective

After completing this module, you will be able to translate the ReAct loop you studied in Modules 6 and 7 into running Python code using LangChain. You will define tools using the `@tool` decorator, `StructuredTool`, and Pydantic schemas, and write tool descriptions that reliably guide a local LLM to choose the right tool at the right time. You will build and run agents using both the modern `create_agent()` API (LangChain 1.0+) and the legacy `create_react_agent()` / `create_tool_calling_agent()` + `AgentExecutor` pattern, so you can read existing code and write new production code. You will understand which Ollama models support native function calling, why that matters, and how to handle the cases when a local model produces malformed tool invocations. You will produce structured Pydantic output from agents, add conversation memory, and debug agent failures by inspecting reasoning traces and enabling LangChain's global debug mode. You will build a practical, reusable tool library — a web-search tool, a Python REPL tool, a file-reader tool, a RAG retrieval tool, and a safe calculator — and combine them in three complete, copy-pasteable examples that run entirely on a local Ollama instance.

---

## Prerequisites

- Completed **Module 0: Setup & Local AI Stack** — Ollama is installed and running
- Completed **Module 1: Working with Local Models** — familiar with `ollama.chat()` and inference parameters
- Completed **Module 3: LangChain Fundamentals** — understand `ChatOllama`, LCEL, prompt templates, and `RunnableWithMessageHistory`
- Completed **Module 4: RAG with LangChain** — comfortable with Chroma, embeddings, and retriever interfaces
- Completed **Module 6: Agentic AI Theory** — understand the ReAct loop, tool categories, and agent failure modes
- Completed **Module 7: Agentic Workflows** — understand topology patterns, state management, and error handling
- At least one tool-calling-capable model pulled via Ollama (see Section 4 for the list)
- Python 3.10 or later with an active virtual environment

> Note: Every code block in this module is written to run against a local Ollama instance. No API keys or cloud services are required. The primary examples target **LangChain 1.0+** (`langchain>=1.0.0`). Where the older `AgentExecutor` pattern is shown for educational purposes, it is clearly marked as the legacy approach. All examples were validated against `langchain>=1.0.0`, `langchain-ollama>=0.3.0`, `langgraph>=0.3.0`, and `langchain-community>=0.3.0`.

---

## Installation

Install all packages needed for this module:

```bash
pip install "langchain>=1.0.0" langchain-ollama langchain-community langgraph \
            duckduckgo-search chromadb langchain-chroma langchain-huggingface \
            sentence-transformers pydantic
```

Pull at least one tool-capable model:

```bash
ollama pull llama3.1          # 8B — good starting point, ~4.7 GB
ollama pull qwen2.5           # 7B — excellent tool calling, ~4.4 GB
ollama pull qwen3             # 8B — latest Qwen generation, strong agent performance, ~5.2 GB
```

---

## Key Concepts

### 1. From Theory to Code — Mapping ReAct to Python

In Module 6 you studied the ReAct loop in the abstract:

```
Thought: I need to find X.
Action: search("X")
Observation: X is ...
Thought: Now I know X, I can compute Y.
Action: calculator("X * 2")
Observation: Y = ...
Thought: I have the answer.
Action: finish("The answer is Y.")
```

In LangChain, this loop is not magic — it is a Python `while` loop driven by the LLM's output. Here is a stripped-down illustration of what the agent runtime does under the hood:

```python
# Pseudocode illustrating the agent loop (applies to all agent types)
context = [SystemMessage(system_prompt), HumanMessage(user_input)]

for step in range(max_iterations):
    # THINK: the LLM reads the full context and decides what to do next
    llm_output = llm.invoke(context)

    # Parse the LLM's output into either a tool call or a final answer
    parsed = output_parser.parse(llm_output)

    if isinstance(parsed, AgentFinish):
        # The LLM said it's done — return the final answer
        return parsed.return_values

    if isinstance(parsed, AgentAction):
        # ACT: look up the tool by name and call it
        tool_fn = tool_map[parsed.tool]
        observation = tool_fn(parsed.tool_input)

        # OBSERVE: add the action + observation back to context
        context.append(AIMessage(llm_output))
        context.append(ToolMessage(observation, tool_call_id=...))
        # Loop continues — the LLM now sees its prior reasoning and the result

return "Agent stopped: max_iterations reached"
```

**The three things the agent framework provides for you:**

1. **Prompt construction** — formatting the tool list, the user query, and the growing scratchpad into the prompt the LLM receives each iteration
2. **Output parsing** — interpreting the LLM's text (or structured JSON) as either a tool call or a final answer
3. **Tool dispatch** — looking up the right tool by name and executing it safely

Everything else — the tools themselves, the model, the stopping conditions — you provide.

#### The LangChain Agent API — Legacy vs. Modern

LangChain's agent API has evolved significantly. Understanding both generations is important: the legacy API appears throughout community examples and existing codebases, while the modern API is what you should write for new projects.

| | **Legacy (LangChain < 1.0)** | **Modern (LangChain 1.0+)** |
|---|---|---|
| **Primary API** | `create_react_agent()` + `AgentExecutor` | `create_agent()` |
| **Import** | `from langchain.agents import create_react_agent, AgentExecutor` | `from langchain.agents import create_agent` |
| **Under the hood** | Custom Python loop | LangGraph graph |
| **State** | Implicit in message list | Explicit LangGraph state |
| **Checkpointing** | Not built in | Built in (via LangGraph) |
| **Status** | Deprecated, still importable | Recommended |
| **Module 9 connection** | N/A | `create_agent` is the bridge to full LangGraph |

> **Practical guidance:** If you encounter `AgentExecutor` in tutorials, Stack Overflow answers, or older codebases, it still runs — but expect deprecation warnings with `langchain>=1.0.0`. New code should use `create_agent()`. The legacy patterns are shown in this module to help you read existing code; the hands-on examples use the modern API.

#### Where Agent Types Still Diverge

Regardless of which API generation you use, the same two invocation styles exist:

| | `ReAct-style` (free text) | `Tool-calling-style` (structured JSON) |
|---|---|---|
| **Model requirement** | Any chat/completion model | Chat model with `bind_tools()` support |
| **Tool invocation format** | Free-text (`Action: tool_name\nAction Input: ...`) | Structured JSON (`{"name": "tool", "args": {...}}`) |
| **Reliability with local models** | Works with any instruction-tuned model; parsing can break | Requires model with native tool calling; cleaner when it works |
| **Best for** | Transparency, debugging, models without function calling | Production use with capable models (llama3.1+, qwen2.5+, qwen3) |

---

### 2. Defining Tools in LangChain

A tool in LangChain is an object with three attributes that the agent reads: a **name**, a **description**, and a **callable function**. The description is what the LLM reads to decide when to invoke the tool — it is the most important part you will write.

#### The `@tool` Decorator

The simplest way to create a tool is to decorate a Python function:

```python
from langchain_core.tools import tool

@tool
def get_word_count(text: str) -> int:
    """Count the number of words in a text string.

    Use this when you need to know the length of a piece of text in words,
    for example when checking whether text meets a word limit.

    Args:
        text: The text to count words in.

    Returns:
        The number of words as an integer.
    """
    return len(text.split())
```

LangChain reads the function's type annotations to build the input schema. The docstring becomes the tool's description — exactly what the LLM sees. You can inspect what was generated:

```python
print(get_word_count.name)         # "get_word_count"
print(get_word_count.description)  # (your full docstring)
print(get_word_count.args_schema.schema())  # Pydantic JSON schema
```

You can override the name if you want the agent to see a different one:

```python
@tool("word_counter")
def get_word_count(text: str) -> int:
    """..."""
    return len(text.split())
```

#### Tools with Pydantic Input Schemas

When your tool takes multiple parameters, define an explicit Pydantic schema. This gives the LLM precise field names and types to populate:

```python
from pydantic import BaseModel, Field
from langchain_core.tools import tool

class SearchInput(BaseModel):
    query: str = Field(description="The search query to look up")
    max_results: int = Field(default=5, description="Maximum number of results to return (1-10)")

@tool(args_schema=SearchInput)
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for current information not available in the model's training data.

    Use this tool when the question requires recent events, current prices, live data,
    sports scores, news, or any fact that may have changed since the model's knowledge
    cutoff. Returns a text summary of the top search results.

    Do NOT use this tool for general knowledge questions the model can answer directly.
    """
    # Implementation in Section 6
    pass
```

#### `StructuredTool` — When You Cannot Use a Decorator

Sometimes you want to create a tool from a function you do not control (for example, a method from a library), or you want to create tools dynamically. Use `StructuredTool.from_function()`:

```python
from langchain_core.tools import StructuredTool

def celsius_to_fahrenheit(celsius: float) -> float:
    return (celsius * 9 / 5) + 32

temp_tool = StructuredTool.from_function(
    func=celsius_to_fahrenheit,
    name="celsius_to_fahrenheit",
    description=(
        "Convert a temperature from Celsius to Fahrenheit. "
        "Use this when the user provides a temperature in Celsius "
        "and asks for the Fahrenheit equivalent."
    ),
    return_direct=False,  # True would skip re-sending to the LLM
)
```

#### The `Tool` Class for Simple Single-Input Tools

For quick single-string-input tools, the `Tool` class is the most concise option:

```python
from langchain.tools import Tool
import datetime

current_date_tool = Tool(
    name="current_date",
    func=lambda _: datetime.date.today().isoformat(),
    description=(
        "Returns today's date in ISO format (YYYY-MM-DD). "
        "Use this when the user asks about today's date or needs "
        "to know the current date for a calculation."
    ),
)
```

#### Writing Good Tool Descriptions

The tool description is the only information the LLM has when deciding whether and how to use your tool. A poor description leads to the model picking the wrong tool, ignoring the tool entirely, or calling it with wrong arguments.

**A poor description:**
```
"search: Searches the web."
```

**A good description — answers what it does, when to use it, and what it returns:**
```
"web_search(query: str) -> str: Searches the internet for current information not available in
the model's training data. Use this when the question requires recent events, sports scores,
current prices, live news, or any fact that may have changed since the model's knowledge cutoff.
Returns a text summary of the top search results. Do NOT use for general knowledge or math."
```

Checklist for good tool descriptions:
- **What it does** — one specific sentence
- **When to use it** — the conditions that make this tool appropriate (as specific as possible)
- **When NOT to use it** — helps avoid over-triggering
- **What it returns** — format and content of the output
- **Parameter names and types** — the LLM reads these when constructing the call

#### Handling Tool Errors with `ToolException`

By default, if your tool raises an exception, the agent runtime will crash. The better pattern is to catch errors inside the tool and return a helpful error string — or raise `ToolException`, which the runtime can catch and feed back to the LLM:

```python
from langchain_core.tools import tool, ToolException

@tool
def divide(numerator: float, denominator: float) -> float:
    """Divide numerator by denominator and return the result.

    Use this for division operations. Raises an error if denominator is zero.

    Args:
        numerator: The number to divide.
        denominator: The number to divide by. Must not be zero.

    Returns:
        The result of numerator divided by denominator.
    """
    if denominator == 0:
        raise ToolException("Division by zero is undefined. Please provide a non-zero denominator.")
    return numerator / denominator
```

For the modern `create_agent()` runtime, tool errors are caught by default. For the legacy `AgentExecutor`, set `handle_parsing_errors=True` on the executor and `handle_tool_error=True` on the tool:

```python
# Legacy pattern — AgentExecutor
divide_tool = divide
divide_tool.handle_tool_error = True
```

---

### 3. Building Agents with LangChain

#### The Modern API: `create_agent()` (LangChain 1.0+)

`create_agent()` is the recommended way to build agents as of LangChain 1.0. Under the hood, it builds a LangGraph graph, giving you automatic state management, streaming, and optional checkpointing without requiring you to write graph code yourself.

```python
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city. Returns a simulated weather report.

    Args:
        city: The name of the city to get weather for.
    """
    # Simulated — replace with a real weather API in production
    return f"The weather in {city} is currently 22°C and partly cloudy."

llm = ChatOllama(model="qwen2.5", temperature=0)

agent = create_agent(
    model=llm,
    tools=[get_weather],
    system_prompt="You are a helpful assistant. Use tools to answer questions accurately.",
)

# invoke returns a dict with a "messages" key (LangGraph message format)
result = agent.invoke({
    "messages": [{"role": "user", "content": "What is the weather in Berlin?"}]
})

# The final answer is in the last message
print(result["messages"][-1].content)
```

**Streaming with `create_agent()`:**

```python
for chunk in agent.stream({
    "messages": [{"role": "user", "content": "What is the weather in Tokyo and London?"}]
}):
    # Each chunk is a dict with node name as key
    for node_name, node_output in chunk.items():
        if "messages" in node_output:
            last_msg = node_output["messages"][-1]
            if hasattr(last_msg, "content") and last_msg.content:
                print(f"[{node_name}] {last_msg.content}")
```

**Adding a system prompt for better tool guidance:**

```python
agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=(
        "You are a thorough research assistant. Always use the available tools "
        "to verify facts before answering. Do not guess at current information."
    ),
)
```

#### The Legacy API: `create_react_agent()` + `AgentExecutor`

The `AgentExecutor` + `create_react_agent()` pattern remains importable in LangChain 1.0 but is deprecated. It is shown here so you can read existing tutorials and codebases. **Do not use this pattern in new code.**

`create_react_agent()` builds a ReAct-format agent that works with any instruction-following model. It requires a specific prompt template with `{tools}`, `{tool_names}`, and `{agent_scratchpad}` variables.

```python
# LEGACY PATTERN — shown for educational purposes; use create_agent() for new code
from langchain_core.prompts import PromptTemplate
from langchain.agents import create_react_agent, AgentExecutor  # deprecated in 1.0+
from langchain_ollama import ChatOllama

REACT_TEMPLATE = """You are a helpful assistant with access to the following tools:

{tools}

To use a tool, use the following format EXACTLY:

Thought: I need to think about what to do next.
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action

When you have a final answer, use:
Thought: I now know the final answer.
Final Answer: [your answer here]

Begin!

Question: {input}
Thought: {agent_scratchpad}"""

react_prompt = PromptTemplate.from_template(REACT_TEMPLATE)

llm = ChatOllama(model="qwen2.5", temperature=0)

# Build the agent (a Runnable, not yet an executor)
agent = create_react_agent(llm=llm, tools=tools, prompt=react_prompt)

# Wrap in AgentExecutor — this runs the loop
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,             # prints Thought/Action/Observation to stdout
    max_iterations=10,        # hard cap — prevents infinite loops
    handle_parsing_errors=True,  # sends parse errors back to the LLM to self-correct
)

result = agent_executor.invoke({"input": "What is the capital of France?"})
print(result["output"])
```

#### The Legacy API: `create_tool_calling_agent()` + `AgentExecutor`

`create_tool_calling_agent()` is the structured-JSON equivalent for models with native function calling. Also deprecated in LangChain 1.0+ but still functional:

```python
# LEGACY PATTERN — shown for educational purposes; use create_agent() for new code
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor  # deprecated in 1.0+
from langchain_ollama import ChatOllama

tool_calling_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Use the available tools to answer the user's question."),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),  # required
])

llm = ChatOllama(model="llama3.1", temperature=0)

agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=tool_calling_prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=10,
    handle_parsing_errors=True,
)

result = agent_executor.invoke({"input": "Search the web for the current population of Tokyo."})
print(result["output"])
```

#### Streaming the Legacy Agent Loop

```python
for chunk in agent_executor.stream({"input": "How many words are in the Gettysburg Address?"}):
    if "actions" in chunk:
        for action in chunk["actions"]:
            print(f"Tool call: {action.tool}({action.tool_input})")
    elif "steps" in chunk:
        for step in chunk["steps"]:
            print(f"Observation: {step.observation}")
    elif "output" in chunk:
        print(f"Final: {chunk['output']}")
```

#### Inspecting Intermediate Steps (Legacy `AgentExecutor`)

When `return_intermediate_steps=True` is set on the legacy executor, the returned dict includes the full reasoning trace:

```python
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    return_intermediate_steps=True,
    verbose=True,
    max_iterations=10,
)

result = agent_executor.invoke({"input": "What is 47 * 89?"})

for step in result["intermediate_steps"]:
    action, observation = step
    print(f"Tool called: {action.tool}")
    print(f"Tool input:  {action.tool_input}")
    print(f"Observation: {observation}")
    print("---")

print("Final answer:", result["output"])
```

#### Inspecting Message History (Modern `create_agent()`)

With the modern API, the full reasoning trace is available in the `messages` list:

```python
result = agent.invoke({
    "messages": [{"role": "user", "content": "What is 47 * 89?"}]
})

# Print all messages in the reasoning trace
for msg in result["messages"]:
    msg_type = type(msg).__name__
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        for tc in msg.tool_calls:
            print(f"[{msg_type}] Tool call: {tc['name']}({tc['args']})")
    elif hasattr(msg, "content") and msg.content:
        print(f"[{msg_type}] {msg.content[:200]}")
```

---

### 4. Local Model Considerations for Agents

Not all Ollama models are equally capable as agents. Understanding which models support what, and why it matters, will save you hours of debugging.

#### The Two Invocation Styles

**ReAct-style (free text):** The model produces a human-readable chain like:
```
Thought: I should look this up.
Action: web_search
Action Input: current gold price per ounce
Observation: (filled by the framework)
```
The framework parses this text with a regex/parser. This works with any instruction-tuned model. The failure mode is that the model drifts from the exact format after several iterations, producing output the parser cannot understand.

**Function-calling-style (structured JSON):** The model produces a structured tool call:
```json
{"name": "web_search", "arguments": {"query": "current gold price per ounce"}}
```
This is cleaner and far more reliable when supported. The model has been specifically trained to produce this structured output rather than relying on format adherence through prompting alone. `create_agent()` uses this style exclusively and requires a tool-calling-capable model.

#### Recommended Models for Tool Use (as of April 2026)

The following models are confirmed to support Ollama's native tool-calling API and work reliably with `create_agent()` and `bind_tools()`:

| Model | Pull Command | Size | Notes |
|---|---|---|---|
| **llama3.1** | `ollama pull llama3.1` | 4.7 GB | Reliable, good balance of speed and quality |
| **llama3.2** | `ollama pull llama3.2` | 2.0 GB | Smaller; good for constrained hardware |
| **qwen2.5** | `ollama pull qwen2.5` | 4.4 GB | Strong instruction following, recommended default |
| **qwen2.5-coder** | `ollama pull qwen2.5-coder` | 4.4 GB | Best for code execution tasks |
| **qwen3** | `ollama pull qwen3` | 5.2 GB | Latest Qwen generation; strong agent performance |
| **mistral-nemo** | `ollama pull mistral-nemo` | 7.1 GB | Good general-purpose agent model |
| **phi4** | `ollama pull phi4` | 9.1 GB | Strong reasoning; higher RAM requirement |

> You can browse Ollama's complete list of tool-calling-capable models at `ollama.com/search?c=tools`. The list grows with each Ollama release. Models not in this list may still work with ReAct-style prompting but will not reliably support structured function calling.

#### How to Verify Tool Calling Support

```python
from langchain_ollama import ChatOllama
from langchain_core.tools import tool

@tool
def test_add(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum of a and b.
    """
    return a + b

llm = ChatOllama(model="qwen2.5", temperature=0)

try:
    llm_with_tools = llm.bind_tools([test_add])
    response = llm_with_tools.invoke("What is 3 plus 5?")
    print("Tool calls:", response.tool_calls)
    print("Model supports native tool calling.")
except Exception as e:
    print(f"Model does not support bind_tools: {e}")
    print("Fall back to ReAct-style prompting.")
```

#### Prompt Template Requirements for ReAct with Local Models

When using the legacy `create_react_agent()` with smaller local models, two prompt engineering details significantly improve reliability:

**1. Make the format unambiguous.** The exact strings `Thought:`, `Action:`, `Action Input:`, and `Final Answer:` must appear exactly as the parser expects. Add an explicit reminder at the end of the system prompt:

```
IMPORTANT: Always start your response with "Thought:". Never skip the Thought step.
When using a tool, write ONLY the tool name on the Action line — no explanation.
```

**2. List the exact tool names.** Remind the model which names are valid by including `{tool_names}` in the prompt. A model that invents a tool name (for example, `search_web` instead of `web_search`) will cause a parse error.

#### Handling Malformed Tool Calls

With the modern `create_agent()`, tool call error handling is automatic — errors are passed back as tool messages and the agent can self-correct. With the legacy `AgentExecutor`, use:

```python
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    handle_parsing_errors=(
        "The previous output was not in the correct format. "
        "Remember to use:\nThought: ...\nAction: [tool_name]\nAction Input: [input]"
    ),
    max_iterations=12,
)
```

Passing a custom string to `handle_parsing_errors` gives the model a clearer correction message than the default error text.

---

### 5. Structured Output from Agents

Agents normally return plain text. For production use, you often need a structured response you can validate and process programmatically. There are two approaches.

#### Approach 1: Chain the Agent with a Structured Output Step

Run the agent to gather information using tools, then pass its final text output through a `.with_structured_output()` call on a second LLM invocation. This is the most robust pattern:

```python
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_agent

class SearchSummary(BaseModel):
    answer: str = Field(description="Direct answer to the user's question")
    confidence: str = Field(description="High, Medium, or Low")

llm = ChatOllama(model="qwen2.5", temperature=0)

agent = create_agent(model=llm, tools=tools, system_prompt="Answer questions using tools.")

# Step 1: Run the agent to gather information (tools allowed)
result = agent.invoke({"messages": [{"role": "user", "content": user_question}]})
raw_text = result["messages"][-1].content

# Step 2: Structure the raw answer using a second LLM call
structuring_llm = ChatOllama(model="qwen2.5", temperature=0).with_structured_output(SearchSummary)
structuring_prompt = ChatPromptTemplate.from_messages([
    ("system", "Convert the following research findings into the required structured format."),
    ("human", "Research findings:\n{findings}\n\nOriginal question: {question}"),
])

structuring_chain = structuring_prompt | structuring_llm
structured = structuring_chain.invoke({"findings": raw_text, "question": user_question})

print(f"Answer: {structured.answer}")
print(f"Confidence: {structured.confidence}")
```

#### Approach 2: Parse the Agent's Final Output (Legacy Pattern)

With the legacy `AgentExecutor`, define a Pydantic model and parse the `output` field after the agent finishes. Instruct the model via the system prompt to produce JSON:

```python
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser

class ResearchResult(BaseModel):
    summary: str = Field(description="A 2-3 sentence summary of findings")
    key_facts: list[str] = Field(description="List of 3-5 key facts found")
    confidence: str = Field(description="High, Medium, or Low confidence in the findings")
    sources_used: list[str] = Field(description="Names or descriptions of tools used")

parser = PydanticOutputParser(pydantic_object=ResearchResult)

# Add format instructions to the agent's system prompt
system_prompt = f"""You are a research assistant. After completing your research,
your Final Answer MUST be valid JSON matching this schema:

{parser.get_format_instructions()}
"""

# ... set up agent_executor with this prompt, then:
result = agent_executor.invoke({"input": "Research the population of Tokyo."})
try:
    parsed_result = parser.parse(result["output"])
    print(f"Summary: {parsed_result.summary}")
    print(f"Confidence: {parsed_result.confidence}")
except Exception as e:
    print(f"Parse failed: {e}. Raw output: {result['output']}")
```

---

### 6. Building a Practical Tool Library

The following section implements five reusable tools. Each is complete and ready to import. They are combined in the hands-on examples in Section 9.

#### Tool 1: Web Search (DuckDuckGo — No API Key Required)

```python
# tools/web_search.py
import time
from langchain_core.tools import tool, ToolException

@tool
def web_search(query: str) -> str:
    """Search the web for current information not available in the model's training data.

    Use this when the question requires recent events, live data, sports scores,
    current prices, news headlines, or any fact that may have changed since the
    model's knowledge cutoff date. Returns a text summary of the top results.

    Do NOT use this for general knowledge, math, or questions the model can answer
    directly from its training. One search per distinct factual question.

    Args:
        query: A concise, specific search query. Avoid vague terms.

    Returns:
        A string containing search result snippets, one per line.
    """
    try:
        from duckduckgo_search import DDGS
        time.sleep(0.5)  # gentle rate limiting — DuckDuckGo throttles rapid requests
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=4):
                # Format: title + snippet
                results.append(f"{r['title']}: {r['body']}")
        if not results:
            return "No results found for the query. Try rephrasing."
        return "\n\n".join(results)
    except ImportError:
        raise ToolException("duckduckgo-search is not installed. Run: pip install duckduckgo-search")
    except Exception as e:
        return f"Search failed: {str(e)}. Try a different query."
```

> **Note on rate limiting:** DuckDuckGo's unofficial search API throttles requests if you issue many queries in quick succession. If you see rate limit errors, add more sleep time between calls, reduce `max_results`, or catch `RatelimitException` from `duckduckgo_search.exceptions` and retry with exponential backoff.

#### Tool 2: Python REPL (with Sandboxing Warnings)

```python
# tools/python_repl.py
import sys
import io
from langchain_core.tools import tool, ToolException

@tool
def python_repl(code: str) -> str:
    """Execute Python code and return the output or result.

    Use this for mathematical calculations, data transformations, string formatting,
    sorting, counting, or any task requiring exact computation that the model cannot
    reliably do mentally. The tool runs code in the current Python process.

    Write complete, self-contained code. Use print() to show results.
    Do not import network libraries (requests, urllib) — network access is not
    intended for this tool. Use the web_search tool for web lookups.

    Args:
        code: Complete Python code to execute. Must be syntactically valid.

    Returns:
        Standard output from the code execution, or an error message.
    """
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        # WARNING: exec() runs code in the current process with no sandbox.
        # In production, replace this with a sandboxed execution environment
        # such as a subprocess with resource limits, or a Docker-based executor.
        exec(code, {"__builtins__": __builtins__})
        output = buffer.getvalue()
        return output.strip() if output.strip() else "Code executed successfully (no output)."
    except Exception as e:
        return f"Execution error: {type(e).__name__}: {str(e)}"
    finally:
        sys.stdout = old_stdout
```

> **Security warning:** The `exec()` call above runs with the full permissions of your Python process. This is acceptable for local development with trusted inputs. For any agent that might receive untrusted user input, replace the `exec()` block with a proper sandboxed runner — for example, a subprocess with `resource.setrlimit()` limits, or a containerized executor. Never expose this tool to untrusted input in production.

#### Tool 3: File Reader

```python
# tools/file_reader.py
import os
from pathlib import Path
from langchain_core.tools import tool, ToolException

# Restrict the tool to a safe working directory
ALLOWED_BASE_PATH = Path.cwd() / "agent_workspace"
ALLOWED_BASE_PATH.mkdir(exist_ok=True)

@tool
def read_file(file_path: str) -> str:
    """Read the contents of a text file and return them as a string.

    Use this when you need to examine the contents of a file, such as
    reading a report, source code, configuration file, or any plain-text
    document. The file must be located within the agent's working directory.

    Args:
        file_path: Path to the file, relative to the agent workspace directory.
                   Example: "report.txt" or "data/notes.md"

    Returns:
        The file's text contents, or an error message if the file cannot be read.
    """
    try:
        # Resolve the path relative to the allowed base and check it stays inside
        target = (ALLOWED_BASE_PATH / file_path).resolve()
        if not str(target).startswith(str(ALLOWED_BASE_PATH.resolve())):
            raise ToolException(f"Access denied: '{file_path}' is outside the allowed workspace.")
        if not target.exists():
            return f"File not found: '{file_path}'. Check the filename and try again."
        if not target.is_file():
            return f"'{file_path}' is a directory, not a file."
        content = target.read_text(encoding="utf-8", errors="replace")
        if len(content) > 8000:
            # Return a truncated version with a note — avoids flooding the context window
            return content[:8000] + f"\n\n[Truncated — file has {len(content)} characters total.]"
        return content
    except ToolException:
        raise
    except Exception as e:
        return f"Error reading file: {str(e)}"
```

#### Tool 4: RAG Retrieval Tool (Wrapping a Chroma Vector Store)

This tool wraps the Chroma vector store you built in Module 4. It lets the agent query a knowledge base using semantic search.

```python
# tools/rag_retrieval.py
from langchain_core.tools import tool, ToolException

def build_retrieval_tool(vectorstore):
    """Factory function that creates a retrieval tool bound to a specific Chroma vector store.

    Usage:
        from langchain_chroma import Chroma
        # Load an existing Chroma DB built in Module 4
        vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
        retrieval_tool = build_retrieval_tool(vectorstore)
        tools = [retrieval_tool, ...]
    """
    @tool
    def retrieve_from_knowledge_base(query: str) -> str:
        """Search the local knowledge base for relevant information.

        Use this to look up specific facts, definitions, or passages from the
        documents that have been indexed. This searches ONLY the indexed documents —
        it does NOT search the web. Use web_search for current internet information.

        Best for: answering questions about documents loaded into the system,
        finding definitions, looking up previously stored notes or reports.

        Args:
            query: A natural language question or search phrase.

        Returns:
            Relevant passages from the knowledge base, with source metadata.
        """
        try:
            docs = vectorstore.similarity_search(query, k=3)
            if not docs:
                return "No relevant information found in the knowledge base for this query."
            passages = []
            for i, doc in enumerate(docs, 1):
                source = doc.metadata.get("source", "unknown source")
                passages.append(f"[{i}] Source: {source}\n{doc.page_content}")
            return "\n\n".join(passages)
        except Exception as e:
            raise ToolException(f"Retrieval failed: {str(e)}")

    return retrieve_from_knowledge_base
```

#### Tool 5: Safe Calculator

```python
# tools/calculator.py
import ast
import operator
from langchain_core.tools import tool, ToolException

# Whitelist of safe operations — prevents arbitrary code execution via eval()
SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def _safe_eval(node):
    """Recursively evaluate an AST node using only whitelisted operations."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ToolException(f"Non-numeric constant: {node.value}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPS:
            raise ToolException(f"Unsupported operation: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if op_type == ast.Div and right == 0:
            raise ToolException("Division by zero.")
        return SAFE_OPS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPS:
            raise ToolException(f"Unsupported unary operation: {op_type.__name__}")
        return SAFE_OPS[op_type](_safe_eval(node.operand))
    else:
        raise ToolException(f"Unsupported expression type: {type(node).__name__}")

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the numeric result.

    Use this for arithmetic: addition, subtraction, multiplication, division,
    powers, and modulo. Supports standard operator precedence and parentheses.
    Do NOT use for trigonometry, logarithms, or complex math — use python_repl
    for those.

    Args:
        expression: A mathematical expression string. Examples:
                    "2 + 3 * 4", "(10 - 3) / 2", "2 ** 8", "100 % 7"

    Returns:
        The numeric result as a string, or an error message.
    """
    try:
        # Parse to AST first — never passes the string directly to eval()
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(tree.body)
        # Format: avoid unnecessary decimals for integers
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(round(result, 10))
    except ToolException:
        raise
    except SyntaxError:
        return f"Syntax error in expression: '{expression}'. Check for missing operators or parentheses."
    except Exception as e:
        return f"Calculation error: {str(e)}"
```

---

### 7. Memory and State in LangChain Agents

#### Adding Conversation Memory with `create_agent()` + Checkpointing

The modern `create_agent()` approach uses LangGraph's built-in checkpointing for memory. This is more robust than the legacy `RunnableWithMessageHistory` because it persists the entire agent state (all messages, tool calls, and results), not just the conversation messages.

```python
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

@tool
def web_search(query: str) -> str:
    """Search the web for information. Args: query: The search query."""
    # Simplified for illustration — use the full implementation from Section 6
    return f"Search results for: {query}"

llm = ChatOllama(model="qwen2.5", temperature=0)

# MemorySaver keeps state in memory — use SqliteSaver or PostgresSaver for production
memory = MemorySaver()

agent = create_agent(
    model=llm,
    tools=[web_search],
    system_prompt="You are a helpful assistant with memory of our conversation.",
    checkpointer=memory,
)

# thread_id identifies the conversation session
config = {"configurable": {"thread_id": "user-001"}}

# First turn
result1 = agent.invoke(
    {"messages": [{"role": "user", "content": "Search for the population of Berlin."}]},
    config=config,
)
print(result1["messages"][-1].content)

# Second turn — the agent remembers the first turn
result2 = agent.invoke(
    {"messages": [{"role": "user", "content": "How does that compare to Tokyo?"}]},
    config=config,
)
print(result2["messages"][-1].content)
```

#### Adding Conversation Memory with `RunnableWithMessageHistory` (Legacy)

The legacy pattern for adding memory to an `AgentExecutor`:

```python
# LEGACY PATTERN — works with AgentExecutor; shown for reference
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_ollama import ChatOllama

llm = ChatOllama(model="qwen2.5", temperature=0)

# Prompt must include chat_history placeholder
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant with access to tools."),
    MessagesPlaceholder(variable_name="chat_history"),   # injected by history wrapper
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=10)

message_store: dict[str, InMemoryChatMessageHistory] = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in message_store:
        message_store[session_id] = InMemoryChatMessageHistory()
    return message_store[session_id]

agent_with_history = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

config = {"configurable": {"session_id": "user-001"}}
response1 = agent_with_history.invoke({"input": "Search for the population of Berlin."}, config=config)
print(response1["output"])
```

#### Memory vs. Workflow State

An important distinction from Module 7 applies here:

| Dimension | Agent Memory (checkpointing / `RunnableWithMessageHistory`) | Workflow State (LangGraph) |
|---|---|---|
| **What it stores** | The conversation message history (HumanMessage, AIMessage, ToolMessage) | Arbitrary typed state — any Python object in a dict |
| **Scope** | Across turns of a conversation | Across nodes in a workflow graph |
| **Persistence** | In-memory by default; swap to SQLite/Redis/PostgreSQL for production | Checkpointed by LangGraph's checkpointer backend |
| **When to use** | A conversational agent talking to one user | A complex multi-step workflow with branching and recovery |

If your agent needs to run a long-horizon research task with checkpointing, fault recovery, or human-in-the-loop approval gates, use the full LangGraph API (covered in Module 9). If your agent is having a conversation and needs to remember prior turns, `create_agent()` with a `MemorySaver` is sufficient and simpler.

---

### 8. Debugging and Observability

#### Global Debug Mode

```python
from langchain_core.globals import set_debug

# Enable verbose debug output for ALL LangChain components
set_debug(True)

# Run your agent — you will see every LLM call's full prompt and response
result = agent.invoke({"messages": [{"role": "user", "content": "What is 15 * 23?"}]})

# Disable when done debugging
set_debug(False)
```

`set_debug(True)` is extremely verbose — it prints the full prompt sent to the model on every iteration. Use it when you need to understand exactly what text the LLM is seeing. For a higher-level view, use verbose streaming output or inspect the message list directly.

#### Inspecting the Message Trace (Modern `create_agent()`)

```python
result = agent.invoke({
    "messages": [{"role": "user", "content": "Find and calculate: what is 10% of the population of Paris?"}]
})

print("=== Full Reasoning Trace ===")
for msg in result["messages"]:
    msg_type = type(msg).__name__

    # Tool calls made by the AI
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        for tc in msg.tool_calls:
            print(f"\n[{msg_type}] Tool call: {tc['name']}({tc['args']})")

    # Tool results returned to the AI
    elif hasattr(msg, "name") and msg.name:
        print(f"\n[ToolMessage from {msg.name}]")
        print(f"  Result: {str(msg.content)[:200]}...")

    # Human or AI text messages
    elif hasattr(msg, "content") and msg.content:
        print(f"\n[{msg_type}]")
        print(f"  {str(msg.content)[:300]}")

print("\n=== Final Answer ===")
print(result["messages"][-1].content)
```

#### Inspecting `intermediate_steps` (Legacy `AgentExecutor`)

```python
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    return_intermediate_steps=True,
    max_iterations=10,
)

result = agent_executor.invoke({"input": "Find and calculate: what is 10% of the population of Paris?"})

print("=== Intermediate Steps ===")
for i, (action, observation) in enumerate(result["intermediate_steps"]):
    print(f"\nStep {i + 1}:")
    print(f"  Tool called: {action.tool}")
    print(f"  Tool input:  {action.tool_input}")
    print(f"  Observation: {observation[:200]}...")

print("\n=== Final Answer ===")
print(result["output"])
```

#### Logging Tool Inputs and Outputs

For production-level logging without the verbosity of `set_debug()`, use LangChain's callback system:

```python
from langchain_core.callbacks import BaseCallbackHandler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent.tools")

class ToolLoggingCallback(BaseCallbackHandler):
    """Callback handler that logs all tool invocations and their results."""

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs):
        tool_name = serialized.get("name", "unknown_tool")
        logger.info(f"TOOL START | {tool_name} | input: {input_str[:200]}")

    def on_tool_end(self, output: str, **kwargs):
        logger.info(f"TOOL END   | output: {output[:200]}")

    def on_tool_error(self, error: Exception, **kwargs):
        logger.error(f"TOOL ERROR | {type(error).__name__}: {str(error)}")

# Pass the callback to the modern agent at invocation time
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Search for AI news"}]},
    config={"callbacks": [ToolLoggingCallback()]},
)

# For legacy AgentExecutor, pass at construction time:
# agent_executor = AgentExecutor(agent=agent, tools=tools, callbacks=[ToolLoggingCallback()])
```

#### Common Failure Patterns and Diagnosis

| Symptom | Likely Cause | Diagnosis Steps | Fix |
|---|---|---|---|
| Agent never uses any tools — goes straight to a final answer | Tool descriptions too vague; model decides it already knows the answer | Check tool descriptions; read the model's reasoning in the message trace | Rewrite descriptions: be specific about when to use each tool; add "always verify with tools" to the system prompt |
| Same tool called in an identical loop | Model receives the same observation and re-plans the same action | Inspect the message trace — is the observation useful? | Improve tool error output; check that the tool returns different results on retry |
| Agent exits with no answer after exhausting steps | Task too complex for the model; context filling up | Count how many steps were taken; inspect observations | Break task into smaller subtasks; truncate tool output before it enters the context |
| Tool input is malformed JSON | Model generated invalid JSON for function-calling tool | Enable `set_debug(True)` to see raw tool call | Switch to a model with stronger tool calling (qwen2.5, qwen3, llama3.1); simplify tool schemas |
| Context window overflow mid-task | Tool observations are too large, filling the context | Count tokens in the message list after several steps | Truncate tool outputs in the tool function itself; use a model with a larger context window |
| `OutputParserException` (legacy only) | Model drifted from the ReAct format | Enable `set_debug(True)` and check the raw LLM output | Add `handle_parsing_errors=True`; strengthen format instructions in the prompt; switch to `create_agent()` |

---

### 9. Hands-On Examples

Each example is complete and runnable. Copy the file, ensure Ollama is running with the required model, and execute it.

---

#### Example 1: Agent with Web Search and Calculator

This example builds an agent using the modern `create_agent()` API that can search the web and perform arithmetic — the classic combination for answering factual questions that require both information gathering and computation.

```python
# example1_search_calc_agent.py
"""
Agent with DuckDuckGo web search and safe calculator using the modern create_agent() API.
Demonstrates: create_agent, tool definitions, streaming, message trace inspection.

Requirements:
    pip install "langchain>=1.0.0" langchain-ollama duckduckgo-search
    ollama pull qwen2.5
"""

import sys
import ast
import operator
import time
from langchain_core.tools import tool, ToolException
from langchain.agents import create_agent
from langchain_ollama import ChatOllama


# ── Tool 1: Web Search ────────────────────────────────────────────────────────

@tool
def web_search(query: str) -> str:
    """Search the web for current information not available in training data.

    Use for: recent events, live data, current prices, news, sports scores.
    Do NOT use for: general knowledge, math, or questions the model knows.

    Args:
        query: A concise and specific search query string.

    Returns:
        Text snippets from the top search results.
    """
    try:
        from duckduckgo_search import DDGS
        time.sleep(0.5)  # gentle rate limiting
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                results.append(f"- {r['title']}: {r['body']}")
        return "\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search error: {str(e)}"


# ── Tool 2: Safe Calculator ───────────────────────────────────────────────────

SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg,
}

def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPS:
        left, right = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ToolException("Division by zero.")
        return SAFE_OPS[type(node.op)](left, right)
    elif isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPS:
        return SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    raise ToolException(f"Unsupported expression: {ast.dump(node)}")

@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression: +, -, *, /, **, %. Supports parentheses.

    Use for arithmetic and numeric calculations only.
    Do NOT use for trigonometry or logarithms — use python_repl for those.

    Args:
        expression: A mathematical expression, e.g. "(15 + 3) * 2 / 4"

    Returns:
        The numeric result as a string.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(tree.body)
        return str(int(result)) if isinstance(result, float) and result.is_integer() else str(round(result, 8))
    except ToolException:
        raise
    except SyntaxError:
        return f"Syntax error in: '{expression}'"
    except Exception as e:
        return f"Calculation error: {str(e)}"


# ── Agent Setup ───────────────────────────────────────────────────────────────

tools = [web_search, calculator]
llm = ChatOllama(model="qwen2.5", temperature=0)

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=(
        "You are a helpful research assistant. Always use the web_search tool "
        "to verify facts about current events or statistics before answering. "
        "Use the calculator tool for all numeric computations."
    ),
)


# ── Run the Agent ─────────────────────────────────────────────────────────────

def run_query(question: str):
    print(f"\n{'='*60}")
    print(f"Question: {question}")
    print('='*60)

    result = agent.invoke({
        "messages": [{"role": "user", "content": question}]
    })

    # Print the reasoning trace
    tool_calls_made = []
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_made.append(f"{tc['name']}({tc['args']})")

    print(f"Tools invoked: {tool_calls_made if tool_calls_made else 'none'}")
    print(f"Final Answer: {result['messages'][-1].content}")
    return result


if __name__ == "__main__":
    # Question 1: Web lookup only
    run_query("What is the approximate current population of Tokyo?")

    # Question 2: Web lookup + arithmetic
    run_query(
        "Search for the approximate populations of London and Berlin. "
        "Then calculate their combined population and how many times larger "
        "London is than Berlin."
    )
```

---

#### Example 2: File Analysis Agent with RAG Retrieval

This agent can read files from a workspace directory, load them into a Chroma vector store, and answer questions about their contents using semantic retrieval.

```python
# example2_file_analysis_agent.py
"""
File analysis agent: reads files, indexes them in Chroma, and answers questions
using a RAG retrieval tool. Demonstrates: build_retrieval_tool, read_file tool,
create_agent, with_structured_output.

Requirements:
    pip install "langchain>=1.0.0" langchain-ollama langchain-community langchain-chroma \
                langchain-huggingface sentence-transformers chromadb
    ollama pull llama3.1
"""

from pathlib import Path
from langchain_core.tools import tool, ToolException
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field


# ── Workspace Setup ───────────────────────────────────────────────────────────

WORKSPACE = Path("./agent_workspace")
WORKSPACE.mkdir(exist_ok=True)

# Create sample files for demonstration
(WORKSPACE / "report_q1.txt").write_text("""
Q1 2026 Sales Report
====================
Total revenue: $4.2 million
Units sold: 12,400
Top product: Model X Pro (3,100 units, $1.8M revenue)
Worst performer: Model Z Basic (210 units, $63K revenue)
New customers acquired: 847
Customer retention rate: 91%
Notable: Model X Pro exceeded forecast by 23%.
""")

(WORKSPACE / "meeting_notes.txt").write_text("""
Engineering Team Meeting - March 15 2026
=========================================
Attendees: Alice (lead), Bob (backend), Carol (ML), Dave (infra)
Key decisions:
- Deploy new inference cluster by April 30
- Migrate database to PostgreSQL 17 by May 15
- Carol to lead evaluation of Qwen3 for production use
- Bob to implement rate limiting on API v2 by end of month
Action items:
- Alice: draft RFC for new auth system by March 22
- Bob: PR for rate limiting by March 29
- Carol: Qwen3 benchmark results by April 5
- Dave: infra migration plan by March 25
""")

print(f"Sample files created in {WORKSPACE.resolve()}")


# ── Build Vector Store ────────────────────────────────────────────────────────

def build_vectorstore_from_workspace(workspace_path: Path) -> Chroma:
    """Load all .txt and .md files from workspace, split, and index in Chroma."""
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
    )
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = []
    for f in list(workspace_path.glob("*.txt")) + list(workspace_path.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        chunks = splitter.split_text(content)
        for chunk in chunks:
            docs.append(Document(page_content=chunk, metadata={"source": f.name}))

    vectorstore = Chroma.from_documents(docs, embedding=embedding_model)
    print(f"Indexed {len(docs)} chunks from {workspace_path}")
    return vectorstore


vectorstore = build_vectorstore_from_workspace(WORKSPACE)


# ── Tool 1: File Reader ───────────────────────────────────────────────────────

@tool
def read_file(file_path: str) -> str:
    """Read the full contents of a text file from the agent workspace.

    Use this to examine a complete file when you need full context beyond what
    the knowledge base retrieves. Prefer retrieve_from_knowledge_base for
    specific factual questions; use read_file for full-document review.

    Args:
        file_path: Filename relative to the workspace (e.g., "report_q1.txt")

    Returns:
        Full file contents as a string.
    """
    target = (WORKSPACE / file_path).resolve()
    if not str(target).startswith(str(WORKSPACE.resolve())):
        raise ToolException("Access denied: path is outside the workspace.")
    if not target.exists():
        available = [f.name for f in WORKSPACE.iterdir() if f.is_file()]
        return f"File not found: '{file_path}'. Available files: {available}"
    content = target.read_text(encoding="utf-8", errors="replace")
    return content[:6000] if len(content) <= 6000 else content[:6000] + "\n[Truncated]"


# ── Tool 2: RAG Retrieval ─────────────────────────────────────────────────────

@tool
def retrieve_from_knowledge_base(query: str) -> str:
    """Search the indexed knowledge base for relevant passages.

    Use this for specific questions about indexed documents. Returns
    the most relevant passages with their source file names.
    Prefer this over read_file for targeted factual lookups.

    Args:
        query: A natural language question or search phrase.

    Returns:
        Relevant passages with source attribution.
    """
    docs = vectorstore.similarity_search(query, k=3)
    if not docs:
        return "No relevant passages found."
    passages = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        passages.append(f"[{i}] From '{source}':\n{doc.page_content}")
    return "\n\n".join(passages)


# ── Tool 3: List Files ────────────────────────────────────────────────────────

@tool
def list_workspace_files() -> str:
    """List all files available in the agent workspace directory.

    Use this first if you are not sure which files exist before trying to
    read a specific file. Returns filenames and sizes.

    Returns:
        A list of filenames with file sizes.
    """
    files = [f for f in WORKSPACE.iterdir() if f.is_file()]
    if not files:
        return "The workspace is empty."
    lines = [f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)" for f in files]
    return "Files in workspace:\n" + "\n".join(lines)


# ── Agent Setup ───────────────────────────────────────────────────────────────

tools = [list_workspace_files, read_file, retrieve_from_knowledge_base]

llm = ChatOllama(model="llama3.1", temperature=0)

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=(
        "You are a helpful document analysis assistant. You have access to files "
        "in a workspace directory. Use the available tools to read files and "
        "answer questions about their contents. Always cite the source file when "
        "referencing specific information."
    ),
)


# ── Structured Output Model ───────────────────────────────────────────────────

class DocumentAnalysis(BaseModel):
    answer: str = Field(description="Direct answer to the question")
    source_files: list[str] = Field(description="Files consulted to answer")
    confidence: str = Field(description="High, Medium, or Low confidence")

structuring_llm = ChatOllama(model="llama3.1", temperature=0).with_structured_output(DocumentAnalysis)
structuring_prompt = ChatPromptTemplate.from_messages([
    ("system", "Convert the following research findings into structured format."),
    ("human", "Question: {question}\nFindings: {findings}"),
])
structuring_chain = structuring_prompt | structuring_llm


# ── Run the Agent ─────────────────────────────────────────────────────────────

def ask_agent(question: str) -> DocumentAnalysis:
    print(f"\n{'='*60}\nQuestion: {question}\n{'='*60}")
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    raw_answer = result["messages"][-1].content

    structured = structuring_chain.invoke({
        "question": question,
        "findings": raw_answer,
    })
    print(f"\nStructured answer: {structured.answer}")
    print(f"Sources: {structured.source_files}")
    print(f"Confidence: {structured.confidence}")
    return structured


if __name__ == "__main__":
    ask_agent("What were the total revenue and top product in Q1 2026?")
    ask_agent("Who is responsible for the Qwen3 benchmark evaluation and when is it due?")
    ask_agent("Summarize all the action items from the meeting notes.")
```

---

#### Example 3: Multi-Tool Research Agent with Structured Report Output

This agent combines web search, a Python REPL, file writing, and a safe calculator to produce a structured research report saved to disk. It uses conversation memory via `MemorySaver` so a follow-up question can reference prior research.

```python
# example3_research_agent.py
"""
Multi-tool research agent that searches the web, performs calculations,
and writes a structured report to disk. Uses MemorySaver for conversation memory.

Demonstrates: multiple tools, create_agent with checkpointer, structured final output,
write-to-disk pattern, tool error handling, memory across turns.

Requirements:
    pip install "langchain>=1.0.0" langchain-ollama duckduckgo-search langgraph
    ollama pull qwen2.5
"""

import sys
import io
import ast
import operator
import time
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field
from langchain_core.tools import tool, ToolException
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver


# ── Output Directory ──────────────────────────────────────────────────────────

OUTPUT_DIR = Path("./research_output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Tool 1: Web Search ────────────────────────────────────────────────────────

@tool
def web_search(query: str) -> str:
    """Search the web for current information not in the model's training data.

    Use for: recent events, live statistics, current news, market data.
    Returns top search result snippets.

    Args:
        query: A specific, concise search query.
    """
    try:
        from duckduckgo_search import DDGS
        time.sleep(0.5)
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if not results:
            return "No results found."
        return "\n".join(f"- {r['title']}: {r['body']}" for r in results)
    except Exception as e:
        return f"Search failed: {str(e)}"


# ── Tool 2: Python REPL ───────────────────────────────────────────────────────

@tool
def python_repl(code: str) -> str:
    """Execute Python code and return printed output.

    Use for: calculations, data formatting, statistics, string operations.
    Write complete code using print() to show results.
    Do NOT use for network requests — use web_search instead.

    Args:
        code: Complete, runnable Python code.
    """
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        exec(code, {"__builtins__": __builtins__})
        output = buf.getvalue().strip()
        return output if output else "Executed (no output)."
    except Exception as e:
        return f"{type(e).__name__}: {str(e)}"
    finally:
        sys.stdout = old_stdout


# ── Tool 3: Safe Calculator ───────────────────────────────────────────────────

SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg,
}

def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPS:
        l, r = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Div) and r == 0:
            raise ToolException("Division by zero.")
        return SAFE_OPS[type(node.op)](l, r)
    elif isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPS:
        return SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    raise ToolException(f"Unsupported node: {type(node).__name__}")

@tool
def calculator(expression: str) -> str:
    """Evaluate arithmetic: +, -, *, /, **, %. Supports parentheses.

    Args:
        expression: A math expression string, e.g. "(3.14 * 6.2 ** 2)"
    """
    try:
        result = _safe_eval(ast.parse(expression.strip(), mode="eval").body)
        return str(int(result)) if isinstance(result, float) and result.is_integer() else str(round(result, 8))
    except ToolException:
        raise
    except Exception as e:
        return f"Error: {str(e)}"


# ── Tool 4: Save Report to Disk ───────────────────────────────────────────────

@tool
def save_report(filename: str, content: str) -> str:
    """Save a text report to the research output directory.

    Use this as the FINAL step after gathering and analyzing all information.
    The report should be a complete, well-formatted markdown document.

    Args:
        filename: The output filename (e.g., "tokyo_report.md"). Will be saved
                  in the research_output/ directory. ".md" extension recommended.
        content: The full report content in markdown format.

    Returns:
        Confirmation message with the full path where the file was saved.
    """
    # Sanitize filename — prevent directory traversal
    safe_name = Path(filename).name
    if not safe_name:
        raise ToolException("Invalid filename.")
    output_path = OUTPUT_DIR / safe_name
    output_path.write_text(content, encoding="utf-8")
    return f"Report saved successfully: {output_path.resolve()}"


# ── Agent Setup ───────────────────────────────────────────────────────────────

tools = [web_search, calculator, python_repl, save_report]

llm = ChatOllama(model="qwen2.5", temperature=0)

SYSTEM_PROMPT = """You are a thorough research assistant. Your goal is to research
a topic completely and produce a well-structured report saved to disk.

Research process:
1. Use web_search to find current information on the topic.
2. Use calculator or python_repl to perform any needed calculations.
3. Synthesize all findings into a comprehensive markdown report.
4. Use save_report to save the final report to disk.

Your report must include:
- A clear title and today's date
- An executive summary (2-3 sentences)
- Key findings as bullet points
- Any relevant numbers or statistics
- A "Sources" section listing what was searched

Always complete the full research process and save the report before giving your final answer."""

# MemorySaver keeps conversation state in memory across invocations with the same thread_id
memory = MemorySaver()

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=memory,
)


# ── Structured Result Model ───────────────────────────────────────────────────

class ResearchReport(BaseModel):
    topic: str = Field(description="The research topic")
    report_file: str = Field(description="Path to the saved report file")
    summary: str = Field(description="2-3 sentence summary of findings")
    tools_used: list[str] = Field(description="Names of tools invoked during research")
    steps_taken: int = Field(description="Number of tool calls made")


# ── Run Research ──────────────────────────────────────────────────────────────

def run_research(topic: str, thread_id: str = "research-001") -> ResearchReport:
    config = {"configurable": {"thread_id": thread_id}}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = topic[:40].replace(" ", "_").replace("/", "-")
    filename = f"{safe_topic}_{timestamp}.md"

    task = (
        f"Research the following topic and save a complete report to '{filename}':\n\n"
        f"Topic: {topic}\n\n"
        f"After saving the report, confirm the file path in your final answer."
    )

    print(f"\n{'='*60}")
    print(f"Research task: {topic}")
    print(f"Output file: {OUTPUT_DIR / filename}")
    print('='*60)

    result = agent.invoke(
        {"messages": [{"role": "user", "content": task}]},
        config=config,
    )

    # Count tool calls and collect tool names from the message trace
    tools_used = set()
    steps = 0
    report_path = str(OUTPUT_DIR / filename)

    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tools_used.add(tc["name"])
                steps += 1
        # Extract the actual saved path from the save_report tool message
        if hasattr(msg, "name") and msg.name == "save_report":
            content_str = str(msg.content)
            if "saved successfully:" in content_str:
                report_path = content_str.split("saved successfully:", 1)[-1].strip()

    report = ResearchReport(
        topic=topic,
        report_file=report_path,
        summary=result["messages"][-1].content[:300],
        tools_used=list(tools_used),
        steps_taken=steps,
    )

    print(f"\nResearch complete.")
    print(f"Report saved to: {report.report_file}")
    print(f"Tools used: {report.tools_used}")
    print(f"Steps taken: {report.steps_taken}")
    return report


if __name__ == "__main__":
    # Research task 1: current statistics topic
    report1 = run_research("The current state of open-source large language models in 2026")

    # Research task 2: follow-up in the same session (demonstrates memory via MemorySaver)
    report2 = run_research(
        "Compare the top 3 models from the previous research by parameter count",
        thread_id="research-001",  # same thread_id — agent remembers prior research
    )

    print(f"\nAll reports saved to: {OUTPUT_DIR.resolve()}")
```

---

## Common Pitfalls

**Pitfall 1: Using `langchain.agents.AgentExecutor` in new code with `langchain>=1.0.0`**

You will see deprecation warnings when importing `AgentExecutor` or `create_react_agent` from `langchain.agents` in LangChain 1.0+. Existing tutorials using these APIs are abundant online, but new code should use `create_agent()` instead.

- **Fix:** Replace `AgentExecutor` + `create_tool_calling_agent()` with `create_agent()`. The tool definitions (`@tool` decorator, `StructuredTool`, etc.) are identical — only the executor setup changes.

**Pitfall 2: Model does not use tools — goes straight to a final answer**

The model produces an answer immediately without ever invoking a tool, or it uses a natural-language description of an action instead of structured tool calling.

- **Root cause:** The model's instruction-following capability is insufficient, or the tool descriptions do not clearly communicate when to use the tool.
- **Fix:** Use a model with stronger instruction following (qwen2.5, qwen3, llama3.1). Strengthen the system prompt — include an explicit instruction like "always use tools to verify current facts before answering." Rewrite tool descriptions to include specific "Use this when..." clauses.

**Pitfall 3: Tool descriptions too vague**

The model uses the wrong tool or calls tools unnecessarily (for example, calling `web_search` for a question it could answer directly from training data).

- **Root cause:** The description does not specify when the tool is appropriate or when it should NOT be used.
- **Fix:** Add explicit "Use this when..." and "Do NOT use for..." clauses. Be specific about what inputs the tool expects. Inspect the tool calls in the message trace to understand the model's reasoning.

**Pitfall 4: Context window overflow with tool history**

After several tool calls, the model's quality degrades or it ignores earlier information. This is the "lost in the middle" failure from Module 6.

- **Fix:** Truncate tool outputs before they are returned — limit to 500–1000 characters in the tool function itself. Summarize long tool outputs using a separate LLM call before feeding them back. Use a model with a larger context window (llama3.1, qwen2.5, and most current models via Ollama support 32K–128K context).

**Pitfall 5: JSON parse errors in function-calling tool inputs**

With native function calling, the model produces a tool call with invalid JSON arguments (missing quotes, wrong field names, wrong types).

- **Root cause:** The model's function-calling training is imperfect for this argument structure, or the schema is ambiguous.
- **Fix:** Simplify tool schemas — reduce the number of parameters. Use `Field(description=...)` to make parameter expectations crystal clear. Switch to qwen2.5 or qwen3 for the most reliable function call JSON output among local models.

**Pitfall 6: DuckDuckGo rate limiting**

The `duckduckgo-search` library raises `RatelimitException` when called too frequently.

- **Fix:** Add `time.sleep(0.5)` between calls (already included in the examples). Catch the exception explicitly and retry with exponential backoff. For high-volume production use, switch to a search API with a proper rate limit tier (Brave Search API, Serper, etc.).

---

## Best Practices

1. **Use `create_agent()` for new code.** The modern API is backed by LangGraph, gives you automatic state management, streaming, and optional checkpointing. Only use the legacy `AgentExecutor` patterns when maintaining existing code.

2. **Limit your tool set.** Every tool added to the agent is another option the model must reason about. Fewer than ten tools is a good target for local models. If you have many tools, group them into specialized agents rather than one mega-agent.

3. **Write the tool description before the tool implementation.** The description is what the agent uses to decide when to call the tool. Write it first, as if explaining the tool to a human reader who needs to decide whether to use it. If you cannot write a clear description, the tool's purpose may be unclear.

4. **Set `temperature=0` on the model.** Agents need deterministic, structured output. Non-zero temperature increases the probability of format errors and inconsistent tool invocation patterns.

5. **Return useful error strings from tools.** When a tool fails, the string it returns is all the agent has to understand what went wrong. Vague error messages ("Error occurred") lead to unhelpful retries. Specific error messages ("File 'report.txt' not found. Available files: ['notes.md', 'data.csv']") let the agent self-correct.

6. **Truncate large tool outputs.** A web search result, a file read, or a database query can return thousands of tokens. Feed back only the relevant portion — typically 500–1000 characters. Accumulating long observations across multiple steps is the primary cause of context window overflow in long-running agents.

7. **Test tools in isolation before wiring them into agents.** Call your tool functions directly, without an agent, to verify they work correctly and return useful strings. A tool that works in isolation is much easier to debug than a tool that only fails when the agent calls it with unexpected input.

8. **Validate the final output.** Use Pydantic or the two-step structuring approach in Section 5 to validate the agent's final answer. An agent that runs to completion but produces unstructured or incorrect output is just as problematic as one that crashes.

9. **Log tool invocations.** Use `ToolLoggingCallback` (Section 8) in development. In production, structured logs of every tool call are your primary diagnostic tool when something goes wrong.

10. **Plan for model upgrades.** Local model tool calling quality improves significantly with each model generation. If qwen2.5 is unreliable for your use case today, qwen3 or the next Llama release may be substantially better. Write your tool definitions to the standard API so switching the model is a one-line change.

---

## Key Terminology

**`@tool` decorator** — A LangChain decorator that converts a Python function into a `StructuredTool` instance by reading the function's type annotations for the input schema and its docstring for the description.

**`AgentExecutor`** — The legacy LangChain class (deprecated in LangChain 1.0+) that implemented the agent loop: calling the agent (the LLM + output parser), dispatching the chosen tool, feeding the observation back, and repeating until `AgentFinish` or `max_iterations`.

**`agent_scratchpad`** — The placeholder in a legacy ReAct or tool-calling prompt that the framework populates with the growing history of prior Thought/Action/Observation steps within the current invocation. Not used in the modern `create_agent()` API.

**`create_agent()`** — The recommended LangChain 1.0+ function for building agents. Under the hood, builds a LangGraph graph. Accepts a model, tools, and an optional system prompt; returns a compiled LangGraph that can be invoked or streamed like any Runnable.

**`create_react_agent()`** — Legacy LangChain function (deprecated in 1.0+) that creates a ReAct-style agent expecting the LLM to produce human-readable `Thought`/`Action`/`Action Input` text. Works with any instruction-following model.

**`create_tool_calling_agent()`** — Legacy LangChain function (deprecated in 1.0+) that creates a structured function-calling agent expecting the LLM to produce JSON tool invocations. Requires a model with native function calling support.

**`handle_parsing_errors`** — A legacy `AgentExecutor` parameter that, when `True` (or a custom error string), feeds parsing failures back to the LLM as observations instead of crashing.

**`intermediate_steps`** — In the legacy `AgentExecutor`, the list of `(AgentAction, observation_string)` tuples from a completed agent run. In the modern API, the equivalent information is available in the `messages` list of the returned state.

**`MemorySaver`** — A LangGraph checkpointer that stores agent state in memory. Used with `create_agent(checkpointer=memory)` to enable conversation memory across invocations with the same `thread_id`. Not persisted across process restarts.

**`StructuredTool`** — A LangChain tool class that accepts multi-parameter inputs validated against a Pydantic schema. Created via `StructuredTool.from_function()` or the `@tool` decorator with an explicit `args_schema`.

**`ToolException`** — A LangChain exception class that tools can raise to signal a recoverable error. The exception message is fed back to the LLM as an observation, allowing the agent to self-correct.

**`with_structured_output()`** — A method on `ChatOllama` (and other chat models) that constrains the model's output to a Pydantic schema, returning a validated model instance instead of raw text.

---

## Summary

This module moved the ReAct theory from Modules 6 and 7 into working Python code. The key landmarks:

- The agent runtime is a `while` loop: call the LLM, parse its output as a tool call or final answer, execute the tool, feed the observation back, repeat.
- **Tool definitions** have three parts that matter: name, description (what the LLM reads), and the callable function. Tool descriptions are the most impactful thing you write — they determine whether the LLM calls the right tool at the right time.
- **`create_agent()`** (LangChain 1.0+) is the recommended modern API. It builds on LangGraph, giving automatic state management and optional checkpointing. The legacy `AgentExecutor` + `create_react_agent()` / `create_tool_calling_agent()` pattern is still importable but deprecated.
- **Local model selection matters.** Models with Ollama's native tool-calling support (llama3.1, qwen2.5, qwen3, and others) produce significantly more reliable structured invocations than those relying on text format alone.
- **Debugging:** inspect the `messages` list in the returned state for the full reasoning trace; use `set_debug(True)` for the raw LLM I/O; use `ToolLoggingCallback` for structured production logging.
- **Memory** across turns is added via `MemorySaver` + a `thread_id` config when using `create_agent()`. This is conversation memory — separate from the full LangGraph workflow state covered in Module 9.
- The five tools in Section 6 — web search, Python REPL, file reader, RAG retrieval, and safe calculator — form a practical reusable library for the agents in this module and Module 9.

---

## Further Reading

- [LangChain Agents Documentation — Docs by LangChain](https://docs.langchain.com/oss/python/langchain/agents) — The official LangChain documentation for the current `create_agent()` API, covering the model-profile system, middleware, system prompt configuration, and streaming. This is the authoritative reference for the modern agent API introduced in LangChain 1.0 and extended in 1.1.

- [LangChain & LangGraph 1.0 Release — LangChain Blog](https://blog.langchain.com/langchain-langgraph-1dot0/) — The official announcement of LangChain 1.0 and LangGraph 1.0, explaining the deprecation of `AgentExecutor`, the introduction of `create_agent()`, and the commitment to API stability through to version 2.0. Essential reading for understanding why the API changed and what to expect going forward.

- [Tool Calling in Ollama — Official Ollama Documentation](https://ollama.com/blog/tool-support) — The official Ollama documentation on native tool/function calling support, including the JSON schema format for tool definitions, which models support tool calling, how tool responses flow back through the message chain, and streaming tool invocations. Essential reading for understanding what happens below the LangChain abstraction.

- [Ollama Tool-Compatible Models — Ollama Model Library](https://ollama.com/search?c=tools) — The official Ollama model library filtered to models with confirmed tool-calling support. Browse this to find the latest additions and check which models are available for your hardware. The list is updated with each Ollama release.

- [ChatOllama Integration — LangChain Docs](https://docs.langchain.com/oss/python/integrations/chat/ollama) — Complete integration reference for `ChatOllama` including `bind_tools()`, `with_structured_output()`, multimodal inputs, and streaming. The primary reference when the LangChain-Ollama integration behaves unexpectedly.

- [Understanding LangChain Agents: create_react_agent vs create_tool_calling_agent — Medium](https://medium.com/@anil.goyal0057/understanding-langchain-agents-create-react-agent-vs-create-tool-calling-agent-e977a9dfe31e) — A practitioner-level comparison of the two legacy agent constructors with code examples, showing how each prompts the LLM differently and how tool call output is parsed. Valuable for understanding existing codebases that still use these patterns.

- [Migrating Classic LangChain Agents to LangGraph — DEV Community](https://dev.to/focused_dot_io/migrating-classic-langchain-agents-to-langgraph-a-how-to-nea) — A practical step-by-step guide to migrating from `initialize_agent` and `AgentExecutor` to the modern LangGraph-based approach, with before/after code comparisons. Useful if you have existing agent code to upgrade.

- [DuckDuckGo Search — PyPI](https://pypi.org/project/duckduckgo-search/) — The PyPI page for the `duckduckgo-search` library used in this module's web search tool. Documents the `DDGS` class API, text search parameters, rate limiting behavior and the `RatelimitException`. No API key required.

- [MemorySaver and Checkpointers — LangGraph Documentation](https://langchain-ai.github.io/langgraph/reference/checkpoints/) — Reference documentation for LangGraph's checkpointing system, including `MemorySaver` (in-memory), `SqliteSaver` (local persistence), and `PostgresSaver` (production). Explains the `thread_id` session model and how to replay or inspect prior agent runs.

- [OWASP LLM Top 10: Prompt Injection (LLM01:2025)](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) — The OWASP Gen AI Security Project's treatment of prompt injection, the primary security risk for agents that process untrusted tool output (web pages, files, database entries). Read before deploying any agent that reads from external sources. Covers attack vectors, impact, and structural mitigations.
