# Deployment Guide for VM

## Changes Made for VM Deployment

### 1. Port Configuration
- **Changed port from 8000 to 6000**
  - Updated in `app.py` (line 235)
  - Updated in `start_server.sh` (line 13-14)

### 2. Path Configuration
- **Converted absolute paths to relative paths**
  - `CHROMA_DB_DIR` now uses `PROJECT_ROOT/chroma_db`
  - `TEMP_PROCESSING_DIR` now uses `BASE_DIR/temp_processing`
  - This ensures the application works regardless of installation directory

### 3. Network Access
- **Already configured for external access**
  - Server binds to `0.0.0.0` (all interfaces)
  - Frontend uses relative URLs for API calls
  - Works correctly when accessed via VM IP

## Deployment Steps

### 1. Copy files to VM
```bash
# Transfer the entire ea_tool directory to your VM
scp -r /Users/rudraksh.k/Documents/tool_development/ea_tool user@vm_ip:/path/to/destination/
```

### 2. Install Dependencies on VM
```bash
cd /path/to/ea_tool
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Ensure Required Directories Exist
```bash
# The app will auto-create temp_processing, but ensure chroma_db is present
cd /path/to/ea_tool
ls -la chroma_db/  # Verify this directory exists with your embeddings database
```

### 4. Start the Server
```bash
cd duplicate_detection_tool
bash start_server.sh
```

Or run directly:
```bash
cd duplicate_detection_tool
python app.py
```

### 5. Access from Global Network
The tool will be accessible at:
```
http://[VM_IP]:6000
```

For example:
```
http://192.168.1.100:6000
http://10.0.0.50:6000
```

## Firewall Configuration

Make sure port 6000 is open on your VM firewall:

### For UFW (Ubuntu/Debian):
```bash
sudo ufw allow 6000/tcp
sudo ufw reload
```

### For firewalld (CentOS/RHEL):
```bash
sudo firewall-cmd --permanent --add-port=6000/tcp
sudo firewall-cmd --reload
```

### For iptables:
```bash
sudo iptables -A INPUT -p tcp --dport 6000 -j ACCEPT
sudo service iptables save
```

## Running as a Service (Optional)

To keep the application running in the background, consider using systemd:

### Create systemd service file:
```bash
sudo nano /etc/systemd/system/duplicate-detection.service
```

### Add the following content:
```ini
[Unit]
Description=JIRA Duplicate Detection Tool
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/ea_tool/duplicate_detection_tool
Environment="PATH=/path/to/ea_tool/venv/bin"
ExecStart=/path/to/ea_tool/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable duplicate-detection.service
sudo systemctl start duplicate-detection.service
sudo systemctl status duplicate-detection.service
```

## Health Check

Test if the service is running:
```bash
curl http://localhost:6000/health
```

From external network:
```bash
curl http://[VM_IP]:6000/health
```

Expected response:
```json
{"status": "healthy", "service": "duplicate_detection"}
```

## Troubleshooting

### Cannot access from external network:
1. Verify firewall allows port 6000
2. Check if VM has a public IP or is behind NAT
3. Verify server is binding to 0.0.0.0: `netstat -tulpn | grep 6000`

### Application won't start:
1. Check Python version: `python --version` (requires Python 3.8+)
2. Verify all dependencies installed: `pip list`
3. Check logs for errors in console output
4. Ensure chroma_db directory exists and is readable

### API calls failing:
1. Check JIRA credentials in `app.py` are still valid
2. Verify network connectivity from VM to JIRA server
3. Check application logs for detailed error messages

