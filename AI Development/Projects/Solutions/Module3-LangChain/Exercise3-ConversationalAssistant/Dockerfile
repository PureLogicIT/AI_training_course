FROM python:3.11-slim

RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py history_store.py ./

RUN mkdir -p /app/sessions && chown -R appuser:appgroup /app

USER appuser

EXPOSE 7860

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:7860', timeout=4)" \
    || exit 1

CMD ["python", "app.py"]
