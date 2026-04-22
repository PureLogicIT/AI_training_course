# Module 2: Hugging Face & Local Models
> Subject: AI Development | Difficulty: Intermediate | Estimated Time: 270 minutes

## Objective

After completing this module, you will be able to navigate Hugging Face Hub to find, evaluate, and download models suitable for local CPU inference. You will understand the difference between using the Hub as a file download source and using the `transformers` library for inference. You will use the `pipeline()` API for rapid prototyping across multiple task types, and drop down to `AutoModelForCausalLM` and `AutoTokenizer` when you need finer control. You will understand tokenization fundamentals — encoding, decoding, special tokens, and chat templates — and know why those templates differ across model families. You will load quantized models using BitsAndBytes 4-bit and 8-bit quantization and articulate the tradeoffs. You will stream tokens in real time using `TextIteratorStreamer` with threading. Finally, you will confidently choose between Hugging Face `transformers`, Ollama, and `llama-cpp-python` for any given inference task.

## Prerequisites

- Completed **Module 0: Setup & Local AI Stack** — Python virtual environment active, `transformers`, `torch` (CPU build), `huggingface_hub`, and `llama-cpp-python` installed; `pip install` commands from Module 0 are verified working
- Completed **Module 1: Working with Local Models** — familiar with GGUF format, quantization levels (Q4_K_M etc.), and the Ollama Python SDK; downloaded at least one GGUF model to a local directory
- Python 3.10 or later; comfort with functions, loops, dictionaries, and `import` statements
- At least 8 GB of RAM (16 GB recommended for the BitsAndBytes quantization examples)
- At least 10 GB of free disk space for downloaded model weights
- An internet connection for the initial model downloads (after downloading, all examples run offline)

---

## Key Concepts

### 1. The Hugging Face Ecosystem

Hugging Face is best understood as two distinct things that share a brand. Confusing them is the most common source of beginner mistakes in this space.

**Hugging Face Hub (huggingface.co)** is a model and dataset repository — think of it as GitHub for AI model weights. It hosts over one million public model repositories. Each repository contains model weight files (Safetensors, GGUF, GPTQ, AWQ, or older `.bin` format), a `config.json` describing the architecture, a tokenizer configuration, and a Model Card. You interact with the Hub to find and download models. Downloading is free and requires no account for most models.

**The `transformers` library** is a Python package (`pip install transformers`) developed by Hugging Face that provides classes for loading model weights and running inference locally. The Hub and the `transformers` library are entirely separate: you can download a GGUF file from the Hub and run it with `llama-cpp-python` without importing `transformers` at all. Conversely, `transformers` can load models from a local directory without downloading from the Hub at runtime.

The Hugging Face ecosystem includes several supporting packages you will use in this module:

| Package | Purpose | Install |
|---|---|---|
| `huggingface_hub` | Hub client: downloading models, the `hf` CLI, authentication | `pip install huggingface_hub` |
| `transformers` | Loading and running models locally (Safetensors format) | `pip install transformers` |
| `tokenizers` | Fast Rust-backed tokenization (a dependency of `transformers`) | Installed automatically with `transformers` |
| `accelerate` | Device placement and large model loading utilities | `pip install accelerate` |
| `bitsandbytes` | 4-bit and 8-bit post-training quantization at load time | `pip install bitsandbytes` |

As of April 2026, the current stable versions are: `transformers==5.5.4`, `huggingface_hub>=0.32.0`.

---

### 2. Reading a Model Card

Every model on Hugging Face Hub has a Model Card — a `README.md` file that is rendered on the model's page. Learning to read a Model Card quickly is an important skill for selecting models.

Key sections to check on every Model Card:

**License** — Located in the metadata at the top (the YAML front matter). Common licenses you will encounter:
- `apache-2.0` — Permissive. Commercial use allowed. No attribution required for derived models.
- `mit` — Permissive. Commercial use allowed.
- `llama3` / `llama3.2` / `gemma` — Custom Meta/Google licenses. Commercial use is allowed for most users, but with restrictions (e.g., Meta Llama's license requires attribution and prohibits using the model to train a competing frontier model). Read the full license before production use.
- `other` — Read carefully. Some research models prohibit commercial use entirely.

**Gated models** — Some models (e.g., `meta-llama/Llama-3.2-3B-Instruct` on the original Meta repository) require you to agree to a license on the Hub before downloading. The model page shows a form to submit. After submitting, wait for approval (often automatic and immediate for Meta Llama; manual for some others). You then need to authenticate with `huggingface-cli login` before downloading. Models hosted by third-party converters (e.g., `bartowski/Llama-3.2-3B-Instruct-GGUF`) are often re-licensed as `llama3.2` without the gating requirement — read the specific repo's Model Card.

**Model details** — Look for: parameter count, architecture family (Llama, Mistral, Phi, Qwen, Gemma), training data, context window length, and whether it is a base model or an instruction-tuned model. The distinction matters: base models generate continuations of text; instruction-tuned models (often marked `-Instruct`, `-Chat`, or `-it`) are fine-tuned to follow chat-style instructions.

**Evaluation benchmarks** — Most Model Cards include benchmark scores (MMLU, HumanEval, GSM8K, etc.). These give a rough quality signal but are not a substitute for testing on your specific task.

**Files tab** — Click the "Files and versions" tab to see every file in the repository. This is where you identify which files to download. Look for: `.safetensors` files (for `transformers` inference), `.gguf` files (for `llama-cpp-python` or Ollama), and configuration files (`config.json`, `tokenizer_config.json`).

---

### 3. Finding and Downloading Models from the Hub

#### 3.1 Browsing and Filtering

Use the model search at `https://huggingface.co/models`. Key filters:
- **Task** — Filter by `text-generation`, `text2text-generation`, `fill-mask`, etc.
- **Library** — Filter by `transformers` to show only models that work with the `transformers` library, or `gguf` to show models with GGUF files.
- **Language** — Filter by language if you need multilingual or non-English capability.
- **Sort by** — "Trending" shows recently popular models; "Downloads" shows consistently popular ones.

#### 3.2 Authentication for Gated Models

Most models are public. For gated models, you must:

1. Create a free account at `huggingface.co/join`
2. Visit the model page and accept the license agreement
3. Create a User Access Token at `https://huggingface.co/settings/tokens` (choose "Read" scope)
4. Log in from the CLI:

```bash
huggingface-cli login
# You will be prompted for your token. Paste it and press Enter.
# The token is saved to ~/.cache/huggingface/token
```

After logging in, all download functions (`huggingface-cli download`, `hf_hub_download()`, `snapshot_download()`, and `from_pretrained()`) automatically use the stored token.

#### 3.3 The `hf` CLI — Downloading Files

The `huggingface_hub` package installs an `hf` command-line tool (also available as `huggingface-cli` for backwards compatibility):

```bash
# Download a single file to the local cache (returns the cache path)
hf download google/gemma-2-2b config.json

# Download a specific GGUF file to a local directory
hf download bartowski/Qwen2.5-1.5B-Instruct-GGUF \
  --include "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf" \
  --local-dir ./models

# Download the full Safetensors model for use with transformers
hf download HuggingFaceTB/SmolLM2-1.7B-Instruct \
  --local-dir ./models/SmolLM2-1.7B-Instruct

# Preview download size without actually downloading (dry run)
hf download Qwen/Qwen2.5-1.5B-Instruct --dry-run

# List what is currently in your local cache
hf cache ls
```

The `--include` flag accepts glob patterns for selective file download. This is essential when a repository contains multiple GGUF quantization variants and you only want one.

#### 3.4 The `huggingface_hub` Python SDK

For programmatic control within Python scripts:

```python
from huggingface_hub import hf_hub_download, snapshot_download

# Download a single file — returns its local path inside the cache
config_path = hf_hub_download(
    repo_id="HuggingFaceTB/SmolLM2-1.7B-Instruct",
    filename="config.json",
)
print(config_path)
# Output: /home/user/.cache/huggingface/hub/models--HuggingFaceTB--SmolLM2-1.7B-Instruct/...

# Download a specific GGUF file to a target directory
gguf_path = hf_hub_download(
    repo_id="bartowski/Qwen2.5-1.5B-Instruct-GGUF",
    filename="Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",
    local_dir="./models",
)
print(gguf_path)  # ./models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf

# Download an entire model repository (all files)
repo_path = snapshot_download(
    repo_id="HuggingFaceTB/SmolLM2-1.7B-Instruct",
    local_dir="./models/SmolLM2-1.7B-Instruct",
)

# Download only Safetensors files, skipping old .bin files
repo_path = snapshot_download(
    repo_id="Qwen/Qwen2.5-1.5B-Instruct",
    allow_patterns=["*.safetensors", "*.json", "*.txt"],
    ignore_patterns=["*.bin", "*.h5", "*.msgpack"],
    local_dir="./models/Qwen2.5-1.5B-Instruct",
)
```

**Important:** `hf_hub_download()` returns a path that is a symlink inside the cache structure. Do not modify or delete the file at that path directly — use the cache management tools described in the next section. When you pass `local_dir`, it copies the file to that directory instead of symlinking, making the path safe to use directly.

#### 3.5 The Local Cache Directory

By default, downloaded files are stored in `~/.cache/huggingface/hub/`. The structure is:

```
~/.cache/huggingface/hub/
  models--HuggingFaceTB--SmolLM2-1.7B-Instruct/
    blobs/          # actual file contents (by hash)
    refs/           # branch/tag -> commit hash mapping
    snapshots/      # commit hash -> symlinks to blobs
```

**Managing disk space:**

```bash
# See all cached repos and their sizes
hf cache ls

# Interactive deletion — select repos/revisions to remove
huggingface-cli delete-cache

# Set a custom cache location (add to ~/.bashrc or ~/.zshrc)
export HF_HOME=/path/to/large/disk/.hf_cache

# Or change only the Hub model cache:
export HF_HUB_CACHE=/path/to/large/disk/.hf_hub_cache
```

For developers with limited disk space: use `--local-dir` in your download commands to put model files in a specific location you manage, rather than the default cache. This avoids the duplicate-file issue where the cache stores blobs and your `local_dir` stores copies.

---

### 4. The `transformers` Library

#### 4.1 The `pipeline()` API — Quickest Entry Point

The `pipeline()` function is the fastest way to run inference with any `transformers`-compatible model. It handles tokenization, model loading, batching, and decoding transparently.

```python
from transformers import pipeline

# Text generation — the most common task for LLMs
generator = pipeline(
    task="text-generation",
    model="HuggingFaceTB/SmolLM2-1.7B-Instruct",
    device="cpu",          # explicit: use CPU
    torch_dtype="float32", # float32 is required for CPU-only PyTorch
)

result = generator(
    "The capital of France is",
    max_new_tokens=50,
    do_sample=True,
    temperature=0.7,
    return_full_text=False,  # return only the generated portion, not the prompt
)
print(result[0]["generated_text"])
```

Common pipeline tasks and their identifiers:

| Task Identifier | What It Does | Typical Model Type |
|---|---|---|
| `text-generation` | Continues or completes a text prompt | Causal LM (GPT-style decoder) |
| `text2text-generation` | Converts input text to output text | Encoder-decoder (T5, BART) |
| `summarization` | Summarises a document | Encoder-decoder or fine-tuned causal |
| `question-answering` | Extracts an answer span from a context passage | BERT-style encoder |
| `fill-mask` | Predicts the masked token in a sentence | BERT-style encoder (MLM) |

When you do not specify a `model`, `pipeline()` downloads a default model for the task. Always specify `model` explicitly — default models change between library versions and are often too large for CPU.

**CPU-specific notes:**
- Always pass `device="cpu"` explicitly on CPU-only machines. Without it, `transformers` tries to use `device_map="auto"` in recent versions, which may warn about missing GPU.
- Use `torch_dtype="float32"` on CPU. Half-precision (`float16`, `bfloat16`) is not supported for inference on most CPU-only PyTorch builds and raises an error.
- First load is slow (30–120 seconds for a 1–2B model on CPU) because weights are read from disk and loaded into RAM. Subsequent calls to the same pipeline object are fast.

#### 4.2 Explicit Loading: `AutoModelForCausalLM` and `AutoTokenizer`

The `pipeline()` API is convenient but hides what is happening. For full control, load the model and tokenizer separately:

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "HuggingFaceTB/SmolLM2-1.7B-Instruct"

# Load the tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name)

# Load the model
# torch_dtype=torch.float32 is required for CPU-only PyTorch
# device_map is NOT used for CPU-only — see the pitfalls section
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float32,
)
model.eval()  # set to evaluation mode (disables dropout)
```

The `AutoModel*` and `AutoTokenizer` classes use the `config.json` in the repository to determine the correct architecture and load it automatically. You never need to know whether the model is a LlamaForCausalLM, Phi3ForCausalLM, or Qwen2ForCausalLM — `Auto` handles it.

**From a local directory:** If you downloaded the model with `--local-dir`, pass the local path instead of the Hub repo ID:

```python
model = AutoModelForCausalLM.from_pretrained("./models/SmolLM2-1.7B-Instruct")
tokenizer = AutoTokenizer.from_pretrained("./models/SmolLM2-1.7B-Instruct")
```

#### 4.3 The `generate()` Method

After loading a model and tokenizer, the inference loop is:

1. Tokenize the input text into token IDs
2. Pass the token IDs to `model.generate()`
3. Decode the output token IDs back to text

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "HuggingFaceTB/SmolLM2-1.7B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float32)
model.eval()

# Tokenize
prompt = "Explain what a Python decorator does in one paragraph."
inputs = tokenizer(prompt, return_tensors="pt")  # "pt" = PyTorch tensors
# inputs is a dict with keys: input_ids, attention_mask

# Generate
with torch.no_grad():  # disables gradient tracking — required for inference only
    output_ids = model.generate(
        **inputs,
        max_new_tokens=150,      # maximum tokens to generate beyond the prompt
        do_sample=True,          # enable sampling (required for temperature to work)
        temperature=0.7,         # sampling temperature
        repetition_penalty=1.1,  # penalise repeated tokens
    )

# Decode — slice off the input tokens to get only the generated portion
input_length = inputs["input_ids"].shape[1]
generated_ids = output_ids[0][input_length:]
response = tokenizer.decode(generated_ids, skip_special_tokens=True)
print(response)
```

Key `generate()` parameters:

| Parameter | Type | Description |
|---|---|---|
| `max_new_tokens` | `int` | Maximum tokens to generate. Always set this — the default is 20, which truncates most responses. |
| `do_sample` | `bool` | `True` = sample from the probability distribution. `False` = greedy (always picks the most likely token). Must be `True` for `temperature` to have any effect. |
| `temperature` | `float` | Sampling temperature (requires `do_sample=True`). `< 1.0` = more focused; `> 1.0` = more random. |
| `repetition_penalty` | `float` | Values `> 1.0` reduce token repetition. `1.1`–`1.3` is a useful range. |
| `top_p` | `float` | Nucleus sampling cutoff (requires `do_sample=True`). Restricts sampling to tokens whose cumulative probability reaches `top_p`. |
| `top_k` | `int` | Restricts sampling to the top-k most likely tokens at each step. |
| `eos_token_id` | `int` or `list[int]` | Token(s) that end generation. The model's default is usually correct. |

---

### 5. Tokenizers In Depth

#### 5.1 What Tokenization Is

A tokenizer converts raw text into sequences of integer IDs (tokens), and converts IDs back to text. LLMs do not operate on characters or words — they operate entirely on these integer token IDs.

Each model family uses a different vocabulary and tokenization algorithm. Llama 3 uses a 128,000-token BPE vocabulary. Qwen2.5 uses a 151,936-token vocabulary. This means the same input text produces different token sequences (and different token counts) depending on which model you are using.

#### 5.2 `encode()` and `decode()`

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolLM2-1.7B-Instruct")

# Encode text to token IDs
text = "Hello, how are you?"
token_ids = tokenizer.encode(text)
print(token_ids)      # e.g., [1, 15043, 29892, 920, 526, 366, 29973]
print(len(token_ids)) # number of tokens

# Decode token IDs back to text
decoded = tokenizer.decode(token_ids)
print(decoded)  # "Hello, how are you?"

# Decode while skipping special tokens like <bos>, <eos>
decoded_clean = tokenizer.decode(token_ids, skip_special_tokens=True)

# Inspect individual tokens (useful for debugging)
tokens = tokenizer.convert_ids_to_tokens(token_ids)
print(tokens)  # e.g., ['<s>', '▁Hello', ',', '▁how', '▁are', '▁you', '?']
```

The `tokenizer(text, return_tensors="pt")` call used in the generation pipeline is equivalent to `encode()` but also produces the `attention_mask` that `generate()` requires when using batch inference with padding.

#### 5.3 Special Tokens

Special tokens are reserved token IDs with specific roles in the model's training format:

| Token | Common Name | Role |
|---|---|---|
| `tokenizer.bos_token` | BOS (Beginning of Sequence) | Marks the start of a sequence. Often `<s>`, `<bos>`, or `<|begin_of_text|>`. |
| `tokenizer.eos_token` | EOS (End of Sequence) | Marks the end of a sequence. Model generation stops here. Often `</s>`, `<|endoftext|>`, or `<|eot_id|>`. |
| `tokenizer.pad_token` | PAD | Used to pad shorter sequences in a batch to a uniform length. Not always defined for causal LMs. |
| `tokenizer.unk_token` | UNK (Unknown) | Represents a token not in the vocabulary. Rare in modern BPE tokenizers. |

```python
tokenizer = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolLM2-1.7B-Instruct")
print(f"BOS: {tokenizer.bos_token!r}  id={tokenizer.bos_token_id}")
print(f"EOS: {tokenizer.eos_token!r}  id={tokenizer.eos_token_id}")
print(f"PAD: {tokenizer.pad_token!r}  id={tokenizer.pad_token_id}")
```

#### 5.4 Chat Templates with `apply_chat_template()`

Instruction-tuned chat models were fine-tuned on data where user and assistant turns are wrapped in specific special tokens or formatting strings. Using the wrong format produces degraded model output. This formatting is called a chat template and is stored in the tokenizer's `chat_template` attribute.

`apply_chat_template()` reads the stored template and formats a list of message dicts correctly for any model:

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolLM2-1.7B-Instruct")

messages = [
    {"role": "system", "content": "You are a concise technical assistant."},
    {"role": "user", "content": "What is a Python list comprehension?"},
]

# Produce a formatted string (useful to see what the template looks like)
formatted_text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,          # return a string, not token IDs
    add_generation_prompt=True,  # append the assistant turn opening tag
)
print(formatted_text)

# Produce tokenized PyTorch tensors ready for model.generate()
input_ids = tokenizer.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_tensors="pt",
)
```

The `add_generation_prompt=True` argument appends the assistant turn's opening tag at the end of the formatted sequence. Without it, the model may continue the user's message instead of generating an assistant reply.

**Chat template differences across model families (as of 2026):**

| Family | Format Style | System Message | User Turn | Assistant Turn |
|---|---|---|---|---|
| Llama 3.x | Special header tokens | `<\|start_header_id\|>system<\|end_header_id\|>\n\n...` | `<\|start_header_id\|>user<\|end_header_id\|>\n\n...` | `<\|start_header_id\|>assistant<\|end_header_id\|>\n\n...` |
| Mistral v0.1 | `[INST]` tags | Embedded in first user message | `[INST] ... [/INST]` | `... </s>` |
| ChatML (Qwen, Phi, many fine-tunes) | `<\|im_start\|>` tokens | `<\|im_start\|>system\n...<\|im_end\|>` | `<\|im_start\|>user\n...<\|im_end\|>` | `<\|im_start\|>assistant\n...<\|im_end\|>` |
| Gemma | `<start_of_turn>` tokens | Not natively supported (embed in user turn) | `<start_of_turn>user\n...<end_of_turn>` | `<start_of_turn>model\n...<end_of_turn>` |

The key practical point: always use `apply_chat_template()` rather than manually formatting messages. The template is baked into the tokenizer and is always correct for that specific model checkpoint.

---

### 6. Quantized Models on Hugging Face Hub

Running full-precision (float32 or float16) Safetensors models on CPU requires loading all weights in full precision, which is very RAM-intensive. A 1.7B parameter model in float32 needs roughly 6.8 GB of RAM. There are two approaches to reduce this for local CPU work: use GGUF files (covered in the hands-on examples) or use the `bitsandbytes` library for in-memory quantization at load time.

#### 6.1 GPTQ and AWQ Models (GPU-focused)

**GPTQ** (Generative Pre-trained Transformer Quantization) and **AWQ** (Activation-Aware Weight Quantization) are quantization schemes that produce model files designed to run on NVIDIA GPUs with specific kernels.

- GPTQ requires the `auto-gptq` or `optimum` package
- AWQ requires the `autoawq` package
- Both require CUDA and a compatible GPU to achieve their speed advantages
- On CPU-only machines, these formats either fail to load or run very slowly because their specialized kernels are GPU-only

**For CPU-only local inference, avoid GPTQ and AWQ model variants.** Use GGUF (via `llama-cpp-python`) instead. GGUF's CPU-optimised kernels provide far better CPU performance than GPTQ or AWQ running on CPU.

#### 6.2 BitsAndBytes Quantization (`load_in_4bit`, `load_in_8bit`)

BitsAndBytes is a library that quantizes a model's linear layers at load time. Unlike GPTQ/AWQ, which require a pre-quantized checkpoint, BitsAndBytes downloads the standard float16 Safetensors checkpoint and quantizes it in-memory during loading.

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

