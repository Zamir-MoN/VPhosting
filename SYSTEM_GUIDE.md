# 🤖 Valqore Hosting & Discord Bot — Complete System Documentation

Comprehensive guide for deploying, configuring, and managing the Valqore Minecraft Hosting Web Dashboard and Discord Bot.

---

## 📑 Table of Contents
1. [Architecture Overview](#-architecture-overview)
2. [VPS & System Setup](#-vps--system-setup)
3. [Discord Bot Configuration](#-discord-bot-configuration)
4. [Control Panel & UI Features](#-control-panel--ui-features)
5. [Whitelist Management](#-whitelist-management)
6. [World Backups](#-world-backups)
7. [Player Roster & Permissions](#-player-roster--permissions)
8. [Commands & Shortcuts Reference](#-commands--shortcuts-reference)
9. [Troubleshooting & FAQs](#-troubleshooting--faqs)

---

## 🏗️ Architecture Overview

The system consists of two tightly integrated components running on your VPS:
- **FastAPI Web Panel (`main.py`)**: Runs on port `8090`, provides web dashboard, live file management, plugin installer, metrics tracking, and API endpoints.
- **Discord Bot (`discord_bot.py`)**: Real-time Discord interface that communicates with the local FastAPI backend and direct native processes (tmux/Java) with zero lag.

---

## 🖥️ VPS & System Setup

### Prerequisites
- Ubuntu 22.04+ LTS (or Debian-based Linux)
- Java 21+ (`openjdk-21-jre-headless`)
- Python 3.10+ with `virtualenv`
- `tmux`, `git`, `curl`

### Installation Commands
```bash
# Clone the repository
git clone https://github.com/Zamir-MoN/VPhosting.git ~/valqore
cd ~/valqore

# Run the automated installer
chmod +x install.sh
./install.sh
```

### Managing System Services
```bash
# Web Dashboard Panel Service
sudo systemctl status valqore-panel
sudo systemctl restart valqore-panel

# Discord Bot Service
sudo systemctl status valqore-bot
sudo systemctl restart valqore-bot
```

### Updating to Latest Version
```bash
cd ~/valqore
git pull origin main
sudo systemctl restart valqore-panel valqore-bot
```

---

## 🤖 Discord Bot Configuration

### 1. Create Your Application on Discord
1. Visit the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a **New Application** (e.g. `Valqore MC Hosting`).
3. Under the **Bot** tab:
   - Click **Add Bot**.
   - Enable **Message Content Intent** (under Privileged Gateway Intents).
   - Copy your **Bot Token**.
4. Under **OAuth2 > URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Administrator`
   - Copy and open the URL to invite the bot to your Discord server.

### 2. Connect Bot to Your Hosting Panel
In your Discord server:
1. Type `/setupmc` (or `!setupmc`).
2. A secure modal will appear asking for your **6-Digit Web Panel Verification Code**.
3. Enter your code (found in your Web Panel Dashboard).
4. Type `/panel` (or `!panel`) to spawn the live interactive control panel.

---

## 🎛️ Control Panel & UI Features

### Main Control Row
```
[🟢 Start]  [🛑 Stop]  [🔁 Restart]  [📥]  [⚙️ More]
```

- **🟢 Start**: Boot up the Minecraft server with real-time progress animations (JVM initialization, world chunk loading).
- **🛑 Stop**: Safely broadcast shutdown, save player data and world chunks.
- **🔁 Restart**: Smooth two-phase restart (clean stop -> JVM reboot).
- **📥 Download Backup**: Instant 1-click world backup download.
- **⚙️ More**: Opens the secondary actions menu.

---

## 🛡️ Whitelist Management

Access the whitelist system from **⚙️ More** -> **🛡️ Whitelist**:

### Features
1. **Whitelist ON / OFF Toggle**:
   - `Whitelist: ON ✓` (Green): Server actively rejects non-whitelisted connections. Automatically synchronizes `server.properties` (`white-list=true` and `enforce-whitelist=true`) and executes `/whitelist on` + `/whitelist reload`.
   - `Whitelist: OFF` (Gray): Server is open to all players (`white-list=false`).
2. **➕ Add Member**:
   - Opens a modal where you type any Minecraft player's username.
   - Automatically generates offline player UUID hashes and updates `whitelist.json` + runs `/whitelist add <player>`.
3. **Remove Member Dropdown**:
   - Select any whitelisted player from the dropdown to remove them and instantly reload server permissions.

> [!NOTE]
> Server Operators (OPs) have permission to bypass the whitelist by default in Minecraft. To test whitelist enforcement on yourself, remove OP status first.

---

## 📦 World Backups

### How it works:
1. Click the **📥** button on the main Discord panel.
2. The bot archives `mc_server/world`, `mc_server/world_nether`, and `mc_server/world_the_end` into a compressed `.zip` file.
3. **Delivery**:
   - **Files ≤ 24 MB**: Uploaded directly to your Discord chat for 1-click local download.
   - **Files > 24 MB**: Bot generates a direct local web download URL (`http://<server-ip>:8090/api/backup/manual`).

---

## 👥 Player Roster & Permissions

Access the player management menu via **⚙️ More** -> **👥 Players**:

### Live Features:
- **Gamemode Switcher**: Instant buttons for `Survival ✓`, `Creative`, `Spectator`, and `Adventure` with green active highlight.
- **OP / DE-OP Toggle**: Toggle server operator rank with `👑 Make Operator (OP)` or `⛔ Remove OP (DE-OP)`.
- **Ban & Unban**:
   - `🔨 Ban Player`: Executes permanent console ban.
   - `🔓 Unban Player`: Executes console `/pardon` to restore player access.

---

## 📋 Commands & Shortcuts Reference

| Command | Type | Description |
|---|---|---|
| `/setupmc` | Slash | Opens 6-digit verification modal to bind your Discord bot to the host |
| `/panel` | Slash | Spawns the permanent interactive live control panel |
| `!setupmc` | Prefix | Text command fallback for verification |
| `!panel` | Prefix | Text command fallback for panel deployment |

---

## ❓ Troubleshooting & FAQs

### 1. Server says offline but it is running?
The bot checks both the web panel status and performs a direct TCP port check on `25565`. Make sure port `25565` is open in your VPS firewall / security group.

### 2. Backup upload fails?
If your world archive is larger than 25MB, Discord's file upload limit applies. The bot will automatically give you a direct web link to download the zip file from port `8090`.

### 3. Non-whitelisted players can still join?
1. Make sure the player is not an OP (Operators bypass whitelists).
2. Ensure `Whitelist: ON ✓` is active on the Discord panel.
