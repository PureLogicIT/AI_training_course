# Module 1: Working with Local Models
> Subject: AI Development | Difficulty: Beginner-Intermediate | Estimated Time: 225 minutes

## Objective

After completing this module, you will be able to explain how large language models generate text at a conceptual level and understand why inference parameters change model behaviour, use the Ollama Python SDK (`ollama` 0.6+) to send single-turn and multi-turn chat requests both synchronously and with streaming, load a GGUF model file directly with `llama-cpp-python` (`0.3+`) and configure its key constructor parameters, write correctly structured prompts that respect each model family's chat template, tune parameters such as `temperature`, `top_p`, `top_k`, `min_p`, `seed`, `repeat_penalty`, and `num_ctx` with intention, implement streaming output for better user experience, choose an appropriate model for a given task, and build a complete multi-turn chat loop that runs against either backend.

## Prerequisites

- Completed **Module 0: Setup & Local AI Stack** — Ollama is installed and running, `llama-cpp-python` is installed, and your Python virtual environment contains the `ollama` package
- Python 3.10 or later
- At least one model pulled via Ollama (e.g., `ollama pull llama3.2`) and at least one GGUF file downloaded to your local machine (the Module 0 examples download `Llama-3.2-3B-Instruct-Q4_K_M.gguf`)
- Comfort with Python functions, loops, lists, and dictionaries
- No prior experience with AI inference APIs is required

## Key Concepts

### How LLMs Generate Text

Before writing a single line of code it is worth building a mental model of what is actually happening when you call a local LLM. Getting this wrong leads to frustration when outputs are not what you expect.

**Tokens, Not Words**

Language models do not read or produce words — they operate on *tokens*. A token is a chunk of text produced by a trained tokenizer. Common English words are often single tokens (`hello`, `world`), but uncommon words, names, or code may be split across several tokens (`llamacpp` might be three tokens). A rough rule of thumb is that 100 tokens corresponds to about 75 words of English prose, though this varies substantially by language and content type — code and JSON are typically more token-dense than prose.

This matters for two concrete reasons:
1. Model context limits are expressed in tokens, not words. A model with a 4096-token context can hold roughly 3000 words of combined prompt and response.
2. Parameters like `max_tokens` and `num_predict` count tokens, not words. Setting `max_tokens=50` may produce only a sentence or two.

**Next-Token Prediction**

Every modern LLM has one job: given a sequence of tokens, predict the probability of each possible next token. The model does this by passing the input through many layers of neural network operations (the transformer architecture). The output is a vector of scores — one score per token in the model's vocabulary — called *logits*.

These logits are converted to probabilities using a softmax function. The model then *samples* from this probability distribution to pick the next token. The chosen token is appended to the input, and the process repeats until a stop condition is met (end-of-sequence token, stop string, or `max_tokens` limit). This one-token-at-a-time generation is why streaming is natural for LLMs — tokens genuinely arrive sequentially.

**Temperature and Sampling**

The sampling step is where you gain control. Before sampling, the logit scores are divided by the *temperature* value:

- **Temperature = 0**: The model always picks the single highest-probability token. Output is fully deterministic (given a fixed seed).
- **Temperature = 1.0**: Probabilities are used as-is. The model samples naturally from the distribution.
- **Temperature > 1.0**: Lower-probability tokens become relatively more likely. Output becomes more diverse and less predictable, often more creative but also less coherent.

This is why the same prompt can produce completely different outputs on successive calls (unless you fix the `seed`). The model is sampling from a probability distribution at each step. Even with identical input and parameters, a different random seed produces a different token sequence.

**The Practical Takeaway**

For tasks that require correctness — code generation, factual recall, structured output — lower temperatures (0.0–0.3) and a fixed seed produce more reliable, reproducible results. For creative tasks — storytelling, brainstorming, open-ended chat — higher temperatures (0.7–1.0) produce more varied and interesting outputs.

---

### The Ollama Python SDK

Ollama provides an official Python library (`pip install ollama`, current version 0.6.x as of 2026) that wraps its local REST API. It is the simplest way to query a locally running Ollama server from Python.

**Installation**

```bash
pip install ollama
```

Verify that the Ollama server is running before making any calls. If Ollama was installed via the automated install script in Module 0, it should already be running as a systemd service. If not:

```bash
ollama serve   # run this in a separate terminal if not already running as a service
```

**`ollama.chat()` vs `ollama.generate()`**

The library exposes two primary generation functions:

| Function | Input | Best For |
|---|---|---|
| `ollama.chat()` | A list of `messages` dicts with `role` and `content` | Multi-turn conversation, instruction following |
| `ollama.generate()` | A single `prompt` string | Simple completions, raw text continuation |

For almost all practical use cases you will use `ollama.chat()`. It handles the message history structure that instruct and chat models expect. `ollama.generate()` is useful when you want to complete a raw text string without any role-based formatting, or when working with base (non-instruct) models.

**The Message Format**

Messages are plain Python dictionaries with two required keys:

```python
{"role": "system",    "content": "You are a helpful assistant."}
{"role": "user",      "content": "What is the capital of France?"}
{"role": "assistant", "content": "The capital of France is Paris."}
```

Valid roles are `"system"`, `"user"`, and `"assistant"`. A conversation is a list of these dicts in chronological order. The system message, when present, always comes first. Multi-turn conversations simply extend the list with alternating user and assistant messages.

**Synchronous Chat**

```python
import ollama

response = ollama.chat(
    model="llama3.2",
    messages=[
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user",   "content": "Name the three primary colours."},
    ],
)

# Both access patterns work — dict-style and attribute-style
print(response["message"]["content"])
print(response.message.content)  # equivalent
```

The response is a typed object that also supports dictionary-style access. The generated text lives at `response.message.content` (or `response["message"]["content"]`).

**Streaming Chat**

Add `stream=True` to receive tokens as they are generated:

```python
import ollama

stream = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Count slowly from 1 to 5."}],
    stream=True,
)

for chunk in stream:
    print(chunk["message"]["content"], end="", flush=True)
print()  # newline after stream ends
```

Each `chunk` has the same structure as a full response, but `chunk["message"]["content"]` contains only the tokens generated since the previous chunk — typically one to a few tokens. Use `end=""` and `flush=True` to print tokens as they arrive without buffering.

**Collecting a Full Response from a Stream**

When you need both streaming output and the complete text for further processing:

```python
import ollama

collected = []
stream = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Explain recursion briefly."}],
    stream=True,
)

for chunk in stream:
    token = chunk["message"]["content"]
    print(token, end="", flush=True)
    collected.append(token)

print()
full_response = "".join(collected)
```

**The `options` Dictionary**

Both `ollama.chat()` and `ollama.generate()` accept an `options` keyword argument — a dictionary of inference parameters:

```python
response = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Write a haiku about fog."}],
    options={
        "temperature": 0.9,
        "top_p": 0.95,
        "top_k": 40,
        "min_p": 0.05,
        "num_ctx": 4096,
        "seed": 42,
        "stop": ["\n\n"],
        "repeat_penalty": 1.1,
        "repeat_last_n": 64,
        "num_predict": 200,
    },
)
```

