# Module 5: Fine-Tuning Large Language Models
> Subject: LLM | Difficulty: Intermediate-Advanced | Estimated Time: 300 minutes

## Objective

After completing this module, you will be able to explain what fine-tuning is at a conceptual and mathematical level, and apply a decision framework to determine when fine-tuning is the right tool versus prompt engineering or retrieval-augmented generation. You will understand the mechanics of full fine-tuning, LoRA, and QLoRA, including the low-rank decomposition mathematics and how quantization enables consumer-hardware training. You will be able to prepare datasets in Alpaca and chat formats, run a complete QLoRA fine-tuning job using the TRL SFTTrainer and PEFT libraries, and evaluate results using training loss curves and validation metrics. You will be able to merge LoRA adapters back into base model weights, save the result in safetensors format, serve the merged model through Ollama or vLLM, and share it on the Hugging Face Hub. You will also be able to execute an end-to-end API-based fine-tuning workflow using the OpenAI fine-tuning API.

---

## Prerequisites

- Module 1: Basics of Large Language Models — understanding of Transformer architecture, attention layers, weight matrices, and tokenization
- Module 2: API Services vs Local Models — hands-on experience with Ollama, GGUF/quantization formats, and the OpenAI API; VRAM estimation
- Module 3: Prompt Engineering — ability to write structured instruction prompts; familiarity with chat message roles and prompt engineering techniques
- Module 4: Multimodal Models and Model Types — awareness of open-weight model families (LLaMA, Mistral, Qwen, Gemma)
- Python comfort at the level shown in previous modules: pip, environment variables, working with dictionaries and JSON
- Access to a GPU with at least 8 GB VRAM (for QLoRA examples), or a Google Colab account (free T4 GPU is sufficient for the 3B examples)
- An OpenAI API key with billing enabled for the API fine-tuning example

---

## Key Concepts

### What Fine-Tuning Is

A pre-trained LLM has learned a general-purpose representation of language from trillions of tokens of internet text. Its weights encode grammar, facts, reasoning patterns, and stylistic conventions across hundreds of domains. Fine-tuning takes that general-purpose starting point and continues training it on a smaller, curated dataset to shift its behavior toward a specific task, domain, or style.

The key word is *continues*. Fine-tuning does not train a model from scratch — it performs additional gradient descent steps starting from the pre-trained weights rather than from random initialization. This is why it requires far less data and compute than pre-training: the model already "knows" language; you are teaching it a specialization.

```
Pre-training                         Fine-Tuning
─────────────                        ────────────
Corpus: 1–10 trillion tokens         Dataset: hundreds to hundreds of thousands of examples
Duration: weeks–months on thousands  Duration: hours–days on 1–8 GPUs
  of GPUs
Goal: learn general language          Goal: specialize behavior for a task or domain
Output: base model weights            Output: fine-tuned weights or lightweight adapters
```

There are three distinct fine-tuning objectives, and choosing the right one determines your dataset design:

**Instruction fine-tuning** (also called supervised fine-tuning or SFT) teaches a base model to follow natural language instructions. Base models generate coherent text but do not naturally respond to "please summarize this" or "answer like a helpful assistant." Instruction tuning is what converts a base model into a chat-capable assistant. The result is the kind of model you use when calling the OpenAI or Anthropic APIs.

**Domain adaptation** exposes the model to large volumes of specialized text so that it learns domain-specific vocabulary, facts, and reasoning patterns. A model fine-tuned on medical literature learns to reason about diagnoses; one fine-tuned on legal contracts learns the conventions of contract language. Domain adaptation often uses unlabeled text (completion format) rather than instruction-response pairs.

**Style and persona fine-tuning** adjusts how the model writes or speaks — its tone, verbosity, formatting preferences, or persona — without necessarily changing what it knows. This is appropriate when prompt engineering alone cannot consistently enforce the required style.

---

### When to Fine-Tune: The Decision Framework

Fine-tuning is expensive in time, compute, and maintenance burden. Before committing to it, rule out cheaper alternatives:

```
START: You want the model to behave differently
         |
         v
Is the problem solvable with a better system prompt
or few-shot examples? (Module 3)
  YES ──► Use prompt engineering. Stop here.
  NO
   |
   v
Is the problem lack of knowledge about recent events,
private documents, or a large knowledge base?
  YES ──► Use RAG (retrieval-augmented generation). Stop here.
  NO
   |
   v
Does the problem require consistent style, format, or tone
that even long system prompts cannot reliably enforce?
Or do you need a smaller, cheaper model to match a larger
one's performance on a narrow task?
Or do you need the knowledge encoded in weights rather
than retrieved at inference time?
  YES ──► Fine-tuning is appropriate. Continue.
```

Fine-tuning is the right choice when:
- You need consistent output format (e.g., a medical billing code extractor that always outputs valid ICD-10)
- Latency or cost forces you to use a smaller model, and you need to match a frontier model's accuracy on a specific task
- Your domain uses proprietary terminology absent from the pre-training corpus
- You need a custom persona that is resistant to user jailbreaks (baked into weights, not just the system prompt)
- You are building a product where every inference request will carry the same large system prompt — fine-tuning can bake that context into the weights and save tokens

Fine-tuning is NOT the right choice when:
- Your knowledge changes frequently (weights are static; use RAG instead)
- You have fewer than ~50 high-quality examples (the signal-to-noise ratio will be too low)
- You only need to change behavior for one user or one session (system prompts are cheaper)

---

### Types of Fine-Tuning: From Full to Parameter-Efficient

#### Full Fine-Tuning

