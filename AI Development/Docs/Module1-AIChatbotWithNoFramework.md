# Module 1: Building a Basic AI Chatbot with No Framework

**Subject:** AI Development
**Difficulty:** Beginner to Intermediate
**Estimated Time:** 150 minutes (including hands-on examples)
**Prerequisites:** Python basics (functions, lists, dictionaries, loops), familiarity with installing packages via pip, general understanding of what a large language model does (see LLM Module 1 if needed)

---

## Overview

This module walks you through building a fully functional, multi-turn AI chatbot using nothing but a provider's official Python SDK and the standard library. No LangChain, no LlamaIndex, no agent frameworks. Just raw API calls.

That constraint is intentional. Every framework you will eventually use is a layer on top of the same handful of primitives you will learn here: the messages array, the stateless request-response cycle, token budgets, and streaming. Understanding these primitives directly means you can debug any framework, evaluate whether a framework is actually helping you, and write performant code that does not carry unnecessary abstraction overhead.

By the end of this module you will have two working chatbots — one using the Anthropic Claude SDK and one using the OpenAI SDK — and you will understand exactly what they are doing at every step.

---

## Required Libraries and Packages

All three chatbot implementations in this module use only official SDKs and the standard library. Install only what you need for the provider you are targeting.

### Package Summary

| Package | Version | Purpose | Install |
|---|---|---|---|
| `anthropic` | ≥ 0.89 | Anthropic Claude API SDK | `pip install anthropic` |
| `openai` | ≥ 1.30 | OpenAI API SDK | `pip install openai` |
| `ollama` | ≥ 0.6 | Ollama local model SDK | `pip install ollama` |
| `python-dotenv` | ≥ 1.0 | Load `.env` files into environment | `pip install python-dotenv` |
| `requests` | stdlib-free alt | HTTP fallback for Ollama REST API | `pip install requests` |

All other imports (`json`, `logging`, `os`, `sys`, `time`) are Python standard library — no installation required.

### Install by Provider

**Anthropic only:**
```bash
pip install anthropic python-dotenv
```

**OpenAI only:**
```bash
pip install openai python-dotenv
```

**Ollama (local models):**
```bash
pip install ollama python-dotenv
```

**All three:**
```bash
pip install anthropic openai ollama python-dotenv
```

Or use a `requirements.txt`:
```
anthropic>=0.89
openai>=1.30
ollama>=0.6
python-dotenv>=1.0
```
```bash
pip install -r requirements.txt
```

> **Ollama server requirement:** The `ollama` Python package is a thin SDK that talks to a locally running Ollama server. You must also install the Ollama application separately — see [ollama.com/download](https://ollama.com/download). The Python package alone is not enough.

---

## What We Are Building

A CLI chatbot that:

- Accepts typed user messages from the terminal
- Sends the full conversation history to the API on every turn
- Streams the response token by token as it arrives
- Applies a persistent system prompt to control the assistant's persona
- Trims conversation history automatically when it approaches the context limit
- Saves and loads conversation history to a JSON file so sessions persist across runs
- Handles API errors gracefully with retries

The complete working code appears in sections 8 and 9. The intervening sections explain how each piece works and why.

---

## Section 1: The Messages Array

Every call to a modern LLM chat API uses a messages array. This is the single most important data structure you will work with.

Each element in the array is a dictionary with two required keys:

- `role`: one of `"system"`, `"user"`, or `"assistant"`
- `content`: the text of the message

```python
messages = [
    {"role": "system", "content": "You are a concise assistant who answers in plain English."},
    {"role": "user", "content": "What is a context window?"},
    {"role": "assistant", "content": "A context window is the maximum amount of text an LLM can read at once when generating a response, measured in tokens."},
    {"role": "user", "content": "How big is Claude's context window?"},
]
```

### The Three Roles

**system** — Instructions for the model's behavior, persona, tone, or constraints. Sent once at the start of the array. The user never sees this directly. Think of it as the briefing you give an employee before their shift.

**user** — Input from the human side of the conversation. Every message the person types becomes a `user` entry appended to the array.

**assistant** — The model's previous responses. After each API call, you take the text the model returned and append it to the array as an `assistant` entry. This is how the model "remembers" what it said earlier.

### Why You Must Send the Entire History on Every Request

LLM APIs are stateless. The server does not remember your previous requests. When you make your second API call, the server has no record of your first one. This means you are responsible for maintaining conversation history in memory (or on disk) and re-sending the complete messages array on every single request.

```
Turn 1: Send [system, user1]             → receive assistant1
Turn 2: Send [system, user1, asst1, user2]    → receive assistant2
Turn 3: Send [system, user1, asst1, user2, asst2, user3]  → receive assistant3
```

Each request grows by two messages per turn. This is the core mechanics of a multi-turn chatbot.

---

## Section 2: Token Limits and Context Window Management

Every model has a context window — the maximum number of tokens that can appear in a single request (input plus output combined). If you exceed this limit the API returns an error.

### Current Model Context Windows (as of April 2026)

| Model | Context Window | Max Output | Notes |
|---|---|---|---|
| claude-haiku-4-5 | 200,000 tokens | 64,000 tokens | Fastest, lowest cost |
| claude-sonnet-4-6 | 1,000,000 tokens | 64,000 tokens | Best speed/intelligence balance |
| claude-opus-4-6 | 1,000,000 tokens | 128,000 tokens | Most capable, best for complex agents |
| gpt-4o | 128,000 tokens | 16,384 tokens | OpenAI flagship |
| llama3.2 (Ollama) | 128,000 tokens | model-dependent | Free local inference, no API key |

A rough rule of thumb: one token is approximately 0.75 English words, or 4 characters. A 200,000-token context window fits roughly 150,000 words — about 500 pages of dense text.

For a beginner chatbot using `claude-haiku-4-5`, you have 200,000 tokens of headroom. In practice, a conversation will rarely exceed this. But you should still write code that handles the limit gracefully, because production chatbots can and do hit it.

### Why Long Contexts Degrade

More context is not always better. A phenomenon called context rot means that model accuracy and recall degrade as the context grows. Important information buried in the middle of a very long conversation receives less attention than recent information. This is a property of the transformer architecture, not a bug that will be fixed.

Practical implication: keeping your context lean and relevant often produces better responses than stuffing in everything you have.

### Two Strategies for Managing a Growing Context

**Sliding Window** — Remove the oldest messages when total tokens exceed a threshold. Simple, fast, and loses older context entirely.

**Summarization** — Ask the model to summarize the conversation so far, replace the removed messages with that summary, and continue. Preserves meaning at the cost of one additional API call.

Both strategies are implemented in Section 5.

---

## Section 3: API Fundamentals

### Common Request Parameters

Every provider's chat API accepts a roughly similar set of parameters:

| Parameter | Type | Description |
|---|---|---|
| `model` | string | Which model to use (e.g. `"claude-haiku-4-5"`) |
| `messages` | list | The conversation history array |
| `system` | string | System prompt (Anthropic only; OpenAI puts it in messages) |
| `max_tokens` | integer | Hard cap on output length |
| `temperature` | float | Randomness of output. 0.0 = deterministic, 1.0 = creative |
| `stream` | boolean | Whether to stream the response token by token |

### The Anthropic Claude API

Install the SDK:

```bash
pip install anthropic
```

The Python SDK requires Python 3.9 or later. The SDK automatically reads `ANTHROPIC_API_KEY` from the environment.

Basic request:

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment

response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=1024,
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "What is the capital of France?"}
    ],
)

