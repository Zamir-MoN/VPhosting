# MCPannel (Delta X Panel) Documentation

## Overview

**MCPannel** (also known as Delta X Panel) is a custom-built web interface for managing a Minecraft server. It provides a FastAPI-based backend that handles server monitoring, process management, file backups, an auto-installer for various server softwares, and a file manager, while serving a static HTML/JS frontend for the user dashboard.

## Architecture & How It Works

1. **Backend Framework**: Built with Python using **FastAPI** and served via **Uvicorn** (running on port `8090`). It handles HTTP API requests from the frontend and manages background tasks.
2. **Minecraft Process Management**: Instead of running the Minecraft server as a child process of Python, the panel utilizes **tmux** (Terminal Multiplexer). 
   - When the server is started, it launches within a `tmux` session named `mc_server`. 
   - This allows the server console to remain persistent even if the web panel restarts. The panel reads console output by capturing the tmux pane (`tmux capture-pane`) and sends commands via `tmux send-keys`.
3. **Frontend Serving**: The frontend consists of static files (HTML, CSS, JS) located in the `static` directory. FastAPI mounts this directory and serves `index.html` at the root `/` endpoint.
4. **Server Installation System**: The panel can dynamically download and install server softwares like Paper, Fabric, Vanilla, Forge, and NeoForge directly through the API, generating the necessary `start.sh` and accepting the EULA automatically.
5. **Automated Backups**: 
   - The panel features a built-in background scheduler that periodically zips the `world` folder.
   - It can upload these zip files directly to **Google Drive**.
   - It authenticates using OAuth 2.0 (`google-auth-oauthlib`), storing credentials in `token.json` generated via `client_secrets.json`.

## File Structure

- `main.py`: The core FastAPI backend application.
- `requirements.txt`: Python dependencies (FastAPI, uvicorn, mcrcon, google-auth tools, etc.).
- `static/`: Contains the frontend assets for the web dashboard.
- `mc_server/`: The directory where the actual Minecraft server jar, `server.properties`, and `world` files reside.
- `backups/`: Local storage for generated ZIP backups before they are uploaded/deleted.
- `.trash/`: A recycle bin for deleted files to support the "undo delete" feature.

## Network Ports Used

Below is a detailed breakdown of the network ports utilized by this project:

| Port | Protocol | Service | Description |
|------|----------|---------|-------------|
| **8090** | TCP | FastAPI (Uvicorn) | The default port used by the web panel backend, hardcoded in `main.py`. Users will access the web dashboard through this port (or via port 80/443 if Nginx is configured as a reverse proxy). |
| **25565** | TCP/UDP | Minecraft Server | The default public port for Minecraft. Players connect to the server using this port. This **must** be open on the firewall. |
| **25575** | TCP | Minecraft RCON | Remote Console port. Although imported in `main.py`, the panel primarily relies on `tmux` for commands. If enabled in `server.properties`, it should be bound to `127.0.0.1` so it is only accessible internally. **Do not** expose this port to the public. |
| **80/443**| TCP | Nginx (Optional) | If a reverse proxy is set up, standard web traffic connects here to access the panel securely. |

### Security Notes
- The Google Drive authentication uses a hardcoded redirect URI (`http://localhost:8090/api/gdrive/callback`). For VPS usage, you may need an SSH tunnel forwarding port 8090 to localhost to complete the OAuth flow securely.
- Ensure that the RCON port (if used) is never allowed through the external firewall (UFW) as it allows full administrative control over the Minecraft server.
