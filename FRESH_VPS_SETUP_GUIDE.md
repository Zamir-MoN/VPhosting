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

## ⚡ 1-Line Super-Fast Automated Setup (Recommended)

Just run this **single command** on your fresh Ubuntu/Debian VPS terminal:

```bash
curl -sSL https://raw.githubusercontent.com/Zamir-MoN/VPhosting/main/install.sh | sudo bash
```

> **What this does automatically in under 60 seconds:**
> 1. Updates Ubuntu packages & installs Java 21, Python 3, Git, and Tmux.
> 2. Clones the repository & configures the Python virtual environment.
> 3. Creates and starts the 24/7 background system service (`valqore.service`).
> 4. Configures UFW firewall rules for Ports `8090` and `25565`.
> 5. Detects your public IP and prints your ready-to-use dashboard link!

---

## 🛠️ Alternative: Manual Step-by-Step Installation

If you prefer to configure everything manually step-by-step:

### Step 1: Connect to Your New VPS
```bash
ssh ubuntu@YOUR_VPS_IP
```

### Step 2: Update System & Install Java 21 + Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv openjdk-21-jre-headless git tmux curl
```

### Step 3: Clone the Repository
```bash
cd /home/ubuntu
git clone https://github.com/Zamir-MoN/VPhosting.git valqore
cd /home/ubuntu/valqore
```

### Step 4: Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Configure 24/7 System Background Service
```bash
sudo bash -c 'cat <<EOF > /etc/systemd/system/valqore.service
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
EOF'
```

### Step 6: Enable and Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable valqore
sudo systemctl start valqore
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