print(response.content[0].text)
```

The response object has a `content` field which is a list of content blocks. For plain text responses, `response.content[0].text` is what you want.

The `usage` field shows token consumption:

```python
print(response.usage)
# Usage(input_tokens=18, output_tokens=9)
```

Note that the Anthropic API takes the `system` prompt as a separate top-level parameter, not as an element inside the `messages` array. This is different from the OpenAI convention.

### The OpenAI API

Install the SDK:

```bash
pip install openai
```

The SDK automatically reads `OPENAI_API_KEY` from the environment.

Basic request:

```python
from openai import OpenAI

client = OpenAI()  # reads OPENAI_API_KEY from environment

response = client.chat.completions.create(
    model="gpt-4o",
    max_tokens=1024,
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
    ],
)

print(response.choices[0].message.content)
```

With OpenAI, the system prompt is a regular message in the `messages` array with `role: "system"`. It must appear as the first element.

---

## Section 4: Handling API Errors

Both SDKs raise specific exception types for different failure modes. You must handle at least three categories:

1. **Rate limit errors (429)** — You are sending too many requests per minute. Back off and retry.
2. **Connection errors** — Network problems. Retry with backoff.
3. **Authentication errors (401)** — Your API key is wrong or missing. Do not retry; fix the configuration.

### Built-in Retry Behavior

Both the `anthropic` and `openai` SDKs automatically retry transient failures (connection errors, 408 timeouts, 409 conflicts, 429 rate limits, and 5xx server errors) up to 2 times by default, using exponential backoff starting at 0.5 seconds.

You can adjust this:

```python
# Anthropic: configure max retries on the client
client = anthropic.Anthropic(max_retries=4)

# OpenAI: same pattern
client = OpenAI(max_retries=4)
```

### Manual Error Handling

For cases where you need custom logic around retries, wrap your API calls in explicit exception handlers:

```python
import time
import anthropic

client = anthropic.Anthropic()

def call_with_retry(messages, system, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1024,
                system=system,
                messages=messages,
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            wait = 2 ** attempt  # 1s, 2s, 4s
            print(f"Rate limited. Waiting {wait}s before retry {attempt + 1}/{max_attempts}...")
            time.sleep(wait)
        except anthropic.APIConnectionError as e:
            print(f"Connection error: {e}. Retrying...")
            time.sleep(1)
        except anthropic.AuthenticationError:
            print("Authentication failed. Check your ANTHROPIC_API_KEY.")
            raise  # do not retry; this requires human intervention
        except anthropic.APIStatusError as e:
            print(f"API error {e.status_code}: {e.message}")
            raise
    raise RuntimeError(f"Failed after {max_attempts} attempts")
```

---

## Section 5: Building the Chatbot Step by Step

### Step 1: Single-Turn Request (No History)

The simplest possible interaction — one question, one answer, no memory:

```python
import os
import anthropic
from dotenv import load_dotenv

load_dotenv()  # loads ANTHROPIC_API_KEY from .env file

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=512,
    messages=[{"role": "user", "content": "Tell me a fun fact about penguins."}],
)
print(response.content[0].text)
```

### Step 2: Multi-Turn with Manual History Management

Maintain a list and append to it after each exchange:

```python
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()
history = []