Full fine-tuning updates every parameter in the model. All weights participate in gradient computation and are modified by the optimizer. This produces the best possible quality for a given dataset because the model has maximum flexibility to adapt, but it demands enormous hardware:

| Model Size | Full Fine-Tuning VRAM (FP16) |
|---|---|
| 7B | ~67 GB |
| 13B | ~125 GB |
| 30B | ~288 GB |
| 70B | ~672 GB |

These numbers include the model weights, gradients, and Adam optimizer states simultaneously in VRAM. In practice, full fine-tuning of models above 13B requires multi-GPU setups with collective hardware worth tens of thousands of dollars. Full fine-tuning is justified when you have this hardware available, your task is high-stakes enough to warrant maximum quality, and you have a large enough dataset (tens of thousands of examples) to benefit from that flexibility.

#### LoRA: Low-Rank Adaptation

LoRA (Hu et al., 2021) solves the hardware problem by observing that the weight updates needed to adapt a pre-trained model to a new task tend to occupy a low-dimensional subspace — even if the weight matrices themselves are enormous. Instead of updating every element of every weight matrix W, LoRA freezes W and adds a pair of small trainable matrices A and B whose product approximates the update:

```
Standard fine-tuning:   W_new = W + ΔW
                        ΔW shape: (d_out × d_in) — same size as W

LoRA:                   W_new = W + B × A
                        A shape: (r × d_in)     where r << d_in
                        B shape: (d_out × r)    where r << d_out
```

The rank `r` is the key hyperparameter. A weight matrix in a 7B model's attention layer might be 4096 × 4096 = 16.7M parameters. With rank 16, the LoRA matrices A and B together contain only (16 × 4096) + (4096 × 16) = 131,072 parameters — about 128x fewer.

During training, only A and B are updated. W remains frozen. At inference time the product BA is added to W (or folded in as a weight merge). The scaling factor `lora_alpha / r` controls how strongly the adaptation is weighted relative to the frozen base — a higher alpha-to-rank ratio means a bolder adaptation.

**LoRA target modules** specify which weight matrices in the Transformer get LoRA adapters. The attention projection matrices (query `q_proj`, key `k_proj`, value `v_proj`, and output `o_proj`) are the most common targets because they carry most of the model's representational power. For deeper adaptation, you can also target the feed-forward layers (`gate_proj`, `up_proj`, `down_proj` in LLaMA-style architectures).

| LoRA Hyperparameter | Typical Range | Effect |
|---|---|---|
| `r` (rank) | 4–128 | Higher = more trainable parameters, more expressiveness, more VRAM |
| `lora_alpha` | Same as r, or 2× r | Scaling factor; higher = stronger adaptation |
| `lora_dropout` | 0.0–0.1 | Regularization; 0.05 is a safe default |
| `target_modules` | `["q_proj", "v_proj"]` | More modules = broader adaptation |

VRAM requirements with LoRA drop dramatically because only the adapter matrices and their gradients are in high precision:

| Model Size | LoRA VRAM (16-bit base) |
|---|---|
| 7B | ~15 GB |
| 13B | ~28 GB |
| 30B | ~63 GB |
| 70B | ~146 GB |

#### QLoRA: LoRA on a 4-Bit Quantized Base Model

Even LoRA requires the base model weights in memory at 16-bit precision. A 7B model at FP16 occupies ~14 GB before accounting for adapters and optimizer states. QLoRA (Dettmers et al., 2023) solves this by loading the base model in 4-bit precision using a data type called NF4 (NormalFloat 4-bit), which is optimized for normally distributed neural network weights.

The key innovation is that gradient computation and optimizer updates for the LoRA adapters still happen in 16-bit — weights are dequantized on the fly during the forward and backward passes, then re-quantized for storage. The base model weights are never updated; only the LoRA adapters accumulate gradients.

Additional techniques:
- **Double quantization**: quantizes the quantization constants themselves, saving ~0.4 bits per parameter
- **Paged optimizers**: uses CPU RAM to handle VRAM spikes during gradient accumulation

The result: QLoRA makes training on consumer hardware realistic.

| Model Size | QLoRA VRAM (NF4 4-bit) |
|---|---|
| 7B | ~5 GB |
| 13B | ~9 GB |
| 30B | ~20 GB |
| 70B | ~46 GB |

A 7B model fine-tunes comfortably on a single 8 GB GPU. A 13B model fits on a 12–16 GB GPU. This is why QLoRA is the dominant choice for practitioners without datacenter-grade hardware.

#### PEFT: The Hugging Face Library

The `peft` library (Parameter-Efficient Fine-Tuning) by Hugging Face provides a unified API for LoRA, QLoRA, and other adapter methods. The two central classes are:

- **`LoraConfig`**: specifies rank, alpha, target modules, dropout, and the task type
- **`get_peft_model(model, config)`**: wraps any Transformers model with the specified adapters and freezes all non-adapter parameters

---

### Dataset Preparation

#### Dataset Formats

Three formats are in widespread use. Choose based on what behavior you are training:

**Alpaca format** (instruction tuning with optional context input):
```json
{
  "instruction": "Classify the sentiment of the following review.",
  "input": "The battery life is fantastic but the screen is dim.",
  "output": "Mixed — positive sentiment about battery life, negative about display."
}
```
When `input` is empty, the model learns to follow instructions without additional context. About 40% of the original Stanford Alpaca dataset has a non-empty `input` field.

**Chat format / ShareGPT format** (multi-turn conversation):
```json
{
  "conversations": [
    {"from": "human", "value": "What is the capital of France?"},
    {"from": "gpt", "value": "Paris."},
    {"from": "human", "value": "What is its population?"},
    {"from": "gpt", "value": "The Paris metropolitan area has a population of approximately 12 million people."}
  ]
}
```
The TRL SFTTrainer also supports a native messages format using `role` and `content` keys, which maps directly to the OpenAI chat format.

