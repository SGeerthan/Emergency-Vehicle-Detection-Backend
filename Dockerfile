FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV TF_ENABLE_ONEDNN_OPTS=0
ENV FLASK_ENV=production

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

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip

# Keep NumPy below 2 because OpenCV 4.9 and TensorFlow 2.15 need NumPy 1.x
RUN pip install --no-cache-dir numpy==1.26.4 scipy==1.11.4

# Install CPU-only PyTorch
RUN pip install --no-cache-dir --no-deps \
    torch==2.2.2+cpu \
    torchvision==0.17.2+cpu \
    torchaudio==2.2.2+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining requirements except packages handled manually
RUN grep -vE '^(torch|torchvision|torchaudio|numpy|scipy|opencv-python-headless|opencv-python|Flask|flask-cors|gunicorn)(==|>=|<=|~=|$)' requirements.txt > requirements.runtime.txt && \
    pip install --no-cache-dir -r requirements.runtime.txt

# Force install critical packages
RUN pip install --no-cache-dir --force-reinstall \
    numpy==1.26.4 \
    scipy==1.11.4 \
    Flask==3.1.3 \
    flask-cors==6.0.2 \
    gunicorn==23.0.0 \
    opencv-python-headless==4.9.0.80

# Verify imports during build
RUN python -c "import flask; print('flask installed')"
RUN python -c "import cv2; print('cv2:', cv2.__version__)"
RUN python -c "import numpy; print('numpy:', numpy.__version__)"
RUN python -c "import gunicorn; print('gunicorn installed')"

COPY . .

RUN mkdir -p uploads

CMD exec python -m gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers 1 --threads 2 --timeout 180 main:app