All keys in the `options` dict are optional. Unspecified parameters use Ollama's defaults. The full parameter reference is covered in the **Key Model Parameters** section below.

**Using `ollama.Client` for Custom Hosts**

By default, the library connects to `http://localhost:11434`. If your Ollama server runs on a different host or port — for example, on another machine on your local network — instantiate a `Client` directly:

```python
from ollama import Client

client = Client(host="http://192.168.1.50:11434")

response = client.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello from a remote client."}],
)
print(response.message.content)
```

The `Client` instance exposes the same methods as the module-level functions (`chat`, `generate`, `list`, `pull`, etc.). An `AsyncClient` is also available for use in async contexts:

```python
import asyncio
from ollama import AsyncClient

async def main():
    client = AsyncClient()
    async for chunk in await client.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": "Hello!"}],
        stream=True,
    ):
        print(chunk["message"]["content"], end="", flush=True)
    print()

asyncio.run(main())
```

**Error Handling**

```python
import ollama

try:
    response = ollama.chat(
        model="nonexistent-model",
        messages=[{"role": "user", "content": "Hello"}],
    )
except ollama.ResponseError as e:
    print(f"Ollama error {e.status_code}: {e.error}")
    if e.status_code == 404:
        print("Model not found. Run: ollama pull <model-name>")
```

---

### llama-cpp-python: Python Bindings for llama.cpp

`llama-cpp-python` (current version 0.3.x) gives you direct, fine-grained control over the llama.cpp inference engine from Python. Unlike Ollama (which runs as a separate server process), `llama-cpp-python` loads the model directly into your Python process's memory. This is useful when you want lower-level control, when you are embedding inference into a library, or when you are running in an environment where a separate server process is impractical.

**Installation**

CPU-only installation (works everywhere, builds llama.cpp from source during install):

```bash
pip install llama-cpp-python
```

With CUDA GPU acceleration using a pre-built wheel (fastest path, no compilation needed):

```bash
# Replace cu121 with your installed CUDA version: cu118, cu121, cu122, cu123, cu124, cu125
pip install llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

If a pre-built wheel is not available for your exact CUDA version, build from source instead:

```bash
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --no-cache-dir
```

> Note: `CMAKE_ARGS="-DGGML_CUDA=on"` replaced the older `-DLLAMA_CUDA=ON` flag. The build compiles llama.cpp with CUDA support during `pip install` and requires `nvcc` (the CUDA compiler) on your `PATH`. Compilation takes 5–15 minutes.

**Loading a GGUF Model**

```python
from llama_cpp import Llama

llm = Llama(
    model_path="/path/to/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
    n_ctx=4096,
    n_threads=6,
    n_gpu_layers=0,
    verbose=False,
)
```

**Key Constructor Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `model_path` | `str` | — | Absolute or relative path to the `.gguf` file |
| `n_ctx` | `int` | `512` | Context window size in tokens. Must not exceed the model's maximum. Larger values consume more RAM for the KV cache. |
| `n_threads` | `int` | System CPU count | Number of CPU threads for computation. Set to your physical core count (not hyperthreads) for best performance. |
| `n_gpu_layers` | `int` | `0` | Transformer layers to offload to GPU. `0` = CPU only. `-1` = offload all layers. Set a specific number for partial GPU offloading when VRAM is limited. |
| `verbose` | `bool` | `True` | If `True`, prints llama.cpp's internal logging to stderr. Always set to `False` in code others will run. |
| `chat_format` | `str` | Auto-detected | Manually specify the chat template: `"llama-3"`, `"mistral"`, `"chatml"`, etc. Most GGUF files embed their chat template; leave unset unless the model is not selecting the correct format. |
| `seed` | `int` | `-1` (random) | Global random seed for reproducibility. Set at construction time to affect all generations from this instance. |

**Basic Text Completion with `llm()`**

Calling the `Llama` instance directly runs raw text completion — no chat template is applied:

```python
output = llm(
    "The three laws of thermodynamics are:",
    max_tokens=128,
    stop=["\n\n"],
    echo=False,
)

print(output["choices"][0]["text"])
```

The `echo=False` parameter tells the library not to include the input prompt in the output text. The response is a dict with a `choices` list; generated text is at `output["choices"][0]["text"]`.

**Chat Completion with `create_chat_completion()`**

For instruct and chat models, use `create_chat_completion()`. This applies the correct chat template automatically and returns a response in the same shape as the OpenAI Chat Completions API:

```python
response = llm.create_chat_completion(
    messages=[
        {"role": "system", "content": "You are a helpful Python tutor."},
        {"role": "user",   "content": "What does the `*args` syntax do?"},
    ],
    max_tokens=256,
    temperature=0.7,
    top_p=0.95,
    repeat_penalty=1.1,
)

print(response["choices"][0]["message"]["content"])
```

**Streaming with Generators**

Pass `stream=True` to receive a generator that yields completion chunks:

```python
stream = llm.create_chat_completion(
    messages=[{"role": "user", "content": "List five Python best practices."}],
    max_tokens=300,
    temperature=0.7,
    stream=True,
)

for chunk in stream:
    delta = chunk["choices"][0]["delta"]
    if "content" in delta:
        print(delta["content"], end="", flush=True)
print()
```

Each chunk's generated text fragment is nested at `chunk["choices"][0]["delta"]["content"]`. The `delta` dict may not always contain a `"content"` key — the first chunk typically carries only role information — so always guard with `if "content" in delta`.

---

### Prompt Engineering for Local Models

**System Prompts**

A system prompt is a message with `role: "system"` that precedes the conversation. It establishes the model's persona, constraints, and task context. It is not shown to the end user. A well-written system prompt dramatically improves output quality for local models, which tend to be more sensitive to system prompt content than large frontier cloud models.

```python
messages = [
    {
        "role": "system",
        "content": (
            "You are a senior Python engineer. "
            "Give concise, correct answers with code examples when relevant. "
            "Do not apologise or add unnecessary filler."
        ),
    },
    {"role": "user", "content": "How do I read a JSON file in Python?"},
]
```

**User/Assistant Turn Structure**

Multi-turn conversations require you to maintain the full message history yourself. After each assistant response, append both the user's message and the model's reply to your messages list before sending the next request:

```python
messages = [{"role": "system", "content": "You are a helpful assistant."}]

# Turn 1
messages.append({"role": "user", "content": "What is Python?"})
response = ollama.chat(model="llama3.2", messages=messages)
assistant_reply = response.message.content
messages.append({"role": "assistant", "content": assistant_reply})