**Completion format** (domain adaptation on raw text):
```json
{"text": "Myocardial infarction (MI), commonly known as a heart attack, results from obstruction of coronary blood flow..."}
```
Used when you want the model to learn domain vocabulary and writing style from unlabeled text rather than from instruction-response pairs.

#### Data Quality vs Quantity

The most important lesson from practitioners fine-tuning in production is that data quality dominates data quantity. A fine-tuned model is only as good as the responses in your dataset. Key principles:

- **Minimum viable dataset**: 50–100 high-quality examples is enough to observe behavioral change. For reliable task specialization, aim for 500–5,000 examples. Datasets above 50,000 rarely provide marginal gains unless they add meaningful diversity.
- **Diversity over repetition**: 500 examples covering varied phrasings, edge cases, and difficulty levels outperforms 5,000 slight variations of the same prompt.
- **Label consistency**: inconsistent labeling (e.g., sometimes the answer is JSON, sometimes plain text) actively harms the model by introducing contradictory gradients.
- **No contamination**: ensure your validation split is drawn from examples the model has never seen, and that validation examples are not rephrased duplicates of training examples.

#### Data Cleaning Checklist

Before training, apply these cleaning steps:

1. **Deduplicate**: use exact-match deduplication on the `instruction` or `prompt` field first, then consider near-duplicate detection (MinHash or embedding similarity) for paraphrase duplicates
2. **Length filter**: remove examples with very short outputs (< 10 tokens) which often indicate missing data, and very long outputs (> 2048 tokens) which disproportionately dominate loss computation unless you are specifically training for long-form generation
3. **Encoding check**: ensure all strings are valid UTF-8 with no binary artifacts from PDF or web scraping
4. **Sensitive data scan**: check for PII (names, emails, phone numbers) if your data comes from real user logs
5. **Format verification**: for structured-output fine-tuning, validate that every `output` field is parseable as its target format (JSON, SQL, etc.)

#### Train/Validation Split

A standard 90/10 or 95/5 train/validation split is appropriate for most fine-tuning jobs. Unlike pre-training at scale, where the validation set is used primarily for loss monitoring, fine-tuning validation also surfaces overfitting early. With fewer than 200 examples total, use 80/20 to ensure the validation set has enough diversity to be meaningful.

---

### Training Infrastructure

#### The Stack

A practical QLoRA fine-tuning stack in 2026 looks like this:

```
transformers        — model loading, tokenizer, generation
datasets            — dataset loading, processing, train/val split
peft                — LoraConfig, get_peft_model, adapter management
bitsandbytes        — 4-bit quantization (QLoRA's foundation)
trl                 — SFTTrainer, SFTConfig (high-level training loop)
accelerate          — multi-GPU and mixed-precision management
```

Install with:
```bash
pip install transformers datasets peft bitsandbytes trl accelerate
```

#### SFTTrainer (TRL)

The `SFTTrainer` from the TRL (Transformer Reinforcement Learning) library is the standard high-level entry point for supervised fine-tuning. It wraps the Hugging Face `Trainer` class and adds SFT-specific features:

- Automatic chat template application for conversational datasets
- Native PEFT integration via the `peft_config` argument
- `assistant_only_loss` to compute loss only on assistant turns (not user/system tokens)
- `packing` mode to concatenate short examples into full-length sequences for efficiency

Key `SFTConfig` defaults worth knowing:
- `gradient_checkpointing=True` by default (trades compute for VRAM)
- `bf16=True` by default if fp16 is not set (bfloat16 is preferred for stability)
- `learning_rate=2e-5` by default (higher than full fine-tuning; typically 1e-4 to 2e-4 for adapter-only training)

#### Unsloth

Unsloth is an open-source framework that optimizes LoRA and QLoRA training with custom Triton kernels. It achieves up to 2x faster training and up to 70% less VRAM versus the standard Transformers + PEFT stack with no change in output quality. It is compatible with the TRL SFTTrainer and supports LLaMA, Mistral, Qwen, Gemma, DeepSeek, and Phi model families.

Unsloth is particularly useful on Google Colab's free T4 GPU (16 GB VRAM), where memory is tight. The Unsloth `FastLanguageModel` loader replaces the standard `AutoModelForCausalLM.from_pretrained` call.

#### Hardware and Cloud Options

| GPU | VRAM | Models practical with QLoRA | Approximate cost |
|---|---|---|---|
| NVIDIA RTX 4060 Ti | 16 GB | Up to 13B | Consumer; ~$500 |
| NVIDIA RTX 3090 / 4090 | 24 GB | Up to 30B | Consumer; ~$800–$1,500 |
| Google Colab T4 (free) | 16 GB | Up to 13B | Free (limited hours) |
| Google Colab A100 (Pro) | 40 GB | Up to 30B (tight) | ~$10/month subscription |
| RunPod / Lambda Labs A100 | 40–80 GB | Up to 70B | ~$1.50–$3/hour |
| vast.ai RTX 4090 | 24 GB | Up to 30B | ~$0.30–$0.60/hour |

For most practitioners, the recommended starting point is a free Google Colab T4 for experiments, then a rented A100-80GB on RunPod or Lambda Labs for production runs of 13–70B models.

---

### Evaluation and Iteration

#### Reading the Loss Curves

The most important signals during fine-tuning are training loss and validation loss over steps.

