# Exercise 3 — Model Benchmark & Comparison
FROM python:3.11-slim

LABEL maintainer="training-repo"
LABEL exercise="Exercise3-ModelBenchmark"

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# HF cache — mount your host cache with:
#   docker run -v "${HOME}/.cache/huggingface:/home/appuser/.cache/huggingface" ...
ENV HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appgroup app.py benchmark_engine.py sample_prompts.json ./

USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/')" || exit 1

CMD ["python", "app.py"]
