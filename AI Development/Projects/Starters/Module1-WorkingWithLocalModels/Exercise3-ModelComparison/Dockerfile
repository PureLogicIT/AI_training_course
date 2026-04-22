# Exercise 3 — Multi-Turn Model Comparison App
FROM python:3.11-slim

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY requirements.txt .

# TODO (Dockerfile Step 1): Install Python dependencies from requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt

COPY app.py conversation.py inference.py ./

USER appuser

EXPOSE 7860

ENV OLLAMA_HOST=http://ollama:11434

# TODO (Dockerfile Step 2): HEALTHCHECK on http://localhost:7860/
# HEALTHCHECK ...

# TODO (Dockerfile Step 3): CMD to start the app
# CMD [...]