```
Good training:              Overfitting:              Underfitting:

loss                        loss                      loss
 |                           |                         |
1.5 ─ train                1.5 ─ train               1.5 ─ train
 |    \                     |    \                    |    \
1.0    \                   1.0    \___                1.0    \___
 |      \___               |    val /                 |         \___
0.5      \___              0.5  ────/──────            0.5            ─────
 |            \            |                          |     (both still
 |       val   \           └──────────────            └──    decreasing)
 └──────────────           val diverging up
```

- **Training loss decreasing, validation loss tracking it**: healthy training
- **Training loss decreasing, validation loss plateauing or rising**: overfitting — stop training, reduce epochs, or add more data
- **Both losses still decreasing at the end of training**: underfitting — train for more epochs or increase learning rate

A sensible stopping criterion is early stopping when validation loss has not improved for 3 consecutive evaluation steps.

#### Evaluation Metrics

**Perplexity**: measures how confidently the model predicts held-out tokens. Lower is better. Useful for comparing model checkpoints on the same dataset but not comparable across datasets. Compute it on the validation set at the end of each epoch.

**BLEU and ROUGE**: n-gram overlap metrics widely used for translation (BLEU) and summarization (ROUGE). They measure lexical similarity between the model's output and a reference output. Useful as a cheap automated signal when you have reference outputs, but they penalize valid paraphrases and should not be used as the sole quality measure.

**Task-specific metrics**: these are your primary measure of success. If you are fine-tuning a classifier, measure accuracy and F1. If you are fine-tuning a SQL generator, measure execution accuracy (does the generated SQL produce the correct rows?). Design your evaluation around what the model actually needs to do.

**Human evaluation**: for open-ended generation (style, tone, helpfulness), automated metrics are insufficient. Rate 50–200 held-out responses on the dimensions that matter (accuracy, format adherence, tone) using a rubric. Even a simple 1–5 scale applied consistently is more informative than BLEU for instruction-following tasks.

#### Common Failure Modes

**Catastrophic forgetting**: the model loses its general capabilities while specializing. Signs include degraded performance on questions outside your training domain, loss of instruction-following ability, or increased hallucination. Mitigations: use LoRA instead of full fine-tuning (the frozen base weights retain general knowledge), reduce the number of training epochs, or mix a small fraction of general-purpose data into your training set.

**Overfitting**: the model memorizes the training examples rather than generalizing. Signs include validation loss rising while training loss falls, or the model producing training examples verbatim during inference. Mitigations: reduce epochs, increase dropout, gather more diverse data.

**Instruction following regression**: after SFT, the model correctly answers in-domain questions but stops following general instructions (e.g., it ignores system prompts). Cause: the fine-tuning data format did not match the chat template the base model was already tuned for, or the training data did not include system-role messages. Fix: ensure your training data includes system messages and that you apply the model's native chat template during training.

**Repetition and degeneration**: outputs loop or degrade in quality. Usually caused by training with too high a learning rate, too many epochs on too little data, or training on low-quality outputs.

---

## Hands-on Examples

### Example 1: Preparing a Dataset in Alpaca Format

This example builds a small instruction-tuning dataset in Alpaca format, cleans it, splits it into train and validation sets, and saves it to disk using the Hugging Face `datasets` library.

```python
import json
import random
from datasets import Dataset, DatasetDict

# Raw data in Alpaca format.
# In a real project, this list would be loaded from a JSONL file or
# assembled from domain expert annotations.
raw_examples = [
    {
        "instruction": "Classify the sentiment of the customer review.",
        "input": "The delivery was two days late and the packaging was damaged.",
        "output": "Negative",
    },
    {
        "instruction": "Classify the sentiment of the customer review.",
        "input": "Arrived ahead of schedule and the product exceeded my expectations.",
        "output": "Positive",
    },
    {
        "instruction": "Classify the sentiment of the customer review.",
        "input": "The item works as described. Nothing special but no complaints.",
        "output": "Neutral",
    },
    {
        "instruction": "Summarize the following support ticket in one sentence.",
        "input": "Hi, I placed an order three weeks ago (order #8821) and have not received it. I sent two emails and did not get a reply. I would like either a refund or a replacement shipped immediately.",
        "output": "Customer has not received order #8821 placed three weeks ago, has received no email response, and requests a refund or replacement.",
    },
    {
        "instruction": "Translate the following phrase to Spanish.",
        "input": "Where is the nearest train station?",
        "output": "¿Dónde está la estación de tren más cercana?",
    },
    {
        "instruction": "Extract the product name and price from the following sentence.",
        "input": "The Acme ProDrive 3000 is currently on sale for $49.99.",
        "output": '{"product": "Acme ProDrive 3000", "price": "$49.99"}',
    },
    {
        "instruction": "Write a polite decline email for a job offer.",
        "input": "",
        "output": "Dear [Hiring Manager],\n\nThank you so much for offering me the [Position] role at [Company]. After careful consideration, I have decided to decline the offer. This was a difficult decision, as I have great respect for your team and the work you do.\n\nI wish you and the team continued success.\n\nBest regards,\n[Your Name]",
    },
    {
        "instruction": "Convert the following temperature from Celsius to Fahrenheit.",
        "input": "37 degrees Celsius",
        "output": "98.6 degrees Fahrenheit",
    },
]


def clean_examples(examples: list[dict]) -> list[dict]:
    """Apply basic cleaning: strip whitespace, remove empty outputs, deduplicate."""
    seen_instructions = set()
    cleaned = []
    for ex in examples:
        # Strip whitespace from all string fields
        ex = {k: v.strip() if isinstance(v, str) else v for k, v in ex.items()}

        # Skip examples with empty outputs
        if not ex.get("output"):
            print(f"Skipping example with empty output: {ex['instruction'][:50]}")
            continue

        # Deduplicate on (instruction, input) pair
        key = (ex["instruction"], ex.get("input", ""))
        if key in seen_instructions:
            print(f"Skipping duplicate: {ex['instruction'][:50]}")
            continue
        seen_instructions.add(key)

        cleaned.append(ex)

    return cleaned


def alpaca_to_prompt(example: dict) -> str:
    """
    Convert an Alpaca-format example into a single formatted string.
    This is the prompt template used by the original Stanford Alpaca project.
    """
    if example.get("input"):
        return (
            "Below is an instruction that describes a task, paired with an input "
            "that provides further context. Write a response that appropriately "
            "completes the request.\n\n"
            f"### Instruction:\n{example['instruction']}\n\n"
            f"### Input:\n{example['input']}\n\n"
            "### Response:\n"
            f"{example['output']}"
        )
    else:
        return (
            "Below is an instruction that describes a task. Write a response that "
            "appropriately completes the request.\n\n"
            f"### Instruction:\n{example['instruction']}\n\n"
            "### Response:\n"
            f"{example['output']}"
        )


# Clean the raw data
cleaned = clean_examples(raw_examples)
print(f"Examples after cleaning: {len(cleaned)}")

# Add the formatted prompt text field that SFTTrainer will use
for ex in cleaned:
    ex["text"] = alpaca_to_prompt(ex)

# Shuffle before splitting to avoid ordering bias
random.seed(42)
random.shuffle(cleaned)

# 80/20 split (appropriate for small datasets)
split_idx = int(len(cleaned) * 0.8)
train_data = cleaned[:split_idx]
val_data = cleaned[split_idx:]

# Build a Hugging Face DatasetDict
dataset = DatasetDict(
    {
        "train": Dataset.from_list(train_data),
        "validation": Dataset.from_list(val_data),
    }
)

print(f"Train examples: {len(dataset['train'])}")
print(f"Validation examples: {len(dataset['validation'])}")
print("\nSample training example (text field):")
print(dataset["train"][0]["text"])

# Save to disk for use in subsequent training runs
dataset.save_to_disk("./alpaca_dataset")
print("\nDataset saved to ./alpaca_dataset")

# Optionally save as JSONL for inspection
with open("train.jsonl", "w", encoding="utf-8") as f:
    for ex in train_data:
        f.write(json.dumps(ex, ensure_ascii=False) + "\n")
print("Training JSONL saved to train.jsonl")
```

