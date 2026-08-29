// Premium Toast Notification System
function showToast(message, type = 'success', undoAction = null) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let iconHtml = '';
    if (type === 'loading') {
        iconHtml = `
            <div class="toast-orbital-spinner">
                <div class="orbital-ring-outer"></div>
                <div class="orbital-ring-inner"></div>
                <i data-lucide="zap" class="orbital-center-icon"></i>
            </div>
        `;
    } else {
        const icons = {
            success: 'check-circle',
            error: 'alert-circle',
            info: 'info'
        };
        const iconName = icons[type] || 'bell';
        iconHtml = `<i data-lucide="${iconName}" class="toast-icon"></i>`;
    }
    
    toast.innerHTML = `
        ${iconHtml}
        <div class="toast-content">
            <span class="toast-message">${message}</span>
            ${type === 'loading' ? '<div class="toast-loading-bar"><div class="toast-loading-fill"></div></div>' : ''}
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

    return toast; // Return toast element so it can be manually removed
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

    // Update Nav Items (Desktop Topbar Pills)
    document.querySelectorAll('.pill, .nav-item').forEach(el => {
        el.classList.remove('active');
        el.classList.remove('is-active');
    });
    document.querySelectorAll(`.pill[onclick*="'${tabId}'"], .nav-item[onclick*="'${tabId}'"]`).forEach(btn => {
        btn.classList.add('active');
    });

    // Update Mobile Drawer Links
    document.querySelectorAll('.mobile-nav-link').forEach(el => {
        el.classList.remove('is-active');
        el.classList.remove('active');
    });
    document.querySelectorAll(`.mobile-nav-link[onclick*="'${tabId}'"]`).forEach(link => {
        link.classList.add('is-active');
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
                'plugins': 'Plugin Marketplace',
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
    if (tabId === 'plugins') loadPlugins();
    if (tabId === 'players') fetchPlayers();
}

// --- IP Logic ---
function initIpDisplay() {
    const el = document.getElementById('serverIpDisplay');
    if (el) el.innerText = window.location.hostname + ":25565";
}

async function copyIp() {
    const ipText = window.location.hostname + ":25565";
    let copied = false;

    // Try modern Clipboard API
    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(ipText);
            copied = true;
        } catch (e) {
            copied = false;
        }
    }

    // Fallback for non-HTTPS / HTTP IP origins
    if (!copied) {
        try {
            const textArea = document.createElement("textarea");
            textArea.value = ipText;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            textArea.style.top = "-999999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            copied = document.execCommand('copy');
            textArea.remove();
        } catch (err) {
            copied = false;
        }
    }

    // Visual button bounce & icon checkmark feedback
    const btn = document.querySelector('#connectionBar .icon-btn');
    if (btn) {
        btn.innerHTML = `<i data-lucide="check" style="width: 14px; height: 14px; color: var(--primary);"></i>`;
        lucide.createIcons();
        setTimeout(() => {
            btn.innerHTML = `<i data-lucide="copy" style="width: 14px; height: 14px;"></i>`;
            lucide.createIcons();
        }, 2000);
    }

    showToast(`⚡ Server IP (${ipText}) copied to clipboard!`, "success");
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
        const startTime = performance.now();
        const res = await fetch('/api/stats');
        const latency = performance.now() - startTime;
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
            if (startBtn && !isWaitingForStart) {
                startBtn.classList.remove('is-loading');
                startBtn.disabled = true; // Server is already running
            }
            if (stopBtn) stopBtn.disabled = false;
            if (restartBtn && !isWaitingForStart) {
                restartBtn.classList.remove('is-loading');
                restartBtn.disabled = false;
            }
        } else {
            if (globalStatusBadge && !isWaitingForStart) {
                globalStatusBadge.classList.add('offline');
                globalStatusText.innerText = "OFFLINE";
            }
            if (startBtn && !isWaitingForStart) startBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = true; // Disabled when offline
            if (restartBtn && !isWaitingForStart) restartBtn.disabled = true; // Disabled when offline
        }
        
        // RAM
        const ramBar = document.getElementById('bar-ram');
        if (ramBar) ramBar.style.width = `${data.ram_percent}%`;
        const textRam = document.getElementById('text-ram');
        if (textRam) textRam.innerText = `${data.ram_percent}%`;
        const subRam = document.getElementById('sub-ram');
        const usedMb = data.ram_used_mb || 0;
        const totalMb = data.ram_allocated_mb || data.ram_total_mb || 2048;
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

        // Server Ping (Latency)
        const textPing = document.getElementById('text-ping');
        const subPing = document.getElementById('sub-ping');
        const barPing = document.getElementById('bar-ping');
        
        if (data.status === 'online') {
            // Measure pure network ping
            try {
                const pStart = performance.now();
                await fetch('/api/ping', { cache: 'no-store' });
                const realPing = Math.max(1, Math.round(performance.now() - pStart));
                
                if (textPing) textPing.innerText = `${realPing} ms`;
                if (subPing) {
                    if (realPing < 60) subPing.innerText = "Ultra Low Latency";
                    else if (realPing < 120) subPing.innerText = "Good Connection";
                    else if (realPing < 200) subPing.innerText = "Moderate Ping";
                    else subPing.innerText = "High Latency";
                }
                if (barPing) {
                    const barPercent = Math.max(15, Math.min(100, 100 - (realPing / 3)));
                    barPing.style.width = `${barPercent}%`;
                }
            } catch {
                if (textPing) textPing.innerText = `${Math.round(latency)} ms`;
            }
        } else {
            if (textPing) textPing.innerText = "-- ms";
            if (subPing) subPing.innerText = "Server Offline";
            if (barPing) barPing.style.width = "0%";
        }
    } catch (e) { }
}
setInterval(fetchStats, 2500);

// --- INTERACTIVE CONSOLE ---
const logDiv = document.getElementById('log');
let autoScroll = true;
let isWaitingForStart = false;
let startSessionTime = 0;
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
            
            // Only evaluate boot completion if we have been waiting for at least 3 seconds
            const elapsedSinceAction = (Date.now() - startSessionTime) / 1000;
            const isBootDoneText = data.log.includes('Done (') || data.log.includes('For help, type "help"') || data.log.includes('Timings Reset');
            
            if (isWaitingForStart && elapsedSinceAction > 3 && isBootDoneText) {
                // Double-check with stats that server process is truly active
                try {
                    const statsRes = await fetch('/api/stats');
                    const statsData = await statsRes.json();
                    if (statsData.status === 'online') {
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
                            startBtn.disabled = true;
                        }
                        const restartBtn = document.querySelector('button[onclick="apiCall(\'/api/restart\')"]');
                        if (restartBtn) {
                            restartBtn.classList.remove('is-loading');
                            restartBtn.innerHTML = '<i data-lucide="refresh-cw" style="width:16px;height:16px;"></i> Restart';
                            restartBtn.disabled = false;
                        }
                        const stopBtn = document.querySelector('button[onclick="apiCall(\'/api/stop\')"]');
                        if (stopBtn) stopBtn.disabled = false;
                        
                        lucide.createIcons();
                        fetchStats();
                    }
                } catch (err) {}
            }

            // Check if server failed / crashed on boot
            if (isWaitingForStart && elapsedSinceAction > 2 && (data.log.includes('Address already in use') || data.log.includes('UnsupportedClassVersionError') || data.log.includes('Error: Unable to access jarfile') || data.log.includes('Exception in thread "main"'))) {
                if (startLoadingToast) {
                    startLoadingToast.remove();
                    startLoadingToast = null;
                }
                showToast("Startup error detected in console logs. Check terminal stream.", "error");
                isWaitingForStart = false;
                
                const startBtn = document.querySelector('button[onclick="apiCall(\'/api/start\')"]');
                if (startBtn) {
                    startBtn.classList.remove('is-loading');
                    startBtn.innerHTML = '<i data-lucide="play" style="width:16px;height:16px;"></i> Start';
                    startBtn.disabled = false;
                }
                const restartBtn = document.querySelector('button[onclick="apiCall(\'/api/restart\')"]');
                if (restartBtn) {
                    restartBtn.classList.remove('is-loading');
                    restartBtn.innerHTML = '<i data-lucide="refresh-cw" style="width:16px;height:16px;"></i> Restart';
                }
                lucide.createIcons();
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
        const cmd = this.value.trim();
        if (cmd) {
            this.value = '';
            await apiCall('/api/command', { command: cmd });
        }
    }
});

// --- POWER API ---
async function apiCall(endpoint, body = null) {
    const isPowerAction = ['/api/start', '/api/stop', '/api/restart', '/api/delete', '/api/world/regenerate'].includes(endpoint);
    
    let activeToast = null;
    const startBtn = document.querySelector('button[onclick="apiCall(\'/api/start\')"]');
    const stopBtn = document.querySelector('button[onclick="apiCall(\'/api/stop\')"]');
    const restartBtn = document.querySelector('button[onclick="apiCall(\'/api/restart\')"]');
    const globalStatusBadge = document.getElementById('globalStatusBadge');
    const globalStatusText = document.getElementById('globalStatusText');

    if (isPowerAction) {
        let msg = "Processing request...";
        if (endpoint === '/api/start') { 
            msg = "Booting Minecraft Engine (Generating spawn & preparing chunks)..."; 
            isWaitingForStart = true;
            startSessionTime = Date.now();
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
            if (restartBtn) {
                restartBtn.classList.remove('is-loading');
                restartBtn.innerHTML = '<i data-lucide="refresh-cw" style="width:16px;height:16px;"></i> Restart';
                lucide.createIcons();
            }
        }
        if (endpoint === '/api/restart') { 
            msg = "Rebooting Minecraft Server (Safely cycling engine)..."; 
            isWaitingForStart = true;
            startSessionTime = Date.now();
            if (restartBtn) {
                restartBtn.classList.add('is-loading');
                restartBtn.innerHTML = '<i data-lucide="loader" class="spin-icon" style="width:16px;height:16px;"></i> Restarting...';
                lucide.createIcons();
            }
            if (globalStatusBadge) {
                globalStatusBadge.className = 'server-status-pill starting';
                if (globalStatusText) globalStatusText.innerText = "RESTARTING...";
            }
        }
        if (endpoint === '/api/delete') { msg = "Wiping Server Files..."; }
        if (endpoint === '/api/world/regenerate') { msg = "Regenerating World..."; }
        
        activeToast = showToast(msg, "loading");
        if (endpoint === '/api/start' || endpoint === '/api/restart') {
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
        let data = {};
        const responseText = await response.text();
        try {
            data = JSON.parse(responseText);
        } catch (jsonErr) {
            data = { status: 'error', message: response.ok ? responseText : `Server responded with ${response.status}: ${responseText || response.statusText}` };
        }
        
        if (response.ok && data.status === 'success') {
            if (endpoint !== '/api/start' && endpoint !== '/api/restart' && activeToast) {
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
            if (restartBtn) {
                restartBtn.classList.remove('is-loading');
                restartBtn.innerHTML = '<i data-lucide="refresh-cw" style="width:16px;height:16px;"></i> Restart';
                lucide.createIcons();
            }
            showToast(data.message || "An unexpected error occurred", 'error');
            isWaitingForStart = false;
        }
    } catch (error) { 
        if (activeToast) activeToast.remove();
        if (startBtn) {
            startBtn.classList.remove('is-loading');
            startBtn.innerHTML = '<i data-lucide="play" style="width:16px;height:16px;"></i> Start';
            lucide.createIcons();
        }
        if (restartBtn) {
            restartBtn.classList.remove('is-loading');
            restartBtn.innerHTML = '<i data-lucide="refresh-cw" style="width:16px;height:16px;"></i> Restart';
            lucide.createIcons();
        }
        showToast("Operation failed: " + error.message, 'error');
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

function navigateFileBack() {
    if (!currentPath) return;
    const parentPath = currentPath.substring(0, currentPath.lastIndexOf('/'));
    loadFiles(parentPath);
}

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
            
            // Update Header Back Button
            const backBtn = document.getElementById('fileBackButton');
            if (backBtn) {
                backBtn.style.display = currentPath ? 'inline-flex' : 'none';
            }
            
            // Build interactive breadcrumbs
            const pathDisplay = document.getElementById('currentPathDisplay');
            if (pathDisplay) {
                if (!currentPath) {
                    pathDisplay.innerHTML = `<span style="color: var(--primary);">/root</span>`;
                } else {
                    const parts = currentPath.split('/');
                    let html = `<span style="cursor: pointer; color: var(--text-muted);" onclick="loadFiles('')">/root</span>`;
                    let accumulated = '';
                    parts.forEach((part, index) => {
                        accumulated += (index === 0 ? '' : '/') + part;
                        const targetAcc = accumulated;
                        const isLast = (index === parts.length - 1);
                        html += ` <span style="color: rgba(255,255,255,0.3); font-weight:400;">/</span> <span style="${isLast ? 'color: var(--primary); font-weight: 700;' : 'color: var(--text-muted); cursor: pointer;'}" onclick="loadFiles('${targetAcc}')">${part}</span>`;
                    });
                    pathDisplay.innerHTML = html;
                }
            }

            const tbody = document.getElementById('fileListBody');
            tbody.innerHTML = '';
            
            if (currentPath !== '') {
                const parentPath = currentPath.substring(0, currentPath.lastIndexOf('/'));
                tbody.innerHTML += `
                    <tr class="file-row" style="background: rgba(230, 255, 0, 0.04); cursor: pointer;" onclick="loadFiles('${parentPath}')">
                        <td colspan="4" style="padding: 12px 16px;">
                            <div style="display:flex; align-items:center; gap:10px; color: var(--primary); font-weight: 700;">
                                <i data-lucide="arrow-left" style="width:16px;height:16px"></i>
                                <span>.. (Back to parent directory)</span>
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