model_name = "HuggingFaceTB/SmolLM2-1.7B-Instruct"

# 4-bit quantization — halves memory further beyond 8-bit
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",         # NF4 (Normal Float 4) — preferred for inference
    bnb_4bit_compute_dtype=torch.bfloat16,  # compute in bf16 for speed (GPU)
)

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=quantization_config,
    device_map="auto",  # required with BitsAndBytes
)
tokenizer = AutoTokenizer.from_pretrained(model_name)
```

**Memory reduction at a glance:**

| Precision | Bytes per Parameter | RAM for 7B Model | RAM for 1.7B Model |
|---|---|---|---|
| float32 | 4 | ~28 GB | ~6.8 GB |
| float16 / bfloat16 | 2 | ~14 GB | ~3.4 GB |
| 8-bit (LLM.int8) | ~1 | ~7 GB | ~1.7 GB |
| 4-bit (NF4) | ~0.5 | ~3.5 GB | ~0.85 GB |

**Important CPU limitation:** BitsAndBytes has added CPU backend support, but its 4-bit and 8-bit kernels were designed for GPU and the CPU path is significantly slower than running an equivalent GGUF model with `llama-cpp-python`. On CPU-only machines, BitsAndBytes quantization is primarily useful when you want to use the full `transformers` ecosystem (chat templates, `Trainer`, LoRA fine-tuning) and need to fit the model in RAM — not as a performance optimization.

**Tradeoffs summary:**

| Method | RAM Reduction | CPU Performance | Quality Impact | Fine-tuning Compatible |
|---|---|---|---|---|
| Full float32 (Safetensors) | None | Good (CPU-native) | None | Yes |
| BitsAndBytes 8-bit | ~4x | Slower on CPU | Minimal | Yes (extra params only) |
| BitsAndBytes 4-bit (NF4) | ~8x | Slower on CPU | Small | Yes (QLoRA) |
| GGUF Q4_K_M (llama-cpp-python) | ~8x | Excellent (CPU-native SIMD) | Small | No |
| GPTQ / AWQ | ~4-8x | Poor on CPU (GPU kernels) | Small | No |

---

### 7. Practical Local Inference with `transformers`

#### 7.1 Controlling Generation Parameters

The `pipeline()` API passes generation parameters directly as keyword arguments when calling the pipeline:

```python
from transformers import pipeline

generator = pipeline(
    "text-generation",
    model="HuggingFaceTB/SmolLM2-1.7B-Instruct",
    device="cpu",
    torch_dtype="float32",
)

# Pass generation parameters at call time
output = generator(
    "Write a haiku about local AI inference.",
    max_new_tokens=60,
    do_sample=True,
    temperature=0.8,
    top_p=0.9,
    repetition_penalty=1.1,
    return_full_text=False,
)
print(output[0]["generated_text"])
```

#### 7.2 Streaming with `TextIteratorStreamer`

By default, `model.generate()` returns only after the entire sequence is generated. On CPU, a 200-token response at 5 tokens/second takes 40 seconds with no output — then everything appears at once. `TextIteratorStreamer` enables token-by-token output by running generation in a background thread:

```python
import torch
from threading import Thread
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

model_name = "HuggingFaceTB/SmolLM2-1.7B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float32)
model.eval()

# Prepare inputs using the chat template
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "List three tips for writing clean Python code."},
]
input_ids = tokenizer.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_tensors="pt",
)

# Create the streamer
streamer = TextIteratorStreamer(
    tokenizer,
    skip_prompt=True,      # do not re-emit the input tokens
    skip_special_tokens=True,  # do not emit BOS, EOS, etc.
)

# Build the generation kwargs dict
generation_kwargs = {
    "input_ids": input_ids,
    "streamer": streamer,
    "max_new_tokens": 200,
    "do_sample": True,
    "temperature": 0.7,
    "repetition_penalty": 1.1,
}

# Start generation in a background thread
thread = Thread(target=model.generate, kwargs=generation_kwargs)
thread.start()

# Iterate over tokens as they arrive in the main thread
print("Assistant: ", end="", flush=True)
for token_text in streamer:
    print(token_text, end="", flush=True)
print()

# Wait for the generation thread to finish
thread.join()
```

The two-thread requirement is the key design: `model.generate()` runs in a background thread and puts decoded text into a queue; the main thread iterates over that queue via the `streamer` object. This is the standard pattern for streaming in the `transformers` library.

#### 7.3 Batch Inference

When processing many inputs in a script (rather than interactively), you can process them in batches. Note: batch inference does not improve throughput on CPU and may increase memory usage. It is most beneficial on GPU. For CPU-only batch workloads, process inputs one at a time in a loop.

```python
from transformers import pipeline

generator = pipeline(
    "text-generation",
    model="HuggingFaceTB/SmolLM2-1.7B-Instruct",
    device="cpu",
    torch_dtype="float32",
)

prompts = [
    "What is Python?",
    "What is a REST API?",
    "What is version control?",
]

# Pipeline handles batching when given a list
results = generator(
    prompts,
    max_new_tokens=80,
    do_sample=False,       # greedy decoding for consistent batch output
    return_full_text=False,
)

for prompt, result in zip(prompts, results):
    print(f"Q: {prompt}")
    print(f"A: {result[0]['generated_text']}\n")
