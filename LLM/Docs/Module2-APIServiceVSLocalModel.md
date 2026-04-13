# Module 2: API Services vs Local Models
> Subject: LLM | Difficulty: Intermediate | Estimated Time: 165 minutes

## Objective

After completing this module, you will be able to distinguish API-hosted LLM services from locally self-hosted models and articulate the concrete trade-offs between them. You will be able to select and authenticate against the OpenAI, Anthropic, Google Gemini, Mistral, and Cohere APIs, interpret their pricing structures, and handle rate-limit errors gracefully in Python. You will be able to install Ollama, pull open-weight models, and run local inference with both the CLI and the REST API. You will understand how quantization formats (GGUF, GPTQ, AWQ) shrink model files, estimate the VRAM a given model requires, and choose the right format for your hardware. You will be able to apply a structured decision framework to route real workloads toward the right deployment option — including hybrid strategies that use local models for development and API services for production.

## Prerequisites

- Module 1: Basics of Large Language Models — familiarity with tokenization, inference parameters (temperature, top-p), and the major model families (GPT, Claude, Gemini, LLaMA, Mistral)
- Basic Python comfort: installing packages with pip, setting environment variables, running scripts from the terminal
- A computer with at least 8 GB of RAM (16 GB recommended for the local-model examples)
- A credit card or pre-paid balance on at least one LLM API provider for the API examples (free-tier accounts work for the basic examples)

## Key Concepts

### The Deployment Spectrum

When you want to send text to an LLM and get a response back, you are choosing from a spectrum of deployment options. At one end sits a **fully managed API service** — a company runs the model on their infrastructure, you send an HTTP request, you pay per token, and you never think about hardware. At the other end sits a **self-hosted local model** — you download the model weights to your own machine, inference runs entirely in your RAM or GPU, nothing leaves your network, and the marginal cost per token is zero.

```
                     DEPLOYMENT SPECTRUM

  <-------- More control, more responsibility -------->

  API Service       Managed Hosting      Self-Hosted     Local (laptop)
  (OpenAI, etc.)    (AWS Bedrock, etc.)  (own servers)   (Ollama, etc.)

  - Pay per token   - Pay per hour       - Own hardware   - Own hardware
  - Zero setup      - Some config        - Full config    - Full config
  - Data leaves     - Data can stay      - Data stays     - Data stays
    your network      in region            on-prem          on device
  - Latest models   - Latest models      - Open-weight    - Open-weight
    always                                 only             only
  - SLA uptime      - SLA uptime         - You manage     - You manage
```

The vast majority of real-world LLM deployments do not pick one extreme. They mix strategies: local models for development and testing, API services for production workloads that need frontier capability, and private self-hosted models for workloads that cannot touch a third-party network. Understanding the full spectrum is what lets you make that mix intentional rather than accidental.

---

### API-Hosted LLM Services

An API-hosted LLM service exposes model inference through an HTTP endpoint. You send a JSON payload containing your messages and parameters; the provider's infrastructure runs the forward pass; you receive a JSON response containing the generated text and token usage statistics. You are billed based on the number of tokens consumed.

#### OpenAI

OpenAI's API is the most widely integrated LLM API in existence, with a large ecosystem of libraries, documentation, and compatible third-party tools that speak the "OpenAI API format."

**Authentication:** All requests require an `Authorization: Bearer <key>` header. Keys are created in the OpenAI platform dashboard and should be stored as environment variables, never hard-coded.

**Pricing (as of early 2026):**

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Notes |
|---|---|---|---|
| GPT-5.4 | $2.50 | $15.00 | Current flagship* |
| GPT-4o | $2.50 | $10.00 | Legacy; still widely deployed |
| GPT-5-mini | $0.25 | $1.00 | Fast, cheap; suits classification* |

*Projected pricing for early-2026 models — verify current models and pricing at platform.openai.com/docs/models

**Rate limits** are tiered by account spending history. New accounts (Tier 1) start with conservative limits — approximately 500 requests per minute and 30,000 tokens per minute for most models. Limits increase automatically as your account accrues usage history. Exceeding limits returns an HTTP 429 response.

**Key SDK:** `openai` (Python). Install with `pip install openai`.

---

#### Anthropic (Claude)

Anthropic's API exposes the Claude model family. The Sonnet tier is a practical default for most production use: it balances cost and capability. Haiku is the correct choice for high-volume, lower-complexity tasks where cost is the primary constraint.

**Authentication:** API key in the `x-api-key` header or passed to the SDK client constructor. Store as `ANTHROPIC_API_KEY`.

**Pricing (as of early 2026, sourced from platform.claude.com):**

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Context Window |
|---|---|---|---|
| Claude Opus 4.6 | $5.00 | $25.00 | 200K (1M in some tiers) |
| Claude Sonnet 4.6 | $3.00 | $15.00 | 200K (1M standard) |
| Claude Haiku 4.5 | $1.00 | $5.00 | 200K |
| Claude Haiku 3.5 | $0.80 | $4.00 | 200K |

Anthropic also offers a **Batch API** that processes requests asynchronously at a 50% discount on both input and output tokens — useful for offline workloads that are not latency-sensitive. **Prompt caching** is available for repeated context (large system prompts, reference documents) and reduces input token costs by up to 90% on cache hits.

**Rate limits** follow a four-tier structure. The free/trial tier allows approximately 5 requests per minute. Tier 1 (after a $5 purchase) allows 50 RPM. Tiers 2–4 and enterprise accounts have progressively higher limits.

**Key SDK:** `anthropic` (Python). Install with `pip install anthropic`.

