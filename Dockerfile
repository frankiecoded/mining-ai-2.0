# Hugging Face Spaces Dockerfile - AI OS WhatsApp worker
# Build: run the worker + FastAPI on $PORT (default 7860) via hf_runner.py
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    tesseract-ocr \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python requirements (retries guard against transient PyPI timeouts)
# CPU-only torch first: satisfies sentence-transformers' torch dependency and
# avoids pulling ~1.5GB of CUDA wheels that a CPU-only HF Space never uses.
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 120 --default-timeout 120 \
        --index-url https://download.pytorch.org/whl/cpu \
        "torch>=2.2" "torchvision" "torchaudio"
RUN pip install --no-cache-dir --retries 10 --timeout 120 --default-timeout 120 \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements.txt

# Copy application source code
COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROCESSING_MODE=queue \
    HF_HOME=/app/.cache/huggingface

EXPOSE 7860

# Health check (FastAPI exposes /health)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:'+__import__('os').environ.get('PORT','7860')+'/health').raise_for_status()"

CMD ["python", "hf_runner.py"]
