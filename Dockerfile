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

# Install CPU-only Torch first, then install the rest of requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        torch==2.2.2+cpu \
        torchvision==0.17.2+cpu \
        torchaudio==2.2.2+cpu \
        --index-url https://download.pytorch.org/whl/cpu && \
    grep -vE '^(torch|torchvision|torchaudio)(==|>=|<=|~=|$)' requirements.txt > requirements.runtime.txt && \
    pip install --no-cache-dir -r requirements.runtime.txt

COPY . .

RUN mkdir -p uploads

CMD exec gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers 1 --threads 2 --timeout 180 main:app