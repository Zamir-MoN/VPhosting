// Loading system replaced by Toast notifications.
function showToast(message, type = 'success', undoAction = null) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    // Icon mapping
    const icons = {
        success: 'check-circle',
        error: 'alert-circle',
        info: 'info',
        loading: 'loader'
    };
    
    const iconName = icons[type] || 'bell';
    const iconHtml = `<i data-lucide="${iconName}" class="toast-icon ${type === 'loading' ? 'spin' : ''}"></i>`;
    
    toast.innerHTML = `
        ${iconHtml}
        <div class="toast-content">
            <span class="toast-message">${message}</span>
        </div>
    `;

    if (undoAction) {
        const undoBtn = document.createElement('button');
        undoBtn.className = 'toast-undo';
        undoBtn.innerText = "UNDO";
        undoBtn.onclick = (e) => {
            e.stopPropagation();
            undoAction();
            gsap.to(toast, { x: 100, opacity: 0, duration: 0.3, onComplete: () => toast.remove() });
        };
        toast.querySelector('.toast-content').appendChild(undoBtn);
    }

    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.innerHTML = '&times;';
    closeBtn.onclick = () => {
        gsap.to(toast, { x: 100, opacity: 0, duration: 0.3, onComplete: () => toast.remove() });
    };
    toast.appendChild(closeBtn);

    container.appendChild(toast);
    lucide.createIcons();

    // Entrance animation
    gsap.fromTo(toast, { x: 50, opacity: 0 }, { x: 0, opacity: 1, duration: 0.4, ease: "back.out(1.7)" });

    if (type !== 'loading') {
        setTimeout(() => {
            if (toast.parentNode) {
                gsap.to(toast, { x: 100, opacity: 0, duration: 0.3, onComplete: () => toast.remove() });
            }
        }, 5000);
    }

    return toast; // Return toast element so it can be manually removed (e.g. for loading states)
}

// --- Tab Switching ---
let currentTab = 'dashboard';
function switchTab(tabId, element) {
    if (tabId === currentTab && document.getElementById(`tab-${tabId}`).classList.contains('active')) {
        // Only toggle mobile menu if already on the tab
        if (typeof isMobileMenuOpen !== 'undefined' && isMobileMenuOpen) toggleMobileMenu();
        return;
    }

    // Prepare for transition
    const oldTab = document.getElementById(`tab-${currentTab}`);
    const newTab = document.getElementById(`tab-${tabId}`);

    // Update Nav Items (Desktop Sidebar)
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    if (element && element.classList.contains('nav-item')) {
        element.classList.add('active');
    } else {
        document.querySelectorAll(`.nav-item[onclick*="'${tabId}'"]`).forEach(el => el.classList.add('active'));
    }

    // Update PillNav active state (Desktop Topbar & Mobile Menu)
    document.querySelectorAll('.pill').forEach(el => el.classList.remove('is-active'));
    document.querySelectorAll(`.pill[onclick*="'${tabId}'"]`).forEach(btn => {
        btn.classList.add('is-active');
    });

    // Animate Tab Switch
    gsap.to(oldTab, { 
        opacity: 0, 
        y: -10, 
        duration: 0.2, 
        onComplete: () => {
            oldTab.classList.remove('active');
            newTab.classList.add('active');
            gsap.fromTo(newTab, 
                { opacity: 0, y: 10 }, 
                { opacity: 1, y: 0, duration: 0.3, ease: "power2.out" }
            );
        }
    });

    // Animate Title Change
    const titleEl = document.getElementById('pageTitle');
    gsap.to(titleEl, { 
        opacity: 0, 
        x: -10, 
        duration: 0.2, 
        onComplete: () => {
            const titles = {
                'dashboard': 'Dashboard',
                'console': 'Console',
                'files': 'Files',
                'installer': 'Installer',
                'worlds': 'World Management',
                'players': 'Player Management',
                'settings': 'Settings'
            };
            titleEl.innerText = titles[tabId] || 'Panel';
            gsap.fromTo(titleEl, { opacity: 0, x: 10 }, { opacity: 1, x: 0, duration: 0.3 });
        }
    });

    currentTab = tabId;
    if (tabId === 'files') loadFiles('');
    if (tabId === 'installer') loadMarketplace('vanilla');
    if (tabId === 'players') fetchPlayers();
}

// --- IP Logic ---
function initIpDisplay() {
    document.getElementById('serverIpDisplay').innerText = window.location.hostname + ":25565";
}
function copyIp() {
    navigator.clipboard.writeText(window.location.hostname + ":25565").then(() => { showToast("IP Copied to clipboard!", "success"); });
}

