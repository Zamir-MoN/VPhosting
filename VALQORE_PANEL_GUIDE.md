# ⚡ Valqore Hosting — Complete Technical Reference & Setup Guide

This document contains full documentation for the **Valqore Hosting Minecraft Game Panel**, including architecture, deployment instructions, features, API reference, and troubleshooting steps.

---

## 📌 Project Overview

- **Repository**: [https://github.com/Zamir-MoN/VPhosting.git](https://github.com/Zamir-MoN/VPhosting.git)
- **Default Branch**: `main`
- **Application Stack**:
  - **Backend**: Python 3.12+ with FastAPI & Uvicorn (managed via `systemd`).
  - **Frontend**: Vanilla ES6+ JavaScript, Responsive CSS3 Grid/Flexbox, Lucide Icons, GSAP Animations.
  - **Game Engine**: Purpur / Paper / Fabric / Forge / NeoForge / Vanilla (Port `25565`).
  - **Web Dashboard**: Port `8090` (Direct or proxied via Nginx).
  - **Video Engine**: Seamless Enchanted Sword live background wallpaper (`static/bg-video.mp4`).

---

## 🚀 Quick Deployment & Server Updates

Whenever you make changes or want to sync the latest version to your VPS:

```bash
# 1. Navigate to the project directory
cd /home/ubuntu/valqore

# 2. Pull the latest code from GitHub
git pull origin main

# 3. Restart the panel background service
sudo systemctl restart valqore

# 4. Check service status to ensure everything is running cleanly
sudo systemctl status valqore
```

---

## ⚙️ Initial VPS Setup Instructions

### 1. System Requirements & Dependencies

```bash
# Update Ubuntu package index
sudo apt update && sudo apt upgrade -y

# Install Python3, pip, venv, and Java 21 (required for Minecraft 1.20.5+)
sudo apt install -y python3 python3-pip python3-venv openjdk-21-jre-headless git tmux curl
```

### 2. Clone and Setup Environment

```bash
# Clone the repository into your home directory
cd /home/ubuntu
git clone https://github.com/Zamir-MoN/VPhosting.git valqore
cd /home/ubuntu/valqore

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required Python packages
pip install --upgrade pip
pip install fastapi uvicorn requests psutil mcrcon google-auth google-auth-oauthlib google-api-python-client
```

### 3. Setup Systemd Service (`valqore.service`)

Create the service file:
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

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable valqore
sudo systemctl start valqore
```

### 4. Firewall & Port Access (AWS Security Group / UFW)

Ensure the following inbound rules are open in your **AWS EC2 Security Group** and **UFW**:
- **Port 22 (TCP)**: SSH Access.
- **Port 8090 (TCP)**: Valqore Web Management Panel.
- **Port 25565 (TCP/UDP)**: Minecraft Game Server Default Port.

---

## 🎨 Features & System Architecture

### 1. Dashboard & Power Lifecycle
- **Real-Time Live Server Ping Meter**: Direct `/api/ping` probe calculating round-trip millisecond latency.
- **Hardware Telemetry**: Real-time VPS RAM usage (MB and %), CPU load, Core count, and Disk storage.
- **Session-Aware Process Management**: `START`, `STOP`, and `RESTART` buttons protected by process state verification to avoid false online notifications.
- **Live Terminal Stream**: Real-time console logs with auto-scroll and command input.

### 2. Plugin Marketplace (Modrinth + SpigotMC Multi-Index)
- **Live Debounced Search**: Searches as you type with intelligent keyword tokenization.
- **Typo Tolerance**: Auto-corrects common typos (e.g. `vioce` → `voice`, `luckperm` → `luckperms`, `drivebackup` → `drivebackupv2`).
- **Smart Version Matching**: Detects active server version (e.g. `1.21.1`) and automatically downloads compatible plugin release builds.
- **Installed Plugins Manager**: View, count, and remove installed `.jar` files with 1 click.

### 3. File Manager & Asset Explorer
- **Multi-File Drag & Drop**: Full-page glowing dropzone supporting simultaneous multi-file parallel uploads.
- **Interactive Breadcrumb Navigation**: Path trail (e.g. `/root / plugins`) with clickable directory jumps.
- **Header Back Button**: Dedicated `← Back` button when inside subdirectories.
- **Integrated Code Editor**: Edit configuration files (`server.properties`, `bukkit.yml`, `.yml`, `.json`, `.txt`) directly from the browser.

### 4. Software & Engine Installer
- One-click deployment for:
  - **Vanilla** (Official Mojang Server)
  - **PaperMC** (High-Performance Plugin Engine)
  - **Fabric** (Lightweight Modern Modding)
  - **Forge** (Classic Modpack Ecosystem)
  - **NeoForge** (Next-Gen Modding Engine)

### 5. Player & World Management
- **Live Player Roster**: Tracks connected players from log events without console command spam.
- **Player Actions**: Kick, ban, op, and gamemode controls.
- **World Management**: Upload world `.zip` archives or trigger clean world regeneration.

---

## 🛠️ API Endpoints Summary

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/ping` | `GET` | Ultra-fast network latency probe |
| `/api/stats` | `GET` | Telemetry (RAM, CPU, Disk, Online players, Power state) |
| `/api/start` | `POST` | Boot Minecraft server with optimized Aikar JVM flags |
| `/api/stop` | `POST` | Safely shutdown engine and clean up process locks |
| `/api/restart` | `POST` | Controlled stop-and-start reboot sequence |
| `/api/console` | `GET` | Tail console output from `latest.log` |
| `/api/command` | `POST` | Send command to the Minecraft server console |
| `/api/plugins/search` | `GET` | Multi-index plugin search (Modrinth + Spigot) |
| `/api/plugins/install` | `POST` | Version-matched 1-click plugin downloader |
| `/api/plugins/installed`| `GET` | List all active plugins in `/mc_server/plugins/` |
| `/api/files/list` | `GET` | File and directory browser |
| `/api/files/upload` | `POST` | Multi-file uploader |
| `/api/files/delete` | `POST` | File deletion endpoint |

---

## 🔒 Security Best Practices

1. **RCON Protection**: Keep RCON port closed to external traffic; only allow loopback `127.0.0.1`.
2. **Path Traversal Guards**: The backend validates all file operations within `/home/ubuntu/valqore/mc_server` using `get_safe_path()`.
3. **Session Lock Cleanup**: Automatically clears `session.lock` files during crashes to prevent world corruption.
