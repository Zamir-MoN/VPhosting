import os
import subprocess
import shutil
import time
import requests
import asyncio
import random
import zipfile
import json
try:
    import psutil
except ImportError:
    psutil = None

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from mcrcon import MCRcon
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

MC_DIR = os.path.abspath("./mc_server")
BACKUP_DIR = os.path.abspath("./backups")
TOKEN_FILE = os.path.abspath("token.json")
CLIENT_SECRET_FILE = os.path.abspath("client_secrets.json")
TRASH_DIR = os.path.abspath(".trash")
os.makedirs(TRASH_DIR, exist_ok=True)

SCOPES = ['https://www.googleapis.com/auth/drive.file']

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background tasks
    asyncio.create_task(auto_backup_task())
    yield
    # Shutdown: Clean up if needed
    pass

app = FastAPI(title="Delta X Panel API", lifespan=lifespan)

from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print("--- GLOBAL ERROR ---")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": f"Server error: {str(exc)}"}
    )

# Configuration
MC_PROCESS = None
RCON_HOST = "127.0.0.1"
RCON_PORT = 25575
RCON_PASS = "your_rcon_password"

# Mock state for backup countdown
LAST_BACKUP_TIME = time.time()
BACKUP_INTERVAL = 24 * 3600 # 24 hours in seconds

os.makedirs(MC_DIR, exist_ok=True)
os.makedirs(os.path.join(MC_DIR, "plugins"), exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")

def get_safe_path(base_dir, requested_path):
    safe_path = os.path.abspath(os.path.join(base_dir, requested_path.strip('/')))
    if not safe_path.startswith(base_dir): raise HTTPException(status_code=403, detail="Access denied")
    return safe_path

async def upload_to_gdrive(file_path, file_name):
    if not os.path.exists(TOKEN_FILE):
        return False
    
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': file_name}
        media = MediaFileUpload(file_path, mimetype='application/zip')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return True
    except Exception as e:
        print(f"GDrive Upload Error: {e}")
        return False

# --- AUTO BACKUP SCHEDULER ---
async def auto_backup_task():
    global LAST_BACKUP_TIME
    while True:
        await asyncio.sleep(3600) # Check every hour
        if time.time() - LAST_BACKUP_TIME >= BACKUP_INTERVAL:
            print("Auto-backing up...")
            world_path = os.path.join(MC_DIR, "world")
            if os.path.exists(world_path):
                zip_name = f"auto_backup_{int(time.time())}.zip"
                zip_path = os.path.join(BACKUP_DIR, zip_name)
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(world_path):
                        for file in files:
                            zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), os.path.join(world_path, '..')))
                
                # Try upload if connected
                uploaded = await upload_to_gdrive(zip_path, zip_name)
                
                # Cleanup local zip
                if uploaded or True: # Cleanup regardless to save space
                    if os.path.exists(zip_path): os.remove(zip_path)
            
            LAST_BACKUP_TIME = time.time()

# --- STATUS & POWER MANAGEMENT ---
@app.get("/api/ping")
def ping_server():
    return {"status": "ok", "timestamp": time.time()}

@app.get("/api/status")
def check_status():
    is_installed = os.path.exists(os.path.join(MC_DIR, "start.sh")) or os.path.exists(os.path.join(MC_DIR, "server.jar"))
    return {"installed": is_installed}


