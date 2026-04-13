# Module 4: Multimodal Models and Model Types
> Subject: LLM | Difficulty: Intermediate-Advanced | Estimated Time: 240 minutes

## Objective

After completing this module, you will be able to explain how vision is integrated into large language models at an architectural level, including the roles of vision encoders, image tokenization, and cross-attention. You will be able to send images to the OpenAI, Anthropic, and Gemini APIs using both base64 encoding and URL references, and choose correctly between those two methods. You will understand the key vision-language models available in 2026, what they can and cannot do reliably, and how to structure image prompts for consistent results. You will be able to explain what Large Reasoning Models (LRMs) are, how they differ from standard LLMs, and when they are the right (and wrong) tool. You will be able to configure thinking budgets and reasoning effort levels via the OpenAI, Anthropic, and Gemini APIs. Finally, you will be able to apply a decision framework to route tasks to the correct model type and design multi-model pipelines that combine vision, reasoning, and fast-routing models for real production workloads.

---

## Prerequisites

- Module 1: Basics of Large Language Models — understanding of Transformer architecture, tokenization, inference parameters, and the major LLM families
- Module 2: API Services vs Local Models — hands-on experience calling the OpenAI, Anthropic, and Gemini APIs in Python; understanding of model selection trade-offs
- Module 3: Prompt Engineering — ability to write well-structured prompts, system messages, and few-shot examples across providers
- An active API key for at least one of: OpenAI, Anthropic, or Google Gemini

---

## Key Concepts

### What Multimodality Means

A **multimodal model** is one that can accept inputs from more than one modality — a modality being a type of data channel such as text, images, audio, video, or structured documents. Until around 2023, most deployed LLMs were unimodal: text in, text out. The shift toward multimodality is arguably the most significant architectural expansion in deployed LLMs since the Transformer itself.

The modality combinations in practical use today are:

| Input combination | Current example models | Status |
|---|---|---|
| Text + Image | GPT-4o, Claude Opus 4.6, Gemini 2.5 Flash | Widely deployed |
| Text + Document (PDF) | Claude Opus 4.6, Gemini 2.5 Pro | Widely deployed |
| Text + Audio | Gemini 2.0 Flash (native audio), GPT-4o Audio | Available in API |
| Text + Video | Gemini 2.5 Pro | Available in API |
| Text + Image + Audio | GPT-4o (unified) | Available in API |

This module focuses on the most universally available and practically important case: **text + image**, along with the architectural concepts that apply to all multimodal systems.

---

### How Vision Is Integrated into LLMs

Before an image can participate in a language model's forward pass, it must be converted into the same kind of numerical representation that text tokens use — vectors in the model's embedding space. There are three main architectural strategies for doing this, and understanding them helps you reason about what a vision model can and cannot do.

#### Strategy 1: Vision Encoder + MLP Projection (LLaVA / early approach)

This is the simplest architecture to understand and was used by models like LLaVA (Large Language and Vision Assistant). The pipeline has three stages:

```
[Raw Image]
     |
[Vision Encoder (CLIP ViT)]     -- encodes image patches into vectors
     |
[MLP Projection Layer]          -- maps visual vectors into LLM embedding space
     |
[Text Token Sequence]           -- visual tokens are prepended to text tokens
     |
[LLM Transformer Layers]        -- processes everything together
```

**CLIP (Contrastive Language-Image Pretraining)** is an OpenAI model trained on 400 million image-text pairs. It learns a shared embedding space where semantically related images and text end up geometrically close together. The image encoder component of CLIP is almost always a **Vision Transformer (ViT)**, which divides the image into fixed-size patches (e.g., 16x16 pixels), treats each patch as a "token," and applies self-attention across those patch tokens. A 224x224 pixel image with 16x16 patches becomes a sequence of 196 patch vectors.

These patch vectors pass through a lightweight multi-layer perceptron (MLP) projection layer that reshapes them from CLIP's embedding dimension into the LLM's embedding dimension. The resulting visual tokens are then concatenated with text token embeddings and fed into the LLM together.

#### Strategy 2: Cross-Attention Injection (Flamingo-style)

Introduced by DeepMind's Flamingo model (2022), this approach keeps the visual encoder and language model more cleanly separated. Rather than flooding the token sequence with hundreds of image tokens, visual features are injected into the language model's attention mechanism at dedicated cross-attention layers:

```
[Vision Encoder] --> [Visual Features as Keys and Values]
                                    |
[Text Tokens] -------> [Cross-Attention Layer] --> [LLM continues processing]
```

The LLM's text representations become the **queries**, and the visual features become the **keys and values**. This lets the model "look up" relevant visual information at each layer without expanding the token sequence. It is more memory-efficient for high-resolution inputs.

#### Strategy 3: Unified Multimodal Training (GPT-4o / Gemini native)

The most recent frontier models — GPT-4o and Gemini — were trained end-to-end across text, vision, and sometimes audio from the beginning, rather than bolting a vision encoder onto an existing language model. There is no clean architectural seam between "visual encoder" and "language model." The result is stronger cross-modal reasoning (the model can genuinely integrate what it sees with what it knows linguistically) but requires substantially more training compute and data.

#### Image Resolution and Token Cost

Regardless of architecture, processing a high-resolution image is expensive in tokens. Anthropic documents an approximate rule: `tokens = (width_px * height_px) / 750`. A 1000x1000 pixel image costs roughly 1,334 input tokens — equivalent to several paragraphs of text. Most providers automatically downscale images that exceed a certain resolution before processing. OpenAI offers a `detail` parameter (`low`, `high`, or `auto`) that lets you trade token cost for resolution quality.

```
Low detail:   512x512 → 85 tokens flat (fastest, cheapest, good for simple yes/no tasks)
High detail:  full res, tiled into 512x512 tiles → 85 + 170 per tile (best for reading fine text)
Auto:         model decides based on task (default)
```

