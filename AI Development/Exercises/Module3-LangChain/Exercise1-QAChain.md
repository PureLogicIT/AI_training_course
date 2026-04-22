# Exercise 1: LangChain LCEL Q&A Chain with Gradio
> Module: Module 3 — LangChain Fundamentals | Difficulty: Easy | Estimated Time: 60–90 minutes

---

## Overview

In the module's hands-on examples, you ran Q&A chains from the command line. In this exercise you will wire the same LCEL pipeline — `ChatPromptTemplate` → `ChatOllama` → `StrOutputParser` — into a Gradio web application so that a user can interact with it through a browser.

You will add two features the command-line example did not have: a live-editable system prompt that takes effect without restarting the app, and a dropdown that lets the user switch between locally available Ollama models mid-session. Both changes are handled purely by rebuilding or reconfiguring the LCEL chain at request time — no global state mutation.

---

## Learning Objectives

By the end of this exercise you will be able to:

1. Compose a three-step LCEL chain (`ChatPromptTemplate | ChatOllama | StrOutputParser`) inside a Gradio event handler.
2. Pass user-controlled values (system prompt, model name) as chain construction parameters rather than hard-coded constants.
3. Stream LCEL chain output token-by-token into a Gradio `Textbox` using a Python generator.
4. Package a Gradio application in a Docker image using `python:3.11-slim` with a non-root user and a health check.

---

## Prerequisites

- Ollama is installed and running (`ollama serve`).
- At least one model is pulled: `ollama pull llama3.2` (recommended) or `ollama pull phi4-mini`.
- Python 3.11+ virtual environment with `pip` available.
- Docker Desktop (for the Dockerfile bonus step).

---

## Scenario

You are building a developer-facing internal tool that lets teammates query a locally running LLM without needing to write Python. The tool must allow each user to supply their own system prompt (different teams use different personas) and select which model to use from those already pulled on the machine. Responses must stream to the browser — users should see the first token within two seconds.

---

## Project Structure

```
Exercise1-QAChain/
├── app.py              # Main Gradio application — you implement the TODOs here
├── requirements.txt    # Pinned dependencies
├── Dockerfile          # Container definition
└── README.md           # Setup and run instructions
```

---

## Instructions

### Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

Confirm Ollama is reachable before starting the app:

```bash
python -c "import httpx; httpx.get('http://localhost:11434', timeout=2)"
```

If this raises a `ConnectError`, start Ollama with `ollama serve`.

---

### Step 2 — Build the LCEL chain inside the handler

Open `app.py`. Locate `TODO 1` and `TODO 2`.

The `answer_question` function receives three arguments from Gradio: `system_prompt`, `user_message`, and `model_name`. You must:

1. (`TODO 1`) Instantiate a `ChatOllama` with the caller-supplied `model_name`, `temperature=0.7`, and `num_ctx=4096`.
2. (`TODO 2`) Compose the LCEL chain:
   ```
   ChatPromptTemplate.from_messages([
       ("system", system_prompt),
       ("human", "{question}"),
   ]) | llm | StrOutputParser()
   ```

The chain is created fresh per request so the system prompt and model selection take effect immediately without requiring an app restart.

> Hint: Both `ChatOllama` and `ChatPromptTemplate` are `Runnable` objects. The `|` operator connects them because LCEL defines `__or__` on all `Runnable` instances.

---

### Step 3 — Stream the response into the Gradio Textbox

Locate `TODO 3`.

`chain.stream({"question": user_message})` is a synchronous generator that yields `str` chunks. To display them incrementally in Gradio you must yield an ever-growing string from your own generator — Gradio replaces the textbox content with each yielded value.

Implement the accumulation loop:

```python
accumulated = ""
for chunk in chain.stream({"question": user_message}):
    accumulated += chunk
    yield accumulated
```

> Hint: Gradio interprets a generator return from an event handler as a streaming update. Each `yield` replaces the current textbox value. If you `return` a single string instead, the entire response appears at once after generation completes.

---

### Step 4 — Wire the Gradio UI components

Locate `TODO 4`.

Connect the `Submit` button's `click` event to `answer_question`:
- **Inputs:** `[system_prompt_box, user_input_box, model_dropdown]`
- **Outputs:** `[output_box]`

Also connect the `Clear` button to reset both `user_input_box` and `output_box` to empty strings.

> Hint: Use `gr.Button.click(fn=..., inputs=[...], outputs=[...])`. For streaming, Gradio requires that the function is a generator (uses `yield`). If the output is not streaming, verify that `answer_question` contains a `yield` statement.

---

### Step 5 — Run the app

```bash
python app.py
```

Open `http://localhost:7860` in your browser. Test the following:

- [ ] Enter a system prompt, type a question, and click **Submit** — the response streams token-by-token into the output box.
- [ ] Change the system prompt to `"You are a pirate. Respond only in pirate speak."` and re-submit — the new persona is applied immediately.
- [ ] Select a different model from the dropdown and re-submit — the new model is used for the next response.
- [ ] Click **Clear** — both the input and output boxes are emptied.

---

### Step 6 — Build and run with Docker

```bash
docker build -t qa-chain-app:1.0 .
docker run --rm -p 7860:7860 --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  qa-chain-app:1.0
```

Open `http://localhost:7860` and verify the app works inside the container.

Check the health endpoint:

```bash
docker inspect --format='{{json .State.Health}}' $(docker ps -lq)
```

Expected: `"Status":"healthy"`.

---

## Expected Outcome

- [ ] `python app.py` starts a Gradio server on port 7860 with no errors.
- [ ] Submitting a question produces a streaming response visible in the output box.
- [ ] Changing the system prompt text box and re-submitting uses the new system prompt.
- [ ] Selecting a different model from the dropdown and re-submitting uses that model.
- [ ] The Clear button resets both input and output boxes.
- [ ] `docker build -t qa-chain-app:1.0 .` completes without errors.
- [ ] The running container passes its health check (`Status: healthy`).

---

## Hints

- If the response appears all at once instead of streaming, the event handler is not a generator. Confirm it has a `yield` statement (not just `return`).
- If you get `ConnectionRefusedError` inside Docker, the container cannot reach the host's Ollama server. Pass `OLLAMA_HOST=http://host.docker.internal:11434` as an environment variable and use it when constructing `ChatOllama`.
- If the model dropdown is empty at startup, check that at least one model is listed by `ollama list`. The starter code populates the dropdown from `ollama list` output.
- `temperature=0.7` is intentionally set inside the handler so each call uses the current value — placing it on a module-level `llm` object would cache it.

---

## Bonus Challenges

1. Add a `gr.Slider` for temperature (range 0.0 – 1.0, step 0.05, default 0.7) and pass it to `ChatOllama`.
2. Add a `gr.Number` for `num_predict` (max tokens to generate) and wire it the same way.
3. Display the LCEL chain graph (from `chain.get_graph().print_ascii()`) in a `gr.Code` block that updates each time the model or system prompt changes.
