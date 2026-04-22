FROM python:3.11-slim

# Create a non-root user for security
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Install dependencies as root before switching user
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app.py .

# Transfer ownership to the non-root user
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 7860

# Health check: confirm the Gradio server is responding
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:7860', timeout=4)" \
    || exit 1

CMD ["python", "app.py"]