---

### Sending Images via API

#### OpenAI (GPT-4o and Compatible Models)

OpenAI uses the chat completions format with a structured `image_url` content block. Despite the name, this block accepts both public URLs and base64-encoded data URLs.

**Method 1: Public URL**

```python
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png",
                        "detail": "auto"
                    }
                },
                {
                    "type": "text",
                    "text": "Describe what you see in this image."
                }
            ]
        }
    ],
    max_tokens=500
)

print(response.choices[0].message.content)
```

**Method 2: Local File as Base64**

```python
import os
import base64
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

image_path = "screenshot.png"
base64_image = encode_image_to_base64(image_path)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}",
                        "detail": "high"
                    }
                },
                {
                    "type": "text",
                    "text": "What error does this error message show? Explain what caused it."
                }
            ]
        }
    ],
    max_tokens=500
)

print(response.choices[0].message.content)
```

**When to use URL vs base64 with OpenAI:** URL references require the image to be publicly accessible on the internet; OpenAI's servers fetch the image during inference. Use base64 for local images, images behind authentication, or any time you cannot guarantee a public URL. The `detail` parameter defaults to `auto`; set it to `low` when you only need a coarse description or binary yes/no judgment, and `high` when reading fine-grained text or inspecting small details.

---

#### Anthropic (Claude)

Anthropic's API uses a different content block format. The image source is a nested object with a `type` field that is either `"base64"` or `"url"`. The system prompt remains a separate top-level field (as covered in Module 3).

**Method 1: Public URL**

```python
import os
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system="You are a precise technical analyst. Describe visual content clearly and concisely.",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": "https://upload.wikimedia.org/wikipedia/commons/a/a7/Camponotus_flavomarginatus_ant.jpg"
                    }
                },
                {
                    "type": "text",
                    "text": "What species is this? Describe its key identifying features."
                }
            ]
        }
    ]
)

print(message.content[0].text)
```

**Method 2: Base64 Encoded**

```python
import os
import base64
import httpx
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Fetch and encode an image
image_url = "https://upload.wikimedia.org/wikipedia/commons/a/a7/Camponotus_flavomarginatus_ant.jpg"
image_data = base64.standard_b64encode(httpx.get(image_url).content).decode("utf-8")
image_media_type = "image/jpeg"

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type,
                        "data": image_data
                    }
                },
                {
                    "type": "text",
                    "text": "Describe this image in detail."
                }
            ]
        }
    ]
)

print(message.content[0].text)
```

**Key notes on Anthropic's image handling:**
- Supported formats: JPEG, PNG, GIF, WebP
- Maximum image size: 5 MB per image via API
- Token cost approximation: `(width_px * height_px) / 750`
- Images should be placed before the text question in the content array for best results
- In multi-turn conversations, if you use base64, the full image bytes are re-sent on every turn. For repeated use, Anthropic's Files API lets you upload once and reference by `file_id`, keeping payload sizes small.

---

#### Google Gemini

Google's new unified `google-genai` SDK (the older `google-generativeai` SDK was deprecated in November 2025) uses `types.Part.from_bytes()` to include images alongside text.

```python
import os
import requests
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# Fetch image bytes from a URL
image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bf/Bucephala-albeola-010.jpg/320px-Bucephala-albeola-010.jpg"
image_bytes = requests.get(image_url).content

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg"
        ),
        "What bird is shown in this image? Describe its markings."
    ]
)

print(response.text)
```

For local files, Gemini also offers a Files API similar to Anthropic's:

```python
import os
from google import genai

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# Upload once; reuse the file reference in multiple requests
uploaded_file = client.files.upload(file="chart.png")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        uploaded_file,
        "Summarize the key trend shown in this chart. Express it as a single sentence."
    ]
)

print(response.text)
```

**Note:** Inline image data must keep the total request size below 20 MB. For larger images or repeated use, prefer the Files API.

---

### Vision Model Capabilities and Limitations

Understanding what vision models reliably do — and what they fail at — is critical for building production systems.

**What vision-language models do well:**

- Reading text embedded in images (OCR): printed text, receipts, signs, screenshots with large fonts
- Identifying objects, animals, landmarks, and common scenes
- Interpreting charts and graphs with clear labels
- Describing layout and spatial relationships in simple diagrams
- Answering yes/no questions about image content
- Classifying images into predefined categories

**What vision-language models struggle with:**

- Precise spatial reasoning: locating exact pixel positions, reading analog clocks, identifying specific chess piece positions
- Counting large numbers of small objects: approximate counts are reliable; exact counts of dense groups are not
- Identifying specific people by name (deliberately constrained by policy on most platforms)
- Detecting whether an image is AI-generated
- Reading very small text or low-contrast text in complex backgrounds
- Interpreting specialized medical imagery such as CT scans or MRIs (not a substitute for professional medical analysis)
- Fine-grained handwriting in cursive or highly stylized scripts

**Practical image prompting strategies:**

1. **Be explicit about what you want extracted.** Rather than "describe this image," say "list each line item shown in this receipt, including the name and price."
2. **Provide context when available.** "This is a screenshot of a Python traceback. Identify the root cause of the error and suggest a fix."
3. **Use reference labels for multi-image comparisons.** "Image 1: [image]. Image 2: [image]. What structural differences do you see between the two diagrams?"
4. **Specify output format.** "Return your answer as a JSON object with keys: title, x_axis_label, y_axis_label, and key_trend."
5. **For documents, ask about specific sections.** "Focus only on the table in the upper-right quadrant of this page."

---

### Practical Vision Use Cases

**Image analysis and scene understanding:**
A retail company uploads shelf photos taken by store staff. A vision model checks whether products are correctly positioned, flags empty shelf spaces, and returns a structured JSON report — replacing a manual audit process.

