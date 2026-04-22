# Exercise 3: Multi-Turn Model Comparison App

> Module: Module 1 — Working with Local Models | Difficulty: Hard | Estimated Time: 3–4 hours

## Overview

You will build a **production-grade multi-turn chat application** in Gradio that goes well beyond a basic chatbot. The app supports switching between multiple locally available Ollama models mid-conversation, displays real-time token usage statistics (total tokens and generation speed in tokens/sec) for every response, saves and loads full conversation histories as JSON files, and offers a **compare mode** that sends the same message to two models simultaneously and displays both responses side by side.

This exercise integrates nearly every concept from Module 1 into a single cohesive application.

## Learning Objectives

After completing this exercise you will be able to:

- Manage multi-turn conversation state across model switches
- Measure and display tokens/sec for streaming Ollama responses using response metadata
- Serialize and deserialize conversation history to/from JSON
- Run two concurrent Ollama streaming requests using Python's `concurrent.futures`
- Architect a non-trivial Gradio `Blocks` UI with tabs, conditional visibility, and state components

## Prerequisites

- Ollama installed and running with at least two models pulled
  (e.g., `ollama pull llama3.2` and `ollama pull phi4-mini`)
- Python 3.11 with `gradio` and `ollama` installed
- Docker Desktop for the Docker portion

## Scenario

Your AI research team evaluates several small local models for different tasks. You need a shared tool where any team member can:

1. Chat with whichever model is most appropriate for the current topic — and switch models without losing the conversation thread
2. See at a glance how fast each model generates text (tokens/sec), which is a key selection criterion on CPU-only hardware
3. Archive interesting conversations to JSON so they can be reviewed later or replayed
4. Compare two models' answers to the same question side by side, without running two separate terminals

---

## Directory Structure

