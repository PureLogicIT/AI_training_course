# Module 10: Structured Output & Function Calling
> Subject: AI Development | Difficulty: Intermediate-Advanced | Estimated Time: 360 minutes

## Objective

After completing this module, you will understand why structured output is a critical production skill and where it fits on the reliability spectrum — from prompt-only heuristics to grammar-constrained token sampling. You will use Ollama's native JSON mode and schema-constrained output API with the Python SDK, define and validate structured responses with Pydantic `BaseModel`, and integrate LangChain's output parser ecosystem (`PydanticOutputParser`, `with_structured_output`, `OutputFixingParser`, `RetryOutputParser`). You will use `llama-cpp-python`'s GBNF grammar system to constrain token sampling at the sampler level — the most reliable approach for smaller local models. You will implement the full function-calling round-trip with Ollama's tool-calling API: define a tools schema, parse `tool_calls` from the response, execute the function, and feed results back for synthesis. You will apply all of these techniques to real-world extraction and classification pipelines with batch processing, error handling, and storage. All examples run locally against Ollama or `llama-cpp-python` — no API keys or cloud services are required.

---

## Prerequisites

- Completed **Module 0: Setup & Local AI Stack** — Ollama is installed, running, and models can be pulled
- Completed **Module 1: Working with Local Models** — comfortable with `ollama.chat()` and inference parameters
- Completed **Module 3: LangChain Fundamentals** — understand `ChatOllama`, LCEL, prompt templates, and output parsers
- Completed **Module 8: Agents & Tool Use** — understand the tool-calling contract and the `@tool` decorator
- Python 3.10 or later with an active virtual environment
- At least one model pulled that supports structured output (see Section 2 for the list)
- Comfortable with Pydantic v2 (`BaseModel`, `Field`, `model_validate_json`)

> Note: Every executable code block in this module was written for **Ollama 0.5+**, **ollama-python 0.4+**, **langchain-ollama 0.3+**, and **llama-cpp-python 0.3+** (the stable release series as of April 2026). Where a version-specific behavior is relevant it is noted inline.

---

## Installation

Install all packages used in this module:

```bash
pip install "ollama>=0.4.0" \
            "pydantic>=2.7.0" \
            "langchain>=1.0.0" \
            "langchain-ollama>=0.3.0" \
            "langchain-core>=1.3.0"
```

For the llama-cpp-python grammar examples (Section 5 and Example 2), install the CPU-only build if you do not have a GPU, or the appropriate pre-built wheel for your hardware:

```bash
# CPU-only build
pip install "llama-cpp-python>=0.3.0"

# If you have a CUDA GPU, install with GPU support instead:
# CMAKE_ARGS="-DGGML_CUDA=on" pip install "llama-cpp-python>=0.3.0"
```

Pull models for the hands-on examples:

```bash
ollama pull qwen2.5          # 7B — excellent structured output, ~4.4 GB
ollama pull llama3.2         # 3B — good structured output, lighter weight, ~2 GB
ollama pull qwen3            # 8B — latest Qwen generation, strong reliability, ~5.2 GB
```

For llama-cpp-python examples you will need a GGUF model file. Download one from Hugging Face:

```bash
# Example: Qwen2.5 3B in Q4_K_M quantization (~2.0 GB)
# Download from: https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF
# Or use any GGUF you already have from Module 1/2.
```

---

## Key Concepts

### 1. Why Structured Output Matters

#### The Core Problem

LLMs are trained to generate fluent natural language. When you call `ollama.chat()` and ask for a list of cities, you get a paragraph. When you ask for JSON, you might get JSON — or you might get JSON wrapped in a code fence, followed by an explanation, followed by a caveat. Every downstream system that tries to `json.loads()` that response has a bug waiting to happen.

**Applications need typed data.** A job board needs a `salary_range` as a numeric tuple, not "competitive compensation." A medical record system needs a `date_of_birth` as an ISO date string, not "born in the mid-1980s." An invoice parser needs `line_items` as a list of `(description, quantity, unit_price)` tuples, not a prose summary.

The gap between "LLMs return text" and "applications need types" is where structured output lives.

#### The Reliability Spectrum

There are five approaches to getting structured data from an LLM, arranged from least to most reliable:

| Approach | Mechanism | Reliability | Best For |
|---|---|---|---|
| **Prompt-only** | Ask the model to return JSON in the system prompt | Low — model can ignore or partially comply | Quick prototypes, large capable models |
| **Output parsers** | Parse and validate the text response in Python | Medium — parsing fails on malformed output | When you control the prompt and use capable models |
| **JSON mode** | Tell the model via API to output valid JSON | Medium-High — guarantees valid JSON, not your schema | When any valid JSON is acceptable |
| **Schema-constrained (JSON schema)** | Pass your schema to the API; model is guided to match it | High — model is steered toward your schema | Production with Ollama's structured output API |
| **Grammar-constrained (GBNF)** | Constrain the token sampler to only emit schema-valid tokens | Very High — mathematically cannot produce invalid output | Smaller local models, critical reliability requirements |

Each step up the spectrum trades implementation simplicity for reliability. In production with local models, you almost never want to rely on prompt-only approaches. You want at minimum JSON mode, ideally schema-constrained output, and for the highest reliability requirements you want grammar-constrained generation.

#### When Each Approach Is Appropriate

**Prompt-only** is acceptable when:
- You are using a very large, capable model (70B+) with strong instruction following
- The output format is simple (a single number, a category label)
- Failures are acceptable and not user-facing

**Output parsers** are appropriate when:
- You are already using LangChain and want to add validation
- The model is capable but the API does not offer JSON mode
- You want to add retry logic on parse failure

**JSON mode** (`format="json"`) is appropriate when:
- You need guaranteed JSON syntax but your application can handle varying schemas
- You are doing exploratory extraction where the schema is flexible