**Document OCR and extraction:**
A legal operations team sends scanned contracts to a vision model. The prompt asks the model to extract party names, effective date, and termination clauses into a structured JSON object. This works well for clean scans with typed text; handwritten annotations should be treated as approximate.

**Chart and data visualization reading:**
A business analyst uploads a PowerPoint slide as an image. The model reads the chart title, axis labels, and data series to produce a natural-language summary suitable for an email update. For bar charts and line charts with labeled axes, accuracy is high. For 3D pie charts or charts without clear data labels, errors are more common.

**Screenshot debugging:**
A developer copies a stack trace screenshot into a chat interface. The model reads the error message, identifies the offending line number, and suggests probable causes. This is one of the highest-accuracy vision use cases because the text is rendered clearly and the domain is well-represented in training data.

---

### Local Multimodal Models

Running vision-capable models locally gives you full data privacy, no per-token cost, and offline capability. The trade-off is hardware requirements and lower accuracy compared to frontier API models. As of 2026 the local multimodal ecosystem has matured significantly — several models run well on consumer GPUs.

#### Available Local Vision Models

| Model | Parameters | VRAM Required | Architecture | Best For |
|---|---|---|---|---|
| LLaVA 1.6 (Mistral 7B base) | 7B | ~6 GB | CLIP ViT + MLP | General image Q&A, fast responses |
| LLaVA 1.6 (34B) | 34B | ~20 GB | CLIP ViT + MLP | Higher accuracy, complex layouts |
| BakLLaVA | 7B | ~6 GB | CLIP ViT + MLP | Strong OCR and document reading |
| moondream2 | 1.8B | ~2 GB | SigLIP + Phi-2 | Lightweight; embedded/edge use |
| LLaMA 3.2 Vision (11B) | 11B | ~8 GB | Cross-attention | Best local accuracy; Meta open-weight |
| LLaMA 3.2 Vision (90B) | 90B | ~50 GB | Cross-attention | Near-frontier quality; multi-GPU |
| MiniCPM-V 2.6 | 8B | ~6 GB | SigLIP + MiniCPM | Strong OCR; efficient on CPU |
| Qwen2-VL (7B) | 7B | ~6 GB | Unified | Document/chart reading; multilingual |
| Qwen2-VL (72B) | 72B | ~45 GB | Unified | High-accuracy; near GPT-4V quality |

**Quantization note:** All models above can be run in 4-bit (Q4_K_M) or 8-bit (Q8) quantization via Ollama or llama.cpp, cutting VRAM requirements roughly in half at a small accuracy cost. A Q4_K_M LLaMA 3.2 Vision 11B fits in ~6 GB VRAM.

---

#### Running Local Vision Models with Ollama

Ollama supports multimodal models with the same simple interface used for text-only models. Images are passed as a list of base64-encoded strings or file paths alongside the prompt.

**Installation and setup:**

```bash
# Pull a vision-capable model
ollama pull llava:latest           # LLaVA 1.6 7B — general purpose
ollama pull llama3.2-vision:11b    # LLaMA 3.2 Vision 11B — best local accuracy
ollama pull moondream              # moondream2 1.8B — minimal VRAM
ollama pull qwen2-vl:7b            # Qwen2-VL 7B — strong OCR and documents
```

**CLI usage — directly from terminal:**

```bash
# Ask a question about a local image file
ollama run llava "Describe what you see in this image." --image ./screenshot.png

# Read text from a receipt
ollama run llava "List each line item and its price from this receipt." --image ./receipt.jpg
```

**Python — Ollama REST API with base64 image:**

```python
import ollama
import base64
from pathlib import Path

def ask_about_image(image_path: str, question: str, model: str = "llava") -> str:
    image_data = base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")
    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": question,
                "images": [image_data],
            }
        ],
    )
    return response["message"]["content"]

# Example: read a chart
result = ask_about_image(
    image_path="./sales_chart.png",
    question="What is the highest value shown in this chart, and in which month did it occur?",
    model="llama3.2-vision:11b",
)
print(result)
```

**Python — Ollama HTTP REST API (no SDK required):**

```python
import requests
import base64
from pathlib import Path

def query_vision_model(image_path: str, prompt: str, model: str = "llava") -> str:
    image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
    }
    response = requests.post("http://localhost:11434/api/generate", json=payload)
    response.raise_for_status()
    return response.json()["response"]

print(query_vision_model("./diagram.png", "Explain the flow shown in this diagram."))
```

---

#### Running Local Vision Models with llama.cpp

For maximum control over quantization and hardware tuning, llama.cpp supports multimodal models via the `llava-cli` tool and its Python bindings (`llama-cpp-python`).

```bash
# Build llama.cpp with GPU support (CUDA example)
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j

# Download a LLaVA GGUF model + its multimodal projector
# (models available on Hugging Face — search "llava gguf")

# Run inference from the CLI
./build/bin/llava-cli \
  -m ./models/llava-v1.6-mistral-7b.Q4_K_M.gguf \
  --mmproj ./models/llava-v1.6-mistral-7b-mmproj.gguf \
  --image ./photo.jpg \
  -p "Describe this image in detail."
```

**Python bindings with llama-cpp-python:**

```python
from llama_cpp import Llama
from llama_cpp.llama_chat_format import LlavaXxxx16ChatHandler

chat_handler = LlavaXxxx16ChatHandler(
    clip_model_path="./models/llava-v1.6-mistral-7b-mmproj.gguf"
)

llm = Llama(
    model_path="./models/llava-v1.6-mistral-7b.Q4_K_M.gguf",
    chat_handler=chat_handler,
    n_ctx=4096,
    n_gpu_layers=-1,  # offload all layers to GPU
)

response = llm.create_chat_completion(
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What objects are in this image?"},
                {"type": "image_url", "image_url": {"url": "file:///path/to/image.jpg"}},
            ],
        }
    ]
)
print(response["choices"][0]["message"]["content"])
```

