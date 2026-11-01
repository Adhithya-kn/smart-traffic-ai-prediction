# Multi-stage lightweight Python runtime for Smart Traffic AI
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies (supports full ML stack or lightweight fallback)
COPY requirements.txt requirements-dev.txt* ./
RUN pip install --no-cache-dir -r requirements-dev.txt 2>/dev/null || pip install --no-cache-dir -r requirements.txt

# Copy project source code and assets
COPY . .

# Expose standard port
EXPOSE 8080

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://localhost:' + str(os.environ.get('PORT', 8080)) + '/api/health')" || exit 1

# Launch application
CMD ["python3", "run_system.py"]