---

### Example 2: QLoRA Fine-Tuning with TRL SFTTrainer

This is a complete, runnable QLoRA fine-tuning script using the TRL `SFTTrainer`. It loads a 1B-class model (Qwen/Qwen2.5-1.5B-Instruct) in 4-bit quantization, attaches LoRA adapters, trains for two epochs on the dataset from Example 1, and saves the adapter to disk.

This script runs on a GPU with 8 GB VRAM. Swap the `model_id` for a larger model and adjust `per_device_train_batch_size` to fit your hardware.

```python
import os
import torch
from datasets import load_from_disk
from transformers import AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

# ─────────────────────────────────────────────
# 1. Configuration
# ─────────────────────────────────────────────
model_id = "Qwen/Qwen2.5-1.5B-Instruct"   # Swap to e.g. "meta-llama/Llama-3.2-3B-Instruct"
output_dir = "./qwen2.5-1.5b-finetuned"
dataset_path = "./alpaca_dataset"

# ─────────────────────────────────────────────
# 2. Load dataset (from Example 1)
# ─────────────────────────────────────────────
dataset = load_from_disk(dataset_path)
train_dataset = dataset["train"]
eval_dataset = dataset["validation"]

# ─────────────────────────────────────────────
# 3. QLoRA: 4-bit quantization configuration
#    NF4 (NormalFloat 4-bit) is optimal for
#    normally distributed neural network weights.
#    Double quantization saves an additional
#    ~0.4 bits per parameter.
# ─────────────────────────────────────────────
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
)

# ─────────────────────────────────────────────
# 4. LoRA adapter configuration
#    r=16 and lora_alpha=32 is a balanced
#    starting point for instruction tuning.
#    target_modules covers query, key, value,
#    and output projections in attention layers
#    plus the feed-forward layers.
# ─────────────────────────────────────────────
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=[
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

# ─────────────────────────────────────────────
# 5. Training configuration (SFTConfig)
#    SFTConfig extends TrainingArguments with
#    SFT-specific defaults.
# ─────────────────────────────────────────────
sft_config = SFTConfig(
    output_dir=output_dir,
    num_train_epochs=2,
    per_device_train_batch_size=2,
    per_device_eval_batch_size=2,
    gradient_accumulation_steps=4,       # effective batch size = 2 × 4 = 8
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.05,
    max_length=1024,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    bf16=True,                           # bfloat16 for stability on modern GPUs
    logging_steps=10,
    report_to="none",                    # set to "wandb" or "tensorboard" for tracking
    dataset_text_field="text",           # column in our dataset that holds the prompt
    model_init_kwargs={"quantization_config": bnb_config},
)

# ─────────────────────────────────────────────
# 6. Build and run the trainer
# ─────────────────────────────────────────────
trainer = SFTTrainer(
    model=model_id,
    args=sft_config,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    peft_config=lora_config,
)

print("Starting fine-tuning...")
trainer.train()

# ─────────────────────────────────────────────
# 7. Save the LoRA adapter (not the full model)
#    The adapter directory is small (~100 MB
#    for rank-16 on a 1.5B model).
# ─────────────────────────────────────────────
trainer.save_model(output_dir)
print(f"LoRA adapter saved to {output_dir}")

# Print final training stats
final_metrics = trainer.state.log_history[-1]
print(f"\nFinal training loss: {final_metrics.get('train_loss', 'N/A'):.4f}")
```