@app.get("/api/stats")
def get_stats():
    is_running = is_server_running()
    
    # Measure Minecraft Process Specific Metrics vs Host System
    try:
        import psutil
        v_mem = psutil.virtual_memory()
        ram_total_mb = int(v_mem.total / (1024 * 1024))
        cpu_cores = psutil.cpu_count(logical=True) or 2
        disk_usage = psutil.disk_usage('/')
        disk = int(disk_usage.percent)
        
        mc_procs = get_mc_processes() if is_running else []
        ram_used_mb = 0
        total_cpu_val = 0.0
        allocated_ram_mb = 10240 # Default to 10GB configured Minecraft server RAM
        
        # Check start.sh for configured -Xmx value
        start_sh_file = os.path.join(MC_DIR, "start.sh")
        if os.path.exists(start_sh_file):
            try:
                with open(start_sh_file, "r", encoding="utf-8", errors="ignore") as sf:
                    sh_content = sf.read()
                    import re
                    match = re.search(r"-Xmx(\d+)([MGmg])", sh_content)
                    if match:
                        num = int(match.group(1))
                        unit = match.group(2).upper()
                        if unit == "G":
                            allocated_ram_mb = num * 1024
                        elif unit == "M":
                            allocated_ram_mb = num
            except:
                pass
        
        if mc_procs:
            for p in mc_procs:
                try:
                    # Sum RAM across processes (in MB)
                    ram_used_mb += int(p.memory_info().rss / (1024 * 1024))
                    
                    # Read CPU percent
                    p_cpu = p.cpu_percent(interval=None)
                    if p_cpu is not None and p_cpu > 0:
                        total_cpu_val += p_cpu
                        
                    # Check running process cmdline for -Xmx override
                    cmdline = p.cmdline() if callable(getattr(p, 'cmdline', None)) else []
                    for arg in cmdline:
                        if arg.startswith("-Xmx"):
                            val_str = arg[4:].strip().upper()
                            if val_str.endswith("G"):
                                allocated_ram_mb = int(float(val_str[:-1]) * 1024)
                            elif val_str.endswith("M"):
                                allocated_ram_mb = int(float(val_str[:-1]))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Calculate RAM usage % relative to allocated RAM (or total RAM)
            target_max_ram = allocated_ram_mb if allocated_ram_mb > 0 else ram_total_mb
            ram = max(0, min(100, int((ram_used_mb / max(1, target_max_ram)) * 100)))
            
            # Scale CPU % to overall system usage (0 - 100%)
            cpu = max(0, min(100, int(total_cpu_val / max(1, cpu_cores))))
            
            # If server is reported running and active, ensure at least 1% is displayed if active
            if ram_used_mb > 50 and ram == 0:
                ram = 1
        else:
            ram_used_mb = 0
            ram = 0
            cpu = 0
    except Exception as e:
        ram_total_mb = 2048
        allocated_ram_mb = 2048
        ram_used_mb = 0
        ram = 0
        cpu = 0
        cpu_cores = 2
        disk = 0
    
    # Calculate backup countdown
    connected = os.path.exists(TOKEN_FILE)
    if connected:
        elapsed = time.time() - LAST_BACKUP_TIME
        remaining = max(0, BACKUP_INTERVAL - elapsed)
        backup_percent = min(100, int((elapsed / BACKUP_INTERVAL) * 100))
    else:
        remaining = -1
        backup_percent = 0
    
    # Get Online Players by reading latest.log events cleanly without console command spam
    online_players = []
    if is_running:
        log_path = os.path.join(MC_DIR, "logs", "latest.log")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    
                current_active = set()
                for line in lines[-500:]:
                    clean_line = line.strip()
                    # 1. Join patterns
                    if "joined the game" in clean_line:
                        # e.g. [12:00:00 INFO]: ZAMIR909 joined the game
                        user = clean_line.split("joined the game")[0].split("]:")[-1].strip()
                        if user and not user.startswith("/") and len(user.split()) == 1:
                            current_active.add(user)
                    elif "logged in with entity id" in clean_line:
                        # e.g. [12:00:00 INFO]: UUID of player ZAMIR909 is ... OR ZAMIR909[/127.0.0.1:12345] logged in
                        parts = clean_line.split("]:")[-1].strip().split("[")[0].strip()
                        if parts and len(parts.split()) == 1 and not parts.startswith("/"):
                            current_active.add(parts)
                    # 2. Leave / Disconnect patterns
                    elif "left the game" in clean_line:
                        user = clean_line.split("left the game")[0].split("]:")[-1].strip()
                        if user in current_active:
                            current_active.remove(user)
                    elif "lost connection:" in clean_line or "lost connection" in clean_line:
                        user = clean_line.split("lost connection")[0].split("]:")[-1].strip()
                        if user in current_active:
                            current_active.remove(user)
                    elif "Disconnecting " in clean_line:
                        parts = clean_line.split("Disconnecting ")[-1].split(":")[0].strip()
                        if parts in current_active:
                            current_active.remove(parts)
                    # 3. Direct player list output (e.g. from /list)
                    elif "players online:" in clean_line:
                        names_part = clean_line.split("players online:")[-1].strip()
                        if names_part:
                            for n in names_part.split(','):
                                clean_n = n.strip()
                                if clean_n: current_active.add(clean_n)

                online_players = list(current_active)
            except Exception as e:
                pass
    
    # Get All Players (History)
    all_players = []
    cache_path = os.path.join(MC_DIR, "usercache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
                all_players = [entry['name'] for entry in cache_data]
        except: pass

    # Read ops list
    op_names = set()
    ops_path = os.path.join(MC_DIR, "ops.json")
    if os.path.exists(ops_path):
        try:
            with open(ops_path, "r", encoding="utf-8", errors="ignore") as f:
                op_data = json.load(f)
                for op in op_data:
                    if isinstance(op, dict) and "name" in op:
                        op_names.add(op["name"].lower())
                    elif isinstance(op, str):
                        op_names.add(op.lower())
        except:
            pass

    # Read banned players list
    banned_names = set()
    banned_path = os.path.join(MC_DIR, "banned-players.json")
    if os.path.exists(banned_path):
        try:
            with open(banned_path, "r", encoding="utf-8", errors="ignore") as f:
                ban_data = json.load(f)
                for b in ban_data:
                    if isinstance(b, dict) and "name" in b:
                        banned_names.add(b["name"].lower())
                    elif isinstance(b, str):
                        banned_names.add(b.lower())
        except:
            pass

    # Read default gamemode from server.properties
    default_gamemode = "survival"
    max_players = 50
    props_path = os.path.join(MC_DIR, "server.properties")
    if os.path.exists(props_path):
        try:
            with open(props_path, 'r') as f:
                for line in f:
                    if line.startswith("max-players="):
                        max_players = int(line.split("=")[1].strip())
                    elif line.startswith("gamemode="):
                        default_gamemode = line.split("=")[1].strip().lower()
        except: pass

    # Build rich player objects
    rich_online_players = []
    for name in online_players:
        rich_online_players.append({
            "name": name,
            "status": "online",
            "is_op": name.lower() in op_names,
            "is_banned": name.lower() in banned_names,
            "gamemode": default_gamemode
        })

    rich_all_players = []
    for name in all_players:
        rich_all_players.append({
            "name": name,
            "status": "online" if name in online_players else "offline",
            "is_op": name.lower() in op_names,
            "is_banned": name.lower() in banned_names,
            "gamemode": default_gamemode
        })

    # Detect configured public IP of VPS or custom domain
    custom_ip = os.getenv("SERVER_IP")
    if custom_ip:
        vps_ip = custom_ip
    else:
        vps_ip = "play.valqore-arcane-smp.ryzn.pro"

    # Detect engine and version
    detected_engine = "Purpur"
    detected_version = "1.21.1"
    log_file_path = os.path.join(MC_DIR, "logs", "latest.log")
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                header_lines = f.readlines()[:120]
                for line in header_lines:
                    if "(MC:" in line:
                        mc_match = re.search(r"\(MC:\s*([0-9]+\.[0-9]+(?:\.[0-9]+)?)\)", line, re.IGNORECASE)
                        if mc_match:
                            detected_version = mc_match.group(1)
                    elif "Starting minecraft server version" in line:
                        v_match = re.search(r"version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", line, re.IGNORECASE)
                        if v_match:
                            detected_version = v_match.group(1)
                    if "This server is running" in line or "Starting minecraft server" in line:
                        if "Purpur" in line: detected_engine = "Purpur"
                        elif "Paper" in line: detected_engine = "Paper"
                        elif "Fabric" in line: detected_engine = "Fabric"
                        elif "Forge" in line: detected_engine = "Forge"
                        elif "Spigot" in line: detected_engine = "Spigot"
        except:
            pass

    # Clean version string from any build hash artifacts
    v_clean = re.search(r"([0-9]+\.[0-9]+(?:\.[0-9]+)?)", str(detected_version))
    if v_clean:
        detected_version = v_clean.group(1)

    detailed_status = get_server_detailed_state()
    
    # Calculate real Minecraft Server Ping via Domain Handshake
    server_ping_ms = 0
    if is_running or detailed_status == "online":
        import socket
        target_host = "play.valqore-arcane-smp.ryzn.pro"
        for host_to_ping in [target_host, "127.0.0.1"]:
            try:
                t0 = time.perf_counter()
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.2)
                s.connect((host_to_ping, 25565))
                # Minecraft SLP Handshake packet
                host_bytes = host_to_ping.encode('utf-8')
                payload = b'\x00\x00' + bytes([len(host_bytes)]) + host_bytes + b'\x63\xdd\x01'
                packet = bytes([len(payload)]) + payload + b'\x01\x00'
                s.sendall(packet)
                resp = s.recv(512)
                s.close()
                if resp:
                    elapsed = (time.perf_counter() - t0) * 1000
                    server_ping_ms = max(10, round(elapsed))
                    break
            except:
                continue

    return {
        "status": detailed_status,
        "cpu_percent": cpu,
        "cpu_cores": cpu_cores,
        "ram_percent": ram,
        "ram_used_mb": ram_used_mb,
        "ram_total_mb": ram_total_mb,
        "ram_allocated_mb": allocated_ram_mb,
        "disk_percent": disk,
        "players_online": len(online_players),
        "max_players": max_players,
        "server_ping_ms": server_ping_ms,
        "backup_countdown": int(remaining),
        "backup_percent": backup_percent,
        "online_players": rich_online_players,
        "all_players": rich_all_players,
        "public_ip": vps_ip,
        "server_ip": vps_ip,
        "engine": detected_engine,
        "version": detected_version
    }


