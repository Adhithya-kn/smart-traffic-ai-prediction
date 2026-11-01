# Multi-stage lightweight Python runtime for Smart Traffic AI
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

WORKDIR /app

# Copy dependency specification and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and model artifacts
COPY . .

# Expose production port
EXPOSE 10000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://localhost:' + str(os.environ.get('PORT', 10000)) + '/api/health')" || exit 1

# Launch application
CMD ["python3", "run_system.py"]
