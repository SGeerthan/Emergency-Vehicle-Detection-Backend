FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV TF_ENABLE_ONEDNN_OPTS=0
ENV FLASK_ENV=production

# =========================
# System dependencies
# =========================
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    libasound2-dev \
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
# Copy requirements
# =========================
COPY requirements.txt .

# =========================
# Upgrade pip and install setuptools
# pkg_resources comes from setuptools
# =========================
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir setuptools==69.5.1

# =========================
# Core stable versions
# NumPy must stay below 2 for OpenCV 4.9 and TensorFlow 2.15
# =========================
RUN pip install --no-cache-dir \
    numpy==1.26.4 \
    scipy==1.11.4

# =========================
# CPU-only PyTorch
# =========================
RUN pip install --no-cache-dir --no-deps \
    torch==2.2.2+cpu \
    torchvision==0.17.2+cpu \
    torchaudio==2.2.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# =========================
# Install remaining requirements
# Exclude packages controlled manually below
# =========================
RUN grep -vE '^(torch|torchvision|torchaudio|numpy|scipy|opencv-python-headless|opencv-python|Flask|flask-cors|gunicorn|requests|python-dotenv|pymongo|sounddevice|soundfile|tensorflow|keras|tensorflow-hub|tf-keras|setuptools)(==|>=|<=|~=|$)' requirements.txt > requirements.runtime.txt && \
    pip install --no-cache-dir -r requirements.runtime.txt

# =========================
# Force install critical runtime packages
# Fixes repeated Railway missing-module errors
# =========================
RUN pip install --no-cache-dir --force-reinstall \
    setuptools==69.5.1 \
    numpy==1.26.4 \
    scipy==1.11.4 \
    Flask==3.1.3 \
    flask-cors==6.0.2 \
    gunicorn==23.0.0 \
    requests==2.32.5 \
    python-dotenv==1.2.2 \
    pymongo==4.16.0 \
    sounddevice==0.5.5 \
    soundfile==0.13.1 \
    tensorflow==2.15.0 \
    keras==2.15.0 \
    tensorflow-hub==0.16.1 \
    tf-keras==2.15.0 \
    opencv-python-headless==4.9.0.80

# =========================
# Install PyTorch dependencies that were skipped by --no-deps
# =========================
RUN pip install --no-cache-dir \
    filelock \
    fsspec \
    networkx \
    sympy \
    pillow==12.1.1

# =========================
# Verify important imports during build
# =========================
RUN python -c "import pkg_resources; print('pkg_resources installed')"
RUN python -c "import flask; print('flask installed')"
RUN python -c "import requests; print('requests installed')"
RUN python -c "from dotenv import load_dotenv; print('python-dotenv installed')"
RUN python -c "import pymongo; print('pymongo installed')"
RUN python -c "import sounddevice; print('sounddevice installed')"
RUN python -c "import soundfile; print('soundfile installed')"
RUN python -c "import tensorflow as tf; print('tensorflow:', tf.__version__)"
RUN python -c "import tensorflow_hub as hub; print('tensorflow-hub installed')"
RUN python -c "import cv2; print('cv2:', cv2.__version__)"
RUN python -c "import numpy; print('numpy:', numpy.__version__)"
RUN python -c "import torch; print('torch:', torch.__version__)"
RUN python -c "import gunicorn; print('gunicorn installed')"

# =========================
# Copy application files
# =========================
COPY . .

# =========================
# Create upload folder
# =========================
RUN mkdir -p uploads

# =========================
# Run app with Railway PORT
# =========================
CMD exec python -m gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers 1 --threads 2 --timeout 180 main:app