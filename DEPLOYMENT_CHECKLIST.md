# Azure Deployment Checklist

## Pre-Deployment (Local Preparation)

### Clean up project
- [ ] Delete test files: `rm test_*.py`
- [ ] Remove unnecessary cache: `rm -rf __pycache__ .pytest_cache`
- [ ] Verify `.env` has real MongoDB credentials
- [ ] Check `requirements.txt` is up to date
- [ ] Test locally: `python main.py` works without errors

### Prepare Azure environment  
- [ ] Create Azure Account with subscription
- [ ] Install Azure CLI: `az login`
- [ ] Create Resource Group: `az group create --name emergency-detection-rg --location eastus`

---

## Azure VM Setup

### Create VM
- [ ] Create VM in Azure Portal or using Azure CLI
  - **Image**: Ubuntu 22.04 LTS
  - **Size**: Standard_B2s (minimum)
  - **Region**: Choose closest to your location
  - **SSH Key**: Download and save locally
  - **Public IP**: Create and note down the IP address

### Configure Network
- [ ] Add Network Security Group rules:
  - [ ] SSH (port 22) - for remote access
  - [ ] HTTP (port 80) - for Flask API
  - [ ] HTTPS (port 443) - for production
  - [ ] Custom (port 5000) - for Flask development

### Record VM Details
- [ ] VM Public IP: `___________________`
- [ ] VM Username: `azureuser`
- [ ] SSH Key Location: `___________________`

---

## Remote Setup via SSH

### Connect to VM
```bash
# Connect via SSH
ssh -i /path/to/key azureuser@<VM_IP>

# Verify connection and OS
uname -a
```
- [ ] SSH connection successful
- [ ] OS verified as Ubuntu 22.04

### Initial Setup
```bash
# Run deployment script (method 1)
# First, upload or create the script on the VM
bash azure_deploy.sh

# OR manual setup (method 2)
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.10 python3.10-venv python3-pip git
sudo apt install -y libsm6 libxext6 libxrender-dev ffmpeg
```
- [ ] System packages installed
- [ ] Python 3.10 verified: `python3.10 --version`

### Upload Project Files
```bash
# Option 1: Via SCP from local machine
scp -i /path/to/key -r ./Intergration/* azureuser@<VM_IP>:~/emergency-detection/

# Option 2: Clone from Git
git clone <your-repo-url> ~/emergency-detection
```
- [ ] Project files uploaded to `/home/azureuser/emergency-detection`
- [ ] Verify with: `ls -la ~/emergency-detection`

### Setup Python Environment
```bash
cd ~/emergency-detection
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```
- [ ] Virtual environment created
- [ ] Dependencies installed without errors
- [ ] Verify: `pip list | grep flask`

---

## Configuration

### Edit Environment Variables
```bash
nano .env
```
- [ ] Add MongoDB URI: `mongodb+srv://...`
- [ ] Set `DB_NAME=EmergencyDetection`
- [ ] Set `COLLECTION_NAME=detections`
- [ ] Set `FLASK_ENV=production`
- [ ] Set `FLASK_HOST=0.0.0.0`
- [ ] Set `FLASK_PORT=5000`
- [ ] Save and exit

### Modify config.py for Azure
```bash
nano config.py
```
- [ ] Set `PROCESS_FLAGS["front"] = False` (disable live camera)
- [ ] Set `PROCESS_FLAGS["top"] = False` (disable live camera)
- [ ] Verify audio processing can be disabled if needed
- [ ] Save and exit

---

## Testing

### Local Test (on VM)
```bash
source venv/bin/activate
python main.py
```
- [ ] Application starts without errors
- [ ] See: "Integrated Emergency System Started"
- [ ] API available message appears
- [ ] No MongoDB connection errors
- [ ] No camera/audio errors (expected, disabled)
- [ ] Ctrl+C stops cleanly

