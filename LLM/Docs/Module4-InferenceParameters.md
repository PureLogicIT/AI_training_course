# Module 6: Inference Parameters
> Subject: LLM | Difficulty: Intermediate | Estimated Time: 180 minutes

## Objective

After completing this module, you will be able to explain what inference parameters are and why they exist, describe the mechanics of the next-token sampling process in precise detail, and configure temperature, top-p, top-k, min-p, repetition penalty, frequency penalty, presence penalty, stop sequences, max tokens, and seed with intentionality rather than trial and error. You will understand the mathematical relationship between logits, softmax, and the probability distribution that sampling draws from, and you will be able to predict how each parameter shifts that distribution before running a single line of code. You will be able to choose the right parameter combination for deterministic tasks, creative tasks, structured output tasks, and conversational tasks using both the OpenAI API and a local Ollama model.

---

## Prerequisites

- Module 1: Basics of Large Language Models — understanding of next-token prediction, tokenization, and the concept of a probability distribution over the vocabulary
- Module 2: API Services vs Local Models — hands-on experience with the OpenAI API and Ollama; ability to make API calls and read JSON responses
- Module 3: Prompt Engineering — familiarity with system prompts, user/assistant message roles, and the effect of prompt wording on output quality
- Python comfort at the level shown in previous modules: pip, environment variables, working with dictionaries and JSON
- Ollama installed locally with `llama3.2` pulled: `pip install ollama` and `ollama pull llama3.2`

---

## Key Concepts

### What Inference Parameters Are

Every time an LLM generates the next token, it does not simply pick the single most probable word. Instead it runs a multi-step process: (1) the forward pass through the network produces a raw score called a **logit** for every token in the vocabulary; (2) those logits are converted into a probability distribution via the **softmax** function; (3) a **sampling algorithm** draws one token from that distribution. Inference parameters are knobs that modify steps 2 and 3 — they reshape, filter, or re-weight the distribution before sampling occurs.

This is important to internalize: inference parameters do not change the model's weights and they do not change what the model "knows." They only change how the model selects from the distribution its weights produce. The same model with different parameters will produce measurably different outputs from identical prompts.

```
Forward pass
    |
    v
Raw logits: [3.2, 0.1, -1.4, 5.7, 2.3, ...]   (one per vocabulary token)
    |
    v
[Temperature scaling]   →  logits / T
    |
    v
[Softmax]               →  probability distribution summing to 1.0
    |
    v
[Top-k / Top-p / Min-p filtering]  →  zero out low-probability tokens
    |
    v
[Repetition / Frequency / Presence penalty]  →  adjust logits for seen tokens
    |
    v
[Renormalize]           →  redistribute probability mass over remaining tokens
    |
    v
[Sample]                →  draw one token from the filtered distribution
    |
    v
Next token  →  [Stop sequence check]  →  [Max tokens check]  →  continue or halt
```

Every parameter in this module operates at one of these stages. Understanding where in the pipeline each one acts is the key to predicting how they interact.

---

### Logits and Softmax

A **logit** is an unnormalized score. After the final Transformer layer, the model projects its hidden state through a matrix (the language model head) whose rows correspond to vocabulary tokens. The result is a vector of real numbers — one per token. A higher logit means the model assigns that token more weight as the next token, but the raw numbers have no direct probabilistic meaning because they are not bounded and do not sum to 1.

**Softmax** converts the logit vector into a valid probability distribution:

```
softmax(z_i) = exp(z_i) / sum(exp(z_j) for all j)
```

Because softmax uses the exponential function, it amplifies differences between logits: a logit that is 2 points higher than another does not simply get twice the probability — it gets e² ≈ 7.4 times the probability. This exponential amplification is exactly what temperature controls.

A worked example with a vocabulary of five tokens:

```
Token:          "cat"    "dog"    "the"    "a"      "fish"
Logits:          3.2      2.8      1.1      0.4      -0.3

After exp():    24.5     16.4      3.0      1.5       0.7    (sum = 46.1)

Probabilities:  0.531    0.356    0.065    0.033     0.015
```

Without any parameter intervention, sampling from this distribution means "cat" is chosen 53.1% of the time, "dog" 35.6% of the time, and so on.

---

### Temperature

Temperature is the most fundamental inference parameter. It scales the logits before softmax is applied:

```
adjusted_logit_i = logit_i / T
```