After training, the `output_dir` will contain:
- `adapter_config.json` — the LoRA configuration
- `adapter_model.safetensors` — the trained adapter weights
- `tokenizer.json` and related files — the tokenizer

To run inference with just the adapter (without merging):

```python
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer
import torch

model = AutoPeftModelForCausalLM.from_pretrained(
    "./qwen2.5-1.5b-finetuned",
    torch_dtype=torch.bfloat16,
    device_map="auto",
)
tokenizer = AutoTokenizer.from_pretrained("./qwen2.5-1.5b-finetuned")

prompt = (
    "Below is an instruction that describes a task. Write a response that "
    "appropriately completes the request.\n\n"
    "### Instruction:\nClassify the sentiment of the customer review.\n\n"
    "### Input:\nFast shipping but the product quality was disappointing.\n\n"
    "### Response:\n"
)

inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
with torch.no_grad():
    outputs = model.generate(**inputs, max_new_tokens=50, temperature=0.1)

response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
print(response)
```

---

### Example 3: Merging LoRA Adapters and Saving the Full Model

Serving a model through an adapter at every inference request adds a small overhead and requires loading both the base model and the adapter. When deploying to production, it is cleaner to merge the adapter weights back into the base model weights to produce a single standalone model. This also enables conversion to GGUF for Ollama.

```python
import torch
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer

adapter_dir = "./qwen2.5-1.5b-finetuned"
merged_dir = "./qwen2.5-1.5b-merged"

# ─────────────────────────────────────────────
# 1. Load the adapter-wrapped model
#    Use float16 (not bfloat16) for GGUF
#    conversion compatibility.
# ─────────────────────────────────────────────
print("Loading adapter model...")
model = AutoPeftModelForCausalLM.from_pretrained(
    adapter_dir,
    torch_dtype=torch.float16,
    device_map="cpu",            # merge on CPU to avoid VRAM constraints
)

# ─────────────────────────────────────────────
# 2. Merge LoRA weights into the base weights
#    merge_and_unload() is NOT in-place:
#    assign the return value.
# ─────────────────────────────────────────────
print("Merging LoRA adapters into base model weights...")
merged_model = model.merge_and_unload()

# ─────────────────────────────────────────────
# 3. Save as safetensors
#    safe_serialization=True produces .safetensors
#    files (preferred over .bin for security
#    and performance).
# ─────────────────────────────────────────────
print(f"Saving merged model to {merged_dir}...")
merged_model.save_pretrained(merged_dir, safe_serialization=True)

# Save the tokenizer alongside the model
tokenizer = AutoTokenizer.from_pretrained(adapter_dir)
tokenizer.save_pretrained(merged_dir)

print("Merge complete. Contents of merged directory:")
import os
for f in sorted(os.listdir(merged_dir)):
    size_mb = os.path.getsize(os.path.join(merged_dir, f)) / (1024 * 1024)
    print(f"  {f:<40} {size_mb:.1f} MB")

# ─────────────────────────────────────────────
# 4. (Optional) Push to Hugging Face Hub
#    Requires: huggingface-cli login
# ─────────────────────────────────────────────
# merged_model.push_to_hub("your-username/qwen2.5-1.5b-sentiment-classifier")
# tokenizer.push_to_hub("your-username/qwen2.5-1.5b-sentiment-classifier")
```

**Converting to GGUF for Ollama** (run in a terminal after the merge):

```bash
# 1. Clone llama.cpp and install its Python dependencies
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
pip install -r requirements.txt

# 2. Convert the merged safetensors model to GGUF (float16)
python convert_hf_to_gguf.py ../qwen2.5-1.5b-merged \
    --outtype f16 \
    --outfile ../qwen2.5-1.5b-merged.gguf

# 3. (Optional) Quantize the GGUF to Q4_K_M for smaller file size
./llama-quantize ../qwen2.5-1.5b-merged.gguf \
    ../qwen2.5-1.5b-merged-q4km.gguf Q4_K_M
```

**Importing into Ollama:**

```bash
# 4. Create a Modelfile
cat > Modelfile << 'EOF'
FROM ./qwen2.5-1.5b-merged-q4km.gguf

PARAMETER temperature 0.1
PARAMETER stop "### Instruction:"
EOF

# 5. Register the model with Ollama
ollama create my-sentiment-model -f Modelfile

# 6. Run it
ollama run my-sentiment-model "Classify this review: Best product I have ever bought."
```

---

### Example 4: OpenAI API Fine-Tuning Workflow

The OpenAI fine-tuning API provides a managed alternative to self-hosted training. You upload a JSONL dataset, create a fine-tuning job, monitor it, and then call the resulting model by its unique ID. As of 2026, fine-tuning is supported on `gpt-4o-mini-2024-07-18` and `gpt-4o-2024-08-06`, among other models. Check platform.openai.com/docs/guides/fine-tuning for the current list — newer versioned IDs are added regularly.

The dataset format uses the messages array from the chat completions API. Each line in the JSONL file is one training example.