---

#### Choosing a Local Vision Model

| Scenario | Recommended model | Reason |
|---|---|---|
| VRAM ≤ 4 GB | moondream2 | Only 2 GB; runs on integrated GPU |
| VRAM 6–8 GB | LLaVA 1.6 7B or LLaMA 3.2 Vision 11B Q4 | Best quality in this range |
| VRAM 10–16 GB | LLaMA 3.2 Vision 11B (FP16) | Full precision; strong accuracy |
| VRAM 20–24 GB | LLaVA 1.6 34B Q4 or Qwen2-VL 7B FP16 | High accuracy, document reading |
| VRAM 40–50 GB | LLaMA 3.2 Vision 90B Q4 | Near-frontier quality |
| OCR / documents | Qwen2-VL or MiniCPM-V | Trained specifically on dense text |
| Multilingual images | Qwen2-VL | Strong non-English text recognition |
| CPU-only (slow) | moondream2 or MiniCPM-V 2.6 Q4 | Feasible; expect 1–5 tokens/sec |

**Key limitation vs API models:** Local vision models as of 2026 are still noticeably weaker than GPT-4o and Claude Opus 4.6 on tasks requiring complex reasoning about image content. They are competitive on straightforward OCR, object identification, and basic chart reading. For high-stakes extraction tasks, validate outputs carefully or use an API model as a fallback.

---

### Thinking Models: Large Reasoning Models (LRMs)

A **Large Reasoning Model (LRM)** is a language model trained or fine-tuned to produce an extended internal reasoning process before generating its final answer. This internal process is commonly called a "thinking" or "chain-of-thought" scratchpad. In most implementations, you pay for the tokens consumed by this reasoning process even when the scratchpad is not shown in full in the final response.

The core trade-off is simple: **more time and tokens in exchange for higher accuracy on hard problems.** A standard GPT-4o call might complete a response in 1–3 seconds; an o3 call on the same problem might take 15–60 seconds but reason through edge cases, correct initial errors, and produce a more reliable answer.

#### How Thinking Models Differ from Standard LLMs

| Dimension | Standard LLM (e.g., GPT-4o, Claude Sonnet) | Thinking Model (e.g., o3, Claude + extended thinking) |
|---|---|---|
| Reasoning mechanism | Implicit, in-weights | Explicit scratchpad; extended chain-of-thought |
| Latency | Low (1–10 seconds typical) | High (10–120 seconds on hard problems) |
| Token cost | Moderate (output only) | High (output + reasoning tokens) |
| Temperature | Controllable | Often fixed or ignored internally |
| System prompt | Standard | Supported; some restrictions apply per provider |
| Best problem type | Fast, well-defined, creative | Multi-step logic, math, complex code, planning |
| Worst problem type | Deep multi-step derivation | Simple lookup, fast customer response, routing |

---

### OpenAI Reasoning Models: o1, o3, o4-mini

OpenAI's o-series models are trained with extended chain-of-thought reasoning. They are called using the standard `client.chat.completions.create()` interface with the `reasoning_effort` parameter replacing temperature as the primary control knob.

**Current o-series models (as of early 2026):**

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Notes |
|---|---|---|---|
| o3 | $2.00 | $8.00 | Highest-capability reasoning; best for complex STEM and coding |
| o4-mini | $1.10 | $4.40 | Faster and cheaper; strong coding and math; also supports vision |
| o1-mini | (legacy) | (legacy) | Superseded by o4-mini |

The `reasoning_effort` parameter accepts `"low"`, `"medium"`, or `"high"`. Low favors speed and token efficiency; high enables deeper reasoning at greater cost and latency. The default is `"medium"`.

```python
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Using o3 with high reasoning effort for a complex problem
response = client.chat.completions.create(
    model="o3",
    reasoning_effort="high",
    messages=[
        {
            "role": "user",
            "content": (
                "A company has 5 servers. Each server can handle 200 requests/second. "
                "Requests arrive as a Poisson process at 900 requests/second. "
                "Each request takes exactly 10ms to process. "
                "What is the probability that a new request must wait? "
                "Show your work step by step."
            )
        }
    ]
)

print(response.choices[0].message.content)
```

For lower-stakes tasks where you want some reasoning but not the full cost:

```python
# Using o4-mini with low reasoning effort for a moderately complex code task
response = client.chat.completions.create(
    model="o4-mini",
    reasoning_effort="low",
    messages=[
        {
            "role": "user",
            "content": "Write a Python function that validates an email address using only the standard library. Include edge case handling."
        }
    ]
)

print(response.choices[0].message.content)
```

**Important restrictions for OpenAI o-series models:**
- The `temperature` parameter is not supported and is ignored if provided
- `top_p` and `presence_penalty` are also unsupported
- The system message role is supported but internally treated as a high-priority user message in some model versions; test behavior for your specific use case
- Streaming is supported

---

### Anthropic Extended Thinking

Claude's extended thinking is controlled by a `thinking` parameter at the top level of the request. It works on Claude Sonnet 4.6, Claude Opus 4.6, and several earlier models.

The `budget_tokens` field sets the maximum number of tokens Claude may spend on internal reasoning before producing its final response. A higher budget allows deeper reasoning but increases both latency and cost (you are billed for thinking tokens at the same per-token rate as output tokens).

For Claude Opus 4.6 and Claude Sonnet 4.6, Anthropic recommends `"type": "adaptive"` which lets the model decide how much thinking is needed for a given request:

```python
import os
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Adaptive thinking: model decides the thinking depth
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=16000,
    thinking={"type": "adaptive"},
    messages=[
        {
            "role": "user",
            "content": (
                "A binary tree has nodes numbered 1 to 15 in level-order (breadth-first). "
                "Write a Python function that, given two node numbers, returns their lowest "
                "common ancestor. Then trace through nodes 11 and 14 step by step."
            )
        }
    ]
)

for block in response.content:
    if block.type == "thinking":
        print(f"[Internal Reasoning Summary]: {block.thinking[:200]}...")
    elif block.type == "text":
        print(f"[Response]: {block.text}")
```