// --- DASHBOARD RINGS ---
function updateRing(id, percent) {
    const ring = document.getElementById(`ring-${id}`);
    if (ring) {
        ring.style.setProperty('--percentage', percent);
    }
}

async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        
        // Handle Global Status Badge & Power Buttons state
        const startBtn = document.querySelector('button[onclick="apiCall(\'/api/start\')"]');
        const stopBtn = document.querySelector('button[onclick="apiCall(\'/api/stop\')"]');
        const restartBtn = document.querySelector('button[onclick="apiCall(\'/api/restart\')"]');
        const globalStatusBadge = document.getElementById('globalStatusBadge');
        const globalStatusText = document.getElementById('globalStatusText');

        if (data.status === 'online') {
            if (globalStatusBadge) {
                globalStatusBadge.classList.remove('offline');
                globalStatusText.innerText = "ONLINE";
            }
            if (startBtn) startBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = false;
            if (restartBtn) restartBtn.disabled = false;
        } else {
            if (globalStatusBadge) {
                globalStatusBadge.classList.add('offline');
                globalStatusText.innerText = "OFFLINE";
            }
            if (startBtn) startBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = true;
            if (restartBtn) restartBtn.disabled = true;
        }
        
        // RAM
        const ramBar = document.getElementById('bar-ram');
        if (ramBar) ramBar.style.width = `${data.ram_percent}%`;
        const textRam = document.getElementById('text-ram');
        if (textRam) textRam.innerText = `${data.ram_percent}%`;
        const subRam = document.getElementById('sub-ram');
        const usedMb = data.ram_used_mb || 0;
        const totalMb = data.ram_total_mb || 2048;
        if (subRam) subRam.innerText = `${usedMb} / ${totalMb} MB`;
        
        // CPU
        const cpuBar = document.getElementById('bar-cpu');
        if (cpuBar) cpuBar.style.width = `${data.cpu_percent}%`;
        const textCpu = document.getElementById('text-cpu');
        if (textCpu) textCpu.innerText = `${data.cpu_percent}%`;
        const subCpu = document.getElementById('sub-cpu');
        if (subCpu && data.cpu_cores) subCpu.innerText = `${data.cpu_cores} Cores Active`;
        
        // Online Players
        const playerPercent = Math.min(100, (data.players_online / data.max_players) * 100);
        const slotBar = document.getElementById('bar-slot');
        if (slotBar) slotBar.style.width = `${playerPercent}%`;
        const textSlot = document.getElementById('text-slot');
        if (textSlot) textSlot.innerText = `${data.players_online}/${data.max_players}`;

        // Backup Countdown
        const countdownText = document.getElementById('text-overload');
        const overloadBar = document.getElementById('bar-overload');
        
        if (data.backup_countdown === -1) {
            if (countdownText) countdownText.innerText = "STANDBY";
            if (overloadBar) overloadBar.style.width = "0%";
        } else {
            const hours = Math.floor(data.backup_countdown / 3600);
            const mins = Math.floor((data.backup_countdown % 3600) / 60);
            if (countdownText) countdownText.innerText = `${hours}h ${mins}m`;
            if (overloadBar) overloadBar.style.width = `${data.backup_percent}%`;
        }
    } catch (e) { }
}
setInterval(fetchStats, 3000);

// --- INTERACTIVE CONSOLE ---
const logDiv = document.getElementById('log');
let autoScroll = true;
let isWaitingForStart = false;
let startLoadingToast = null;

async function fetchConsoleLogs() {
    try {
        const res = await fetch('/api/console');
        const data = await res.json();
        if (data.status === 'success') {
            const consoleElem = document.getElementById('log');
            if (consoleElem) {
                consoleElem.innerText = data.log;
                if (autoScroll) {
                    consoleElem.scrollTop = consoleElem.scrollHeight;
                }
            }
            
            // Check if server boot completed
            if (isWaitingForStart && (data.log.includes('Done (') || data.log.includes('For help, type "help"') || data.log.includes('Timings Reset'))) {
                if (startLoadingToast) {
                    startLoadingToast.remove();
                    startLoadingToast = null;
                }
                showToast("⚡ Minecraft Server is fully Online & Ready to Play!", "success");
                isWaitingForStart = false;
                
                const startBtn = document.querySelector('button[onclick="apiCall(\'/api/start\')"]');
                if (startBtn) {
                    startBtn.classList.remove('is-loading');
                    startBtn.innerHTML = '<i data-lucide="play" style="width:16px;height:16px;"></i> Start';
                    lucide.createIcons();
                }
                fetchStats();
            }

            // Check if server failed / crashed on boot
            if (isWaitingForStart && (data.log.includes('Address already in use') || data.log.includes('UnsupportedClassVersionError') || data.log.includes('Error: Unable to access jarfile'))) {
                if (startLoadingToast) {
                    startLoadingToast.remove();
                    startLoadingToast = null;
                }
                showToast("Startup issue detected in console logs. Check terminal stream.", "error");
                isWaitingForStart = false;
                
                const startBtn = document.querySelector('button[onclick="apiCall(\'/api/start\')"]');
                if (startBtn) {
                    startBtn.classList.remove('is-loading');
                    startBtn.innerHTML = '<i data-lucide="play" style="width:16px;height:16px;"></i> Start';
                    lucide.createIcons();
                }
                fetchStats();
            }
        }
    } catch (e) { }
}
setInterval(fetchConsoleLogs, 1500);