**Schema-constrained output** (Ollama's structured output) is the right default for most production use cases with local models. It guides the model to match your schema without modifying the sampler.

**Grammar-constrained generation** (GBNF via llama-cpp-python) is appropriate when:
- You are using smaller local models (3B–7B) that struggle with complex schemas
- Output correctness is non-negotiable (medical, financial, legal data)
- You cannot tolerate retry loops

---

### 2. JSON Mode with Ollama

#### Simple JSON Mode

The simplest structured output feature in Ollama is `format="json"`. This tells the model to output valid JSON syntax, but does not constrain the schema:

```python
import json
import ollama

response = ollama.chat(
    model="qwen2.5",
    messages=[
        {
            "role": "system",
            "content": "You are a data extraction assistant. Always respond with valid JSON.",
        },
        {
            "role": "user",
            "content": "Extract the key facts from this text as JSON: "
                       "Alice Johnson, 34, works as a software engineer at Acme Corp "
                       "in San Francisco. Her salary is $120,000 per year.",
        },
    ],
    format="json",
    options={"temperature": 0},
)

data = json.loads(response.message.content)
print(data)
# Output will be valid JSON but schema may vary between runs
```

`format="json"` guarantees syntactically valid JSON but **does not guarantee** that the fields match what your application expects. The model decides the field names and structure.

#### Schema-Constrained Output (Ollama's Structured Output)

Ollama 0.5+ supports passing a full JSON Schema to the `format` parameter. The model is guided to produce output that matches your schema exactly. This is Ollama's structured output feature:

```python
import json
import ollama

# Define the JSON schema directly
person_schema = {
    "type": "object",
    "properties": {
        "name":       {"type": "string"},
        "age":        {"type": "integer"},
        "job_title":  {"type": "string"},
        "company":    {"type": "string"},
        "city":       {"type": "string"},
        "salary_usd": {"type": "number"},
    },
    "required": ["name", "age", "job_title", "company", "city", "salary_usd"],
}

response = ollama.chat(
    model="qwen2.5",
    messages=[
        {
            "role": "system",
            "content": "Extract the structured data from the user's text. "
                       "Return only the JSON object, no explanation.",
        },
        {
            "role": "user",
            "content": "Alice Johnson, 34, works as a software engineer at Acme Corp "
                       "in San Francisco. Her salary is $120,000 per year.",
        },
    ],
    format=person_schema,
    options={"temperature": 0},
)

data = json.loads(response.message.content)
print(data)
# {"name": "Alice Johnson", "age": 34, "job_title": "software engineer",
#  "company": "Acme Corp", "city": "San Francisco", "salary_usd": 120000.0}
```

#### Schema-Constrained Output with the Python SDK and Pydantic

The `ollama` Python library integrates directly with Pydantic. Pass `MyModel.model_json_schema()` to `format` and validate the response with `MyModel.model_validate_json()`:

```python
import ollama
from pydantic import BaseModel, Field

class Person(BaseModel):
    name:       str
    age:        int
    job_title:  str
    company:    str
    city:       str
    salary_usd: float = Field(description="Annual salary in US dollars")

response = ollama.chat(
    model="qwen2.5",
    messages=[
        {
            "role": "system",
            "content": "Extract the structured data from the user's text.",
        },
        {
            "role": "user",
            "content": "Alice Johnson, 34, works as a software engineer at Acme Corp "
                       "in San Francisco. Her salary is $120,000 per year.",
        },
    ],
    format=Person.model_json_schema(),
    options={"temperature": 0},
)

person = Person.model_validate_json(response.message.content)
print(person)
# Person(name='Alice Johnson', age=34, job_title='software engineer',
#         company='Acme Corp', city='San Francisco', salary_usd=120000.0)
print(f"Name: {person.name}, Salary: ${person.salary_usd:,.0f}")
```

#### OpenAI-Compatible Endpoint

If you are using the OpenAI Python client pointed at Ollama's OpenAI-compatible endpoint, use `response_format`:

```python
from openai import OpenAI
import json

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # required but ignored by Ollama
)

response = client.chat.completions.create(
    model="qwen2.5",
    messages=[
        {"role": "system", "content": "Extract structured data as JSON."},
        {"role": "user", "content": "Bob Smith is a 28-year-old data analyst at DataCo."},
    ],
    response_format={"type": "json_object"},
    temperature=0,
)

data = json.loads(response.choices[0].message.content)
print(data)
```

#### Models That Support Ollama Structured Output

Ollama's schema-constrained output works best with models that have strong instruction following. As of April 2026, the most reliable options for structured output via Ollama are:

| Model | Ollama Name | Size | Structured Output Quality |
|---|---|---|---|
| Qwen2.5 7B Instruct | `qwen2.5` | ~4.4 GB | Excellent — recommended default |
| Qwen3 8B | `qwen3` | ~5.2 GB | Excellent — latest generation |
| Llama 3.2 3B Instruct | `llama3.2` | ~2 GB | Good — lightweight option |
| Llama 3.1 8B Instruct | `llama3.1` | ~4.7 GB | Good |
| Phi-4 Mini | `phi4-mini` | ~2.5 GB | Good — Microsoft's compact model |

---

### 3. Pydantic for Output Validation

#### Why Pydantic and LLMs Are a Natural Pair

Pydantic is Python's standard library for data validation. You define a schema as a class, Pydantic generates JSON Schema from it, and you validate any dict or JSON string against it. For LLM output:

- `MyModel.model_json_schema()` gives you a JSON Schema to pass to the model API
- `MyModel.model_validate_json(response_string)` parses and validates the response in one call
- Pydantic raises `ValidationError` with detailed field-level error messages when the model output does not conform

#### Designing Schemas for Local Models

The schema you design has a direct impact on whether a local model can fill it reliably. Follow these principles:

**Use clear, descriptive field names.** A field named `addr` is harder for a model to fill correctly than `street_address`. Field names are part of the model's context.

**Use `Field(description=...)` for ambiguous fields.** The description is included in the JSON Schema and propagates to the model's context in some frameworks.

**Prefer flat schemas when possible.** Deeply nested schemas with 3+ levels of nesting significantly increase failure rates on 7B models.

**Use `Optional` fields for data that may be absent in the source text.** If you mark a field as required and the source text does not contain that information, the model will hallucinate a value.

**Use `Literal` types for enumerations.** A field typed as `Literal["invoice", "receipt", "statement"]` is much more reliable than a free `str` field with a description asking for one of those values.

#### Basic Model Design

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal

class InvoiceLineItem(BaseModel):
    description: str = Field(description="Description of the product or service")
    quantity:    float
    unit_price:  float = Field(description="Price per unit in USD")
    total:       float = Field(description="quantity * unit_price")

class Invoice(BaseModel):
    invoice_number: str
    vendor_name:    str
    vendor_address: Optional[str] = None
    issue_date:     str = Field(description="Date in YYYY-MM-DD format")
    due_date:       Optional[str] = Field(
        default=None,
        description="Due date in YYYY-MM-DD format, if stated"
    )
    line_items:     list[InvoiceLineItem]
    subtotal:       float
    tax_amount:     Optional[float] = None
    total_amount:   float
    currency:       Literal["USD", "EUR", "GBP", "CAD"] = "USD"
```

#### Nested Models

```python
from pydantic import BaseModel, Field
from typing import Optional

class Address(BaseModel):
    street:  str
    city:    str
    state:   Optional[str] = None
    country: str
    zip_code: Optional[str] = None

class Company(BaseModel):
    name:    str
    address: Address
    website: Optional[str] = None
    founded: Optional[int] = Field(
        default=None,
        description="Year the company was founded, as an integer"
    )
```

#### Field Validators

Use `@field_validator` to add custom validation logic that runs after Pydantic's type checking:

```python
from pydantic import BaseModel, Field, field_validator
import re

class ContactRecord(BaseModel):
    name:  str
    email: str
    phone: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError(f"Invalid email format: {v}")
        return v.lower().strip()

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, v):
        if v is None:
            return v
        # Strip everything except digits and leading +
        digits = re.sub(r"[^\d+]", "", str(v))
        return digits if digits else None
```

#### Parsing and Handling Validation Errors

```python
import json
import ollama
from pydantic import BaseModel, ValidationError
from typing import Optional

class ExtractedEvent(BaseModel):
    event_name: str
    date:       str
    location:   Optional[str] = None
    attendees:  Optional[int] = None

def extract_event(text: str) -> ExtractedEvent | None:
    """Extract event data from text, returning None on validation failure."""
    response = ollama.chat(
        model="qwen2.5",
        messages=[
            {
                "role": "system",
                "content": "Extract event information from the text as structured JSON.",
            },
            {"role": "user", "content": text},
        ],
        format=ExtractedEvent.model_json_schema(),
        options={"temperature": 0},
    )

    try:
        event = ExtractedEvent.model_validate_json(response.message.content)
        return event
    except ValidationError as e:
        print(f"Validation failed: {e}")
        # Log the raw response for debugging
        print(f"Raw model output: {response.message.content}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return None

# Test it
result = extract_event(
    "The Python Meetup will be held on 2026-05-15 at the Downtown Library. "
    "About 80 people are expected to attend."
)
if result:
    print(result.model_dump())
```

#### Designing Schemas That Local Models Can Fill

Rules of thumb from production experience with 3B–7B models:

- **Keep required field count under 10** for reliable results with 7B models
- **Avoid deeply nested schemas** — more than 2 levels of nesting drops reliability
- **Use `Optional` generously** — let the model skip fields when data is absent
- **Use `Literal` for categorical fields** — it constrains the output space dramatically
- **Use `int` not `float` for counts** — models occasionally emit `"3.0"` instead of `3`
- **Include the schema in the system prompt as well** when using prompt-only approaches

---

### 4. LangChain Output Parsers

LangChain provides a family of output parsers that sit between the LLM response and your application code. Each parser handles a specific use case.

#### `StrOutputParser`

The simplest parser — returns the model's response as a plain string. Useful as the terminal step in chains that produce natural language output:

```python
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOllama(model="qwen2.5", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", "Summarize the following text in one sentence."),
    ("human", "{text}"),
])

chain = prompt | llm | StrOutputParser()
result = chain.invoke({"text": "LLMs are powerful but need careful handling of their outputs."})
print(result)
```

#### `JsonOutputParser`

Parses the model's text response as JSON. Does not validate against a schema but is useful for exploratory extraction:

```python
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

llm = ChatOllama(model="qwen2.5", format="json", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Extract data from the text and return it as a JSON object with keys: "
        "name, company, role, years_experience.",
    ),
    ("human", "{text}"),
])

chain = prompt | llm | JsonOutputParser()
result = chain.invoke({
    "text": "Sarah Chen has been a DevOps engineer at CloudScale Inc for 6 years."
})
print(result)
# {"name": "Sarah Chen", "company": "CloudScale Inc",
#  "role": "DevOps engineer", "years_experience": 6}
```

#### `PydanticOutputParser`

Injects format instructions into the prompt (so the model knows what schema to fill) and then validates the response against your Pydantic model. This approach works without native JSON mode support because it relies on prompt engineering plus parsing:

```python
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field
from typing import Optional

class JobPosting(BaseModel):
    title:           str = Field(description="Job title")
    company:         str = Field(description="Company name")
    location:        str = Field(description="City and state or 'Remote'")
    salary_min:      Optional[int] = Field(default=None, description="Minimum salary in USD")
    salary_max:      Optional[int] = Field(default=None, description="Maximum salary in USD")
    required_skills: list[str] = Field(description="List of required technical skills")
    experience_years: Optional[int] = Field(
        default=None, description="Minimum years of experience required"
    )
    remote:          bool = Field(description="True if the position is fully remote")

llm = ChatOllama(model="qwen2.5", temperature=0)
parser = PydanticOutputParser(pydantic_object=JobPosting)

# PydanticOutputParser generates format instructions automatically
prompt = PromptTemplate(
    template=(
        "Extract structured information from the job posting below.\n\n"
        "{format_instructions}\n\n"
        "Job Posting:\n{job_text}"
    ),
    input_variables=["job_text"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

chain = prompt | llm | parser

raw_posting = """
Senior Python Engineer at TechCorp
Location: Austin, TX (Remote OK)
Salary: $140,000 - $180,000/year

We're looking for a senior engineer with 5+ years of Python experience.
Must have: FastAPI, PostgreSQL, Docker, AWS.
Nice to have: Kubernetes, Kafka.
"""

result: JobPosting = chain.invoke({"job_text": raw_posting})
print(result.model_dump())
```

#### `with_structured_output` on `ChatOllama`

The preferred approach in LangChain for getting typed output from `ChatOllama`. As of `langchain-ollama` 0.3.0, the default method is `json_schema`, which uses Ollama's schema-constrained output API:

```python
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Optional, Literal

class DocumentClassification(BaseModel):
    category:   Literal["invoice", "contract", "report", "email", "other"]
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    summary:    str   = Field(description="One-sentence summary of the document")
    language:   Optional[str] = Field(
        default=None, description="Detected language of the document"
    )

llm = ChatOllama(model="qwen2.5", temperature=0)

# .with_structured_output() returns a Runnable that outputs a DocumentClassification instance
structured_llm = llm.with_structured_output(
    DocumentClassification,
    method="json_schema",    # uses Ollama's schema-constrained output (default in 0.3.0+)
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "Classify the following document and extract metadata."),
    ("human", "{document_text}"),
])

chain = prompt | structured_llm

result: DocumentClassification = chain.invoke({
    "document_text": "INVOICE #1042\nFrom: Acme Supplies\nTo: WidgetCo\nTotal: $4,250.00"
})