// --- DRAG & DROP & MULTI-FILE UPLOADER ---
function initDragAndDrop() {
    const dropTarget = document.getElementById('fileExplorer');
    if (!dropTarget) return;

    ['dragenter', 'dragover'].forEach(eventName => {
        window.addEventListener(eventName, (e) => {
            const filesTab = document.getElementById('tab-files');
            if (filesTab && filesTab.classList.contains('active')) {
                e.preventDefault();
                e.stopPropagation();
                dropTarget.classList.add('drag-over');
            }
        }, false);
    });

    ['dragleave', 'dragend'].forEach(eventName => {
        window.addEventListener(eventName, (e) => {
            if (e.clientX <= 0 || e.clientY <= 0 || e.clientX >= window.innerWidth || e.clientY >= window.innerHeight) {
                dropTarget.classList.remove('drag-over');
            }
        }, false);
    });

    window.addEventListener('drop', (e) => {
        const filesTab = document.getElementById('tab-files');
        if (filesTab && filesTab.classList.contains('active')) {
            e.preventDefault();
            e.stopPropagation();
            dropTarget.classList.remove('drag-over');
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleMultiUpload(e.dataTransfer.files);
            }
        }
    }, false);
}

function dragOverHandler(e) { 
    e.preventDefault(); 
    e.stopPropagation();
    const el = document.getElementById('fileExplorer');
    if (el) el.classList.add('drag-over'); 
}