def chat(user_input, system_prompt="You are a helpful assistant."):
    history.append({"role": "user", "content": user_input})

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=system_prompt,
        messages=history,
    )

    assistant_reply = response.content[0].text
    history.append({"role": "assistant", "content": assistant_reply})
    return assistant_reply

print(chat("My name is Alex."))
print(chat("What is my name?"))  # The model will answer correctly because history is preserved
```

### Step 3: Adding a System Prompt for Persona

The system prompt is the single most effective way to shape behavior. Define it once as a constant and never repeat it in user messages:

```python
SYSTEM_PROMPT = """You are Aria, a knowledgeable assistant specializing in Python programming.
Your answers are concise, accurate, and include runnable code examples when relevant.
You do not answer questions unrelated to programming or software development.
When you do not know something, say so clearly rather than guessing."""
```

### Step 4: Streaming Responses Token by Token

Without streaming, the API waits until the entire response is generated before sending it back. For a long response this can mean a 5-10 second wait with no feedback. Streaming sends tokens as they are generated, so the user sees output immediately.

**Anthropic streaming:**

```python
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()

def chat_streaming(messages, system_prompt):
    full_response = ""

    with client.messages.stream(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    ) as stream:
        for text_chunk in stream.text_stream:
            print(text_chunk, end="", flush=True)
            full_response += text_chunk

    print()  # newline after response ends
    return full_response
```

The `flush=True` argument to `print()` forces Python to write the character to the terminal immediately rather than buffering it. Without this, streaming output would appear in chunks or only at the end.

**OpenAI streaming:**

```python
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

def chat_streaming_openai(messages):
    full_response = ""

    stream = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=messages,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta is not None:
            print(delta, end="", flush=True)
            full_response += delta

    print()
    return full_response
```

### Step 5: Context Window Trimming

Two implementations — one for each strategy discussed in Section 2.

**Sliding window** (drops oldest non-system messages):

```python
def trim_history_sliding_window(history, max_messages=20):
    """
    Keep only the most recent max_messages messages.
    Always preserves the full array structure; does not touch the system prompt
    (which is passed separately to the Anthropic API).
    """
    if len(history) <= max_messages:
        return history
    # Drop oldest messages from the front, but always keep pairs intact
    # by ensuring we trim an even number (user+assistant pairs)
    excess = len(history) - max_messages
    if excess % 2 != 0:
        excess += 1
    return history[excess:]
```

**Summarization** (preserves meaning):

```python
def summarize_and_trim(history, client, system_prompt):
    """
    Ask the model to summarize the conversation, then replace the history
    with a single user message containing the summary.
    """
    conversation_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in history
    )

    summary_response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": (
                    "Summarize the following conversation in 3-5 sentences, "
                    "preserving the key facts and decisions made:\n\n"
                    + conversation_text
                ),
            }
        ],
    )
    summary = summary_response.content[0].text

    # Replace the full history with a synthetic user message containing the summary
    return [
        {
            "role": "user",
            "content": f"[Summary of earlier conversation]: {summary}",
        },
        {
            "role": "assistant",
            "content": "Understood. I have the context from our earlier conversation.",
        },
    ]
```

### Step 6: Adding a CLI Interface

```python
def run_cli(client, system_prompt):
    history = []
    print("Chatbot ready. Type 'quit' or 'exit' to stop, 'save' to save history.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye.")
            break
        if user_input.lower() == "save":
            save_history(history, "conversation.json")
            print("History saved to conversation.json")
            continue

        history.append({"role": "user", "content": user_input})
        history = trim_history_sliding_window(history, max_messages=40)

        print("Assistant: ", end="", flush=True)
        reply = chat_streaming(history[:-1] + [history[-1]], system_prompt, client)
        history.append({"role": "assistant", "content": reply})
```

### Step 7: Graceful Exit and Keyboard Interrupt Handling

The `try/except (EOFError, KeyboardInterrupt)` block in the loop above covers two cases:

- **KeyboardInterrupt** — the user presses Ctrl+C during normal input
- **EOFError** — the input stream is closed (e.g., when piping input from a file)

For an in-progress streaming response, you may also want to handle Ctrl+C mid-stream:

```python
try:
    with client.messages.stream(...) as stream:
        for text_chunk in stream.text_stream:
            print(text_chunk, end="", flush=True)
            full_response += text_chunk
except KeyboardInterrupt:
    print("\n[Response interrupted by user]")
    # full_response contains whatever was received before the interrupt