@app.get("/api/backup/manual")
async def manual_backup(background_tasks: BackgroundTasks):
    world_path = os.path.join(MC_DIR, "world")
    if not os.path.exists(world_path):
        return {"status": "error", "message": "World folder not found."}
    
    zip_name = f"manual_backup_{int(time.time())}.zip"
    zip_path = os.path.join(BACKUP_DIR, zip_name)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(world_path):
            for file in files:
                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), os.path.join(world_path, '..')))
    
    def cleanup():
        time.sleep(60)
        if os.path.exists(zip_path):
            os.remove(zip_path)
            
    background_tasks.add_task(cleanup)
    return FileResponse(zip_path, filename=zip_name)

@app.get("/api/gdrive/auth")
async def gdrive_auth(request: Request):
    if not os.path.exists(CLIENT_SECRET_FILE):
        return {"status": "error", "message": "Google Client Secret file missing. Please upload client_secrets.json to the VPS."}
    
    try:
        with open(CLIENT_SECRET_FILE, 'r') as f:
            client_data = json.load(f)
            key = 'web' if 'web' in client_data else 'installed'
            client_id = client_data[key]['client_id']

        # Construct "Classic" Auth URL without PKCE
        auth_base = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": client_id,
            "redirect_uri": "http://localhost:8090/api/gdrive/callback",
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent"
        }
        from urllib.parse import urlencode
        auth_url = f"{auth_base}?{urlencode(params)}"
        return {"status": "success", "url": auth_url}
    except Exception as e:
        return {"status": "error", "message": f"Auth generation failed: {str(e)}"}

@app.post("/api/gdrive/verify")
async def gdrive_verify(request: Request):
    data = await request.json()
    code = data.get("code")
    if not code: return {"status": "error", "message": "Code missing."}
    
    if not os.path.exists(CLIENT_SECRET_FILE):
        return {"status": "error", "message": "Client secret file missing."}

    try:
        with open(CLIENT_SECRET_FILE, 'r') as f:
            client_data = json.load(f)
            # Handle both 'web' and 'installed' types
            key = 'web' if 'web' in client_data else 'installed'
            client_id = client_data[key]['client_id']
            client_secret = client_data[key]['client_secret']

        # Manual exchange using requests for stateless reliability
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": "http://localhost:8090/api/gdrive/callback",
            "grant_type": "authorization_code"
        }
        
        res = requests.post(token_url, data=payload)
        token_data = res.json()
        
        if "error" in token_data:
            return {"status": "error", "message": f"Google Error: {token_data.get('error_description', 'Unknown error')}"}
            
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f)
            
        return {"status": "success", "message": "Google Drive linked successfully!"}
    except Exception as e:
        return {"status": "error", "message": f"Verification failed: {str(e)}"}


