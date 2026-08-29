# 🚀 Valqore Hosting Panel — Complete Management & VPS Guide

Welcome to the comprehensive reference guide for **Valqore Hosting**, a modern, high-performance Minecraft Server Management Engine with automated 1-line deployment, live resource telemetry, real-time interactive terminal, automated Google Drive cloud backups, multi-engine marketplace, and granular player controls.

---

## ⚡ 1-Line Super-Fast VPS Deployment

To install and run Valqore Hosting on any **fresh Ubuntu (20.04/22.04/24.04) or Debian (11/12) VPS**, connect via SSH and run:

```bash
curl -sSL https://raw.githubusercontent.com/Zamir-MoN/VPhosting/main/install.sh | sudo bash
```

### 🛡️ Open Required Firewall Ports
Run this command block on your VPS to ensure all panel and game ports are open:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8090/tcp
sudo ufw allow 25565/tcp
sudo ufw allow 25565/udp
sudo ufw allow 19132/udp
sudo ufw allow 24454/udp
sudo ufw --force enable
```

---

## 🌐 Port Mapping & Cloud Firewall Reference

Ensure the following inbound rules are permitted in your Cloud Provider's console (AWS Security Groups, Oracle Cloud VCN, DigitalOcean Firewall, Hetzner, etc.):

| Port | Protocol | Service | Description |
| :--- | :---: | :--- | :--- |
| **`22`** | TCP | SSH Terminal | Remote command-line administration |
| **`8090`** | TCP | Web Dashboard | Access Valqore Panel (`http://YOUR_VPS_IP:8090`) |
| **`25565`** | TCP & UDP | Minecraft Java | Default Minecraft Java game server connection |
| **`19132`** | UDP | GeyserMC / Bedrock | Crossplay for Mobile (iOS/Android), Xbox, PlayStation, Switch |
| **`24454`** | UDP | Simple Voice Chat | In-game proximity voice communication |
| **`8123`** | TCP | BlueMap / Dynmap | Optional browser-based 3D live world map |

---

## 🖥️ Panel Features & Tab-by-Tab Walkthrough

### 1. 📊 Dashboard Tab
* **Live Server Telemetry**:
  * **SERVER RAM**: Process-level RSS telemetry vs. allocated Java memory (`-Xmx10240M`). Displays `0 / 10240 MB` when stopped.
  * **SERVER CPU**: Accurate multi-core normalized CPU utilization percentage.
  * **PLAYERS**: Current live connected players vs. server capacity (e.g. `0/50`).
  * **SERVER PING**: Real-time network latency and connection health indicator.
* **Power Management**:
  * **START**: Boots the Minecraft engine inside a dedicated, detached `tmux` session with Aikar G1GC flags.
  * **STOP**: Gracefully executes `/stop`, saves world data, and forcefully terminates any lingering Java worker threads.
  * **RESTART**: Safely cycles the server process with automated cleanup of stale `session.lock` files.
* **Interactive Terminal**:
  * Real-time console logs streamed from `latest.log`.
  * Send live commands (`op`, `gamemode`, `give`, `whitelist`, etc.) directly into the console.

---

### 2. 📁 Files Tab
* **Web-Based File Explorer**:
  * Navigate folders with breadcrumbs and top **`← BACK`** button.
  * In-browser code and config editor for `server.properties`, `start.sh`, `bukkit.yml`, `paper-global.yml`, etc.
  * Upload, download, and delete server files and configs with 1 click.

---

### 3. 🧩 Plugins Tab
* **Integrated Modrinth & Spiget Marketplace**:
  * Search thousands of plugins directly from the dashboard.
  * 1-Click automatic installation directly into the `/mc_server/plugins/` directory.
  * Automatic Minecraft version compatibility matching.

---

### 4. ⚙️ Installer Tab
* **Multi-Engine Universal Installer**:
  * **Purpur**: High-performance Paper fork with extensive gameplay customization.
  * **PaperMC**: The gold standard for performance, stability, and plugin support.
  * **Fabric**: Lightweight, bleeding-edge mod loader for modern Minecraft versions.
  * **Forge / NeoForge**: Heavy modpack compatibility.
  * **Vanilla**: Official Mojang release binaries.

---

### 5. 👥 Players Tab
* **Player Management & Roles**:
  * **Online Now**: Real-time list of connected players.
  * **Player History**: Cached log of all past visitors.
  * **Operator Control**: Dynamic **`★ OP (Active)`** button with purple glow.
  * **Ban Control**: Dynamic **`Ban / Unban`** toggle with red glow.
  * **Gamemode Switcher**: Instant switching between **Survival**, **Creative**, and **Spectator** modes.
  * **Kill Action**: Instant player reset command.

---

### 6. 🌍 Worlds Tab
* **World Management**:
  * **Regenerate World**: Safely wipe and re-seed the Overworld, Nether, and End dimensions.
  * **Upload Custom World**: Upload a `.zip` file of any custom map (e.g., custom spawn or adventure map) with automatic extraction.

---

### 7. ☁️ Backups Tab
* **Google Drive Automated Cloud Sync**:
  * Link Google Drive using OAuth 2.0 (`client_secrets.json`).
  * Automated cloud backups scheduled periodically.
  * Manual 1-click cloud snapshot generation.

---

## 🔄 Daily VPS Maintenance & Admin Commands

```bash
# 1. Update the panel to latest version from GitHub
cd /home/ubuntu/valqore
git pull origin main
sudo systemctl restart valqore

# 2. Check panel background service status
sudo systemctl status valqore

# 3. View live background system logs
sudo journalctl -u valqore -f

# 4. Restart panel service
sudo systemctl restart valqore

# 5. Stop panel service
sudo systemctl stop valqore
```

*(Note: If logged in as `root`, replace `/home/ubuntu/valqore` with `/root/valqore`)*.

---

## 🎮 Recommended Settings for 50 Players

To maintain **20.0 TPS** with 50 concurrent players:
1. **Engine**: Install **Purpur** or **Paper** from the **INSTALLER** tab.
2. **RAM**: Configured at **10 GB (10240 MB)** with Aikar G1GC flags.
3. **`server.properties`** (in **FILES** tab):
   ```properties
   view-distance=6
   simulation-distance=4
   max-players=50
   network-compression-threshold=256
   ```
4. **Pre-generation**: Install the `Chunky` plugin from the **PLUGINS** tab and run `/chunky radius 5000` then `/chunky start`.
