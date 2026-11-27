# Hugging Face Spaces Docker image (CPU Basic: 16 GB RAM, 2 vCPU, port 7860)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/tmp/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/tmp/huggingface

WORKDIR /app

# Install CPU-only PyTorch first to keep the image small and fast to build
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

COPY app ./app
COPY data ./data

# Hugging Face Spaces routes HTTP traffic to port 7860
EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