For earlier models (Sonnet 4.5, Opus 4.5, and older), use `"type": "enabled"` with an explicit `budget_tokens`:

```python
import os
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Manual thinking budget: explicit token ceiling
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000
    },
    messages=[
        {
            "role": "user",
            "content": "Prove that there are infinitely many primes of the form 4k + 3."
        }
    ]
)

for block in response.content:
    if block.type == "thinking":
        print(f"[Thinking]: {block.thinking}")
    elif block.type == "text":
        print(f"[Answer]: {block.text}")
```

**Key rules for Claude extended thinking:**
- `budget_tokens` must be less than `max_tokens` (except when using interleaved thinking with tool use)
- You are charged for the full thinking tokens, even when `display` is set to `"summarized"` or `"omitted"`
- `tool_choice: {"type": "any"}` and forced specific tool calls are not supported with thinking enabled
- In tool-use loops, you must pass the thinking block back to the API alongside the tool-use block in the assistant turn; omitting it causes a 400 error

---

### Google Gemini Thinking Models

Google introduced thinking capabilities starting with Gemini 2.5, controlled via a `thinking_config` object. The Gemini 2.5 and 3 series support these features natively.

```python
import os
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# Gemini 2.5 Flash with an explicit thinking budget
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Solve this step by step: What is the 50th Fibonacci number? Derive it from first principles.",
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=1024)
    )
)

print(response.text)
```

For Gemini 3 series models, the `thinking_level` parameter replaces `thinking_budget`:

```python
import os
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# Gemini 3 Flash with high thinking level
response = client.models.generate_content(
    model="gemini-3-flash-preview",  # verify current model ID at aistudio.google.com — may be gemini-2.5-flash if Gemini 3 is not yet released
    contents="Design a load balancer algorithm for 10,000 concurrent requests with sticky sessions. Analyze trade-offs.",
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level="high",
            include_thoughts=True
        )
    )
)

# Access thoughts and final response separately
for part in response.candidates[0].content.parts:
    if hasattr(part, "thought") and part.thought:
        print(f"[Thought]: {part.text[:300]}...")
    else:
        print(f"[Response]: {part.text}")
```

The Gemini `thinking_level` parameter accepts: `"minimal"`, `"low"`, `"medium"`, and `"high"`. Setting `thinking_budget=0` disables thinking; `-1` enables dynamic thinking where the model allocates what it needs.

---

### DeepSeek-R1: Open-Weight Reasoning

DeepSeek-R1 is a notable open-weight reasoning model that achieves performance comparable to o1 on mathematics, coding, and logic benchmarks. It is available via DeepSeek's own API and through hosting providers like OpenRouter. The model exposes its chain-of-thought as `reasoning_content` in the response, separate from the final `content` answer.

```python
import os
from openai import OpenAI

# DeepSeek's API is OpenAI-compatible
client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-reasoner",
    messages=[
        {
            "role": "user",
            "content": "Write a Python function to detect if a directed graph has a cycle. Explain your approach."
        }
    ]
)

# Access reasoning content and final answer
message = response.choices[0].message
if hasattr(message, "reasoning_content") and message.reasoning_content:
    print("[Reasoning]:")
    print(message.reasoning_content[:500])
    print("\n[Final Answer]:")
print(message.content)
```

**Important:** In multi-turn conversations with DeepSeek-R1, pass only the `content` field from the assistant's previous turn back into the next request's message history. Do not include `reasoning_content` in the conversation history; doing so returns a 400 error. The chain-of-thought is ephemeral — it is not carried forward.

---

### Current Model Landscape: Comparison Table

The following table reflects the model landscape as of early 2026. Pricing is approximate and subject to change; always verify at the provider's pricing page before committing to a cost estimate.

| Model | Provider | Type | Vision | Thinking | Context | Input $/1M | Output $/1M | Primary Strength |
|---|---|---|---|---|---|---|---|---|
| GPT-4o | OpenAI | Standard LLM | Yes | No | 128K | $2.50 | $10.00 | Balanced quality and speed |
| o3 | OpenAI | Reasoning (LRM) | No | Yes | 200K | $2.00 | $8.00 | Complex STEM and coding |
| o4-mini | OpenAI | Reasoning (LRM) | Yes | Yes | 200K | $1.10 | $4.40 | Efficient reasoning + vision |
| Claude Opus 4.6 | Anthropic | Standard / Thinking | Yes | Yes (adaptive) | 1M | $5.00 | $25.00 | Deep reasoning, long context |
| Claude Sonnet 4.6 | Anthropic | Standard / Thinking | Yes | Yes (adaptive) | 1M | $3.00 | $15.00 | Production balance |
| Claude Haiku 4.5 | Anthropic | Standard | Yes | Yes | 200K | $1.00 | $5.00 | Fast, cost-effective routing |
| Gemini 2.5 Flash | Google | Standard / Thinking | Yes | Yes | 1M | ~$0.15 | ~$0.60 | High volume, multimodal |
| Gemini 2.5 Pro | Google | Standard / Thinking | Yes | Yes | 2M | ~$1.25 | ~$5.00 | Long documents, video |
| Gemini 3 Flash | Google | Standard / Thinking | Yes | Yes | 1M | Check docs | Check docs | Latest fast model |
| DeepSeek-R1 | DeepSeek | Reasoning (LRM) | No | Yes (chain-of-thought) | 64K | $0.55 | $2.19 | Open-weight reasoning |
| LLaVA 1.6 (7B) | Meta/Community | Standard (local) | Yes | No | 4K | Free (self-hosted) | Free | Local vision, low VRAM |
| LLaVA 1.6 (34B) | Meta/Community | Standard (local) | Yes | No | 4K | Free (self-hosted) | Free | Local vision, higher accuracy |
| LLaMA 3.2 Vision (11B) | Meta | Standard (local) | Yes | No | 128K | Free (self-hosted) | Free | Best local vision accuracy |
| Qwen2-VL (7B) | Alibaba | Standard (local) | Yes | No | 32K | Free (self-hosted) | Free | Local OCR, multilingual |
| moondream2 | Vikhyatk | Standard (local) | Yes | No | 2K | Free (self-hosted) | Free | Edge / minimal VRAM (2 GB) |

