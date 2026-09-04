# 🤖 Valqore Discord Bot — Setup & Usage Guide

The Discord Bot allows server administrators to manage the Minecraft server directly from Discord using intuitive Slash Commands and an interactive pinned button panel.

---

## ✨ Features

- 🎮 **Server Controls**: Start, Stop, and Restart Minecraft directly with 1-click buttons or commands.
- 📊 **Real-Time Stats**: RAM usage, CPU load, and disk space monitoring.
- 👥 **Live Player Tracking**: View online players, capacity, and active presence status on Discord.
- 💻 **Full Console Access**: Run any Minecraft server command (e.g. `/op`, `/ban`, `/gamemode`, `/give`, `/whitelist`, `/say`) and inspect the latest console output logs.
- 📌 **Interactive Pinned Panel**: Post a live dashboard card with buttons in any Discord channel using `/panel`.
- 🏓 **Bot & Server Ping**: Instant status and latency checks.

---

## 🚀 Quick Setup

### 1. Create a Discord Bot
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** and give it a name (e.g., `Valqore Bot`).
3. Under the **Bot** tab:
   - Click **Add Bot**.
   - Enable **Message Content Intent** (under Privileged Gateway Intents).
   - Copy your **Bot Token**.
4. Under **OAuth2 > URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Administrator` (or `Send Messages`, `Embed Links`, `Read Message History`, `Use Slash Commands`).
   - Copy and open the generated link in your browser to invite the bot to your Discord server.

---

### 2. Configure Token & Run

You can provide your bot token via environment variable or by editing [discord_bot.py](file:///c:/Users/zisha/Desktop/Test%20VS/Valqore%20Hosting/discord_bot.py):

#### Option A: Running with environment variable (Recommended)
```bash
# On Linux / VPS:
export DISCORD_BOT_TOKEN="your_bot_token_here"
python3 discord_bot.py
```

#### Option B: Inside a `screen` session (24/7 background)
```bash
screen -S mcbot
cd /home/ubuntu/valqore
source venv/bin/activate
export DISCORD_BOT_TOKEN="your_bot_token_here"
python discord_bot.py
```
*(Press `Ctrl+A` then `D` to detach the screen and leave the bot running in the background).*

---

## 📋 Available Commands

| Slash Command | Description |
|---|---|
| `/panel` | Posts an interactive control panel card with **Start**, **Stop**, **Restart**, **Refresh**, and **Live Logs** buttons. |
| `/status` | Displays live RAM usage, CPU percentage, disk space, and online players. |
| `/cmd <command>` | Runs any Minecraft command in the console (e.g., `/cmd command:op PlayerName` or `/cmd command:say Hello World`). |
| `/players` | Lists all players currently connected to the server. |
| `/console [lines]`| Fetches the latest live Minecraft console output logs. |
| `/start` | Boots up the Minecraft server. |
| `/stop` | Safely stops the server. |
| `/restart` | Safely restarts the server. |
| `/ping` | Displays Discord API response time and Minecraft process health. |

---

## 🔒 Admin Security
- By default, users with **Administrator** permissions on your Discord server can execute power and console commands.
- You can restrict access to specific Discord user IDs by adding them to `ADMIN_USER_IDS` in [discord_bot.py](file:///c:/Users/zisha/Desktop/Test%20VS/Valqore%20Hosting/discord_bot.py#L29) (e.g., `ADMIN_USER_IDS = [123456789012345678]`).