function dragLeaveHandler(e) { 
    e.preventDefault(); 
    e.stopPropagation();
    const el = document.getElementById('fileExplorer');
    if (el) el.classList.remove('drag-over'); 
}

async function dropHandler(e) {
    e.preventDefault();
    e.stopPropagation();
    const el = document.getElementById('fileExplorer');
    if (el) el.classList.remove('drag-over');
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleMultiUpload(e.dataTransfer.files);
    }
}

async function handleMultiUpload(files) {
    if (!files || files.length === 0) return;
    
    const fileArray = Array.from(files);
    const activeToast = showToast(`Uploading ${fileArray.length} file(s)...`, "loading");
    
    let uploadedPaths = [];
    const uploadPromises = fileArray.map(async (file) => {
        try {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("path", currentPath);
            const res = await fetch('/api/files/upload', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.status === 'success') {
                uploadedPaths.push(currentPath ? `${currentPath}/${file.name}` : file.name);
            }
        } catch (e) {
            console.error("Upload error for", file.name, e);
        }
    });

    await Promise.all(uploadPromises);
    
    if (activeToast) activeToast.remove();
    showToast(`⚡ Uploaded ${uploadedPaths.length}/${fileArray.length} files successfully!`, "success", uploadedPaths.length > 0 ? () => undoUpload(uploadedPaths) : null);
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

// --- PLUGIN MARKETPLACE ---
let activePluginView = 'browse';

function showPluginView(view) {
    activePluginView = view;
    const browseView = document.getElementById('pluginBrowseView');
    const installedView = document.getElementById('pluginInstalledView');
    const btnBrowse = document.getElementById('btn-browse-plugins');
    const btnInstalled = document.getElementById('btn-installed-plugins');

    if (view === 'browse') {
        browseView.style.display = 'block';
        installedView.style.display = 'none';
        btnBrowse.className = 'plugin-subnav-btn active';
        btnInstalled.className = 'plugin-subnav-btn';
    } else {
        browseView.style.display = 'none';
        installedView.style.display = 'block';
        btnBrowse.className = 'plugin-subnav-btn';
        btnInstalled.className = 'plugin-subnav-btn active';
        loadInstalledPlugins();
    }
}

async function loadPlugins(query = "") {
    const grid = document.getElementById('pluginGrid');
    if (!grid) return;
    grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;"><p style="color: #a0abb8;">Searching popular plugins from Modrinth & Spigot...</p></div>';
    
    try {
        const res = await fetch(`/api/plugins/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        
        if (data.status === 'success' && data.hits.length > 0) {
            grid.innerHTML = '';
            data.hits.forEach(plugin => {
                const card = document.createElement('div');
                card.className = 'plugin-card';
                const icon = plugin.icon_url || 'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9e9.png';
                const downloads = plugin.downloads > 1000 ? `${(plugin.downloads/1000).toFixed(1)}k` : plugin.downloads;
                
                card.innerHTML = `
                    <div>
                        <div class="plugin-header">
                            <img src="${icon}" class="plugin-icon" onerror="this.src='https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9e9.png'">
                            <div class="plugin-info">
                                <div class="plugin-title" title="${plugin.title}">${plugin.title}</div>
                                <div class="plugin-author">by ${plugin.author || 'Community'}</div>
                            </div>
                        </div>
                        <p class="plugin-desc" title="${plugin.description || ''}">${plugin.description || 'No description available.'}</p>
                    </div>
                    <div class="plugin-meta">
                        <div class="plugin-stats">
                            <span><i data-lucide="download" style="width:12px;height:12px"></i> ${downloads}</span>
                            <span><i data-lucide="heart" style="width:12px;height:12px"></i> ${plugin.follows || 0}</span>
                        </div>
                        <button class="plugin-install-btn" onclick="installPlugin('${plugin.id}', '${plugin.title.replace(/'/g, "\\'")}', '${plugin.source || 'modrinth'}')">
                            <i data-lucide="download" style="width:13px;height:13px"></i> Install
                        </button>
                    </div>
                `;
                grid.appendChild(card);
            });
            lucide.createIcons();
        } else {
            grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;"><p style="color: #a0abb8;">No plugins found for this query. Try a broader search keyword.</p></div>';
        }
        loadInstalledPluginsCount();
    } catch (e) {
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;"><p style="color: #ff4757;">Failed to connect to plugin index.</p></div>';
    }
}

let searchDebounceTimer = null;
function debouncePluginSearch(query) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        loadPlugins(query);
    }, 350);
}

async function searchPlugins(query) {
    loadPlugins(query);
}

async function installPlugin(id, title, source = "modrinth") {
    const activeToast = showToast(`Downloading & applying ${title}...`, "loading");
    try {
        const res = await fetch('/api/plugins/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id, source: source })
        });
        const data = await res.json();
        if (activeToast) activeToast.remove();
        
        if (data.status === 'success') {
            showToast(`⚡ ${title} installed & applied to /plugins folder! Restart server to enable.`, "success");
            loadInstalledPluginsCount();
        } else {
            showToast(data.message || "Failed to install plugin", "error");
        }
    } catch (e) {
        if (activeToast) activeToast.remove();
        showToast("Error communicating with download API.", "error");
    }
}

async function loadInstalledPlugins() {
    const body = document.getElementById('installedPluginsBody');
    if (!body) return;
    body.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px; color: #a0abb8;">Loading installed plugins...</td></tr>';
    
    try {
        const res = await fetch('/api/plugins/installed');
        const data = await res.json();
        if (data.status === 'success' && data.plugins.length > 0) {
            body.innerHTML = '';
            data.plugins.forEach(p => {
                const tr = document.createElement('tr');
                tr.className = 'file-row';
                const sizeKb = (p.size / 1024).toFixed(1) + ' KB';
                tr.innerHTML = `
                    <td style="font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px;">
                        <i data-lucide="box" style="width: 16px; height: 16px; color: var(--primary);"></i>
                        ${p.name}
                    </td>
                    <td>${sizeKb}</td>
                    <td><span style="color: var(--success-color); font-size: 0.78rem; font-weight: 700;">● Active</span></td>
                    <td style="text-align: right;">
                        <button class="action-btn stop" style="padding: 5px 10px; font-size: 0.72rem;" onclick="deletePlugin('${p.name}')">
                            <i data-lucide="trash-2" style="width: 13px; height: 13px;"></i> Remove
                        </button>
                    </td>
                `;
                body.appendChild(tr);
            });
            lucide.createIcons();
        } else {
            body.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 30px; color: #a0abb8;">No plugins installed yet in <code>mc_server/plugins/</code>. Browse and install above!</td></tr>';
        }
        loadInstalledPluginsCount();
    } catch (e) {
        body.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px; color: #ff4757;">Failed to read plugins directory.</td></tr>';
    }
}

async function loadInstalledPluginsCount() {
    try {
        const res = await fetch('/api/plugins/installed');
        const data = await res.json();
        if (data.status === 'success') {
            const el = document.getElementById('installedPluginCount');
            if (el) el.innerText = data.plugins.length;
        }
    } catch (e) {}
}

async function deletePlugin(name) {
    if (!confirm(`Delete plugin ${name}?`)) return;
    const activeToast = showToast(`Removing ${name}...`, "loading");
    try {
        const res = await fetch('/api/plugins/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name })
        });
        const data = await res.json();
        if (activeToast) activeToast.remove();
        if (data.status === 'success') {
            showToast(`Plugin ${name} deleted.`, "success");
            loadInstalledPlugins();
        } else {
            showToast(data.message, "error");
        }
    } catch (e) {
        if (activeToast) activeToast.remove();
        showToast("Error deleting plugin.", "error");
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
    initDragAndDrop();
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

// Background Video Auto-play Insurance
document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('bgVideo');
    if (video) {
        video.muted = true;
        const playPromise = video.play();
        if (playPromise !== undefined) {
            playPromise.catch(() => {
                // If browser autoplay policy paused it, play on first user interaction
                window.addEventListener('click', () => video.play(), { once: true });
                window.addEventListener('touchstart', () => video.play(), { once: true });
            });
        }
    }
});