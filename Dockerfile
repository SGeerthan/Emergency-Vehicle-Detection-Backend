FROM python:3.10-slim

# Set working directory
WORKDIR /app

# =========================
# System dependencies
# =========================
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    libasound2-dev \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# =========================
# Install Python dependencies
# =========================
COPY requirements.txt .

RUN pip install --upgrade pip

# FIX: ensure torch installs cleanly before others (important for YOLO)
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

# =========================
# Copy application
# =========================
COPY . .

# Create uploads folder
RUN mkdir -p uploads

# =========================
# Environment variables
# =========================
ENV FLASK_APP=main.py \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    TF_ENABLE_ONEDNN_OPTS=0

# =========================
# Health check
# =========================
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/status')"

# =========================
# Run app
# =========================
CMD ["python", "main.py"]