```
Exercise3-ModelComparison/
├── app.py              # Main Gradio application
├── conversation.py     # ConversationManager class
├── inference.py        # Streaming helpers + compare mode
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Instructions

### Step 1 — Implement `ConversationManager` in `conversation.py`

The `ConversationManager` class owns the canonical message history for the session. Implement these methods:

**`__init__(system_prompt)`**
Store the system prompt and initialise an empty messages list. The system message is always position 0 when non-empty.

**`add_user(text)`**
Append `{"role": "user", "content": text}` to messages.

**`add_assistant(text, model_name)`**
Append `{"role": "assistant", "content": text, "model": model_name}` to messages. The extra `"model"` key is non-standard — Ollama ignores unknown keys, so this is safe to include for display purposes.

**`get_ollama_messages()`**
Return a copy of the messages list with the `"model"` key stripped from all assistant entries. This is what gets sent to `ollama.chat()`.

**`to_gradio_history()`**
Convert messages to the `[[user_text, assistant_text], ...]` format Gradio's Chatbot component expects. System messages are excluded. Consecutive user messages without an assistant reply between them should be paired with `None`.

**`save_to_json(filepath)`**
Write the full messages list (including the `"model"` key) to `filepath` as indented JSON. Raise `IOError` with a useful message if the write fails.

**`load_from_json(filepath)`**
Load a previously saved JSON file and replace the current messages list. Validate that the file contains a list of dicts, each with at least `"role"` and `"content"` keys. Raise `ValueError` with a clear message if validation fails.

**`clear(keep_system=True)`**
Reset the messages list. If `keep_system=True` and a system prompt was set, keep the system message.

**`turn_count` (property)**
Return the number of completed user turns (messages with `role == "user"`).

> Hint: `json.dumps(data, indent=2, ensure_ascii=False)` for pretty JSON output.

### Step 2 — Implement streaming helpers in `inference.py`

**`stream_response(client, model, messages, options)`**
Generator function. Call `client.chat()` with `stream=True`. For each chunk, yield the token string (`chunk["message"]["content"]`). After the stream is exhausted, also yield a final sentinel: a dict `{"done": True, "stats": {...}}` where `stats` contains:

- `total_tokens`: `chunk.get("eval_count", 0)` from the final chunk
- `tokens_per_sec`: `chunk.get("eval_count", 0) / chunk.get("eval_duration", 1) * 1e9` (Ollama reports duration in nanoseconds)

> Hint: The final chunk from Ollama has `chunk.get("done") == True`. Check for this to capture the stats. Regular text chunks have `done == False`.

**`compare_responses(client, model_a, model_b, messages, options)`**
Run both models **concurrently** using `concurrent.futures.ThreadPoolExecutor`. Each thread should call a non-streaming `client.chat()` and return `(response_text, stats_dict)`. Return a tuple `(result_a, result_b)` where each result is `(text, stats)`.

> Hint: Use `executor.submit()` for both calls and then call `.result()` on each future. Wrap in `try/except` so one model failing does not crash the other.

### Step 3 — Build the main chat tab in `app.py`

The main tab ("Chat") should contain:

- A `gr.Dropdown` for model selection populated from `client.list()`
- A `gr.Chatbot` component displaying the conversation
- A `gr.Textbox` for message input (submit on Enter)
- A `gr.Markdown` or `gr.HTML` area that shows stats for the last response:
  `"Last response: {total_tokens} tokens at {tokens_per_sec:.1f} tok/s"`
- A `gr.State` holding the `ConversationManager` instance

Implement `send_message(user_text, model, conv_manager)` as a generator:

1. Add the user message to `conv_manager`.
2. Start `stream_response()` from `inference.py`.
3. Yield intermediate Gradio updates as tokens arrive (update the Chatbot with the partial assistant text on each token).
4. When the `done` sentinel arrives, finalise the assistant message in `conv_manager` and yield the stats string.

> Hint: Gradio generators should yield tuples matching the output list. For three outputs (chatbot, stats, conv_state), yield `(history, stats_text, conv_manager)` on each iteration.

### Step 4 — Implement model switching

Implement `switch_model(new_model, conv_manager)`. When the user changes the model mid-conversation:

- Do **not** clear the conversation history.
- Add a visible marker to the chat — append a special assistant message like `"[Switched to model: {new_model}]"` using `conv_manager.add_assistant(...)` with the new model name.
- Return the updated Gradio history and the updated `conv_manager`.

Wire this to the dropdown's `.change()` event.

> Rationale: The conversation history sent to the new model will include all prior turns regardless of which model produced them. The switch marker is purely cosmetic for the UI.

### Step 5 — Save and Load conversation history

Add a second tab ("Save / Load") containing:

- A `gr.File` component for uploading a previously saved `.json` file
- A `gr.Textbox` for entering a save path (default: `"conversation.json"`)
- A **Save** button and a **Load** button
- A `gr.Markdown` status area that shows success or error messages

Implement:

- `save_conversation(filepath, conv_manager)`: calls `conv_manager.save_to_json(filepath)`, returns a status string.
- `load_conversation(file_obj, conv_manager)`: reads the uploaded file path from `file_obj.name`, calls `conv_manager.load_from_json(...)`, returns `(updated_gradio_history, updated_conv_manager, status_string)`.

### Step 6 — Compare mode

Add a third tab ("Compare"). It should contain:

- Two `gr.Dropdown` components, one for Model A and one for Model B
- A `gr.Textbox` for the prompt
- A **Compare** button
- Two side-by-side `gr.Textbox` output areas (Model A output | Model B output)
- Two `gr.Markdown` areas below the outputs for stats (tokens and tok/s per model)

Implement `run_compare(prompt, model_a, model_b)`:

1. Build a minimal messages list: `[system_prompt_dict, user_dict]`.
2. Call `compare_responses()` from `inference.py` with both model names.
3. Return `(text_a, text_b, stats_a_str, stats_b_str)`.

> Hint: The compare tab should use its own independent messages list — it does not share history with the main chat tab.

### Step 7 — Complete the Dockerfile and docker-compose.yml

**Dockerfile**: python:3.11-slim base, non-root user, `pip install` from requirements.txt, health check on port 7860, `CMD ["python", "app.py"]`.

**docker-compose.yml**: Define two services:
- `ollama`: uses image `ollama/ollama:0.6.0`, exposes port `11434`, mounts a named volume `ollama_data` at `/root/.ollama`
- `app`: builds from the local Dockerfile, depends on `ollama`, sets `OLLAMA_HOST=http://ollama:11434`, exposes port `7860`

---

## Expected Outcome

- [ ] The Chat tab starts a conversation, streams responses token-by-token into the Chatbot
- [ ] The stats area shows total tokens and tok/s after each response
- [ ] Changing the model dropdown mid-conversation inserts a `[Switched to model: ...]` marker in the chat and subsequent responses come from the new model
- [ ] Clicking Save writes a valid JSON file to the specified path; reloading the file restores the full conversation in the Chatbot
- [ ] The Compare tab sends the same prompt to two models concurrently and displays both responses side by side within a few seconds of each other
- [ ] The Compare stats show tok/s for each model independently
- [ ] `docker compose up --build` starts both the app and Ollama containers; the UI is accessible at http://localhost:7860
- [ ] The health check passes (`docker inspect` shows `healthy` after startup)

---

## Bonus Challenges

1. Add a **context warning** beneath the chat: when the estimated token count in `conv_manager` exceeds 80 % of 4096, display a yellow warning `gr.Markdown` reminding the user to start a new session or clear history.
2. Add a **"Summarise and compress"** button that sends the current history to the active model with a compression prompt ("Summarise this conversation in bullet points") and replaces the middle turns with the summary — preserving the first user turn and the summary as a fake assistant turn.
3. In compare mode, add a third column where a third model (or the same model with different temperature) runs simultaneously, making it a three-way comparison.
