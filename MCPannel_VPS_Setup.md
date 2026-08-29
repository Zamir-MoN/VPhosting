# Valqore Hosting VPS Setup Guide

This guide provides step-by-step instructions for deploying **Valqore Hosting Control Panel** on a Linux-based Virtual Private Server (VPS) such as Ubuntu 20.04/22.04/24.04 or Debian.

## 1. Initial Server Preparation

First, update your system packages and install necessary utilities, including Java (required for Minecraft), Python, and Tmux:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv tmux curl git openjdk-21-jre-headless -y
```

## 2. Clone the Project Repository

Clone your repository into `/var/opt/valqore`:

```bash
sudo mkdir -p /var/opt/valqore
sudo chown -R $USER:$USER /var/opt/valqore
cd /var/opt/valqore

# Clone your repository
git clone https://github.com/Zamir-MoN/VPhosting.git .
```

## 3. Python Environment & Dependencies

Create a virtual environment and install the Python requirements:

```bash
cd /var/opt/mcpannel

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install the required packages
pip install -r requirements.txt
```

## 4. Google Drive Backup Configuration (Optional)

If you plan to use the automated Google Drive backup feature, you must upload your `client_secrets.json` file to the root of the project folder (`/var/opt/mcpannel/client_secrets.json`).
*Note: The callback URL in `main.py` is hardcoded to `http://localhost:8090/api/gdrive/callback`. To authenticate on a VPS, you may need to forward port 8090 via SSH to your local machine (`ssh -L 8090:localhost:8090 user@vps_ip`) during the initial setup.*

## 5. Minecraft Server Preparation

The panel can automatically install server software (Paper, Fabric, Vanilla, Forge, NeoForge) via the web interface. However, ensure the directory exists:

```bash
mkdir -p mc_server
```

*Note: The panel uses Tmux for console interactions (`tmux send-keys`), meaning RCON is actually not strictly required for command execution, but the code still contains some RCON configurations.*

## 6. Run as a Systemd Service (Production Recommended)

To ensure the FastAPI panel runs continuously and starts on boot, create a Systemd service file.

```bash
sudo nano /etc/systemd/system/mcpannel.service
```

Add the following configuration (adjust `User` and `WorkingDirectory` if needed):

```ini
[Unit]
Description=MCPannel FastAPI Service
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/var/opt/mcpannel
Environment="PATH=/var/opt/mcpannel/venv/bin"
# The app runs on port 8090 natively as defined in main.py
ExecStart=/var/opt/mcpannel/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8090
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mcpannel
sudo systemctl start mcpannel
```

## 7. Setup Nginx Reverse Proxy (Optional)

If you want to access the panel via standard HTTP/HTTPS ports or a domain name, configure Nginx.

```bash
sudo apt install nginx -y
sudo nano /etc/nginx/sites-available/mcpannel
```

Add the following config:

```nginx
server {
    listen 80;
    server_name yourdomain.com; # Replace with your domain or IP

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable the configuration:

```bash
sudo ln -s /etc/nginx/sites-available/mcpannel /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

## 8. Firewall Configuration (UFW)

You need to open ports for the Web Panel and the Minecraft server.

```bash
# Allow SSH
sudo ufw allow OpenSSH

# Allow Minecraft Server Default Port
sudo ufw allow 25565/tcp
sudo ufw allow 25565/udp

# Allow Nginx / HTTP (if using reverse proxy)
sudo ufw allow 'Nginx Full'

# OR Allow port 8090 directly if not using Nginx
# sudo ufw allow 8090/tcp

sudo ufw enable
```
