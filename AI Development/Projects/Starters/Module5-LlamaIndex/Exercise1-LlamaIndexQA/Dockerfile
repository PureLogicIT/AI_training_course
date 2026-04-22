FROM python:3.11-slim

# Install system dependencies for PDF support
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy and install Python dependencies as root first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app.py .

# Create index storage directory owned by appuser
RUN mkdir -p /app/index_storage && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 7860

# Health check: verify Gradio is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

CMD ["python", "app.py"]