# Turn 2 — model now has full context from Turn 1
messages.append({"role": "user", "content": "What is it used for?"})
response = ollama.chat(model="llama3.2", messages=messages)
```

This is critical. If you only send the latest user message without the history, the model has no memory of the prior conversation.

**Chat Templates and Why They Matter for Local Models**

Every chat/instruct model was fine-tuned with a specific prompt format baked into its weights. This format — the *chat template* — defines the special tokens that separate system prompts, user turns, and assistant turns. Using the wrong format causes the model to perform poorly, ignore instructions, or produce garbled output.

The three most common formats you will encounter:

*Llama 3 format* (used by Meta's Llama 3.x and Llama 4 families):

```
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are a helpful assistant.<|eot_id|><|start_header_id|>user<|end_header_id|>

Hello!<|eot_id|><|start_header_id|>assistant<|end_header_id|>
```

*Mistral format* (used by Mistral 7B and variants):

```
[INST] You are a helpful assistant.

Hello! [/INST] Hi, how can I help?</s>[INST] Next question [/INST]
```

*ChatML format* (used by Qwen, Phi-4, and many fine-tuned models):

```
<|im_start|>system
You are a helpful assistant.<|im_end|>
<|im_start|>user
Hello!<|im_end|>
<|im_start|>assistant
Hi! How can I help you today?<|im_end|>
```

**The good news**: Both Ollama and `llama-cpp-python` read the chat template embedded in the GGUF file's metadata and apply it automatically when you use `ollama.chat()` or `llm.create_chat_completion()`. You do not need to manually construct these strings. The danger arises when you use `ollama.generate()` or `llm()` (raw completion) — in those cases, no template is applied, and you must format the prompt yourself if you are using an instruct model.

**Few-Shot Prompting**

Few-shot prompting provides the model with one or more examples of the desired input/output pattern before the actual request. It is particularly effective for structured output tasks where the format must be exact:

```python
messages = [
    {
        "role": "system",
        "content": "Extract the city and country from text. Return JSON only.",
    },
    {"role": "user",      "content": "I live in Berlin."},
    {"role": "assistant", "content": '{"city": "Berlin", "country": "Germany"}'},
    {"role": "user",      "content": "She moved to Osaka last year."},
    {"role": "assistant", "content": '{"city": "Osaka", "country": "Japan"}'},
    {"role": "user",      "content": "Our office is in São Paulo."},
]
```

Each example pair trains the model's in-context behaviour for the duration of that request. Examples consume tokens from your context window, so balance example count against available context.

**Common Prompt Pitfalls with Local Models**

- **Using raw completion for instruct models.** If you call `ollama.generate()` or `llm()` with a bare question string against an instruct model, you may get poor results because the model expects special role tokens surrounding the question. Use `ollama.chat()` or `llm.create_chat_completion()` instead.
- **Skipping the system prompt.** Local models benefit more from explicit system prompts than frontier models do. Without one, the model's behaviour is often unfocused and generic.
- **Cramming all context into one enormous message.** Break long instructions into clearly separated parts within the system prompt. Very long system prompts can push the useful conversation into the middle of the context window, leaving less room for the response.
- **Assuming the model remembers previous Python sessions.** Local models have no persistent memory. Every new Python process or `Llama()` instance starts from scratch.

---

### Key Model Parameters

These parameters are available in both Ollama's `options` dict and as direct keyword arguments to `llama-cpp-python`'s completion methods.

**`temperature`**

Controls randomness during token sampling. Range: `0.0` to `2.0` (practical range: `0.0` to `1.2`). Ollama default: `0.8`.

| Value | Effect | Use When |
|---|---|---|
| `0.0` | Fully deterministic — always picks the top token | Code generation, structured output, factual Q&A |
| `0.3` | Low creativity, high reliability | Summarisation, extraction, classification |
| `0.7` | Balanced (good general default) | Instruction following, explanations |
| `1.0` | Natural distribution sampling | Open conversation, moderate creativity |
| `1.2+` | High creativity, lower coherence | Brainstorming, creative writing |

Setting `temperature=0` is the single most effective change for making model output reliable and reproducible for code or structured tasks.

**`top_p` (Nucleus Sampling)**

After temperature scaling, the model's vocabulary is sorted by probability. `top_p` defines the cumulative probability threshold: only tokens that together account for the top `top_p` fraction of probability mass are eligible for sampling. All other tokens are excluded before the random draw. Ollama default: `0.9`.

- `top_p=1.0`: No filtering — the full vocabulary is eligible.
- `top_p=0.9`: Excludes the long tail of very unlikely tokens.
- `top_p=0.5`: Only the highest-probability tokens remain in the pool.

The general recommendation: adjust `temperature` *or* `top_p` for a given task, not both simultaneously, as their effects compound in ways that are difficult to reason about.

**`top_k`**

A simpler alternative to `top_p`. Instead of a probability threshold, `top_k` directly limits the candidate pool to the `k` most probable tokens at each step. Ollama default: `40`.

- `top_k=1`: Equivalent to greedy (deterministic) sampling.
- `top_k=40`: Good general default.
- `top_k=100`: Larger pool, more diversity.

`top_k` is applied first when both `top_k` and `top_p` are set: the vocabulary is first trimmed to the top-k tokens, then nucleus sampling trims further by probability threshold.

**`min_p`**

A more recent sampling parameter that sets a minimum probability threshold *relative to the most probable token*. A token is excluded if its probability is less than `min_p × (probability of most likely token)`. Ollama default: `0.0` (disabled).

```python
options={"temperature": 0.8, "min_p": 0.05}
```

`min_p` is particularly effective at preventing the model from picking very unlikely tokens at high temperatures, while still preserving more diversity than a fixed `top_k`. It can be used alongside `top_p` or as a standalone alternative to `top_k`.

**`num_ctx` / `n_ctx` (Context Window)**

Defines the maximum number of tokens the model processes at once — the combined length of the input (system prompt + history + user message) plus the output. Ollama default: `2048`. Most modern 7B–8B models support up to 8192 or 32768 tokens natively.

**RAM implications**: Increasing `num_ctx` increases the memory required to hold the key-value cache (KV cache). As a rough guide, doubling the context window roughly doubles KV cache memory usage. On a system with 16 GB of RAM running a 4-bit quantized 8B model (~5 GB), setting `num_ctx=8192` is comfortable. Setting `num_ctx=32768` may exhaust available RAM and cause the OS to swap to disk, making inference unusably slow.

```python
# Ollama
options={"num_ctx": 8192}

# llama-cpp-python — must be set at model load time, not per-request
llm = Llama(model_path="...", n_ctx=8192)
```

**`seed`**

Sets the random number generator seed for sampling. With the same `seed`, `temperature`, and input, the model produces identical output across calls. Use this for:
- Reproducible test cases and CI pipelines
- Debugging prompt changes in isolation (only the prompt changed, not the randomness)
- Deterministic outputs in data pipelines

```python
# Ollama
options={"seed": 42, "temperature": 0.7}

# llama-cpp-python — can be set at construction or per-request
llm = Llama(model_path="...", seed=42)
# or per-request:
response = llm.create_chat_completion(messages=[...], seed=42, temperature=0.7)
```

Setting `seed` does not eliminate randomness — it makes it reproducible. If `temperature=0`, the output is already deterministic and `seed` has no visible effect on output content.

**`stop` Sequences**

A list of strings that cause generation to halt when any of them appears in the output. The stop string itself is not included in the response.

```python
# Ollama: stop when the model tries to start a new Q&A turn
options={"stop": ["User:", "Human:", "Q:"]}

