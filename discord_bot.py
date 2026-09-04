import os
import sys
import time
import asyncio
import subprocess
import shutil
import json
import re
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

# ==========================================
# CONFIGURATION
# ==========================================
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
# SERVER CONTROLLER HELPER FUNCTIONS
# ==========================================
def get_mc_processes():
    global MC_PROCESS
    found_procs = []
    if MC_PROCESS and MC_PROCESS.poll() is None:
        try:
            parent = psutil.Process(MC_PROCESS.pid)
            found_procs.append(parent)
            found_procs.extend(parent.children(recursive=True))
        except Exception:
            pass

    if psutil:
        try:
            current_pid = os.getpid()
            mc_dir_clean = os.path.abspath(MC_DIR).lower()
            for p in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
                try:
                    if p.pid == current_pid:
                        continue
                    cmdline = p.info.get('cmdline') or []
                    cmd_str = " ".join(cmdline).lower()
                    cwd = (p.info.get('cwd') or "").lower()
                    name = (p.info.get('name') or "").lower()
                    
                    if "server.jar" in cmd_str or ("java" in name and (mc_dir_clean in cwd or "minecraft" in cmd_str or "paper" in cmd_str or "purpur" in cmd_str or "fabric" in cmd_str or "forge" in cmd_str)):
                        if p.pid not in [x.pid for x in found_procs]:
                            found_procs.append(p)
                            found_procs.extend([c for c in p.children(recursive=True) if c.pid not in [x.pid for x in found_procs]])
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass
    return found_procs

def is_server_running() -> bool:
    global MC_PROCESS
    if shutil.which("tmux"):
        try:
            subprocess.check_output(["tmux", "has-session", "-t", "mc_server"], stderr=subprocess.STDOUT)
            return True
        except:
            pass
    if MC_PROCESS and MC_PROCESS.poll() is None:
        return True
    procs = get_mc_processes()
    return len(procs) > 0

def start_mc_server():
    global MC_PROCESS
    if is_server_running():
        return False, "Minecraft server is already running!"

    start_script = os.path.join(MC_DIR, "start.sh")
    server_jar = os.path.join(MC_DIR, "server.jar")

    if not os.path.exists(start_script) and os.path.exists(server_jar):
        optimized_sh = """#!/bin/bash
java -Xms10240M -Xmx10240M \\
  --add-modules=jdk.incubator.vector \\
  -Djava.net.preferIPv4Stack=true \\
  -XX:+UseG1GC \\
  -XX:+ParallelRefProcEnabled \\
  -XX:MaxGCPauseMillis=200 \\
  -XX:+UnlockExperimentalVMOptions \\
  -XX:+DisableExplicitGC \\
  -XX:+AlwaysPreTouch \\
  -XX:G1NewSizePercent=30 \\
  -XX:G1MaxNewSizePercent=40 \\
  -XX:G1ReservePercent=20 \\
  -XX:G1HeapWastePercent=5 \\
  -XX:G1MixedGCCountTarget=4 \\
  -XX:InitiatingHeapOccupancyPercent=15 \\
  -XX:G1MixedGCLiveThresholdPercent=90 \\
  -XX:G1RSetUpdatingPauseTimePercent=5 \\
  -XX:SurvivorRatio=32 \\
  -XX:+PerfDisableSharedMem \\
  -XX:MaxTenuringThreshold=1 \\
  -Dusing.aikars.flags=https://mcflags.emc.gs \\
  -Daikars.new.flags=true \\
  -jar server.jar nogui
"""
        with open(start_script, "w") as f:
            f.write(optimized_sh)
        os.chmod(start_script, 0o755)

    if not os.path.exists(start_script) and not os.path.exists(server_jar):
        return False, "No server installed! `server.jar` or `start.sh` missing in `mc_server/`."

    eula_path = os.path.join(MC_DIR, "eula.txt")
    if not os.path.exists(eula_path):
        with open(eula_path, "w") as f:
            f.write("eula=true\n")

    for world_folder in ["world", "world_nether", "world_the_end"]:
        lock_file = os.path.join(MC_DIR, world_folder, "session.lock")
        if os.path.exists(lock_file):
            try: os.remove(lock_file)
            except: pass

    os.makedirs(os.path.join(MC_DIR, "logs"), exist_ok=True)
    open(LOG_PATH, "w").close()

    bash_bin = shutil.which("bash") or "/bin/bash"
    tmux_bin = shutil.which("tmux") or "/usr/bin/tmux"
    java_bin = shutil.which("java") or "/usr/bin/java"

    if os.path.exists(start_script) and os.path.exists(bash_bin):
        run_cmd_str = f"{bash_bin} {start_script}"
        cmd = [bash_bin, start_script]
    else:
        run_cmd_str = f"{java_bin} -Xms1G -Xmx2G -jar {server_jar} nogui"
        cmd = [java_bin, "-Xms1G", "-Xmx2G", "-jar", server_jar, "nogui"]

    env = os.environ.copy()
    env["PATH"] = f"/usr/bin:/bin:/usr/local/bin:{env.get('PATH', '')}"

    if shutil.which("tmux"):
        try:
            subprocess.run(["tmux", "kill-session", "-t", "mc_server"], stderr=subprocess.DEVNULL)
        except:
            pass
        tmux_cmd = f"cd '{MC_DIR}' && {run_cmd_str} 2>&1 | tee -a '{LOG_PATH}'"
        subprocess.Popen(["tmux", "new-session", "-d", "-s", "mc_server", "bash", "-c", tmux_cmd], env=env)
    else:
        log_file = open(LOG_PATH, "a", buffering=1)
        MC_PROCESS = subprocess.Popen(
            cmd,
            cwd=MC_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            env=env
        )

    return True, "🚀 Minecraft server boot initiated!"

