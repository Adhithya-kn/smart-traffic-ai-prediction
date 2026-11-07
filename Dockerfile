# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    HOST=0.0.0.0 \
    ENV=production \
    MAX_VIDEO_UPLOAD_SIZE=268435456 \
    CHUNK_UPLOAD_SIZE=8388608

WORKDIR /app

# System dependencies: headless OpenCV runtime libs + FFmpeg for video transcode/annotation.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch first: otherwise pip pulls multi-GB CUDA/NVIDIA wheels on Linux.
# requirements.txt then resolves "torch" and "torchvision" as already satisfied.
RUN pip install --no-cache-dir "torch>=2.2,<3.0" "torchvision>=0.17,<1.0" --index-url https://download.pytorch.org/whl/cpu

# Python runtime dependencies (includes cryptography for the secrets vault).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Application source. `architecture/` is served at /architecture/*; `app/static/` is the UI;
# `yolo11n.pt` is the local fallback detector weight. Mutable state is excluded via .dockerignore.
COPY . .

# Writable runtime/cache directories (state defaults to /app/var unless PERSISTENT_DATA_DIR is set).
RUN mkdir -p /app/var \
        /app/traffic_system/storage/videos/uploads \
        /app/traffic_system/storage/videos/chunks \
        /app/traffic_system/storage/videos/processed \
        /app/traffic_system/storage/videos/temp

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://localhost:' + str(os.environ.get('PORT', 10000)) + '/api/health', timeout=3)" || exit 1

CMD ["python3", "run_system.py"]