print(f"Category: {result.category}")
print(f"Confidence: {result.confidence:.0%}")
print(f"Summary: {result.summary}")
```

The three `method` values available in `langchain-ollama` 0.3.0+:

| Method | Mechanism | Notes |
|---|---|---|
| `"json_schema"` | Passes schema to Ollama's `format` parameter | Default. Most reliable. |
| `"function_calling"` | Uses Ollama's tool-calling API under the hood | Requires a tool-calling-capable model |
| `"json_mode"` | Sets `format="json"` | Least constrained; requires format instructions in the prompt |

#### `include_raw=True` for Debugging

When you need to see both the validated output and the raw model response (useful for debugging validation failures):

```python
structured_llm_debug = llm.with_structured_output(
    DocumentClassification,
    method="json_schema",
    include_raw=True,
)

result = structured_llm_debug.invoke("INVOICE #1042\nTotal: $4,250.00")
print("Parsed:", result["parsed"])
print("Raw:", result["raw"].content)
if result["parsing_error"]:
    print("Error:", result["parsing_error"])
```

#### `OutputFixingParser`

When a model produces slightly malformed JSON or output that almost matches your schema, `OutputFixingParser` sends the bad output back to the LLM with a correction instruction:

```python
from langchain.output_parsers import OutputFixingParser
from langchain_core.output_parsers import PydanticOutputParser
from langchain_ollama import ChatOllama
from pydantic import BaseModel

class SimpleRecord(BaseModel):
    name:  str
    value: int
    units: str

llm    = ChatOllama(model="qwen2.5", temperature=0)
parser = PydanticOutputParser(pydantic_object=SimpleRecord)

# OutputFixingParser wraps the primary parser. On parse failure it calls the
# LLM again with the bad output and the error message to produce a corrected version.
fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=llm)

# Simulate a slightly malformed response the model might produce
bad_output = '{"name": "temperature", "value": "23", "units": "Celsius"}'
# Note: "value" is a string "23" not an integer 23

result = fixing_parser.parse(bad_output)
print(result)  # SimpleRecord(name='temperature', value=23, units='Celsius')
```

#### `RetryOutputParser`

`RetryOutputParser` (also called `RetryWithErrorOutputParser`) is more aggressive than `OutputFixingParser`: it re-runs the entire original prompt, appending the error and the bad output as context, asking the model to try again from scratch:

```python
from langchain.output_parsers import RetryOutputParser
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_ollama import ChatOllama
from pydantic import BaseModel

class Measurement(BaseModel):
    quantity: float
    unit:     str
    substance: str

llm    = ChatOllama(model="qwen2.5", temperature=0)
parser = PydanticOutputParser(pydantic_object=Measurement)