---

#### Google Gemini

Google's Gemini API provides access to the Gemini model family, including the multimodal Gemini 2.5 and Gemini 3 series. A **free tier** with a generous request allowance makes Gemini a practical choice for prototyping and low-volume use.

**Authentication:** API key passed as a query parameter or header. Keys are generated in Google AI Studio (aistudio.google.com).

**Pricing (as of early 2026):**

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Notes |
|---|---|---|---|
| Gemini 3 Pro | $2.00 | $12.00 | Flagship reasoning* |
| Gemini 2.5 Pro | $1.25 | $10.00 | ~60% of Gemini 3 Pro cost |
| Gemini 2.5 Flash | $0.15 | $0.60 | Fast; 8x cheaper than 2.5 Pro |
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | Cheapest tier |

Free tier limits: approximately 15 requests per minute for Gemini 2.5 Flash — adequate for development and personal projects.

*Gemini 3 Pro is a projected model — verify availability and pricing at aistudio.google.com

**Key SDK:** `google-genai` (Python). Install with `pip install google-genai`.

---

#### Mistral AI

Mistral AI is a French company producing highly efficient open-weight models alongside a hosted API. The same models available via their API can often be self-hosted, which is a meaningful advantage: you can develop against the API and deploy self-hosted for cost or privacy reasons without changing your model or fine-tune.

**Authentication:** API key in the `Authorization: Bearer` header. Keys are managed at console.mistral.ai.

**Pricing (as of early 2026):**

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Notes |
|---|---|---|---|
| Mistral Large (latest) | $2.00 | $6.00 | Frontier capability |
| Mistral Medium 3 | $0.40 | $2.00 | Strong mid-tier |
| Mistral Tiny | $0.14 | $0.42 | Fast classification |
| Mistral Nemo | $0.02 | $0.02 | Cheapest available |

**Key SDK:** `mistralai` (Python). Also accepts the OpenAI Python SDK with a custom base URL (`https://api.mistral.ai/v1`), which simplifies migration.

---

#### Cohere

Cohere focuses on enterprise use cases, particularly retrieval-augmented generation (RAG), embeddings, and reranking. Their Command R+ model is purpose-optimized for RAG pipelines and multi-step tool use. Cohere is notable for offering strong **embedding models** alongside generation models under the same API key.

**Authentication:** API key passed in the `Authorization: Bearer` header. Keys from dashboard.cohere.com.

**Key SDK:** `cohere` (Python). Install with `pip install cohere`.

---

#### API Key Security: Non-Negotiable Practices

Across all providers, the same security rules apply:

1. **Never commit API keys to source control.** A key committed to a public GitHub repository will be scraped and used within minutes. Rotate it immediately if this happens.
2. **Store keys as environment variables**, not string literals in code.
3. **Use a secrets manager** (AWS Secrets Manager, HashiCorp Vault, or even a `.env` file excluded from git via `.gitignore`) in any team or production context.
4. **Set spending limits** on your API dashboard to cap accidental overuse.

```bash
# Correct: key in environment, never in code
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="AIza..."

# Wrong: key hard-coded in source file
client = OpenAI(api_key="sk-proj-abc123xyz")   # do not do this
```

---

### Local and Self-Hosted Models

Running a model locally means downloading the model weights to your machine and running inference using a local process. No data leaves your network. The token cost is zero after the initial setup investment in hardware.

#### Ollama

Ollama is the most accessible entry point for local inference. It provides a CLI that downloads, manages, and serves open-weight models, plus a local HTTP server on `http://localhost:11434` that speaks a dialect compatible with the OpenAI API format. As of early 2026, Ollama has over 166,000 GitHub stars and approximately 1.3 million monthly downloads.

**Supported models** include Llama 4, Gemma 3, Mistral Small 3, DeepSeek R1, Qwen 3, Phi-4, and dozens more. The full catalog is at `ollama.com/library`. Models are identified using a `name:tag` convention where the tag encodes parameter count and quantization level (e.g., `llama3.2:8b-q4_K_M`).

**Installation:**

| Platform | Command |
|---|---|
| macOS / Linux | `curl -fsSL https://ollama.com/install.sh \| sh` |
| Windows | Download `OllamaSetup.exe` from ollama.com/download |
| Docker | `docker run -d -p 11434:11434 ollama/ollama` |

After installation, the `ollama` daemon starts automatically as a background service.

---

#### LM Studio

LM Studio is a cross-platform desktop application that provides a graphical interface for discovering, downloading, and running local models. It is aimed at users who prefer a GUI over a terminal and is particularly useful for comparing models side by side before committing to one for a project. Internally, LM Studio uses llama.cpp for inference. It also exposes a local OpenAI-compatible server that your code can target.

**Best used for:** Model discovery, evaluation, non-programmer use cases.

---

#### llama.cpp

llama.cpp is the foundational C++ inference engine that powers Ollama, LM Studio, GPT4All, and KoboldCpp under the hood. It implements optimized inference kernels for CPU and GPU, supports the GGUF model format, and has been ported to virtually every platform including ARM-based devices and WebAssembly. Using llama.cpp directly gives you the most control over quantization settings, context length, threading, and memory management — at the cost of a more complex setup.

**Best used for:** Embedded deployments, custom inference pipelines, maximum performance tuning.

---

#### Hugging Face Transformers

The `transformers` library from Hugging Face is the standard Python interface for loading and running models in their original PyTorch or JAX format (FP16 or BF16 weights). It requires a CUDA-capable GPU for models larger than about 7B parameters to run at useful speeds. `transformers` is less suited to consumer hardware than Ollama/llama.cpp but is the standard choice for research, fine-tuning, and production GPU deployments.