### API Test (in new SSH session)
```bash
# Test health endpoint
curl http://localhost:5000/api/status

# Should return JSON with system status
```
- [ ] API responds with JSON
- [ ] Status shows "video": {"front": {}, "top": {}, ...}
- [ ] No 500 errors

### Video Upload Test
```bash
# Upload a test video
curl -X POST \
  -F "video=@test_video.mp4" \
  -F "view=front" \
  http://localhost:5000/api/upload_video
```
- [ ] Upload returns: `{"status": "success"}`
- [ ] Video file appears in `/uploads` directory
- [ ] Check logs for processing: `tail -f app.log`

---

## Production Deployment

### Create Systemd Service
```bash
# This is already done by azure_deploy.sh
# Or manually:

sudo nano /etc/systemd/system/emergency-detection.service
# [Add service content from AZURE_DEPLOYMENT.md]
sudo systemctl daemon-reload
sudo systemctl enable emergency-detection
```
- [ ] Service file created
- [ ] Service enabled on boot
- [ ] Verified with: `sudo systemctl status emergency-detection`

### Start Service
```bash
sudo systemctl start emergency-detection
sudo systemctl status emergency-detection
```
- [ ] Service running (active)
- [ ] No errors in status output
- [ ] Test: `curl http://localhost:5000/api/status`

### View Logs
```bash
# Real-time logs
sudo journalctl -u emergency-detection -f

# Last 50 lines
sudo journalctl -u emergency-detection -n 50
```
- [ ] Logs show clean startup
- [ ] No critical errors
- [ ] MongoDB connection confirmed

---

## Production Reverse Proxy (Nginx)

### Install & Configure Nginx
```bash
sudo apt install -y nginx

# Create config
sudo nano /etc/nginx/sites-available/emergency-detection
# [Add nginx config from AZURE_DEPLOYMENT.md]

sudo ln -s /etc/nginx/sites-available/emergency-detection /etc/nginx/sites-enabled/
sudo nginx -t  # Verify syntax
sudo systemctl restart nginx
```
- [ ] Nginx installed
- [ ] Config verified
- [ ] Nginx restarted successfully

### Test via Public IP
```bash
# From any browser or curl on your local machine:
curl http://<VM_PUBLIC_IP>/api/status
```
- [ ] Public access works
- [ ] API responds through Nginx
- [ ] Port 80 is accessible

### SSL Certificate (Recommended)
```bash
sudo apt install -y certbot python3-certbot-nginx

# For production domains:
sudo certbot --nginx -d your-domain.com
```
- [ ] [ ] SSL certificate obtained (if using domain)
- [ ] [ ] Nginx updated with SSL
- [ ] [ ] HTTPS working

---

## Monitoring & Maintenance

### Setup Log Rotation
```bash
sudo nano /etc/logrotate.d/emergency-detection
# Add: /home/azureuser/emergency-detection/logs/*.log { daily rotate 7 }

sudo logrotate /etc/logrotate.d/emergency-detection
```
- [ ] Log rotation configured

### Monitor Service
```bash
# Check service status
sudo systemctl status emergency-detection

# Restart if needed
sudo systemctl restart emergency-detection

# View real-time logs
sudo journalctl -u emergency-detection -f
```
- [ ] Monitoring setup
- [ ] Restart procedure documented
- [ ] Log viewing procedure tested

### Check Disk Usage
```bash
df -h
du -sh ~/emergency-detection

# Clean old uploads if needed
rm -rf ~/emergency-detection/uploads/*
```
- [ ] Disk space checked
- [ ] Upload cleanup procedure ready

---

## Backup & Disaster Recovery

### Backup Project Files
```bash
# From local machine:
scp -i /path/to/key -r azureuser@<VM_IP>:~/emergency-detection ~/backups/emergency-detection-$(date +%Y%m%d)
```
- [ ] Backup strategy defined
- [ ] First backup completed
- [ ] Backup location documented

### Backup MongoDB Data
```bash
# Backup via MongoDB Atlas UI
# Or via CLI if self-hosted:
mongodump --uri "mongodb+srv://..." --out ./backup/
```
- [ ] MongoDB backup procedure documented
- [ ] Regular backup schedule set