**When T < 1.0 (low temperature):** Dividing logits by a number less than 1 makes them larger in magnitude and widens the gaps between them. After softmax, the highest-probability tokens receive even more probability mass — the distribution becomes sharper ("more confident"). At the extreme of T → 0, the model always selects the single highest-logit token (greedy decoding) and the output becomes fully deterministic.

**When T = 1.0:** Logits pass through unchanged. This is the baseline distribution produced by the model's weights.

**When T > 1.0 (high temperature):** Dividing logits by a number greater than 1 shrinks their magnitude and compresses the gaps between them. After softmax, probability mass spreads more evenly across the vocabulary — the distribution becomes flatter ("more uncertain"). At the extreme of T → ∞, all tokens become equally probable.

```
Temperature effect on the five-token example:

T = 0.5  (low):       "cat": 0.814   "dog": 0.163   "the": 0.015   "a": 0.005   "fish": 0.002
T = 1.0  (baseline):  "cat": 0.531   "dog": 0.356   "the": 0.065   "a": 0.033   "fish": 0.015
T = 2.0  (high):      "cat": 0.344   "dog": 0.296   "the": 0.167   "a": 0.132   "fish": 0.061
```

At T = 0.5, "cat" dominates at 81.4%. At T = 2.0, even "fish" now has a 6.1% chance.

**Practical guidance by task type:**

| Task type | Recommended temperature |
|---|---|
| Code generation, math, data extraction | 0.0 – 0.2 |
| Structured output (JSON/XML) | 0.0 – 0.3 |
| Factual Q&A, summarization | 0.2 – 0.5 |
| General-purpose chatbot | 0.5 – 0.9 |
| Creative writing, brainstorming | 0.9 – 1.3 |
| Highly experimental / exploratory | 1.3 – 2.0 |

> **Provider note:** Anthropic (Claude) caps temperature at **1.0** — values above 1.0 return a validation error. OpenAI and Google Gemini accept 0.0–2.0. For cross-provider code, clamp temperature to 0.0–1.0.

---

### Top-k Sampling

Top-k sampling filters the distribution before sampling: only the k tokens with the highest probability are kept; all others are set to zero probability and the remaining probabilities are renormalized to sum to 1.0.

```
Sorted by probability (T = 1.0 example, descending):
Rank 1: "cat"    0.531
Rank 2: "dog"    0.356
Rank 3: "the"    0.065
Rank 4: "a"      0.033
Rank 5: "fish"   0.015

With top-k = 2:
Keep: "cat", "dog"
Discard: "the", "a", "fish"
Renormalized: "cat": 0.598   "dog": 0.402
```

Top-k prevents the model from accidentally sampling extremely improbable tokens (nonsense words, random punctuation) that still technically have non-zero probability after softmax. It is a hard cutoff based on rank.

The weakness of top-k is that the cutoff is insensitive to the shape of the distribution. If the top 50 tokens all have nearly equal probability, k=50 keeps many reasonable tokens. But if one token has probability 0.99 and the next 49 have 0.01 total, k=50 still keeps those 49 very unlikely tokens. Top-p solves this problem.

Setting `top_k = 0` or `top_k = -1` disables top-k filtering on most local runtimes.

---

### Top-p Sampling (Nucleus Sampling)

Top-p sampling (nucleus sampling) selects the smallest set of tokens whose cumulative probability is at least p, then samples from that set. The "nucleus" of the distribution is kept; the long tail is discarded.

```
Sorted by probability descending, with cumulative probability:
Token     Probability    Cumulative
"cat"       0.531          0.531
"dog"       0.356          0.887     ← cumulative crosses 0.85 here
"the"       0.065          0.952
"a"         0.033          0.985
"fish"      0.015          1.000

With top-p = 0.85:
The nucleus is {"cat", "dog"} (cumulative = 0.887 ≥ 0.85)
Renormalized: "cat": 0.598   "dog": 0.402
```

The size of the nucleus adapts to the distribution. When the model is confident (one token dominates), the nucleus is small. When the model is genuinely uncertain (many plausible continuations), the nucleus is large. This adaptive behavior is the core advantage of top-p over top-k.

**Common values:**
- `top_p = 1.0`: no filtering, all tokens are eligible
- `top_p = 0.95`: standard default; removes the most improbable tail
- `top_p = 0.7`: more focused, fewer alternative tokens considered
- `top_p = 0.1`: very focused; only the highest-probability tokens

