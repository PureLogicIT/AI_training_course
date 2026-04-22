# Exercise 3: Multi-Turn Conversational Assistant with Session Management
> Module: Module 3 — LangChain Fundamentals | Difficulty: Hard | Estimated Time: 150–210 minutes

---

## Overview

The module's Example 3 showed a `RunnableWithMessageHistory` conversational chain operating in a terminal REPL. In this exercise you will promote that chain into a full-featured Gradio application with five production-relevant capabilities the terminal demo did not have:

1. **Persistent Gradio Chatbot UI** — conversation history rendered in a `gr.Chatbot` component.
2. **Live history inspector** — a sidebar showing the raw `ChatMessageHistory` messages as formatted JSON, updated after every turn.
3. **Automatic context-window trimming** — `trim_messages()` applied in the history factory so the model never silently loses context.
4. **Named session save/load** — conversation sessions persisted to JSON files on disk, loadable by name.
5. **Chain inspector tab** — displays the LCEL chain graph as ASCII text using `.get_graph().print_ascii()`.

---

## Learning Objectives

By the end of this exercise you will be able to:

1. Wire `RunnableWithMessageHistory` to a Gradio `Chatbot` component using a streaming generator.
2. Implement `trim_messages()` inside the history factory function with correct `strategy`, `token_counter`, `include_system`, and `start_on` arguments.
3. Serialise and deserialise `ChatMessageHistory` to/from JSON for persistent named sessions.
4. Use `chain.get_graph().print_ascii()` to capture and display an LCEL chain's structure.
5. Compose a multi-tab Gradio layout with shared state across tabs.

---

## Prerequisites

- Exercises 1 and 2 completed (Gradio and LangChain installed and working).
- Familiarity with `RunnableWithMessageHistory` and `MessagesPlaceholder` from the module.
- Python 3.11+ with the packages in `requirements.txt` installed.
- Docker Desktop (for the docker-compose bonus step).

---

## Scenario

You are building a developer-facing AI assistant tool for your team. The tool must feel like a real chat product: messages appear one at a time as they stream, the conversation persists across browser refreshes (via named save/load), and a technical sidebar gives power users visibility into what the chain is doing. A separate tab lets users inspect the LCEL chain graph without disturbing the active conversation.

---

## Project Structure

```
Exercise3-ConversationalAssistant/
├── app.py              # Main Gradio application — complete the TODOs
├── history_store.py    # Session persistence helpers — complete the TODOs
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Instructions

### Step 1 — Implement session persistence in `history_store.py`

Open `history_store.py`. You will find two functions with TODOs.

**`save_session(session_id, history, sessions_dir)`**

Serialise a `ChatMessageHistory` to a JSON file at `sessions_dir/{session_id}.json`.

The JSON format should be a list of message dicts:
```json
[
  {"role": "human", "content": "What is a generator?"},
  {"role": "ai", "content": "A generator is..."}
]
```

Map `HumanMessage` → `"human"`, `AIMessage` → `"ai"`, `SystemMessage` → `"system"`.

> Hint: Iterate `history.messages`. Each message has `.content` and a class name. Use `type(msg).__name__` to produce the role string, then lower-case and strip `"message"`:
> `HumanMessage` → `"human"`, `AIMessage` → `"ai"`, `SystemMessage` → `"system"`.

**`load_session(session_id, sessions_dir)`**

Read `sessions_dir/{session_id}.json` and reconstruct a `ChatMessageHistory`. Return `None` if the file does not exist. Map roles back to message classes:
- `"human"` → `HumanMessage`
- `"ai"` → `AIMessage`
- `"system"` → `SystemMessage`

---

### Step 2 — Build the conversational chain in `app.py`

Locate `TODO 2` in `app.py`. Implement `build_chain(model_name)`.

The chain must follow the structure from the module's Section 4:

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])
chain = prompt | llm | StrOutputParser()
```