```bash
pip install transformers torch accelerate
```

---

### Hardware Requirements for Local Inference

The key physical constraint for local inference is **GPU VRAM** (or system RAM if running CPU-only). The model weights must fit entirely in memory before a single token can be generated. Memory bandwidth — how fast the GPU can read from VRAM — is the primary bottleneck on generation speed, not raw compute (FLOPs).

#### VRAM Requirements by Model Size

The table below shows approximate VRAM requirements. Quantization reduces requirements significantly; the figures use Q4_K_M quantization (the practical default) and FP16 (full precision) for comparison.

| Model Size | FP16 VRAM | Q4_K_M VRAM | Minimum GPU |
|---|---|---|---|
| 3B parameters | ~6 GB | ~2 GB | Any modern GPU |
| 7–8B parameters | ~16 GB | ~5–6 GB | RTX 3060 (12 GB) |
| 13B parameters | ~26 GB | ~8–9 GB | RTX 3080 (10 GB) or RTX 4070 Ti |
| 30B parameters | ~60 GB | ~20 GB | RTX 3090 / 4090 (24 GB) |
| 70B parameters | ~140 GB | ~35–40 GB | 2x RTX 4090 or A100 (40 GB) |

**Apple Silicon note:** MacBooks and Mac Minis with M-series chips use unified memory shared between CPU and GPU. A Mac Mini M4 Pro with 48 GB of unified memory can run 70B models with Q4_K_M quantization (~40 GB) at 15–25 tokens/second — for roughly $2,000, this is often better value than comparable discrete GPU configurations. Ollama supports Apple Silicon natively using Metal acceleration.

**CPU fallback:** All llama.cpp-based tools (including Ollama) can run on CPU when no GPU is available. A 7B Q4_K_M model on a modern 8-core CPU produces approximately 2–5 tokens/second — slow but usable for batch processing or development where latency is not critical.

**KV cache overhead:** As discussed in Module 1, the KV cache grows with context length. An 8B model with a 32K-token context needs an additional ~3–4 GB beyond the base model weight. Plan for this when choosing hardware.

---

### Quantization Explained

Quantization is the process of reducing the numerical precision of model weights to shrink the model's memory footprint and speed up inference. A model's weights are originally stored as 32-bit floating-point numbers (FP32) during training. Serving them at lower precision sacrifices a small amount of quality in exchange for dramatically reduced memory usage.

#### Precision Formats

```
Format    Bits   Size (7B model)   Quality vs FP32   Primary Use
------    ----   ---------------   ---------------   -----------
FP32      32     ~28 GB            100% (baseline)   Training
FP16      16     ~14 GB            ~99.9%            Standard inference
BF16      16     ~14 GB            ~99.9%            Training / inference
INT8       8     ~7 GB             ~98–99%           Moderate compression
INT4       4     ~4 GB             ~92–96%           Consumer inference
INT2       2     ~2 GB             ~70–80%           Edge; quality degrades
```

The leap from FP16 to INT4 (4-bit) cuts memory use by 75% while keeping quality within about 4–8 percentage points of the unquantized baseline on most benchmarks — a trade-off the vast majority of use cases can accept.

#### Quantization Formats in Practice

Three formats dominate practical local deployment:

**GGUF** (GPT-Generated Unified Format) is the format used by llama.cpp and all tools built on it (Ollama, LM Studio, GPT4All). GGUF files contain the model weights, tokenizer, and metadata in a single portable file. They support a range of quantization levels — the most important are:

| GGUF Quantization | Quality Retention | VRAM (7B model) | Best For |
|---|---|---|---|
| Q8_0 | ~99% | ~8 GB | Near-lossless, GPU with headroom |
| Q5_K_M | ~97% | ~6 GB | Best quality/size balance |
| Q4_K_M | ~92% | ~5 GB | **Recommended default** |
| Q3_K_M | ~85% | ~4 GB | Tight memory constraint |
| Q2_K | ~70% | ~3 GB | Last resort; noticeable quality loss |

The `_K_M` suffix indicates k-quant variants that apply non-uniform quantization — quantizing less-important weights more aggressively and preserving precision on weights that disproportionately affect output quality.

**GPTQ** (Generalized Post-Training Quantization) applies a calibration step on a small dataset to minimize the quantization error. The result is slightly better quality retention than naively rounding weights. GPTQ models are stored in a GPU-specific format and cannot run on CPU. They are the mature choice for GPU-based production inference when GGUF is not an option.

**AWQ** (Activation-Aware Weight Quantization) identifies the roughly 1% of weights that contribute most to model outputs (by observing activations during a calibration pass) and preserves their precision while aggressively quantizing the rest. Combined with the Marlin inference kernel used in vLLM, AWQ achieves approximately 741 tokens/second throughput on an H200 GPU — faster than FP16 baseline at 92% quality retention. AWQ is the optimal choice for high-throughput GPU production serving.

**Quick selection guide:**

```
Running locally on CPU or Mac Silicon?         → GGUF (Q4_K_M recommended)
Running on GPU locally (Ollama, LM Studio)?   → GGUF (Q4_K_M or Q5_K_M)
Production GPU serving (vLLM, TensorRT)?      → AWQ
Pre-quantized model only in this format?      → GPTQ
Fine-tuning with QLoRA?                       → bitsandbytes (not listed above)
```

---

### Trade-Off Comparison: API vs Local

The following matrix covers the dimensions that matter most when making a deployment decision.