```python
import json
import os
import time
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ─────────────────────────────────────────────
# 1. Prepare the JSONL training dataset
#    Each example is a complete conversation.
#    The system message defines the assistant's
#    role; the user message is the input;
#    the assistant message is the target output.
# ─────────────────────────────────────────────
training_examples = [
    {
        "messages": [
            {"role": "system", "content": "You are a customer review sentiment classifier. Reply with exactly one word: Positive, Negative, or Neutral."},
            {"role": "user", "content": "The delivery was two days late and the packaging was damaged."},
            {"role": "assistant", "content": "Negative"},
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "You are a customer review sentiment classifier. Reply with exactly one word: Positive, Negative, or Neutral."},
            {"role": "user", "content": "Arrived ahead of schedule and the product exceeded my expectations."},
            {"role": "assistant", "content": "Positive"},
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "You are a customer review sentiment classifier. Reply with exactly one word: Positive, Negative, or Neutral."},
            {"role": "user", "content": "The item works as described. Nothing special but no complaints."},
            {"role": "assistant", "content": "Neutral"},
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "You are a customer review sentiment classifier. Reply with exactly one word: Positive, Negative, or Neutral."},
            {"role": "user", "content": "Terrible quality, broke after one use. Total waste of money."},
            {"role": "assistant", "content": "Negative"},
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "You are a customer review sentiment classifier. Reply with exactly one word: Positive, Negative, or Neutral."},
            {"role": "user", "content": "Great value for the price. Highly recommend to anyone."},
            {"role": "assistant", "content": "Positive"},
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "You are a customer review sentiment classifier. Reply with exactly one word: Positive, Negative, or Neutral."},
            {"role": "user", "content": "Average product. Does what it says on the box."},
            {"role": "assistant", "content": "Neutral"},
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "You are a customer review sentiment classifier. Reply with exactly one word: Positive, Negative, or Neutral."},
            {"role": "user", "content": "Absolutely love this! Will buy again without hesitation."},
            {"role": "assistant", "content": "Positive"},
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "You are a customer review sentiment classifier. Reply with exactly one word: Positive, Negative, or Neutral."},
            {"role": "user", "content": "Customer service was rude and unhelpful when I had a problem."},
            {"role": "assistant", "content": "Negative"},
        ]
    },
]

validation_examples = [
    {
        "messages": [
            {"role": "system", "content": "You are a customer review sentiment classifier. Reply with exactly one word: Positive, Negative, or Neutral."},
            {"role": "user", "content": "Fast shipping but the product quality was disappointing."},
            {"role": "assistant", "content": "Negative"},
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "You are a customer review sentiment classifier. Reply with exactly one word: Positive, Negative, or Neutral."},
            {"role": "user", "content": "Works as expected. No frills but reliable."},
            {"role": "assistant", "content": "Neutral"},
        ]
    },
]

# Write JSONL files
def write_jsonl(path: str, data: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for example in data:
            f.write(json.dumps(example) + "\n")

write_jsonl("openai_train.jsonl", training_examples)
write_jsonl("openai_val.jsonl", validation_examples)
print(f"Wrote {len(training_examples)} training examples and {len(validation_examples)} validation examples.")

# ─────────────────────────────────────────────
# 2. Upload files to the OpenAI Files API
# ─────────────────────────────────────────────
print("\nUploading training file...")
with open("openai_train.jsonl", "rb") as f:
    train_file = client.files.create(file=f, purpose="fine-tune")
training_file_id = train_file.id
print(f"Training file ID: {training_file_id}")

print("Uploading validation file...")
with open("openai_val.jsonl", "rb") as f:
    val_file = client.files.create(file=f, purpose="fine-tune")
validation_file_id = val_file.id
print(f"Validation file ID: {validation_file_id}")

# ─────────────────────────────────────────────
# 3. Create the fine-tuning job
#    n_epochs: number of passes over the data;
#      "auto" lets OpenAI choose (recommended
#      for small datasets).
#    suffix: appended to the fine-tuned model
#      name to identify it.
# ─────────────────────────────────────────────
print("\nCreating fine-tuning job...")
job = client.fine_tuning.jobs.create(
    training_file=training_file_id,
    validation_file=validation_file_id,
    model="gpt-4o-mini-2024-07-18",
    suffix="sentiment-v1",
    hyperparameters={
        "n_epochs": "auto",              # "auto", or an integer 1–50
    },
)
job_id = job.id
print(f"Fine-tuning job created. Job ID: {job_id}")
print(f"Status: {job.status}")

# ─────────────────────────────────────────────
# 4. Poll for completion
#    Jobs typically take 10–60 minutes
#    depending on dataset size and model.
#    In production, use a webhook instead
#    of polling.
# ─────────────────────────────────────────────
print("\nPolling for job completion (this may take several minutes)...")
while True:
    job = client.fine_tuning.jobs.retrieve(job_id)
    print(f"  Status: {job.status}")

    if job.status in ("succeeded", "failed", "cancelled"):
        break

    # Print the latest event for progress visibility
    events = client.fine_tuning.jobs.list_events(job_id, limit=1)
    if events.data:
        print(f"  Latest event: {events.data[0].message}")

    time.sleep(30)

if job.status != "succeeded":
    raise RuntimeError(f"Fine-tuning job {job_id} ended with status: {job.status}")

fine_tuned_model_id = job.fine_tuned_model
print(f"\nFine-tuning complete. Model ID: {fine_tuned_model_id}")

# ─────────────────────────────────────────────
# 5. Use the fine-tuned model
#    The fine-tuned model ID is used exactly
#    like any other model name in chat completions.
# ─────────────────────────────────────────────
test_reviews = [
    "Best purchase I have made this year!",
    "Stopped working after one week. Very frustrated.",
    "It is okay. Nothing to write home about.",
]

print("\nTesting fine-tuned model:")
for review in test_reviews:
    response = client.chat.completions.create(
        model=fine_tuned_model_id,
        messages=[
            {
                "role": "system",
                "content": "You are a customer review sentiment classifier. Reply with exactly one word: Positive, Negative, or Neutral.",
            },
            {"role": "user", "content": review},
        ],
        temperature=0,
        max_tokens=5,
    )
    sentiment = response.choices[0].message.content.strip()
    print(f"  Review: {review}")
    print(f"  Sentiment: {sentiment}\n")
```

