# Azure Deployment Quick Reference

## 1. VM Creation Command

```bash
# Create Azure Resource Group
az group create --name emergency-detection-rg --location eastus

# Create Ubuntu VM
az vm create \
  --resource-group emergency-detection-rg \
  --name emergency-vehicle-vm \
  --image UbuntuLTS \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard

# Get Public IP
az vm list-ip-addresses --resource-group emergency-detection-rg --output table
```

---

## 2. SSH Connection

```bash
# Connect to VM
ssh -i ~/.ssh/id_rsa azureuser@<PUBLIC_IP>

# If key not found
ssh azureuser@<PUBLIC_IP>  # Azure will generate and display key on first run
```

---

## 3. Initial Setup (One-liner)

```bash
# Copy and paste on VM terminal

sudo apt update && sudo apt upgrade -y && \
sudo apt install -y python3.10 python3.10-venv python3-pip git libsm6 libxext6 libxrender-dev ffmpeg && \
mkdir -p ~/emergency-detection && \
cd ~/emergency-detection
```

---

## 4. Upload Project Files

```bash
# From your local machine (NOT on VM)

scp -i /path/to/ssh/key -r /path/to/local/Intergration/* azureuser@<PUBLIC_IP>:~/emergency-detection/
```

---

## 5. Python Setup (On VM)

```bash
cd ~/emergency-detection

python3.10 -m venv venv

source venv/bin/activate

pip install --upgrade pip

pip install -r requirements.txt
```

---

## 6. Configuration (.env File)

```bash
# Create .env on VM
cat > .env << 'EOF'
ENVIRONMENT=AZURE
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/emergency_detection?retryWrites=true&w=majority
DB_NAME=EmergencyDetection
COLLECTION_NAME=detections
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
EOF
```

---

## 7. Update config.py

```bash
# Edit config.py and find PROCESS_FLAGS section
# Change to:

PROCESS_FLAGS = {
    "front": False,
    "top": False,
    "upload_front": True,
    "upload_top": True
}
```

Or set via environment variable:
```bash
echo "ENVIRONMENT=AZURE" >> .env
```

---

## 8. Test Application

```bash
# Activate venv
source venv/bin/activate

# Run app
python main.py

# In another SSH session, test:
curl http://localhost:5000/api/status

# If OK, press Ctrl+C to stop
```

---

## 9. Setup as Systemd Service

```bash
sudo tee /etc/systemd/system/emergency-detection.service > /dev/null << 'EOF'
[Unit]
Description=Emergency Vehicle Detection System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/azureuser/emergency-detection
Environment="PATH=/home/azureuser/emergency-detection/venv/bin"
ExecStart=/home/azureuser/emergency-detection/venv/bin/python /home/azureuser/emergency-detection/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable emergency-detection
sudo systemctl start emergency-detection
sudo systemctl status emergency-detection
```

---

## 10. Setup Nginx (Production)

```bash
sudo apt install -y nginx

sudo tee /etc/nginx/sites-available/emergency-detection > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/emergency-detection /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 11. Important Commands (On VM)

```bash
# Check service status
sudo systemctl status emergency-detection

# Restart service
sudo systemctl restart emergency-detection

# Stop service
sudo systemctl stop emergency-detection

# View logs (real-time)
sudo journalctl -u emergency-detection -f

# View last 50 lines of logs
sudo journalctl -u emergency-detection -n 50

# Check if listening on port 5000
netstat -tulpn | grep 5000

# Test API from VM
curl http://localhost:5000/api/status

# Upload test video
curl -X POST -F "video=@test.mp4" -F "view=front" http://localhost:5000/api/upload_video
```

---

## 12. Network Security Group Rules

In Azure Portal, go to: **VM → Networking → Add inbound port rule**

```
Protocol: TCP
Source: *
Destination port: 22       (SSH)
Priority: 300

Protocol: TCP
Source: *
Destination port: 80       (HTTP)
Priority: 301

Protocol: TCP
Source: *
Destination port: 443      (HTTPS)
Priority: 302

Protocol: TCP
Source: *
Destination port: 5000     (Flask Dev)
Priority: 303
```

---

## 13. Frontend API URL

```javascript
// Update in your dashboard/frontend:
const API_BASE_URL = "http://<YOUR_VM_PUBLIC_IP>:5000";