| Dimension | API Service | Local / Self-Hosted |
|---|---|---|
| **Setup time** | Minutes (get an API key) | 30 minutes to several hours |
| **Marginal cost** | Per-token pricing ($0.02–$25 per 1M tokens) | ~Zero (electricity + hardware amortization) |
| **Capital cost** | None | $500–$5,000+ for hardware |
| **Model quality** | Frontier (GPT-5, Claude 4, Gemini 3) | Open-weight (Llama 4, Mistral, Qwen) — excellent but behind frontier |
| **Latency** | 200ms–2s for first token (network-dependent) | 50–500ms on good hardware (no network) |
| **Throughput** | Scales automatically | Limited by your hardware |
| **Privacy** | Data sent to provider's servers | Data never leaves your machine |
| **Offline access** | Requires internet | Fully offline |
| **Customization** | Prompt-only (no weight access) | Full control: fine-tune, quantize, modify |
| **Reliability** | Provider SLA (99.9%+) | You manage uptime |
| **Compliance (GDPR/HIPAA)** | Requires DPA; data may cross borders | Automatic: processing stays on-premise |

**The dominant signal in practice:** If you are handling data that is confidential, regulated, or competitively sensitive, the default should be local or private self-hosted. If you need the highest available model quality and can accept data leaving your environment, API services are the faster path. Everything else is a trade-off negotiation on cost, latency, and setup complexity.

---

### Decision Framework: Choosing API vs Local

The following flowchart covers the decision logic that experienced practitioners apply. Work through it for each workload or application, not once for your entire system — different components within the same application often warrant different deployment choices.

```
START: You have a workload to run
        |
        v
[1] Does the data contain PII, PHI, trade secrets, or
    regulated information (GDPR, HIPAA, SOC 2, etc.)?
        |
       YES --> Local / private self-hosted. Stop.
        |
        NO
        v
[2] Do you need capabilities only frontier models provide?
    (e.g., complex multi-step reasoning, vision, 100K+ context)
        |
       YES --> API service.
        |
       NO
        v
[3] Is this a high-volume, repetitive task
    (>100K tokens/day on an ongoing basis)?
        |
       YES --> Calculate: API cost vs hardware amortization.
              - API: multiply token count * per-token price
              - Local: spread hardware cost over 12-24 months
              - If local is cheaper: local.
              - If API is cheaper or capital is unavailable: API.
        |
       NO
        v
[4] Is internet access reliably available where this runs?
        |
        NO --> Local.
        |
       YES
        v
[5] Is this development / testing / personal use?
        |
       YES --> Local (free experimentation; no API costs).
        |
        NO
        v
[6] Default: API service (lowest operational complexity).
    Re-evaluate if costs grow or privacy requirements change.
```

#### Concrete Scenarios

**Scenario A — Healthcare startup building a patient note summarizer:**
Patient notes are PHI (Protected Health Information) under HIPAA. Even with a signed Business Associate Agreement (BAA), sending PHI to a third-party API creates compliance complexity and audit liability. A 7B or 13B model running on-premise, with access controlled by the organization's existing security infrastructure, is the straightforward choice.

**Scenario B — Indie developer building a recipe chatbot:**
No sensitive data, variable traffic, no capital for hardware. API service is correct. Start with the cheapest capable model (GPT-5-mini or Gemini 2.5 Flash at $0.10–$0.25 per 1M input tokens); upgrade to a larger model only if quality is observably insufficient.

**Scenario C — Large e-commerce company classifying 10 million product descriptions per month:**
At 10 million descriptions × ~200 tokens each = 2 billion tokens/month. At $0.25/1M tokens (GPT-5-mini), that is $500/month. A single server with an RTX 4090 running Mistral 7B Q4_K_M can process this volume faster and for less once hardware is amortized. Local wins on cost.

**Scenario D — AI-powered IDE plugin that works offline (airplane mode):**
Requires offline access. A small local model (3B or 7B quantized) embedded in the development environment is the only viable option.

**Scenario E — Research team experimenting with a new prompting technique:**
During research and iteration, the volume is low and the goal is rapid experimentation. Use the API. If the technique proves effective and gets productionized at scale, revisit the deployment decision.

---

### Security and Privacy Considerations

#### What Happens to Data Sent to API Services

When you call an LLM API, your prompt is transmitted to the provider's servers, processed, and a response is returned. The key privacy questions are:

1. **Is my data used to train future models?** Most enterprise-tier API contracts explicitly exclude customer data from training. Verify this in the provider's data processing agreement (DPA). Consumer-facing products (ChatGPT.com, Claude.ai web) may have different terms than API access.

2. **Where is my data processed geographically?** For GDPR compliance, data must either stay within the EU or be transferred under an approved framework (EU-U.S. Data Privacy Framework). Anthropic processes API requests primarily in US data centers. For region-specific processing requirements, use AWS Bedrock's regional endpoints, which offer US and EU options for Claude models. Google Vertex AI similarly offers regional endpoints for EU/US data segregation.

3. **How long is my data retained?** Providers typically retain request logs for a short window (days to weeks) for abuse detection. Enterprise agreements often provide zero-retention options.

#### GDPR, HIPAA, and Compliance at a Glance

| Regulation | Key Requirement | API Service Path | Local Path |
|---|---|---|---|
| **GDPR** | Data processing within or under approved transfer | DPA + regional endpoints | Automatic (on-premise) |
| **HIPAA** | Signed Business Associate Agreement (BAA) | Some providers sign BAAs (OpenAI does) | Automatic if on-premise |
| **SOC 2** | Audit trail of data processing | Provider's compliance certification | Your own certification |
| **LGPD (Brazil)** | Data residency in Brazil or approved transfer | Check provider's regional options | Automatic (on-premise) |