```

---

### 8. When to Use HF `transformers` vs Ollama vs `llama-cpp-python`

| Criterion | HF `transformers` | Ollama | `llama-cpp-python` |
|---|---|---|---|
| **Model availability** | Entire Hub: 1M+ models, all formats | Ollama library: ~500 models | Any GGUF on the Hub: ~50K files |
| **Ease of use** | Moderate (explicit loading, tokenization) | Very easy (pull and run) | Moderate (model path, GGUF only) |
| **CPU performance** | Good for small models; slow for large float32 | Good (wraps llama.cpp) | Excellent (optimised C++ SIMD kernels) |
| **GPU performance** | Excellent | Good | Good |
| **Model format** | Safetensors (primary) | GGUF (managed internally) | GGUF only |
| **Quantization** | BitsAndBytes 4/8-bit, GPTQ, AWQ | Q-quantized GGUF | Q-quantized GGUF |
| **Fine-tuning support** | Yes (Trainer, PEFT, QLoRA) | No | No |
| **Streaming** | Yes (TextIteratorStreamer, requires threading) | Yes (stream=True) | Yes (stream=True) |
| **REST API built-in** | No (use FastAPI/Flask as wrapper) | Yes (OpenAI-compatible) | No (use llama-server separately) |
| **Memory overhead** | Higher (PyTorch runtime) | Low (managed service) | Lowest (C++ binary) |
| **First-load time** | Slow (Python, PyTorch init) | Fast (preloaded service) | Moderate (C++ load) |

**Decision guide:**

- **Use HF `transformers` when:** you need to access models not in the Ollama library, you plan to fine-tune, you are integrating with the Hugging Face ecosystem (datasets, Trainer, evaluation), or you need tasks beyond text generation (classification, question answering, fill-mask).
- **Use Ollama when:** you want a persistent local model server with an OpenAI-compatible API, you are building integrations with tools that expect a REST endpoint, or you want the quickest path to a working local inference server.
- **Use `llama-cpp-python` when:** CPU performance is critical, you need maximum control over memory and threading, you are distributing a standalone application that loads a model directly, or you are working with GGUF files that are not in the Ollama library.

---

### 9. Recommended Small Models for Local CPU Development

These models are suitable for 8–16 GB RAM machines running inference on CPU. All are available directly on Hugging Face Hub.

| Model | Parameters | Context | License | Hub ID | CPU Use Case |
|---|---|---|---|---|---|
| **SmolLM2-1.7B-Instruct** | 1.7B | 8K | Apache 2.0 | `HuggingFaceTB/SmolLM2-1.7B-Instruct` | Fastest capable instruct model; great for scripting and quick tests |
| **Qwen2.5-1.5B-Instruct** | 1.5B | 32K | Apache 2.0 | `Qwen/Qwen2.5-1.5B-Instruct` | Long-context tasks; strong multilingual; very fast on CPU |
| **Qwen2.5-3B-Instruct** | 3B | 32K | Apache 2.0 | `Qwen/Qwen2.5-3B-Instruct` | Best quality-to-RAM balance in the 3B range; good reasoning |
| **Phi-3-mini-4k-instruct** | 3.8B | 4K | MIT | `microsoft/Phi-3-mini-4k-instruct` | Strong reasoning for its size; excellent for code and logic tasks |
| **Gemma-2-2B-it** | 2.6B | 8K | Gemma (permissive) | `google/gemma-2-2b-it` | High-quality responses; Google's smallest practical instruct model |
| **TinyLlama-1.1B-Chat** | 1.1B | 2K | Apache 2.0 | `TinyLlama/TinyLlama-1.1B-Chat-v1.0` | Ultra-fast prototyping; limited quality but very low RAM (~1.3 GB) |

**GGUF versions** of all models above are available on Hub from trusted converters: `bartowski/` and `unsloth/` are the most actively maintained sources for GGUF quantizations. Search for `bartowski/SmolLM2-1.7B-Instruct-GGUF` on the Hub.

---

## Best Practices

1. **Separate the Hub download step from the inference step in your code.** Download once with `hf_hub_download()` or `hf download`, verify the file is present, then load with `from_pretrained(local_path)`. This avoids unexpected downloads during inference and makes offline operation reliable.

2. **Always set `torch_dtype=torch.float32` explicitly for CPU-only PyTorch.** Many tutorials use `torch_dtype=torch.float16` or `torch_dtype="auto"`. On a CPU-only build of PyTorch, float16 inference is either unsupported or very slow. Set float32 explicitly to avoid silent errors or slowdowns.

3. **Use `model.eval()` and `torch.no_grad()` for inference.** `model.eval()` disables dropout layers (which exist for training). `torch.no_grad()` disables gradient tracking, which cuts memory usage roughly in half for inference. Both are required for correct, efficient inference.

4. **Never use `device_map="auto"` on a CPU-only machine with standard `from_pretrained()`.** `device_map="auto"` requires the `accelerate` library and assumes GPU devices are available. On a CPU-only machine it may silently place the entire model on CPU anyway, or raise an error. For CPU-only inference, omit `device_map` entirely — the model loads to CPU by default.

5. **Use `apply_chat_template()` instead of manually constructing prompt strings.** Every model family has a specific token format for system/user/assistant turns. Manually constructing these strings is error-prone. `apply_chat_template()` reads the correct format from the tokenizer's stored template.

6. **Set `skip_special_tokens=True` in `tokenizer.decode()`** for human-readable output. Without it, the decoded string includes special tokens like `<|begin_of_text|>` and `<|eot_id|>` that are meaningless to end users.

7. **Plan your disk budget before downloading.** A 1.7B model in Safetensors float32 is approximately 7 GB. A Q4_K_M GGUF of the same model is approximately 1 GB. Decide whether you need the Safetensors version (for fine-tuning) or the GGUF version (for CPU inference), and download only what you need.

8. **Monitor memory during the first run of a new model.** Use `htop` or `watch -n 1 free -h` in a second terminal. If the system starts swapping (swap usage increases rapidly), the model is too large for your RAM. Stop the process immediately to avoid minutes-long thrashing.

---

## Use Cases

### Use Case 1: Batch Summarisation Pipeline for Internal Documents

A legal team needs to summarise thousands of contract clauses into single sentences for a searchable index. The data is confidential and cannot be sent to cloud APIs. Using the `transformers` `pipeline()` API with `task="summarization"` and a small encoder-decoder model (such as `google/flan-t5-base`), a Python script reads documents from disk, processes them through the local pipeline, and writes summaries to a CSV. The pipeline runs on CPU overnight. Key concepts from this module: `pipeline()` API, `device="cpu"`, `torch_dtype="float32"`, and the Hub download workflow to fetch the model once before the batch job.

### Use Case 2: Interactive Chat Assistant with Streamed Output

A developer is building an internal chatbot for their team that must run on a laptop with no GPU. They load `SmolLM2-1.7B-Instruct` with `AutoModelForCausalLM`, apply the chat template with `apply_chat_template()`, and use `TextIteratorStreamer` with threading to display tokens as they are generated. The result is a terminal chatbot where responses appear immediately, character by character, making the 5-8 token/second CPU speed feel acceptable to users. Key concepts: `apply_chat_template()`, `TextIteratorStreamer`, threading pattern, and maintaining message history for multi-turn context.

### Use Case 3: Offline Text Classification for Field Research

A researcher is collecting survey responses in a location with no internet access. They need to classify each response into one of five categories in real time. Using the `pipeline()` API with `task="text-classification"` and a fine-tuned BERT-style model downloaded in advance, the classification runs entirely on CPU at under 100ms per response — fast enough for interactive use. Key concepts: choosing the right pipeline task for classification (not text generation), offline-first download workflow, and the Hub's filter by task to find a suitable pre-fine-tuned classifier.

### Use Case 4: Prototype with HF `transformers` Before Committing to Fine-Tuning

A team is evaluating whether fine-tuning a small model on their domain-specific data will improve over a general-purpose baseline. They first test the general baseline using the `pipeline()` API, measure quality on their evaluation set, then decide to fine-tune. Because they are already using the `transformers` library, the transition from inference to fine-tuning requires adding only the `Trainer` and `PEFT` components — no infrastructure change. This is the core advantage of `transformers` over Ollama or `llama-cpp-python` for research workflows. Key concepts: `AutoModelForCausalLM`, `AutoTokenizer`, and understanding that the `transformers` library is the only path among the three runtimes that supports fine-tuning.

---

## Hands-on Examples

### Example 1: Download a Model with `huggingface_hub` and Run Text Generation with `pipeline()`

This example downloads a small model to a local directory using the Python SDK, then runs text generation using `pipeline()`. Before running, ensure your virtual environment is active and `transformers`, `huggingface_hub`, and `torch` are installed.

```python
# example1_pipeline.py

import os
from huggingface_hub import snapshot_download
from transformers import pipeline

MODEL_ID = "HuggingFaceTB/SmolLM2-1.7B-Instruct"
LOCAL_DIR = "./models/SmolLM2-1.7B-Instruct"


