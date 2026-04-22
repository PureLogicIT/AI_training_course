# Exercise 1 — Pipeline Playground
# Base image: python:3.11-slim (pinned, never use "latest")
FROM python:3.11-slim

# Metadata
LABEL maintainer="training-repo"
LABEL exercise="Exercise1-PipelinePlayground"

# Create a non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

# Install OS-level dependencies required by torch and transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set the Hugging Face cache directory.
# Mount your host cache at runtime to reuse already-downloaded models:
#   docker run -v "${HOME}/.cache/huggingface:/home/appuser/.cache/huggingface" ...
ENV HF_HOME=/home/appuser/.cache/huggingface

# Working directory inside the container
WORKDIR /app

# Copy and install Python dependencies first (maximises Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=appuser:appgroup app.py download_models.py ./

# Switch to the non-root user
USER appuser

# Expose Gradio's default port
EXPOSE 7860

# Health check: poll the Gradio server every 30 seconds
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/')" || exit 1

# Launch the app
CMD ["python", "app.py"]