```

---

## Section 6: Storing and Managing Conversation State

### In-Memory (Simplest)

A plain Python list. All state is lost when the process exits. Fine for prototyping.

```python
history = []
```

### Saving and Loading to JSON

```python
import json
import os

def save_history(history, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def load_history(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
```

Usage in the main loop:

```python
HISTORY_FILE = "conversation.json"
history = load_history(HISTORY_FILE)  # resume previous session if file exists

# ... run the chat loop ...

save_history(history, HISTORY_FILE)  # persist before exit
```

### Session IDs for Multiple Concurrent Conversations

If you need to support multiple independent conversations — for example, a web server handling many users — give each conversation a unique session ID and store histories in a dictionary:

```python
import uuid

sessions = {}  # session_id -> list of messages

def get_or_create_session(session_id=None):
    if session_id is None:
        session_id = str(uuid.uuid4())
    if session_id not in sessions:
        sessions[session_id] = []
    return session_id, sessions[session_id]

def chat_session(session_id, user_input, system_prompt, client):
    session_id, history = get_or_create_session(session_id)
    history.append({"role": "user", "content": user_input})

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=system_prompt,
        messages=history,
    )

    reply = response.content[0].text
    history.append({"role": "assistant", "content": reply})
    return session_id, reply
```

For a production system you would replace the in-memory `sessions` dictionary with a database or Redis cache.

---

## Section 7: Best Practices

### Separate Configuration from Code

Never hardcode API keys, model names, or system prompts inline in your functions. Group them at the top of your file or in a dedicated config module:

```python
# config.py
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]  # raises KeyError if missing
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1024
MAX_HISTORY_MESSAGES = 40

SYSTEM_PROMPT = """You are a helpful, concise assistant.
Answer questions accurately. If you are unsure, say so."""
```

Using `os.environ["KEY"]` (square brackets, not `.get()`) is intentional: it raises a `KeyError` immediately at startup if the variable is missing, rather than silently returning `None` and producing a confusing authentication error later.

### Use python-dotenv for Secrets

Never commit API keys to source control. Store them in a `.env` file:

```
# .env  (add this file to .gitignore)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Load the file at the top of your script:

```python
from dotenv import load_dotenv
load_dotenv()
```

Add `.env` to `.gitignore`:

```
# .gitignore
.env
```

### Log Requests and Responses for Debugging

The Anthropic SDK has a built-in logging facility. Enable it by setting an environment variable — no code changes needed:

```bash
export ANTHROPIC_LOG=debug
```

For structured application logging, log the request ID returned with every response. This allows you to file a precise support ticket if something goes wrong:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

response = client.messages.create(...)
logger.info("Request ID: %s | Input tokens: %d | Output tokens: %d",
            response._request_id,
            response.usage.input_tokens,
            response.usage.output_tokens)
```

### Keep the System Prompt DRY

Define the system prompt exactly once. Import it wherever needed. Do not copy-paste it into multiple functions or files — when you need to update it you will miss one.

---

## Section 8: Complete Working Example — Anthropic SDK

This is a self-contained, runnable CLI chatbot using the Anthropic SDK. Save it as `chatbot_anthropic.py`.

Dependencies:
```bash
pip install anthropic python-dotenv
```

```python
"""
chatbot_anthropic.py
A multi-turn CLI chatbot using the Anthropic Python SDK.
No frameworks — only the official SDK and the standard library.
"""

import json
import logging
import os
import sys
import time

import anthropic
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1024
MAX_HISTORY_MESSAGES = 40  # trim when history exceeds this many messages
HISTORY_FILE = "conversation_anthropic.json"

SYSTEM_PROMPT = """You are a helpful, concise assistant.
Answer questions accurately and directly.
If you do not know something, say so honestly rather than guessing."""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.FileHandler("chatbot.log"), logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# History persistence
# ---------------------------------------------------------------------------