def download_if_needed(model_id: str, local_dir: str) -> str:
    """Download the model if not already present; return the local path."""
    # Check for the config file as a proxy for a complete download
    config_path = os.path.join(local_dir, "config.json")
    if os.path.exists(config_path):
        print(f"Model already present at {local_dir}, skipping download.")
        return local_dir

    print(f"Downloading {model_id} to {local_dir} ...")
    print("This downloads approximately 3.4 GB (float16 Safetensors). Be patient.")
    snapshot_download(
        repo_id=model_id,
        local_dir=local_dir,
        allow_patterns=["*.safetensors", "*.json", "*.txt", "tokenizer.model"],
        ignore_patterns=["*.bin", "*.gguf"],  # skip legacy and GGUF formats
    )
    print("Download complete.")
    return local_dir


def run_pipeline_examples(model_path: str) -> None:
    """Load the model via pipeline() and run several text generation examples."""
    print("\nLoading model into pipeline (this may take 30-90 seconds on CPU)...")
    generator = pipeline(
        task="text-generation",
        model=model_path,
        device="cpu",
        torch_dtype="float32",
    )
    print("Pipeline ready.\n")

    # Example A: simple prompt completion
    print("=== Example A: Prompt Completion ===")
    result = generator(
        "The three most important principles of software engineering are",
        max_new_tokens=80,
        do_sample=False,       # greedy for deterministic output
        return_full_text=False,
    )
    print(result[0]["generated_text"])
    print()

    # Example B: chat-style input using the pipeline's messages parameter
    # TextGenerationPipeline accepts messages= for instruct models
    print("=== Example B: Chat-style Input ===")
    messages = [
        {"role": "system", "content": "You are a concise coding assistant. Answer in 2-3 sentences."},
        {"role": "user", "content": "What does the 'yield' keyword do in Python?"},
    ]
    chat_result = generator(
        messages,
        max_new_tokens=100,
        do_sample=True,
        temperature=0.5,
        return_full_text=False,
    )
    # When messages are passed, the generated text is in the last message
    generated_content = chat_result[0]["generated_text"]
    if isinstance(generated_content, list):
        # pipeline returns a messages list when input is messages
        print(generated_content[-1]["content"])
    else:
        print(generated_content)
    print()

    # Example C: summarization-style task (using text-generation, not a dedicated summarizer)
    print("=== Example C: Structured Task via System Prompt ===")
    summary_messages = [
        {
            "role": "system",
            "content": "Summarise the following text in exactly one sentence.",
        },
        {
            "role": "user",
            "content": (
                "The Python programming language was created by Guido van Rossum "
                "and first released in 1991. It emphasises code readability and "
                "supports multiple programming paradigms, including procedural, "
                "object-oriented, and functional programming. Python has become one "
                "of the most popular languages in the world, widely used in web "
                "development, data science, AI, and automation."
            ),
        },
    ]
    summary_result = generator(
        summary_messages,
        max_new_tokens=60,
        do_sample=False,
        return_full_text=False,
    )
    generated_content = summary_result[0]["generated_text"]
    if isinstance(generated_content, list):
        print(generated_content[-1]["content"])
    else:
        print(generated_content)


if __name__ == "__main__":
    model_path = download_if_needed(MODEL_ID, LOCAL_DIR)
    run_pipeline_examples(model_path)
```

To run: `python example1_pipeline.py`

The first run downloads the model and is slow. On subsequent runs, `download_if_needed()` detects the local files and skips the download, loading the pipeline directly from disk.

---

### Example 2: Load a Model with `AutoModelForCausalLM`, Apply a Chat Template, and Stream a Response

This example uses explicit model loading and tokenization, applies the chat template manually, and streams the response token-by-token using `TextIteratorStreamer` and threading. It also maintains a multi-turn conversation history.

Update `LOCAL_DIR` to point to the model directory from Example 1, or change `MODEL_ID` to any model available on Hub.

```python
# example2_chat_stream.py

import torch
from threading import Thread
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

MODEL_ID = "HuggingFaceTB/SmolLM2-1.7B-Instruct"
LOCAL_DIR = "./models/SmolLM2-1.7B-Instruct"


def load_model_and_tokenizer(path: str):
    """Load model and tokenizer from a local directory."""
    print(f"Loading tokenizer from {path}...")
    tokenizer = AutoTokenizer.from_pretrained(path)

    print(f"Loading model from {path} (this takes 20-60 seconds on CPU)...")
    model = AutoModelForCausalLM.from_pretrained(
        path,
        torch_dtype=torch.float32,  # required for CPU-only PyTorch
    )
    model.eval()  # disable dropout layers
    print("Model loaded.\n")
    return model, tokenizer


def generate_streamed(
    model,
    tokenizer,
    messages: list[dict],
    max_new_tokens: int = 200,
    temperature: float = 0.7,
) -> str:
    """
    Apply chat template, generate a streamed response, print tokens as they arrive,
    and return the full generated text.
    """
    # Apply the stored chat template to format messages correctly
    input_ids = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,  # append the assistant turn opening
        return_tensors="pt",
    )

    # Create the streamer
    streamer = TextIteratorStreamer(
        tokenizer,
        skip_prompt=True,          # do not re-emit the input tokens
        skip_special_tokens=True,  # do not emit BOS, EOS, pad tokens
    )

    # Build generation kwargs — streamer is passed as a keyword argument
    generation_kwargs = {
        "input_ids": input_ids,
        "streamer": streamer,
        "max_new_tokens": max_new_tokens,
        "do_sample": temperature > 0.0,
        "temperature": temperature if temperature > 0.0 else 1.0,
        "repetition_penalty": 1.1,
    }

    # Run generation in a background thread so main thread can iterate streamer
    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()

    # Collect tokens as they arrive
    collected: list[str] = []
    for token_text in streamer:
        print(token_text, end="", flush=True)
        collected.append(token_text)

    # Wait for the generation thread to complete
    thread.join()
    print()  # newline after streamed output

    return "".join(collected)


def run_conversation(model, tokenizer) -> None:
    """Run a multi-turn chat session demonstrating history tracking."""
    system_prompt = (
        "You are a helpful Python programming assistant. "
        "Give concise, accurate answers. Use code examples when relevant."
    )

    messages = [{"role": "system", "content": system_prompt}]

    conversation = [
        "What is a Python context manager?",
        "Can you show me a simple example of writing one from scratch?",
        "How does that compare to using @contextlib.contextmanager?",
    ]

    for user_input in conversation:
        print(f"User: {user_input}")
        print("Assistant: ", end="", flush=True)

        messages.append({"role": "user", "content": user_input})

        with torch.no_grad():
            reply = generate_streamed(model, tokenizer, messages, max_new_tokens=250)

        # Append assistant reply to maintain conversation context
        messages.append({"role": "assistant", "content": reply})
        print()


if __name__ == "__main__":
    model, tokenizer = load_model_and_tokenizer(LOCAL_DIR)
    run_conversation(model, tokenizer)
```

To run: `python example2_chat_stream.py`

Watch how the third turn ("How does that compare to using @contextlib.contextmanager?") is answered with awareness of the context manager example from turn two. This is because all prior messages — including the assistant's previous replies — are passed to `apply_chat_template()` on each turn. Without appending the assistant replies to `messages`, the model would have no memory of prior turns.

---

### Example 3: Download a GGUF File from Hub and Run It with `llama-cpp-python`

This example shows the complete workflow for using Hugging Face Hub purely as a model download source, then running inference with `llama-cpp-python` — no `transformers` library involved in the inference step. This is the recommended path for CPU-performance-critical workloads.

```python
# example3_gguf_inference.py

