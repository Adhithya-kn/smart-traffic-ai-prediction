FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    HOST=0.0.0.0 \
    ENV=production \
    MAX_VIDEO_UPLOAD_SIZE=268435456 \
    CHUNK_UPLOAD_SIZE=8388608

WORKDIR /app

# Install system dependencies for headless OpenCV, video transcoding, and FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python production dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source code and serialized model artifacts
COPY . .

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://localhost:' + str(os.environ.get('PORT', 10000)) + '/api/health')" || exit 1

CMD ["python3", "run_system.py"]
