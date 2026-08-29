# 🚀 Complete Fresh VPS Setup Guide — Valqore Hosting Panel

This step-by-step guide walks you through setting up a **brand new, fresh Ubuntu VPS** (such as AWS EC2, DigitalOcean, Linode, Hetzner, or Oracle Cloud) to run the **Valqore Hosting Minecraft Panel** 24/7.

---

## 📋 Prerequisites & Required Ports

Before you begin, ensure the following inbound ports are allowed in your **Cloud Firewall / Security Group**:

| Port | Protocol | Purpose |
| :--- | :---: | :--- |
| **22** | TCP | SSH Terminal Access |
| **8090** | TCP | Valqore Web Management Panel |
| **25565** | TCP & UDP | Minecraft Game Server Default Port |

---

## ⚡ Step-by-Step Installation

### Step 1: Connect to Your New VPS

Open your terminal (PowerShell, Command Prompt, or PuTTY) and connect via SSH:

```bash
ssh ubuntu@YOUR_VPS_IP
```
*(Replace `YOUR_VPS_IP` with your actual VPS IP address)*

---

### Step 2: Update System Packages & Install Dependencies

Run the following command to install **Python 3, Virtualenv, Git, Tmux, and Java 21** (required for Minecraft 1.20.5+):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv openjdk-21-jre-headless git tmux curl
```

Verify Java 21 is installed:
```bash
java -version
```

---

### Step 3: Clone the Valqore Hosting Repository

Clone the project directly into your home folder:

```bash
cd /home/ubuntu
git clone https://github.com/Zamir-MoN/VPhosting.git valqore
cd /home/ubuntu/valqore
```

---

### Step 4: Create Virtual Environment & Install Python Packages

```bash
# Create isolated Python virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip and install all backend requirements
pip install --upgrade pip
pip install fastapi uvicorn requests psutil mcrcon google-auth google-auth-oauthlib google-api-python-client
```

---

### Step 5: Configure the 24/7 System Background Service

Create a `systemd` service so the panel runs 24/7 in the background and restarts automatically on server boot:

```bash
sudo nano /etc/systemd/system/valqore.service
```

Paste the following configuration:

```ini
[Unit]
Description=Valqore Hosting Minecraft Panel Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/valqore
ExecStart=/home/ubuntu/valqore/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8090
Restart=always
RestartSec=5
Environment=PATH=/usr/bin:/bin:/usr/local/bin:/home/ubuntu/valqore/venv/bin

[Install]
WantedBy=multi-user.target
```

*Save and exit in nano:* Press `Ctrl + O`, then `Enter`, then `Ctrl + X`.

---

### Step 6: Enable and Start the Service

```bash
# Reload systemd daemon
sudo systemctl daemon-reload

# Enable service to start on system boot
sudo systemctl enable valqore

# Start the service now
sudo systemctl start valqore

# Check the status (should show 'active (running)')
sudo systemctl status valqore
```

---

### Step 7: (Optional) Configure Local Firewall (UFW)

If your VPS uses Ubuntu's built-in `ufw` firewall:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8090/tcp
sudo ufw allow 25565/tcp
sudo ufw allow 25565/udp
sudo ufw --force enable
```

---

## 🌐 Accessing Your Dashboard

Open your web browser and navigate to:

```text
http://YOUR_VPS_IP:8090
```

1. Go to the **INSTALLER** tab.
2. Select your desired engine (**PaperMC, Purpur, Fabric, Forge, or Vanilla**).
3. Select your version (e.g. **1.21.1**) and click **Install**.
4. Return to the **DASHBOARD** and click **START**!
5. Join your server in Minecraft using: `YOUR_VPS_IP:25565`.

---

## 🔄 Useful Daily Maintenance Commands

```bash
# Update the panel to the latest code from GitHub
cd /home/ubuntu/valqore
git pull origin main
sudo systemctl restart valqore

# View real-time panel system logs
sudo journalctl -u valqore -f

# Restart the panel service
sudo systemctl restart valqore

# Stop the panel service
sudo systemctl stop valqore
```
