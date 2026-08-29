# ⚡ Valqore Hosting — Setup & Usage Guide

### 🚀 1. Install on Fresh VPS (1-Line Command)
```bash
curl -sSL https://raw.githubusercontent.com/Zamir-MoN/VPhosting/main/install.sh | sudo bash
```

### 🔓 Ports to Open in Cloud Firewall
* `22` (TCP) — SSH
* `8090` (TCP) — Web Panel Dashboard
* `25565` (TCP/UDP) — Minecraft Server
* `19132` (UDP) — Bedrock / PE Crossplay *(Optional)*
* `24454` (UDP) — Voice Chat *(Optional)*

---

### 🌐 2. Access Dashboard & Start Playing
1. Open browser: `http://YOUR_VPS_IP:8090`
2. **Installer Tab**: Pick **Paper** or **Purpur** (1.21.1) & click **Install**.
3. **Dashboard Tab**: Click **START**!
4. **Join in Minecraft**: `YOUR_VPS_IP:25565`

---

### 📋 3. Panel Features
* **Dashboard**: Live RAM (10GB) / CPU stats, console & Power controls.
* **Files**: Browser file manager & config editor.
* **Plugins**: 1-Click install from Modrinth & Spigot.
* **Installer**: Switch between Paper, Purpur, Fabric & Forge.
* **Players**: Live player list, OP, Gamemodes & Bans.
* **Worlds**: Upload custom world `.zip` or regenerate.
* **Backups**: Automated Google Drive cloud sync.

---

### 🔄 4. Quick VPS Commands
* **Update Panel**: `cd /home/ubuntu/valqore && git pull origin main && sudo systemctl restart valqore`
* **Restart Panel**: `sudo systemctl restart valqore`
* **Live Logs**: `sudo journalctl -u valqore -f`