import os
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

# Qwen2.5-1.5B has a GGUF repo on Hub from bartowski
REPO_ID = "bartowski/Qwen2.5-1.5B-Instruct-GGUF"
FILENAME = "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"
LOCAL_DIR = "./models"


def download_gguf(repo_id: str, filename: str, local_dir: str) -> str:
    """Download a single GGUF file from Hub to a local directory."""
    local_path = os.path.join(local_dir, filename)
    if os.path.exists(local_path):
        print(f"GGUF file already present at {local_path}, skipping download.")
        return local_path

    print(f"Downloading {filename} from {repo_id}...")
    print("Approximate download size: ~1.0 GB for Q4_K_M of a 1.5B model.")
    downloaded_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=local_dir,
    )
    print(f"Downloaded to: {downloaded_path}")
    return downloaded_path


def load_gguf_model(model_path: str) -> Llama:
    """Load a GGUF model with llama-cpp-python."""
    print(f"\nLoading GGUF model from {model_path}...")
    llm = Llama(
        model_path=model_path,
        n_ctx=4096,           # context window size
        n_threads=4,          # set to your physical CPU core count
        n_gpu_layers=0,       # 0 = CPU only; -1 = offload all to GPU if available
        verbose=False,        # suppress llama.cpp internal logging
    )
    print("Model loaded.\n")
    return llm


def run_single_turn(llm: Llama, user_message: str, system: str = "") -> str:
    """Run a single-turn chat completion and return the response text."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_message})

    response = llm.create_chat_completion(
        messages=messages,
        max_tokens=256,
        temperature=0.7,
        repeat_penalty=1.1,
        stream=False,
    )
    return response["choices"][0]["message"]["content"]


def run_streamed(llm: Llama, user_message: str, system: str = "") -> str:
    """Run a chat completion with streaming output."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_message})

    stream = llm.create_chat_completion(
        messages=messages,
        max_tokens=300,
        temperature=0.7,
        repeat_penalty=1.1,
        stream=True,
    )

    collected: list[str] = []
    for chunk in stream:
        delta = chunk["choices"][0]["delta"]
        if "content" in delta:
            text = delta["content"]
            print(text, end="", flush=True)
            collected.append(text)
    print()
    return "".join(collected)


if __name__ == "__main__":
    # Step 1: Download the GGUF file from Hub
    model_path = download_gguf(REPO_ID, FILENAME, LOCAL_DIR)

    # Step 2: Load with llama-cpp-python
    llm = load_gguf_model(model_path)

    system_prompt = "You are a concise assistant. Answer in 2-3 sentences."

    # Step 3: Non-streamed single-turn example
    print("=== Non-Streamed Response ===")
    question = "What is the difference between a process and a thread?"
    print(f"User: {question}")
    print(f"Assistant: {run_single_turn(llm, question, system_prompt)}\n")

    # Step 4: Streamed response
    print("=== Streamed Response ===")
    question2 = "Explain what a Python generator is and give a one-line example."
    print(f"User: {question2}")
    print("Assistant: ", end="", flush=True)
    run_streamed(llm, question2, system_prompt)
    print()

    # Step 5: Show the cache management command to free disk space when done
    print("Tip: To see all cached HF models and their disk usage, run:")
    print("  hf cache ls")
    print("To delete cached models interactively, run:")
    print("  huggingface-cli delete-cache")
```

To run: `python example3_gguf_inference.py`

Notice that this example does not import `transformers` at all. `llama-cpp-python` reads the GGUF file's embedded tokenizer and chat template metadata directly, so `apply_chat_template()` is handled internally when you call `create_chat_completion()`. This is the fastest CPU inference path for GGUF models.

---

## Common Pitfalls

### Pitfall 1: Using `device_map="auto"` on a CPU-only Machine

**Description:** Passing `device_map="auto"` to `AutoModelForCausalLM.from_pretrained()` on a machine with no GPU causes warnings, errors, or unexpected behaviour.

**Why it happens:** `device_map="auto"` is an `accelerate` library feature that tries to distribute model layers across all available devices, starting with GPU. On a CPU-only machine, it may raise `ValueError: No GPU available`, require `accelerate` to be installed, or silently work but add overhead.

**Incorrect pattern:**
```python
# This may fail or warn on CPU-only machines
model = AutoModelForCausalLM.from_pretrained(
    "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    device_map="auto",
)
```

**Correct pattern:**
```python
import torch

# Omit device_map entirely — model loads to CPU by default
model = AutoModelForCausalLM.from_pretrained(
    "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    torch_dtype=torch.float32,
)
```

---

### Pitfall 2: Gated Model Download Fails with 401 or 403 Error

**Description:** Attempting to download a gated model (e.g., original Meta Llama repositories) without accepting the license or authenticating.

**Why it happens:** Gated models require you to visit the model page on huggingface.co, accept the license agreement, and provide your HF token when downloading.

**Symptom:**
```
huggingface_hub.errors.GatedRepoError: 401 Client Error: ...
Repository Not Found for url: https://huggingface.co/meta-llama/...
Make sure you have access to the repository.
```

**Correct pattern:**
```bash
# 1. Visit the model page and accept the license:
#    https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct

# 2. Generate a read token at: https://huggingface.co/settings/tokens

# 3. Log in from the CLI:
huggingface-cli login
# Paste your token when prompted

# 4. Now download works:
hf download meta-llama/Llama-3.2-3B-Instruct --local-dir ./models/llama3-3b
```

For many models, third-party GGUF converters (e.g., `bartowski/Llama-3.2-3B-Instruct-GGUF`) host pre-converted GGUF files that are not gated. Check these repositories if you only need a GGUF for inference.

---

### Pitfall 3: Slow First Load Due to Model Compilation and Cache Warming

**Description:** The first call to `pipeline()` or `from_pretrained()` takes far longer than expected — sometimes 2–5 minutes for a small model.

**Why it happens:** First load involves: downloading weights if not cached (one-time, large download), reading weights from disk into RAM (I/O bound — slow on HDDs), initializing the PyTorch runtime, and loading the tokenizer. Subsequent loads of the same model are much faster because weights are already in the OS page cache.

**What to do:**
- Run your script once with a simple test prompt before expecting production-speed results. The second run is representative of real-world performance.
- Use an SSD rather than an HDD for your model storage. For a 3 GB model on an HDD (100 MB/s), disk read alone takes 30 seconds. On an NVMe SSD (3 GB/s), it takes 1 second.
- Load the model once at application startup and keep the reference alive. Do not reload the model on every request.

---

### Pitfall 4: dtype Mismatch — `float16` on CPU-only PyTorch

**Description:** Specifying `torch_dtype=torch.float16` or `torch_dtype="auto"` causes errors or very slow inference on a CPU-only PyTorch installation.

**Why it happens:** The PyTorch CPU build does not include optimised float16 arithmetic kernels. When a model is loaded in float16 on CPU, PyTorch may silently upcast computations to float32 (slow) or raise a RuntimeError.

**Symptom:**
```
RuntimeError: "addmm_impl_cpu_" not implemented for 'Half'
# or very slow inference with no error
```

**Correct pattern:**
```python
import torch

