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
        online_p_raw = api_stats.get("online_players", [])
        all_p_raw = api_stats.get("all_players", [])
        
        online_p = [p["name"] if isinstance(p, dict) else str(p) for p in online_p_raw]
        
        # Build comprehensive players list (online + offline)
        players_map = {}
        for p in all_p_raw:
            if isinstance(p, dict) and "name" in p:
                players_map[p["name"]] = p
            elif isinstance(p, str):
                players_map[p] = {"name": p, "status": "offline", "is_op": False}
        for p in online_p_raw:
            if isinstance(p, dict) and "name" in p:
                players_map[p["name"]] = p
            elif isinstance(p, str):
                players_map[p] = {"name": p, "status": "online", "is_op": False}

        return {
            "running": is_running,
            "raw_status": status_val,
            "ram_percent": api_stats.get("ram_percent", 0),
            "ram_used_mb": api_stats.get("ram_used_mb", 0),
            "ram_allocated_mb": api_stats.get("ram_allocated_mb", 4096),
            "cpu_percent": api_stats.get("cpu_percent", 0),
            "disk_percent": api_stats.get("disk_percent", 0),
            "online_players": online_p,
            "all_players_details": list(players_map.values()),
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

    # Read usercache.json and ops.json for fallback player list
    fallback_players = []
    try:
        usercache_file = os.path.join(MC_DIR, "usercache.json")
        ops_file = os.path.join(MC_DIR, "ops.json")
        ops_set = set()
        if os.path.exists(ops_file):
            with open(ops_file, "r") as of:
                for o in json.load(of):
                    if isinstance(o, dict) and "name" in o: ops_set.add(o["name"].lower())
        if os.path.exists(usercache_file):
            with open(usercache_file, "r") as uf:
                for u in json.load(uf):
                    if isinstance(u, dict) and "name" in u:
                        fallback_players.append({
                            "name": u["name"],
                            "status": "offline",
                            "is_op": u["name"].lower() in ops_set
                        })
    except: pass

    return {
        "running": running,
        "ram_percent": ram_percent,
        "ram_used_mb": ram_used_mb,
        "ram_allocated_mb": allocated_ram_mb,
        "cpu_percent": int(cpu_percent),
        "disk_percent": disk_percent,
        "online_players": [],
        "all_players_details": fallback_players,
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

# ==========================================
# SERVER SECURITY & AUTHORIZATION SYSTEM
# ==========================================
def get_auth_config():
    """Fetches the authorized guilds and permission rules from local config or FastAPI backend."""
    cfg = call_api("bot/auth/config", method="GET")
    if cfg and isinstance(cfg, dict):
        return cfg
    
    # Fallback to local bot_config.json
    local_cfg_file = os.path.join(BASE_DIR, "bot_config.json")
    if os.path.exists(local_cfg_file):
        try:
            with open(local_cfg_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"approved_guilds": {}}

def check_guild_authorized(guild_id: str) -> tuple[bool, dict]:
    """Checks if a Discord Server (Guild) has been approved via the 6-digit code."""
    cfg = get_auth_config()
    approved = cfg.get("approved_guilds", {})
    if str(guild_id) in approved:
        return True, approved[str(guild_id)]
    return False, {}

def is_admin(interaction_or_ctx):
    """
    Strict Security Check:
    1. The Guild must be authorized via /setupmc.
    2. Commands can ONLY be run in the designated Channel.
    3. The user must hold the designated Role (or be Guild Owner / Administrator).
    """
    user = interaction_or_ctx.user if hasattr(interaction_or_ctx, "user") else interaction_or_ctx.author
    guild = interaction_or_ctx.guild if hasattr(interaction_or_ctx, "guild") else None
    channel = interaction_or_ctx.channel if hasattr(interaction_or_ctx, "channel") else None

    if not guild:
        return False

    is_auth, guild_rule = check_guild_authorized(str(guild.id))
    if not is_auth:
        return False

    # 1. Enforce Designated Channel
    allowed_channel_id = str(guild_rule.get("channel_id", "")).strip()
    if allowed_channel_id and channel and str(channel.id) != allowed_channel_id:
        return False

    # 2. Enforce Designated Role (or Guild Owner / Administrator override)
    if hasattr(user, "guild_permissions") and (user.guild_permissions.administrator or guild.owner_id == user.id):
        return True

    allowed_role_id = str(guild_rule.get("role_id", "")).strip()
    if allowed_role_id and hasattr(user, "roles"):
        user_role_ids = [str(r.id) for r in user.roles]
        if allowed_role_id in user_role_ids:
            return True

    return False

def make_mini_bar(percent: int, length: int = 8) -> str:
    """Creates a sleek visual monospace bar for RAM, CPU, Disk."""
    filled = max(0, min(length, round((percent / 100) * length)))
    return f"`[{'█' * filled}{'░' * (length - filled)}]`"

def build_status_embed(custom_status: str = None, custom_color: discord.Color = None, progress_bar: str = None) -> discord.Embed:
    stats = get_stats_data()
    server_ip = get_public_ip()
    
    # Valqore Signature Brand Cyber Lime Color (#E6FF00)
    brand_color = discord.Color.from_rgb(230, 255, 0)
    color = custom_color or brand_color

    if custom_status:
        status_text = custom_status
    else:
        raw_status = stats.get("raw_status", "online" if stats["running"] else "offline")
        if raw_status == "online":
            status_text = "🟢 **ONLINE (READY TO PLAY)**"
        elif raw_status == "starting":
            status_text = "🟡 **BOOTING (LOADING WORLD & PLUGINS...)** ⏳"
        else:
            status_text = "🔴 **OFFLINE**"

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
    
    # Calculate real Minecraft Server Ping Latency
    import socket
    server_ping_ms = 0
    is_socket_open = False
    
    try:
        t_start = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        res = s.connect_ex(('127.0.0.1', 25565))
        s.close()
        if res == 0:
            server_ping_ms = max(1, round((time.time() - t_start) * 1000))
            is_socket_open = True
    except Exception:
        pass

    if stats["running"] or is_socket_open:
        ping_val = f"{server_ping_ms} ms" if is_socket_open else "Starting..."
    else:
        ping_val = "Offline"

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
        name="📶 **SERVER PING**",
        value=f"```fix\n{ping_val}\n```",
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
    embed.set_image(url="https://raw.githubusercontent.com/Zamir-MoN/VPhosting/main/static/banner.png")
    
    embed.set_footer(
        text="⚡ Live Sync Active • Auto-refreshes silently",
        icon_url="https://cdn-icons-png.flaticon.com/512/3208/3208726.png"
    )
    return embed





def strip_ansi_codes(text: str) -> str:
    """Removes ANSI terminal escape sequences and raw color artifact codes."""
    if not text: return ""
    # Strip \x1b[...] or \033[...]
    ansi_regex = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\033\[[0-9;]*[a-zA-Z]|\[[0-9;]+m')
    clean = ansi_regex.sub('', text)
    # Filter out stray non-printable control chars except \n and \t
    clean = "".join(ch for ch in clean if ch == '\n' or ch == '\t' or ord(ch) >= 32)
    return clean.strip()

def get_clean_logs(lines_count=18) -> str:
    raw = get_latest_logs(lines_count)
    cleaned = strip_ansi_codes(raw)
    if not cleaned:
        return "No logs available or server is offline."
    # Ensure fits in Discord code block
    if len(cleaned) > 1800:
        cleaned = cleaned[-1800:]
    return cleaned


# ==========================================
# MORE OPTIONS MODAL & SUB-VIEW
# ==========================================
class SendConsoleCommandModal(discord.ui.Modal, title="💻 Execute Server Command"):
    cmd_input = discord.ui.TextInput(
        label="Minecraft Command",
        placeholder="e.g. op PlayerName, weather clear, time set day",
        required=True,
        max_length=150
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
        raw_cmd = self.cmd_input.value.strip().lstrip("/")
        ok, msg = send_console_command(raw_cmd)
        if ok:
            await interaction.response.send_message(f"✅ **Command executed on console:**\n`/{raw_cmd}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)


class LiveConsoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Refresh Logs", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="mc_btn_console_refresh")
    async def btn_refresh_console(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
        logs = get_clean_logs(18)
        embed = discord.Embed(
            title="📜 LIVE MINECRAFT CONSOLE",
            description=f"```fix\n{logs}\n```",
            color=discord.Color.from_rgb(230, 255, 0),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="⚡ Valqore Live Console • Click Refresh to fetch latest lines", icon_url="https://cdn-icons-png.flaticon.com/512/3208/3208726.png")
        if interaction.message and interaction.message.id in active_panel_messages:
            active_panel_messages[interaction.message.id]["mode"] = "console"
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Send Command", style=discord.ButtonStyle.success, emoji="💻", custom_id="mc_btn_console_sendcmd")
    async def btn_send_cmd(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
        await interaction.response.send_modal(SendConsoleCommandModal())

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️", custom_id="mc_btn_console_back")
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.message and interaction.message.id in active_panel_messages:
            active_panel_messages[interaction.message.id]["mode"] = "options"
        embed = build_status_embed()
        embed.set_footer(text="⚙️ More Options Menu • Select an action below or click Back", icon_url="https://cdn-icons-png.flaticon.com/512/3208/3208726.png")
        await interaction.response.edit_message(embed=embed, view=MoreOptionsView())


# ==========================================
# PLAYER MANAGER & ACTION VIEWS
# ==========================================
class PlayerActionsView(discord.ui.View):
    def __init__(self, player_name: str, is_online: bool = True, is_op: bool = False, current_gamemode: str = "survival"):
        super().__init__(timeout=None)
        self.player_name = player_name
        self.is_online = is_online
        self.is_op = is_op
        self.current_gamemode = (current_gamemode or "survival").lower()
        self.setup_buttons()

    def setup_buttons(self):
        self.clear_items()
        
        # Row 0: Gamemode Switchers with active highlight (✅ and Green style for currently active mode)
        modes = [
            ("survival", "Survival", "⚔️"),
            ("creative", "Creative", "🧱"),
            ("spectator", "Spectator", "👁️"),
            ("adventure", "Adventure", "🗺️")
        ]
        
        for mode_id, mode_label, mode_emoji in modes:
            is_active = (self.current_gamemode == mode_id)
            label = f"{mode_label} ✓" if is_active else mode_label
            style = discord.ButtonStyle.success if is_active else discord.ButtonStyle.secondary
            btn = discord.ui.Button(label=label, style=style, emoji=mode_emoji, row=0)
            btn.callback = self.make_gamemode_callback(mode_id, mode_label)
            self.add_item(btn)

        # Row 1: OP Toggle (Shows OP Player if not OP, DE-OP if currently OP)
        if self.is_op:
            btn_deop = discord.ui.Button(label="Remove OP (DE-OP)", style=discord.ButtonStyle.danger, emoji="⛔", row=1)
            btn_deop.callback = self.cb_deop
            self.add_item(btn_deop)
        else:
            btn_op = discord.ui.Button(label="Make Operator (OP)", style=discord.ButtonStyle.primary, emoji="👑", row=1)
            btn_op.callback = self.cb_op
            self.add_item(btn_op)

        # Kick button (Only functional if online)
        kick_style = discord.ButtonStyle.danger if self.is_online else discord.ButtonStyle.secondary
        kick_label = "Kick Player" if self.is_online else "Offline (Cannot Kick)"
        btn_kick = discord.ui.Button(label=kick_label, style=kick_style, emoji="👢", disabled=not self.is_online, row=1)
        btn_kick.callback = self.cb_kick
        self.add_item(btn_kick)

        # Row 2: Back button
        btn_back = discord.ui.Button(label="Back to Player List", style=discord.ButtonStyle.danger, emoji="↩️", row=2)
        btn_back.callback = self.cb_back
        self.add_item(btn_back)

    def build_embed(self) -> discord.Embed:
        avatar_url = f"https://mc-heads.net/avatar/{self.player_name}/100"
        status_badge = "🟢 **ONLINE (IN-GAME)**" if self.is_online else "⚫ **OFFLINE**"
        op_badge = "👑 **OPERATOR (ADMIN)**" if self.is_op else "👤 **Standard Player**"
        mode_badge = f"🎮 **{self.current_gamemode.upper()}**"

        embed = discord.Embed(
            title=f"👤 PLAYER CONTROL: {self.player_name}",
            description=(
                f"**Connection Status:** {status_badge}\n"
                f"**Permission Rank:** {op_badge}\n"
                f"**Active Gamemode:** {mode_badge}\n\n"
                f"*(Active states are highlighted with **Green & ✓ Checkmarks**)*"
            ),
            color=discord.Color.from_rgb(230, 255, 0),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text="⚡ Valqore Live Player Controls • Real-time Sync", icon_url="https://cdn-icons-png.flaticon.com/512/3208/3208726.png")
        return embed

    def make_gamemode_callback(self, mode_id, mode_label):
        async def callback(interaction: discord.Interaction):
            if not is_admin(interaction):
                return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
            send_console_command(f"gamemode {mode_id} {self.player_name}")
            self.current_gamemode = mode_id
            self.setup_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        return callback

    async def cb_op(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
        send_console_command(f"op {self.player_name}")
        self.is_op = True
        self.setup_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def cb_deop(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
        send_console_command(f"deop {self.player_name}")
        self.is_op = False
        self.setup_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def cb_kick(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
        send_console_command(f"kick {self.player_name} Kicked by Server Administrator")
        self.is_online = False
        self.setup_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def cb_back(self, interaction: discord.Interaction):
        if interaction.message and interaction.message.id in active_panel_messages:
            active_panel_messages[interaction.message.id]["mode"] = "players"
        view = PlayerManagerView()
        embed = view.build_player_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PlayerSelectDropdown(discord.ui.Select):
    def __init__(self, players_list):
        options = []
        # Show online players first, then offline players
        for p in players_list[:25]:
            p_name = p.get("name", "Unknown")
            is_online = (p.get("status") == "online")
            is_op = p.get("is_op", False)
            
            emoji = "🟢" if is_online else "⚫"
            desc = f"{'ONLINE' if is_online else 'OFFLINE'}" + (" | OP Admin" if is_op else " | Player")
            
            options.append(discord.SelectOption(
                label=p_name,
                description=desc,
                emoji=emoji,
                value=p_name
            ))
            
        if not options:
            options.append(discord.SelectOption(
                label="No players registered yet",
                description="Join the server to appear here",
                value="none"
            ))

        super().__init__(placeholder="👉 Select a player to manage...", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
        
        selected_name = self.values[0]
        if selected_name == "none":
            return await interaction.response.send_message("ℹ️ No player selected.", ephemeral=True)
        
        stats = get_stats_data()
        all_players = stats.get("all_players_details", [])
        p_data = next((p for p in all_players if p.get("name") == selected_name), None)
        is_online = p_data.get("status") == "online" if p_data else False
        is_op = p_data.get("is_op", False) if p_data else False
        current_gamemode = p_data.get("gamemode", "survival") if p_data else "survival"
        
        view = PlayerActionsView(selected_name, is_online, is_op, current_gamemode)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PlayerManagerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        stats = get_stats_data()
        all_players = stats.get("all_players_details", [])
        self.add_item(PlayerSelectDropdown(all_players))

    def build_player_embed(self) -> discord.Embed:
        stats = get_stats_data()
        all_players = stats.get("all_players_details", [])
        online_players = [p for p in all_players if p.get("status") == "online"]
        offline_players = [p for p in all_players if p.get("status") != "online"]

        online_txt = " ".join([f"`{p.get('name')}`" for p in online_players]) if online_players else "*No players currently online.*"
        offline_txt = " ".join([f"`{p.get('name')}`" for p in offline_players[:15]]) if offline_players else "*No registered player history.*"

        embed = discord.Embed(
            title=f"👥 PLAYER ROSTER ({len(online_players)}/{stats['max_players']} Online)",
            description="Select any player from the dropdown below to change **Gamemode (Survival/Creative/Spectator)**, **OP / DE-OP**, or **Kick** them live.",
            color=discord.Color.from_rgb(230, 255, 0),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🟢 **ONLINE PLAYERS**", value=f"> {online_txt}\n\u200b", inline=False)
        embed.add_field(name="⚫ **OFFLINE / RECENT PLAYERS**", value=f"> {offline_txt}\n\u200b", inline=False)
        embed.set_footer(text="⚡ Valqore Player Manager • Select player below or click Back", icon_url="https://cdn-icons-png.flaticon.com/512/3208/3208726.png")
        return embed

    @discord.ui.button(label="Refresh Roster", style=discord.ButtonStyle.primary, emoji="🔄", row=1)
    async def btn_refresh_roster(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
        new_view = PlayerManagerView()
        embed = new_view.build_player_embed()
        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️", row=1)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.message and interaction.message.id in active_panel_messages:
            active_panel_messages[interaction.message.id]["mode"] = "options"
        embed = build_status_embed()
        embed.set_footer(text="⚙️ More Options Menu • Select an action below or click Back", icon_url="https://cdn-icons-png.flaticon.com/512/3208/3208726.png")
        await interaction.response.edit_message(embed=embed, view=MoreOptionsView())


class MoreOptionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Live Console", style=discord.ButtonStyle.primary, emoji="📜", custom_id="mc_btn_opt_live_console")
    async def btn_live_console(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
        if interaction.message and interaction.message.id in active_panel_messages:
            active_panel_messages[interaction.message.id]["mode"] = "console"
        logs = get_clean_logs(18)
        embed = discord.Embed(
            title="📜 LIVE MINECRAFT CONSOLE",
            description=f"```fix\n{logs}\n```",
            color=discord.Color.from_rgb(230, 255, 0),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="⚡ Valqore Live Console • Click Refresh to fetch latest lines", icon_url="https://cdn-icons-png.flaticon.com/512/3208/3208726.png")
        await interaction.response.edit_message(embed=embed, view=LiveConsoleView())

    @discord.ui.button(label="Player Controls", style=discord.ButtonStyle.secondary, emoji="👥", custom_id="mc_btn_opt_players")
    async def btn_opt_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
        if interaction.message and interaction.message.id in active_panel_messages:
            active_panel_messages[interaction.message.id]["mode"] = "players"
        view = PlayerManagerView()
        embed = view.build_player_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.danger, emoji="↩️", custom_id="mc_btn_opt_back")
    async def btn_opt_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.message and interaction.message.id in active_panel_messages:
            active_panel_messages[interaction.message.id]["mode"] = "main"
        embed = build_status_embed()
        await interaction.response.edit_message(embed=embed, view=ServerControlView())


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

    @discord.ui.button(label="More Options", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="mc_btn_more_options")
    async def btn_more_options(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ You do not have permission to manage this server.", ephemeral=True)
        if interaction.message and interaction.message.id in active_panel_messages:
            active_panel_messages[interaction.message.id]["mode"] = "options"
        embed = build_status_embed()
        embed.set_footer(text="⚙️ More Options Menu • Select an action below or click Back", icon_url="https://cdn-icons-png.flaticon.com/512/3208/3208726.png")
        await interaction.response.edit_message(embed=embed, view=MoreOptionsView())


# ==========================================
# BOT EVENTS & SILENT AUTO REFRESH LOOP
# ==========================================
@bot.event
async def on_ready():
    print(f"🤖 Bot Logged in as {bot.user.name} ({bot.user.id})")
    
    # 1. Sync updated commands directly to each connected guild for INSTANT schema update
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            synced_g = await bot.tree.sync(guild=guild)
            print(f"⚡ Guild {guild.name}: Synced {len(synced_g)} commands.")
        except Exception as e:
            print(f"Notice syncing {guild.name}: {e}")
            
    # 2. Sync global slash commands cleanly
    try:
        synced = await bot.tree.sync()
        print(f"✅ Cleanly synced {len(synced)} global slash commands.")
    except Exception as e:
        print(f"Global sync error: {e}")


    bot.add_view(ServerControlView())
    bot.add_view(MoreOptionsView())
    bot.add_view(LiveConsoleView())
    bot.add_view(PlayerManagerView())
    if not update_presence.is_running():
        update_presence.start()
    if not auto_refresh_panels.is_running():
        auto_refresh_panels.start()


@tasks.loop(seconds=5)
async def auto_refresh_panels():
    if not active_panel_messages:
        return
    try:
        dead_keys = []
        for key, info in list(active_panel_messages.items()):
            if isinstance(info, dict):
                msg = info.get("msg")
                mode = info.get("mode", "main")
            elif isinstance(info, (list, tuple)):
                msg = info[1]
                mode = "main"
            else:
                msg = info
                mode = "main"

            if not msg:
                dead_keys.append(key)
                continue

            try:
                if mode == "console":
                    logs = get_clean_logs(18)
                    c_embed = discord.Embed(
                        title="📜 LIVE MINECRAFT CONSOLE",
                        description=f"```fix\n{logs}\n```",
                        color=discord.Color.from_rgb(230, 255, 0),
                        timestamp=discord.utils.utcnow()
                    )
                    c_embed.set_footer(text="⚡ Valqore Live Console • Live Updating", icon_url="https://cdn-icons-png.flaticon.com/512/3208/3208726.png")
                    await msg.edit(embed=c_embed)
                elif mode in ["options", "players"]:
                    # Keep menus and player selection interactive
                    pass
                else:
                    # Main panel mode
                    m_embed = build_status_embed()
                    await msg.edit(embed=m_embed)
            except discord.NotFound:
                dead_keys.append(key)
            except:
                pass

        for k in dead_keys:
            active_panel_messages.pop(k, None)
    except:
        pass

@tasks.loop(seconds=5)
async def update_presence():
    try:
        stats = get_stats_data()
        
        # Check socket 25565 directly for 100% reliable online detection
        import socket
        socket_open = False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            socket_open = (s.connect_ex(('127.0.0.1', 25565)) == 0)
            s.close()
        except:
            pass

        is_online = stats["running"] or socket_open
        p_count = stats.get('players_count', 0)
        p_max = stats.get('max_players', 50)

        if is_online:
            activity = discord.Activity(
                type=discord.ActivityType.playing,
                name=f"Minecraft ({p_count}/{p_max} Online) 🎮"
            )
            await bot.change_presence(status=discord.Status.online, activity=activity)
        else:
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name="Server is Offline 🔴"
            )
            await bot.change_presence(status=discord.Status.idle, activity=activity)
    except Exception as e:
        pass

# ==========================================
# /setupmc SETUP & PAIRING COMMAND (SLASH & PREFIX)
# ==========================================
class SetupCodeModal(discord.ui.Modal, title="🔑 Authenticate Valqore Server"):
    def __init__(self, channel: discord.TextChannel, role: discord.Role):
        super().__init__()
        self.target_channel = channel
        self.target_role = role

    code_input = discord.ui.TextInput(
        label="6-Digit Authentication Code",
        placeholder="Enter 6-digit code from Web Panel (e.g. 849201)",
        min_length=6,
        max_length=6,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        success, result = await execute_setup_verification(
            interaction.guild,
            interaction.user,
            self.target_channel,
            self.target_role,
            self.code_input.value
        )
        if success:
            await interaction.followup.send(embed=result, ephemeral=True)
        else:
            await interaction.followup.send(result, ephemeral=True)

async def execute_setup_verification(guild, user, channel, role, code: str):
    """Core verification logic shared by slash command, modal, and prefix command."""
    clean_code = code.strip().upper()

    payload = {
        "code": clean_code,
        "guild_id": str(guild.id),
        "guild_name": guild.name,
        "channel_id": str(channel.id),
        "channel_name": channel.name,
        "role_id": str(role.id),
        "role_name": role.name,
        "admin_user": f"{user.name} ({user.id})"
    }

    res = call_api("bot/auth/verify", method="POST", data=payload)
    if not res:
        return False, "❌ Could not connect to Valqore Web Panel backend to verify code. Make sure your web panel is running on port 8090."

    if res.get("status") == "success":
        embed = discord.Embed(
            title="🛡️ VALQORE BOT AUTHENTICATED SUCCESSFULLY!",
            description=(
                f"✅ **{guild.name}** is now linked to your Valqore Minecraft VPS!\n\n"
                f"📌 **Restricted Channel:** {channel.mention}\n"
                f"👑 **Authorized Role:** {role.mention}\n"
                f"🔒 **Security Status:** `Active & Protected`\n\n"
                f"👉 Go to {channel.mention} and type **`/panel`** or **`!panel`** to summon your 24/7 Minecraft control center!"
            ),
            color=discord.Color.from_rgb(230, 255, 0),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3208/3208726.png")
        embed.set_footer(text="⚡ Valqore Security Gateway • Protected VPS Link")
        return True, embed
    else:
        err_msg = res.get("message", "Invalid or expired 6-digit code.")
        return False, f"❌ **Authentication Failed:** {err_msg}"

@bot.tree.command(name="setupmc", description="Authenticate & pair this Discord server with the Valqore Web Panel.")
@app_commands.describe(
    channel="The only text channel where Minecraft bot commands & panels are allowed",
    role="The staff/operator role allowed to use bot commands"
)
async def cmd_setupmc(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
    if not (interaction.user.guild_permissions.administrator or interaction.guild.owner_id == interaction.user.id):
        return await interaction.response.send_message("❌ Only Server Administrators or the Server Owner can pair this Discord server.", ephemeral=True)
    
    # Immediately pop up the clean interactive modal to enter the 6-digit code!
    await interaction.response.send_modal(SetupCodeModal(channel=channel, role=role))


@bot.command(name="setupmc")
async def p_setupmc(ctx, channel: discord.TextChannel = None, role: discord.Role = None, code: str = None):
    """Prefix command fallback: !setupmc #channel @Role 123456"""
    if not (ctx.author.guild_permissions.administrator or ctx.guild.owner_id == ctx.author.id):
        return await ctx.send("❌ Only Server Administrators or the Server Owner can pair this Discord server.")
    
    if not channel or not role or not code:
        return await ctx.send(
            "⚠️ **Incorrect Usage!**\n"
            "**Format:** `!setupmc #channel @Role 6_DIGIT_CODE`\n"
            "**Example:** `!setupmc #minecraft-control @Staff 839201`\n"
            "*Get your 6-digit pairing code in Web Panel > Settings > Approved Discord Servers.*"
        )
    
    # Try deleting the message containing the code for privacy
    try: await ctx.message.delete()
    except: pass

    success, result = await execute_setup_verification(ctx.guild, ctx.author, channel, role, code)
    if success:
        await ctx.send(embed=result)
    else:
        await ctx.send(result)

@bot.command(name="setup")
async def p_setup_alias(ctx, channel: discord.TextChannel = None, role: discord.Role = None, code: str = None):
    """Alias for !setupmc"""
    await p_setupmc(ctx, channel, role, code)




# ==========================================
# SLASH & PREFIX COMMANDS
# ==========================================
async def check_command_access(interaction_or_ctx) -> tuple[bool, str]:
    """Helper to check if command is allowed and provide helpful error reason."""
    guild = interaction_or_ctx.guild if hasattr(interaction_or_ctx, "guild") else None
    channel = interaction_or_ctx.channel if hasattr(interaction_or_ctx, "channel") else None
    user = interaction_or_ctx.user if hasattr(interaction_or_ctx, "user") else interaction_or_ctx.author

    if not guild:
        return False, "❌ Bot commands can only be used in an approved Discord server."

    is_auth, rule = check_guild_authorized(str(guild.id))
    if not is_auth:
        return False, "🔒 **Server Not Authorized!**\nThis bot is linked to a private Minecraft VPS.\nTo authenticate, an Administrator must run `/setupmc` with the 6-digit code found in your **Web Panel > Settings > Approved Servers**."

    allowed_channel_id = str(rule.get("channel_id", "")).strip()
    if allowed_channel_id and channel and str(channel.id) != allowed_channel_id:
        return False, f"⚠️ Bot commands are restricted to the designated channel: <#{allowed_channel_id}>"

    # Check role / admin
    if hasattr(user, "guild_permissions") and (user.guild_permissions.administrator or guild.owner_id == user.id):
        return True, ""

    allowed_role_id = str(rule.get("role_id", "")).strip()
    if allowed_role_id and hasattr(user, "roles"):
        if allowed_role_id in [str(r.id) for r in user.roles]:
            return True, ""
        return False, f"⛔ You must have the <@&{allowed_role_id}> role to use Minecraft control commands."

    return False, "❌ Access denied."


async def purge_old_panel_messages(channel):
    """Deletes all previous Valqore panel messages in the channel from memory and channel history."""
    # 1. Delete from in-memory tracking
    channel_id = channel.id
    to_delete = []
    for msg_id, info in list(active_panel_messages.items()):
        c_id = info.get("channel_id") if isinstance(info, dict) else (info[0] if isinstance(info, (list, tuple)) else None)
        msg_obj = info.get("msg") if isinstance(info, dict) else (info[1] if isinstance(info, (list, tuple)) else info)
        if c_id == channel_id:
            to_delete.append((msg_id, msg_obj))
    for msg_id, msg_obj in to_delete:
        try:
            if msg_obj: await msg_obj.delete()
        except: pass
        active_panel_messages.pop(msg_id, None)

    # 2. Comprehensive channel history scan (deletes any existing bot panel even after bot restarts)
    try:
        async for old_msg in channel.history(limit=50):
            if old_msg.author.id == bot.user.id and old_msg.embeds:
                for emb in old_msg.embeds:
                    if emb.title and ("VALQORE" in emb.title or "MINECRAFT ENGINE" in emb.title or "LIVE MINECRAFT CONSOLE" in emb.title):
                        try:
                            await old_msg.delete()
                            await asyncio.sleep(0.3)
                        except: pass
                        break
    except Exception as e:
        pass


@bot.tree.command(name="panel", description="Post the live Minecraft Control Panel (Silently auto-refreshed in real-time).")
async def cmd_panel(interaction: discord.Interaction):
    ok, err = await check_command_access(interaction)
    if not ok:
        return await interaction.response.send_message(err, ephemeral=True)
    await interaction.response.defer()

    # Clean up any existing panel messages in the channel
    if interaction.channel:
        await purge_old_panel_messages(interaction.channel)

    view = ServerControlView()
    embed = build_status_embed()
    msg = await interaction.followup.send(embed=embed, view=view)
    active_panel_messages[msg.id] = {"channel_id": interaction.channel_id, "msg": msg, "mode": "main"}


@bot.command(name="panel")
async def p_panel(ctx):
    ok, err = await check_command_access(ctx)
    if not ok:
        return await ctx.send(err)
    
    # Clean up any existing panel messages in the channel
    if ctx.channel:
        await purge_old_panel_messages(ctx.channel)

    # Delete the user's trigger message if bot has manage_messages permission
    try: await ctx.message.delete()
    except: pass

    view = ServerControlView()
    embed = build_status_embed()
    msg = await ctx.send(embed=embed, view=view)
    active_panel_messages[msg.id] = {"channel_id": ctx.channel.id, "msg": msg, "mode": "main"}

@bot.tree.command(name="status", description="Check live RAM, CPU, disk usage, and online players.")
async def cmd_status(interaction: discord.Interaction):
    ok, err = await check_command_access(interaction)
    if not ok:
        return await interaction.response.send_message(err, ephemeral=True)
    embed = build_status_embed()
    await interaction.response.send_message(embed=embed)

@bot.command(name="status")
async def p_status(ctx):
    ok, err = await check_command_access(ctx)
    if not ok:
        return await ctx.send(err)
    embed = build_status_embed()
    await ctx.send(embed=embed)

@bot.tree.command(name="ping", description="Check Discord Bot latency and server status.")
async def cmd_ping(interaction: discord.Interaction):
    ok, err = await check_command_access(interaction)
    if not ok:
        return await interaction.response.send_message(err, ephemeral=True)
    latency_ms = round(bot.latency * 1000)
    server_text = "🟢 Online" if is_server_running() else "🔴 Offline"
    embed = discord.Embed(title="🏓 Pong!", color=discord.Color.blue())
    embed.add_field(name="Discord API Latency", value=f"`{latency_ms} ms`", inline=True)
    embed.add_field(name="Minecraft Process", value=f"`{server_text}`", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.command(name="ping")
async def p_ping(ctx):
    ok, err = await check_command_access(ctx)
    if not ok:
        return await ctx.send(err)
    latency_ms = round(bot.latency * 1000)
    server_text = "🟢 Online" if is_server_running() else "🔴 Offline"
    embed = discord.Embed(title="🏓 Pong!", color=discord.Color.blue())
    embed.add_field(name="Discord API Latency", value=f"`{latency_ms} ms`", inline=True)
    embed.add_field(name="Minecraft Process", value=f"`{server_text}`", inline=True)
    await ctx.send(embed=embed)

@bot.tree.command(name="start", description="Start the Minecraft Server.")
async def cmd_start(interaction: discord.Interaction):
    ok, err = await check_command_access(interaction)
    if not ok:
        return await interaction.response.send_message(err, ephemeral=True)
    await interaction.response.defer()
    s_ok, msg = start_mc_server()
    await interaction.followup.send(msg)

@bot.command(name="start")
async def p_start(ctx):
    ok, err = await check_command_access(ctx)
    if not ok:
        return await ctx.send(err)
    s_ok, msg = start_mc_server()
    await ctx.send(msg)

@bot.tree.command(name="stop", description="Stop the Minecraft Server cleanly.")
async def cmd_stop(interaction: discord.Interaction):
    ok, err = await check_command_access(interaction)
    if not ok:
        return await interaction.response.send_message(err, ephemeral=True)
    await interaction.response.defer()
    s_ok, msg = stop_mc_server()
    await interaction.followup.send(msg)

@bot.command(name="stop")
async def p_stop(ctx):
    ok, err = await check_command_access(ctx)
    if not ok:
        return await ctx.send(err)
    s_ok, msg = stop_mc_server()
    await ctx.send(msg)

@bot.tree.command(name="restart", description="Restart the Minecraft Server.")
async def cmd_restart(interaction: discord.Interaction):
    ok, err = await check_command_access(interaction)
    if not ok:
        return await interaction.response.send_message(err, ephemeral=True)
    await interaction.response.defer()
    stop_mc_server()
    await asyncio.sleep(2)
    start_mc_server()
    await interaction.followup.send("🔄 Minecraft server is restarting...")

@bot.command(name="restart")
async def p_restart(ctx):
    ok, err = await check_command_access(ctx)
    if not ok:
        return await ctx.send(err)
    stop_mc_server()
    await asyncio.sleep(2)
    start_mc_server()
    await ctx.send("🔄 Minecraft server is restarting...")

@bot.tree.command(name="cmd", description="Execute any command on the Minecraft Server console (e.g. op, ban, gamemode).")
@app_commands.describe(command="The Minecraft command to run (without leading slash)")
async def cmd_console(interaction: discord.Interaction, command: str):
    ok, err = await check_command_access(interaction)
    if not ok:
        return await interaction.response.send_message(err, ephemeral=True)
    clean_cmd = command.strip().lstrip("/")
    s_ok, msg = send_console_command(clean_cmd)
    if s_ok:
        await interaction.response.send_message(f"💻 **Sent to Console:** `{clean_cmd}`\n*Allow 1-2 seconds for execution.*")
    else:
        await interaction.response.send_message(f"❌ {msg}", ephemeral=True)

@bot.command(name="cmd")
async def p_cmd(ctx, *, command: str = ""):
    ok, err = await check_command_access(ctx)
    if not ok:
        return await ctx.send(err)
    if not command:
        return await ctx.send("Usage: `!cmd <minecraft command>` (e.g. `!cmd op PlayerName`)")
    clean_cmd = command.strip().lstrip("/")
    s_ok, msg = send_console_command(clean_cmd)
    if s_ok:
        await ctx.send(f"💻 **Sent to Console:** `{clean_cmd}`")
    else:
        await ctx.send(f"❌ {msg}")

@bot.tree.command(name="players", description="View list of all online players.")
async def cmd_players(interaction: discord.Interaction):
    ok, err = await check_command_access(interaction)
    if not ok:
        return await interaction.response.send_message(err, ephemeral=True)
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
    ok, err = await check_command_access(ctx)
    if not ok:
        return await ctx.send(err)
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
    ok, err = await check_command_access(interaction)
    if not ok:
        return await interaction.response.send_message(err, ephemeral=True)
    log_count = min(max(5, lines or 20), 40)
    logs = get_latest_logs(log_count)
    if len(logs) > 1900:
        logs = logs[-1900:]
    await interaction.response.send_message(f"**📜 Console Output (Last {log_count} lines):**\n```\n{logs}\n```")

@bot.command(name="console")
async def p_console(ctx, lines: int = 20):
    ok, err = await check_command_access(ctx)
    if not ok:
        return await ctx.send(err)
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