def stop_mc_server():
    global MC_PROCESS
    if shutil.which("tmux"):
        try:
            subprocess.run(["tmux", "send-keys", "-t", "mc_server", "stop", "ENTER"], stderr=subprocess.DEVNULL)
        except:
            pass
    elif MC_PROCESS and MC_PROCESS.stdin:
        try:
            MC_PROCESS.stdin.write(b"stop\n")
            MC_PROCESS.stdin.flush()
        except:
            pass

    time.sleep(2)

    if MC_PROCESS:
        try:
            MC_PROCESS.terminate()
            MC_PROCESS.kill()
        except:
            pass
        MC_PROCESS = None

    if psutil:
        try:
            procs = get_mc_processes()
            for p in procs:
                try: p.terminate()
                except: pass
            time.sleep(0.5)
            for p in procs:
                try: p.kill()
                except: pass
        except:
            pass

    if shutil.which("tmux"):
        try:
            subprocess.run(["tmux", "kill-session", "-t", "mc_server"], stderr=subprocess.DEVNULL)
        except:
            pass

    for world_folder in ["world", "world_nether", "world_the_end"]:
        lock_file = os.path.join(MC_DIR, world_folder, "session.lock")
        if os.path.exists(lock_file):
            try: os.remove(lock_file)
            except: pass

    return True, "🛑 Minecraft server stopped."