**Practical PII rule:** Regardless of your compliance obligations, do not include names, addresses, social security numbers, financial account numbers, or medical record identifiers in prompts sent to third-party APIs unless you have explicitly reviewed the provider's data handling terms and your organization's legal counsel has signed off. This is Module 1's best practice #7, and it is worth repeating here in a compliance context.

#### Local Model Privacy Properties

A local model provides the strongest possible data isolation: inference runs entirely in your hardware's memory, no network connection is made, and no log is generated outside your own system. This is why local LLMs have become the default choice for:

- Legal and compliance teams reviewing privileged documents
- Healthcare applications processing clinical notes
- Financial institutions running models on trading data
- Security researchers analyzing malware samples
- Any organization subject to data residency laws that prohibit cross-border transfers

---

### Hybrid Approaches: Routing, Fallback, and Local-for-Dev

A well-designed production system rarely commits exclusively to one deployment mode. The patterns below appear repeatedly in real architectures.

#### Pattern 1: Local for Development, API for Production

During development, API costs accumulate even when you are running the same prompt fifty times to test a change. A local model (e.g., Ollama serving Mistral 7B) eliminates this cost and provides instant, offline feedback loops. When code is promoted to production, the same interface is pointed at the API service.

This works cleanly when your local inference server exposes an OpenAI-compatible endpoint (Ollama does this on `http://localhost:11434/v1`). Your application code does not change — only the `base_url` environment variable switches between development and production.

#### Pattern 2: Tiered Routing by Task Complexity

Not every request in an application requires a frontier model. A routing layer inspects incoming requests and sends them to the cheapest model capable of handling them:

```
Incoming request
        |
        v
[Classifier: simple or complex?]
   |                    |
 Simple              Complex
   |                    |
   v                    v
Local 7B or         Frontier API
cheap API tier      (GPT-5, Claude
(classification,    Opus, Gemini 3 Pro)
summarization,      (reasoning, code
Q&A over docs)      generation, analysis)
```

#### Pattern 3: API with Local Fallback

For applications that need high availability but want to avoid API outages causing total failure:

```python
def call_with_fallback(prompt: str) -> str:
    try:
        # Try the primary API service first
        return call_openai_api(prompt)
    except (RateLimitError, APIConnectionError, APIStatusError) as e:
        # Fall back to local Ollama instance on failure
        print(f"Primary API failed ({e}), falling back to local model")
        return call_local_ollama(prompt)
```

---

## Best Practices

1. **Store all API keys as environment variables and exclude them from version control from day one.** Add `.env` to `.gitignore` before your first commit. Rotating a leaked key is time-consuming and potentially costly if the key is abused before discovery.

2. **Always implement exponential backoff retry logic for API calls.** HTTP 429 (rate limit) and 503 (service unavailable) are transient errors. Retrying immediately makes the problem worse. Use a library like `tenacity` or implement your own exponential backoff with jitter.

3. **Benchmark your specific workload before committing to a deployment decision.** Published benchmarks measure average performance across broad test suites. A 7B local model may outperform a frontier model on your specific narrow task while costing 100x less per token.

4. **For local inference, start with Q4_K_M GGUF via Ollama unless you have a specific reason to do otherwise.** This format is portable, CPU-capable, widely supported, and achieves approximately 92% of FP16 quality at a quarter of the memory cost.

5. **Do not send PII or confidential data to any API service without first verifying the provider's DPA and, where applicable, obtaining a signed BAA.** The time cost of this review is far lower than the cost of a breach disclosure.

6. **Model the token economics of your production workload before launch.** Multiply expected daily active users × average conversation length in tokens × per-token price. Build in a 2x headroom buffer for growth. Compare against the annualized cost of hardware capable of running a local alternative.

7. **Use the Anthropic Batch API or equivalent asynchronous endpoints for non-real-time workloads** such as nightly data processing, document indexing, or bulk annotation. The 50% price discount is substantial at scale and requires only minor code changes.

8. **When using local models in a team environment, standardize on Ollama and commit a `pull_models.sh` script to the repository** that lists every model used by the project. This ensures all developers run the same model versions and eliminates "works on my machine" inference inconsistencies.

---

## Use Cases

### Use Case 1: Confidential Legal Document Analysis

A law firm wants to use an LLM to extract key terms and obligations from client contracts, but the contracts contain privileged attorney-client communications.

- **Problem:** Sending privileged documents to a third-party API creates professional responsibility risks and potentially waives privilege. The firm cannot use any public API service.
- **Deployment decision:** Local model on firm-owned hardware. Mistral 7B or LLaMA 3.2 13B with Q4_K_M quantization, served via Ollama on a workstation or on-premise server.
- **Concepts applied:** GGUF quantization to fit the model on available hardware; zero data egress; Ollama's OpenAI-compatible API so existing code patterns apply.
- **Expected outcome:** Contract extraction pipeline runs entirely within the firm's network. Documents never leave firm infrastructure. Quality is sufficient for extracting structured fields (parties, dates, payment terms, jurisdiction) even at 7–13B scale.

### Use Case 2: Startup Building a High-Volume Content Moderation System

A social media platform needs to classify 50 million posts per day as safe, borderline, or policy-violating.

