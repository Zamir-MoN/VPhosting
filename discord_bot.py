import os
import sys
import time
import asyncio
import subprocess
import shutil
import json
import re
import urllib.request
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None

import discord
from discord.ext import commands, tasks
from discord import app_commands

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MC_DIR = os.path.join(BASE_DIR, "mc_server")
LOG_PATH = os.path.join(MC_DIR, "logs", "latest.log")
ENV_FILE = os.path.join(BASE_DIR, ".env")
PANEL_API_URL = "http://127.0.0.1:8090/api"

def get_public_ip():
    """Fetches the real public VPS IP address with domain fallback."""
    custom_ip = os.getenv("SERVER_IP")
    if custom_ip:
        return custom_ip

    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=2) as r:
            ip = r.read().decode('utf-8').strip()
            if ip:
                return f"{ip}:25565"
    except Exception:
        pass

    try:
        with urllib.request.urlopen("https://ifconfig.me/ip", timeout=2) as r:
            ip = r.read().decode('utf-8').strip()
            if ip:
                return f"{ip}:25565"
    except Exception:
        pass

    return "valqore-arcane-smp.indevs.in"

# Load BOT_TOKEN from env or .env file
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not BOT_TOKEN and os.path.exists(ENV_FILE):
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as ef:
            for line in ef:
                line = line.strip()
                if line.startswith("DISCORD_BOT_TOKEN="):
                    BOT_TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except Exception:
        pass

if not BOT_TOKEN:
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

ADMIN_USER_IDS = []


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
MC_PROCESS = None

# Active live panels to auto-refresh in real time
active_panel_messages = {}

# ==========================================
# UNIFIED POWER ACTIONS (Using Valqore Web Panel API + Native Fallback)
# ==========================================
def call_api(endpoint: str, method="POST", data=None):
    """Communicates directly with the Valqore FastAPI backend for 100% synchronized execution."""
    try:
        url = f"{PANEL_API_URL}/{endpoint.lstrip('/')}"
        req_data = json.dumps(data).encode('utf-8') if data else None
        headers = {"Content-Type": "application/json"} if req_data else {}
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=5) as response:
            res_body = response.read().decode('utf-8')
            return json.loads(res_body)
    except Exception as e:
        return None

def start_mc_server():
    # 1. Try FastAPI endpoint first
    res = call_api("start", method="POST")
    if res and res.get("status") == "success":
        return True, "🚀 Server boot initiated!"
    elif res and res.get("status") == "error":
        return False, res.get("message", "Failed to start")

    # 2. Native start fallback
    if is_server_running():
        return False, "Minecraft server is already running!"

    start_script = os.path.join(MC_DIR, "start.sh")
    server_jar = os.path.join(MC_DIR, "server.jar")
    if not os.path.exists(start_script) and not os.path.exists(server_jar):
        return False, "No server installed! `server.jar` missing."

    eula_path = os.path.join(MC_DIR, "eula.txt")
    if not os.path.exists(eula_path):
        with open(eula_path, "w") as f: f.write("eula=true\n")

    os.makedirs(os.path.join(MC_DIR, "logs"), exist_ok=True)
    open(LOG_PATH, "w").close()

    bash_bin = shutil.which("bash") or "/bin/bash"
    java_bin = shutil.which("java") or "/usr/bin/java"
    run_cmd_str = f"{bash_bin} {start_script}" if os.path.exists(start_script) else f"{java_bin} -Xms10240M -Xmx10240M -jar {server_jar} nogui"

    env = os.environ.copy()
    env["PATH"] = f"/usr/bin:/bin:/usr/local/bin:{env.get('PATH', '')}"

    if shutil.which("tmux"):
        try: subprocess.run(["tmux", "kill-session", "-t", "mc_server"], stderr=subprocess.DEVNULL)
        except: pass
        tmux_cmd = f"cd '{MC_DIR}' && {run_cmd_str} 2>&1 | tee -a '{LOG_PATH}'"
        subprocess.Popen(["tmux", "new-session", "-d", "-s", "mc_server", "bash", "-c", tmux_cmd], env=env)
    return True, "🚀 Boot sequence initiated."

