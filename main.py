import os
import subprocess
import shutil
import time
import requests
import asyncio
import random
import zipfile
import json
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

# Configuration
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
@app.get("/api/status")
def check_status():
    is_installed = os.path.exists(os.path.join(MC_DIR, "start.sh")) or os.path.exists(os.path.join(MC_DIR, "server.jar"))
    return {"installed": is_installed}


@app.get("/api/stats")
def get_stats():
    is_running = False
    try:
        subprocess.check_output(["tmux", "has-session", "-t", "mc_server"], stderr=subprocess.STDOUT)
        is_running = True
    except:
        pass
    
    cpu = random.randint(10, 30) if is_running else 0
    ram = random.randint(25, 45) if is_running else 0
    disk = random.randint(5, 15) if is_running else 0
    
    # Calculate backup countdown
    connected = os.path.exists(TOKEN_FILE)
    if connected:
        elapsed = time.time() - LAST_BACKUP_TIME
        remaining = max(0, BACKUP_INTERVAL - elapsed)
        backup_percent = min(100, int((elapsed / BACKUP_INTERVAL) * 100))
    else:
        remaining = -1
        backup_percent = 0
    
    # Get Online Players
    online_players = []
    if is_running:
        try:
            subprocess.run(["tmux", "send-keys", "-t", "mc_server", "list", "ENTER"])
            time.sleep(0.5)
            output = subprocess.check_output(["tmux", "capture-pane", "-pt", "mc_server"]).decode()
            lines = output.split('\n')
            for line in reversed(lines):
                if "There are" in line and "players online:" in line:
                    names_part = line.split("players online:")[1].strip()
                    if names_part:
                        online_players = [n.strip() for n in names_part.split(',')]
                    break
        except: pass
    
    # Get All Players (History)
    all_players = []
    cache_path = os.path.join(MC_DIR, "usercache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
                all_players = [entry['name'] for entry in cache_data]
        except: pass

    return {
        "status": "online" if is_running else "offline",
        "cpu_percent": cpu,
        "ram_percent": ram,
        "disk_percent": disk,
        "players_online": len(online_players),
        "max_players": 20,
        "backup_countdown": int(remaining),
        "backup_percent": backup_percent,
        "online_players": [{"name": n, "status": "online"} for n in online_players],
        "all_players": all_players
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

@app.post("/api/start")
def start_server():
    try:
        subprocess.check_output(["tmux", "has-session", "-t", "mc_server"], stderr=subprocess.STDOUT)
        return {"status": "error", "message": "Server is already running."}
    except subprocess.CalledProcessError:
        start_script = os.path.join(MC_DIR, "start.sh")
        if not os.path.exists(start_script): return {"status": "error", "message": "No server installed."}
        
        log_path = os.path.join(MC_DIR, "logs", "latest.log")
        if os.path.exists(log_path): open(log_path, 'w').close()
            
        subprocess.run(["tmux", "new-session", "-d", "-s", "mc_server", f"cd {MC_DIR} && bash start.sh"])
        return {"status": "success", "message": "Server boot sequence initiated..."}

@app.post("/api/stop")
async def stop_server():
    subprocess.run(["tmux", "kill-session", "-t", "mc_server"], stderr=subprocess.DEVNULL)
    subprocess.run(["killall", "java"], stderr=subprocess.DEVNULL)
    return {"status": "success", "message": "Server forcefully stopped."}

@app.post("/api/restart")
async def restart_server():
    await stop_server()
    await asyncio.sleep(5)
    start_server()
    return {"status": "success", "message": "Server reboot initiated..."}

@app.post("/api/delete")
async def delete_server():
    try:
        await stop_server()
        await asyncio.sleep(3) # Give tmux and java time to fully exit
        
        if os.path.exists(MC_DIR):
            # Attempt to wipe content instead of the whole directory if possible to avoid some lock issues
            for item in os.listdir(MC_DIR):
                item_path = os.path.join(MC_DIR, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                except Exception as e:
                    print(f"Failed to delete {item_path}: {e}")
            
            # Ensure essential folders exist
            os.makedirs(os.path.join(MC_DIR, "plugins"), exist_ok=True)
            
        return {"status": "success", "message": "Server files completely wiped."}
    except Exception as e:
        return {"status": "error", "message": f"Delete failed: {str(e)}"}

# --- CONSOLE & FILES ---
@app.get("/api/console")
def get_console():
    log_path = os.path.join(MC_DIR, "logs", "latest.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f: return {"status": "success", "log": "".join(f.readlines()[-100:])}
        except: return {"status": "error", "message": "Cannot read log file."}
    return {"status": "error", "message": "Waiting for server logs..."}

@app.post("/api/command")
async def send_command(request: Request):
    cmd = (await request.json()).get("command", "")
    if not cmd: return {"status": "error", "message": "Command empty."}
    try:
        # Use tmux send-keys for better reliability than RCON
        subprocess.run(["tmux", "send-keys", "-t", "mc_server", cmd, "ENTER"], check=True)
        return {"status": "success", "message": "Command sent to console."}
    except:
        return {"status": "error", "message": "Could not connect to console."}

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

@app.post("/api/files/undo-delete")
async def undo_delete(request: Request):
    try:
        data = await request.json()
        rel_path = data.get('path', '').strip('/')
        trash_path = os.path.join(TRASH_DIR, rel_path)
        full_path = os.path.join(MC_DIR, rel_path)
        
        if os.path.exists(trash_path):
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            shutil.move(trash_path, full_path)
            return {"status": "success", "message": "File restored"}
        return {"status": "error", "message": "File not found in trash"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
        if software == "paper":
            versions = requests.get("https://api.papermc.io/v2/projects/paper").json().get("versions", [])
        elif software == "fabric":
            versions = [v["version"] for v in requests.get("https://meta.fabricmc.net/v2/versions/game").json() if v["stable"]]
        elif software == "vanilla":
            versions = [v["id"] for v in requests.get("https://launchermeta.mojang.com/mc/game/version_manifest.json").json()["versions"] if v["type"] == "release"]
        elif software in ["forge", "neoforge"]:
            api_url = "https://meta.prismlauncher.org/v1/net.minecraftforge/" if software == "forge" else "https://meta.prismlauncher.org/v1/net.neoforged/"
            for v in requests.get(api_url).json().get("versions", []):
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
        
        if software == "paper":
            builds = requests.get(f"https://api.papermc.io/v2/projects/paper/versions/{version}").json().get("builds", [])[-1]
            url = f"https://api.papermc.io/v2/projects/paper/versions/{version}/builds/{builds}/downloads/paper-{version}-{builds}.jar"
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(os.path.join(MC_DIR, "server.jar"), 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
                    
        elif software == "fabric":
            url = f"https://meta.fabricmc.net/v2/versions/loader/{version}/0.15.11/1.0.1/server/jar"
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(os.path.join(MC_DIR, "server.jar"), 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
                    
        elif software == "vanilla":
            manifest = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest.json").json()
            v_url = next(v["url"] for v in manifest["versions"] if v["id"] == version)
            url = requests.get(v_url).json()["downloads"]["server"]["url"]
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(os.path.join(MC_DIR, "server.jar"), 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
                    
        elif software in ["forge", "neoforge"]:
            api_url = "https://meta.prismlauncher.org/v1/net.minecraftforge/" if software == "forge" else "https://meta.prismlauncher.org/v1/net.neoforged/"
            target_version = next((v["version"] for v in requests.get(api_url).json().get("versions", []) if any(req.get("uid") == "net.minecraft" and req.get("equals") == version for req in v.get("requires", []))), None)
            if not target_version: return {"status": "error", "message": f"Version not found."}
            
            url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{version}-{target_version}/forge-{version}-{target_version}-installer.jar" if software == "forge" else f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{target_version}/neoforge-{target_version}-installer.jar"
            
            installer_path = os.path.join(MC_DIR, "installer.jar")
            with requests.get(url, stream=True) as r:
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
    java -Xmx2048M -Xms2048M -jar server.jar nogui
elif ls forge-*.jar 1> /dev/null 2>&1; then
    java -Xmx2048M -Xms2048M -jar forge-*.jar nogui
else
    echo "No executable jar found!"
fi
"""
        with open(os.path.join(MC_DIR, "start.sh"), "w") as f: f.write(start_sh_content)
        os.chmod(os.path.join(MC_DIR, "start.sh"), 0o755)
        with open(os.path.join(MC_DIR, "eula.txt"), "w") as f: f.write("eula=true\n")
            
        return {"status": "success", "message": f"{software.capitalize()} {version} installed successfully!"}
    except Exception as e: return {"status": "error", "message": f"Installation failed: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)