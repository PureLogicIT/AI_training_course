# Exercise 2: Structured Data Extraction with PydanticOutputParser
> Module: Module 3 — LangChain Fundamentals | Difficulty: Medium | Estimated Time: 90–120 minutes

---

## Overview

The module's Example 2 showed a single-schema extraction chain run from the command line against job postings. In this exercise you will build a Gradio application that supports **three different Pydantic schemas** — a job posting, a product description, and an event announcement — switchable at runtime. The app shows the model's raw text output alongside the parsed result so the learner can observe exactly what the model produced and whether the parser accepted it.

You will also implement **`OutputFixingParser`**, which wraps `PydanticOutputParser` and automatically asks the model to repair malformed JSON before raising an exception — a practical production pattern for unreliable local models.

---

## Learning Objectives

By the end of this exercise you will be able to:

1. Define three distinct Pydantic schemas with `Field` descriptions and optional fields.
2. Build per-schema LCEL chains using `PydanticOutputParser` and `.partial()` for format instructions.
3. Wrap a `PydanticOutputParser` with `OutputFixingParser` to add automatic JSON repair.
4. Capture the model's raw string output **and** the parsed Pydantic object in the same chain using `RunnablePassthrough` and `RunnableParallel`.
5. Display side-by-side raw/parsed output in a Gradio interface.

---

## Prerequisites

- Exercise 1 completed (confirms Gradio and LangChain work in your environment).
- Ollama running with at least one model pulled.
- Familiarity with Pydantic `BaseModel` and `Field`.

---

## Scenario

Your team receives daily text dumps from three data sources: a job board, a product catalogue, and an events calendar. The sources provide unstructured prose — no consistent format. You are building an internal extraction tool so that non-technical staff can paste raw text, choose the schema that matches the source, and download a clean JSON record. The tool must degrade gracefully when the model produces slightly malformed JSON rather than crashing.

---

## Project Structure

```
Exercise2-StructuredExtractor/
├── app.py              # Gradio app — complete the TODOs
├── schemas.py          # Pydantic model definitions — complete the TODOs
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Instructions

### Step 1 — Define the three Pydantic schemas in `schemas.py`

Open `schemas.py`. You will find three skeleton classes with TODOs.

**Schema A — `JobPosting`** (already familiar from the module):
- `job_title: str` — the role name
- `company: str` — organisation name
- `location: str` — city/country or "Remote"
- `salary_range: Optional[str]` — e.g. "$80k–$100k", or `None`
- `required_skills: list[str]` — list of technologies or skills
- `experience_years: Optional[int]` — minimum years, or `None`

**Schema B — `ProductDescription`**:
- `product_name: str` — the product's marketing name
- `brand: str` — manufacturer or brand
- `price: Optional[str]` — price as a string (e.g. "$49.99"), or `None`
- `key_features: list[str]` — up to five bullet-point features
- `category: str` — product category (e.g. "Electronics", "Clothing")
- `in_stock: Optional[bool]` — availability, or `None` if not mentioned

**Schema C — `EventAnnouncement`**:
- `event_name: str` — full name of the event
- `organiser: str` — person or organisation running the event
- `date: str` — date as a string (e.g. "14 June 2026")
- `location: str` — venue name and/or city, or "Online"
- `topics: list[str]` — list of topics, themes, or speakers
- `registration_url: Optional[str]` — URL or `None` if not mentioned

Each field must have a `Field(description="...")` so the parser can generate meaningful format instructions.

> Hint: Make all `Optional` fields default to `None` (`= Field(default=None, description="...")`). Without `default=None`, the parser will require the model to always supply that field and will reject output that omits it.

---

### Step 2 — Build the extraction chain factory in `app.py`

Locate `TODO 2` in `app.py`. Implement `build_extraction_chain(schema_name, model_name)`.

This function must:

1. Select the correct Pydantic class from `SCHEMA_MAP` using `schema_name`.
2. Create a `PydanticOutputParser` for that class.
3. Wrap it in an `OutputFixingParser` (pass the `llm` as the `parser` argument's `llm`):
   ```python
   from langchain.output_parsers import OutputFixingParser
   fixing_parser = OutputFixingParser.from_llm(parser=base_parser, llm=llm)
   ```
4. Build the prompt with `ChatPromptTemplate` and `.partial(format_instructions=base_parser.get_format_instructions())`.
5. Construct and return the chain: `prompt | llm | fixing_parser`.

> Hint: Use `temperature=0.0` for the extraction `ChatOllama`. Structured extraction is a deterministic task — temperature above 0 increases the rate of malformed JSON with no benefit.

---

### Step 3 — Capture raw LLM output alongside the parsed result

Locate `TODO 3` in `app.py`. Implement `run_extraction(text, schema_name, model_name)`.

The standard chain `prompt | llm | parser` returns only the parsed object. To display the raw model output you need to split the chain after the `llm` step. Use `RunnableParallel`:

```python
from langchain_core.runnables import RunnableParallel
from langchain_core.output_parsers import StrOutputParser