Top-k and top-p are often applied together: top-k is applied first as a hard ceiling on the number of candidates, then top-p further shrinks the nucleus based on cumulative probability.

---

### Min-p Sampling

Min-p is a newer alternative to top-p that sets a minimum probability threshold *relative to the top token* rather than using a fixed cumulative cutoff. A token is kept only if its probability is at least `min_p × probability_of_top_token`.

```
Top token probability: 0.531
min_p = 0.1

Threshold = 0.1 × 0.531 = 0.053

Keep tokens with probability ≥ 0.053:
"cat"  0.531  ✓
"dog"  0.356  ✓
"the"  0.065  ✓
"a"    0.033  ✗  (0.033 < 0.053)
"fish" 0.015  ✗
```

Min-p scales the threshold with the model's confidence. When the top token has probability 0.99, the threshold is 0.099 — a tight cutoff that only allows near-certain alternatives. When the top token has probability 0.25 (a genuinely uncertain prediction), the threshold is 0.025 — loose, allowing many options. This behaviour is generally more principled than top-p for creative tasks.

Min-p is supported in Ollama and llama.cpp (via the `min_p` option). It is not yet uniformly supported by all cloud APIs.

---

### Repetition Penalty, Frequency Penalty, and Presence Penalty

These three parameters all address the same problem — LLMs tend to repeat themselves — but with different mathematical mechanisms.

**Repetition penalty** (Ollama, llama.cpp, Hugging Face) multiplicatively reduces the logit of any token that has appeared in the output:

```
adjusted_logit = logit / penalty     if the token appeared previously
adjusted_logit = logit               otherwise
```

A penalty of 1.0 has no effect. A penalty of 1.3 reduces the logit of previously seen tokens before softmax, making them less likely to be selected again. Default in Ollama: 1.1.

**Frequency penalty** (OpenAI API, range −2.0 to 2.0) additively reduces a token's logit in proportion to how many times it has already appeared:

```
adjusted_logit = logit − (frequency_penalty × count_of_token_in_output)
```

A token that has appeared 3 times with frequency_penalty = 0.5 will have its logit reduced by 1.5. This penalizes tokens that are used repeatedly throughout a long output.

**Presence penalty** (OpenAI API, range −2.0 to 2.0) additively reduces a token's logit by a flat amount if it has appeared at all, regardless of how many times:

```
adjusted_logit = logit − presence_penalty    if token appeared at least once
adjusted_logit = logit                       otherwise
```

The distinction is subtle but meaningful: frequency penalty scales with repetition count (it increasingly discourages heavily repeated words), while presence penalty is a one-time penalty that encourages topic diversity by discouraging any previously introduced token.

```
Practical guidance:

Goal                                          Parameter choice
──────────────────────────────────────────    ───────────────────────────────────────
Prevent a loop repeating a phrase             repetition_penalty 1.1–1.3 (local)
                                                or frequency_penalty 0.3–0.7 (OpenAI)
Encourage the model to introduce new topics   presence_penalty 0.3–0.7 (OpenAI)
Factual or structured output (JSON, code)     Leave all penalties at 0.0 / 1.0 default
```

Be conservative. Values above 1.5 (repetition_penalty) or 1.0 (frequency/presence penalty) often cause the model to avoid necessary repeated words, producing incoherent or fragmented output.

---

### Stop Sequences

A stop sequence is a string (or list of strings) that tells the model to halt generation immediately when that string appears in the output. Stop sequences operate as a post-generation filter — they do not affect the probability distribution.

```
User prompt:    "List three fruits."
Stop sequence:  "\n4."

Model begins generating:
"1. Apple\n2. Banana\n3. Mango\n4."
                                ^
                                Generation halts here.
```

Common use cases:
- `stop=["```"]` — capture exactly one code block and prevent the model from generating a second
- `stop=["\n\nUser:", "\n\nHuman:"]` — prevent the model from hallucinating further turns in a manually built conversation loop
- `stop=["</answer>"]` — stop at the closing XML tag when prompting for structured XML output

Stop sequences are zero-cost until matched and are one of the most underused inference parameters.

---

### Max Tokens

`max_tokens` (also `max_new_tokens` in local runtimes) sets a hard upper bound on the number of tokens the model will generate in a single response. It does not affect the probability distribution — it simply truncates generation.

```
Context window = input tokens + output tokens
                 ────────────────────────────
                 The sum must not exceed the
                 model's total context window.
```

