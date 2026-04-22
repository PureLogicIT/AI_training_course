# Exercise 1 — Streaming Chat App
# Base image: python:3.11-slim (pinned, never use 'latest')
FROM python:3.11-slim

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy dependency list first so Docker can cache this layer
COPY requirements.txt .

# TODO (Dockerfile Step 1): Install Python dependencies from requirements.txt
# Use --no-cache-dir to keep the image small.
# RUN pip install ...

# Copy application source
COPY app.py .

# Switch to non-root user
USER appuser

# Expose the Gradio default port
EXPOSE 7860

# Environment variable for Ollama host — override at runtime with -e
ENV OLLAMA_HOST=http://host.docker.internal:11434

# TODO (Dockerfile Step 2): Add a HEALTHCHECK that polls http://localhost:7860/
# Use: --interval=30s --timeout=10s --start-period=15s --retries=3
# Command: curl -f http://localhost:7860/ || exit 1
# HEALTHCHECK ...

# TODO (Dockerfile Step 3): Set the CMD to start the app with Python
# CMD [...]