**Notes:** Vision support means the model accepts image inputs. Thinking/reasoning support means the model has a configurable extended reasoning mode. Local models run on your own hardware with no per-token cost but require GPU resources — see the Local Multimodal Models section for VRAM requirements.

---

### When NOT to Use a Reasoning Model

The latency and cost premium of reasoning models is only justified for problems where additional deliberation actually helps. Applying a thinking model to simple tasks wastes both money and time.

**Do not use a reasoning model when:**
- The task is a simple factual lookup ("What is the capital of France?")
- The task is formatting or transformation with a clear rule ("Convert this CSV to JSON")
- The task is routing or classification ("Is this message a complaint, a question, or a compliment?")
- Latency is critical and errors are recoverable (a chatbot that should respond within 2 seconds)
- You are iterating rapidly on a prompt — use a fast model for development, upgrade only for final testing

**Do use a reasoning model when:**
- The task involves mathematical proof or derivation
- The task is a complex debugging session with multiple interacting components
- The task requires multi-step planning with constraint satisfaction
- The output has high stakes and is costly to verify manually
- The task involves logic puzzles, game theory, or formal reasoning
- You are building an agentic workflow where incorrect intermediate steps compound into failures

---

### Choosing the Right Model Type: Decision Framework

The following framework maps task characteristics to model types. Use it as a starting point, not a rigid rule — actual performance varies by task and should always be validated empirically.

```
                        TASK ASSESSMENT

Is image or document input required?
   YES --> Use a vision-capable model
           - High accuracy needed + complex reasoning: Claude Opus 4.6 / Gemini 2.5 Pro
           - Speed + cost matters: Claude Sonnet 4.6 / Gemini 2.5 Flash / GPT-4o
           - Local / private data: LLaMA 3.2 Vision or LLaVA via Ollama (see Local Multimodal Models section)
   NO  --> Continue below

Is the problem multi-step, logical, or mathematical?
   YES --> Consider a reasoning model
           - Maximum capability: o3 (reasoning_effort: high)
           - Cost-efficient reasoning: o4-mini / DeepSeek-R1
           - Claude with adaptive thinking: claude-sonnet-4-6 (thinking: adaptive)
   NO  --> Use a standard LLM

Is latency the primary constraint (< 3 seconds)?
   YES --> Fast tier: Claude Haiku 4.5 / Gemini 2.5 Flash / GPT-4o
   NO  --> Use the most capable model that fits budget
```

#### The Cost / Latency / Quality Triangle

Every model choice involves a trade-off among three dimensions. You can optimize for at most two of the three at any given point:

```
              QUALITY
              /\
             /  \
            /    \
           /      \
LATENCY --/--------\ COST

Fast + Cheap   = Lower quality (Haiku, Gemini Flash)
Fast + Quality = More expensive (GPT-4o, Sonnet)
Quality + Cheap = Slower (DeepSeek-R1, local LLaVA)
```

In practice, most production systems do not pick a single point on this triangle. They build a **tiered pipeline** that routes tasks to the appropriate model.

---

### Multi-Model Pipeline Design

A practical production pipeline often chains multiple model types rather than routing everything through one model. Here is a worked example of a document analysis assistant that handles screenshots, PDFs, and text questions.

**Architecture:**

```
User Input
    |
[Stage 1: Fast Classifier]          -- Claude Haiku 4.5
    Determines: text-only, vision-required, or complex-reasoning
    |
    |-- text-only, simple --> [Stage 2a: Standard LLM]   -- Claude Sonnet 4.6
    |
    |-- vision-required   --> [Stage 2b: Vision Model]   -- Claude Sonnet 4.6 (vision)
    |                             Extract structured data from image
    |                                   |
    |                         [Stage 3: Optional reasoning] -- o3 / Claude + thinking
    |                             If extracted data needs deep analysis
    |
    |-- complex-reasoning --> [Stage 2c: Reasoning Model] -- o3 or Claude + thinking
    |
Output: Structured JSON or prose response
```

**Implementation skeleton:**

```python
import os
import json
import anthropic
from openai import OpenAI

anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def classify_task(user_message: str, has_image: bool) -> str:
    """
    Stage 1: Use the cheapest fast model to classify the incoming task.
    Returns one of: 'simple_text', 'vision', 'complex_reasoning'
    """
    classification_prompt = f"""Classify this user request into exactly one category.
Return only the category name as a single word.

Categories:
- simple_text: factual question, summary, translation, formatting, or generation task with no image
- vision: request that requires analyzing an image or document
- complex_reasoning: mathematical proof, debugging across multiple systems, logic puzzle, or multi-step planning

Has image attached: {has_image}
User message: {user_message}

Category:"""

    response = anthropic_client.messages.create(
        model="claude-haiku-4-5",  # short alias — routes to latest Haiku 4.5 version
        max_tokens=20,
        messages=[{"role": "user", "content": classification_prompt}]
    )
    return response.content[0].text.strip().lower()


def handle_vision_task(user_message: str, image_base64: str, media_type: str) -> str:
    """
    Stage 2b: Vision model extracts structured information from the image.
    """
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system="Extract information from images precisely and return structured data.",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64
                        }
                    },
                    {"type": "text", "text": user_message}
                ]
            }
        ]
    )
    return response.content[0].text


def handle_reasoning_task(user_message: str) -> str:
    """
    Stage 2c: Reasoning model for complex analytical problems.
    """
    response = openai_client.chat.completions.create(
        model="o4-mini",
        reasoning_effort="medium",
        messages=[{"role": "user", "content": user_message}]
    )
    return response.choices[0].message.content


def handle_simple_text(user_message: str) -> str:
    """
    Stage 2a: Standard model for routine text tasks.
    """
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": user_message}]
    )
    return response.content[0].text


def dispatch(user_message: str, image_base64: str = None, media_type: str = None) -> str:
    """
    Main dispatcher: classify then route.
    """
    has_image = image_base64 is not None
    task_type = classify_task(user_message, has_image)

    if task_type == "vision" and has_image:
        return handle_vision_task(user_message, image_base64, media_type)
    elif task_type == "complex_reasoning":
        return handle_reasoning_task(user_message)
    else:
        return handle_simple_text(user_message)
```