Setting max tokens too low causes responses to be cut off mid-sentence. A practical approach: set it 20–30% higher than the longest response you expect and rely on stop sequences and well-crafted prompts to terminate generation naturally at the right point. For open-ended chat, most providers default to a high value (e.g., 4096 or 8192).

---

### Seed

A `seed` parameter initializes the random number generator used during sampling. Two calls with identical prompts, parameters, and seed values will produce identical outputs (assuming the same model version and hardware). This is invaluable for:

- Reproducible evaluations: comparing two prompts while holding sampling constant
- Debugging: reproducing a specific surprising output
- Automated testing: asserting that a given prompt produces a given output in a test suite

Setting `temperature = 0.0` also produces deterministic output (greedy decoding); in that case the seed has no effect because no sampling is performed.

**Provider support:** Ollama supports `seed` natively. OpenAI supports it for most models. Anthropic does not expose a seed parameter — use `temperature = 0` for reproducibility with Claude.

---

### How Parameters Interact

Inference parameters do not operate in isolation. Their interactions are the source of most configuration confusion.

The most important interaction is between temperature and top-p:

```
                          top-p
                    low (0.1)          high (0.95–1.0)
                 ┌───────────────────┬──────────────────────┐
temperature  low │  near-greedy,     │  focused,            │
(0.0–0.3)        │  very tight       │  near-greedy         │
                 ├───────────────────┼──────────────────────┤
temperature  high│  oddly focused    │  diverse,            │
(1.0–2.0)        │  (unusual combo)  │  creative, risky     │
                 └───────────────────┴──────────────────────┘
```

When the distribution is already sharp (low temperature), top-p rarely removes any tokens because the mass is concentrated. When the distribution is flat (high temperature), top-p does significant filtering. A common mistake is setting both temperature and top-p to conservative values simultaneously and being surprised when the model becomes extremely terse. The standard recommendation: tune temperature and leave top-p at 0.95, rather than adjusting both.

Similarly, repetition penalties interact with temperature: at very low temperature the model already strongly disfavors previously seen tokens (because high-probability tokens dominate), so repetition penalties add little. At high temperature, repetition penalties become more impactful because the flat distribution otherwise allows any token.

---

## Best Practices

1. **Start with temperature alone; add other parameters only when you observe a specific problem.** Temperature is the highest-leverage parameter for most tasks. Adding top-k, min-p, or penalties preemptively creates a configuration with too many variables to reason about.

2. **Use temperature = 0.0 for any task with a single correct answer.** Code generation, data extraction, classification, and JSON output all benefit from greedy decoding. Introducing randomness adds no value and degrades consistency.

3. **Do not tune both temperature and top-p simultaneously.** They interact in a way that makes it hard to attribute output changes to either variable. Set top-p to 0.95 as a default and tune temperature only.

4. **Keep repetition and frequency penalties near their defaults unless you observe looping.** Penalties above 1.5 (local) or 1.0 (OpenAI) frequently cause the model to avoid necessary repeated words like "the," "and," or field names in JSON, producing incoherent output.

5. **Use stop sequences for structured output extraction instead of relying solely on prompt instructions.** A stop sequence is a hard guarantee; prompt instructions are a soft suggestion. Combining both ("output only JSON" + `stop=["}"]`) produces the most reliable results.

6. **Fix seed when running evaluations or regression tests.** Without a fixed seed, any stochastic output difference between two prompt versions is indistinguishable from sampling variance. Seed first, then evaluate.

7. **Account for the Anthropic temperature cap in cross-provider code.** Claude rejects temperature > 1.0. If you share prompt configurations across providers, always validate temperature before the API call.

8. **Verify parameter names against each provider's documentation.** The same concept has different names: `repeat_penalty` in Ollama, `repetition_penalty` in Hugging Face, and `frequency_penalty` / `presence_penalty` in OpenAI. Passing an unknown parameter usually silently does nothing rather than throwing an error.

---

## Use Cases

### Use Case 1: Deterministic Data Extraction Pipeline

A data engineering team extracts structured fields from thousands of unstructured customer records per day. Every run must produce the same output for the same input to ensure downstream pipeline idempotency. The team uses temperature = 0.0, no repetition penalties (JSON field names are expected to repeat), and a stop sequence to cap output at the closing brace.

**Concepts applied:** temperature = 0.0 (greedy decoding), stop sequences, seed (for test harness), max_tokens sized to the expected JSON payload.