Return the plain chain (not yet wrapped with history). `RunnableWithMessageHistory` is added in `TODO 3`.

---

### Step 3 — Implement the history factory with trimming

Locate `TODO 3`. Implement `get_history_factory(model_name)`.

This function must return a **closure** — a function that, given a `session_id` string, returns the appropriate `ChatMessageHistory`. The closure captures `model_name` so it can construct the `llm` needed by `trim_messages(token_counter=llm)`.

The inner function must:
1. Look up or create the `ChatMessageHistory` in `_session_store`.
2. If the history has messages, apply `trim_messages()` with:
   - `max_tokens=MAX_HISTORY_TOKENS`
   - `strategy="last"`
   - `token_counter=llm` (a `ChatOllama` instance using `model_name`)
   - `include_system=True`
   - `allow_partial=False`
   - `start_on="human"`
3. Replace `history.messages` with the trimmed list.
4. Return the history object.

> Hint: The closure pattern looks like:
> ```python
> def get_history_factory(model_name):
>     llm_for_counting = ChatOllama(model=model_name, ...)
>     def get_session_history(session_id: str) -> ChatMessageHistory:
>         ...
>     return get_session_history
> ```

---

### Step 4 — Implement the streaming chat handler

Locate `TODO 4`. Implement `chat(user_message, history_list, session_id, model_name)`.

This is the Gradio event handler for the chat input. The function must:

1. Build the LCEL chain with `build_chain(model_name)`.
2. Wrap it with `RunnableWithMessageHistory` using the history factory from `TODO 3`.
3. Stream the response using `chain_with_history.stream({"input": user_message}, config=...)`.
4. Accumulate the streamed chunks and yield the growing `history_list` to Gradio's `Chatbot` component after each chunk.

The `history_list` for Gradio's `Chatbot` is a list of `[user_str, assistant_str]` pairs. When streaming begins, append `[user_message, ""]` to start a new turn, then update the last pair's assistant string as chunks arrive:

```python
history_list = history_list + [[user_message, ""]]
for chunk in chain_with_history.stream(...):
    history_list[-1][1] += chunk
    yield history_list
```

> Hint: The `config` dict for `RunnableWithMessageHistory` must include:
> `{"configurable": {"session_id": session_id}}`

---

### Step 5 — Implement the history inspector update

Locate `TODO 5`. Implement `get_history_json(session_id)`.

This function must format the current `ChatMessageHistory` for `session_id` as a pretty-printed JSON string. Each message should appear as `{"role": "...", "content": "..."}`.

If the session has no history yet, return `"[]"`.

This function is called by Gradio after each chat turn to refresh the sidebar inspector.

---

### Step 6 — Implement save and load handlers

Locate `TODO 6`. Implement `handle_save(session_id)` and `handle_load(session_id)`.

**`handle_save(session_id)`**:
- Call `save_session(session_id, history, SESSIONS_DIR)` from `history_store`.
- Return a status string: `"Session '{session_id}' saved."` or an error message.

**`handle_load(session_id)`**:
- Call `load_session(session_id, SESSIONS_DIR)` from `history_store`.
- If the session file exists, update `_session_store[session_id]` with the loaded history and return the reconstructed `history_list` (as `[[human, ai], ...]` pairs for the Chatbot) plus a status string.
- If the file does not exist, return an unchanged history and `"Session not found."`.

---

### Step 7 — Implement the chain inspector

Locate `TODO 7`. Implement `get_chain_graph(model_name)`.

Call `build_chain(model_name).get_graph().print_ascii()`. Capture the printed output using `io.StringIO` and `contextlib.redirect_stdout`. Return the captured string.

```python
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    build_chain(model_name).get_graph().print_ascii()
return buf.getvalue()
```

---

### Step 8 — Wire the Gradio UI

Locate `TODO 8`. Wire all buttons and inputs to their handlers. The UI skeleton provides all component variables; you must connect them:

| Component | Event | Handler | Inputs | Outputs |
|---|---|---|---|---|
| `submit_btn` | `click` | `chat` | `[msg_input, chatbot, session_id_box, model_dropdown]` | `[chatbot]` |
| `msg_input` | `submit` | `chat` | same as above | `[chatbot]` |
| `chatbot` | `change` | `get_history_json` | `[session_id_box]` | `[history_json_box]` |
| `save_btn` | `click` | `handle_save` | `[session_id_box]` | `[status_box]` |
| `load_btn` | `click` | `handle_load` | `[session_id_box]` | `[chatbot, status_box]` |
| `clear_btn` | `click` | lambda `[]` | `[]` | `[chatbot, history_json_box]` |
| `inspect_btn` (chain tab) | `click` | `get_chain_graph` | `[model_dropdown]` | `[chain_graph_box]` |

After wiring `submit_btn.click`, add a `.then()` call to clear `msg_input`:
```python
submit_btn.click(...).then(fn=lambda: "", outputs=[msg_input])
```

---

### Step 9 — Run and verify

```bash
python app.py
```

Open `http://localhost:7860` and verify:

- [ ] Sending a message streams tokens into the Chatbot component.
- [ ] The history inspector (JSON sidebar) updates after each turn.
- [ ] After 10+ turns, responses remain coherent (trimming is working).
- [ ] Clicking Save writes a `.json` file to `./sessions/`.
- [ ] Clicking Load restores a previously saved session into the Chatbot.
- [ ] The Chain Inspector tab shows the LCEL graph ASCII diagram.

---

### Step 10 — Build and run with docker-compose

```bash
docker-compose up --build
```

Open `http://localhost:7860`. The `docker-compose.yml` starts both the app container and an Ollama container so no local Ollama installation is required.

> Note: On first run, the Ollama container must pull the model. This may take several minutes depending on network speed.

---

## Expected Outcome

- [ ] `python app.py` starts without errors.
- [ ] Multi-turn chat works and history is maintained across turns within a session.
- [ ] The history inspector shows correctly formatted JSON after each turn.
- [ ] `trim_messages` prevents the history from growing beyond `MAX_HISTORY_TOKENS`.
- [ ] Save writes `sessions/{session_id}.json`; Load restores it correctly.
- [ ] The Chain Inspector tab shows a non-empty ASCII diagram.
- [ ] `docker-compose up --build` starts all services; the app is reachable at port 7860.
- [ ] The app container passes its health check.

---

## Hints

- If streaming does not update the Chatbot incrementally, confirm the handler is a generator (`yield` not `return`). Gradio `Chatbot` supports streaming via generator functions.
- The `trim_messages` call in the history factory modifies the `history.messages` list. If the model's responses become incoherent after many turns, add a `print(f"[trim] {len(before)} -> {len(after)} messages")` log to verify trimming is firing.
- `ChatMessageHistory` stores messages in `.messages` as a Python list. You can iterate and inspect it directly in debugging.
- For the save/load format: `HumanMessage.__name__` is `"HumanMessage"`. Strip `"message"` (case-insensitive) to get `"human"`, or use an explicit `isinstance` check — either approach is acceptable.
- The `sessions/` directory must exist before saving. Use `pathlib.Path(SESSIONS_DIR).mkdir(parents=True, exist_ok=True)` in the startup code.
- `io.StringIO` + `contextlib.redirect_stdout` is the standard way to capture output from functions that print to stdout (like `.print_ascii()`).

---

## Bonus Challenges

1. Add a `gr.Slider` for `MAX_HISTORY_TOKENS` so the user can tune the trim threshold live.
2. Add a message count badge next to the session ID box showing how many messages are in the current session.
3. Replace the JSON file persistence with `SQLChatMessageHistory` from `langchain-community` (requires SQLite — already available in Python's standard library).
4. Add a "New Session" button that generates a UUID session ID automatically so users never need to type one.
