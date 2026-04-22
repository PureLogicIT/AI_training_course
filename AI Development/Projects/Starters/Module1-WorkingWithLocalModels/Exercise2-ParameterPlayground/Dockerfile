# Exercise 2 — Parameter Playground
# Note: llama-cpp-python is NOT installed in this image (it requires a GGUF
# file path from the host). Use the Ollama backend when running in Docker.
FROM python:3.11-slim

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY requirements.txt .

# TODO (Dockerfile Step 1): Install dependencies from requirements.txt.
# Exclude llama-cpp-python for the Docker image (Ollama backend only).
# Hint: pip install --no-cache-dir gradio ollama
# RUN pip install ...

COPY app.py backends.py ./

USER appuser

EXPOSE 7860

ENV OLLAMA_HOST=http://host.docker.internal:11434
ENV OLLAMA_MODEL=llama3.2

# TODO (Dockerfile Step 2): Add a HEALTHCHECK for http://localhost:7860/
# HEALTHCHECK ...

# TODO (Dockerfile Step 3): Set CMD to start the app
# CMD [...]
