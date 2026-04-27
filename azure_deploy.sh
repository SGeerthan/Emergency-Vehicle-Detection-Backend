#!/bin/bash
# Azure VM Deployment Script
# Run this on the Azure VM after SSH connection
# Usage: bash azure_deploy.sh

set -e  # Exit on error

echo "================================"
echo "Emergency Detection System Setup"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Update system
echo -e "${YELLOW}[1/10] Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

# Step 2: Install system dependencies
echo -e "${YELLOW}[2/10] Installing system dependencies...${NC}"
sudo apt install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    git \
    wget \
    curl \
    build-essential \
    python3-dev \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ffmpeg

# Step 3: Create application directory
echo -e "${YELLOW}[3/10] Creating application directory...${NC}"
APP_DIR="$HOME/emergency-detection"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Step 4: Create virtual environment
echo -e "${YELLOW}[4/10] Creating Python virtual environment...${NC}"
python3.10 -m venv venv
source venv/bin/activate

# Step 5: Upgrade pip
echo -e "${YELLOW}[5/10] Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel

# Step 6: Copy files (if running from uploaded directory)
echo -e "${YELLOW}[6/10] Checking for requirement files...${NC}"
if [ -f "requirements.txt" ]; then
    echo -e "${GREEN}Found requirements.txt${NC}"
else
    echo -e "${RED}requirements.txt not found. Make sure to upload your project files!${NC}"
fi

# Step 7: Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}[7/10] Installing Python dependencies...${NC}"
    pip install -r requirements.txt
else
    echo -e "${YELLOW}[7/10] Skipping pip install - requirements.txt not found${NC}"
fi

# Step 8: Create .env file template
echo -e "${YELLOW}[8/10] Creating .env template...${NC}"
if [ ! -f ".env" ]; then
    cat > .env << EOF
# MongoDB Configuration
MONGO_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/<database>?retryWrites=true&w=majority
DB_NAME=EmergencyDetection
COLLECTION_NAME=detections
SUMO_COLLECTION_NAME=SUMOinjections

# Flask Configuration
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
EOF
    echo -e "${GREEN}.env file created at $APP_DIR/.env${NC}"
    echo -e "${YELLOW}Please edit .env and add your MongoDB credentials${NC}"
else
    echo -e "${GREEN}.env already exists${NC}"
fi

# Step 9: Create systemd service
echo -e "${YELLOW}[9/10] Creating systemd service...${NC}"
sudo tee /etc/systemd/system/emergency-detection.service > /dev/null << EOF
[Unit]
Description=Emergency Vehicle Detection System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable emergency-detection
echo -e "${GREEN}Service created and enabled${NC}"

# Step 10: Create quick start guide
echo -e "${YELLOW}[10/10] Creating quick start guide...${NC}"
cat > QUICK_START.txt << EOF
===========================================
Emergency Detection System - Quick Start
===========================================

1. Edit Configuration:
   - Edit .env file with your MongoDB URI
   - nano .env

2. Test the application:
   - source venv/bin/activate
   - python main.py
   - Check: curl http://localhost:5000/api/status

3. Start as service:
   - sudo systemctl start emergency-detection
   - sudo systemctl status emergency-detection

4. View logs:
   - sudo journalctl -u emergency-detection -f

5. Upload video for testing:
   - curl -X POST -F "video=@video.mp4" -F "view=front" http://localhost:5000/api/upload_video

6. Nginx setup (production):
   - sudo apt install nginx
   - Configure as reverse proxy (see AZURE_DEPLOYMENT.md)

===========================================
EOF

echo -e "${GREEN}✓ Setup completed!${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Edit .env with your MongoDB credentials"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python main.py (to test)"
echo "4. Or: sudo systemctl start emergency-detection (for service mode)"