def send_console_command(cmd: str):
    if not is_server_running():
        return False, "Server is offline. Cannot execute command."

    sent = False
    if shutil.which("tmux"):
        try:
            check = subprocess.run(["tmux", "has-session", "-t", "mc_server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if check.returncode == 0:
                subprocess.run(["tmux", "send-keys", "-t", "mc_server", cmd, "ENTER"], check=True)
                sent = True
        except:
            pass

    if not sent and MC_PROCESS and MC_PROCESS.stdin and MC_PROCESS.poll() is None:
        try:
            MC_PROCESS.stdin.write(f"{cmd}\n".encode())
            MC_PROCESS.stdin.flush()
            sent = True
        except Exception as e:
            return False, f"Error: {e}"

    if sent:
        return True, f"Command sent: `{cmd}`"
    return False, "Failed to send command to console."

def get_stats_data():
    running = is_server_running()
    ram_percent = 0
    ram_used_mb = 0
    allocated_ram_mb = 10240
    cpu_percent = 0
    cpu_cores = 2
    disk_percent = 0

    if psutil:
        try:
            v_mem = psutil.virtual_memory()
            ram_total_mb = int(v_mem.total / (1024 * 1024))
            cpu_cores = psutil.cpu_count(logical=True) or 2
            disk_percent = int(psutil.disk_usage('/').percent)

            mc_procs = get_mc_processes() if running else []
            total_cpu_val = 0.0

            start_sh = os.path.join(MC_DIR, "start.sh")
            if os.path.exists(start_sh):
                try:
                    with open(start_sh, "r", encoding="utf-8", errors="ignore") as f:
                        m = re.search(r"-Xmx(\d+)([MGmg])", f.read())
                        if m:
                            val = int(m.group(1))
                            unit = m.group(2).upper()
                            allocated_ram_mb = val * 1024 if unit == "G" else val
                except:
                    pass

            if mc_procs:
                for p in mc_procs:
                    try:
                        ram_used_mb += int(p.memory_info().rss / (1024 * 1024))
                        p_cpu = p.cpu_percent(interval=None)
                        if p_cpu and p_cpu > 0:
                            total_cpu_val += p_cpu
                    except:
                        continue
                target_ram = allocated_ram_mb if allocated_ram_mb > 0 else ram_total_mb
                ram_percent = max(0, min(100, int((ram_used_mb / max(1, target_ram)) * 100)))
                cpu_percent = max(0, min(100, int(total_cpu_val / max(1, cpu_cores))))
                if ram_used_mb > 50 and ram_percent == 0:
                    ram_percent = 1
        except:
            pass

    online_players = []
    if running and os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            active_set = set()
            for line in lines[-500:]:
                clean = line.strip()
                if "joined the game" in clean:
                    u = clean.split("joined the game")[0].split("]:")[-1].strip()
                    if u and not u.startswith("/") and len(u.split()) == 1:
                        active_set.add(u)
                elif "logged in with entity id" in clean:
                    p = clean.split("]:")[-1].strip().split("[")[0].strip()
                    if p and len(p.split()) == 1 and not p.startswith("/"):
                        active_set.add(p)
                elif "left the game" in clean:
                    u = clean.split("left the game")[0].split("]:")[-1].strip()
                    if u in active_set: active_set.remove(u)
                elif "lost connection:" in clean or "lost connection" in clean:
                    u = clean.split("lost connection")[0].split("]:")[-1].strip()
                    if u in active_set: active_set.remove(u)
                elif "players online:" in clean:
                    n_part = clean.split("players online:")[-1].strip()
                    if n_part:
                        for n in n_part.split(','):
                            cn = n.strip()
                            if cn: active_set.add(cn)
            online_players = list(active_set)
        except:
            pass

    max_players = 50
    props = os.path.join(MC_DIR, "server.properties")
    if os.path.exists(props):
        try:
            with open(props, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("max-players="):
                        max_players = int(line.split("=")[1].strip())
        except:
            pass

    return {
        "running": running,
        "ram_percent": ram_percent,
        "ram_used_mb": ram_used_mb,
        "ram_allocated_mb": allocated_ram_mb,
        "cpu_percent": cpu_percent,
        "disk_percent": disk_percent,
        "online_players": online_players,
        "players_count": len(online_players),
        "max_players": max_players
    }

def get_latest_logs(lines_count=20) -> str:
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                if lines:
                    return "".join(lines[-lines_count:])
        except:
            pass

    tmux_bin = shutil.which("tmux")
    if tmux_bin:
        try:
            out = subprocess.check_output([tmux_bin, "capture-pane", "-pt", "mc_server", "-S", f"-{lines_count}"], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
            if out.strip():
                return out
        except:
            pass

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

def build_status_embed() -> discord.Embed:
    stats = get_stats_data()
    status_text = "🟢 **Online**" if stats["running"] else "🔴 **Offline**"
    color = discord.Color.green() if stats["running"] else discord.Color.red()

    embed = discord.Embed(
        title="⚡ Valqore Minecraft Control Center",
        description=f"**Server Status:** {status_text}\n*(Live auto-refresh active)*",
        color=color,
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(name="🧠 RAM Usage", value=f"`{stats['ram_used_mb']} MB` / `{stats['ram_allocated_mb']} MB` ({stats['ram_percent']}%)", inline=True)
    embed.add_field(name="⚙️ CPU Load", value=f"`{stats['cpu_percent']}%`", inline=True)
    embed.add_field(name="💾 Disk Usage", value=f"`{stats['disk_percent']}%`", inline=True)

    player_list_str = ", ".join(stats["online_players"]) if stats["online_players"] else "*None*"
    embed.add_field(name=f"👥 Players ({stats['players_count']}/{stats['max_players']})", value=player_list_str, inline=False)
    embed.set_footer(text="⚡ Auto-updates silently every 5s")
    return embed

# ==========================================
# INTERACTIVE CONTROL PANEL VIEW (BUTTONS)
# ==========================================
class ServerControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Start", style=discord.ButtonStyle.success, emoji="▶️", custom_id="mc_btn_start")
    async def btn_start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ You do not have permission to manage this server.", ephemeral=True)
        # Edit message immediately without sending popup notification
        ok, msg = start_mc_server()
        await interaction.response.edit_message(embed=build_status_embed(), view=self)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️", custom_id="mc_btn_stop")
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ You do not have permission to manage this server.", ephemeral=True)
        ok, msg = stop_mc_server()
        await interaction.response.edit_message(embed=build_status_embed(), view=self)

    @discord.ui.button(label="Restart", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="mc_btn_restart")
    async def btn_restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ You do not have permission to manage this server.", ephemeral=True)
        # Silent restart update
        await interaction.response.edit_message(embed=build_status_embed(), view=self)
        stop_mc_server()
        await asyncio.sleep(2)
        start_mc_server()
        try:
            await interaction.message.edit(embed=build_status_embed(), view=self)
        except:
            pass

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔃", custom_id="mc_btn_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Silent 1-click refresh without ephemeral popup or ping
        await interaction.response.edit_message(embed=build_status_embed(), view=self)

    @discord.ui.button(label="Live Logs", style=discord.ButtonStyle.secondary, emoji="📜", custom_id="mc_btn_logs")
    async def btn_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        logs = get_latest_logs(15)
        if len(logs) > 1900:
            logs = logs[-1900:]
        await interaction.response.send_message(f"**📜 Recent Console Logs:**\n```ansi\n{logs}\n```", ephemeral=True)

# ==========================================
# BOT EVENTS & AUTO REFRESH LOOP
# ==========================================
@bot.event
async def on_ready():
    print(f"🤖 Bot Logged in as {bot.user.name} ({bot.user.id})")
    
    # Clean up any duplicate guild-specific commands so only single global commands exist
    for guild in bot.guilds:
        try:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
        except Exception:
            pass
            
    # Sync single global slash commands
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
    """Silently auto-refreshes all active Discord panel cards in real-time."""
    if not active_panel_messages:
        return
    
    try:
        embed = build_status_embed()
        dead_keys = []
        for key, msg in list(active_panel_messages.items()):
            try:
                await msg.edit(embed=embed)
            except discord.NotFound:
                dead_keys.append(key)
            except Exception:
                pass
        for k in dead_keys:
            active_panel_messages.pop(k, None)
    except Exception:
        pass

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
    except:
        pass

# ==========================================
# SLASH & PREFIX COMMANDS
# ==========================================
@bot.tree.command(name="panel", description="Post the live Minecraft Control Panel (Silently auto-refreshed in real-time).")
async def cmd_panel(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You need Admin permissions to post the control panel.", ephemeral=True)
    view = ServerControlView()
    embed = build_status_embed()
    await interaction.response.send_message(embed=embed, view=view)
    msg = await interaction.original_response()
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

@bot.command(name="sync")
async def p_sync(ctx):
    if not is_admin(ctx):
        return await ctx.send("❌ Admin permissions required.")
    bot.tree.copy_global_to(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("✅ Slash commands successfully synced to this server!")

if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not BOT_TOKEN:
        print("❌ ERROR: DISCORD_BOT_TOKEN missing in .env")
        sys.exit(1)
    bot.run(BOT_TOKEN)
