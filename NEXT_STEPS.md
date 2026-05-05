# 🚀 NEXT STEPS - Azure Deployment Instructions

## Your VM Details
```
Public IP:    172.168.19.116
Username:     azureuser
SSH Port:     22
Region:       Southeast Asia
Size:         Standard D2s v3 (2 vCPUs, 8GB RAM)
OS:           Ubuntu 24.04
```

---

## PHASE 1: Connect to VM (5 minutes)

### Step 1.1: Open PowerShell
Open Windows PowerShell on your local machine.

### Step 1.2: Navigate to SSH Key Location
```powershell
# Find your SSH key (Azure generates it for you)
# It's usually in: C:\Users\<YourUsername>\.ssh\

# Or if you downloaded it from Azure Portal, it's in your Downloads folder
# Look for: emergency-vehicle-vm_key.pem (or similar name)
```

### Step 1.3: Connect to VM
```powershell
ssh -i "C:\Users\sange\.ssh\id_rsa" azureuser@172.168.19.116
```

**Expected output:** You should see a Linux terminal prompt like:
```
azureuser@EmergencyDetection:~$
```

✅ **If successful, move to Phase 2**

---

## PHASE 2: Install System Dependencies (5 minutes)

### Step 2.1: Update System
In the VM terminal, paste this command:

```bash
sudo apt update && sudo apt upgrade -y
```

Wait for completion (~2 minutes)

### Step 2.2: Install Required Packages
```bash
sudo apt install -y python3.10 python3.10-venv python3-pip git libsm6 libxext6 libxrender-dev ffmpeg
```

Wait for completion (~3 minutes)

### Step 2.3: Create Application Directory
```bash
mkdir -p ~/emergency-detection
cd ~/emergency-detection
```

### Step 2.4: Create Python Virtual Environment
```bash
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

✅ **If you see `(venv)` at the start of your terminal line, you're ready for Phase 3**

---

## PHASE 3: Upload Project Files (5 minutes)

### Step 3.1: Open NEW PowerShell Window (Keep VM terminal open!)
Open a separate PowerShell window on your local machine.

### Step 3.2: Navigate to Project Folder
```powershell
cd C:\Users\sange\Desktop\Intergration
```

### Step 3.3: Upload All Files to VM
```powershell
scp -i "C:\Users\sange\.ssh\id_rsa" -r * azureuser@172.168.19.116:~/emergency-detection/
```

**Wait for completion** - You'll see file transfer progress.

### Step 3.4: Verify Upload (In VM terminal)
```bash
ls -la ~/emergency-detection/
```

**Expected:** You should see all your project files listed (main.py, config.py, requirements.txt, etc.)

✅ **If files are there, move to Phase 4**

---

## PHASE 4: Install Python Dependencies (5 minutes)

### Step 4.1: In VM Terminal
```bash
cd ~/emergency-detection
source venv/bin/activate
pip install -r requirements.txt
```

**This may take 3-5 minutes** - It's installing all Python packages (Flask, OpenCV, PyTorch, etc.)

**Expected:** Ends with:
```
Successfully installed ...
```

✅ **If no errors, move to Phase 5**

---

## PHASE 5: Configure Environment Variables (3 minutes)

### Step 5.1: Create .env File
In VM terminal:
```bash
nano .env
```

### Step 5.2: Copy & Paste Configuration
Paste this into the nano editor:

```ini
ENVIRONMENT=AZURE
MONGO_URI=mongodb+srv://USERNAME:PASSWORD@cluster.mongodb.net/emergency_detection?retryWrites=true&w=majority
DB_NAME=EmergencyDetection
COLLECTION_NAME=detections
SUMO_COLLECTION_NAME=SUMOinjections
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

### Step 5.3: UPDATE with Your MongoDB Details
**IMPORTANT:** Replace:
- `USERNAME` - Your MongoDB username
- `PASSWORD` - Your MongoDB password  
- `cluster` - Your MongoDB cluster name

**Example (yours will look like this):**
```ini
MONGO_URI=mongodb+srv://admin:myPassword123@myCluster.mongodb.net/emergency_detection?retryWrites=true&w=majority
```

### Step 5.4: Save File
- Press: `Ctrl + X`
- Type: `Y` (for yes)
- Press: `Enter`

✅ **.env file is saved**

---

## PHASE 6: Disable Cameras for Azure (3 minutes)

### Step 6.1: Edit config.py
In VM terminal:
```bash
nano config.py
```

### Step 6.2: Find PROCESS_FLAGS Section
**Search for this (around line 80):**
```python
PROCESS_FLAGS = {
    "front": True,
    "top": True,
    "upload_front": False,
    "upload_top": False
}
```

### Step 6.3: Replace With
**Change to this:**
```python
PROCESS_FLAGS = {
    "front": False,
    "top": False,
    "upload_front": True,
    "upload_top": True
}
```

### Step 6.4: Save
- Press: `Ctrl + X`
- Type: `Y`
- Press: `Enter`

✅ **Cameras are now disabled for Azure**

---

## PHASE 7: Test Application Locally (3 minutes)

### Step 7.1: Make Sure You're in Virtual Environment
In VM terminal:
```bash
source venv/bin/activate
cd ~/emergency-detection
```

### Step 7.2: Run Application
```bash
python main.py
```