prompt = PromptTemplate(
    template="Extract the measurement from this text.\n{format_instructions}\n\nText: {text}",
    input_variables=["text"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

# RetryOutputParser re-issues the full prompt with the error appended on failure
retry_parser = RetryOutputParser.from_llm(parser=parser, llm=llm)

prompt_value = prompt.format_prompt(text="We used 2.5 kilograms of sodium chloride.")
bad_output   = '{"quantity": 2.5, "unit": "kg"}'  # missing "substance"

result = retry_parser.parse_with_prompt(bad_output, prompt_value)
print(result)  # Measurement(quantity=2.5, unit='kg', substance='sodium chloride')
```

---

### 5. Grammar-Constrained Generation with llama.cpp

#### What GBNF Grammars Are

GBNF (GGML Backus-Naur Form) is a formal grammar notation used by llama.cpp to constrain the token sampler during generation. Instead of post-processing the output and hoping the model produced valid JSON, GBNF makes it mathematically impossible for the model to produce a token that would result in invalid output.

Here is how it works at the sampling layer:

1. You define a GBNF grammar that describes the set of valid outputs
2. After every token is generated, the grammar engine checks which tokens are valid next given the current output so far
3. The probability of every invalid token is set to zero before sampling
4. The sampler can only pick from tokens that keep the output on a valid path through the grammar

This means: if your grammar says the output must be a JSON object with a required field `name` of type string, the model cannot generate output that violates this — not because it chose not to, but because those tokens were mathematically excluded.

#### Why This Matters for Smaller Local Models

Larger models (70B+) have strong enough instruction following that prompt-based JSON requests succeed most of the time. Smaller models (3B–7B) are more erratic. On a complex schema, a 7B model might succeed 85% of the time with prompt-only approaches, meaning 15% of requests require a retry or fail. Grammar-constrained generation raises this to ~100% by operating below the model's language understanding — at the token sampling level.

The tradeoff: grammar-constrained generation is available through `llama-cpp-python` directly, not through Ollama (Ollama's schema-constrained output is different — it guides the model but does not constrain the sampler). If you need grammar-level guarantees, use `llama-cpp-python`.

#### Simple GBNF Example

A GBNF grammar that constrains output to a JSON object with specific fields:

```
root   ::= object
object ::= "{" ws "\"status\"" ws ":" ws string ws "," ws "\"code\"" ws ":" ws number ws "}"
string ::= "\"" [^"]* "\""
number ::= [0-9]+ ("." [0-9]+)?
ws     ::= [ \t\n]*
```

Reading a grammar file and using it with `llama-cpp-python`:

```python
from llama_cpp import Llama, LlamaGrammar

# Load the model (update the path to your GGUF file)
llm = Llama(
    model_path="/path/to/qwen2.5-3b-instruct-q4_k_m.gguf",
    n_ctx=2048,
    verbose=False,
)

# Write the grammar inline (or load from a .gbnf file)
grammar_text = r"""
root   ::= object
value  ::= object | array | string | number | "true" | "false" | "null"
object ::= "{" ws (string ":" ws value ("," ws string ":" ws value)*)? ws "}"
array  ::= "[" ws (value ("," ws value)*)? ws "]"
string ::= "\"" ([^"\\] | "\\" .)* "\""
number ::= "-"? ([0-9] | [1-9] [0-9]*) ("." [0-9]+)? ([eE] [-+]? [0-9]+)?
ws     ::= [ \t\n\r]*
"""

grammar = LlamaGrammar.from_string(grammar_text)

response = llm(
    "Extract the person's name and age as a JSON object:\n"
    "Marcus Thompson is a 42-year-old architect.\n",
    grammar=grammar,
    max_tokens=200,
    temperature=0.0,
)

import json
output_text = response["choices"][0]["text"]
print(output_text)
data = json.loads(output_text)
print(data)
```

#### `LlamaGrammar.from_json_schema()`

The most practical way to use GBNF for structured extraction is to let `llama-cpp-python` convert your JSON Schema (or Pydantic schema) into a GBNF grammar automatically:

```python
import json
from llama_cpp import Llama, LlamaGrammar
from pydantic import BaseModel, Field
from typing import Optional, Literal

class MedicalRecord(BaseModel):
    patient_name:  str
    date_of_birth: str = Field(description="Date in YYYY-MM-DD format")
    diagnosis:     str
    severity:      Literal["mild", "moderate", "severe"]
    medications:   list[str]
    follow_up_days: Optional[int] = Field(
        default=None, description="Days until follow-up appointment"
    )

# Generate JSON Schema from Pydantic model
schema = MedicalRecord.model_json_schema()

# Convert the JSON Schema to a GBNF grammar
grammar = LlamaGrammar.from_json_schema(json.dumps(schema))

# Load the model
llm = Llama(
    model_path="/path/to/your-model.gguf",
    n_ctx=2048,
    verbose=False,
)

# Run inference with grammar constraint
note = (
    "Patient: John Rivera, DOB 1985-03-22. "
    "Diagnosed with moderate hypertension. "
    "Prescribed lisinopril 10mg and amlodipine 5mg. "
    "Return in 30 days."
)

response = llm(
    f"Extract the medical record information as structured JSON:\n\n{note}\n",
    grammar=grammar,
    max_tokens=512,
    temperature=0.0,
)

output_text = response["choices"][0]["text"]
record = MedicalRecord.model_validate_json(output_text)
print(record.model_dump())
```

#### Grammar-Constrained vs. Prompt-Only: What the Difference Looks Like

The practical difference between prompt-only JSON requests and grammar-constrained output on a 3B model:

- **Prompt-only**: The model might output `{"patient_name": "John Rivera", "date_of_birth": "March 22, 1985", ...}` — the date is in the wrong format, so your validator fails. Or it wraps the JSON in markdown code fences. Or it adds a trailing explanation.
- **Grammar-constrained**: The model cannot produce invalid output. The sampler enforces the schema at each token position. The output is always a parseable, schema-valid JSON object.

> **Note:** `LlamaGrammar.from_json_schema()` was introduced in `llama-cpp-python` 0.1.78. Verify your installed version supports it with `pip show llama-cpp-python`. If it is not available, use `LlamaGrammar.from_string()` with a hand-written GBNF grammar or a GBNF grammar generated by the `json_schema_to_grammar.py` script in the llama.cpp repository.

---

### 6. Function Calling / Tool Calling Mechanics

#### What Function Calling Is

Function calling (also called tool calling) is a protocol where you describe callable functions to the LLM in your API request, and instead of generating a text response, the model outputs a structured call to one of those functions — including the arguments it wants to pass.

Your application receives the function call specification, executes the actual function in Python, and returns the result to the model. The model then generates a final natural language response incorporating the function's output.

This is different from structured output in a key way: structured output extracts data from existing text. Function calling is a mechanism for the model to request information or actions from your application dynamically.

#### The Full Round-Trip

The complete function-calling cycle has four steps:

```
1. Your app sends: user query + list of available tools (with schemas)
        |
        v
2. Model responds with: tool_calls (function name + arguments)
        |
        v
3. Your app: executes the function with the given arguments
        |
        v
4. Your app sends: original conversation + tool result as a "tool" message
        |
        v
5. Model responds with: final natural language answer incorporating the result
```

#### Defining Tools for Ollama

In Ollama's tool-calling API, tools are defined as a list of dictionaries, each describing one callable function:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Get the current stock price for a ticker symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol, e.g. AAPL or MSFT",
                    },
                    "currency": {
                        "type": "string",
                        "enum": ["USD", "EUR", "GBP"],
                        "description": "Currency for the price. Defaults to USD.",
                    },
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_info",
            "description": "Get basic information about a publicly traded company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol",
                    },
                },
                "required": ["ticker"],
            },
        },
    },
]
```

#### Complete Round-Trip Example with Ollama

```python
import json
import ollama

# ── 1. Define the actual Python functions ─────────────────────────────────────

def get_stock_price(ticker: str, currency: str = "USD") -> dict:
    """Simulated stock price lookup."""
    prices = {
        "AAPL": 182.50,
        "MSFT": 415.20,
        "GOOGL": 175.80,
    }
    price = prices.get(ticker.upper(), 0.0)
    return {
        "ticker":   ticker.upper(),
        "price":    price,
        "currency": currency,
    }

def get_company_info(ticker: str) -> dict:
    """Simulated company info lookup."""
    companies = {
        "AAPL":  {"name": "Apple Inc.",      "sector": "Technology", "employees": 161000},
        "MSFT":  {"name": "Microsoft Corp.", "sector": "Technology", "employees": 221000},
        "GOOGL": {"name": "Alphabet Inc.",   "sector": "Technology", "employees": 182000},
    }
    return companies.get(ticker.upper(), {"error": "Company not found"})

# Map function names to callables
AVAILABLE_FUNCTIONS = {
    "get_stock_price":  get_stock_price,
    "get_company_info": get_company_info,
}

# ── 2. Define the tools schema ────────────────────────────────────────────────

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Get the current stock price for a ticker symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker":   {"type": "string", "description": "Stock ticker, e.g. AAPL"},
                    "currency": {"type": "string", "enum": ["USD", "EUR", "GBP"]},
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_info",
            "description": "Get basic information about a publicly traded company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                },
                "required": ["ticker"],
            },
        },
    },
]

# ── 3. Build the conversation and make the first call ─────────────────────────

messages = [
    {
        "role": "user",
        "content": "What is Apple's current stock price and how many employees do they have?",
    }
]

response = ollama.chat(
    model="qwen2.5",
    messages=messages,
    tools=tools,
)

# ── 4. Process tool calls ─────────────────────────────────────────────────────

# The model's response — append it to the conversation history
messages.append(response.message)

if response.message.tool_calls:
    for tool_call in response.message.tool_calls:
        function_name = tool_call.function.name
        function_args = tool_call.function.arguments  # already a dict

        print(f"Model wants to call: {function_name}({function_args})")

        # Execute the function
        if function_name in AVAILABLE_FUNCTIONS:
            result = AVAILABLE_FUNCTIONS[function_name](**function_args)
        else:
            result = {"error": f"Unknown function: {function_name}"}

        # Append the tool result to the conversation
        messages.append({
            "role":      "tool",
            "content":   json.dumps(result),
        })

# ── 5. Get the final response ─────────────────────────────────────────────────

final_response = ollama.chat(
    model="qwen2.5",
    messages=messages,
    tools=tools,
)

print("\nFinal answer:")
print(final_response.message.content)
```

#### Passing Python Functions Directly

The Ollama Python SDK (0.4+) can automatically generate tool schemas from Python functions with type annotations and docstrings:

```python
import ollama

def get_weather(city: str, units: str = "celsius") -> dict:
    """
    Get the current weather for a city.

    Args:
        city: The name of the city to get weather for.
        units: Temperature units, either 'celsius' or 'fahrenheit'.
    """
    # Simulated weather data
    return {"city": city, "temperature": 22, "units": units, "condition": "partly cloudy"}

response = ollama.chat(
    model="qwen2.5",
    messages=[{"role": "user", "content": "What's the weather like in Tokyo?"}],
    tools=[get_weather],  # Pass the function directly — SDK generates the schema
)

print(response.message.tool_calls)
```

#### Models That Support Tool Calling

Tool calling requires a model that was fine-tuned to understand the tool-calling protocol. As of April 2026:

| Model | Tool Calling Support |
|---|---|
| `qwen2.5`, `qwen3` | Excellent — recommended |
| `llama3.1`, `llama3.2` | Good |
| `mistral`, `mistral-nemo` | Good |
| `phi4-mini` | Good |
| General base models (e.g., `phi3:mini` base) | Poor — use instruct variants |

---

### 7. Structured Data Extraction Pipelines

#### Entity Extraction from Unstructured Text

A common real-world task: given a block of free text (a contract, an email, a news article), extract specific named entities into a structured format.

```python
import ollama
from pydantic import BaseModel, Field
from typing import Optional

class ExtractedEntities(BaseModel):
    people:        list[str] = Field(default_factory=list, description="Full names of people mentioned")
    organizations: list[str] = Field(default_factory=list, description="Company or organization names")
    locations:     list[str] = Field(default_factory=list, description="Cities, countries, or addresses")
    dates:         list[str] = Field(default_factory=list, description="Dates mentioned in any format")
    monetary_amounts: list[str] = Field(default_factory=list, description="Dollar amounts or financial figures")

def extract_entities(text: str, model: str = "qwen2.5") -> ExtractedEntities:
    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert entity extraction system. "
                    "Extract all named entities from the user's text. "
                    "Return empty lists if no entities of a type are found. "
                    "Do not invent entities not present in the text."
                ),
            },
            {"role": "user", "content": text},
        ],
        format=ExtractedEntities.model_json_schema(),
        options={"temperature": 0},
    )
    return ExtractedEntities.model_validate_json(response.message.content)

# Test
text = (
    "On March 15, 2026, Meridian Capital agreed to acquire DataBridge Inc. "
    "for $2.3 billion. The deal was negotiated by CEO Patricia Walsh and "
    "DataBridge founder Raj Patel in New York and London. The acquisition "
    "is expected to close by June 30, 2026."
)
entities = extract_entities(text)
print(f"People: {entities.people}")
print(f"Organizations: {entities.organizations}")
print(f"Dates: {entities.dates}")
print(f"Amounts: {entities.monetary_amounts}")
```

#### Document Classification with Confidence Scores

```python
import ollama
from pydantic import BaseModel, Field
from typing import Literal

class ClassificationResult(BaseModel):
    category:    Literal["invoice", "contract", "email", "report", "receipt", "other"]
    confidence:  float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning:   str   = Field(description="One sentence explaining the classification")
    subcategory: str   = Field(default="", description="Optional subcategory if applicable")

def classify_document(text: str) -> ClassificationResult:
    response = ollama.chat(
        model="qwen2.5",
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify the provided document into one of these categories: "
                    "invoice, contract, email, report, receipt, other. "
                    "Assign a confidence score from 0.0 (uncertain) to 1.0 (certain). "
                    "Be honest about uncertainty."
                ),
            },
            {"role": "user", "content": text[:2000]},  # Truncate very long docs
        ],
        format=ClassificationResult.model_json_schema(),
        options={"temperature": 0},
    )
    return ClassificationResult.model_validate_json(response.message.content)
```

#### Batch Extraction with Error Handling

```python
import json
import time
from pathlib import Path
from pydantic import BaseModel, ValidationError
import ollama

class ExtractionResult(BaseModel):
    document_id: str
    success:     bool
    data:        dict | None = None
    error:       str | None  = None

def batch_extract(
    documents: list[dict],
    schema_model,
    system_prompt: str,
    model: str = "qwen2.5",
    delay_seconds: float = 0.1,
) -> tuple[list[ExtractionResult], float]:
    """
    Extract structured data from a batch of documents.

    Args:
        documents:     List of {"id": str, "text": str} dicts
        schema_model:  A Pydantic BaseModel class defining the output schema
        system_prompt: System prompt describing the extraction task
        model:         Ollama model to use
        delay_seconds: Pause between requests to avoid overwhelming Ollama

    Returns:
        Tuple of (list of ExtractionResult, success_rate as float 0-1)
    """
    results = []

    for i, doc in enumerate(documents, start=1):
        doc_id   = doc.get("id", str(i))
        doc_text = doc.get("text", "")

        print(f"Processing {i}/{len(documents)}: {doc_id}")

        try:
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": doc_text},
                ],
                format=schema_model.model_json_schema(),
                options={"temperature": 0},
            )

            parsed = schema_model.model_validate_json(response.message.content)
            results.append(ExtractionResult(
                document_id=doc_id,
                success=True,
                data=parsed.model_dump(),
            ))

        except ValidationError as e:
            results.append(ExtractionResult(
                document_id=doc_id,
                success=False,
                error=f"Validation error: {e.error_count()} field(s) failed",
            ))
        except Exception as e:
            results.append(ExtractionResult(
                document_id=doc_id,
                success=False,
                error=str(e),
            ))

        if delay_seconds > 0 and i < len(documents):
            time.sleep(delay_seconds)

    success_rate = sum(1 for r in results if r.success) / len(results) if results else 0.0
    return results, success_rate
```

#### Chaining Extraction, Validation, and Storage to SQLite

```python
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional
import ollama

class ContactRecord(BaseModel):
    name:         str
    email:        Optional[str] = None
    phone:        Optional[str] = None
    company:      Optional[str] = None
    job_title:    Optional[str] = None

def setup_database(db_path: str) -> sqlite3.Connection:
    """Create the SQLite database and contacts table."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            email        TEXT,
            phone        TEXT,
            company      TEXT,
            job_title    TEXT,
            extracted_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def extract_and_store_contact(text: str, conn: sqlite3.Connection) -> bool:
    """Extract a contact from text and store it in SQLite. Returns True on success."""
    response = ollama.chat(
        model="qwen2.5",
        messages=[
            {
                "role": "system",
                "content": "Extract contact information from the text. "
                           "Leave fields as null if the information is not present.",
            },
            {"role": "user", "content": text},
        ],
        format=ContactRecord.model_json_schema(),
        options={"temperature": 0},
    )

    contact = ContactRecord.model_validate_json(response.message.content)

    conn.execute(
        """
        INSERT INTO contacts (name, email, phone, company, job_title, extracted_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            contact.name,
            contact.email,
            contact.phone,
            contact.company,
            contact.job_title,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    return True

# Usage
if __name__ == "__main__":
    conn = setup_database("contacts.db")

    texts = [
        "Hi, I'm Sarah Chen, VP of Engineering at DataScale. "
        "Reach me at sarah.chen@datascale.io or 415-555-0192.",
        "Dr. Marcus Webb, research@medilab.org — no phone number on file.",
    ]

    for text in texts:
        success = extract_and_store_contact(text, conn)
        print(f"Stored: {success}")

    # Read back and verify
    for row in conn.execute("SELECT name, email, company FROM contacts"):
        print(row)

    conn.close()
```

---

### 8. Reliability Techniques for Local Models

Getting consistent structured output from smaller local models (3B–13B) requires deliberate engineering. This section covers the techniques that matter most in production.

#### Schema Simplification

The single most impactful reliability improvement: reduce the complexity of your schema.

```python
# FRAGILE: Too many required fields, nested objects, complex types
class FragileSchema(BaseModel):
    personal_info: PersonalInfo           # Nested model
    employment:    list[EmploymentRecord] # List of nested models
    education:     list[EducationRecord]  # Another list of nested models
    skills:        dict[str, list[str]]   # Dict of lists — very hard for small models
    references:    list[Reference]        # Optional but complex
    salary_history: list[SalaryRecord]   # 6+ required fields in this model

# ROBUST: Flat schema, optional fields, simple types
class RobustSchema(BaseModel):
    full_name:    str
    current_role: str
    company:      Optional[str] = None
    skills:       list[str] = Field(default_factory=list)
    years_exp:    Optional[int] = None
```

#### Few-Shot Examples in the Prompt

For models that struggle with complex schemas, show them a worked example in the system prompt:

```python
SYSTEM_PROMPT_WITH_EXAMPLE = """
You are a data extraction assistant. Extract structured information from text.

Always respond with valid JSON matching this schema:
{schema}

Example input: "Jane Smith, 35, software engineer at TechCorp in Austin."
Example output:
{{
  "name": "Jane Smith",
  "age": 35,
  "job_title": "software engineer",
  "company": "TechCorp",
  "city": "Austin"
}}

Extract the data from the user's text in the same format.
""".strip()
```

#### Temperature=0 for Deterministic Output

Always use `temperature=0` for structured extraction. Higher temperatures introduce randomness that can corrupt JSON structure and field values:

```python
# Always include this for structured output tasks
options={"temperature": 0}
```

#### Retry on Validation Failure with Error Feedback

When a model produces invalid output, retry with the error message included in the prompt. This is often more effective than a blind retry:

```python
import ollama
from pydantic import BaseModel, ValidationError
import json

def extract_with_retry(
    text: str,
    schema_model,
    system_prompt: str,
    model: str = "qwen2.5",
    max_retries: int = 3,
):
    """Extract structured data with retry on validation failure."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": text},
    ]

    for attempt in range(max_retries):
        try:
            response = ollama.chat(
                model=model,
                messages=messages,
                format=schema_model.model_json_schema(),
                options={"temperature": 0},
            )

            raw_output = response.message.content
            result     = schema_model.model_validate_json(raw_output)
            return result

        except (ValidationError, json.JSONDecodeError) as e:
            if attempt < max_retries - 1:
                # Add the failed output and error to the conversation
                # so the model can see what went wrong
                messages.append({"role": "assistant", "content": raw_output})
                messages.append({
                    "role":    "user",
                    "content": (
                        f"The previous response was invalid. Error: {e}\n"
                        "Please correct the JSON and try again. "
                        "Return only valid JSON with no extra text."
                    ),
                })
            else:
                raise

    return None
```

#### Field-by-Field Extraction for Complex Schemas

When a schema is too complex for a model to fill in one pass, extract one field at a time and assemble the result:

```python
import ollama

def extract_field(
    text: str,
    field_name: str,
    field_description: str,
    field_type: str,
    model: str = "qwen2.5",
) -> str:
    """Extract a single field value from text."""
    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    f"Extract the {field_name} from the user's text. "
                    f"Field description: {field_description}. "
                    f"Return only the value as a {field_type}, with no extra text or explanation."
                ),
            },
            {"role": "user", "content": text},
        ],
        format={"type": field_type} if field_type in ("string", "number", "boolean") else None,
        options={"temperature": 0},
    )
    return response.message.content.strip()

# Use for complex schemas by extracting each field separately, then assembling
```

#### Model Selection for Structured Output

Summary of which local models perform best for structured output tasks as of April 2026:

| Model | Structured Output | Tool Calling | Size | Notes |
|---|---|---|---|---|
| `qwen2.5:7b` | Excellent | Excellent | 4.4 GB | Best overall for structured tasks |
| `qwen3:8b` | Excellent | Excellent | 5.2 GB | Latest generation, strong reasoning |
| `llama3.2:3b` | Good | Good | 2.0 GB | Best lightweight option |
| `llama3.1:8b` | Good | Good | 4.7 GB | Solid all-rounder |
| `phi4-mini` | Good | Good | 2.5 GB | Fast, compact |
| `mistral:7b` | Moderate | Moderate | 4.1 GB | Use Mistral Nemo for better results |
| Base models (non-instruct) | Poor | Poor | varies | Do not use for structured output |

**Rule of thumb:** If your schema has more than 8 required fields, use `qwen2.5` or `qwen3`. If you need absolute reliability, use `llama-cpp-python` with GBNF grammar constraints. Avoid base (non-instruct) model variants for any structured output task.

---

## Hands-On Examples

### Example 1: Ollama JSON Mode — Job Posting Extractor

This example extracts a fully structured `JobPosting` Pydantic model from raw job description text using Ollama's schema-constrained output, with retry logic on validation failure.

```python
"""
example1_job_posting_extractor.py

Extracts structured job posting data from raw text using Ollama's
schema-constrained output and Pydantic validation.

Requirements:
    pip install "ollama>=0.4.0" "pydantic>=2.7.0"
    ollama pull qwen2.5

Usage:
    python example1_job_posting_extractor.py
"""

import json
from typing import Optional, Literal
from pydantic import BaseModel, Field, ValidationError
import ollama

# ── 1. Define the Output Schema ────────────────────────────────────────────────

class JobPosting(BaseModel):
    title:            str = Field(description="Exact job title as listed")
    company:          str = Field(description="Company name")
    location:         str = Field(description="City and state/country, or 'Remote'")
    employment_type:  Literal["full-time", "part-time", "contract", "internship"] = "full-time"
    remote_policy:    Literal["on-site", "hybrid", "remote"] = "on-site"
    salary_min:       Optional[int] = Field(
        default=None, description="Minimum annual salary in USD as an integer"
    )
    salary_max:       Optional[int] = Field(
        default=None, description="Maximum annual salary in USD as an integer"
    )
    required_skills:  list[str] = Field(
        default_factory=list,
        description="Required technical skills, each as a short string"
    )
    preferred_skills: list[str] = Field(
        default_factory=list,
        description="Nice-to-have skills"
    )
    experience_years: Optional[int] = Field(
        default=None,
        description="Minimum years of experience as an integer"
    )
    education:        Optional[str] = Field(
        default=None,
        description="Required education level, e.g. 'Bachelor\\'s degree in CS'"
    )
    benefits:         list[str] = Field(
        default_factory=list,
        description="Listed benefits, each as a short phrase"
    )

# ── 2. Extraction Function with Retry ─────────────────────────────────────────

SYSTEM_PROMPT = """
You are a job posting data extraction specialist.
Extract all structured information from the job posting provided.
Return only valid JSON matching the schema. Do not add explanations.
If information is not stated, use null for optional fields and empty lists for list fields.
"""

def extract_job_posting(
    raw_text: str,
    model: str = "qwen2.5",
    max_retries: int = 3,
) -> JobPosting:
    """Extract a structured JobPosting from raw job description text."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": raw_text},
    ]

    last_error = None

    for attempt in range(1, max_retries + 1):
        print(f"  Attempt {attempt}/{max_retries}...")

        response = ollama.chat(
            model=model,
            messages=messages,
            format=JobPosting.model_json_schema(),
            options={"temperature": 0},
        )

        raw_output = response.message.content

        try:
            posting = JobPosting.model_validate_json(raw_output)
            print(f"  Extraction succeeded on attempt {attempt}.")
            return posting

        except (ValidationError, json.JSONDecodeError) as e:
            last_error = e
            print(f"  Validation failed: {e}")

            if attempt < max_retries:
                # Feed the error back to the model so it can self-correct
                messages.append({"role": "assistant", "content": raw_output})
                messages.append({
                    "role": "user",
                    "content": (
                        f"The JSON you returned was invalid. Error details: {e}\n"
                        "Please fix the issues and return only corrected JSON."
                    ),
                })

    raise ValueError(
        f"Extraction failed after {max_retries} attempts. Last error: {last_error}"
    )

# ── 3. Run the Extractor ───────────────────────────────────────────────────────

if __name__ == "__main__":
    sample_postings = [
        {
            "id": "posting_001",
            "text": """
Senior Machine Learning Engineer — QuantumLeap AI
Location: San Francisco, CA (Hybrid - 2 days/week in office)
Salary: $180,000 – $230,000/year + equity

About the Role:
We're hiring a Senior ML Engineer to join our core inference team.
You'll design and optimize production ML pipelines serving 10M+ requests/day.

Requirements:
- 5+ years of experience in ML engineering or applied research
- Strong Python skills (PyTorch, TensorFlow, JAX)
- Experience with model deployment: ONNX, TensorRT, vLLM, or similar
- Familiarity with distributed training (DeepSpeed, FSDP)
- BS/MS/PhD in Computer Science, Statistics, or related field

Nice to have:
- Experience with quantization and model compression
- Contributions to open-source ML projects
- Experience with Kubernetes and ML infra at scale

Benefits: Unlimited PTO, health/dental/vision, $5k/year learning budget,
remote work equipment stipend, 401k with 4% match.
""",
        },
        {
            "id": "posting_002",
            "text": """
Part-Time Data Entry Specialist (Contract)
Company: RecordKeep Solutions
Location: Remote

Responsibilities include data entry into our CRM, spreadsheet maintenance,
and basic reporting. No specific technical skills required. Previous experience
with Excel or Google Sheets is helpful. Contract duration: 3 months, 20 hours/week.
Compensation: $25/hour.
""",
        },
    ]

    results = []

    for posting in sample_postings:
        print(f"\nProcessing: {posting['id']}")
        print("-" * 50)
        try:
            job = extract_job_posting(posting["text"])
            results.append({"id": posting["id"], "status": "success", "data": job.model_dump()})

            print(f"Title:     {job.title}")
            print(f"Company:   {job.company}")
            print(f"Location:  {job.location}")
            print(f"Salary:    ${job.salary_min:,} – ${job.salary_max:,}" if job.salary_min else "Salary: Not specified")
            print(f"Remote:    {job.remote_policy}")
            print(f"Skills:    {', '.join(job.required_skills[:5])}")

        except ValueError as e:
            print(f"Failed: {e}")
            results.append({"id": posting["id"], "status": "failed", "error": str(e)})

    # Save results to JSON
    output_path = "job_postings_extracted.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"\nCompleted: {success_count}/{len(results)} succeeded. Saved to {output_path}")
```

---

### Example 2: llama-cpp-python with GBNF Grammar — Medical Record Parser

This example demonstrates grammar-constrained generation using `llama-cpp-python`. It also runs the same extraction with prompt-only JSON to show the reliability difference directly.

```python
"""
example2_medical_record_grammar.py

Demonstrates grammar-constrained JSON generation with llama-cpp-python.
Compares grammar-constrained output against prompt-only JSON requests
to illustrate the reliability difference on a small local model.

Requirements:
    pip install "llama-cpp-python>=0.3.0" "pydantic>=2.7.0"

    You need a GGUF model file. Download one from Hugging Face, e.g.:
    https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF
    (Use the Q4_K_M quantization for a good quality/size tradeoff)

    Update MODEL_PATH below to point to your GGUF file.

Usage:
    python example2_medical_record_grammar.py
"""

import json
import time
from typing import Optional, Literal
from pydantic import BaseModel, Field, ValidationError
from llama_cpp import Llama, LlamaGrammar

# ── Configuration ──────────────────────────────────────────────────────────────

MODEL_PATH = "/path/to/your-model.gguf"  # Update this path

# ── 1. Define the Medical Record Schema ───────────────────────────────────────

class VitalSigns(BaseModel):
    systolic_bp:  Optional[int]   = Field(default=None, description="Systolic blood pressure in mmHg")
    diastolic_bp: Optional[int]   = Field(default=None, description="Diastolic blood pressure in mmHg")
    heart_rate:   Optional[int]   = Field(default=None, description="Heart rate in beats per minute")
    temperature_f: Optional[float] = Field(default=None, description="Temperature in Fahrenheit")

class MedicalRecord(BaseModel):
    patient_name:   str
    date_of_birth:  str   = Field(description="Date in YYYY-MM-DD format")
    visit_date:     str   = Field(description="Visit date in YYYY-MM-DD format")
    chief_complaint: str  = Field(description="Patient's primary complaint")
    diagnosis:      str
    severity:       Literal["mild", "moderate", "severe", "critical"]
    vitals:         Optional[VitalSigns] = None
    medications:    list[str] = Field(
        default_factory=list,
        description="List of prescribed medications with dosages"
    )
    follow_up_days: Optional[int] = Field(
        default=None,
        description="Days until follow-up appointment as an integer"
    )
    notes:          Optional[str] = None

# ── 2. Sample Clinical Notes ───────────────────────────────────────────────────

CLINICAL_NOTES = [
    {
        "id": "note_001",
        "text": (
            "Patient: Emily Vasquez, DOB 1990-07-14. Visit: 2026-04-10. "
            "Chief complaint: persistent headache and fatigue for 3 days. "
            "BP 145/92, HR 78, Temp 99.1F. "
            "Assessment: Moderate hypertension with tension headache. "
            "Prescribed: Lisinopril 10mg daily, Acetaminophen 500mg PRN. "
            "Return in 14 days for blood pressure recheck."
        ),
    },
    {
        "id": "note_002",
        "text": (
            "Marcus Reid, born June 3rd, 1978. Seen today 2026-04-15. "
            "Patient presents with mild seasonal allergies — runny nose, sneezing, itchy eyes. "
            "No fever. No vitals taken. Recommended Loratadine 10mg once daily and "
            "Fluticasone nasal spray. Follow up only if symptoms worsen."
        ),
    },
]

# ── 3. Load the Model ──────────────────────────────────────────────────────────

print("Loading model...")
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=2048,
    verbose=False,
)

# ── 4. Generate Grammar from Schema ───────────────────────────────────────────

schema_json = json.dumps(MedicalRecord.model_json_schema())
grammar = LlamaGrammar.from_json_schema(schema_json)

# ── 5. Extraction Function ─────────────────────────────────────────────────────

def build_prompt(note_text: str) -> str:
    return (
        f"<|im_start|>system\n"
        f"Extract the medical record data from the clinical note as structured JSON.\n"
        f"<|im_end|>\n"
        f"<|im_start|>user\n"
        f"{note_text}\n"
        f"<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

def extract_grammar_constrained(note_text: str) -> dict:
    """Extract using GBNF grammar — output is guaranteed valid JSON matching the schema."""
    prompt   = build_prompt(note_text)
    response = llm(
        prompt,
        grammar=grammar,
        max_tokens=512,
        temperature=0.0,
        stop=["<|im_end|>"],
    )
    raw_output = response["choices"][0]["text"].strip()
    record     = MedicalRecord.model_validate_json(raw_output)
    return {"success": True, "data": record.model_dump()}

def extract_prompt_only(note_text: str) -> dict:
    """Extract using prompt-only JSON request — may produce invalid output."""
    prompt = (
        build_prompt(note_text).replace(
            "Extract the medical record data from the clinical note as structured JSON.",
            (
                "Extract the medical record data from the clinical note. "
                "Respond with a JSON object. Do not include any other text."
            ),
        )
    )
    response = llm(
        prompt,
        max_tokens=512,
        temperature=0.0,
        stop=["<|im_end|>"],
    )
    raw_output = response["choices"][0]["text"].strip()

    # Try to parse and validate — may fail
    try:
        # Some models wrap output in code fences — strip them
        if raw_output.startswith("```"):
            lines      = raw_output.split("\n")
            raw_output = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        record = MedicalRecord.model_validate_json(raw_output)
        return {"success": True, "data": record.model_dump()}
    except (ValidationError, json.JSONDecodeError) as e:
        return {"success": False, "error": str(e), "raw": raw_output}

# ── 6. Run Comparison ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("GRAMMAR-CONSTRAINED vs. PROMPT-ONLY COMPARISON")
    print("=" * 60)

    grammar_results  = []
    promptonly_results = []

    for note in CLINICAL_NOTES:
        print(f"\n--- {note['id']} ---")

        # Grammar-constrained extraction
        print("Grammar-constrained:")
        try:
            g_result = extract_grammar_constrained(note["text"])
            grammar_results.append(g_result)
            if g_result["success"]:
                data = g_result["data"]
                print(f"  Patient: {data['patient_name']}")
                print(f"  Diagnosis: {data['diagnosis']} ({data['severity']})")
                print(f"  Medications: {data['medications']}")
        except Exception as e:
            grammar_results.append({"success": False, "error": str(e)})
            print(f"  Error: {e}")

        # Prompt-only extraction
        print("Prompt-only:")
        p_result = extract_prompt_only(note["text"])
        promptonly_results.append(p_result)
        if p_result["success"]:
            data = p_result["data"]
            print(f"  Patient: {data['patient_name']}")
            print(f"  Diagnosis: {data['diagnosis']} ({data['severity']})")
        else:
            print(f"  FAILED: {p_result['error']}")
            if "raw" in p_result:
                print(f"  Raw output (first 200 chars): {p_result['raw'][:200]}")

    # Summary
    g_success  = sum(1 for r in grammar_results  if r["success"])
    p_success  = sum(1 for r in promptonly_results if r["success"])
    total      = len(CLINICAL_NOTES)

    print(f"\n{'=' * 60}")
    print(f"Grammar-constrained: {g_success}/{total} ({g_success/total:.0%}) succeeded")
    print(f"Prompt-only:         {p_success}/{total} ({p_success/total:.0%}) succeeded")
    print("=" * 60)
```

---

### Example 3: Batch Document Classification Pipeline

This example classifies 10 documents into categories with confidence scores, handles failures gracefully, saves all results (including failures) to JSON, and reports the overall success rate.

```python
"""
example3_batch_classifier.py

Classifies a batch of 10 documents into categories with confidence scores.
Handles failures gracefully. Saves results to JSON. Reports success rate.

Requirements:
    pip install "ollama>=0.4.0" "pydantic>=2.7.0"
    ollama pull qwen2.5

Usage:
    python example3_batch_classifier.py
"""

import json
import time
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, ValidationError
import ollama

# ── 1. Schema ──────────────────────────────────────────────────────────────────

class ClassificationResult(BaseModel):
    document_id: str
    category:    Literal["invoice", "contract", "email", "report", "receipt", "legal", "other"]
    confidence:  float = Field(description="Confidence score from 0.0 (uncertain) to 1.0 (certain)")
    reasoning:   str   = Field(description="One sentence explaining why this category was chosen")
    key_signals: list[str] = Field(
        default_factory=list,
        description="Up to 3 words or phrases that most strongly indicate the category"
    )

class BatchReport(BaseModel):
    run_timestamp:   str
    model:           str
    total_documents: int
    successful:      int
    failed:          int
    success_rate:    float
    results:         list[dict]

# ── 2. Sample Documents ────────────────────────────────────────────────────────

DOCUMENTS = [
    {"id": "doc_01", "text": "INVOICE #5023\nBilled to: Apex Corp\nFrom: PrintRight LLC\nDate: 2026-03-01\nTotal due: $1,240.00\nPayment terms: Net 30"},
    {"id": "doc_02", "text": "SERVICE AGREEMENT\nThis agreement is entered into by TechServe Inc. (Provider) and ClientCo (Client). Provider will deliver software maintenance services for a period of 12 months commencing April 1, 2026. Monthly retainer: $3,500."},
    {"id": "doc_03", "text": "Hi team,\nJust a reminder that the sprint planning meeting is tomorrow at 10am EST. Please review the backlog items before joining.\nBest,\nDan"},
    {"id": "doc_04", "text": "Q1 2026 SALES REPORT\nExecutive Summary: Total revenue for Q1 reached $4.2M, up 18% YoY. Top performing region: Southwest (34% of total). Customer churn rate declined to 3.1%."},
    {"id": "doc_05", "text": "RECEIPT\nMerchant: Office Depot\nDate: 2026-04-05\nItems: 2x Ink Cartridge ($24.99 each), 1x Paper Ream ($12.49)\nTotal: $62.47\nPayment: Visa ending 4821"},
    {"id": "doc_06", "text": "LEASE AGREEMENT\nThis Residential Lease Agreement is made between Landlord Jane Morrison and Tenant Kyle Peters for the property at 482 Oak Street, Denver, CO 80203. Lease term: 12 months. Monthly rent: $1,850."},
    {"id": "doc_07", "text": "PURCHASE ORDER #PO-8821\nFrom: BuildRight Construction\nTo: Steelman Supplies\nItems: 500x Steel bolts M12 @ $0.45 each\nExpected delivery: 2026-04-20\nTotal: $225.00"},
    {"id": "doc_08", "text": "QUARTERLY RISK ASSESSMENT — IT INFRASTRUCTURE\nPrepared by: Security Team\nDate: April 2026\nExecutive Summary: Three critical vulnerabilities identified in the legacy ERP system. Immediate patching recommended. Full report attached."},
    {"id": "doc_09", "text": "Dear Mr. Patel,\nWe are writing to formally notify you of a potential breach of Section 4.2 of the Master Services Agreement dated January 15, 2026. Failure to remedy within 30 days may result in contract termination per Section 9.1.\nRegards,\nLegal Team"},
    {"id": "doc_10", "text": "VOLUNTEER APPRECIATION CERTIFICATE\nThis certifies that Maria Gonzalez has contributed 120 hours of volunteer service to the Riverside Food Bank between January and March 2026. Thank you for your dedication!"},
]

# ── 3. Classification Function ─────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a document classification specialist.
Classify the provided document into exactly one category: 
invoice, contract, email, report, receipt, legal, or other.
Assign a confidence score from 0.0 (very uncertain) to 1.0 (completely certain).
Provide one sentence explaining your reasoning.
List up to 3 key signals (words/phrases) that indicate the category.
"""

def classify_document(
    doc_id: str,
    doc_text: str,
    model: str = "qwen2.5",
) -> ClassificationResult:
    """Classify a single document. Raises on validation failure."""
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Document ID: {doc_id}\n\n{doc_text}"},
        ],
        format=ClassificationResult.model_json_schema(),
        options={"temperature": 0},
    )

    result = ClassificationResult.model_validate_json(response.message.content)
    # Ensure the document_id matches what we sent
    result.document_id = doc_id
    return result

# ── 4. Batch Processing Pipeline ───────────────────────────────────────────────

def run_batch_classification(
    documents: list[dict],
    model: str = "qwen2.5",
    delay_seconds: float = 0.2,
    output_path: str = "classification_results.json",
) -> BatchReport:
    """
    Classify all documents. Save results to JSON. Return a BatchReport.
    Documents that fail are recorded with error details, not skipped.
    """
    all_results = []
    successful  = 0
    failed      = 0

    print(f"Classifying {len(documents)} documents using {model}...")
    print("-" * 60)

    for i, doc in enumerate(documents, start=1):
        doc_id   = doc["id"]
        doc_text = doc["text"]

        print(f"[{i:2d}/{len(documents)}] {doc_id}...", end=" ", flush=True)

        try:
            result = classify_document(doc_id, doc_text, model)
            all_results.append({
                "status":      "success",
                "document_id": doc_id,
                "category":    result.category,
                "confidence":  round(result.confidence, 3),
                "reasoning":   result.reasoning,
                "key_signals": result.key_signals,
            })
            successful += 1
            print(f"{result.category} ({result.confidence:.0%})")

        except ValidationError as e:
            all_results.append({
                "status":        "failed",
                "document_id":   doc_id,
                "error_type":    "ValidationError",
                "error_message": str(e),
            })
            failed += 1
            print(f"FAILED (validation)")

        except Exception as e:
            all_results.append({
                "status":        "failed",
                "document_id":   doc_id,
                "error_type":    type(e).__name__,
                "error_message": str(e),
            })
            failed += 1
            print(f"FAILED ({type(e).__name__})")

        # Brief pause between requests
        if delay_seconds > 0 and i < len(documents):
            time.sleep(delay_seconds)

    success_rate = successful / len(documents) if documents else 0.0

    report = BatchReport(
        run_timestamp=   datetime.utcnow().isoformat() + "Z",
        model=           model,
        total_documents= len(documents),
        successful=      successful,
        failed=          failed,
        success_rate=    round(success_rate, 4),
        results=         all_results,
    )

    # Save to JSON
    with open(output_path, "w") as f:
        json.dump(report.model_dump(), f, indent=2)

    return report

# ── 5. Display Summary ─────────────────────────────────────────────────────────

def print_summary(report: BatchReport) -> None:
    """Print a formatted summary of batch classification results."""
    print("\n" + "=" * 60)
    print("BATCH CLASSIFICATION SUMMARY")
    print("=" * 60)
    print(f"Model:         {report.model}")
    print(f"Timestamp:     {report.run_timestamp}")
    print(f"Total docs:    {report.total_documents}")
    print(f"Successful:    {report.successful}")
    print(f"Failed:        {report.failed}")
    print(f"Success rate:  {report.success_rate:.1%}")
    print("-" * 60)

    # Category breakdown
    from collections import Counter
    categories = Counter(
        r["category"] for r in report.results if r["status"] == "success"
    )
    print("Category breakdown:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        bar = "#" * count
        print(f"  {cat:<12} {bar} ({count})")

    # Average confidence
    confidences = [r["confidence"] for r in report.results if r["status"] == "success"]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        print(f"\nAverage confidence: {avg_conf:.1%}")

    # Low-confidence items (may need human review)
    low_conf = [r for r in report.results if r.get("status") == "success" and r.get("confidence", 1) < 0.70]
    if low_conf:
        print(f"\nLow-confidence results (< 70%) — recommend human review:")
        for r in low_conf:
            print(f"  {r['document_id']}: {r['category']} ({r['confidence']:.0%})")

    print("=" * 60)

# ── 6. Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    output_file = "classification_results.json"

    report = run_batch_classification(
        documents=    DOCUMENTS,
        model=        "qwen2.5",
        delay_seconds=0.2,
        output_path=  output_file,
    )

    print_summary(report)
    print(f"\nFull results saved to: {output_file}")
```

---

## Common Pitfalls

**Schema too complex for the model.** A schema with 15+ required fields, 3 levels of nesting, and `dict[str, list[Model]]` types will fail on 7B models even with schema-constrained output. Simplify: flatten the schema, make non-critical fields optional, and split complex extractions into multiple simpler calls.

**Missing required fields causing hallucination.** If your schema marks a field as required but the source text does not mention it, the model invents a value. Use `Optional[T] = None` for any field that may not be present in every document.

**JSON with trailing commas.** Some models (especially smaller ones in prompt-only mode) produce `{"key": "value",}` which is invalid JSON. Python's `json.loads()` will reject it. Use `json5` (`pip install json5`) as a fallback parser in prompt-only flows, or switch to schema-constrained output.

**Model ignores the format instruction.** When using `PydanticOutputParser` (which relies on prompt injection), some models ignore the format instructions and produce free text. Fix: switch to `with_structured_output(..., method="json_schema")` to use Ollama's schema-constrained API instead. Never rely on prompt-only format instructions as your only mechanism for structured output in production.

**Validation errors on numeric types.** Models frequently emit `"salary": "120000"` (string) instead of `"salary": 120000` (integer), causing Pydantic validation errors. Mitigate by using `model_validator` with `mode="before"` to coerce strings to numbers, or by using Pydantic v2's `model_config = ConfigDict(coerce_numbers_to_str=False)` and a pre-validator.

**`tool_calls` is None when expected.** Ollama returns `tool_calls` as `None` (not an empty list) when the model does not call a tool. Always check `if response.message.tool_calls:` before iterating. If the model consistently fails to call the tool when it should, improve the tool description and verify you are using an instruct model, not a base model.

**Using a base model for structured output.** Base models (variants without `-instruct` or `-it` in their name) have not been fine-tuned to follow formatting instructions. They will produce erratic output with any structured output technique. Always use instruct/chat variants.

**Forgetting `temperature=0`.** Even small temperature values (0.3–0.7) introduce randomness that can corrupt JSON structure — extra keys, values that switch types between runs, or fields that appear out of order. Set `temperature=0` for all deterministic extraction tasks.

**Not handling the `include_raw` output shape.** When you use `with_structured_output(..., include_raw=True)`, the return value is a `dict` with keys `"raw"`, `"parsed"`, and `"parsing_error"` — not a direct Pydantic instance. Accessing `.name` on this dict raises `AttributeError`. Always check `result["parsed"]` explicitly.

---

## Best Practices

Use **schema-constrained output** (`format=MyModel.model_json_schema()` in Ollama) as your default approach for all production extraction tasks. Prompt-only JSON is for prototyping only.

Use **GBNF grammar constraints** (`llama-cpp-python`) when absolute reliability is required, when you cannot tolerate retries, or when your target model is smaller than 7B.

Design schemas with **Optional fields and Literal types** wherever possible. Optional fields prevent hallucination; Literal types constrain the model's output space and dramatically improve reliability for categorical fields.

Always set **`temperature=0`** for structured extraction and classification tasks. Structured output is a deterministic task — temperature adds noise with no benefit.

Use **`model_validate_json()`** rather than `json.loads()` followed by `Model(**data)`. `model_validate_json()` handles both steps in one call and raises a single well-structured `ValidationError` on failure.

**Include the schema in the system prompt** as a fallback, especially when using smaller models. Even with schema-constrained output, giving the model a textual description of what you need improves field-level accuracy.

Implement **retry with error feedback**: when validation fails, append the failure message to the conversation and ask the model to correct it. Two retries with error context typically resolve 80–90% of initial failures.

**Log raw model output** on validation failure before raising an exception. The raw output is essential for diagnosing whether the model misunderstood the schema, produced nearly-valid JSON, or generated something completely unexpected.

Use **`with_structured_output(..., include_raw=True)`** during development and testing. Switch to `include_raw=False` in production once you have validated reliability.

Keep **required field count under 10** for reliable results with 7B models. If your extraction task genuinely requires more fields, split it into two sequential calls and merge the results.

**Monitor success rates** in batch pipelines. A sudden drop from 95% to 80% is often a model version change or a shift in the source document format — not a bug in your code.

---

## Key Terminology

**GBNF (GGML Backus-Naur Form)** — A grammar notation used by llama.cpp to define the set of valid output strings. When a GBNF grammar is active during inference, the token sampler enforces it by zeroing out the probability of any token that would produce invalid output.

**Grammar-constrained generation** — Inference with a GBNF grammar active. The model cannot produce output that violates the grammar, regardless of what it "wants" to generate. Used via `llama-cpp-python`'s `grammar` parameter.

**JSON mode** — An Ollama API feature activated by `format="json"`. Guarantees syntactically valid JSON output but does not enforce a specific schema.

**`LlamaGrammar`** — The Python class in `llama-cpp-python` that holds a compiled GBNF grammar. Created with `LlamaGrammar.from_string()` or `LlamaGrammar.from_json_schema()`.

**`model_json_schema()`** — A Pydantic v2 method on any `BaseModel` subclass that returns a JSON Schema dict representing the model's field structure and types. Used to pass the schema to Ollama's `format` parameter.

**`model_validate_json()`** — A Pydantic v2 method that parses a JSON string and validates it against the model's schema in a single call. Raises `ValidationError` if the JSON is invalid or fields fail validation.

**OutputFixingParser** — A LangChain parser that wraps another parser. On parse failure, it sends the bad output back to the LLM with a correction instruction and tries again.

**RetryOutputParser** — A LangChain parser that re-runs the full original prompt on failure, appending the error and bad output to guide the model to produce a corrected response.

**Schema-constrained output** — Ollama's structured output feature (0.5+), activated by passing a JSON Schema to the `format` parameter. The model is steered toward producing output that matches the schema.

**Tool calling (function calling)** — A protocol where the LLM responds with a structured function invocation (name + arguments) instead of natural language, allowing your application to execute the function and feed the result back to the model.

**`with_structured_output()`** — A LangChain method on `ChatOllama` that returns a `Runnable` producing validated Pydantic instances or typed dicts. Supports three methods: `json_schema` (default), `function_calling`, and `json_mode`.

---

## Summary

- LLMs return free text by default. Getting typed, validated data requires intentional engineering — the choice of technique determines your reliability ceiling.
- The **reliability spectrum** runs from prompt-only (unreliable) to grammar-constrained generation (guaranteed valid output). Use the highest-reliability approach your infrastructure supports.
- **Ollama's schema-constrained output** (`format=MyModel.model_json_schema()`) is the right default for most production use cases. It is available from Ollama 0.5+ and integrates directly with Pydantic.
- **Pydantic** is the natural pair for LLM structured output: `model_json_schema()` generates the schema, `model_validate_json()` validates the response, and `ValidationError` gives field-level error detail for retry logic.
- **LangChain's `with_structured_output()`** on `ChatOllama` is the cleanest integration for LangChain-based pipelines. Use `method="json_schema"` (the default since langchain-ollama 0.3.0) to leverage Ollama's schema API.
- **GBNF grammar constraints** via `llama-cpp-python` operate at the token-sampling level, making invalid output mathematically impossible. Use this for critical reliability requirements or when working with sub-7B models.
- **Function calling** follows a four-step round-trip: define tools → LLM selects and specifies a call → you execute the function → LLM synthesizes the result. Use `qwen2.5` or `qwen3` for the most reliable tool calling behavior locally.
- **Reliability techniques** that matter most in production: simplify schemas, use Optional fields, set `temperature=0`, retry with error feedback, and select instruction-tuned models (never base models).
- Schema complexity is the most common source of structured output failures. When extraction fails consistently, flatten the schema before changing models or prompts.

---

## Further Reading

- [Ollama Structured Outputs Documentation — docs.ollama.com](https://docs.ollama.com/capabilities/structured-outputs) — The official Ollama documentation for the `format` parameter and schema-constrained output. Covers the JSON schema format, Python/JavaScript SDK usage, Pydantic integration, and OpenAI-compatible endpoint configuration. Start here when debugging format parameter behavior.

- [Ollama Tool Calling Documentation — docs.ollama.com](https://docs.ollama.com/capabilities/tool-calling) — Official reference for Ollama's tool-calling API, including the tools array schema, the `tool_calls` response format, the complete round-trip protocol, and how to pass Python functions directly. Essential reading before building any function-calling pipeline with Ollama.

- [llama.cpp GBNF Grammars README — github.com/ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) — The authoritative reference for GBNF grammar syntax: non-terminals, terminals, character classes, quantifiers, alternation, and the built-in JSON and other example grammars. Read this when writing custom GBNF grammars beyond what `from_json_schema()` generates.

- [LangChain `with_structured_output` API Reference — reference.langchain.com](https://reference.langchain.com/python/langchain-ollama/chat_models/ChatOllama/with_structured_output) — API reference for `ChatOllama.with_structured_output()`, documenting all parameters (`schema`, `method`, `include_raw`), return types, and the differences between `json_schema`, `function_calling`, and `json_mode` methods. Check here for exact parameter names and version-specific behavior notes.

- [Pydantic v2 Validators Documentation — docs.pydantic.dev](https://docs.pydantic.dev/latest/concepts/validators/) — The Pydantic v2 guide to `@field_validator`, `@model_validator`, `mode="before"` vs. `mode="after"`, and validation error handling. Required reading for building robust LLM output schemas with custom validation logic.

- [A Guide to Structured Outputs Using Constrained Decoding — aidancooper.co.uk](https://www.aidancooper.co.uk/constrained-decoding/) — A deep technical explanation of how constrained decoding (GBNF and logit masking) works at the token-sampling level, comparing grammar-based approaches, outlines, and other constraint mechanisms. Bridges the conceptual gap between "the model is guided" and "the sampler is constrained."

- [Generating Structured Outputs from Language Models: Benchmark and Studies — arxiv.org](https://arxiv.org/html/2501.10868v1) — A January 2025 research paper benchmarking structured output compliance rates across multiple constrained decoding frameworks. Provides empirical data on the reliability gap between prompt-only, JSON mode, and grammar-constrained approaches across different model sizes.

- [LangChain Output Parsers — python.langchain.com](https://python.langchain.com/api_reference/core/output_parsers/langchain_core.output_parsers.pydantic.PydanticOutputParser.html) — The LangChain API reference for `PydanticOutputParser`, including `get_format_instructions()`, the chain integration pattern, and the `OutputParserException` type. Complements Section 4 of this module.

- [Structured Outputs with Ollama and Instructor — python.useinstructor.com](https://python.useinstructor.com/integrations/ollama/) — Documentation for the `instructor` library's Ollama integration, which provides an alternative structured output API with automatic retry, validation, and streaming support. Worth reading as a comparison to the native Ollama SDK approach covered in this module.

- [Simon Willison — Using llama-cpp-python grammars to generate JSON — til.simonwillison.net](https://til.simonwillison.net/llms/llama-cpp-python-grammars) — A practical walkthrough of grammar-constrained generation with `llama-cpp-python`, including loading GBNF files, using `LlamaGrammar.from_string()`, and the edge case of incomplete JSON when `max_tokens` is too low. Directly relevant to the llama-cpp-python examples in this module.
