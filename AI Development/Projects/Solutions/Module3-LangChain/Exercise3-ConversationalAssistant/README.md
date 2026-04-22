# Exercise 3 - Multi-Turn Conversational Assistant (Solution)

Complete reference solution for Exercise 3.

## Running the Solution

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:7860.

## Docker Compose

```bash
docker-compose up --build
```

Pull the model inside the Ollama container on first run:

```bash
docker exec -it ollama ollama pull llama3.2
```

## What the Solution Demonstrates

- RunnableWithMessageHistory wired to a Gradio Chatbot with streaming.
- trim_messages() inside the history factory to prevent context window overflow.
- Named session persistence: save/load ChatMessageHistory to JSON files on disk.
- RunnableParallel-free architecture: history is managed by the wrapper, not manually.
- get_graph().print_ascii() captured via io.StringIO and displayed in a Chain Inspector tab.
- Multi-tab Gradio layout with shared model_dropdown state across tabs.