**Expected output:**
```
[INFO] Integrated Emergency System Started.
[INFO] API available at http://localhost:5000/api/status
[INFO] Use /api/upload_video endpoint for video analysis
```

**NO camera/audio errors should appear!** ✅

### Step 7.3: Test API (In NEW PowerShell on your local machine)
```powershell
curl http://172.168.19.116:5000/api/status
```

**Expected:** JSON response with system status

### Step 7.4: Stop Application
Back in VM terminal where `python main.py` is running:
```
Press: Ctrl + C
```

✅ **Application works correctly!**

---

## PHASE 8: Setup as Background Service (5 minutes)

### Step 8.1: Create Service File
In VM terminal:
```bash
sudo tee /etc/systemd/system/emergency-detection.service > /dev/null << 'EOF'
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
EOF
```

### Step 8.2: Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable emergency-detection
sudo systemctl start emergency-detection
```

### Step 8.3: Check Status
```bash
sudo systemctl status emergency-detection
```

**Expected:** Shows `active (running)` ✅

---

## PHASE 9: Setup Nginx Reverse Proxy (5 minutes)

### Step 9.1: Install Nginx
```bash
sudo apt install -y nginx
```

### Step 9.2: Create Nginx Configuration
```bash
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
```

### Step 9.3: Enable Configuration
```bash
sudo ln -s /etc/nginx/sites-available/emergency-detection /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**Expected:** Shows `test is successful` ✅

---

## PHASE 10: Verify Everything Works (5 minutes)

### Step 10.1: Test Service Status
```bash
sudo systemctl status emergency-detection
```

Should show: `active (running)` ✅

### Step 10.2: Test API from Local Machine
Open PowerShell on your local machine:
```powershell
curl http://172.168.19.116/api/status
```

**Should return JSON data** ✅

### Step 10.3: Test Video Upload
```powershell
curl -X POST `
  -F "video=@C:\Users\sange\Desktop\test_video.mp4" `
  -F "view=front" `
  http://172.168.19.116:5000/api/upload_video
```

**Should return:** `{"status": "success", ...}` ✅

### Step 10.4: View Logs
```bash
sudo journalctl -u emergency-detection -f
```

Press `Ctrl + C` to exit

---

## PHASE 11: Update Network Security Group (5 minutes)

### In Azure Portal:

1. Go to: **EmergencyDetection** VM
2. Click: **Networking** (left sidebar)
3. Click: **Add inbound port rule**

**Add these rules:**

```
Rule 1:
  Protocol: TCP
  Source: * (or your IP)
  Destination port: 80
  Priority: 100

Rule 2:
  Protocol: TCP
  Source: * (or your IP)
  Destination port: 443
  Priority: 101

Rule 3:
  Protocol: TCP
  Source: * (or your IP)
  Destination port: 5000
  Priority: 102
```

✅ **Public access now enabled**

---

## PHASE 12: Update Your Frontend (5 minutes)

### Update API Endpoint in Your Dashboard/Frontend

**Change from:**
```javascript
const API_URL = "http://localhost:5000";
```

**To:**
```javascript
const API_URL = "http://172.168.19.116";
// or if using Nginx with domain:
const API_URL = "https://yourdomain.com";
```

Test in your browser:
```
http://172.168.19.116/api/status
```

---

## ✅ COMPLETION CHECKLIST

Mark each as complete:

- [ ] Connected to VM via SSH
- [ ] Installed system packages
- [ ] Created virtual environment
- [ ] Uploaded project files
- [ ] Installed Python dependencies
- [ ] Created .env with MongoDB URI
- [ ] Modified config.py (disabled cameras)
- [ ] Tested app locally (python main.py)
- [ ] API returned JSON response
- [ ] Created systemd service
- [ ] Service is running
- [ ] Nginx installed and configured
- [ ] Network security group rules added
- [ ] Public API access works
- [ ] Video upload tested
- [ ] Updated frontend API URL

---

## 🔍 TROUBLESHOOTING

### If API doesn't respond:
```bash
# Check service status
sudo systemctl status emergency-detection

# View logs
sudo journalctl -u emergency-detection -f

# Restart service
sudo systemctl restart emergency-detection
```

### If MongoDB error:
```bash
# Check .env file
cat .env

# Verify MongoDB URI and add Azure VM IP to MongoDB Atlas whitelist
```

### If port 5000 in use:
```bash
sudo lsof -i :5000
sudo kill -9 <PID>
sudo systemctl restart emergency-detection
```

---

## 📞 USEFUL COMMANDS

```bash
# Connect to VM
ssh -i "C:\Users\sange\.ssh\id_rsa" azureuser@172.168.19.116

# Check service
sudo systemctl status emergency-detection

# View real-time logs
sudo journalctl -u emergency-detection -f

# Restart service
sudo systemctl restart emergency-detection

# Stop service
sudo systemctl stop emergency-detection

# Start service
sudo systemctl start emergency-detection

# Test API
curl http://localhost:5000/api/status

# Check Nginx
sudo systemctl status nginx
```

---

## 🎉 YOU'RE DONE!

Your application is now:
✅ Running on Azure VM
✅ Accessible via public IP
✅ Auto-starting on VM reboot
✅ Ready for production use

**Your API is available at:** `http://172.168.19.116`

Next: Connect your frontend and start uploading videos!