if (logDiv) {
    logDiv.addEventListener('scroll', () => { 
        autoScroll = (logDiv.scrollTop + logDiv.clientHeight >= logDiv.scrollHeight - 10); 
    });
}

document.getElementById('consoleInput').addEventListener('keypress', async function (e) {
    if (e.key === 'Enter') {
        const cmd = e.target.value;
        if (!cmd) return;
        apiCall('/api/command', { command: cmd });
        e.target.value = '';
    }
});

// --- POWER API ---
async function apiCall(endpoint, body = null) {
    const isPowerAction = ['/api/start', '/api/stop', '/api/restart', '/api/delete', '/api/world/regenerate'].includes(endpoint);
    
    let activeToast = null;
    const startBtn = document.querySelector('button[onclick="apiCall(\'/api/start\')"]');
    const globalStatusBadge = document.getElementById('globalStatusBadge');
    const globalStatusText = document.getElementById('globalStatusText');

    if (isPowerAction) {
        let msg = "Processing request...";
        if (endpoint === '/api/start') { 
            msg = "Booting Minecraft Engine (Generating spawn & preparing chunks)..."; 
            isWaitingForStart = true;
            if (startBtn) {
                startBtn.classList.add('is-loading');
                startBtn.innerHTML = '<i data-lucide="loader" class="spin-icon" style="width:16px;height:16px;"></i> Starting...';
                lucide.createIcons();
            }
            if (globalStatusBadge) {
                globalStatusBadge.className = 'server-status-pill starting';
                if (globalStatusText) globalStatusText.innerText = "STARTING...";
            }
        }
        if (endpoint === '/api/stop') { 
            msg = "Stopping Server..."; 
            isWaitingForStart = false;
            if (startBtn) {
                startBtn.classList.remove('is-loading');
                startBtn.innerHTML = '<i data-lucide="play" style="width:16px;height:16px;"></i> Start';
                lucide.createIcons();
            }
        }
        if (endpoint === '/api/restart') { 
            msg = "Restarting Server..."; 
            isWaitingForStart = true;
        }
        if (endpoint === '/api/delete') { msg = "Wiping Server Files..."; }
        if (endpoint === '/api/world/regenerate') { msg = "Regenerating World..."; }
        
        activeToast = showToast(msg, "loading");
        if (endpoint === '/api/start') {
            startLoadingToast = activeToast;
        }
    } else {
        activeToast = showToast("Executing Command...", "loading");
    }

    try {
        const options = { method: 'POST' };
        if (body) {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(body);
        }
        const response = await fetch(endpoint, options);
        const data = await response.json();
        
        if (data.status === 'success') {
            if (endpoint !== '/api/start' && activeToast) {
                activeToast.remove();
                showToast(data.message || "Action completed", "success");
            }
            fetchStats();
        } else {
            if (activeToast) activeToast.remove();
            if (startBtn) {
                startBtn.classList.remove('is-loading');
                startBtn.innerHTML = '<i data-lucide="play" style="width:16px;height:16px;"></i> Start';
                lucide.createIcons();
            }
            showToast(data.message, 'error');
            isWaitingForStart = false;
        }
    } catch (error) { 
        if (activeToast) activeToast.remove();
        if (startBtn) {
            startBtn.classList.remove('is-loading');
            startBtn.innerHTML = '<i data-lucide="play" style="width:16px;height:16px;"></i> Start';
            lucide.createIcons();
        }
        showToast("Network error or connection lost.", "error");
        isWaitingForStart = false; 
    }
}

async function checkStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        const mainNavItems = document.querySelectorAll('.main-nav');
        const navInstallerDesktop = document.getElementById('nav-installer');
        const navInstallerMobile = document.getElementById('nav-installer-mobile');
        
        if (data.installed) {
            document.getElementById('connectionInfoCard').style.display = 'flex';
            if (navInstallerDesktop) navInstallerDesktop.style.display = 'none';
            if (navInstallerMobile) navInstallerMobile.style.display = 'none';
            mainNavItems.forEach(el => el.style.display = 'flex');
        } else {
            document.getElementById('connectionInfoCard').style.display = 'none';
            if (navInstallerDesktop) navInstallerDesktop.style.display = 'flex';
            if (navInstallerMobile) navInstallerMobile.style.display = 'flex';
            mainNavItems.forEach(el => el.style.display = 'none');
            // Force switch to installer if not installed
            if (currentTab !== 'installer') {
                switchTab('installer');
                document.getElementById('pageTitle').innerText = 'Create Your Server';
            }
        }
    } catch (e) { }
}