# llama-cpp-python
output = llm("Q: What is Python?\nA:", stop=["Q:", "\n\n"], max_tokens=128)
```

Stop sequences are essential for raw completion tasks where you know the structural boundary of the desired output. They are also useful for enforcing output length limits more precisely than `max_tokens` alone.

**`repeat_penalty`**

Penalises the model for repeating tokens that have already appeared in the output. Values above `1.0` reduce repetition; values below `1.0` encourage it. Ollama default: `1.1`.

- `1.0`: No penalty — repetition is allowed freely
- `1.1`: Mild penalty (recommended default — reduces obvious loops)
- `1.3`: Strong penalty (useful if the model gets stuck repeating phrases)
- Values above `1.5` can cause the model to avoid common words erratically

**`repeat_last_n`**

Controls how far back in the generated text the repeat penalty looks. The penalty is applied only to tokens that appeared within the last `repeat_last_n` tokens. Ollama default: `64`. Set to `-1` to look back through the entire context; set to `0` to disable the penalty entirely.

```python
options={"repeat_penalty": 1.2, "repeat_last_n": 128}
```

**`max_tokens` / `num_predict`**

The maximum number of tokens to generate in the response. Generation stops sooner if a stop sequence is hit or the model produces an end-of-sequence token.

- Ollama uses `num_predict`. Set `-1` for unlimited (generation stops only on EOS or stop sequences). Ollama default: `-1`.
- `llama-cpp-python` uses `max_tokens`. Set `-1` for unlimited.

```python
# Ollama
options={"num_predict": 512}

# llama-cpp-python
llm.create_chat_completion(messages=[...], max_tokens=512)
```

Always set a reasonable `max_tokens` in production to prevent runaway generation from consuming all context window space or running indefinitely.

---

### Streaming Responses

**Why Streaming Matters**

Local model inference is sequential: one token at a time. A 300-token response at 15 tokens/second takes 20 seconds to complete. Without streaming, the user sees nothing for 20 seconds, then the entire response appears at once. With streaming, the first token appears in under a second and the user reads along as the model writes. This transforms the perceived responsiveness of your application dramatically.

Streaming also enables early stopping: if you detect that the model is going off-track (or the user presses Ctrl+C), you can break out of the stream loop without waiting for generation to finish.

**Streaming with the Ollama SDK**

```python
import ollama


def stream_response(model: str, messages: list) -> str:
    """Stream a response to stdout and return the full text."""
    chunks = []
    stream = ollama.chat(model=model, messages=messages, stream=True)
    for chunk in stream:
        token = chunk["message"]["content"]
        print(token, end="", flush=True)
        chunks.append(token)
    print()
    return "".join(chunks)
```

**Streaming with llama-cpp-python**

```python
from llama_cpp import Llama


def stream_llama(llm: Llama, messages: list) -> str:
    """Stream a chat completion to stdout and return the full text."""
    chunks = []
    stream = llm.create_chat_completion(messages=messages, stream=True, max_tokens=512)
    for chunk in stream:
        delta = chunk["choices"][0]["delta"]
        if "content" in delta:
            token = delta["content"]
            print(token, end="", flush=True)
            chunks.append(token)
    print()
    return "".join(chunks)
```

**Handling KeyboardInterrupt in a Stream**

```python
import ollama

stream = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Write a long essay about the ocean."}],
    stream=True,
)

try:
    for chunk in stream:
        print(chunk["message"]["content"], end="", flush=True)
except KeyboardInterrupt:
    print("\n[Generation stopped by user]")
print()
```

---

### Model Selection for Tasks

Choosing the right model matters as much as tuning parameters. Larger models are generally more capable but slower and more memory-intensive on CPU. Smaller models are faster but may struggle with complex reasoning or long-form generation.

**Model Size vs. Quality on CPU**

| Model Size | RAM Required (Q4_K_M) | CPU Tokens/sec (8-core) | Quality Level |
|---|---|---|---|
| 1B–3B | ~2–3 GB | 20–60 t/s | Good for simple tasks, fast iteration |
| 7B–8B | ~5–6 GB | 8–20 t/s | Strong general purpose |
| 13B–14B | ~9–10 GB | 4–10 t/s | Excellent instruction following |
| 32B+ | 20 GB+ | 1–4 t/s | Near-frontier quality, slow on CPU |

Token generation speed is heavily hardware-dependent. These figures are rough estimates for a modern 8-core x86 CPU with DDR4 RAM.

**Recommended Models by Task (Available via Ollama as of 2026)**

| Task | Recommended Model | Pull Command | Notes |
|---|---|---|---|
| General chat / beginners | `llama3.2` (3B) | `ollama pull llama3.2` | Fast, excellent small general-purpose model |
| Best general balance (8–16 GB) | `llama3.1:8b` | `ollama pull llama3.1:8b` | Strong instruction following |
| Coding (primary choice) | `qwen2.5-coder:7b` | `ollama pull qwen2.5-coder:7b` | 128K context, strong HumanEval, FIM support |
| Coding (large, high quality) | `qwen2.5-coder:14b` | `ollama pull qwen2.5-coder:14b` | Best local coding model for 16 GB systems |
| Reasoning and math | `deepseek-r1:7b` | `ollama pull deepseek-r1:7b` | Chain-of-thought, strong math performance |
| Instruction following | `mistral:7b` | `ollama pull mistral:7b` | Very efficient, reliable |
| Small / fast | `phi4-mini` | `ollama pull phi4-mini` | Microsoft 3.8B, surprisingly capable |
| Reasoning (14B, punches above weight) | `phi4` | `ollama pull phi4` | Strong at logic, math, structured tasks on 16 GB |
| Multilingual and general | `qwen2.5:7b` | `ollama pull qwen2.5:7b` | Best local multilingual support |
| Long documents (128K context) | `gemma3:9b` | `ollama pull gemma3:9b` | Google's 9B model, strong context handling |
| Tool calling / agents | `gemma3:4b` | `ollama pull gemma3:4b` | Built-in tool calling, 6 GB RAM |

**Task-Specific Parameter Suggestions**

| Task | temperature | top_p | repeat_penalty | Notes |
|---|---|---|---|---|
| Code generation | 0.0–0.2 | 0.95 | 1.0–1.1 | Determinism critical; use `seed` |
| Structured output (JSON) | 0.0 | 1.0 | 1.0 | Use stop sequences; low temp for validity |
| Summarisation | 0.3 | 0.9 | 1.1 | Low creativity needed |
| General Q&A | 0.5–0.7 | 0.95 | 1.1 | Balanced |
| Creative writing | 0.8–1.1 | 0.95 | 1.2 | Encourage diversity |
| Brainstorming | 1.0–1.2 | 1.0 | 1.1 | Maximum variety |

---

### Building a Simple Chat Loop

A complete, runnable multi-turn chat loop demonstrates everything covered so far. This implementation supports both the Ollama and llama-cpp-python backends through a unified interface.

**The Unified Chat Interface**

```python
# chat_interface.py

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator


class ChatBackend(ABC):
    """Abstract base class for a chat backend."""

    @abstractmethod
    def stream_reply(self, messages: list[dict]) -> Iterator[str]:
        """Yield response tokens one at a time."""
        ...


class OllamaBackend(ChatBackend):
    """Ollama Python SDK backend."""

    def __init__(self, model: str, options: dict | None = None, host: str | None = None):
        import ollama
        self._model = model
        self._options = options or {"temperature": 0.7, "num_ctx": 4096}
        if host:
            self._client = ollama.Client(host=host)
        else:
            import ollama as _ollama
            self._client = _ollama  # use module-level functions

    def stream_reply(self, messages: list[dict]) -> Iterator[str]:
        stream = self._client.chat(
            model=self._model,
            messages=messages,
            options=self._options,
            stream=True,
        )
        for chunk in stream:
            yield chunk["message"]["content"]


class LlamaCppBackend(ChatBackend):
    """llama-cpp-python backend."""

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 4096,
        n_threads: int | None = None,
        n_gpu_layers: int = 0,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ):
        from llama_cpp import Llama
        self._llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )
        self._temperature = temperature
        self._max_tokens = max_tokens

    def stream_reply(self, messages: list[dict]) -> Iterator[str]:
        stream = self._llm.create_chat_completion(
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk["choices"][0]["delta"]
            if "content" in delta:
                yield delta["content"]
```

**The Chat Loop**

```python
# chat_loop.py

from chat_interface import ChatBackend, OllamaBackend, LlamaCppBackend

SYSTEM_PROMPT = (
    "You are a knowledgeable and concise assistant. "
    "Answer clearly and directly. "
    "If you are unsure about something, say so."
)


def run_chat_loop(backend: ChatBackend, system_prompt: str = SYSTEM_PROMPT) -> None:
    """Run an interactive multi-turn chat loop."""
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    print("Chat started. Type 'quit' or press Ctrl+C to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye.")
            break

        messages.append({"role": "user", "content": user_input})

        print("Assistant: ", end="", flush=True)
        collected: list[str] = []

        try:
            for token in backend.stream_reply(messages):
                print(token, end="", flush=True)
                collected.append(token)
        except KeyboardInterrupt:
            print("\n[Interrupted]")

        print()

        full_reply = "".join(collected)
        if full_reply:
            messages.append({"role": "assistant", "content": full_reply})

        # Warn if approaching context limit (rough estimate: 1 token ~ 4 chars)
        estimated_tokens = sum(len(m["content"]) // 4 for m in messages)
        if estimated_tokens > 3000:
            print(f"  [Note: Estimated context usage ~{estimated_tokens} tokens. "
                  "Consider starting a new session soon.]\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "llama":
        # Usage: python chat_loop.py llama /path/to/model.gguf
        model_path = sys.argv[2] if len(sys.argv) > 2 else "model.gguf"
        backend = LlamaCppBackend(model_path=model_path, n_ctx=4096, temperature=0.7)
    else:
        # Usage: python chat_loop.py [ollama] [model_name]
        model_name = sys.argv[2] if len(sys.argv) > 2 else "llama3.2"
        backend = OllamaBackend(model=model_name)

    run_chat_loop(backend)
```

Run with Ollama: `python chat_loop.py ollama llama3.2`
Run with llama-cpp-python: `python chat_loop.py llama /path/to/model.Q4_K_M.gguf`

---

## Best Practices

1. **Start with the Ollama SDK for new projects.** The server-side model caching means the model stays loaded in memory between requests, dramatically reducing latency for interactive development. Switch to `llama-cpp-python` when you need direct control, embedding inference into a library, or distributing a single-process application that must not depend on an external service.

2. **Use `temperature=0` and a fixed `seed` during prompt development.** This lets you isolate the effect of prompt changes from sampling randomness. Once your prompt is solid, re-enable natural randomness for production or conversational use.

3. **Keep system prompts specific and instructive.** Vague system prompts produce vague behaviour. "Be concise" is better than nothing; "Answer in at most three sentences, using plain language, without bullet points" is better still. Local models benefit from this guidance more than frontier cloud models.

4. **Set `num_ctx` / `n_ctx` deliberately.** The Ollama default of `2048` tokens is often too small for multi-turn conversations. `4096` is a good working default; increase to `8192` only if your task requires it and your RAM permits.

5. **Always set `verbose=False` in `llama-cpp-python` for code others will read.** The default `verbose=True` prints pages of model metadata, load times, and per-layer information to stderr. This is useful once when debugging a new setup, and noise thereafter.

6. **Log your prompts and parameters during development.** When you iterate on prompts, record the exact parameters that produced each output. Without this log, it is impossible to reproduce good results or understand why a change improved or degraded quality.

7. **Match `num_ctx` to your actual content, not the model's maximum.** Running a 3B model with `num_ctx=32768` when your average conversation fits in 2048 tokens wastes memory and slows the initial prompt evaluation step. Size the context window to your workload.

8. **Prefer streaming for all interactive output.** Even in scripts that write to a log file, streaming avoids holding large responses in memory simultaneously and gives you an early exit path if something goes wrong.

9. **Set thread count explicitly for `llama-cpp-python` on CPU.** The default thread count is not always optimal. Use `n_threads` equal to your physical core count (not hyperthreads). For a 4-core / 8-thread CPU, use `n_threads=4` — LLM inference is memory-bandwidth-bound, and adding hyperthreads typically reduces throughput.

10. **Pull models before running scripts, not inside them.** Use `ollama pull <model>` once from the command line. Do not trigger pulls inside application code — a slow or failed download during a user session degrades the experience. Treat models like dependencies that are installed in advance.

---

## Use Cases

### Use Case 1: Private Code Review Assistant

A software consultancy handles client code covered by NDAs. Sending code to a cloud API would violate those agreements. The team runs `qwen2.5-coder:7b` through Ollama on a development server, and developers query it from their laptops via a `Client(host="http://server-ip:11434")` instance. Every prompt and response stays within the internal network. The concepts from this module that apply are: the `ollama.Client` custom host configuration, the Ollama streaming API for interactive feel, and the system prompt pattern to set up a code review persona.

**Expected outcome**: Developers get AI-assisted code review on sensitive codebases with zero data leaving the office network, and zero per-request cost.

### Use Case 2: Batch Document Information Extraction

A researcher needs to extract structured data from thousands of PDF documents converted to text. The extraction must run on a laptop during field work with no internet access. Using `llama-cpp-python` directly in a Python script, they load a Q4_K_M quantized 7B model once at startup and process documents in a loop, passing each as a user message with a few-shot system prompt that shows the required JSON output format. Streaming is disabled to simplify result handling. The concepts that apply are: `Llama()` constructor parameters for CPU-only load, `create_chat_completion()` with structured prompt and stop sequences, `temperature=0` for consistent JSON output, and `seed` for reproducibility.

**Expected outcome**: Thousands of documents processed without network access, at zero per-document cost, with deterministic structured output.

### Use Case 3: Prompt Engineering Workbench

A developer new to LLMs wants to run hundreds of prompt experiments to understand how system prompts, temperature, and context affect outputs. Running every experiment through a cloud API would cost money and introduce latency. With Ollama running locally, experiments are free and fast for small models. The developer uses `ollama run llama3.2:3b` for quick interactive testing and switches to the Ollama Python SDK with a fixed `seed` and varying `temperature` values to systematically measure output variation. The concepts that apply are: the `options` dictionary for parameter control, `seed` for isolating changes, and the streaming response pattern for responsive output.

**Expected outcome**: Deep intuition for inference parameters built quickly, at no cost, with complete control over the experiment setup.

### Use Case 4: Prototype Application Before Cloud Commitment

A startup is evaluating whether an LLM fits their product before choosing a cloud provider. They prototype the entire application — conversation management, system prompts, response parsing — using a local model as a stand-in. Because both Ollama and the `LlamaCppBackend` in the unified interface expose the same method signature, swapping to a production cloud endpoint later requires only changing the backend constructor. The concepts that apply are: the `ChatBackend` abstraction pattern, the message history management, and the `num_ctx` and `temperature` tuning to simulate production behaviour.

**Expected outcome**: A fully prototyped application that can be switched to cloud inference by changing one line, with zero cost during development.

---

## Hands-On Examples

### Example 1: Ollama SDK — Single-Turn and Multi-Turn Chat with Streaming

This example demonstrates single-turn and multi-turn chat using the Ollama SDK with streaming enabled for both cases. Before running, ensure Ollama is running (`sudo systemctl status ollama` or `ollama serve`) and the model is pulled (`ollama pull llama3.2`).

```python
# example1_ollama_chat.py

import ollama


MODEL = "llama3.2"  # change to any model you have pulled locally


def single_turn_example() -> None:
    """Send one message and print the streamed response."""
    print("=== Single-Turn Example ===")
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Be concise.",
        },
        {
            "role": "user",
            "content": "What are three benefits of type hints in Python?",
        },
    ]

    print("Assistant: ", end="", flush=True)
    stream = ollama.chat(
        model=MODEL,
        messages=messages,
        options={"temperature": 0.3, "num_ctx": 2048, "seed": 1},
        stream=True,
    )
    for chunk in stream:
        print(chunk["message"]["content"], end="", flush=True)
    print("\n")


def multi_turn_example() -> None:
    """Conduct a three-turn conversation, streaming each reply."""
    print("=== Multi-Turn Example ===")
    messages = [
        {
            "role": "system",
            "content": "You are a patient Python tutor. Give short, clear answers.",
        }
    ]

    turns = [
        "What is a list comprehension?",
        "Can you show me a simple example?",
        "How does that differ from a regular for loop?",
    ]

    for user_text in turns:
        messages.append({"role": "user", "content": user_text})
        print(f"User: {user_text}")
        print("Assistant: ", end="", flush=True)

        collected: list[str] = []
        stream = ollama.chat(
            model=MODEL,
            messages=messages,
            options={"temperature": 0.5, "num_ctx": 4096},
            stream=True,
        )
        for chunk in stream:
            token = chunk["message"]["content"]
            print(token, end="", flush=True)
            collected.append(token)
        print("\n")

        # Add the assistant reply to history so the next turn has context
        messages.append({"role": "assistant", "content": "".join(collected)})


if __name__ == "__main__":
    single_turn_example()
    multi_turn_example()
```

To run: `python example1_ollama_chat.py`

You should see each assistant answer stream to the terminal token-by-token. Notice how the third turn ("How does that differ from a regular for loop?") is answered coherently — the model has the full prior conversation in context because you appended each reply to `messages`.

---

### Example 2: llama-cpp-python — Loading a GGUF Model and Running Chat Completion with Parameter Tuning

This example loads a GGUF model directly and demonstrates the effect of temperature on output character. Update `MODEL_PATH` to point to a `.gguf` file on your machine (from Module 0, this is `./models/Llama-3.2-3B-Instruct-Q4_K_M.gguf`).

```python
# example2_llama_cpp.py

from llama_cpp import Llama


MODEL_PATH = "./models/Llama-3.2-3B-Instruct-Q4_K_M.gguf"  # update this path


def load_model() -> Llama:
    """Load the GGUF model with reasonable defaults."""
    print("Loading model (this takes a few seconds)...")
    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=4096,
        n_threads=6,        # set to your physical CPU core count
        n_gpu_layers=0,     # set to -1 to offload all layers to GPU if available
        verbose=False,
    )
    print("Model loaded.\n")
    return llm