**Why this pattern works:**
- The classifier uses Claude Haiku (the cheapest tier) so its cost is negligible — a few tenths of a cent per dispatch decision
- Vision and reasoning models are only invoked when genuinely needed, avoiding unnecessary spend on the expensive tiers
- The pipeline is easy to extend: add a new `task_type` branch without touching the other handlers
- Each handler can be replaced independently as better models become available

**Pipeline scenario: chart summarization for a business report**

A user uploads a PNG of a quarterly revenue chart and asks "Summarize the key trend and flag any anomalies." The dispatcher classifies this as `vision`, sends it to Claude Sonnet 4.6 with a structured extraction prompt, and gets back a JSON object with `trend`, `anomalies`, and `data_points`. If the user then asks "Given this trend, what would revenues look like in Q4 if growth slows by 30%?" — a projection requiring arithmetic reasoning — the dispatcher re-classifies this as `complex_reasoning` and hands off to o4-mini, which receives the JSON context extracted in the previous step.

---

## Hands-on Examples

### Example 1: Screenshot Error Diagnosis

**Goal:** Send a screenshot of an error message to a vision model and receive a structured diagnosis.

**Setup:** You will need an API key for Anthropic and a PNG or JPEG image file on disk. If you do not have an error screenshot handy, take a screenshot of any text-heavy web page.

```python
import os
import base64
import json
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def diagnose_screenshot(image_path: str) -> dict:
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # Determine media type from extension
    ext = image_path.rsplit(".", 1)[-1].lower()
    media_type_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    media_type = media_type_map.get(ext, "image/png")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=(
            "You are a software debugging assistant. When given a screenshot of an error, "
            "return a JSON object with these exact keys: "
            "error_type, error_message, likely_cause, suggested_fix. "
            "If no error is visible, return {\"error_type\": \"none\"}."
        ),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data
                        }
                    },
                    {
                        "type": "text",
                        "text": "Analyze this screenshot and return the structured diagnosis."
                    }
                ]
            }
        ]
    )

    raw = response.content[0].text
    # Strip markdown code fences if the model wrapped the JSON
    if raw.strip().startswith("```"):
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    return json.loads(raw)


if __name__ == "__main__":
    result = diagnose_screenshot("error_screenshot.png")
    print(json.dumps(result, indent=2))
```

**Expected output structure:**
```json
{
  "error_type": "NameError",
  "error_message": "name 'pd' is not defined",
  "likely_cause": "The pandas library was imported under a different alias or not imported at all",
  "suggested_fix": "Add 'import pandas as pd' at the top of the file"
}
```

---

### Example 2: Extended Reasoning for a Multi-Step Problem

**Goal:** Use Claude with adaptive thinking to solve a problem that rewards deliberate step-by-step analysis, and observe the thinking output.

```python
import os
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

problem = """
A software team has the following constraints:
- 3 developers: Alice, Bob, Carol
- 4 tasks: API, Frontend, Database, Testing
- Alice cannot work on Frontend (no React experience)
- Bob cannot work on Database (no SQL experience)
- Carol must work on Testing (contractual requirement)
- Each developer gets exactly one task
- The remaining unassigned task can go to any developer

Find all valid task assignments. For each valid assignment,
calculate the total "risk score" where:
- Alice on API = 1, Alice on Database = 3, Alice on Testing = 2
- Bob on API = 2, Bob on Frontend = 1, Bob on Testing = 3
- Carol on Testing = 1

Identify the lowest-risk valid assignment.
"""

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8000,
    thinking={"type": "adaptive"},
    messages=[{"role": "user", "content": problem}]
)

print("=" * 60)
for block in response.content:
    if block.type == "thinking":
        # Show only the first 400 chars of reasoning to illustrate it exists
        print(f"[Reasoning process ({len(block.thinking)} chars)]:")
        print(block.thinking[:400] + "...\n")
    elif block.type == "text":
        print("[Final Answer]:")
        print(block.text)
print("=" * 60)
print(f"\nTotal tokens used: {response.usage.input_tokens} input, {response.usage.output_tokens} output")
```

---

### Example 3: Multi-Model Routing in Practice

**Goal:** Run the dispatcher built in the Key Concepts section with two different inputs — one text-only, one that requires reasoning — and observe the routing behavior.

```python
import os
import anthropic
from openai import OpenAI

anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# --- Paste the classify_task, handle_simple_text, and handle_reasoning_task
# --- functions from the Key Concepts section here before running ---

test_cases = [
    {
        "label": "Simple text task",
        "message": "Translate the following sentence to Spanish: 'The deployment was successful.'",
        "image": None
    },
    {
        "label": "Complex reasoning task",
        "message": (
            "I have a recursive function that computes Fibonacci numbers. "
            "It works correctly but is too slow for fib(40). "
            "Explain three different optimization strategies, compare their time and space complexity, "
            "and recommend the best one for a production system where fib(n) is called frequently "
            "with the same n values."
        ),
        "image": None
    }
]