async function deleteServer() {
    if (confirm("Are you sure? This CANNOT be undone!")) {
        await apiCall('/api/delete');
        checkStatus();
    }
}

async function regenerateWorld() {
    if (confirm("REGENERATE WORLD? This will DELETE your current world and create a new one. This cannot be undone!")) {
        await apiCall('/api/world/regenerate');
        showToast("World regeneration sequence started.", "info");
    }
}

async function downloadBackup() {
    showToast("Compressing world files... please wait.", "info");
    window.location.assign('/api/backup/manual');
}

async function saveAutoBackupConfig() {
    const hours = document.getElementById('autoBackupInterval').value;
    const res = await fetch('/api/backup/auto-config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ hours: parseInt(hours) })
    });
    const data = await res.json();
    if (data.status === 'success') {
        showToast(data.message, "success");
    }
}

async function connectGoogleDrive() {
    try {
        const res = await fetch('/api/gdrive/auth');
        const data = await res.json();
        if (data.status === 'success') {
            showToast("Redirecting to Google...", "info");
            window.open(data.url, '_blank');
            document.getElementById('gdrive-verify-box').style.display = 'block';
        } else {
            showToast(data.message, "error");
        }
    } catch (e) { showToast("Auth error.", "error"); }
}

async function verifyGDriveCode() {
    const code = document.getElementById('gdrive-code').value;
    if (!code) return showToast("Please paste the code first.", "error");
    
    const activeToast = showToast("Verifying code...", "loading");
    try {
        const res = await fetch('/api/gdrive/verify', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ code: code.trim() })
        });
        const data = await res.json();
        if (data.status === 'success') {
            if (activeToast) activeToast.remove();
            showToast(data.message, "success");
            document.getElementById('gdrive-verify-box').style.display = 'none';
            checkGDriveStatus();
        } else {
            if (activeToast) activeToast.remove();
            showToast(data.message, "error");
        }
    } catch (e) { 
        if (activeToast) activeToast.remove();
        showToast("Verification error.", "error"); 
    }
}

async function checkGDriveStatus() {
    try {
        const res = await fetch('/api/gdrive/status');
        const data = await res.json();
        const btn = document.getElementById('btn-gdrive');
        const btnBackup = document.getElementById('btn-gdrive-backup');
        const btnUnlink = document.getElementById('btn-gdrive-unlink');
        const status = document.getElementById('gdrive-status');
        
        if (data.connected) {
            status.innerText = `Status: Connected (${data.email})`;
            status.style.color = "#00ff7f";
            btn.style.display = "none";
            btnBackup.style.display = "block";
            btnUnlink.style.display = "block";
        } else {
            status.innerText = "Status: Not Connected";
            status.style.color = "#ff4c4c";
            btn.style.display = "block";
            btnBackup.style.display = "none";
            btnUnlink.style.display = "none";
            btn.innerText = "Connect Google Drive";
            btn.className = "action-btn start w-100";
            btn.disabled = false;
        }
    } catch (e) { }
}

async function unlinkGDrive() {
    if (!confirm("Are you sure you want to unlink Google Drive?")) return;
    try {
        const res = await fetch('/api/gdrive/unlink', { method: 'POST' });
        const data = await res.json();
        showToast(data.message, "info");
        checkGDriveStatus();
    } catch (e) { showToast("Unlink error.", "error"); }
}