def run_with_params(llm: Llama, user_message: str, **params) -> str:
    """Run a single-turn chat completion and return the response text."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user",   "content": user_message},
    ]
    response = llm.create_chat_completion(messages=messages, **params)
    return response["choices"][0]["message"]["content"]


def compare_temperatures(llm: Llama) -> None:
    """Show how temperature changes the creative character of output."""
    prompt = "Describe the colour blue to someone who has never seen it."

    print("=== Temperature Comparison (same seed, same prompt) ===")
    for temp in [0.0, 0.5, 1.0]:
        print(f"\n--- temperature={temp} ---")
        text = run_with_params(llm, prompt, temperature=temp, max_tokens=120, seed=99)
        print(text)


def streaming_example(llm: Llama) -> None:
    """Stream a response token by token."""
    print("\n=== Streaming Example ===")
    messages = [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user",   "content": "List four Python standard library modules and one use case each."},
    ]

    stream = llm.create_chat_completion(
        messages=messages,
        max_tokens=300,
        temperature=0.4,
        top_p=0.9,
        repeat_penalty=1.1,
        stream=True,
    )

    print("Assistant: ", end="", flush=True)
    for chunk in stream:
        delta = chunk["choices"][0]["delta"]
        if "content" in delta:
            print(delta["content"], end="", flush=True)
    print()


if __name__ == "__main__":
    llm = load_model()
    compare_temperatures(llm)
    streaming_example(llm)
```

To run: `python example2_llama_cpp.py`

The temperature comparison block sends the same prompt three times with different temperatures but the same `seed=99`. At `temperature=0.0` the output is deterministic and typically literal. At `temperature=1.0` the description tends to be more metaphorical and varied. This directly demonstrates the sampling mechanics explained in the Key Concepts section.

---

### Example 3: Unified Chat Interface Class

This example implements the `ChatSession` + `ChatBackend` abstraction from the **Building a Simple Chat Loop** section. It shows how to write inference code that is completely agnostic to the underlying backend.

```python
# example3_unified.py

"""
A unified chat interface that works with both Ollama and llama-cpp-python.
Switch backends by changing a single constructor call in main().
"""

from __future__ import annotations
from typing import Iterator


class ChatBackend:
    """Base class — override stream_reply() in each implementation."""

    def stream_reply(self, messages: list[dict]) -> Iterator[str]:
        raise NotImplementedError


class OllamaBackend(ChatBackend):
    """Wraps the Ollama Python SDK."""

    def __init__(self, model: str, temperature: float = 0.7, num_ctx: int = 4096):
        import ollama as _ollama
        self._ollama = _ollama
        self._model = model
        self._options = {"temperature": temperature, "num_ctx": num_ctx}

    def stream_reply(self, messages: list[dict]) -> Iterator[str]:
        stream = self._ollama.chat(
            model=self._model,
            messages=messages,
            options=self._options,
            stream=True,
        )
        for chunk in stream:
            yield chunk["message"]["content"]


class LlamaCppBackend(ChatBackend):
    """Wraps llama-cpp-python."""

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 4096,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ):
        from llama_cpp import Llama
        self._llm = Llama(model_path=model_path, n_ctx=n_ctx, verbose=False)
        self._temperature = temperature
        self._max_tokens = max_tokens

    def stream_reply(self, messages: list[dict]) -> Iterator[str]:
        stream = self._llm.create_chat_completion(
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk["choices"][0]["delta"]
            if "content" in delta:
                yield delta["content"]


class ChatSession:
    """
    Manages a multi-turn conversation with a pluggable backend.
    Maintains message history and provides streaming and non-streaming reply methods.
    """

    def __init__(self, backend: ChatBackend, system_prompt: str = ""):
        self._backend = backend
        self._messages: list[dict] = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})

    def send(self, user_message: str) -> str:
        """Send a message and return the full response (non-streaming)."""
        self._messages.append({"role": "user", "content": user_message})
        tokens = list(self._backend.stream_reply(self._messages))
        reply = "".join(tokens)
        self._messages.append({"role": "assistant", "content": reply})
        return reply

    def send_stream(self, user_message: str) -> Iterator[str]:
        """
        Send a message and yield response tokens as they arrive.
        The caller must exhaust the iterator for history to be updated correctly.
        """
        self._messages.append({"role": "user", "content": user_message})
        collected: list[str] = []

        for token in self._backend.stream_reply(self._messages):
            collected.append(token)
            yield token

        self._messages.append({"role": "assistant", "content": "".join(collected)})

    def clear_history(self, keep_system: bool = True) -> None:
        """Clear conversation history, optionally keeping the system prompt."""
        if keep_system and self._messages and self._messages[0]["role"] == "system":
            self._messages = [self._messages[0]]
        else:
            self._messages = []

    @property
    def turn_count(self) -> int:
        """Number of completed user turns in the current session."""
        return sum(1 for m in self._messages if m["role"] == "user")


def demo_session(backend: ChatBackend) -> None:
    session = ChatSession(
        backend=backend,
        system_prompt="You are a concise Python expert. Answer in 2–3 sentences max.",
    )

    questions = [
        "What is the GIL?",
        "Does that mean Python can't use multiple CPU cores at all?",
        "What's the recommended alternative for CPU-bound parallelism?",
    ]

    for question in questions:
        print(f"User: {question}")
        print("Assistant: ", end="", flush=True)
        for token in session.send_stream(question):
            print(token, end="", flush=True)
        print(f"\n  [Turn {session.turn_count} complete]\n")


if __name__ == "__main__":
    import sys

    if "--llama" in sys.argv:
        idx = sys.argv.index("--llama")
        model_path = sys.argv[idx + 1]
        backend = LlamaCppBackend(model_path=model_path, n_ctx=4096)
        print(f"Using llama-cpp-python backend: {model_path}\n")
    else:
        model = sys.argv[1] if len(sys.argv) > 1 else "llama3.2"
        backend = OllamaBackend(model=model)
        print(f"Using Ollama backend: {model}\n")

    demo_session(backend)
```

Run with Ollama: `python example3_unified.py llama3.2`
Run with llama-cpp-python: `python example3_unified.py --llama /path/to/model.gguf`

The three-question conversation about the GIL demonstrates that the third answer is informed by the first two — the model knows from turn 2 that you already understand Python's threading limitations, so turn 3's answer builds on that context rather than re-explaining it.

---

## Common Pitfalls

### Context Window Overflow

**Description:** The model silently truncates the beginning of the conversation when the combined message history exceeds the context window size.

**Why it happens:** Every model has a hard maximum context window. When the total token count of all messages plus the expected response exceeds `num_ctx` / `n_ctx`, the runtime discards the oldest tokens. This is not an error — it is by design — but it means the model loses memory of early conversation turns without any warning to your code.

**Incorrect pattern:**
```python
# Running a long conversation without any context management
messages = [{"role": "system", "content": "..."}]
for i in range(100):
    messages.append({"role": "user", "content": f"Turn {i}: tell me something new."})
    response = ollama.chat(model="llama3.2", messages=messages)
    messages.append({"role": "assistant", "content": response.message.content})
    # After ~20 turns, early messages are silently dropped from context
```

**Correct pattern:**
```python
# Estimate tokens and warn before overflow occurs
estimated_tokens = sum(len(m["content"]) // 4 for m in messages)
if estimated_tokens > 3500:  # conservative threshold for num_ctx=4096
    print("Warning: approaching context limit. Starting new session.")
    # Either clear history or summarise early turns before continuing
```

---

### Chat Template Mismatches

**Description:** Passing a bare question string to raw completion functions produces poor or confused output from instruct models.

**Why it happens:** Instruct models were fine-tuned with specific special tokens wrapping each role's turn. When those tokens are absent, the model receives input that does not match its training distribution. It may attempt to continue the text rather than answer the question, or it may emit the role tokens it expected to see in the input.

**Incorrect pattern:**
```python
# Using raw completion with an instruct model — no chat template applied
output = llm("What is the capital of France?", max_tokens=50)
# The model may continue the sentence, not answer the question
print(output["choices"][0]["text"])
```

**Correct pattern:**
```python
# Use create_chat_completion — applies the embedded chat template automatically
response = llm.create_chat_completion(
    messages=[{"role": "user", "content": "What is the capital of France?"}],
    max_tokens=50,
)
print(response["choices"][0]["message"]["content"])
```

---

### `temperature=0` Does Not Guarantee Cross-Machine Reproducibility

**Description:** Setting `temperature=0` and expecting byte-for-byte identical output across different machines, thread counts, or library versions.

**Why it happens:** `temperature=0` eliminates the *random sampling* step by always selecting the top-probability token. However, floating-point operations in parallel threads are not fully associative — the order in which intermediate results are accumulated can vary between hardware, OS, or library version, producing slightly different logit values. The most likely token is almost always the same, but edge cases exist.

**Incorrect assumption:**
```python
# Assuming temperature=0 makes output identical across all machines
llm1 = Llama(model_path="...", n_threads=4, verbose=False)
llm2 = Llama(model_path="...", n_threads=8, verbose=False)  # different thread count
# These may produce different output even at temperature=0
```

**Correct pattern:**
```python
# Use temperature=0 + a fixed seed for best reproducibility within one machine
llm = Llama(model_path="...", n_threads=6, seed=42, verbose=False)
response = llm.create_chat_completion(messages=[...], temperature=0.0)
# Document the n_threads value alongside the seed for reproducibility records
```

---

### RAM Exhaustion from Large `n_ctx`

**Description:** Setting a very large context window causes the OS to swap to disk, making inference extremely slow.

**Why it happens:** The KV cache — the runtime's working memory for the context window — scales roughly linearly with `n_ctx`. Increasing `n_ctx` from `2048` to `32768` (16×) can add several gigabytes of RAM usage on top of the model weights. When total RAM usage exceeds physical memory, the OS pages memory to disk, dropping throughput from tokens-per-second to tokens-per-minute.

**Incorrect pattern:**
```python
# Setting maximum context on a RAM-constrained machine
llm = Llama(
    model_path="./models/llama-3.1-8b.Q4_K_M.gguf",  # ~5 GB on disk
    n_ctx=131072,   # model's maximum — but adds ~8+ GB of KV cache
    verbose=False,
)
# On a 16 GB machine, this may cause heavy swapping
```

**Correct pattern:**
```python
# Match n_ctx to actual workload — most tasks fit in 4096-8192 tokens
llm = Llama(
    model_path="./models/llama-3.1-8b.Q4_K_M.gguf",
    n_ctx=4096,   # comfortable for most conversations on 16 GB systems
    verbose=False,
)
```

---

### Forgetting to Append Assistant Replies to History

**Description:** Each turn sends only the new user message, causing the model to have no memory of its previous answers.

**Why it happens:** The message list is just a Python list — it does not auto-update. After calling `ollama.chat()` or `create_chat_completion()`, the assistant's reply exists only in the response object. If you only append the next user message without first appending the assistant's reply, the model receives a conversation where it apparently never answered.

**Incorrect pattern:**
```python
messages = [{"role": "system", "content": "..."}]
messages.append({"role": "user", "content": "What is Python?"})
response = ollama.chat(model="llama3.2", messages=messages)
# Bug: forgot to append assistant's reply to messages

messages.append({"role": "user", "content": "What is it used for?"})
response = ollama.chat(model="llama3.2", messages=messages)
# Model sees two user messages with no assistant turn in between — breaks coherence
```

**Correct pattern:**
```python
messages = [{"role": "system", "content": "..."}]
messages.append({"role": "user", "content": "What is Python?"})
response = ollama.chat(model="llama3.2", messages=messages)
messages.append({"role": "assistant", "content": response.message.content})  # required

messages.append({"role": "user", "content": "What is it used for?"})
response = ollama.chat(model="llama3.2", messages=messages)
```

---

### Verbose `llama-cpp-python` Output Cluttering Logs

**Description:** The default `verbose=True` prints pages of internal model metadata to stderr, making it hard to see your application's actual output.

**Why it happens:** `llama-cpp-python` defaults to `verbose=True` so that first-time users can see the model loading correctly. In any code beyond personal exploration, this output is noise.

**Incorrect pattern:**
```python
# Omitting verbose=False — clutters stderr with model metadata
llm = Llama(model_path="./model.gguf", n_ctx=4096)
# stderr will contain: "llama_model_load_internal: loading model ...", layer info, etc.
```

**Correct pattern:**
```python
llm = Llama(model_path="./model.gguf", n_ctx=4096, verbose=False)
```

---

## Summary

- LLMs generate text one token at a time through next-token prediction and probability sampling; the `temperature`, `top_p`, `top_k`, `min_p`, `seed`, `repeat_penalty`, and `num_ctx` parameters all shape how that sampling behaves, and understanding each parameter's effect lets you tune outputs reliably for any task type.
- The Ollama Python SDK (`ollama` 0.6+) provides the simplest path to local inference — `ollama.chat()` handles the message format, streaming, error handling, and options dict, while `ollama.Client` enables connection to remote Ollama servers; use it for interactive development and application prototyping.
- `llama-cpp-python` (`0.3+`) loads GGUF model files directly into your Python process for fine-grained control; always use `create_chat_completion()` for instruct models (not the raw `llm()` call), set `verbose=False`, and match `n_ctx` to your actual workload to avoid RAM exhaustion.
- Chat templates — the model-specific special tokens that separate system, user, and assistant turns — are applied automatically by both Ollama and `llama-cpp-python` when you use their chat APIs; the pitfall is using raw completion functions with instruct models, which bypasses the template entirely.
- A backend abstraction class that exposes a single `stream_reply(messages)` method lets you write conversation management, history tracking, and UI code once and run it against either Ollama or llama-cpp-python by changing one constructor line.

---

## Further Reading

- [Ollama Python Library — GitHub](https://github.com/ollama/ollama-python) — Official source repository for the `ollama` Python SDK (current: v0.6.x), containing the complete API reference, changelog, and usage examples for `chat()`, `generate()`, `Client`, `AsyncClient`, and tool-calling variants.
- [llama-cpp-python — GitHub](https://github.com/abetlen/llama-cpp-python) — Official Python bindings for llama.cpp (current: v0.3.x), including the full `Llama` class API reference, installation instructions for all backends (CPU, CUDA 12.1–12.5, Metal, ROCm), and the OpenAI-compatible server mode.
- [Ollama Modelfile Reference — docs.ollama.com](https://docs.ollama.com/modelfile) — Complete reference for all Ollama inference parameters including `temperature`, `top_k`, `top_p`, `min_p`, `num_ctx`, `seed`, `repeat_penalty`, `repeat_last_n`, and `num_predict` with their types, defaults, and valid ranges; the authoritative source before setting any `options` dict value.
- [Ollama Model Library](https://ollama.com/library) — Browse all models available via `ollama pull`, with parameter counts, context window sizes, quantization variants, and task tags; essential for evaluating new models before committing to a download.
- [Chat Templates — Hugging Face LLM Course](https://huggingface.co/learn/llm-course/chapter11/2) — Explains the Llama 3, Mistral, ChatML, Qwen, and Phi chat template formats in detail, why mixing templates causes degraded model behaviour, and how `apply_chat_template()` automates template selection; useful background for understanding what Ollama and `llama-cpp-python` do automatically.
- [Prompt Engineering Guide — Model Settings](https://www.promptingguide.ai/introduction/settings) — Concise reference for all major inference parameters with practical recommendations for common NLP tasks (summarisation, classification, generation, code) and guidance on which parameters interact and compound.
- [LLM Inference Parameters Explained — Let's Data Science](https://letsdatascience.com/blog/llm-sampling-temperature-top-k-top-p-and-min-p-explained) — In-depth explanation of temperature, top-k, top-p, and min-p sampling with mathematical intuition, visualisations of the probability distribution effects, and practical guidance on when to use each.
- [Best Open-Source LLMs in 2026 — ML Journey](https://mljourney.com/best-open-source-llms-in-2026-a-practical-guide-by-use-case/) — Curated and benchmarked guide to the best open-weight models by task category (coding, reasoning, multilingual, long context) as of 2026, with Ollama pull commands and hardware requirements for each.