**Note on API fine-tuning economics**: API fine-tuning charges a per-token training fee (check the OpenAI pricing page for current rates) plus standard inference charges. For a small classification dataset of a few hundred examples, the total training cost is typically a few dollars. However, if you intend to run millions of inferences, a self-hosted QLoRA fine-tuned open-weight model will be significantly cheaper at scale.

---

### API-Based Fine-Tuning: Anthropic

As of early 2026, Anthropic's direct API does not offer a fine-tuning endpoint. Fine-tuning for Claude 3 Haiku is available through **Amazon Bedrock**, AWS's managed model hosting service. This is Anthropic's official supported channel for enterprise customers who need fine-tuned Claude models.

The Bedrock fine-tuning workflow differs from the OpenAI approach: training data is uploaded to S3, a fine-tuning job is triggered through the Bedrock API or AWS Console, and the resulting model is provisioned on a dedicated throughput endpoint. Text-based fine-tuning supports context lengths up to 32K tokens.

For teams already operating in the AWS ecosystem, Bedrock fine-tuning provides a fully managed pipeline. For teams outside AWS, the OpenAI fine-tuning API or self-hosted QLoRA is a more accessible path.

---

## Summary

Fine-tuning adapts a pre-trained model's weights to a specific task, domain, or style through continued gradient descent. The three-step decision framework — try prompt engineering first, then RAG, then fine-tuning — prevents over-engineering and ensures the tool matches the problem.

LoRA reduces trainable parameters by approximating weight updates as a product of two small matrices (B × A) added to the frozen pre-trained weights. QLoRA layers 4-bit NF4 quantization onto LoRA, cutting base model VRAM requirements by 4× and making fine-tuning of 7B–13B models practical on consumer hardware. The PEFT and TRL libraries provide a production-grade Python API for both techniques.

Dataset preparation — cleaning, deduplication, format standardization, and an honest train/validation split — is the most time-leveraged activity in a fine-tuning project. A small, clean, diverse dataset outperforms a large noisy one. Training loss curves and task-specific metrics are the primary feedback mechanism; automated metrics like BLEU and ROUGE are supplementary signals.

After training, LoRA adapters are merged back into the base model weights with `merge_and_unload()`, saved as safetensors, and deployed through Ollama (via GGUF conversion), vLLM, or llama.cpp. The Hugging Face Hub provides versioned hosting and easy sharing.

---

## Further Reading

- [Hugging Face PEFT Documentation](https://huggingface.co/docs/peft) — Official documentation for the PEFT library covering LoraConfig, get_peft_model, model merging, and all supported adapter methods. The authoritative reference for the code patterns in this module.

- [TRL SFTTrainer Documentation](https://huggingface.co/docs/trl/sft_trainer) — Full API reference for SFTTrainer and SFTConfig, covering dataset formats, packing, assistant-only loss, PEFT integration, and vision-language model training.

- [QLoRA: Efficient Finetuning of Quantized LLMs (Dettmers et al., 2023)](https://arxiv.org/abs/2305.14314) — The original QLoRA paper. Introduces NF4 quantization, double quantization, and paged optimizers. Required reading for understanding why the BitsAndBytesConfig parameters in Example 2 are set as they are.

- [LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., 2021)](https://arxiv.org/abs/2106.09685) — The original LoRA paper. Explains the mathematical motivation for low-rank weight updates, including why the adaptation update tends to be intrinsically low-rank, with ablations over rank values.

- [OpenAI Fine-Tuning Guide](https://platform.openai.com/docs/guides/fine-tuning/) — Official documentation for the OpenAI supervised fine-tuning API, including supported models, dataset format requirements, hyperparameter options, and pricing. Check this page for the latest supported base models.

- [Unsloth Documentation](https://unsloth.ai/docs) — Official documentation for the Unsloth fast fine-tuning framework, including installation, LoRA hyperparameter guidance, supported models (Qwen3, LLaMA 4, DeepSeek, Gemma 3), and memory requirement tables.

- [How Much VRAM Do I Need for LLM Fine-Tuning? (Modal Blog)](https://modal.com/blog/how-much-vram-need-fine-tuning) — A practical reference article with a detailed VRAM requirement table for full fine-tuning, LoRA, and QLoRA across 7B to 110B model sizes. Useful for hardware selection and cloud instance sizing.

- [Fine-Tuning for Claude 3 Haiku on Amazon Bedrock](https://aws.amazon.com/blogs/aws/fine-tuning-for-anthropics-claude-3-haiku-model-in-amazon-bedrock-is-now-generally-available/) — AWS announcement and walkthrough for fine-tuning Claude 3 Haiku through Bedrock, the only currently supported path for fine-tuning Anthropic models.

- [Ollama Model Import Documentation](https://docs.ollama.com/import) — Official guide for importing custom GGUF models into Ollama via Modelfile, covering the FROM instruction, ADAPTER format for LoRA GGUF adapters, and conversion from Safetensors using llama.cpp.

- [Making LLMs More Accessible with bitsandbytes 4-bit Quantization and QLoRA (Hugging Face Blog)](https://huggingface.co/blog/4bit-transformers-bitsandbytes) — Hugging Face's introduction to 4-bit quantization via bitsandbytes. Explains NF4, double quantization, and the BitsAndBytesConfig API with concrete code examples and VRAM benchmarks.
