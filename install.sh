#!/bin/bash
# ==============================================================================
# 🚀 Valqore Hosting — Universal 1-Line Automated Installer & Setup Script
# ==============================================================================
# Supported OS: Ubuntu 20.04 / 22.04 / 24.04 & Debian 11 / 12
# Usage: curl -sSL https://raw.githubusercontent.com/Zamir-MoN/VPhosting/main/install.sh | bash
# ==============================================================================

set -e

# Color definitions
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
PURPLE='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

clear
echo -e "${PURPLE}${BOLD}"
echo "██╗   ██╗ █████╗ ██╗      ██████╗  ██████╗ ██████╗ ███████╗"
echo "██║   ██║██╔══██╗██║     ██╔═══██╗██╔═══██╗██╔══██╗██╔════╝"
echo "██║   ██║███████║██║     ██║   ██║██║   ██║██████╔╝█████╗  "
echo "╚██╗ ██╔╝██╔══██║██║     ██║▄▄ ██║██║   ██║██╔══██╗██╔══╝  "
echo " ╚████╔╝ ██║  ██║███████╗╚██████╔╝╚██████╔╝██║  ██║███████╗"
echo "  ╚═══╝  ╚═╝  ╚═╝╚══════╝ ╚══▀▀═╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝"
echo -e "${CYAN}      ⚡ Minecraft Game Management Panel — Automated Setup ⚡${NC}\n"

# 1. Check Root / Sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Please run this script as root or using sudo.${NC}"
    exit 1
fi

# Detect current non-root user or fallback to root
CURRENT_USER="${SUDO_USER:-$USER}"
if [ "$CURRENT_USER" = "root" ]; then
    INSTALL_DIR="/root/valqore"
else
    INSTALL_DIR="/home/$CURRENT_USER/valqore"
fi

echo -e "${CYAN}📌 User detected:${NC} ${BOLD}$CURRENT_USER${NC}"
echo -e "${CYAN}📁 Installation Path:${NC} ${BOLD}$INSTALL_DIR${NC}\n"

# 2. Update System Packages & Install Core Dependencies
echo -e "${YELLOW}⚡ [1/5] Updating packages and installing Java 21, Python 3, and utilities...${NC}"
apt-get update -y
apt-get install -y python3 python3-pip python3-venv openjdk-21-jre-headless git tmux curl ufw

# 3. Clone or Update Valqore Repository
echo -e "${YELLOW}⚡ [2/5] Setting up Valqore panel files...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${CYAN}ℹ️ Existing installation found in $INSTALL_DIR. Pulling latest updates...${NC}"
    cd "$INSTALL_DIR"
    git pull origin main || true
else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone https://github.com/Zamir-MoN/VPhosting.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Set proper ownership
chown -R "$CURRENT_USER:$CURRENT_USER" "$INSTALL_DIR"

# 4. Create Virtual Environment & Install Python Dependencies
echo -e "${YELLOW}⚡ [3/5] Configuring Python environment and requirements...${NC}"
if [ ! -d "$INSTALL_DIR/venv" ]; then
    sudo -u "$CURRENT_USER" python3 -m venv "$INSTALL_DIR/venv"
fi

sudo -u "$CURRENT_USER" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$CURRENT_USER" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# 5. Create and Enable Systemd Background Service
echo -e "${YELLOW}⚡ [4/5] Creating 24/7 System Background Service (valqore.service)...${NC}"
cat <<EOF > /etc/systemd/system/valqore.service
[Unit]
Description=Valqore Hosting Minecraft Panel Service
After=network.target

[Service]
User=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8090
Restart=always
RestartSec=5
Environment=PATH=/usr/bin:/bin:/usr/local/bin:$INSTALL_DIR/venv/bin

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable valqore
systemctl restart valqore

# 6. Configure Firewall Ports
echo -e "${YELLOW}⚡ [5/5] Configuring firewall rules for web panel and Minecraft...${NC}"
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 8090/tcp >/dev/null 2>&1 || true
ufw allow 25565/tcp >/dev/null 2>&1 || true
ufw allow 25565/udp >/dev/null 2>&1 || true

# Get Server Public IP
PUBLIC_IP=$(curl -s https://api.ipify.org || curl -s https://ifconfig.me || hostname -I | awk '{print $1}')

echo -e "\n${GREEN}${BOLD}========================================================================${NC}"
echo -e "${GREEN}${BOLD}🎉 CONGRATULATIONS! VALQORE PANEL IS INSTALLED & RUNNING 24/7! 🎉${NC}"
echo -e "${GREEN}${BOLD}========================================================================${NC}\n"
echo -e "🌐 ${BOLD}Open your Web Dashboard in your browser:${NC}"
echo -e "   👉 ${CYAN}${BOLD}http://${PUBLIC_IP}:8090${NC}\n"
echo -e "🎮 ${BOLD}Minecraft Game Server Connection Address:${NC}"
echo -e "   👉 ${YELLOW}${BOLD}${PUBLIC_IP}:25565${NC}\n"
echo -e "⚙️ ${BOLD}Quick Management Commands:${NC}"
echo -e "   • Check Status:    ${CYAN}sudo systemctl status valqore${NC}"
echo -e "   • Restart Panel:   ${CYAN}sudo systemctl restart valqore${NC}"
echo -e "   • Live Logs:       ${CYAN}sudo journalctl -u valqore -f${NC}"
echo -e "${GREEN}${BOLD}========================================================================${NC}\n"