**Outcome:** Extraction results are identical across repeated runs of the same document; differences in output between pipeline runs are attributable to input changes only, not sampling variance.

### Use Case 2: Interactive Storytelling App

A creative writing app gives users a story starter and continues it collaboratively. The team wants varied, surprising continuations that still remain coherent. They use temperature = 1.1, top-p = 0.92, and a light repetition penalty (1.1) to prevent the model from looping on phrases.

**Concepts applied:** high temperature for creativity, top-p to keep continuations coherent, repetition penalty to prevent phrase echoing.

**Outcome:** Each story continuation feels different and surprising while remaining readable. Users report the experience feels genuinely creative rather than formulaic.

### Use Case 3: Multi-Turn Customer Support Bot

A support bot must be helpful and conversational but not creative — the stakes of a wrong answer are high. The team sets temperature = 0.3, top-p = 0.9, and uses stop sequences to prevent the model from hallucinating follow-up turns. They explicitly disable frequency and presence penalties because they want the bot to repeat product names and policy terms accurately.

**Concepts applied:** low temperature for consistency, stop sequences to control turn boundaries, penalties disabled to allow necessary term repetition, max_tokens set to cap response length for mobile readability.

**Outcome:** Responses are consistent across similar queries, use correct product terminology, and fit within the mobile UI's length constraints.

---

## Hands-on Examples

### Example 1: Observing Temperature with Ollama

Run `ollama pull llama3.2` before running this script.

```python
import ollama

# Pull model first: ollama pull llama3.2

PROMPT = "Describe the ocean in one sentence."
TEMPERATURES = [0.0, 0.3, 0.7, 1.2, 1.8]

for temp in TEMPERATURES:
    response = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": PROMPT}],
        options={"temperature": temp, "seed": 42}
    )
    text = response["message"]["content"].strip()
    print(f"T={temp:.1f}: {text}\n")
```

Run this script several times. At T=0.0 with a fixed seed, the output should be identical every run. At T=1.8, it varies noticeably even with the same seed because sampling introduces entropy that the seed only partially constrains at high temperature.

---

### Example 2: Top-k and Top-p with Ollama

```python
import ollama

PROMPT = "Continue this story: The door opened and inside was"
CONFIGS = [
    {"label": "top_k=1  (greedy)",     "top_k": 1,   "top_p": 1.0},
    {"label": "top_k=10, top_p=1.0",   "top_k": 10,  "top_p": 1.0},
    {"label": "top_k=40, top_p=0.9",   "top_k": 40,  "top_p": 0.9},
    {"label": "top_k=100, top_p=0.95", "top_k": 100, "top_p": 0.95},
]

for config in CONFIGS:
    response = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": PROMPT}],
        options={
            "temperature": 1.0,
            "top_k": config["top_k"],
            "top_p": config["top_p"],
            "seed": 99
        }
    )
    text = response["message"]["content"].strip()
    print(f'[{config["label"]}]\n{text}\n{"─"*60}\n')
```

top_k=1 produces a single fixed continuation. Increasing top_k combined with top_p produces progressively more varied story openings.

---

### Example 3: Stop Sequences for Structured Output

```python
import ollama
import json

# Pull model first: ollama pull llama3.2

PROMPT = """Respond with a JSON object only. No explanation.
Format:
{
  "animal": "<name>",
  "legs": <number>,
  "habitat": "<environment>"
}

Animal: penguin"""

response = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": PROMPT}],
    options={
        "temperature": 0.1,
        "stop": ["\n}"]  # halt after the closing brace
    }
)

raw = response["message"]["content"].strip()
raw_complete = raw + "\n}"  # the stop string is consumed — add it back before parsing

try:
    data = json.loads(raw_complete)
    print("Parsed successfully:", data)
    # Expected: {"animal": "penguin", "legs": 2, "habitat": "Antarctic coastline"}
except json.JSONDecodeError as e:
    print("Parse error:", e)
    print("Raw output:", raw_complete)
```

---

### Example 4: Frequency and Presence Penalty with OpenAI

