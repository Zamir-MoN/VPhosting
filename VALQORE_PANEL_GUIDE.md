# ⚡ Valqore Hosting — Quick Start Guide

A simple, user-friendly guide to set up and manage your Valqore Minecraft Panel in seconds.

---

## 🚀 1. Setup in 1-Click (Fresh VPS)

Connect to your VPS terminal via SSH and run this **single command**:

```bash
curl -sSL https://raw.githubusercontent.com/Zamir-MoN/VPhosting/main/install.sh | sudo bash
```

---

## 🌐 2. Access Your Dashboard

1. Open your browser and go to: **`http://YOUR_VPS_IP:8090`**
2. **Install Server**: Go to the **INSTALLER** tab, choose **Paper** or **Purpur** (1.21.1), and click **Install**.
3. **Start Playing**: Go back to the **DASHBOARD** tab and click **START**!
4. **Join in Minecraft**: Connect using: **`YOUR_VPS_IP:25565`**

---

## 📋 3. Tabs Overview

* **📊 Dashboard**: View live RAM/CPU usage, Start/Stop/Restart the server, and send live console commands.
* **📁 Files**: Edit `server.properties` and other config files directly in your browser.
* **🧩 Plugins**: Search and install plugins in 1 click from Modrinth & Spigot.
* **⚙️ Installer**: Change your Minecraft version or engine anytime (Paper, Purpur, Fabric, Forge).
* **👥 Players**: See who is online, grant OP, change gamemodes, or ban/unban players.
* **🌍 Worlds**: Upload a custom world `.zip` or regenerate a fresh world.
* **☁️ Backups**: Connect Google Drive for automatic world backups.

---

## 🔄 4. Quick Daily Commands

| Task | Command |
| :--- | :--- |
| **Update Panel** | `cd /home/ubuntu/valqore && git pull origin main && sudo systemctl restart valqore` |
| **Restart Panel** | `sudo systemctl restart valqore` |
| **View Live Logs** | `sudo journalctl -u valqore -f` |
| **Check Status** | `sudo systemctl status valqore` |

*(If using `root`, replace `/home/ubuntu/valqore` with `/root/valqore`)*.