async function manualGDriveBackup() {
    showToast("Starting manual cloud backup...", "info");
    try {
        const res = await fetch('/api/backup/gdrive', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') showToast(data.message, "success");
        else showToast(data.message, "error");
    } catch (e) { showToast("Backup error.", "error"); }
}

// Check status on load
checkGDriveStatus();
setInterval(checkGDriveStatus, 30000); // Check every 30s

async function uploadWorldZip(file) {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    const activeToast = showToast("Uploading & Applying World...", "loading");
    try {
        const res = await fetch('/api/world/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (activeToast) activeToast.remove();
        if (data.status === 'success') showToast(data.message, "success");
        else showToast(data.message, "error");
    } catch (e) { 
        if (activeToast) activeToast.remove();
        showToast("World upload error.", "error"); 
    }
}

// --- FILE EXPLORER ---
let currentPath = '';
let editingFilePath = '';

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024, sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

const IMPORTANT_FILES = ['world', 'world_nether', 'world_the_end', 'server.properties', 'banned-ips.json', 'banned-players.json', 'ops.json', 'usercache.json', 'whitelist.json', 'eula.txt', 'server.jar', 'start.sh', 'plugins'];

async function loadFiles(path) {
    const tbody = document.getElementById('fileListBody');
    let activeToast = null;
    if (!tbody.innerHTML) activeToast = showToast("Loading Files...", "loading");
    try {
        const res = await fetch(`/api/files/list?path=${encodeURIComponent(path)}`);
        const data = await res.json();
        if (activeToast) activeToast.remove();
        if (data.status === 'success') {
            currentPath = data.current_path;
            document.getElementById('currentPathDisplay').innerText = '/root' + (currentPath ? '/' + currentPath : '');
            const tbody = document.getElementById('fileListBody');
            tbody.innerHTML = '';
            
            if (currentPath !== '') {
                const parentPath = currentPath.substring(0, currentPath.lastIndexOf('/'));
                tbody.innerHTML += `
                    <tr class="file-row">
                        <td colspan="4" onclick="loadFiles('${parentPath}')">
                            <div style="display:flex; align-items:center; gap:10px;">
                                <i data-lucide="chevron-left" style="width:16px;height:16px"></i>
                                <strong>.. (Back)</strong>
                            </div>
                        </td>
                    </tr>`;
            }

            data.files.forEach(f => {
                const isImportant = IMPORTANT_FILES.includes(f.name.toLowerCase());
                const icon = f.is_dir ? 'folder' : 'file-text';
                const date = new Date(f.modified * 1000).toLocaleString();
                const size = f.is_dir ? '--' : formatBytes(f.size);
                const targetPath = currentPath ? `${currentPath}/${f.name}` : f.name;
                
                const row = document.createElement('tr');
                row.className = 'file-row';
                row.innerHTML = `
                    <td onclick="${f.is_dir ? `loadFiles('${targetPath}')` : `openEditor('${targetPath}')`}">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <i data-lucide="${icon}" class="${f.is_dir ? 'folder-icon' : ''}" style="width:18px;height:18px"></i>
                            <span style="${isImportant ? 'color:#ffca28; font-weight:600;' : ''}">${f.name}</span>
                        </div>
                    </td>
                    <td>${size}</td>
                    <td>${date}</td>
                    <td>
                        <button class="action-btn stop" style="padding: 5px; min-width: 32px;" onclick="deleteFile('${targetPath}', ${isImportant})">
                            <i data-lucide="trash-2" style="width:14px;height:14px"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(row);
            });
            lucide.createIcons();
        }
    } catch (e) { if (activeToast) activeToast.remove(); }
}

async function deleteFile(path, isImportant) {
    let msg = `Are you sure you want to delete '${path}'?`;
    if (isImportant) {
        msg = `⚠️ CRITICAL FILE DETECTED! ⚠️\n\nDeleting '${path}' may break your server or result in data loss.\n\nAre you absolutely sure?`;
    }

    if (!confirm(msg)) return;

    try {
        const res = await fetch('/api/files/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ path: path })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast(`Moved '${path}' to trash.`, "info", () => undoDelete(path));
            loadFiles(currentPath);
        } else {
            showToast(data.message, "error");
        }
    } catch (e) { showToast("Delete error.", "error"); }
}

async function undoDelete(path) {
    try {
        const res = await fetch('/api/files/undo-delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ path: path })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast("Restored successfully!", "success");
            loadFiles(currentPath);
        } else {
            showToast(data.message, "error");
        }
    } catch (e) { showToast("Undo error.", "error"); }
}

async function openEditor(filePath) {
    try {
        const res = await fetch(`/api/files/read?path=${encodeURIComponent(filePath)}`);
        const data = await res.json();
        if (data.status === 'success') {
            editingFilePath = filePath;
            document.getElementById('fileExplorer').style.display = 'none';
            document.getElementById('fileEditor').style.display = 'block';
            document.getElementById('editingFileName').innerText = `Editing: ${filePath}`;
            document.getElementById('fileEditorArea').value = data.content;
        } else showToast(data.message, "error");
    } catch (e) { }
}

function closeModal() {
    document.getElementById('actionModal').classList.remove('active');
}

function closeEditor() {
    editingFilePath = '';
    document.getElementById('fileEditor').style.display = 'none';
    document.getElementById('fileExplorer').style.display = 'block';
}

async function saveFile() {
    const activeToast = showToast("Saving Changes...", "loading");
    try {
        const res = await fetch('/api/files/write', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: editingFilePath, content: document.getElementById('fileEditorArea').value }) });
        const data = await res.json();
        if (activeToast) activeToast.remove();
        if (data.status === 'success') showToast(data.message, "success");
        else showToast("Failed to save.", "error");
    } catch (e) { 
        if (activeToast) activeToast.remove();
        showToast("Error saving file.", "error"); 
    }
}

function dragOverHandler(e) { e.preventDefault(); document.getElementById('fileExplorer').classList.add('drag-over'); }
function dragLeaveHandler(e) { e.preventDefault(); document.getElementById('fileExplorer').classList.remove('drag-over'); }
async function dropHandler(e) {
    e.preventDefault();
    document.getElementById('fileExplorer').classList.remove('drag-over');
    if (e.dataTransfer.files) {
        handleMultiUpload(e.dataTransfer.files);
    }
}

async function handleMultiUpload(files) {
    if (!files || files.length === 0) return;
    
    const fileArray = Array.from(files);
    const activeToast = showToast(`Uploading ${fileArray.length} files...`, "loading");
    
    let uploadedPaths = [];
    for (const file of fileArray) {
        try {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("path", currentPath);
            const res = await fetch('/api/files/upload', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.status === 'success') {
                uploadedPaths.push(currentPath ? `${currentPath}/${file.name}` : file.name);
            }
        } catch (e) { console.error("Upload error for", file.name, e); }
    }
    
    if (activeToast) activeToast.remove();
    showToast(`Successfully uploaded ${uploadedPaths.length}/${fileArray.length} files.`, "success", uploadedPaths.length > 0 ? () => undoUpload(uploadedPaths) : null);
    loadFiles(currentPath);
}

async function undoUpload(paths) {
    const activeToast = showToast("Undoing Upload...", "loading");
    for (const path of paths) {
        try {
            await fetch('/api/files/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ path: path })
            });
        } catch (e) {}
    }
    if (activeToast) activeToast.remove();
    showToast("Upload undone (files moved to trash).", "info");
    loadFiles(currentPath);
}


// --- MARKETPLACE INSTALLER ---
let currentSoftware = 'vanilla';
let isInstalling = false;

function showStep(stepId) {
    document.getElementById('softwareSelectionStep').style.display = 'none';
    document.getElementById('versionSelectionStep').style.display = 'none';
    document.getElementById(stepId).style.display = 'block';
}

function selectSoftware(software) {
    currentSoftware = software;
    const names = {
        'vanilla': 'Vanilla',
        'paper': 'PaperMC',
        'fabric': 'Fabric',
        'forge': 'Forge',
        'neoforge': 'NeoForge'
    };
    document.getElementById('selectedSoftwareName').innerText = names[software] || software;
    
    const searchInput = document.getElementById('versionSearch');
    if (searchInput) searchInput.value = '';

    showStep('versionSelectionStep');
    loadMarketplace(software);
    setTimeout(() => lucide.createIcons(), 100);
}

function filterVersions() {
    const input = document.getElementById('versionSearch');
    if (!input) return;
    const filter = input.value.toLowerCase();
    const cards = document.querySelectorAll('.version-card');
    
    let visibleCount = 0;
    cards.forEach(card => {
        const version = card.querySelector('.card-version').innerText.toLowerCase();
        if (version.includes(filter)) {
            card.style.display = 'flex';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });

    const grid = document.getElementById('marketplaceGrid');
    let noResultsMsg = document.getElementById('noResultsMsg');
    
    if (visibleCount === 0) {
        if (!noResultsMsg) {
            noResultsMsg = document.createElement('p');
            noResultsMsg.id = 'noResultsMsg';
            noResultsMsg.style.color = '#a0abb8';
            noResultsMsg.style.gridColumn = '1 / -1';
            noResultsMsg.style.textAlign = 'center';
            grid.appendChild(noResultsMsg);
        }
        noResultsMsg.innerText = 'No versions found.';
        noResultsMsg.style.display = 'block';
    } else if (noResultsMsg) {
        noResultsMsg.style.display = 'none';
    }
}

async function loadMarketplace(software) {
    const grid = document.getElementById('marketplaceGrid');
    grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;"><p style="color: #a0abb8;">Fetching sorted versions from global API...</p></div>';
    const activeToast = showToast("Loading Versions...", "loading");

    try {
        const res = await fetch(`/api/versions/${software}`);
        const data = await res.json();

        if (activeToast) activeToast.remove();

        if (data.status === 'success') {
            grid.innerHTML = '';
            const displayVersions = data.versions.slice(0, 60);

            displayVersions.forEach(v => {
                grid.innerHTML += `
                    <div class="version-card">
                        <div class="card-title">${software.charAt(0).toUpperCase() + software.slice(1)}</div>
                        <div class="card-version">${v}</div>
                        <button class="select-btn" onclick="executeInstall('${software}', '${v}')">Select</button>
                    </div>
                `;
            });
        }
    } catch (e) { 
        if (activeToast) activeToast.remove();
        grid.innerHTML = '<p style="color: #ff4c4c;">Failed to load versions.</p>'; 
    }
}

async function executeInstall(software, version) {
    if (isInstalling) return;
    if (!confirm(`Install ${software} ${version}? This will wipe current server files!`)) return;

    isInstalling = true;
    const activeToast = showToast(`Installing ${software} ${version}...`, "loading");

    document.querySelectorAll('.select-btn').forEach(btn => btn.disabled = true);

    try {
        const res = await fetch(`/api/install/${software}/${version}`, { method: 'POST' });
        const data = await res.json();

        if (data.status === 'success') {
            if (activeToast) activeToast.remove();
            showToast(`Server Installed Successfully!`, 'success');
            checkStatus();
            switchTab('dashboard');
        } else {
            if (activeToast) activeToast.remove();
            showToast(data.message, 'error');
        }
    } catch (e) {
        if (activeToast) activeToast.remove();
        showToast("Installation is still running in the background. Please wait 60 seconds.", 'info');
    } finally {
        isInstalling = false;
        document.querySelectorAll('.select-btn').forEach(btn => btn.disabled = false);
    }
}

// --- PILL NAV LOGIC ---
function handleLogoEnter() {
    const logo = document.querySelector('.dx-logo');
    gsap.to(logo, { scale: 1.1, duration: 0.3, ease: "power2.out", yoyo: true, repeat: 1 });
}

let isMobileMenuOpen = false;
function toggleMobileMenu() {
    isMobileMenuOpen = !isMobileMenuOpen;
    const menu = document.getElementById('mobileMenu');
    const lines = document.querySelectorAll('.hamburger-line');

    if (isMobileMenuOpen) {
        gsap.to(lines[0], { rotation: 45, y: 8, duration: 0.4, ease: "power2.out" });
        gsap.to(lines[1], { opacity: 0, duration: 0.2 });
        gsap.to(lines[2], { rotation: -45, y: -8, duration: 0.4, ease: "power2.out" });
        menu.classList.add('active');
    } else {
        gsap.to(lines[0], { rotation: 0, y: 0, duration: 0.4, ease: "power2.in" });
        gsap.to(lines[1], { opacity: 1, duration: 0.2, delay: 0.2 });
        gsap.to(lines[2], { rotation: 0, y: 0, duration: 0.4, ease: "power2.in" });
        menu.classList.remove('active');
    }
}

window.addEventListener("load", () => {
    const splash = document.getElementById('splash-screen');
    if (splash) {
        gsap.timeline()
            .to('.splash-icon-wrapper', { scale: 1.08, duration: 0.4, ease: "power2.out" })
            .to(splash, { 
                opacity: 0, 
                duration: 0.4, 
                ease: "power2.inOut", 
                onComplete: () => {
                    splash.style.display = 'none';
                    splash.remove(); // Fully remove splash from DOM so it can never linger
                    
                    // Smooth Entrance for UI elements with clearProps so margins/layouts stay 100% intact
                    gsap.from('.topbar', { y: -30, opacity: 0, duration: 0.4, ease: "power2.out", clearProps: "all" });
                    gsap.from('.content-header', { y: -15, opacity: 0, duration: 0.4, delay: 0.1, ease: "power2.out", clearProps: "all" });
                    gsap.from('.metric-card', { 
                        y: 15, 
                        opacity: 0, 
                        duration: 0.4, 
                        stagger: 0.06, 
                        delay: 0.15, 
                        ease: "power2.out",
                        clearProps: "all"
                    });
                    gsap.from('.power-panel', { 
                        y: 15, 
                        opacity: 0, 
                        duration: 0.4, 
                        delay: 0.25, 
                        ease: "power2.out",
                        clearProps: "all"
                    });
                    gsap.from('.tab-content.active > .glass-panel:last-child', {
                        y: 15,
                        opacity: 0,
                        duration: 0.4,
                        delay: 0.3,
                        ease: "power2.out",
                        clearProps: "all"
                    });
                }
            });
    }
});

document.addEventListener("DOMContentLoaded", () => {
    initIpDisplay();
    checkStatus();
    fetchStats();
    fetchConsoleLogs();
});
setInterval(checkStatus, 5000);

// --- PLAYER MANAGEMENT ---
async function fetchPlayers() {
    const playerList = document.getElementById('playerList');
    playerList.innerHTML = '<div class="skeleton" style="height: 60px; margin-bottom: 10px;"></div>';
    
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        
        playerList.innerHTML = '';
        
        // --- ONLINE SECTION ---
        if (data.online_players && data.online_players.length > 0) {
            const h = document.createElement('h3');
            h.style.cssText = 'margin: 10px 0; font-size: 0.9rem; color: #00ff7f; display: flex; align-items: center; gap: 8px;';
            h.innerHTML = `<i data-lucide="zap" style="width:14px;height:14px"></i> Online Now`;
            playerList.appendChild(h);
            data.online_players.forEach(p => playerList.appendChild(createPlayerCard(p, true)));
        }

        // --- HISTORY SECTION ---
        const historyPlayers = (data.all_players || []).filter(name => 
            !data.online_players.some(op => op.name === name)
        );

        if (historyPlayers.length > 0) {
            const h = document.createElement('h3');
            h.style.cssText = 'margin: 25px 0 10px; font-size: 0.9rem; color: #8892a0; display: flex; align-items: center; gap: 8px;';
            h.innerHTML = `<i data-lucide="history" style="width:14px;height:14px"></i> Player History`;
            playerList.appendChild(h);
            historyPlayers.forEach(name => {
                playerList.appendChild(createPlayerCard({name: name}, false));
            });
        }
        
        if (data.online_players.length === 0 && historyPlayers.length === 0) {
            playerList.innerHTML = '<div style="text-align:center; padding: 40px; color: #5c6672; font-style: italic;">No player history found.</div>';
        }
        
        lucide.createIcons();
    } catch (e) {
        playerList.innerHTML = '<div class="no-players">Could not fetch players.</div>';
    }
}

function createPlayerCard(p, isOnline) {
    const card = document.createElement('div');
    card.className = `player-card ${!isOnline ? 'offline' : ''}`;
    card.innerHTML = `
        <div class="player-main" onclick="togglePlayerDetail(this)">
            <div class="player-info">
                <img src="https://mc-heads.net/avatar/${p.name}/40" class="player-avatar" style="filter: ${isOnline ? 'none' : 'grayscale(1)'}">
                <div>
                    <div class="player-name">${p.name}</div>
                    <div class="player-status" style="color: ${isOnline ? '#00ff7f' : '#8892a0'}">${isOnline ? 'Online' : 'Offline'}</div>
                </div>
            </div>
            <div class="expand-btn">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 20px;">
                    <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
            </div>
        </div>
        <div class="player-details">
            <div class="player-actions" style="margin-bottom: 15px; flex-wrap: wrap;">
                <button class="action-btn stop" onclick="apiCall('/api/command', {command: 'kill ${p.name}'})">
                    <svg style="width:14px;height:14px;margin-right:5px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg> Kill
                </button>
                <button class="action-btn stop" onclick="apiCall('/api/command', {command: 'ban ${p.name}'})">
                    <svg style="width:14px;height:14px;margin-right:5px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg> Ban
                </button>
                <button class="action-btn neutral" onclick="apiCall('/api/command', {command: 'pardon ${p.name}'})">
                    <svg style="width:14px;height:14px;margin-right:5px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><polyline points="17 11 19 13 23 9"/></svg> Unban
                </button>
                <button class="action-btn restart" onclick="apiCall('/api/command', {command: 'op ${p.name}'})">
                    <svg style="width:14px;height:14px;margin-right:5px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> Op
                </button>
                <button class="action-btn start" onclick="apiCall('/api/command', {command: 'deop ${p.name}'})">
                     <svg style="width:14px;height:14px;margin-right:5px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="17" y1="8" x2="23" y2="14"/><line x1="23" y1="8" x2="17" y2="14"/></svg> De-Op
                </button>
            </div>
            <div style="padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.05);">
                <label style="display:flex; align-items:center; gap:5px; font-size: 0.75rem; color: #8892a0; margin-bottom: 12px;">
                    <svg style="width:12px;height:12px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg> Change Gamemode
                </label>
                <div class="player-actions">
                    <button class="action-btn start" style="font-size: 0.7rem; padding: 5px 12px;" onclick="apiCall('/api/command', {command: 'gamemode survival ${p.name}'})">Survival</button>
                    <button class="action-btn restart" style="font-size: 0.7rem; padding: 5px 12px;" onclick="apiCall('/api/command', {command: 'gamemode creative ${p.name}'})">Creative</button>
                    <button class="action-btn stop" style="font-size: 0.7rem; padding: 5px 12px;" onclick="apiCall('/api/command', {command: 'gamemode spectator ${p.name}'})">Spectator</button>
                </div>
            </div>
        </div>
    `;
    return card;
}

function togglePlayerDetail(element) {
    const card = element.closest('.player-card');
    card.classList.toggle('expanded');
}
// Modal system removed in favor of Toast notifications.