for case in test_cases:
    print(f"\n{'='*60}")
    print(f"Test: {case['label']}")
    print(f"Message: {case['message'][:80]}...")
    task_type = classify_task(case["message"], has_image=False)
    print(f"Classified as: {task_type}")
    result = dispatch(case["message"])
    print(f"Response (first 200 chars): {result[:200]}...")
```

---

## Summary

This module covered the two major expansions to the standard LLM model type: **multimodal (vision) models** and **reasoning (thinking) models**.

For vision models, you learned how images are transformed into token-space through vision encoders like CLIP ViT, MLP projections, or cross-attention, and how the three major API providers — OpenAI, Anthropic, and Gemini — handle image inputs with different content block schemas. You saw the practical trade-offs between base64 encoding (no public URL required; larger payloads) and URL references (smaller payloads; requires public access), and explored the real limits of what vision models can and cannot reliably do.

For reasoning models, you learned how the thinking scratchpad architecture produces more accurate results on complex problems at the cost of latency and token spend. You practiced configuring OpenAI's `reasoning_effort`, Anthropic's `thinking` parameter (both `"adaptive"` for new models and explicit `budget_tokens` for older ones), and Gemini's `thinking_config`. You also saw DeepSeek-R1 as an open-weight alternative with an OpenAI-compatible interface.

Finally, the decision framework and multi-model pipeline pattern showed you how to combine these model types in production: a cheap fast model classifies each incoming request, a vision model handles media input, a reasoning model handles hard analytical work, and a standard LLM handles everything in between.

---

## Further Reading

- [OpenAI Images and Vision Guide](https://platform.openai.com/docs/guides/images-vision) — Official documentation for GPT-4o vision inputs, including the `detail` parameter, base64 vs URL usage, and supported image formats.
- [Anthropic Vision Documentation](https://platform.claude.com/docs/en/build-with-claude/vision) — Complete reference for Claude's image handling, including token cost calculation, image size limits, the Files API for repeated image use, and known limitations like spatial reasoning gaps.
- [Anthropic Extended Thinking Guide](https://platform.claude.com/docs/en/build-with-claude/extended-thinking) — Detailed documentation on the `thinking` parameter, `budget_tokens`, streaming support, and the rules around thinking blocks in tool-use loops.
- [OpenAI Reasoning Models Guide](https://platform.openai.com/docs/guides/reasoning) — Official reference for the o-series models, `reasoning_effort` values, API restrictions (no temperature), and guidance on when to use o3 versus o4-mini.
- [Gemini Thinking API](https://ai.google.dev/gemini-api/docs/thinking) — Google's documentation on `thinking_config`, `thinkingBudget`, and `thinking_level` across the Gemini 2.5 and 3 model families, including how to access thought summaries in responses.
- [DeepSeek-R1 Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode) — DeepSeek's API documentation for the `deepseek-reasoner` model, covering the `reasoning_content` field, multi-turn conversation rules, and unsupported parameters.
- [Understanding Multimodal LLMs (Sebastian Raschka)](https://magazine.sebastianraschka.com/p/understanding-multimodal-llms) — An accessible technical deep-dive into the architectures of multimodal models, including CLIP, LLaVA, Flamingo, and the unified approach used by GPT-4o and Gemini.
- [Google Image Understanding API](https://ai.google.dev/gemini-api/docs/vision?lang=python) — Python examples for the `google-genai` SDK showing `types.Part.from_bytes()`, the Files API, and inline vs uploaded image handling.

---

## Glossary

**Base64 encoding:** A binary-to-text encoding scheme that converts arbitrary binary data (such as an image file) into a string of ASCII characters. Used to embed image bytes directly in JSON API payloads.

**CLIP (Contrastive Language-Image Pretraining):** An OpenAI model trained on 400 million image-text pairs that learns a shared embedding space for images and text. Its image encoder is widely used as the visual backbone in vision-language models.

**Cross-attention:** An attention mechanism where queries come from one modality (e.g., text) and keys and values come from another (e.g., image features). Used in Flamingo-style architectures to inject visual information into language models without expanding the text token sequence.

**Extended thinking / Adaptive thinking:** Anthropic's terms for Claude's reasoning mode. Extended thinking uses a fixed `budget_tokens` ceiling; adaptive thinking lets the model decide how much reasoning to apply per request.

**LRM (Large Reasoning Model):** An informal term for a language model trained to produce an extended chain-of-thought scratchpad before generating its final answer. OpenAI's o-series and Anthropic's thinking-enabled Claude models are examples.

**MLP projection:** A multi-layer perceptron used in vision-language models to translate visual feature vectors from a vision encoder's embedding dimension into the language model's embedding dimension, allowing the two components to share a common token space.

**Multimodal:** Capable of processing inputs from more than one data modality. In the context of LLMs, typically means accepting both text and images (and sometimes audio or video) in a single request.

**reasoning_effort:** An OpenAI API parameter for o-series models that controls how deeply the model reasons before answering. Accepts `"low"`, `"medium"`, or `"high"`. Replaces temperature as the primary quality control knob for reasoning models.

**thinking_budget / thinkingBudget:** The maximum number of tokens a model may spend on internal reasoning in a single request. Available in Anthropic (`budget_tokens`) and Gemini (`thinkingBudget`) APIs.

**ViT (Vision Transformer):** A Transformer architecture adapted for image processing. The image is divided into fixed-size patches, each treated as a token, and self-attention is applied across patch tokens. Used as the image encoder component in CLIP and many vision-language models.

**Vision encoder:** The component of a vision-language model responsible for converting a raw image into a sequence of numerical vectors that the language model can process.
