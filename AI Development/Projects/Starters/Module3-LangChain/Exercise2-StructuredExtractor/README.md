# Exercise 2 — Structured Data Extraction

A Gradio application that extracts structured data from unstructured text using
LangChain's `PydanticOutputParser` and `OutputFixingParser`.

## Prerequisites

- Ollama running: `ollama serve`
- At least one model pulled: `ollama pull llama3.2`
- Python 3.11+

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:7860.

## Sample Texts for Testing

### Job Posting

```
Senior Data Engineer — CloudBase Inc (Austin, TX)

We are hiring an experienced Data Engineer to build and maintain our lakehouse
architecture. You will work closely with data scientists and analysts.

Requirements:
- 4+ years of experience with Python and SQL
- Proficiency with Apache Spark and dbt
- Experience with cloud platforms (AWS preferred)
- Familiarity with Airflow or Prefect for orchestration

Compensation: $120,000 - $145,000
Hybrid work (3 days on-site per week)
```

### Product Description

```
Introducing the NovaBrew Pro Coffee Maker by Helix Appliances.

Brew barista-quality coffee at home. Features a built-in grinder, temperature
control (195-205F), and programmable 24-hour timer. Compatible with whole beans
and pre-ground coffee. Makes up to 12 cups per cycle.

Price: $189.99 | Category: Kitchen Appliances | In stock: Yes
```

### Event Announcement

```
PyCon Regional 2026 — Call for Proposals Now Open!

Join us on 22 August 2026 at the Grand Convention Centre, Seattle.
Organised by the Pacific Northwest Python Users Group.

Topics include: machine learning in production, async Python, developer tooling,
and community building. Keynote speakers TBA.

Register at: https://pycon-pnw-2026.org/register
```

## Docker

```bash
docker build -t structured-extractor:1.0 .
docker run --rm -p 7860:7860 \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  structured-extractor:1.0
```