- **Problem:** At 50M posts × 30 tokens/post = 1.5 billion tokens/day. At $0.15/1M tokens (Gemini 2.5 Flash), that is $225/day or ~$82,000/year.
- **Deployment decision:** Self-hosted Mistral 7B Q4_K_M on two GPU servers, using vLLM with AWQ quantization for maximum throughput. Hardware amortizes below $82,000/year within months.
- **Concepts applied:** Cost modeling; AWQ for throughput optimization; vLLM for batched inference serving.
- **Expected outcome:** Per-token cost drops to near-zero. Classification latency stays under 100ms. Privacy risk is eliminated (no user content leaves the platform's infrastructure).

### Use Case 3: Developer Tool with Offline Support

An IDE extension generates inline code suggestions. The extension must work on planes and in secure environments without internet access.

- **Problem:** Cloud API calls require internet. Security-conscious developers in air-gapped environments cannot use an external API.
- **Deployment decision:** Bundled local model via llama.cpp or Ollama. A 3B model (Phi-4-mini or Qwen 2.5-3B) with Q4_K_M quantization fits in under 2 GB and runs on CPU at 5–10 tokens/second — sufficient for short code completions.
- **Concepts applied:** CPU inference via llama.cpp; 3B-parameter models that fit in laptop memory; offline-first architecture.
- **Expected outcome:** Suggestions work regardless of network status. Latency is higher than cloud alternatives but acceptable for a completion use case.

### Use Case 4: Multi-Stage Research Summarization Pipeline

A research organization needs to summarize 10,000 academic papers per month. The papers contain no confidential data, but cost is a concern.

- **Problem:** Running 10,000 papers through a frontier model at $5–$15 per 1M output tokens is expensive. Quality matters but need not be frontier-level.
- **Deployment decision:** Anthropic Batch API with Claude Haiku 4.5 ($0.50/1M input, $2.50/1M output in batch mode). Asynchronous processing; no latency requirement.
- **Concepts applied:** Batch API for 50% cost reduction; Haiku tier for adequate quality at minimum cost; async processing pattern.
- **Expected outcome:** Monthly token cost roughly $500–$800 instead of $5,000–$15,000 with a frontier model, while achieving summary quality adequate for research indexing.

---

## Hands-on Examples

### Example 1: Calling the OpenAI API with Python

This example calls the OpenAI chat completions endpoint and demonstrates proper error handling including rate-limit retries.

1. Install dependencies:

```bash
pip install openai tenacity
```

2. Set your API key in the environment:

```bash
export OPENAI_API_KEY="sk-proj-..."
```

3. Create `openai_demo.py`:

```python
import os
import time
from openai import OpenAI, RateLimitError, APIConnectionError

client = OpenAI()  # reads OPENAI_API_KEY automatically


def chat_with_retry(prompt: str, model: str = "gpt-4o-mini", retries: int = 4) -> str:
    """Call the OpenAI API with exponential backoff on rate limit errors."""
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.3,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a concise technical assistant. Answer in three sentences or fewer."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            text = response.choices[0].message.content
            usage = response.usage
            print(f"[Tokens] prompt={usage.prompt_tokens} "
                  f"completion={usage.completion_tokens} "
                  f"total={usage.total_tokens}")
            return text

        except RateLimitError:
            wait = 2 ** attempt  # 1s, 2s, 4s, 8s
            print(f"Rate limit hit. Waiting {wait}s before retry {attempt + 1}/{retries}...")
            time.sleep(wait)

        except APIConnectionError as e:
            print(f"Connection error: {e}")
            raise

    raise RuntimeError("Exceeded retry limit due to rate limiting.")


if __name__ == "__main__":
    answer = chat_with_retry("What is the difference between FP16 and INT4 quantization?")
    print(answer)
```

4. Run the script:

```bash
python openai_demo.py
```

Expected output (content varies; token counts are approximate):

```
[Tokens] prompt=57 completion=74 total=131
FP16 stores each model weight as a 16-bit floating-point number, using 2 bytes
per value and preserving high numerical precision. INT4 stores each weight as a
4-bit integer, using 0.5 bytes per value and reducing memory by 75% at the cost
of slightly lower output quality. For most inference tasks, INT4 quantization
retains over 90% of the original model's performance.
```

---

### Example 2: Calling the Anthropic API with Python

This example mirrors the OpenAI example using the Anthropic SDK, highlighting the structural differences between the two.

1. Install the SDK:

```bash
pip install anthropic
```

2. Set your API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

3. Create `anthropic_demo.py`:

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY automatically


def ask_claude(prompt: str, model: str = "claude-haiku-4-5") -> str:
    """Send a message to Claude and return the text response."""
    message = client.messages.create(
        model=model,
        max_tokens=256,
        system="You are a concise technical assistant. Answer in three sentences or fewer.",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    text = message.content[0].text
    usage = message.usage
    print(f"[Tokens] input={usage.input_tokens} output={usage.output_tokens}")
    return text


if __name__ == "__main__":
    answer = ask_claude("What is the difference between FP16 and INT4 quantization?")
    print(answer)
```

4. Run the script:

```bash
python anthropic_demo.py
```

Key differences from the OpenAI SDK to note:
- The `system` prompt is a top-level parameter, not a message with `role: "system"`
- The response body is `message.content[0].text` rather than `response.choices[0].message.content`
- `max_tokens` is required (the API will reject a request without it)
- Token usage is under `message.usage.input_tokens` / `message.usage.output_tokens`

---

### Example 3: Running a Local Model with Ollama

This example installs Ollama, pulls the Llama 3.2 3B model (a practical first model for most laptops), and calls it from both the CLI and Python.

**Step 1: Install Ollama**

On macOS or Linux:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

On Windows, download `OllamaSetup.exe` from `https://ollama.com/download` and run it. After installation, Ollama starts as a background service.

**Step 2: Pull a model**

```bash
ollama pull llama3.2:3b
```

This downloads the model file (~2 GB for the default Q4_K_M quantization). The model is cached in `~/.ollama/models/` and only needs to be downloaded once.

```bash
# List models you have downloaded
ollama list

# Expected output:
# NAME                  ID              SIZE    MODIFIED
# llama3.2:3b           a80c4f17acd5    2.0 GB  2 minutes ago
```

**Step 3: Run inference from the CLI**

```bash
# Interactive chat session
ollama run llama3.2:3b

# One-shot query (non-interactive)
ollama run llama3.2:3b "Explain INT4 quantization in two sentences."
```

**Step 4: Call via the REST API**

Ollama exposes a local server on port 11434. You can call it with curl or Python's `requests` library:

```bash
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:3b",
    "stream": false,
    "messages": [
      {"role": "user", "content": "What is quantization in the context of LLMs?"}
    ]
  }'
```

**Step 5: Call from Python using the OpenAI-compatible endpoint**

Ollama exposes an OpenAI-compatible endpoint at `http://localhost:11434/v1`. This means your OpenAI SDK code works with a local model by changing only the `base_url`:

```python
from openai import OpenAI

# Point the OpenAI client at Ollama instead of api.openai.com
local_client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # Ollama does not check this value; any string works
)

response = local_client.chat.completions.create(
    model="llama3.2:3b",
    temperature=0.3,
    messages=[
        {
            "role": "system",
            "content": "You are a concise technical assistant. Answer in three sentences or fewer."
        },
        {
            "role": "user",
            "content": "What is quantization in the context of LLMs?"
        }
    ]
)

print(response.choices[0].message.content)
```

This pattern — the same `OpenAI` client class, different `base_url` — is what makes switching between local development and production API deployment a one-line change.

---

### Example 4: Building a Provider-Agnostic Wrapper with Fallback

This example builds a small abstraction that accepts a prompt and tries a list of providers in order, falling back to the next provider if one fails. It demonstrates the hybrid routing pattern described in the Key Concepts section.

```python
import os
import time
from typing import Callable

from openai import OpenAI, RateLimitError, APIConnectionError, APIStatusError

# Client pointed at OpenAI's production API
openai_client = OpenAI()

# Client pointed at a local Ollama instance
ollama_client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)


def call_openai(prompt: str) -> str:
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def call_ollama(prompt: str) -> str:
    response = ollama_client.chat.completions.create(
        model="llama3.2:3b",
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def call_with_fallback(prompt: str) -> tuple[str, str]:
    """
    Try the primary provider (OpenAI API). On failure, fall back to local Ollama.
    Returns (response_text, provider_used).
    """
    providers: list[tuple[str, Callable]] = [
        ("openai-gpt-4o-mini", call_openai),
        ("ollama-llama3.2:3b", call_ollama),
    ]

    for provider_name, provider_fn in providers:
        try:
            result = provider_fn(prompt)
            return result, provider_name
        except (RateLimitError, APIConnectionError, APIStatusError) as e:
            print(f"[{provider_name}] Failed: {e}. Trying next provider...")
            time.sleep(1)

    raise RuntimeError("All providers failed.")


if __name__ == "__main__":
    test_prompt = "What are the top three reasons to run an LLM locally instead of via API?"
    answer, used_provider = call_with_fallback(test_prompt)
    print(f"[Provider used: {used_provider}]\n")
    print(answer)
```

Run this script with Ollama running locally. Kill the Ollama daemon (`ollama stop`) or use an invalid OpenAI key to test that the fallback triggers correctly.

---

## Common Pitfalls

### Pitfall 1: Hard-Coding API Keys in Source Files

**Description:** A developer pastes an API key directly into a Python script to quickly test something, then commits the file to GitHub.

**Why it happens:** It is faster in the moment. The developer plans to remove it before committing but forgets, or pushes the file thinking the repository is private.

**Consequence:** Automated scanners continuously monitor public repositories for API key patterns. A key committed to a public repository is typically discovered and used within minutes. Even in private repositories, keys in source control create a persistent exposure risk in git history that survives even if the line is deleted.

**Incorrect pattern:**
```python
# Do NOT do this
client = OpenAI(api_key="sk-proj-abc123")
```

**Correct pattern:**
```python
import os
from openai import OpenAI

# Key is read from the environment; never appears in source code
client = OpenAI()  # reads os.environ["OPENAI_API_KEY"] automatically
```

**Fix:** If a key has been committed, rotate it immediately in the provider's dashboard. Scan your git history with a tool like `git-secrets` or `truffleHog` to confirm no other keys are present.

---

### Pitfall 2: Choosing a Model Size That Does Not Fit Available VRAM

**Description:** A learner reads that Llama 4 is an impressive model and runs `ollama pull llama4:70b` on a laptop with 16 GB of unified memory. The pull succeeds (the file downloads), but inference immediately exhausts memory and either crashes or runs at 0.2 tokens/second due to swapping.

**Why it happens:** Model file size on disk does not equal the memory required during inference. The KV cache, activations, and runtime overhead consume additional memory beyond the weights themselves.

**How to estimate before pulling:**

```
Required VRAM ≈ (parameter_count_billions × bits_per_weight / 8) × 1.2 overhead factor

Example: Llama 4 70B at Q4_K_M
  = (70 × 4 / 8) × 1.2
  = 35 GB × 1.2
  = ~42 GB required
```

A laptop with 16 GB cannot run a 70B Q4_K_M model. The correct choice for 16 GB is a 7B or 8B model.

**Correct approach:**
```bash
# Check available memory first
# macOS:
vm_stat | grep "Pages free"

# Linux:
free -h

# Then pull a model sized to fit:
# 8 GB available  → llama3.2:3b  (Q4_K_M: ~2 GB)
# 16 GB available → llama3.2:8b  (Q4_K_M: ~5 GB) or mistral:7b
# 24 GB+ GPU VRAM → llama3.1:13b (Q4_K_M: ~9 GB)
```

---

### Pitfall 3: Ignoring Token Economics Until the First Bill Arrives

**Description:** A developer builds a chatbot, launches it, and discovers that heavy user sessions with large system prompts and long conversation histories are consuming 10x more tokens than expected.

**Why it happens:** Token costs accumulate from four sources that developers often account for incompletely: (1) the system prompt on every call, (2) the entire conversation history on every call (LLM APIs are stateless — you re-send history each turn), (3) output tokens, and (4) tool call overhead.

**Example calculation:**

```
System prompt:           500 tokens (resent every call)
Conversation history:    grows by ~200 tokens per turn
User message:            ~50 tokens
Response:               ~200 tokens

Turn 1 input:   500 + 50 = 550 tokens
Turn 5 input:   500 + (4 × 200) + 50 = 1,350 tokens
Turn 20 input:  500 + (19 × 200) + 50 = 4,350 tokens

At Claude Sonnet 4.6 ($3/1M input, $15/1M output):
20-turn conversation ≈ ~40,000 input tokens total (summed across all turns)
Cost per 20-turn conversation ≈ $0.12 input + $0.06 output = ~$0.18
1,000 users × 5 conversations/week × $0.18 = $900/week
```

**Correct approach:** Model your token economics before launch. Implement a maximum conversation history window (truncate old turns). Use prompt caching for large static system prompts. Consider Haiku or Flash tiers for conversations where quality requirements allow it.

---

### Pitfall 4: Assuming Local Models Are "Always Private"

**Description:** A team sets up Ollama on a shared development server and assumes that because the model runs locally, all queries are private. In fact, Ollama's default configuration exposes port 11434 to all network interfaces, meaning any machine on the same network can query it.

**Why it happens:** "Local" in the context of the machine running the model does not automatically mean "inaccessible from the network."

**Correct approach:** Bind Ollama to localhost explicitly, or secure the port with a firewall rule that limits access to trusted IPs. On a shared server, run Ollama behind an authenticated reverse proxy (e.g., nginx with HTTP Basic Auth or an API key middleware).

```bash
# Bind Ollama to localhost only (Linux/macOS)
OLLAMA_HOST=127.0.0.1 ollama serve
```

Additionally, on managed cloud infrastructure, verify that your instance's security group or firewall does not expose port 11434 to the public internet.

---

## Further Reading

1. **[OpenAI API Documentation — Rate Limits](https://platform.openai.com/docs/guides/rate-limits)** — Official reference for OpenAI's rate limit tiers, how limits are calculated, and the recommended patterns for handling 429 errors with backoff.

2. **[Anthropic Claude API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)** — Official Anthropic pricing page with current per-token costs for all Claude model tiers, including Batch API discounts and prompt caching multipliers. Used as a primary source for this module.

3. **[Ollama GitHub Repository](https://github.com/ollama/ollama)** — Official repository for Ollama with installation instructions, REST API documentation, and the full list of supported models and platforms.

4. **[LLM Quantization Guide: GGUF vs AWQ vs GPTQ vs bitsandbytes (Prem AI, 2026)](https://blog.premai.io/llm-quantization-guide-gguf-vs-awq-vs-gptq-vs-bitsandbytes-compared-2026/)** — Empirical comparison of quantization formats with throughput benchmarks, quality retention data, and practical recommendations for each format's ideal use case.

5. **[Local LLM Inference in 2026: The Complete Guide (DEV Community)](https://dev.to/starmorph/local-llm-inference-in-2026-the-complete-guide-to-tools-hardware-open-weight-models-2iho)** — Practitioner survey of local inference tools (Ollama, LM Studio, vLLM, llama.cpp), hardware sweet spots, and architectural patterns for local vs cloud hybrid deployments.

6. **[Gemini API Pricing — Google AI for Developers](https://ai.google.dev/gemini-api/docs/pricing)** — Official Google pricing reference for the Gemini model family, including free tier limits and per-model token costs.

7. **[Mistral AI Pricing](https://mistral.ai/pricing)** — Official Mistral pricing page covering their API model tiers from Nemo (cheapest) through Mistral Large.

8. **[LLM Data Privacy: Protecting Enterprise Data (Lasso Security)](https://www.lasso.security/blog/llm-data-privacy)** — Analysis of the data privacy risks associated with third-party LLM APIs, covering GDPR, HIPAA, data retention policies, and mitigation strategies relevant to enterprise deployments.

9. **[Ollama VRAM Requirements: Complete 2026 Guide (LocalLLM.in)](https://localllm.in/blog/ollama-vram-requirements-for-local-llms)** — Detailed reference tables for VRAM requirements by model size and quantization level, including KV cache overhead calculations for different context lengths.

10. **[AI API Pricing Comparison 2026 (IntuitionLabs)](https://intuitionlabs.ai/articles/ai-api-pricing-comparison-grok-gemini-openai-claude)** — Side-by-side pricing comparison across OpenAI, Anthropic, Google, and other major providers updated to current rates, useful for rapid cost modeling across providers.