// Or with domain:
const API_BASE_URL = "https://yourdomain.com";
```

---

## 14. Deployment Checklist

- [ ] Resource Group created
- [ ] VM created and running
- [ ] Public IP assigned
- [ ] NSG rules added
- [ ] SSH connection verified
- [ ] System packages installed
- [ ] Project files uploaded
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] .env file configured
- [ ] config.py modified (PROCESS_FLAGS)
- [ ] App tested locally
- [ ] Systemd service created
- [ ] Service enabled and running
- [ ] Nginx configured (production)
- [ ] API endpoints accessible
- [ ] MongoDB connection verified
- [ ] Video upload tested
- [ ] Frontend updated with API URL

---

## 15. Cost Optimization Commands

```bash
# Deallocate VM (pauses billing)
az vm deallocate --resource-group emergency-detection-rg --name emergency-vehicle-vm

# Start VM again
az vm start --resource-group emergency-detection-rg --name emergency-vehicle-vm

# Check disk usage
df -h

# Clean old uploads
rm -rf ~/emergency-detection/uploads/*

# Delete resource group (WARNING: deletes everything)
az group delete --name emergency-detection-rg
```

---

## 16. Troubleshooting One-Liners

```bash
# Check all logs for errors
sudo journalctl -u emergency-detection | grep ERROR

# Restart everything
sudo systemctl restart emergency-detection nginx

# Kill hanging process on port 5000
sudo lsof -i :5000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Test MongoDB connection from VM
python3 -c "import pymongo; print(pymongo.MongoClient('$MONGO_URI').server_info())"

# Check Python version
python3.10 --version

# Verify venv activation
which python  # Should show venv path
```

---

## 17. Scaling Options

If you need more power:

```bash
# Resize VM to larger size
az vm resize \
  --resource-group emergency-detection-rg \
  --name emergency-vehicle-vm \
  --size Standard_B4ms

# Common sizes:
# Standard_B1s - 1 vCPU, 1GB (cheapest)
# Standard_B2s - 2 vCPUs, 4GB (recommended)
# Standard_B4ms - 4 vCPUs, 16GB (high traffic)
```

---

## 18. Useful Links

- Azure Portal: https://portal.azure.com
- Azure Pricing: https://azure.microsoft.com/pricing/calculator/
- Azure CLI Docs: https://learn.microsoft.com/cli/azure/
- MongoDB Atlas: https://www.mongodb.com/cloud/atlas
- Nginx Docs: https://nginx.org/en/docs/

---

## 19. File Locations on VM

```
/home/azureuser/emergency-detection/       # Project root
├── main.py
├── config.py
├── requirements.txt
├── .env                                     # Configuration (create this)
├── uploads/                                 # Video uploads
├── venv/                                    # Virtual environment
└── logs/                                    # Application logs

/etc/systemd/system/emergency-detection.service  # Service config
/etc/nginx/sites-available/emergency-detection   # Nginx config
```

---

## 20. Quick Deployment (All Steps in One)

```bash
# Run this script after SSH connection:
bash << 'EOF'
set -e

echo "Installing dependencies..."
sudo apt update && sudo apt install -y python3.10 python3.10-venv python3-pip git libsm6 libxext6 ffmpeg

echo "Setting up project..."
mkdir -p ~/emergency-detection && cd ~/emergency-detection
python3.10 -m venv venv
source venv/bin/activate

echo "Installing Python packages..."
pip install --upgrade pip setuptools wheel

echo "Ready for project upload!"
echo "From local machine, run:"
echo "scp -r /path/to/Intergration/* azureuser@\`curl -s http://169.254.169.254/metadata/instance?api-version=2021-02-01 | jq -r '.network.interface[0].ipv4.ipAddress[0].publicIpAddress'\`:~/emergency-detection/"
EOF
```

---

## Help Commands

```bash
# Create an alias for quick status check
echo "alias vStatus='sudo journalctl -u emergency-detection -n 20'" >> ~/.bashrc
source ~/.bashrc
vStatus

# Create a maintenance script
cat > ~/check_health.sh << 'EOF'
#!/bin/bash
echo "=== Service Status ==="
sudo systemctl status emergency-detection --no-pager
echo -e "\n=== Recent Errors ==="
sudo journalctl -u emergency-detection -p err -n 10 --no-pager
echo -e "\n=== API Status ==="
curl -s http://localhost:5000/api/status | jq '.is_emergency'
EOF

chmod +x ~/check_health.sh
./check_health.sh
```

---

## Notes

- Replace `<PUBLIC_IP>` with your actual Azure VM public IP
- Replace `mongodb+srv://...` with your real MongoDB URI
- Keep SSH key secure (chmod 600)
- Regularly backup MongoDB data
- Monitor logs for errors
- Test video uploads regularly

