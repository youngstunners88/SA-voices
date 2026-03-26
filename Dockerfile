FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install Qwen3-TTS
RUN git clone https://github.com/QwenLM/Qwen3-TTS.git /tmp/Qwen3-TTS && \
    cd /tmp/Qwen3-TTS && \
    pip install -e . && \
    cd /app && \
    rm -rf /tmp/Qwen3-TTS

# Create necessary directories
RUN mkdir -p data/{cache,waxal,sessions,state} models/cache logs

# Expose ports
EXPOSE 8000 7860

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