@app.get("/api/gdrive/callback")
async def gdrive_callback(request: Request, code: str):
    success_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Authorization Successful</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;900&display=swap" rel="stylesheet">
        <style>
            body {{ background: #0a0c10; color: white; font-family: 'Inter', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; overflow: hidden; }}
            .card {{ background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); padding: 40px; border-radius: 24px; text-align: center; max-width: 400px; width: 90%; backdrop-filter: blur(20px); box-shadow: 0 20px 50px rgba(0,0,0,0.5); }}
            h1 {{ font-weight: 900; margin-bottom: 10px; background: linear-gradient(135deg, #ff007f, #ff4c4c); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
            p {{ color: #a0abb8; font-size: 0.9rem; margin-bottom: 30px; }}
            .code-box {{ background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); padding: 15px; border-radius: 12px; font-family: monospace; font-size: 1rem; word-break: break-all; margin-bottom: 20px; color: #00ff7f; position: relative; }}
            button {{ background: #ff007f; color: white; border: none; padding: 12px 30px; border-radius: 12px; font-weight: bold; cursor: pointer; transition: 0.3s; width: 100%; }}
            button:hover {{ transform: scale(1.02); background: #ff3399; box-shadow: 0 0 20px rgba(255,0,127,0.4); }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Success!</h1>
            <p>Your Google account is authorized. Copy the code below and paste it into your MCPanel.</p>
            <div class="code-box" id="code">{{code}}</div>
            <button onclick="copyCode()">Copy to Clipboard</button>
        </div>
        <script>
            function copyCode() {{
                const code = document.getElementById('code').innerText;
                navigator.clipboard.writeText(code);
                const btn = document.querySelector('button');
                btn.innerText = 'COPIED!';
                btn.style.background = '#00ff7f';
                setTimeout(() => {{ window.close(); }}, 2000);
            }}
        </script>
    </body>
    </html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=success_html)

@app.get("/api/gdrive/status")
async def gdrive_status():
    connected = os.path.exists(TOKEN_FILE)
    email = "Not Linked"
    if connected:
        try:
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)
                # Google tokens don't always contain the email, but we can signal 'Active'
                email = "Active Account"
        except: connected = False
    return {"connected": connected, "email": email}

@app.post("/api/gdrive/unlink")
async def gdrive_unlink():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
    return {"status": "success", "message": "Google Drive unlinked successfully."}

@app.post("/api/backup/gdrive")
async def manual_gdrive_backup(background_tasks: BackgroundTasks):
    if not os.path.exists(TOKEN_FILE):
        return {"status": "error", "message": "Google Drive not connected."}
    
    world_path = os.path.join(MC_DIR, "world")
    if not os.path.exists(world_path):
        return {"status": "error", "message": "World folder not found."}
    
    async def run_backup():
        zip_name = f"manual_cloud_backup_{int(time.time())}.zip"
        zip_path = os.path.join(BACKUP_DIR, zip_name)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(world_path):
                for file in files:
                    zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), os.path.join(world_path, '..')))
        
        uploaded = await upload_to_gdrive(zip_path, zip_name)
        if os.path.exists(zip_path): os.remove(zip_path)
        
    background_tasks.add_task(run_backup)
    return {"status": "success", "message": "Cloud backup started in background."}

def get_mc_processes():
    """Finds and returns a list of psutil.Process instances for the running Minecraft server (including Java and its children)."""
    global MC_PROCESS
    found_procs = []
    
    # 1. Direct subprocess if active
    if MC_PROCESS and MC_PROCESS.poll() is None:
        try:
            parent = psutil.Process(MC_PROCESS.pid)
            found_procs.append(parent)
            found_procs.extend(parent.children(recursive=True))
        except Exception:
            pass

    # 2. Search running processes for java or processes running inside MC_DIR
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
                
                # Check if it's Java running Minecraft or any process running with server.jar or inside mc_server
                if "server.jar" in cmd_str or ("java" in name and (mc_dir_clean in cwd or "minecraft" in cmd_str or "paper" in cmd_str or "purpur" in cmd_str or "fabric" in cmd_str or "forge" in cmd_str)):
                    if p.pid not in [x.pid for x in found_procs]:
                        found_procs.append(p)
                        found_procs.extend([c for c in p.children(recursive=True) if c.pid not in [x.pid for x in found_procs]])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception:
        pass
    return found_procs

def is_server_running():
    global MC_PROCESS
    # Check via tmux first if available
    if shutil.which("tmux"):
        try:
            subprocess.check_output(["tmux", "has-session", "-t", "mc_server"], stderr=subprocess.STDOUT)
            return True
        except:
            pass
    # Check direct subprocess if running
    if MC_PROCESS and MC_PROCESS.poll() is None:
        return True
    # Check via process inspection
    procs = get_mc_processes()
    if len(procs) > 0:
        return True
    return False

def get_server_detailed_state():
    """Returns 'online' (fully ready), 'starting' (booting JVM/loading plugins), or 'offline'."""
    if not is_server_running():
        return "offline"

    # 1. If port 25565 is open and accepting TCP connections, the server is 100% ONLINE
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        res = sock.connect_ex(('127.0.0.1', 25565))
        sock.close()
        if res == 0:
            return "online"
    except Exception:
        pass

    # 2. Check latest.log to see if Paper/Minecraft finished boot or is stopping
    log_path = os.path.join(MC_DIR, "logs", "latest.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            for line in reversed(lines[-80:]):
                if ")! For help, type \"help\"" in line or "Done (" in line or "Ready for connections" in line:
                    return "online"
                if "Stopping server" in line or "Saving players" in line:
                    return "stopping"
        except:
            pass

    return "starting"



@app.post("/api/start")
async def start_server():
    global MC_PROCESS
    if is_server_running():
        return {"status": "error", "message": "Server is already running."}

    try:
        start_script = os.path.join(MC_DIR, "start.sh")
        server_jar = os.path.join(MC_DIR, "server.jar")

        # If server.jar exists but start.sh is missing, auto-create optimized start.sh
        if not os.path.exists(start_script) and os.path.exists(server_jar):
            # Calculate optimal RAM (assign up to 10GB or 75% of total VPS RAM)
            try:
                import psutil
                total_mb = int(psutil.virtual_memory().total / (1024 * 1024))
                alloc_mb = min(10240, max(4096, int(total_mb * 0.75)))
            except:
                alloc_mb = 10240
                
            optimized_sh = f"""#!/bin/bash
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
            return {"status": "error", "message": "No Minecraft server installed! Please install one from the Installer tab."}
        
        # Accept EULA automatically if not present
        eula_path = os.path.join(MC_DIR, "eula.txt")
        if not os.path.exists(eula_path):
            with open(eula_path, "w") as f:
                f.write("eula=true\n")

        # Clean up any zombie process or port collision on 25565
        try:
            if shutil.which("fuser"):
                subprocess.run(["fuser", "-k", "25565/tcp"], stderr=subprocess.DEVNULL)
            elif shutil.which("pkill"):
                subprocess.run(["pkill", "-9", "-f", "server.jar"], stderr=subprocess.DEVNULL)
            elif shutil.which("killall"):
                subprocess.run(["killall", "-9", "java"], stderr=subprocess.DEVNULL)
            time.sleep(0.5)
        except:
            pass

        # Remove stale session.lock files if any past crash left them behind
        for world_folder in ["world", "world_nether", "world_the_end"]:
            lock_file = os.path.join(MC_DIR, world_folder, "session.lock")
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except:
                    pass

        log_path = os.path.join(MC_DIR, "logs", "latest.log")
        os.makedirs(os.path.join(MC_DIR, "logs"), exist_ok=True)
        # Clear previous session log so old crash text doesn't trigger false alerts
        open(log_path, "w").close()

        # Find binary paths
        bash_bin = shutil.which("bash") or "/bin/bash"
        tmux_bin = shutil.which("tmux") or "/usr/bin/tmux"
        java_bin = shutil.which("java") or "/usr/bin/java"

        # Determine start command
        if os.path.exists(start_script) and os.path.exists(bash_bin):
            run_cmd_str = f"{bash_bin} {start_script}"
            cmd = [bash_bin, start_script]
        else:
            run_cmd_str = f"{java_bin} -Xms1G -Xmx2G -jar {server_jar} nogui"
            cmd = [java_bin, "-Xms1G", "-Xmx2G", "-jar", server_jar, "nogui"]
            
        # Ensure full environment with PATH containing Java
        env = os.environ.copy()
        env["PATH"] = f"/usr/bin:/bin:/usr/local/bin:{env.get('PATH', '')}"

        # If tmux is installed, launch inside tmux session 'mc_server' so console is fully interactive & persistent
        if shutil.which("tmux"):
            try:
                subprocess.run(["tmux", "kill-session", "-t", "mc_server"], stderr=subprocess.DEVNULL)
            except:
                pass
            
            # Start tmux session and pipe output to latest.log as well
            tmux_cmd = f"cd '{MC_DIR}' && {run_cmd_str} 2>&1 | tee -a '{log_path}'"
            subprocess.Popen(["tmux", "new-session", "-d", "-s", "mc_server", "bash", "-c", tmux_cmd], env=env)
        else:
            # Fallback: direct subprocess Popen
            log_file = open(log_path, "a", buffering=1)
            MC_PROCESS = subprocess.Popen(
                cmd, 
                cwd=MC_DIR, 
                stdout=log_file, 
                stderr=subprocess.STDOUT, 
                stdin=subprocess.PIPE,
                env=env
            )

        return {"status": "success", "message": "Server boot sequence initiated..."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to start server: {str(e)}"}

@app.post("/api/stop")
async def stop_server():
    global MC_PROCESS
    try:
        # 1. Attempt graceful Minecraft stop command first via tmux or stdin
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

        # Give server 1.5 seconds to save world cleanly
        await asyncio.sleep(1.5)

        # 2. Terminate tracked direct subprocess if present
        if MC_PROCESS:
            try:
                MC_PROCESS.terminate()
                MC_PROCESS.kill()
            except:
                pass
            MC_PROCESS = None

        # 3. Kill all detected Minecraft Java processes directly via psutil
        try:
            procs = get_mc_processes()
            for p in procs:
                try:
                    p.terminate()
                except:
                    pass
            # Force kill if still lingering
            for p in procs:
                try:
                    p.kill()
                except:
                    pass
        except:
            pass

        # 4. Kill tmux session
        if shutil.which("tmux"):
            try:
                subprocess.run(["tmux", "kill-session", "-t", "mc_server"], stderr=subprocess.DEVNULL)
            except:
                pass

        # 5. OS-level fallback kills
        try:
            if shutil.which("fuser"):
                subprocess.run(["fuser", "-k", "25565/tcp"], stderr=subprocess.DEVNULL)
            if shutil.which("pkill"):
                subprocess.run(["pkill", "-9", "-f", "server.jar"], stderr=subprocess.DEVNULL)
                subprocess.run(["pkill", "-9", "-f", "mc_server"], stderr=subprocess.DEVNULL)
            elif shutil.which("killall"):
                subprocess.run(["killall", "-9", "java"], stderr=subprocess.DEVNULL)
        except:
            pass

        # 6. Clean up world lock files so server can restart without lock collisions
        for world_folder in ["world", "world_nether", "world_the_end"]:
            lock_file = os.path.join(MC_DIR, world_folder, "session.lock")
            if os.path.exists(lock_file):
                try: os.remove(lock_file)
                except: pass

        return {"status": "success", "message": "Server stopped successfully."}
    except Exception as e:
        return {"status": "error", "message": f"Stop error: {str(e)}"}

@app.post("/api/restart")
async def restart_server():
    await stop_server()
    await asyncio.sleep(2)
    return await start_server()

@app.post("/api/delete")
async def delete_server():
    try:
        await stop_server()
        await asyncio.sleep(3)
        
        if os.path.exists(MC_DIR):
            for item in os.listdir(MC_DIR):
                item_path = os.path.join(MC_DIR, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                except Exception as e:
                    print(f"Failed to delete {item_path}: {e}")
            
            os.makedirs(os.path.join(MC_DIR, "plugins"), exist_ok=True)
            
        return {"status": "success", "message": "Server files completely wiped."}
    except Exception as e:
        return {"status": "error", "message": f"Delete failed: {str(e)}"}

# --- CONSOLE & FILES ---
@app.get("/api/console")
def get_console():
    tmux_bin = shutil.which("tmux") or "/usr/bin/tmux"
    log_path = os.path.join(MC_DIR, "logs", "latest.log")
    
    # 1. Read from logs/latest.log if available
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                content = "".join(f.readlines()[-100:])
                if content.strip():
                    return {"status": "success", "log": content}
        except: 
            pass

    # 2. Fallback to tmux capture-pane if latest.log is not written yet
    if os.path.exists(tmux_bin):
        try:
            output = subprocess.check_output([tmux_bin, "capture-pane", "-pt", "mc_server", "-S", "-100"], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
            if output.strip():
                return {"status": "success", "log": output}
        except:
            pass

    return {"status": "success", "log": "Connecting to Minecraft console..."}

@app.post("/api/command")
async def send_command(request: Request):
    global MC_PROCESS
    cmd = (await request.json()).get("command", "")
    if not cmd: return {"status": "error", "message": "Command empty."}
    
    sent = False
    error_detail = ""

    # 1. Try sending via active tmux session
    if shutil.which("tmux"):
        try:
            # Check if mc_server session exists first
            check = subprocess.run(["tmux", "has-session", "-t", "mc_server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if check.returncode == 0:
                subprocess.run(["tmux", "send-keys", "-t", "mc_server", cmd, "ENTER"], check=True)
                sent = True
        except Exception as e:
            error_detail = str(e)

    # 2. Fallback to direct Python subprocess stdin
    if not sent and MC_PROCESS and MC_PROCESS.stdin and MC_PROCESS.poll() is None:
        try:
            MC_PROCESS.stdin.write(f"{cmd}\n".encode())
            MC_PROCESS.stdin.flush()
            sent = True
        except Exception as e:
            error_detail = str(e)

    # 3. Fallback to writing into active screen / stdin pipe if present
    if sent:
        return {"status": "success", "message": "Command sent to console."}
    else:
        # If server is running but tmux session was started under a different detached name or restarted
        return {"status": "error", "message": f"Server console session not active. {error_detail}".strip()}

@app.get("/api/files/list")
def list_files(path: str = ""):
    safe_path = get_safe_path(MC_DIR, path)
    if not os.path.exists(safe_path): return {"status": "error", "message": "Not found"}
    items = []
    for item in os.listdir(safe_path):
        fpath = os.path.join(safe_path, item)
        items.append({"name": item, "is_dir": os.path.isdir(fpath), "size": os.stat(fpath).st_size if not os.path.isdir(fpath) else 0, "modified": os.stat(fpath).st_mtime})
    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    return {"status": "success", "files": items, "current_path": path}

@app.get("/api/files/read")
def read_file(path: str):
    try:
        with open(get_safe_path(MC_DIR, path), "r", encoding="utf-8") as f: return {"status": "success", "content": f.read()}
    except: return {"status": "error", "message": "Cannot read binary file."}

@app.post("/api/files/write")
async def write_file(request: Request):
    data = await request.json()
    with open(get_safe_path(MC_DIR, data.get("path")), "w", encoding="utf-8") as f: f.write(data.get("content"))
    return {"status": "success", "message": "File saved!"}

@app.post("/api/files/upload")
async def upload_file(path: str = Form(""), file: UploadFile = File(...)):
    with open(os.path.join(get_safe_path(MC_DIR, path), file.filename), "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    return {"status": "success", "message": "Uploaded."}

@app.post("/api/files/delete")
async def delete_file(request: Request):
    try:
        data = await request.json()
        rel_path = data.get('path', '').strip('/')
        if not rel_path: return {"status": "error", "message": "Invalid path"}
        
        full_path = get_safe_path(MC_DIR, rel_path)
        trash_path = os.path.join(TRASH_DIR, rel_path)
        
        os.makedirs(os.path.dirname(trash_path), exist_ok=True)
        if os.path.exists(trash_path):
            if os.path.isdir(trash_path): shutil.rmtree(trash_path)
            else: os.remove(trash_path)
            
        shutil.move(full_path, trash_path)
        return {"status": "success", "message": f"'{rel_path}' moved to trash"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/plugins/installed")
def get_installed_plugins():
    plugins_dir = os.path.join(MC_DIR, "plugins")
    os.makedirs(plugins_dir, exist_ok=True)
    installed = []
    for item in os.listdir(plugins_dir):
        if item.endswith(".jar"):
            fpath = os.path.join(plugins_dir, item)
            installed.append({
                "name": item,
                "size": os.stat(fpath).st_size,
                "modified": os.stat(fpath).st_mtime
            })
    return {"status": "success", "plugins": installed}

@app.get("/api/plugins/search")
def search_plugins(q: str = "", limit: int = 30):
    headers = {"User-Agent": "ValqoreHosting/2.0 (admin@valqore.com)"}
    results = []
    seen_ids = set()

    clean_raw = q.strip()
    
    # Common typo fixes for Minecraft plugins
    typo_map = {
        "vioce": "voice",
        "voic": "voice",
        "dowlode": "download",
        "downlaod": "download",
        "esential": "essentials",
        "essensial": "essentials",
        "luckperm": "luckperms",
        "luckprem": "luckperms",
        "geyser": "geyser",
        "viabackward": "viabackwards",
        "viaback": "viabackwards",
        "authme": "authmereloaded",
        "drivebackup": "drivebackupv2",
        "drivebackupv": "drivebackupv2"
    }
    
    tokens = clean_raw.lower().split()
    corrected_tokens = [typo_map.get(t, t) for t in tokens]
    corrected_str = " ".join(corrected_tokens)

    # Search list ordered by priority
    search_terms = []
    if corrected_str and corrected_str != clean_raw.lower():
        search_terms.append(corrected_str)
    search_terms.append(clean_raw)
    for t in corrected_tokens:
        if len(t) >= 3 and t not in search_terms:
            search_terms.append(t)

    # 1. Search Modrinth
    for term in search_terms[:4]:
        if len(results) >= limit:
            break
        try:
            params = {"limit": 20}
            if term.strip():
                params["query"] = term.strip()
            else:
                params["facets"] = '[["project_type:plugin"]]'
                
            r = requests.get("https://api.modrinth.com/v2/search", params=params, headers=headers, timeout=6)
            if r.status_code == 200:
                data = r.json()
                for hit in data.get("hits", []):
                    pid = str(hit.get("project_id"))
                    if pid not in seen_ids:
                        seen_ids.add(pid)
                        results.append({
                            "id": pid,
                            "slug": hit.get("slug"),
                            "title": hit.get("title"),
                            "description": hit.get("description"),
                            "icon_url": hit.get("icon_url") or "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9e9.png",
                            "downloads": hit.get("downloads", 0),
                            "follows": hit.get("follows", 0),
                            "author": hit.get("author", "Community"),
                            "source": "modrinth"
                        })
        except Exception as e:
            print(f"Modrinth request error for '{term}': {e}")

    # 2. Search Spiget (SpigotMC Database)
    for term in search_terms[:2]:
        if not term or len(results) >= limit:
            continue
        try:
            r2 = requests.get(f"https://api.spiget.org/v2/search/resources/{term.strip()}", params={"size": 15, "field": "name"}, headers=headers, timeout=6)
            if r2.status_code == 200:
                spiget_data = r2.json()
                for item in spiget_data:
                    res_id = str(item.get("id"))
                    if res_id not in seen_ids:
                        seen_ids.add(res_id)
                        icon = item.get("icon", {}).get("url")
                        if icon and not icon.startswith("http"):
                            icon = f"https://www.spigotmc.org/{icon}"
                        results.append({
                            "id": res_id,
                            "slug": f"spiget-{res_id}",
                            "title": item.get("name"),
                            "description": item.get("tag", "SpigotMC Resource"),
                            "icon_url": icon or "https://static.spigotmc.org/img/spigot.png",
                            "downloads": item.get("downloads", 0),
                            "follows": item.get("likes", 0),
                            "author": "SpigotMC",
                            "source": "spiget"
                        })
        except Exception as e:
            print(f"Spiget request error for '{term}': {e}")

    # Fallback if 0 results
    if not results:
        try:
            r3 = requests.get("https://api.modrinth.com/v2/search", params={"limit": 24}, headers=headers, timeout=6)
            if r3.status_code == 200:
                data3 = r3.json()
                for hit in data3.get("hits", []):
                    pid = str(hit.get("project_id"))
                    if pid not in seen_ids:
                        seen_ids.add(pid)
                        results.append({
                            "id": pid,
                            "slug": hit.get("slug"),
                            "title": hit.get("title"),
                            "description": hit.get("description"),
                            "icon_url": hit.get("icon_url") or "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9e9.png",
                            "downloads": hit.get("downloads", 0),
                            "follows": hit.get("follows", 0),
                            "author": hit.get("author", "Community"),
                            "source": "modrinth"
                        })
        except:
            pass

    return {"status": "success", "hits": results}

def detect_server_version():
    """Detects Minecraft server version from latest.log, version_history.json, or defaults to 1.21.1"""
    # 1. Check version_history.json
    vh_path = os.path.join(MC_DIR, "version_history.json")
    if os.path.exists(vh_path):
        try:
            with open(vh_path, "r", encoding="utf-8") as f:
                vh_data = json.load(f)
                if isinstance(vh_data, dict) and "currentVersion" in vh_data:
                    return vh_data["currentVersion"].split("-")[0].strip()
        except:
            pass

    # 2. Check latest.log
    log_path = os.path.join(MC_DIR, "logs", "latest.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(4096)
                import re
                m = re.search(r"Minecraft (\d+\.\d+(\.\d+)?)", content)
                if m:
                    return m.group(1)
        except:
            pass

    return "1.21.1"

@app.post("/api/plugins/install")
async def install_plugin(request: Request):
    data = await request.json()
    slug_or_id = str(data.get("id") or data.get("slug") or "")
    source = data.get("source", "modrinth")
    mc_version = detect_server_version()

    if not slug_or_id:
        return {"status": "error", "message": "Plugin ID required."}

    plugins_dir = os.path.join(MC_DIR, "plugins")
    os.makedirs(plugins_dir, exist_ok=True)
    headers = {"User-Agent": "ValqoreHosting/2.0"}

    # Case A: Spiget Direct Download
    if source == "spiget" or slug_or_id.startswith("spiget-"):
        spiget_id = slug_or_id.replace("spiget-", "")
        download_url = f"https://api.spiget.org/v2/resources/{spiget_id}/download"
        dest_filename = f"plugin_{spiget_id}.jar"
        dest_path = os.path.join(plugins_dir, dest_filename)
        try:
            r = requests.get(download_url, headers=headers, stream=True, timeout=25)
            if "filename=" in r.headers.get("Content-Disposition", ""):
                dest_filename = r.headers["Content-Disposition"].split("filename=")[1].replace('"', '').strip()
                dest_path = os.path.join(plugins_dir, dest_filename)
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return {"status": "success", "message": f"'{dest_filename}' downloaded & applied to /plugins folder!", "filename": dest_filename}
        except Exception as e:
            return {"status": "error", "message": f"Spiget download error: {str(e)}"}

    # Case B: Modrinth Download with Automatic Version Matching
    try:
        # Request all versions for this plugin
        url = f"https://api.modrinth.com/v2/project/{slug_or_id}/version"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return {"status": "error", "message": "Plugin version not found."}
        
        versions = r.json()
        if not versions:
            return {"status": "error", "message": "No versions available for download."}
        
        # Smart Filter: Find the best version matching our server's MC version (e.g. 1.21.1) and loaders (purpur, paper, spigot, bukkit)
        matched_version = None
        
        # Priority 1: Exact MC version match + Server plugin loader match
        for v in versions:
            game_versions = v.get("game_versions", [])
            loaders = v.get("loaders", [])
            has_server_loader = any(l in ["paper", "purpur", "spigot", "bukkit", "folia", "velocity", "bungeecord"] for l in loaders)
            if mc_version in game_versions and (has_server_loader or not loaders):
                matched_version = v
                break

        # Priority 2: Exact MC version match (any loader)
        if not matched_version:
            for v in versions:
                if mc_version in v.get("game_versions", []):
                    matched_version = v
                    break

        # Priority 3: Server loader match on newest release
        if not matched_version:
            for v in versions:
                loaders = v.get("loaders", [])
                if any(l in ["paper", "purpur", "spigot", "bukkit"] for l in loaders):
                    matched_version = v
                    break

        # Priority 4: Fallback to latest published version
        if not matched_version:
            matched_version = versions[0]

        files = matched_version.get("files", [])
        jar_file = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not jar_file:
            return {"status": "error", "message": "Could not find compatible .jar file."}
        
        download_url = jar_file.get("url")
        filename = jar_file.get("filename")
        dest_path = os.path.join(plugins_dir, filename)

        dl_r = requests.get(download_url, headers=headers, stream=True, timeout=30)
        with open(dest_path, "wb") as f:
            for chunk in dl_r.iter_content(chunk_size=8192):
                f.write(chunk)

        matched_ver_num = matched_version.get("version_number", "")
        return {
            "status": "success", 
            "message": f"'{filename}' (v{matched_ver_num} for MC {mc_version}) downloaded & applied to /plugins folder!", 
            "filename": filename,
            "mc_version": mc_version
        }
    except Exception as e:
        return {"status": "error", "message": f"Download failed: {str(e)}"}

@app.post("/api/plugins/delete")
async def delete_plugin(request: Request):
    data = await request.json()
    name = data.get("name")
    if not name:
        return {"status": "error", "message": "Plugin name required."}
    target = os.path.join(MC_DIR, "plugins", name)
    if os.path.exists(target):
        try:
            os.remove(target)
            return {"status": "success", "message": f"Plugin '{name}' removed."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Plugin not found."}

@app.post("/api/backup")
def backup_world():
    if os.path.exists(os.path.join(MC_DIR, "world")):
        shutil.make_archive(os.path.join(BACKUP_DIR, f"backup_{time.strftime('%Y%m%d-%H%M%S')}"), 'zip', os.path.join(MC_DIR, "world"))
        return {"status": "success", "message": "World backed up."}
    return {"status": "error", "message": "World folder not found."}

@app.post("/api/world/regenerate")
async def regenerate_world():
    await stop_server()
    await asyncio.sleep(3)
    world_path = os.path.join(MC_DIR, "world")
    if os.path.exists(world_path):
        try:
            shutil.rmtree(world_path)
        except Exception as e:
            return {"status": "error", "message": f"Could not wipe world folder: {e}"}
    # Also delete nether and end if they exist
    for dim in ["world_nether", "world_the_end"]:
        p = os.path.join(MC_DIR, dim)
        if os.path.exists(p): shutil.rmtree(p)
        
    # Start server again to generate new world
    # We use a slight delay to ensure files are released
    await asyncio.sleep(2)
    start_server()
    return {"status": "success", "message": "World wiped. Server is regenerating a fresh world..."}

@app.post("/api/world/upload")
async def upload_world(file: UploadFile = File(...)):
    await stop_server()
    import zipfile
    zip_path = os.path.join(MC_DIR, "world_upload.zip")
    with open(zip_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    
    try:
        # Wipe old world
        world_path = os.path.join(MC_DIR, "world")
        if os.path.exists(world_path): shutil.rmtree(world_path)
        
        # Unzip new world
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(MC_DIR)
        
        os.remove(zip_path)
        # Start server
        await asyncio.sleep(2)
        start_server()
        return {"status": "success", "message": "World uploaded and applied successfully!"}
    except Exception as e:
        if os.path.exists(zip_path): os.remove(zip_path)
        return {"status": "error", "message": f"World apply failed: {str(e)}"}

# --- UNIVERSAL AUTO-INSTALLER & SORTER ---
@app.get("/api/versions/{software}")
def get_versions(software: str):
    try:
        versions = []
        if software in ["paper", "purpur"]:
            # Purpur / Paper compatible API
            res = requests.get("https://api.purpurmc.org/v2/purpur", timeout=10)
            if res.status_code == 200:
                versions = res.json().get("versions", [])
            if not versions:
                # Fallback versions
                versions = ["1.21.4", "1.21.3", "1.21.1", "1.21", "1.20.6", "1.20.4", "1.20.2", "1.20.1", "1.19.4", "1.18.2", "1.16.5", "1.12.2", "1.8.8"]
        elif software == "fabric":
            versions = [v["version"] for v in requests.get("https://meta.fabricmc.net/v2/versions/game", timeout=10).json() if v.get("stable")]
        elif software == "vanilla":
            manifest = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest.json", timeout=10).json()
            versions = [v["id"] for v in manifest.get("versions", []) if v.get("type") == "release"]
        elif software in ["forge", "neoforge"]:
            api_url = "https://meta.prismlauncher.org/v1/net.minecraftforge/" if software == "forge" else "https://meta.prismlauncher.org/v1/net.neoforged/"
            for v in requests.get(api_url, timeout=10).json().get("versions", []):
                for req in v.get("requires", []):
                    if req.get("uid") == "net.minecraft" and req.get("equals") not in versions:
                        versions.append(req.get("equals"))
        
        def version_key(v):
            parts = []
            for p in str(v).split('-')[0].split('.'):
                try: parts.append(int(p))
                except: parts.append(0)
            return parts

        unique_versions = list(dict.fromkeys(versions))
        unique_versions.sort(key=version_key, reverse=True)

        return {"status": "success", "versions": unique_versions}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/api/install/{software}/{version}")
def install_software(software: str, version: str):
    try:
        for item in os.listdir(MC_DIR):
            if item != "plugins": 
                p = os.path.join(MC_DIR, item)
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        
        if software in ["paper", "purpur"]:
            url = f"https://api.purpurmc.org/v2/purpur/{version}/latest/download"
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(os.path.join(MC_DIR, "server.jar"), 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
                    
        elif software == "fabric":
            url = f"https://meta.fabricmc.net/v2/versions/loader/{version}/0.15.11/1.0.1/server/jar"
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(os.path.join(MC_DIR, "server.jar"), 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
                    
        elif software == "vanilla":
            manifest = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest.json", timeout=10).json()
            v_url = next(v["url"] for v in manifest["versions"] if v["id"] == version)
            url = requests.get(v_url, timeout=10).json()["downloads"]["server"]["url"]
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(os.path.join(MC_DIR, "server.jar"), 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
                    
        elif software in ["forge", "neoforge"]:
            api_url = "https://meta.prismlauncher.org/v1/net.minecraftforge/" if software == "forge" else "https://meta.prismlauncher.org/v1/net.neoforged/"
            target_version = next((v["version"] for v in requests.get(api_url, timeout=10).json().get("versions", []) if any(req.get("uid") == "net.minecraft" and req.get("equals") == version for req in v.get("requires", []))), None)
            if not target_version: return {"status": "error", "message": f"Version not found."}
            
            url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{version}-{target_version}/forge-{version}-{target_version}-installer.jar" if software == "forge" else f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{target_version}/neoforge-{target_version}-installer.jar"
            
            installer_path = os.path.join(MC_DIR, "installer.jar")
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(installer_path, 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
            
            subprocess.run(["java", "-jar", "installer.jar", "--installServer"], cwd=MC_DIR, check=True)
            os.remove(installer_path)

        start_sh_content = """#!/bin/bash
if [ -f "run.sh" ]; then
    chmod +x run.sh
    sed -i 's/read -p.*/echo "Server stopped."/g' run.sh
    ./run.sh
elif [ -f "server.jar" ]; then
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
elif ls forge-*.jar 1> /dev/null 2>&1; then
    java -Xms10240M -Xmx10240M -jar forge-*.jar nogui
else
    echo "No executable jar found!"
fi
"""
        with open(os.path.join(MC_DIR, "start.sh"), "w") as f: f.write(start_sh_content)
        os.chmod(os.path.join(MC_DIR, "start.sh"), 0o755)
        with open(os.path.join(MC_DIR, "eula.txt"), "w") as f: f.write("eula=true\n")
            
        return {"status": "success", "message": f"{software.capitalize()} {version} installed successfully!"}
    except Exception as e: return {"status": "error", "message": f"Installation failed: {str(e)}"}

# ==========================================
# DISCORD BOT 6-DIGIT AUTHENTICATION & APPROVED SERVERS
# ==========================================
BOT_CONFIG_FILE = os.path.abspath("bot_config.json")
CURRENT_AUTH_CODE = None
AUTH_CODE_EXPIRY = 0

def load_bot_config():
    if os.path.exists(BOT_CONFIG_FILE):
        try:
            with open(BOT_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"approved_guilds": {}}

def save_bot_config(config):
    try:
        with open(BOT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except:
        pass

@app.get("/api/bot/auth/code")
def get_or_create_auth_code():
    global CURRENT_AUTH_CODE, AUTH_CODE_EXPIRY
    now = time.time()
    # If code expired or missing, generate a new 6-digit code (valid for 15 minutes)
    if not CURRENT_AUTH_CODE or now > AUTH_CODE_EXPIRY:
        CURRENT_AUTH_CODE = f"{random.randint(100000, 999999)}"
        AUTH_CODE_EXPIRY = now + (15 * 60)
    
    cfg = load_bot_config()
    return {
        "code": CURRENT_AUTH_CODE,
        "expires_in": max(0, int(AUTH_CODE_EXPIRY - now)),
        "approved_guilds": cfg.get("approved_guilds", {})
    }

@app.post("/api/bot/auth/verify")
async def verify_bot_auth(request: Request):
    global CURRENT_AUTH_CODE, AUTH_CODE_EXPIRY
    data = await request.json()
    code = str(data.get("code", "")).strip()
    guild_id = str(data.get("guild_id", "")).strip()
    guild_name = str(data.get("guild_name", "Discord Server")).strip()
    channel_id = str(data.get("channel_id", "")).strip()
    channel_name = str(data.get("channel_name", "")).strip()
    role_id = str(data.get("role_id", "")).strip()
    role_name = str(data.get("role_name", "")).strip()
    admin_user = str(data.get("admin_user", "Admin")).strip()

    now = time.time()
    if not CURRENT_AUTH_CODE or now > AUTH_CODE_EXPIRY:
        return {"status": "error", "message": "The verification code has expired. Please refresh your Web Panel Settings for a new 6-digit code."}
    
    if code != CURRENT_AUTH_CODE:
        return {"status": "error", "message": "Invalid 6-digit verification code. Please check your Web Panel under Settings > Approved Servers."}

    cfg = load_bot_config()
    cfg["approved_guilds"][guild_id] = {
        "guild_id": guild_id,
        "guild_name": guild_name,
        "channel_id": channel_id,
        "channel_name": channel_name,
        "role_id": role_id,
        "role_name": role_name,
        "approved_by": admin_user,
        "approved_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_bot_config(cfg)
    
    # Generate new code after successful link
    CURRENT_AUTH_CODE = f"{random.randint(100000, 999999)}"
    AUTH_CODE_EXPIRY = now + (15 * 60)

    return {"status": "success", "message": f"Successfully verified and authorized {guild_name}!"}

@app.get("/api/bot/auth/config")
def get_bot_config():
    return load_bot_config()

@app.post("/api/bot/auth/revoke")
async def revoke_guild(request: Request):
    data = await request.json()
    guild_id = str(data.get("guild_id", "")).strip()
    cfg = load_bot_config()
    if guild_id in cfg.get("approved_guilds", {}):
        del cfg["approved_guilds"][guild_id]
        save_bot_config(cfg)
        return {"status": "success", "message": "Server authorization revoked."}
    return {"status": "error", "message": "Server not found."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)