```python
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

PROMPT = "Write a short paragraph about machine learning."

configs = [
    (0.0, 0.0, "No penalties"),
    (0.8, 0.0, "Frequency penalty 0.8 only"),
    (0.0, 0.8, "Presence penalty 0.8 only"),
    (0.5, 0.5, "Both at 0.5"),
]

for freq_pen, pres_pen, label in configs:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": PROMPT}],
        temperature=0.9,
        frequency_penalty=freq_pen,
        presence_penalty=pres_pen,
        max_tokens=120,
    )
    text = response.choices[0].message.content.strip()
    print(f"[{label}]\n{text}\n{'─'*60}\n")

# --- Optional: Ollama equivalent using repeat_penalty ---
# response = ollama.chat(
#     model="llama3.2",
#     messages=[{"role": "user", "content": PROMPT}],
#     options={"temperature": 0.9, "repeat_penalty": 1.3}
# )
```

With no penalties you may notice the model repeats words like "machine learning" or "models." With frequency_penalty=0.8, heavily repeated words are penalized more each time, producing more varied vocabulary. With presence_penalty, the model is pushed toward new topics rather than elaborating on the same ones.

---

### Example 5: Building a Parameter Tuning Script

A single interactive script that lets you experiment with all major parameters against any prompt:

```python
import ollama
import json

# Pull model first: ollama pull llama3.2

def run_with_params(
    prompt: str,
    model: str = "llama3.2",
    temperature: float = 0.7,
    top_k: int = 40,
    top_p: float = 0.9,
    min_p: float = 0.0,
    repeat_penalty: float = 1.1,
    max_tokens: int = 256,
    stop: list[str] | None = None,
    seed: int | None = None,
) -> str:
    options: dict = {
        "temperature": temperature,
        "top_k": top_k,
        "top_p": top_p,
        "min_p": min_p,
        "repeat_penalty": repeat_penalty,
        "num_predict": max_tokens,
    }
    if stop:
        options["stop"] = stop
    if seed is not None:
        options["seed"] = seed

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options=options,
    )
    return response["message"]["content"].strip()


if __name__ == "__main__":
    test_prompt = "Write a two-sentence summary of how neural networks learn."

    # Preset 1: Deterministic (code/extraction)
    print("=== DETERMINISTIC ===")
    print(run_with_params(test_prompt, temperature=0.0, seed=1))

    # Preset 2: Balanced (general chat)
    print("\n=== BALANCED ===")
    print(run_with_params(test_prompt, temperature=0.7, top_p=0.95))

    # Preset 3: Creative (brainstorming)
    print("\n=== CREATIVE ===")
    print(run_with_params(test_prompt, temperature=1.2, top_p=0.95, min_p=0.05))

    # Preset 4: Anti-repetition (long-form text)
    print("\n=== ANTI-REPETITION ===")
    print(run_with_params(test_prompt, temperature=0.8, repeat_penalty=1.3))
```

Modify the preset configurations to explore how the parameter combinations interact on your specific use case.

---

## Common Pitfalls

1. **Setting temperature to 0 and expecting perfectly consistent results across providers.**
   - *Why it happens:* Temperature = 0 (greedy decoding) is deterministic within a single model version, but different providers may use different model versions, quantization levels, or batching strategies.
   - *Incorrect assumption:* "Temperature 0 with the same prompt will always produce the same answer on any deployment."
   - *Correct understanding:* Temperature 0 guarantees determinism within a single model serving infrastructure. Across providers or model version updates, outputs may still differ. Use `seed` and pin the model version string for maximum reproducibility.

2. **Tuning temperature and top-p simultaneously.**
   - *Why it happens:* Both parameters affect output diversity, so it feels logical to adjust both.
   - *Incorrect:* Setting temperature=1.5 and top-p=0.3 expecting "creative but coherent" output.
   - *Correct:* Fix top-p at 0.9–0.95 and tune only temperature. The interaction between the two is non-intuitive; adjusting both at once makes it impossible to attribute output changes to either variable.

3. **Setting repetition penalty too high and getting fragmented output.**
   - *Why it happens:* Developers want to prevent any repetition and overshoot the penalty.
   - *Incorrect:* `repeat_penalty = 2.0` — the model will avoid common words ("the," "is," "and") that legitimately need to repeat.
   - *Correct:* Stay in the range 1.05–1.3 for repetition penalty. If you still observe looping at 1.3, the problem is usually the prompt design, not the penalty value.

4. **Forgetting that stop sequences consume the matched string differently across APIs.**
   - *Why it happens:* Stop sequence behavior at the boundary is not standardized.
   - *Incorrect:* Assuming `stop=["}"]` always includes the closing brace in the output.
   - *Correct:* Test empirically with your specific provider and model. Some APIs include the stop token; others exclude it. Add the stop string back manually before parsing if needed (as shown in Example 3).