# Build the chain up to (but not including) the parser
pre_parse_chain = prompt | llm

# Run both parsers on the same AIMessage output
dual_chain = pre_parse_chain | RunnableParallel(
    raw=StrOutputParser(),
    parsed=fixing_parser,
)

result = dual_chain.invoke({"text": text})
# result["raw"]    -> str:    the model's exact text output
# result["parsed"] -> object: the validated Pydantic instance
```

Return a tuple `(raw_str, parsed_object)`.

> Hint: If the `OutputFixingParser` still raises after its internal retry, catch `Exception` and return `(raw_str, None)` with an error message in place of the parsed object.

---

### Step 4 — Format the parsed result for display

Locate `TODO 4`. Implement `format_parsed(parsed_object)`.

Convert the Pydantic object to a pretty-printed JSON string for display in the UI:

```python
import json
return json.dumps(parsed_object.model_dump(), indent=2, ensure_ascii=False)
```

If `parsed_object` is `None`, return a clear error message string such as `"[Parser failed — see raw output for the model's response]"`.

---

### Step 5 — Wire the Gradio UI

Locate `TODO 5`. The UI skeleton already provides:
- `input_text` — a `gr.Textbox` for pasting unstructured text
- `schema_radio` — a `gr.Radio` with choices `["Job Posting", "Product Description", "Event Announcement"]`
- `model_dropdown` — a `gr.Dropdown` populated from `ollama list`
- `raw_output_box` — a `gr.Textbox` for the model's raw text
- `parsed_output_box` — a `gr.Code` block (JSON mode) for the structured result
- `extract_btn` and `clear_btn`

Connect `extract_btn.click` to a handler that:
1. Calls `run_extraction(text, schema_name, model_name)` to get `(raw, parsed_obj)`.
2. Calls `format_parsed(parsed_obj)` to get the display string.
3. Returns `(raw, formatted)` to update `[raw_output_box, parsed_output_box]`.

---

### Step 6 — Test with the provided sample texts

Run `python app.py`, open `http://localhost:7860`, and test each schema with the sample texts in `README.md`. Verify:

- [ ] The raw output box shows the model's exact response (including any JSON fencing if present).
- [ ] The parsed output box shows indented JSON matching the selected schema.
- [ ] Switching schemas and re-extracting the same text produces a different JSON structure.
- [ ] A clearly malformed or off-topic input shows the error message in the parsed box rather than crashing.

---

### Step 7 — Build and run with Docker

```bash
docker build -t structured-extractor:1.0 .
docker run --rm -p 7860:7860 \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  structured-extractor:1.0
```

---

## Expected Outcome

- [ ] `python app.py` starts without errors.
- [ ] All three schemas can be selected and produce correctly shaped JSON from appropriate sample text.
- [ ] The raw output panel shows the model's literal text before parsing.
- [ ] The parsed output panel shows indented JSON or a clear error message — never a Python traceback.
- [ ] `docker build -t structured-extractor:1.0 .` completes without errors.
- [ ] The running container passes its health check.

---

## Hints

- If the parsed result is always `None`, enable debug logging:
  ```python
  from langchain.globals import set_debug
  set_debug(True)
  ```
  Look for what the model actually produced between `"Entering"` and `"Finished"` log lines.
- `OutputFixingParser` sends a second request to the model with instructions to fix the JSON. If both attempts fail, it raises `OutputParserException`. Catch it.
- The `gr.Code` component with `language="json"` provides syntax-highlighted JSON display. Pass it a plain string — it handles the rendering.
- If a field has `Optional[str]` but no `default`, Pydantic v2 requires the caller to supply it. Always pair `Optional` with `= Field(default=None, ...)`.

---

## Bonus Challenges

1. Add a fourth schema: `RecipeCard` with fields `recipe_name`, `servings`, `ingredients: list[str]`, `steps: list[str]`, `prep_time_minutes: Optional[int]`.
2. Add a `gr.DownloadButton` that saves the parsed JSON to a `.json` file.
3. Add a confidence indicator: after parsing, display how many `Optional` fields were populated versus left `None` as a simple completeness score.
