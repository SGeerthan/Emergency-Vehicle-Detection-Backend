# Azure Deployment Guide - Emergency Vehicle Detection System

## Overview
This guide will help you deploy the Emergency Vehicle Detection System to an Azure VM using the video upload functionality (no live camera required).

## Prerequisites
- Azure Account with active subscription
- Azure CLI installed locally (optional but recommended)
- SSH client for remote access
- Your MongoDB connection URI (MONGO_URI)

---

## Step 1: Create an Azure VM

### Via Azure Portal:
1. Go to [Azure Portal](https://portal.azure.com)
2. Click **Create a resource** → Search for **Virtual Machine**
3. Configure VM with these specs:
   - **Image**: Ubuntu 22.04 LTS (recommended)
   - **Size**: Standard_B2s (2 vCPUs, 4GB RAM - adequate for this project)
   - **Authentication**: Generate SSH keys (save them locally)
   - **Public IP**: Create new (required for Flask API access)
   - **Allow SSH**: Yes (port 22)
   - **Allow HTTP/HTTPS**: Yes (ports 80, 443)

### Via Azure CLI:
```bash
az vm create \
  --resource-group <your-rg> \
  --name emergency-vehicle-vm \
  --image Ubuntu2204 \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard
```

---

## Step 2: Configure Network Security Group

Allow traffic on:
- **SSH (22)**: For remote access
- **HTTP (80)**: For Flask API (if not using HTTPS)
- **HTTPS (443)**: For production
- **Custom Port 5000**: For Flask development server (or whatever port you use)

### In Azure Portal:
VM → Networking → Add Inbound rule for port 5000

---

## Step 3: SSH into VM and Setup

```bash
# SSH into your VM (use public IP from Azure)
ssh azureuser@<VM_PUBLIC_IP>

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and required system packages
sudo apt install -y python3.10 python3.10-venv python3-pip git
sudo apt install -y libsm6 libxext6 libxrender-dev  # For OpenCV
sudo apt install -y ffmpeg                          # For video processing
sudo apt install -y portaudio19-dev                 # Optional: if needed for audio

# Create app directory
mkdir -p ~/emergency-detection
cd ~/emergency-detection
```

---

## Step 4: Clone/Copy Your Project

```bash
# Option A: Clone from Git (if available)
git clone <your-repo-url> .

# Option B: Upload files manually via SCP
# From your local machine:
scp -r /path/to/local/Intergration/* azureuser@<VM_PUBLIC_IP>:~/emergency-detection/
```

---

## Step 5: Setup Python Environment

```bash
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Note: If you get errors with specific packages, see Troubleshooting section
```

---

## Step 6: Configure Environment Variables

```bash
# Create .env file
nano .env
```

Add the following (adjust with your actual values):
```
MONGO_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/<database>?retryWrites=true&w=majority
DB_NAME=EmergencyDetection
COLLECTION_NAME=detections
SUMO_COLLECTION_NAME=SUMOinjections
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

Save: `Ctrl+X` → `Y` → `Enter`

---

## Step 7: Disable Audio/Camera Processing

Since you're using **video upload only**, update `config.py`:

```python
# In config.py - set these to False:
PROCESS_FLAGS = {
    "front": False,           # Disable live camera
    "top": False,             # Disable live camera
    "upload_front": True,     # Enable video upload
    "upload_top": True        # Enable video upload
}
```

Or use environment variable to control this. **Edit config.py**:

---

## Step 8: Test Flask Application

```bash
# Activate venv
source venv/bin/activate

# Run Flask app
python main.py
```

Expected output:
```
 * Running on http://0.0.0.0:5000
 * WARNING: This is a development server. Do not use it in production.
```

**Test endpoints** from another terminal:
```bash
# Check status
curl http://localhost:5000/api/status

# Upload test video
curl -X POST -F "video=@test_video.mp4" -F "view=front" http://localhost:5000/api/upload_video
```

---

## Step 9: Run as Background Service (Systemd)

For production, run Flask as a system service:

```bash
# Create service file
sudo nano /etc/systemd/system/emergency-detection.service
```

Paste this content:
```ini
[Unit]
Description=Emergency Vehicle Detection System
After=network.target

[Service]
Type=simple
User=azureuser
WorkingDirectory=/home/azureuser/emergency-detection
Environment="PATH=/home/azureuser/emergency-detection/venv/bin"
ExecStart=/home/azureuser/emergency-detection/venv/bin/python /home/azureuser/emergency-detection/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable emergency-detection
sudo systemctl start emergency-detection

# Check status
sudo systemctl status emergency-detection
```

---

## Step 10: Setup Reverse Proxy with Nginx (Production)

For production deployment, use Nginx as reverse proxy:

```bash
sudo apt install -y nginx

# Create Nginx config
sudo nano /etc/nginx/sites-available/emergency-detection
```

Add:
```nginx
server {
    listen 80;
    server_name <your-domain-or-ip>;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it:
```bash
sudo ln -s /etc/nginx/sites-available/emergency-detection /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Step 11: Connect Frontend/Dashboard

Update your frontend API endpoint to:
```
http://<VM_PUBLIC_IP>:5000
```

or

```
http://<your-domain>:80
```

---

## Step 12: Monitor Logs

```bash
# View service logs
sudo journalctl -u emergency-detection -f

# View MongoDB connection issues
tail -f ~/.pm2/logs/*

# Check Flask app directly
curl http://localhost:5000/api/status
```

---

## Troubleshooting

### Issue: Dependencies fail to install
```bash
# Try installing system dependencies first
sudo apt install -y build-essential python3-dev
pip install --upgrade pip setuptools wheel
```

### Issue: MongoDB connection fails
- Verify MONGO_URI in .env
- Check MongoDB cluster allows connections from VM IP
- In MongoDB Atlas → Network Access → Add current IP

### Issue: Permission denied on service
```bash
sudo chown -R azureuser:azureuser ~/emergency-detection
sudo chmod -R 755 ~/emergency-detection
```

### Issue: Port 5000 already in use
```bash
# Find process using port 5000
sudo lsof -i :5000
# Kill it if needed
sudo kill -9 <PID>
```

---

## API Endpoints Available

- `GET /api/status` - Current system status
- `POST /api/upload_video` - Upload video for analysis
- `GET /api/analytics` - Get analytics data
- `GET /api/alerts` - Get recent alerts
- `GET /api/latest_detection` - Latest detection info
- `POST /api/video/control` - Start/stop processing

---

## Scale Up (Optional)

For production with high traffic:
- Use Azure App Service instead of VM
- Add Azure Load Balancer
- Setup Azure Database for MongoDB integration
- Use Azure Container Instances/Kubernetes

---

## Cost Optimization

- Use **Standard_B1s** for testing (cheapest option)
- **Deallocate VM** when not in use (saves compute costs)
- Use **reserved instances** for long-term deployment

---

## Next Steps

1. Delete test files: `test_*.py`
2. Update config.py for upload-only mode
3. Setup CI/CD pipeline with GitHub Actions
4. Add SSL certificate with Let's Encrypt for HTTPS
5. Setup monitoring and alerting

