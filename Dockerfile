FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV TF_ENABLE_ONEDNN_OPTS=0
ENV FLASK_ENV=production
ENV ENABLE_AUDIO=false
ENV ENABLE_LIVE_CAMERA=false
ENV ENABLE_VIDEO_UPLOAD=true

# =========================
# System dependencies
# =========================
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# =========================
# Copy requirements (must be UTF-8!)
# =========================
COPY requirements.txt .

# =========================
# Install Python packages
# =========================
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir setuptools==69.5.1

# Install NumPy first (required by OpenCV and ultralytics)
RUN pip install --no-cache-dir \
    numpy==1.26.4 \
    scipy==1.11.4

# CPU-only PyTorch (required by ultralytics/YOLO)
RUN pip install --no-cache-dir \
    torch==2.2.2+cpu \
    torchvision==0.17.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining requirements
RUN pip install --no-cache-dir -r requirements.txt

# Install PyTorch sub-dependencies that --no-deps would skip
RUN pip install --no-cache-dir \
    filelock \
    fsspec \
    networkx \
    sympy

# =========================
# Verify critical imports
# =========================
RUN python -c "import flask; print('flask:', flask.__version__)"
RUN python -c "import cv2; print('cv2:', cv2.__version__)"
RUN python -c "import numpy; print('numpy:', numpy.__version__)"
RUN python -c "import torch; print('torch:', torch.__version__)"
RUN python -c "import gunicorn; print('gunicorn OK')"
RUN python -c "import pymongo; print('pymongo OK')"
RUN python -c "from dotenv import load_dotenv; print('dotenv OK')"

# =========================
# Copy application files
# =========================
COPY . .

# =========================
# Create required directories
# =========================
RUN mkdir -p uploads

# =========================
# Download YOLO model if URL is provided
# If you host bestAllVehicle.pt on cloud storage,
# uncomment and set the URL:
# =========================
# ARG MODEL_URL=""
# RUN if [ -n "$MODEL_URL" ]; then \
#       pip install --no-cache-dir gdown 2>/dev/null || true; \
#       python -c "import urllib.request; urllib.request.urlretrieve('${MODEL_URL}', 'bestAllVehicle.pt')" \
#       && echo "[INFO] Model downloaded successfully" \
#       || echo "[WARNING] Model download failed"; \
#     fi

# =========================
# Expose port (Railway sets PORT dynamically)
# =========================
EXPOSE ${PORT:-5000}

# =========================
# Start with gunicorn via wsgi.py
# - 1 worker (ML models are memory-heavy)
# - 2 threads (handle concurrent API requests)
# - 180s timeout (video uploads can be large)
# =========================
CMD exec python -m gunicorn \
    --bind "0.0.0.0:${PORT:-5000}" \
    --workers 1 \
    --threads 2 \
    --timeout 180 \
    --access-logfile - \
    --error-logfile - \
    wsgi:app