---

## Access & Documentation

### Update Dashboard Frontend
```bash
# Update API endpoint in your frontend
const API_URL = "http://<VM_PUBLIC_IP>:5000";
// or
const API_URL = "https://your-domain.com";
```
- [ ] Frontend API URL updated
- [ ] Frontend tested with new endpoint
- [ ] Dashboard displays data correctly

### Document Access
- [ ] API Endpoint: `http://<VM_PUBLIC_IP>:5000` or `https://your-domain.com`
- [ ] SSH Command: `ssh -i /path/to/key azureuser@<VM_IP>`
- [ ] Service Control: `sudo systemctl [start|stop|restart] emergency-detection`
- [ ] Logs: `sudo journalctl -u emergency-detection -f`
- [ ] MongoDB Connection: `mongodb+srv://...`

### Share with Team
- [ ] Documentation uploaded to shared location
- [ ] Team has access to VM (via SSH key)
- [ ] Alert procedures documented
- [ ] Escalation contacts defined

---

## Post-Deployment

### Performance Monitoring
```bash
# Monitor CPU/Memory
top
# or
ps aux | grep main.py

# Check connections
netstat -tulpn | grep 5000
```
- [ ] Performance baseline established
- [ ] Monitoring tools installed (optional: Prometheus, Grafana)

### Scaling (If Needed)
- [ ] [ ] Consider upgrading VM size if CPU > 80%
- [ ] [ ] Add Azure Load Balancer for multiple VMs
- [ ] [ ] Use Azure Container Instances for auto-scaling
- [ ] [ ] Setup Azure App Service as alternative

### Security Review
- [ ] [ ] SSH keys secured (not shared)
- [ ] [ ] MongoDB URI not in public repos
- [ ] [ ] Firewall rules restricted (only needed ports)
- [ ] [ ] Consider Azure Bastion for SSH access
- [ ] [ ] Enable VM monitoring and alerts

---

## Troubleshooting Reference

| Issue | Solution |
|-------|----------|
| Permission denied (SSH) | Check key permissions: `chmod 600 /path/to/key` |
| Connection timeout | Check Network Security Group rules; add your IP |
| Flask not starting | Check logs: `python main.py` (run directly to see errors) |
| MongoDB error | Verify .env MONGO_URI; check Atlas whitelist |
| Port 5000 in use | `sudo lsof -i :5000` and kill process |
| High memory usage | Check if threads are leaking; restart service |
| Disk full | Clean `/uploads`: `rm -rf uploads/*` |

---

## Final Verification Checklist

- [ ] VM created and running
- [ ] SSH access verified
- [ ] Project deployed successfully
- [ ] Dependencies installed
- [ ] Configuration files set (.env, config.py)
- [ ] Application starts without errors
- [ ] API endpoints responding
- [ ] MongoDB connected
- [ ] Systemd service active
- [ ] Nginx configured (production)
- [ ] Public IP accessible
- [ ] Video upload working
- [ ] Logs monitoring working
- [ ] Backups scheduled
- [ ] Team trained on access
- [ ] Documentation shared

---

## Cost Estimate (Monthly)

| Component | SKU | Est. Cost |
|-----------|-----|-----------|
| VM Compute | Standard_B2s | $30-40 |
| Storage | 128GB managed disk | $5-10 |
| Public IP | Static IP | $2-5 |
| Bandwidth | Outbound egress | $5-20 |
| **Total** | | **$50-75/month** |

*Note: Prices vary by region. Use [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/)*

---

## Support & Escalation

For issues:
1. Check logs: `sudo journalctl -u emergency-detection -f`
2. Test API: `curl http://localhost:5000/api/status`
3. Restart service: `sudo systemctl restart emergency-detection`
4. Review AZURE_DEPLOYMENT.md troubleshooting section
5. Contact: [Your team contact info]