def stop_mc_server():
    # 1. Try FastAPI endpoint first
    res = call_api("stop", method="POST")
    if res and res.get("status") == "success":
        return True, "🛑 Minecraft server stopped."

    # 2. Native stop fallback
    if shutil.which("tmux"):
        try: subprocess.run(["tmux", "send-keys", "-t", "mc_server", "stop", "ENTER"], stderr=subprocess.DEVNULL)
        except: pass
    time.sleep(2)
    if shutil.which("tmux"):
        try: subprocess.run(["tmux", "kill-session", "-t", "mc_server"], stderr=subprocess.DEVNULL)
        except: pass
    return True, "🛑 Minecraft server stopped."

def send_console_command(cmd: str):
    # 1. Try FastAPI endpoint first
    res = call_api("command", method="POST", data={"command": cmd})
    if res and res.get("status") == "success":
        return True, f"Command sent: `{cmd}`"

    # 2. Native send-keys fallback
    if shutil.which("tmux"):
        try:
            check = subprocess.run(["tmux", "has-session", "-t", "mc_server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if check.returncode == 0:
                subprocess.run(["tmux", "send-keys", "-t", "mc_server", cmd, "ENTER"], check=True)
                return True, f"Command sent: `{cmd}`"
        except: pass
    return False, "Failed to send command to console."

def get_stats_data():
    # 1. Try FastAPI stats endpoint for 100% exact sync with web dashboard
    api_stats = call_api("stats", method="GET")
    if api_stats and isinstance(api_stats, dict):
        status_val = api_stats.get("status", "offline")
        is_running = (status_val in ["online", "starting"])
        online_p = [p["name"] for p in api_stats.get("online_players", []) if isinstance(p, dict)]
        return {
            "running": is_running,
            "raw_status": status_val,
            "ram_percent": api_stats.get("ram_percent", 0),
            "ram_used_mb": api_stats.get("ram_used_mb", 0),
            "ram_allocated_mb": api_stats.get("ram_allocated_mb", 4096),
            "cpu_percent": api_stats.get("cpu_percent", 0),
            "disk_percent": api_stats.get("disk_percent", 0),
            "online_players": online_p,
            "players_count": len(online_p),
            "max_players": api_stats.get("max_players", 50)
        }


    # 2. Local fallback stats
    running = is_server_running()
    ram_percent = 0
    ram_used_mb = 0
    allocated_ram_mb = 4096
    cpu_percent = 0
    disk_percent = 0

    if psutil:
        try:
            disk_percent = int(psutil.disk_usage('/').percent)
            procs = get_mc_processes() if running else []
            if procs:
                for p in procs:
                    try:
                        ram_used_mb += int(p.memory_info().rss / (1024 * 1024))
                        p_cpu = p.cpu_percent(interval=None)
                        if p_cpu: cpu_percent += p_cpu
                    except: pass
                ram_percent = min(100, int((ram_used_mb / max(1, allocated_ram_mb)) * 100))
        except: pass

    return {
        "running": running,
        "ram_percent": ram_percent,
        "ram_used_mb": ram_used_mb,
        "ram_allocated_mb": allocated_ram_mb,
        "cpu_percent": int(cpu_percent),
        "disk_percent": disk_percent,
        "online_players": [],
        "players_count": 0,
        "max_players": 50
    }

def get_mc_processes():
    global MC_PROCESS
    found_procs = []
    if psutil:
        try:
            current_pid = os.getpid()
            for p in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
                try:
                    if p.pid == current_pid: continue
                    cmdline = p.info.get('cmdline') or []
                    cmd_str = " ".join(cmdline).lower()
                    if "server.jar" in cmd_str or ("java" in (p.info.get('name') or "").lower() and "nogui" in cmd_str):
                        found_procs.append(p)
                except: pass
        except: pass
    return found_procs

def is_server_running() -> bool:
    if shutil.which("tmux"):
        try:
            subprocess.check_output(["tmux", "has-session", "-t", "mc_server"], stderr=subprocess.STDOUT)
            return True
        except: pass
    return len(get_mc_processes()) > 0

def get_latest_logs(lines_count=20) -> str:
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                if lines: return "".join(lines[-lines_count:])
        except: pass
    tmux_bin = shutil.which("tmux")
    if tmux_bin:
        try:
            out = subprocess.check_output([tmux_bin, "capture-pane", "-pt", "mc_server", "-S", f"-{lines_count}"], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
            if out.strip(): return out
        except: pass
    return "No logs available or server is offline."

def is_admin(interaction_or_ctx):
    user = interaction_or_ctx.user if hasattr(interaction_or_ctx, "user") else interaction_or_ctx.author
    if ADMIN_USER_IDS and user.id in ADMIN_USER_IDS:
        return True
    if hasattr(user, "guild_permissions") and user.guild_permissions.administrator:
        return True
    if not ADMIN_USER_IDS and not hasattr(user, "guild_permissions"):
        return True
    return False

def make_mini_bar(percent: int, length: int = 8) -> str:
    """Creates a sleek visual monospace bar for RAM, CPU, Disk."""
    filled = max(0, min(length, round((percent / 100) * length)))
    return f"`[{'█' * filled}{'░' * (length - filled)}]`"

def build_status_embed(custom_status: str = None, custom_color: discord.Color = None, progress_bar: str = None) -> discord.Embed:
    stats = get_stats_data()
    server_ip = get_public_ip()
    
    if custom_status:
        status_text = custom_status
        color = custom_color or discord.Color.gold()
    else:
        raw_status = stats.get("raw_status", "online" if stats["running"] else "offline")
        if raw_status == "online":
            status_text = "🟢 **ONLINE (READY TO PLAY)**"
            color = discord.Color.from_rgb(0, 255, 127) # Vibrant Emerald Green
        elif raw_status == "starting":
            status_text = "🟡 **BOOTING (LOADING WORLD & PLUGINS...)** ⏳"
            color = discord.Color.from_rgb(255, 204, 0) # Gold
        else:
            status_text = "🔴 **OFFLINE**"
            color = discord.Color.from_rgb(255, 59, 48) # Sleek Red

    # Header description block
    desc = f"**SERVER STATUS**\n> {status_text}\n"
    if progress_bar:
        desc += f"\n> {progress_bar}\n"

    embed = discord.Embed(
        title="⚡ VALQORE MINECRAFT ENGINE",
        description=desc,
        color=color,
        timestamp=discord.utils.utcnow()
    )

    # 1. Connection Section
    embed.add_field(
        name="📡 **CONNECTION ADDRESS**",
        value=f"```fix\n{server_ip}\n```",
        inline=False
    )

    # 2. Performance & Hardware Metrics
    ram_bar = make_mini_bar(stats['ram_percent'])
    cpu_bar = make_mini_bar(stats['cpu_percent'])
    disk_bar = make_mini_bar(stats['disk_percent'])

    embed.add_field(
        name="🧠 **MEMORY (RAM)**",
        value=f"{ram_bar} **{stats['ram_percent']}%**\n`{stats['ram_used_mb']} MB / {stats['ram_allocated_mb']} MB`",
        inline=True
    )
    embed.add_field(
        name="⚙️ **CPU LOAD**",
        value=f"{cpu_bar} **{stats['cpu_percent']}%**\n`4 Cores Active`",
        inline=True
    )
    embed.add_field(
        name="💾 **STORAGE**",
        value=f"{disk_bar} **{stats['disk_percent']}%**\n`NVMe SSD`",
        inline=True
    )

    # 3. Players Section
    players = stats["online_players"]
    if players:
        player_display = " ".join([f"`{p}`" for p in players])
    else:
        player_display = "*No players currently in-game.*"

    embed.add_field(
        name=f"👥 **ONLINE PLAYERS ({stats['players_count']} / {stats['max_players']})**",
        value=f"> {player_display}\n\u200b",
        inline=False
    )
    
    # Minecraft Banner Image
    embed.set_image(url="https://cdn.mos.cms.futurecdn.net/v6XoEzDajGRMWNeLY5NMSb.jpg")
    
    embed.set_footer(
        text="⚡ Live Sync Active • Auto-refreshes silently",
        icon_url="https://cdn-icons-png.flaticon.com/512/3208/3208726.png"
    )
    return embed




# ==========================================
# REAL PROGRESS-TRACKED CONTROL PANEL VIEW
# ==========================================
class ServerControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Start", style=discord.ButtonStyle.success, emoji="▶️", custom_id="mc_btn_start")
    async def btn_start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ You do not have permission to manage this server.", ephemeral=True)
        
        # Frame 1: Starting trigger
        anim_embed = build_status_embed(
            custom_status="🟡 **Starting Server...** ⏳",
            custom_color=discord.Color.yellow(),
            progress_bar="`[▰▰▱▱▱▱▱▱▱▱] 20% Initializing boot sequence...`"
        )
        await interaction.response.edit_message(embed=anim_embed, view=self)
        
        start_mc_server()

        # Frame 2: Real verification loop (polls up to 15 seconds until actually online)
        for i in range(1, 6):
            await asyncio.sleep(2.0)
            stats = get_stats_data()
            if stats["running"]:
                anim_embed = build_status_embed(
                    custom_status="🟢 **Server Online & Active!** 🚀",
                    custom_color=discord.Color.green(),
                    progress_bar="`[▰▰▰▰▰▰▰▰▰▰] 100% Process running smoothly.`"
                )
                try: await interaction.message.edit(embed=anim_embed, view=self)
                except: pass
                await asyncio.sleep(1.5)
                break
            else:
                pct = min(90, 20 + i * 15)
                fill = "▰" * (pct // 10)
                empty = "▱" * (10 - (pct // 10))
                anim_embed = build_status_embed(
                    custom_status="🟡 **Spawning Java Engine...** ⏳",
                    custom_color=discord.Color.gold(),
                    progress_bar=f"`[{fill}{empty}] {pct}% Booting world & plugins...`"
                )
                try: await interaction.message.edit(embed=anim_embed, view=self)
                except: pass

        try: await interaction.message.edit(embed=build_status_embed(), view=self)
        except: pass

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️", custom_id="mc_btn_stop")
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ You do not have permission to manage this server.", ephemeral=True)
        
        # Frame 1: Stopping trigger
        anim_embed = build_status_embed(
            custom_status="🟠 **Saving World & Stopping...** 💾",
            custom_color=discord.Color.orange(),
            progress_bar="`[▰▰▰▰▰▱▱▱▱▱] 50% Saving chunks & players...`"
        )
        await interaction.response.edit_message(embed=anim_embed, view=self)
        
        stop_mc_server()

        # Real shutdown verification loop
        for i in range(1, 5):
            await asyncio.sleep(1.5)
            stats = get_stats_data()
            if not stats["running"]:
                anim_embed = build_status_embed(
                    custom_status="🔴 **Server Stopped Safely.** 🛑",
                    custom_color=discord.Color.dark_red(),
                    progress_bar="`[▰▰▰▰▰▰▰▰▰▰] 100% Stopped cleanly.`"
                )
                try: await interaction.message.edit(embed=anim_embed, view=self)
                except: pass
                await asyncio.sleep(1.5)
                break

        try: await interaction.message.edit(embed=build_status_embed(), view=self)
        except: pass

    @discord.ui.button(label="Restart", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="mc_btn_restart")
    async def btn_restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ You do not have permission to manage this server.", ephemeral=True)
        
        # Step 1: Stop
        anim_embed = build_status_embed(
            custom_status="🟠 **Restart 1/2: Saving & Stopping...** 🛑",
            custom_color=discord.Color.orange(),
            progress_bar="`[▰▰▰▰▱▱▱▱▱▱] 40% Saving world and shutting down...`"
        )
        await interaction.response.edit_message(embed=anim_embed, view=self)
        stop_mc_server()
        await asyncio.sleep(2.5)

        # Step 2: Start
        anim_embed = build_status_embed(
            custom_status="🟡 **Restart 2/2: Rebooting Engine...** ⚡",
            custom_color=discord.Color.yellow(),
            progress_bar="`[▰▰▰▰▰▰▰▰▱▱] 80% Initializing clean JVM session...`"
        )
        try: await interaction.message.edit(embed=anim_embed, view=self)
        except: pass
        start_mc_server()

        # Step 3: Verify boot
        for _ in range(5):
            await asyncio.sleep(2.0)
            stats = get_stats_data()
            if stats["running"]:
                break

        try: await interaction.message.edit(embed=build_status_embed(), view=self)
        except: pass

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔃", custom_id="mc_btn_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        pulse_embed = build_status_embed(
            custom_status="🔄 **Fetching Latest Stats...**",
            custom_color=discord.Color.blurple()
        )
        await interaction.response.edit_message(embed=pulse_embed, view=self)
        await asyncio.sleep(0.4)
        try: await interaction.message.edit(embed=build_status_embed(), view=self)
        except: pass

    @discord.ui.button(label="Live Logs", style=discord.ButtonStyle.secondary, emoji="📜", custom_id="mc_btn_logs")
    async def btn_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        logs = get_latest_logs(15)
        if len(logs) > 1900: logs = logs[-1900:]
        await interaction.response.send_message(f"**📜 Recent Console Logs:**\n```ansi\n{logs}\n```", ephemeral=True)

# ==========================================
# BOT EVENTS & SILENT AUTO REFRESH LOOP
# ==========================================
@bot.event
async def on_ready():
    print(f"🤖 Bot Logged in as {bot.user.name} ({bot.user.id})")
    for guild in bot.guilds:
        try:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
        except: pass
            
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} global slash commands cleanly.")
    except Exception as e:
        print(f"Sync error: {e}")

    bot.add_view(ServerControlView())
    if not update_presence.is_running():
        update_presence.start()
    if not auto_refresh_panels.is_running():
        auto_refresh_panels.start()

@tasks.loop(seconds=5)
async def auto_refresh_panels():
    if not active_panel_messages:
        return
    try:
        embed = build_status_embed()
        dead_keys = []
        for key, msg in list(active_panel_messages.items()):
            try: await msg.edit(embed=embed)
            except discord.NotFound: dead_keys.append(key)
            except: pass
        for k in dead_keys:
            active_panel_messages.pop(k, None)
    except: pass

@tasks.loop(seconds=20)
async def update_presence():
    try:
        stats = get_stats_data()
        if stats["running"]:
            activity = discord.Activity(
                type=discord.ActivityType.playing,
                name=f"Minecraft ({stats['players_count']}/{stats['max_players']} online)"
            )
            await bot.change_presence(status=discord.Status.online, activity=activity)
        else:
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name="Server is Offline 🔴"
            )
            await bot.change_presence(status=discord.Status.dnd, activity=activity)
    except: pass

# ==========================================
# SLASH & PREFIX COMMANDS
# ==========================================
@bot.tree.command(name="panel", description="Post the live Minecraft Control Panel (Silently auto-refreshed in real-time).")
async def cmd_panel(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You need Admin permissions to post the control panel.", ephemeral=True)
    await interaction.response.defer()
    view = ServerControlView()
    embed = build_status_embed()
    msg = await interaction.followup.send(embed=embed, view=view)
    active_panel_messages[msg.id] = msg


@bot.command(name="panel")
async def p_panel(ctx):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin permissions required.")
    view = ServerControlView()
    embed = build_status_embed()
    msg = await ctx.send(embed=embed, view=view)
    active_panel_messages[msg.id] = msg

@bot.tree.command(name="status", description="Check live RAM, CPU, disk usage, and online players.")
async def cmd_status(interaction: discord.Interaction):
    embed = build_status_embed()
    await interaction.response.send_message(embed=embed)

@bot.command(name="status")
async def p_status(ctx):
    embed = build_status_embed()
    await ctx.send(embed=embed)

@bot.tree.command(name="ping", description="Check Discord Bot latency and server status.")
async def cmd_ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    server_text = "🟢 Online" if is_server_running() else "🔴 Offline"
    embed = discord.Embed(title="🏓 Pong!", color=discord.Color.blue())
    embed.add_field(name="Discord API Latency", value=f"`{latency_ms} ms`", inline=True)
    embed.add_field(name="Minecraft Process", value=f"`{server_text}`", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.command(name="ping")
async def p_ping(ctx):
    latency_ms = round(bot.latency * 1000)
    server_text = "🟢 Online" if is_server_running() else "🔴 Offline"
    embed = discord.Embed(title="🏓 Pong!", color=discord.Color.blue())
    embed.add_field(name="Discord API Latency", value=f"`{latency_ms} ms`", inline=True)
    embed.add_field(name="Minecraft Process", value=f"`{server_text}`", inline=True)
    await ctx.send(embed=embed)

@bot.tree.command(name="start", description="Start the Minecraft Server.")
async def cmd_start(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
    await interaction.response.defer()
    ok, msg = start_mc_server()
    await interaction.followup.send(msg)

@bot.command(name="start")
async def p_start(ctx):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin permissions required.")
    ok, msg = start_mc_server()
    await ctx.send(msg)

@bot.tree.command(name="stop", description="Stop the Minecraft Server cleanly.")
async def cmd_stop(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
    await interaction.response.defer()
    ok, msg = stop_mc_server()
    await interaction.followup.send(msg)

@bot.command(name="stop")
async def p_stop(ctx):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin permissions required.")
    ok, msg = stop_mc_server()
    await ctx.send(msg)

@bot.tree.command(name="restart", description="Restart the Minecraft Server.")
async def cmd_restart(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
    await interaction.response.defer()
    stop_mc_server()
    await asyncio.sleep(2)
    start_mc_server()
    await interaction.followup.send("🔄 Minecraft server is restarting...")

@bot.command(name="restart")
async def p_restart(ctx):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin permissions required.")
    stop_mc_server()
    await asyncio.sleep(2)
    start_mc_server()
    await ctx.send("🔄 Minecraft server is restarting...")

@bot.tree.command(name="cmd", description="Execute any command on the Minecraft Server console (e.g. op, ban, gamemode).")
@app_commands.describe(command="The Minecraft command to run (without leading slash)")
async def cmd_console(interaction: discord.Interaction, command: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Admin permissions required to run console commands.", ephemeral=True)
    clean_cmd = command.strip().lstrip("/")
    ok, msg = send_console_command(clean_cmd)
    if ok:
        await interaction.response.send_message(f"💻 **Sent to Console:** `{clean_cmd}`\n*Allow 1-2 seconds for execution.*")
    else:
        await interaction.response.send_message(f"❌ {msg}", ephemeral=True)

@bot.command(name="cmd")
async def p_cmd(ctx, *, command: str = ""):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin permissions required.")
    if not command:
        return await ctx.send("Usage: `!cmd <minecraft command>` (e.g. `!cmd op PlayerName`)")
    clean_cmd = command.strip().lstrip("/")
    ok, msg = send_console_command(clean_cmd)
    if ok:
        await ctx.send(f"💻 **Sent to Console:** `{clean_cmd}`")
    else:
        await ctx.send(f"❌ {msg}")

@bot.tree.command(name="players", description="View list of all online players.")
async def cmd_players(interaction: discord.Interaction):
    stats = get_stats_data()
    if not stats["running"]:
        return await interaction.response.send_message("🔴 Server is currently offline.")
    players = stats["online_players"]
    embed = discord.Embed(
        title=f"👥 Online Players ({len(players)}/{stats['max_players']})",
        color=discord.Color.green()
    )
    if players:
        embed.description = "\n".join([f"• `{p}`" for p in players])
    else:
        embed.description = "*No players currently connected.*"
    await interaction.response.send_message(embed=embed)

@bot.command(name="players")
async def p_players(ctx):
    stats = get_stats_data()
    if not stats["running"]:
        return await ctx.send("🔴 Server is currently offline.")
    players = stats["online_players"]
    embed = discord.Embed(
        title=f"👥 Online Players ({len(players)}/{stats['max_players']})",
        color=discord.Color.green()
    )
    if players:
        embed.description = "\n".join([f"• `{p}`" for p in players])
    else:
        embed.description = "*No players currently connected.*"
    await ctx.send(embed=embed)

@bot.tree.command(name="console", description="Get latest live console output logs.")
@app_commands.describe(lines="Number of log lines to retrieve (default: 20)")
async def cmd_logs(interaction: discord.Interaction, lines: Optional[int] = 20):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
    log_count = min(max(5, lines or 20), 40)
    logs = get_latest_logs(log_count)
    if len(logs) > 1900:
        logs = logs[-1900:]
    await interaction.response.send_message(f"**📜 Console Output (Last {log_count} lines):**\n```\n{logs}\n```")

@bot.command(name="console")
async def p_console(ctx, lines: int = 20):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin permissions required.")
    log_count = min(max(5, lines), 40)
    logs = get_latest_logs(log_count)
    if len(logs) > 1900:
        logs = logs[-1900:]
    await ctx.send(f"**📜 Console Output (Last {log_count} lines):**\n```\n{logs}\n```")

if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not BOT_TOKEN:
        print("❌ ERROR: DISCORD_BOT_TOKEN missing in .env")
        sys.exit(1)
    bot.run(BOT_TOKEN)
