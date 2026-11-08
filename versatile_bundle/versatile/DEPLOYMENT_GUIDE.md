# Smart Traffic AI - Unified Versatile Deployment Guide

## 1. Directory Structure

- `frontend/`: Clean, production-ready static assets (HTML, CSS, JS, Canvas engine) with the White & Blue theme and bespoke Traffic AI crest.
- `backend/`: Core REST API application server, Vercel serverless entrypoint (`api/index.py`), road registry, and heatmap services.
- `versatile/`: Cloud deployment manifests for Vercel, Render, Docker, and environment configuration.

---

## 2. Deployment Targets

### A. Vercel (Production Serverless)
1. Deploy command:
   ```bash
   vercel deploy --prod --yes
   ```
2. Public production URL:
   `https://smart-traffic-ai-prediction.vercel.app`

### B. Render (Production Web Service)
1. Configuration: `render.yaml`
2. Auto-build with CPU-only PyTorch to prevent OOM errors:
   ```bash
   python3 run_system.py
   ```
3. Health check path: `/api/health`

### C. Docker
1. Build image:
   ```bash
   docker build -t smart-traffic-ai:latest .
   ```
2. Run container:
   ```bash
   docker run -p 10000:10000 --name smart-traffic smart-traffic-ai:latest
   ```

### D. Local Isolated Daemon
1. Start dedicated background daemon on custom port:
   ```bash
   python3 run_system.py --port 8090
   ```
2. Access locally:
   `http://localhost:8090/portal`
   `http://localhost:8090/login`
   *(Port 8080 preserved for Java NRMS)*

---

## 3. End-to-End Verification Commands

- Run unit & regression test suite:
  ```bash
  pytest -m "not integration" tests/
  ```
- Run Playwright E2E verification:
  ```bash
  BASE_URL=http://localhost:8090 node tests/e2e_playwright/test_theme_switcher.js
  BASE_URL=http://localhost:8090 node tests/e2e_playwright/test_vision_video_and_theme_e2e.js
  ```
