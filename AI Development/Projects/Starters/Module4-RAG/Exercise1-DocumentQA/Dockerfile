FROM python:3.11-slim

# Create a non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Install dependencies as root before switching users
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Gradio listens on 7860 by default
EXPOSE 7860

# Environment variable for Ollama host (override at runtime)
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/')" || exit 1

CMD ["python", "app.py"]