def load_history(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(history, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------------
# Context trimming
# ---------------------------------------------------------------------------

def trim_history(history, max_messages):
    """Drop the oldest messages when history grows too long.
    Always removes pairs (user + assistant) to keep the array well-formed."""
    if len(history) <= max_messages:
        return history
    excess = len(history) - max_messages
    if excess % 2 != 0:
        excess += 1
    trimmed = history[excess:]
    logger.info("Trimmed %d messages from history.", excess)
    return trimmed

# ---------------------------------------------------------------------------
# API call with streaming
# ---------------------------------------------------------------------------

def send_message(client, history, max_attempts=3):
    """Send the current history to the API and stream the response.
    Returns the complete assistant reply as a string."""
    for attempt in range(max_attempts):
        try:
            full_response = ""
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=history,
            ) as stream:
                for text_chunk in stream.text_stream:
                    print(text_chunk, end="", flush=True)
                    full_response += text_chunk

            print()  # newline after streaming ends

            # Log token usage from the final message object
            final_message = stream.get_final_message()
            logger.info(
                "Request ID: %s | Input tokens: %d | Output tokens: %d",
                final_message._request_id,
                final_message.usage.input_tokens,
                final_message.usage.output_tokens,
            )
            return full_response

        except anthropic.RateLimitError:
            wait = 2 ** attempt
            logger.warning("Rate limited. Waiting %ds (attempt %d/%d).", wait, attempt + 1, max_attempts)
            time.sleep(wait)
        except anthropic.APIConnectionError as e:
            logger.warning("Connection error: %s. Retrying...", e)
            time.sleep(1)
        except anthropic.AuthenticationError:
            logger.error("Authentication failed. Check ANTHROPIC_API_KEY.")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n[Response interrupted]")
            return full_response  # return whatever arrived before the interrupt

    raise RuntimeError(f"API call failed after {max_attempts} attempts.")

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    client = anthropic.Anthropic()

    history = load_history(HISTORY_FILE)
    if history:
        print(f"Resumed session with {len(history)} messages from {HISTORY_FILE}")

    print(f"Model: {MODEL}")
    print("Commands: 'quit'/'exit' to stop, 'save' to save, 'clear' to reset history.")
    print("-" * 60)

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            save_history(history, HISTORY_FILE)
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye.")
            save_history(history, HISTORY_FILE)
            break

        if user_input.lower() == "save":
            save_history(history, HISTORY_FILE)
            print(f"Saved {len(history)} messages to {HISTORY_FILE}.")
            continue

        if user_input.lower() == "clear":
            history = []
            print("History cleared.")
            continue

        history.append({"role": "user", "content": user_input})
        history = trim_history(history, MAX_HISTORY_MESSAGES)

        print("Assistant: ", end="", flush=True)
        reply = send_message(client, history)
        history.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()
```

---

## Section 9: Complete Working Example — OpenAI SDK

Save this as `chatbot_openai.py`. The logic is identical to the Anthropic version; only the SDK-specific calls differ.

Dependencies:
```bash
pip install openai python-dotenv
```

```python
"""
chatbot_openai.py
A multi-turn CLI chatbot using the OpenAI Python SDK.
No frameworks — only the official SDK and the standard library.
"""

import json
import logging
import os
import sys
import time

from openai import OpenAI, RateLimitError, APIConnectionError, AuthenticationError
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "gpt-4o"
MAX_TOKENS = 1024
MAX_HISTORY_MESSAGES = 40
HISTORY_FILE = "conversation_openai.json"

SYSTEM_PROMPT = """You are a helpful, concise assistant.
Answer questions accurately and directly.
If you do not know something, say so honestly rather than guessing."""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.FileHandler("chatbot.log"), logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# History persistence
# ---------------------------------------------------------------------------

def load_history(filepath):
    if not os.path.exists(filepath):
        # OpenAI puts the system prompt inside the messages array
        return [{"role": "system", "content": SYSTEM_PROMPT}]
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(history, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------------
# Context trimming
# ---------------------------------------------------------------------------

def trim_history(history, max_messages):
    """Drop the oldest non-system messages when history grows too long.
    Preserves the system message at index 0."""
    system_messages = [m for m in history if m["role"] == "system"]
    non_system = [m for m in history if m["role"] != "system"]

    if len(non_system) <= max_messages:
        return history

    excess = len(non_system) - max_messages
    if excess % 2 != 0:
        excess += 1
    trimmed_non_system = non_system[excess:]
    logger.info("Trimmed %d messages from history.", excess)
    return system_messages + trimmed_non_system

# ---------------------------------------------------------------------------
# API call with streaming
# ---------------------------------------------------------------------------

def send_message(client, history, max_attempts=3):
    """Send the current history to the API and stream the response."""
    for attempt in range(max_attempts):
        try:
            full_response = ""
            stream = client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=history,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta is not None:
                    print(delta, end="", flush=True)
                    full_response += delta

            print()
            return full_response

        except RateLimitError:
            wait = 2 ** attempt
            logger.warning("Rate limited. Waiting %ds (attempt %d/%d).", wait, attempt + 1, max_attempts)
            time.sleep(wait)
        except APIConnectionError as e:
            logger.warning("Connection error: %s. Retrying...", e)
            time.sleep(1)
        except AuthenticationError:
            logger.error("Authentication failed. Check OPENAI_API_KEY.")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n[Response interrupted]")
            return full_response

    raise RuntimeError(f"API call failed after {max_attempts} attempts.")

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    client = OpenAI()

    history = load_history(HISTORY_FILE)
    non_system_count = sum(1 for m in history if m["role"] != "system")
    if non_system_count > 0:
        print(f"Resumed session with {non_system_count} messages from {HISTORY_FILE}")

    print(f"Model: {MODEL}")
    print("Commands: 'quit'/'exit' to stop, 'save' to save, 'clear' to reset history.")
    print("-" * 60)

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            save_history(history, HISTORY_FILE)
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye.")
            save_history(history, HISTORY_FILE)
            break

        if user_input.lower() == "save":
            save_history(history, HISTORY_FILE)
            print(f"Saved to {HISTORY_FILE}.")
            continue

        if user_input.lower() == "clear":
            history = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("History cleared.")
            continue

        history.append({"role": "user", "content": user_input})
        history = trim_history(history, MAX_HISTORY_MESSAGES)

        print("Assistant: ", end="", flush=True)
        reply = send_message(client, history)
        history.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()
```

---

## Section 10: Local Chatbot with Ollama

Ollama lets you run open-weight models (LLaMA 3, Mistral, Gemma, Qwen, and others) entirely on your own machine. No API key, no per-token cost, no data leaving your system. The `ollama` Python SDK exposes the same messages-array pattern you already know — the chat loop code is nearly identical to the API versions.

### Prerequisites

1. Install Ollama: [ollama.com/download](https://ollama.com/download) (available for macOS, Linux, Windows)
2. Pull a model:

```bash
ollama pull llama3.2          # Meta LLaMA 3.2 3B — fast, low VRAM (~2 GB)
ollama pull mistral           # Mistral 7B — strong general-purpose (~5 GB)
ollama pull qwen2.5:7b        # Qwen 2.5 7B — strong reasoning (~5 GB)
ollama pull gemma3:4b         # Google Gemma 3 4B — efficient (~3 GB)
```

3. Verify Ollama is running:
```bash
ollama list          # lists downloaded models
ollama run llama3.2  # quick sanity check — type /bye to exit
```

4. Install the Python SDK:
```bash
pip install ollama python-dotenv
```

### How the Ollama SDK Relates to the API SDKs

Ollama's Python SDK mirrors the OpenAI SDK interface intentionally. If you understand the OpenAI version, the Ollama version is almost a drop-in swap:

| | Anthropic SDK | OpenAI SDK | Ollama SDK |
|---|---|---|---|
| Client | `anthropic.Anthropic()` | `openai.OpenAI()` | No client object needed |
| Chat call | `client.messages.create()` | `client.chat.completions.create()` | `ollama.chat()` |
| System prompt | Top-level `system=` param | First message `role:"system"` | First message `role:"system"` |
| Response text | `response.content[0].text` | `response.choices[0].message.content` | `response['message']['content']` |
| Streaming | `client.messages.stream()` | `stream=True`, iterate chunks | `stream=True`, iterate chunks |
| API key | `ANTHROPIC_API_KEY` env var | `OPENAI_API_KEY` env var | None required |
| Internet required | Yes | Yes | No (fully local) |

### Basic Single-Turn Request

```python
import ollama

response = ollama.chat(
    model="llama3.2",
    messages=[
        {"role": "user", "content": "What is a context window?"}
    ],
)

print(response['message']['content'])
```

### Multi-Turn with History

```python
import ollama

history = [
    {"role": "system", "content": "You are a concise assistant. Answer in plain English."}
]

def chat(user_input: str) -> str:
    history.append({"role": "user", "content": user_input})
    response = ollama.chat(model="llama3.2", messages=history)
    reply = response['message']['content']
    history.append({"role": "assistant", "content": reply})
    return reply

print(chat("What is the transformer architecture?"))
print(chat("How does attention work in it?"))   # model remembers context
```

### Streaming Responses

```python
import ollama
import sys

def chat_stream(model: str, messages: list) -> str:
    full_reply = []
    stream = ollama.chat(model=model, messages=messages, stream=True)
    for chunk in stream:
        token = chunk['message']['content']
        print(token, end="", flush=True)
        full_reply.append(token)
    print()  # newline after stream ends
    return "".join(full_reply)
```

### Complete Working Example — Ollama

Save as `chatbot_ollama.py`. No API key needed — just a running Ollama server and at least one pulled model.

Dependencies:
```bash
pip install ollama python-dotenv
```

```python
"""
chatbot_ollama.py
A multi-turn CLI chatbot using a local Ollama model.
No API key required. Runs entirely on your machine.
"""

import json
import logging
import os
import sys

import ollama
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")    # override via .env: OLLAMA_MODEL=mistral
MAX_HISTORY_MESSAGES = 40
HISTORY_FILE = "chat_history_ollama.json"
SYSTEM_PROMPT = """You are a helpful, concise assistant.
Answer questions accurately. If you are unsure, say so.
Keep responses focused and avoid unnecessary padding."""

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# --- History helpers ---

def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def save_history(history: list) -> None:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def trim_history(history: list) -> list:
    """Keep system message + most recent MAX_HISTORY_MESSAGES user/assistant pairs."""
    system_messages = [m for m in history if m["role"] == "system"]
    conversation = [m for m in history if m["role"] != "system"]
    if len(conversation) > MAX_HISTORY_MESSAGES:
        conversation = conversation[-MAX_HISTORY_MESSAGES:]
    return system_messages + conversation


# --- Core chat function ---

def send_message(history: list, user_input: str) -> str:
    history.append({"role": "user", "content": user_input})
    history = trim_history(history)

    full_reply = []

    try:
        stream = ollama.chat(model=MODEL, messages=history, stream=True)
        for chunk in stream:
            token = chunk['message']['content']
            print(token, end="", flush=True)
            full_reply.append(token)
        print()  # newline after stream ends

    except ollama.ResponseError as e:
        # Covers model-not-found, server errors, etc.
        if "model" in str(e).lower() and "not found" in str(e).lower():
            print(f"\n[Error] Model '{MODEL}' not found. Run: ollama pull {MODEL}")
        else:
            print(f"\n[Ollama error] {e}")
        history.pop()   # remove the user message we just added
        return ""

    except Exception as e:
        print(f"\n[Unexpected error] {e}")
        logger.exception("Unexpected error in send_message")
        history.pop()
        return ""

    reply = "".join(full_reply)
    history.append({"role": "assistant", "content": reply})
    return reply


# --- Main loop ---

def main() -> None:
    print(f"Ollama Chatbot — model: {MODEL}")
    print("Type 'quit' or press Ctrl+C to exit. Type 'reset' to clear history.\n")

    # Check Ollama server is reachable
    try:
        models = ollama.list()
        available = [m['name'] for m in models.get('models', [])]
        if MODEL not in available and not any(MODEL in name for name in available):
            print(f"Warning: '{MODEL}' not found in pulled models.")
            print(f"Available models: {available or 'none'}")
            print(f"Run: ollama pull {MODEL}\n")
    except Exception:
        print("Warning: Could not connect to Ollama server.")
        print("Make sure Ollama is running: https://ollama.com/download\n")

    history = load_history()

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "bye"):
                print("Goodbye!")
                break
            if user_input.lower() == "reset":
                history = [{"role": "system", "content": SYSTEM_PROMPT}]
                save_history(history)
                print("[History cleared]\n")
                continue

            print("Assistant: ", end="", flush=True)
            send_message(history, user_input)
            save_history(history)

    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")

    save_history(history)


if __name__ == "__main__":
    main()
```

### Choosing a Local Model

| Model | Size | VRAM | Strength |
|---|---|---|---|
| `llama3.2` | 3B | ~2 GB | Fast, everyday chat |
| `llama3.2:1b` | 1B | ~1 GB | Minimal hardware |
| `mistral` | 7B | ~5 GB | Strong general-purpose |
| `qwen2.5:7b` | 7B | ~5 GB | Reasoning, coding |
| `gemma3:4b` | 4B | ~3 GB | Efficient, Google-trained |
| `phi4` | 14B | ~9 GB | Strong reasoning, small size |
| `llama3.1:8b` | 8B | ~6 GB | Balanced quality/speed |

> **CPU fallback:** If you have no GPU, Ollama will run on CPU. Expect 1–5 tokens/second for 7B models. Use a 1B–3B model for a tolerable interactive experience.

---

## Section 11: Side-by-Side Comparison

The three implementations are structurally identical. The differences are all at the SDK boundary:

| Concern | Anthropic SDK | OpenAI SDK | Ollama SDK |
|---|---|---|---|
| Install | `pip install anthropic` | `pip install openai` | `pip install ollama` |
| Client class | `anthropic.Anthropic()` | `openai.OpenAI()` | No client object |
| API call method | `client.messages.stream(...)` | `client.chat.completions.create(..., stream=True)` | `ollama.chat(..., stream=True)` |
| System prompt location | Top-level `system=` parameter | First message `role:"system"` | First message `role:"system"` |
| Streaming iteration | `for text in stream.text_stream` | `for chunk in stream; chunk.choices[0].delta.content` | `for chunk in stream; chunk['message']['content']` |
| Response text (non-streaming) | `response.content[0].text` | `response.choices[0].message.content` | `response['message']['content']` |
| Token usage | `response.usage.input_tokens` / `.output_tokens` | `response.usage.prompt_tokens` / `.completion_tokens` | Not returned by default |
| Rate limit exception | `anthropic.RateLimitError` | `openai.RateLimitError` | N/A (local, no rate limits) |
| Connection exception | `anthropic.APIConnectionError` | `openai.APIConnectionError` | `ollama.ResponseError` |
| Auth exception | `anthropic.AuthenticationError` | `openai.AuthenticationError` | N/A (no auth required) |
| API key required | Yes (`ANTHROPIC_API_KEY`) | Yes (`OPENAI_API_KEY`) | No |
| Internet required | Yes | Yes | No |
| Cost per token | Yes | Yes | Free (self-hosted) |
| Model runs on | Anthropic's servers | OpenAI's servers | Your machine |

The key architectural difference is the system prompt placement. Anthropic treats it as a separate concern from the conversation history. OpenAI and Ollama both embed it as the first element of the `messages` array with `role: "system"`. When writing history trimming code, never accidentally remove the system message for the OpenAI or Ollama versions.

---

## Section 12: Common Mistakes and How to Avoid Them

**Forgetting to append the assistant reply to history.** If you send the user message but do not append the model's reply after receiving it, the next turn will not include the model's previous response. The model will appear to have amnesia.

**Printing the raw response object.** `print(response)` prints a Pydantic model representation, not the text. Always use `response.content[0].text` (Anthropic) or `response.choices[0].message.content` (OpenAI).

**Setting `max_tokens` too low.** If the model's natural response would be 500 tokens but you set `max_tokens=100`, the response will be cut off mid-sentence. The API returns this as `stop_reason: "max_tokens"`. For a conversational chatbot, `1024` is a reasonable default.

**Not using `flush=True` when streaming.** Without `flush=True`, Python buffers terminal output. The streaming effect — characters appearing one at a time — will not work.

**Storing API keys in source code.** Use `.env` files with `python-dotenv` and add `.env` to `.gitignore`. Leaked API keys are the most common and most avoidable security incident for AI developers.

**Trimming history mid-pair.** Removing just a user message without its paired assistant response (or vice versa) creates a malformed history. The messages array must always alternate user/assistant after any system messages. Always trim in pairs.

**Treating `temperature=0` as truly deterministic.** Temperature 0 makes the model highly consistent but not mathematically deterministic in all cases due to floating-point nondeterminism in GPU operations. Do not write tests that assert exact output text.

---

## Exercises

1. **Basic connection test.** Install the `anthropic` package, create a `.env` file with your API key, and run the single-turn example from Section 5 Step 1. Verify you receive a response.

2. **Observe statelessness.** Comment out the line that appends the assistant reply to `history` in the multi-turn example. Run the chatbot and ask two related questions. Notice that the second answer does not reference the first. Re-add the line and confirm the behavior returns.

3. **Measure token usage.** Modify the `send_message` function in `chatbot_anthropic.py` to print input and output token counts after every response. Have a 10-turn conversation. Plot (or simply note) how input tokens grow with each turn.

4. **Implement sliding window trimming.** Set `MAX_HISTORY_MESSAGES = 4` in `chatbot_anthropic.py`. Have a conversation of 10 turns. Observe that the model forgets context from early turns.

5. **Add summarization trimming.** Implement the `summarize_and_trim` function from Section 5 Step 5 and wire it into the main loop so it fires when history exceeds 10 messages. Compare how much context the model retains versus the sliding window approach.

6. **Port to OpenAI.** Take the complete `chatbot_anthropic.py` and convert it to `chatbot_openai.py` without looking at the provided solution. Pay attention to the system prompt placement and streaming iteration differences.

7. **Run a local model with Ollama.** Install Ollama, pull `llama3.2`, and run `chatbot_ollama.py`. Compare response quality and speed to the API versions. Try the same 5 questions against all three implementations and note the differences.

8. **Swap Ollama models.** Modify `chatbot_ollama.py` to accept the model name as a command-line argument (`sys.argv[1]`). Run it with `mistral` and `qwen2.5:7b`. Compare their response styles on a coding question.

---

## Key Takeaways

- The messages array (system, user, assistant) is the universal interface for chat APIs. All complexity builds on top of it.
- LLM APIs are stateless. You own the conversation history and must send it in full with every request.
- Streaming uses `flush=True` printing and provides immediate feedback to users at no extra API cost.
- Both the Anthropic and OpenAI SDKs handle retries automatically for transient errors. Explicit error handling is still needed for authentication failures and non-retriable errors.
- Separate your configuration (API key, model name, system prompt) from your logic. Define each value exactly once.
- Context windows are large but not infinite. Write trimming logic from the start; retrofitting it is painful.

---

## Further Reading

- [Anthropic Python SDK documentation](https://platform.claude.com/docs/en/api/sdks/python) — Complete reference for the `anthropic` Python package including async usage, streaming helpers, token counting, and advanced configuration. Start here for anything SDK-related.

- [Anthropic Models Overview](https://platform.claude.com/docs/en/about-claude/models/overview) — Current model names, context window sizes, pricing, and capability comparisons. Consult this page before choosing a model for a new project; model IDs change across generations.

- [Anthropic Context Windows Guide](https://platform.claude.com/docs/en/build-with-claude/context-windows) — Explains context rot, token budgeting, and the API-level behavior when you exceed the context limit. Essential reading before building any long-running chatbot or agent.

- [OpenAI Python library on GitHub](https://github.com/openai/openai-python) — Source code and README for the official OpenAI Python SDK. Includes configuration options, streaming patterns, and the full exception hierarchy not always reflected in the web documentation.

- [How to handle rate limits — OpenAI Cookbook](https://cookbook.openai.com/examples/how_to_handle_rate_limits) — Practical patterns for exponential backoff and rate limit management, including the Tenacity library approach. The patterns transfer directly to the Anthropic SDK.

- [python-dotenv on PyPI](https://pypi.org/project/python-dotenv/) — Documentation for loading `.env` files. Covers precedence rules, multiline values, and the difference between `load_dotenv()` and `dotenv_values()`.

- [Real Python: Python Logging Tutorial](https://realpython.com/python-logging/) — Thorough walkthrough of the standard library `logging` module. Knowing how to configure log levels, handlers, and formatters is essential for debugging API integrations in development and production.

- [Ollama Python SDK on GitHub](https://github.com/ollama/ollama-python) — Source code and full API reference for the `ollama` Python package, including async support, custom host configuration, and the full response schema.

- [Ollama Model Library](https://ollama.com/library) — Browse all models available via `ollama pull`. Each listing shows parameter count, quantization options, VRAM requirements, and benchmark scores. Consult this before choosing a local model.

---

*Module 1 of the AI Development series. Next module: Prompt Engineering Fundamentals — how to write system prompts, few-shot examples, and structured output instructions that produce reliable, predictable behavior.*