# Always use float32 on CPU-only machines
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.float32,  # not float16, not "auto"
)
```

---

### Pitfall 5: Disk Space Exhaustion from the HF Cache

**Description:** Running out of disk space because the `~/.cache/huggingface/hub/` directory has grown to dozens of gigabytes from accumulated model downloads.

**Why it happens:** `from_pretrained()` and `hf_hub_download()` cache all downloaded files automatically. Each new model version downloaded creates additional blobs in the cache. The cache never self-prunes.

**How to manage it:**

```bash
# See what is cached and how much space each repo uses
hf cache ls

# Delete specific repos interactively (arrow keys to select, Enter to confirm)
huggingface-cli delete-cache

# Or: set a different cache location on a larger disk before downloading
export HF_HUB_CACHE=/mnt/large_drive/.hf_cache
```

Alternatively, use `local_dir` in download calls to bypass the cache entirely and store model files where you manage them:
```python
hf_hub_download(repo_id="...", filename="...", local_dir="./models")
# Files go to ./models/ — manage deletion yourself with rm
```

---

### Pitfall 6: Forgetting `skip_prompt=True` in `TextIteratorStreamer`

**Description:** When streaming, the model's entire input prompt is emitted as the first output tokens before the actual response begins.

**Why it happens:** `TextIteratorStreamer` decodes and emits all tokens, including the input tokens that were passed to `generate()`. Without `skip_prompt=True`, the streamer re-prints the entire formatted prompt (including all special tokens) before the assistant reply.

**Incorrect pattern:**
```python
streamer = TextIteratorStreamer(tokenizer)
# First output: the full formatted prompt including system message and user turn
# Then: the actual response
```

**Correct pattern:**
```python
streamer = TextIteratorStreamer(
    tokenizer,
    skip_prompt=True,          # skip re-emitting the input tokens
    skip_special_tokens=True,  # skip BOS, EOS, and format tokens
)
# Output starts directly with the assistant's response text
```

---

### Pitfall 7: `BitsAndBytes` on CPU has Limited Performance Benefit

**Description:** Installing `bitsandbytes` and loading a model with `load_in_4bit=True` on a CPU-only machine expecting the same speed improvement as on GPU.

**Why it happens:** `bitsandbytes` 4-bit quantization kernels are optimised for CUDA GPUs. On CPU, the quantized matrix multiplications are either emulated in software or use CPU-specific paths that are slower than running a float32 model with `llama-cpp-python`'s CPU-native GGUF kernels.

**Correct approach for CPU-only machines:**
- Use GGUF models with `llama-cpp-python` for CPU performance. GGUF's kernels use AVX2/AVX512 SIMD instructions that are natively fast on modern CPUs.
- Only use `bitsandbytes` on CPU if you specifically need the `transformers` ecosystem (fine-tuning, custom training loops) and need to fit the model in RAM — accept the performance cost.

---

## Summary

- Hugging Face Hub (`huggingface.co`) is a model file repository, not an inference service. The `transformers` library is a separate Python package for running those model files locally. You can use the Hub as a download source for GGUF files without ever importing `transformers`.
- Model Cards tell you the license, architecture, context window, whether the model is gated, and which file formats are available. Always check the license before production use and authenticate with `huggingface-cli login` before downloading gated models.
- The `hf` CLI and `hf_hub_download()` / `snapshot_download()` Python SDK functions handle all downloads, cache management, and authentication. Use `--local-dir` to store files in a directory you manage rather than the default cache.
- The `pipeline()` API is the fastest entry point for common tasks; `AutoModelForCausalLM` with explicit tokenization gives full control. Always set `device="cpu"` and `torch_dtype=torch.float32` explicitly on CPU-only machines.
- Every chat/instruct model has a specific token format (chat template) for system, user, and assistant turns. Always use `tokenizer.apply_chat_template()` to format messages — it reads the correct format from the tokenizer itself. Never manually construct prompt strings for instruct models.
- `TextIteratorStreamer` with threading enables real-time token-by-token output from `model.generate()`. The pattern: spawn a thread that calls `model.generate(kwargs=generation_kwargs)` where `streamer` is in `generation_kwargs`, then iterate over `streamer` in the main thread.
- For CPU performance, GGUF models with `llama-cpp-python` outperform BitsAndBytes-quantized Safetensors models. Use `transformers` + BitsAndBytes when you need the full ecosystem (fine-tuning, PEFT); use GGUF when you need raw inference speed.
- Recommended starting models for CPU development in 2026: `SmolLM2-1.7B-Instruct`, `Qwen2.5-1.5B-Instruct`, `Qwen2.5-3B-Instruct`, `Phi-3-mini-4k-instruct`, and `Gemma-2-2B-it` — all Apache 2.0 or similarly permissive, all available in GGUF format from `bartowski/` on Hub.

---

## Further Reading

- [Hugging Face Transformers Documentation](https://huggingface.co/docs/transformers/index) — The authoritative reference for the `transformers` library (current version 5.5.4 as of 2026); covers `pipeline()`, `AutoModel`, `AutoTokenizer`, generation strategies, quantization, and fine-tuning. Start here for any API reference questions.
- [Hugging Face Hub — Downloading Files Guide](https://huggingface.co/docs/huggingface_hub/en/guides/download) — Official guide to `hf_hub_download()`, `snapshot_download()`, the `hf download` CLI command, `allow_patterns`/`ignore_patterns` for selective download, `local_dir` usage, and the cache directory structure. Essential reading before building download pipelines.
- [Hugging Face Hub — CLI Reference](https://huggingface.co/docs/huggingface_hub/guides/cli) — Complete reference for the `hf` CLI tool, including `hf auth login`, `hf download`, `hf cache ls`, and `hf cache rm` commands with all flags and examples. The source of truth for command-line Hub interaction.
- [Chat Templates Documentation](https://huggingface.co/docs/transformers/main/en/chat_templating) — Explains why chat templates exist, how `apply_chat_template()` works, the `add_generation_prompt` parameter, and how different model families format system, user, and assistant turns. Required reading for anyone building multi-turn applications.
- [Text Generation Guide — Hugging Face](https://huggingface.co/docs/transformers/en/llm_tutorial) — Covers `model.generate()` in depth: all common parameters (`max_new_tokens`, `do_sample`, `temperature`, `repetition_penalty`), decoding strategies (greedy, beam search, sampling), and common pitfalls like output length and padding side. Directly relevant to Examples 2 and 3.
- [BitsAndBytes Quantization — Hugging Face](https://huggingface.co/docs/transformers/en/quantization/bitsandbytes) — Official documentation for `BitsAndBytesConfig`, `load_in_4bit`, `load_in_8bit`, NF4 quantization, nested quantization, and hardware compatibility. Includes memory footprint comparison and guidance on when to use 4-bit vs 8-bit.
- [Hugging Face Hub — Cache Management](https://huggingface.co/docs/huggingface_hub/guides/manage-cache) — Explains the cache directory structure, how to scan with `hf cache ls`, and how to use `huggingface-cli delete-cache` for interactive cleanup. Essential for managing disk space as your model library grows.
- [SmolLM2 Model Card — HuggingFaceTB](https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct) — The Model Card for SmolLM2-1.7B-Instruct, a recommended starting model for this module. Shows how to read benchmark scores, license details, and the Files tab to see available weight formats. A good template for understanding what information a well-written Model Card provides.