5. **Applying frequency/presence penalties to structured output tasks.**
   - *Why it happens:* Penalties are set globally and not turned off for specific task types.
   - *Incorrect:* Using presence_penalty=0.7 on a task that generates JSON — field names like `"name"`, `"id"`, `"value"` need to appear in every object.
   - *Correct:* Set all penalties to 0.0 for structured output. Reserve penalties for long-form prose generation where repetition is genuinely undesirable.

6. **Passing unsupported parameters and not noticing the silent failure.**
   - *Why it happens:* Most APIs silently ignore unknown parameters rather than raising an error.
   - *Incorrect:* Passing `frequency_penalty` to Ollama (which does not support it) and assuming it had an effect.
   - *Correct:* Verify parameter names per provider. In Ollama use `repeat_penalty`; in OpenAI use `frequency_penalty` and `presence_penalty`; in Hugging Face use `repetition_penalty`. Log the actual options you sent and verify the response headers/metadata.

7. **Ignoring max_tokens and being surprised by truncated outputs.**
   - *Why it happens:* The default max_tokens is often lower than expected (some APIs default to 256 or 512).
   - *Incorrect:* Asking the model to write a detailed 5-page report without setting max_tokens, then wondering why it cuts off mid-sentence.
   - *Correct:* Always set max_tokens explicitly based on the task. For open-ended generation, start with a generous value (4096) and add a stop sequence or prompt-based length instruction to control actual output length.

---

## Summary

- Inference parameters operate at the sampling stage of text generation — they reshape, filter, or re-weight the probability distribution produced by the model's forward pass without altering the model's weights.
- **Temperature** is the most impactful parameter: it scales logits before softmax and controls the sharpness of the probability distribution. Use 0.0–0.2 for deterministic tasks; 0.5–1.0 for general use; up to 2.0 for creativity (OpenAI/Gemini only — Anthropic caps at 1.0).
- **Top-k** applies a hard rank cutoff; **top-p** (nucleus sampling) applies an adaptive cumulative probability cutoff; **min-p** applies a threshold relative to the top token. They are often used in combination and operate after temperature scaling.
- **Repetition, frequency, and presence penalties** all discourage repeated tokens but via different mechanisms: multiplicative logit division (local runtimes), linear scaling by count (frequency), or flat one-time penalty (presence).
- **Stop sequences** and **max_tokens** control output length and termination without affecting the probability distribution — they are hard post-generation constraints, not soft statistical nudges.
- **Seed** enables reproducible sampling, which is essential for evaluation and testing; set `temperature = 0` for fully deterministic output when a seed is not available.

---

## Further Reading

- [Holtzman et al. (2020) — "The Curious Case of Neural Text Degeneration"](https://arxiv.org/abs/1904.09751) — The paper that introduced top-p (nucleus) sampling, with a clear analysis of why greedy decoding and beam search produce repetitive, degenerate text.
- [Ollama API Documentation — Modelfile Options](https://github.com/ollama/ollama/blob/main/docs/modelfile.md#valid-parameters-and-values) — Full reference for all inference parameters supported by Ollama, including `temperature`, `top_k`, `top_p`, `min_p`, `repeat_penalty`, `repeat_last_n`, `mirostat`, and `seed`.
- [OpenAI API Reference — Chat Completions](https://platform.openai.com/docs/api-reference/chat/create) — Authoritative parameter reference for `temperature`, `top_p`, `frequency_penalty`, `presence_penalty`, `stop`, `max_tokens`, and `logprobs`.
- [Anthropic API Reference — Messages](https://docs.anthropic.com/en/api/messages) — Covers `temperature` (0.0–1.0), `top_p`, `top_k`, `stop_sequences`, and `max_tokens` for Claude models.
- [Hugging Face GenerationConfig](https://huggingface.co/docs/transformers/main_classes/text_generation) — Full parameter surface for local generation via the `transformers` library, covering `do_sample`, `repetition_penalty`, beam search options, and `min_new_tokens`.
- [Min-p Sampling: A Simple Dynamic Truncation Scheme](https://arxiv.org/abs/2407.01082) — Research paper introducing min-p sampling, explaining the motivation and comparing it empirically against top-p on creative and factual tasks.
- [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) — Open-source tool for evaluating LLMs across benchmarks; useful for systematically measuring how inference parameter changes affect task accuracy, not just subjective quality.
