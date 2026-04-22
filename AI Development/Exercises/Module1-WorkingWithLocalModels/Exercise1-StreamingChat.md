# Exercise 1: Streaming Chat App with Gradio

> Module: Module 1 — Working with Local Models | Difficulty: Easy | Estimated Time: 60–90 minutes

## Overview

You will build a **Gradio-powered chat application** that connects to a locally running Ollama server and streams responses token-by-token into the UI. Users can pick any locally available model from a dropdown, adjust the sampling temperature via a slider, and hold a full multi-turn conversation — all without touching the command line after launch.

This exercise forces you to wire together three distinct skills from Module 1:

1. Using `ollama.Client` with a configurable host (not the default `localhost`)
2. Streaming chat responses using `stream=True` and yielding tokens incrementally
3. Maintaining multi-turn conversation history (the `messages` list pattern)

## Learning Objectives

After completing this exercise you will be able to:

- Discover available Ollama models at runtime using `client.list()`
- Connect to an Ollama server at a custom host via environment variable
- Stream a chat response through Gradio's generator-based `ChatInterface`
- Correctly append both user and assistant turns to the message history
- Package a Gradio app in a Docker image with a non-root user and health check

## Prerequisites

- Ollama installed and running (`ollama serve` or the system service)
- At least one model pulled locally (e.g., `ollama pull llama3.2`)
- Python 3.11 with `gradio` and `ollama` installed, **or** Docker Desktop

## Scenario

Your team runs Ollama on a shared development server. Colleagues without terminal access need a web UI to chat with whatever models are currently available on that server. You are building that UI. The server address must be configurable via an environment variable (`OLLAMA_HOST`) so the same Docker image works in any environment.

---

## Directory Structure

```
Exercise1-StreamingChat/
├── app.py            # Main Gradio application (you implement the TODOs)
├── requirements.txt  # Python dependencies
├── Dockerfile        # Container definition
└── README.md         # Run instructions
```

---

## Instructions

### Step 1 — Connect to Ollama using a configurable host

Open `app.py`. At the top, read the `OLLAMA_HOST` environment variable (default `http://localhost:11434`) and use it to create an `ollama.Client` instance. This client will be used for every subsequent SDK call.

> Hint: `os.environ.get("OLLAMA_HOST", "http://localhost:11434")` and `ollama.Client(host=...)`.

### Step 2 — List available models for the dropdown

Implement the `get_available_models()` function. It should call `client.list()` and return a list of model name strings. These names will populate the model selector dropdown on page load.

> Hint: `client.list()` returns an object with a `models` attribute. Each entry has a `model` field containing the model name string (e.g., `"llama3.2:latest"`).

### Step 3 — Build the message history from Gradio's chat history

Implement `build_messages()`. Gradio's `ChatInterface` passes conversation history as a list of `[user_text, assistant_text]` pairs. Convert these into the `[{"role": ..., "content": ...}]` format that Ollama expects. Include a fixed system prompt at position 0.

> Hint: Iterate over `history` pairs. For each pair, append a user dict, then — only if the assistant text is not `None` — append an assistant dict.

### Step 4 — Stream the response

Implement `chat_stream()`. This function receives the current user message, the full Gradio chat history, the selected model name, and the temperature value. It must:

1. Call `build_messages()` to assemble the full history including the new user turn
2. Call `client.chat()` with `stream=True` and the selected model and temperature
3. Yield partial response strings incrementally so Gradio can update the UI in real time

> Hint: Accumulate tokens in a list and yield `"".join(accumulated)` after each chunk so the UI always shows the full partial response, not just the latest token.

### Step 5 — Wire up the Gradio interface

Implement `build_ui()`. Create a `gr.Blocks` layout containing:

- A `gr.Dropdown` for model selection (choices from `get_available_models()`, label `"Model"`)
- A `gr.Slider` for temperature (minimum `0.0`, maximum `2.0`, step `0.05`, value `0.7`, label `"Temperature"`)
- A `gr.ChatInterface` that calls `chat_stream` and passes the dropdown and slider as `additional_inputs`

Launch the app on host `0.0.0.0` and port `7860`.

### Step 6 — Complete the Dockerfile

The provided Dockerfile has three TODO markers. Fill in:

1. The `pip install` command using `requirements.txt`
2. The `HEALTHCHECK` instruction that curls `http://localhost:7860/`
3. The `CMD` that starts the app with `python app.py`

---

## Expected Outcome

Verify each item before marking the exercise complete:

- [ ] Running `python app.py` (with Ollama running locally) opens the Gradio UI at `http://localhost:7860`
- [ ] The model dropdown lists every model returned by `ollama list` on your machine
- [ ] Sending a message produces a streaming response — text appears token-by-token, not all at once
- [ ] Sending a second message in the same session produces a reply that is aware of the first exchange (multi-turn context works)
- [ ] Changing the temperature slider and sending a new message uses the updated value
- [ ] `docker build -t streaming-chat .` completes without error
- [ ] `docker run -e OLLAMA_HOST=http://host.docker.internal:11434 -p 7860:7860 streaming-chat` starts and the UI is reachable at `http://localhost:7860`

---

## Bonus Challenges

1. Add a **"Clear conversation"** button that resets the chat history without reloading the page.
2. Display the name of the currently active model as a `gr.Markdown` header that updates when the dropdown changes.
3. Add a `num_ctx` slider (range 512–16384, step 512) and include it in the `options` dict passed to `client.chat()`.
