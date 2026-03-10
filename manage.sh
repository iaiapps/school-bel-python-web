#!/bin/bash

# ==========================================
# Management Script - Aplikasi Bel Sekolah
# Usage: ./manage.sh [command]
# Commands: start, stop, restart, status, info, logs
# ==========================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE_NAME="bel-sekolah.service"
APP_NAME="Aplikasi Bel Sekolah"

# Required pip packages
REQUIRED_PACKAGES=("mutagen")

# Helper functions
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }

check_python_packages() {
    print_info "Checking required Python packages..."
    
    # Check if venv exists
    if [ ! -d "venv" ]; then
        print_warning "Virtual environment not found. Creating..."
        python3 -m venv venv
        print_success "Virtual environment created"
    fi
    
    # Activate venv
    source venv/bin/activate
    
    # Check and install required packages
    for pkg in "${REQUIRED_PACKAGES[@]}"; do
        if pip show "$pkg" > /dev/null 2>&1; then
            print_success "$pkg already installed"
        else
            print_info "Installing $pkg..."
            pip install "$pkg"
            if [ $? -eq 0 ]; then
                print_success "$pkg installed"
            else
                print_error "Failed to install $pkg"
            fi
        fi
    done
    
    # Check requirements.txt if exists
    if [ -f "requirements.txt" ]; then
        print_info "Installing packages from requirements.txt..."
        pip install -r requirements.txt
        print_success "Requirements installed"
    fi
    
    deactivate
}

get_ip_address() {
    IP=$(hostname -I | awk '{print $1}')
    [ -z "$IP" ] && IP="localhost"
    echo "$IP"
}

get_port() {
    python3 -c "from config import Config; print(Config.PORT)" 2>/dev/null || echo "5000"
}

is_running() {
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        return 0
    fi
    if pgrep -f "python.*run.py" > /dev/null; then
        return 0
    fi
    return 1
}

show_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              🔧 MANAGEMENT BEL SEKOLAH                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

show_help() {
    show_banner
    echo "Usage: ./manage.sh [command]"
    echo ""
    echo -e "${BLUE}Commands:${NC}"
    echo "  ${GREEN}start${NC}         - Start aplikasi (manual mode)"
    echo "  ${GREEN}stop${NC}          - Stop aplikasi"
    echo "  ${GREEN}restart${NC}       - Restart aplikasi"
    echo "  ${GREEN}status${NC}        - Cek status aplikasi"
    echo "  ${GREEN}info${NC}          - Tampilkan info akses & QR code"
    echo "  ${GREEN}logs${NC}          - Lihat log aplikasi"
    echo "  ${GREEN}install-deps${NC}  - Install dependencies (mutagen, etc)"
    echo "  ${GREEN}help${NC}          - Tampilkan bantuan ini"
    echo ""
    echo -e "${YELLOW}Note:${NC} Untuk install/uninstall, gunakan:"
    echo "  sudo ./install.sh      # Install aplikasi"
    echo "  sudo ./uninstall.sh    # Uninstall aplikasi"
    echo ""
}

cmd_start() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Starting ${APP_NAME}${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    
    # Check and install required packages
    check_python_packages
    
    # Check if venv exists
    if [ ! -d "venv" ]; then
        print_error "Virtual environment not found."
        echo "  Please run: sudo ./install.sh"
        exit 1
    fi
    if [ ! -d "venv" ]; then
        print_error "Virtual environment not found."
        echo "  Please run: sudo ./install.sh"
        exit 1
    fi
    
    # Check if running via systemd
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        print_info "Service sudah berjalan via systemd"
        echo "  Use: sudo systemctl status ${SERVICE_NAME}"
        exit 0
    fi
    
    # Check if already running manually
    if pgrep -f "python.*run.py" > /dev/null; then
        print_warning "Aplikasi sudah berjalan (manual)"
        exit 0
    fi
    
    # Activate and start
    source venv/bin/activate
    print_success "Starting application..."
    echo ""
    python3 run.py
}

cmd_stop() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Stopping ${APP_NAME}${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    
    # Check if running via systemd
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        print_info "Stopping systemd service..."
        sudo systemctl stop "${SERVICE_NAME}"
        print_success "Service stopped"
        return
    fi
    
    # Try to find and kill manual process
    PID=$(pgrep -f "python.*run.py" | head -1)
    
    if [ -z "$PID" ]; then
        print_error "Aplikasi tidak berjalan"
        exit 1
    else
        print_info "Stopping application (PID: ${PID})..."
        kill "$PID"
        sleep 1
        
        # Force kill if still running
        if kill -0 "$PID" 2>/dev/null; then
            echo "Force stopping..."
            kill -9 "$PID"
        fi
        
        print_success "Application stopped"
    fi
}

cmd_restart() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Restarting ${APP_NAME}${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        print_info "Restarting systemd service..."
        sudo systemctl restart "${SERVICE_NAME}"
        sleep 2
        if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
            print_success "Service restarted successfully"
        else
            print_error "Service failed to restart"
        fi
    else
        cmd_stop
        sleep 1
        cmd_start
    fi
}

cmd_status() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Status ${APP_NAME}${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        print_success "Service status: RUNNING (systemd)"
        echo ""
        sudo systemctl status "${SERVICE_NAME}" --no-pager
    elif pgrep -f "python.*run.py" > /dev/null; then
        PID=$(pgrep -f "python.*run.py" | head -1)
        print_success "Application status: RUNNING (manual)"
        print_info "PID: ${PID}"
    else
        print_error "Application status: STOPPED"
        echo ""
        print_info "Start with: ./manage.sh start"
        print_info "   or: sudo systemctl start ${SERVICE_NAME}"
    fi
}

cmd_info() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           📱 INFO AKSES APLIKASI BEL SEKOLAH                ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    
    IP_ADDRESS=$(get_ip_address)
    HOSTNAME=$(hostname)
    PORT=$(get_port)
    
    echo -e "${BLUE}🌐 URL Akses:${NC}"
    echo ""
    echo -e "  ${GREEN}➜ http://${IP_ADDRESS}:${PORT}${NC}"
    echo ""
    echo -e "  Alternatif:"
    echo -e "  • http://${HOSTNAME}.local:${PORT}  (jika mDNS aktif)"
    echo -e "  • http://localhost:${PORT}          (dari Raspberry Pi)"
    echo ""
    
    # Generate QR Code if qrencode available
    if command -v qrencode &> /dev/null; then
        echo -e "${BLUE}📱 Scan QR Code dengan HP:${NC}"
        echo ""
        URL="http://${IP_ADDRESS}:${PORT}"
        qrencode -t ANSIUTF8 -m 2 "${URL}"
        echo ""
    fi
    
    # Check if access-qr.png exists
    if [ -f "access-qr.png" ]; then
        echo -e "${BLUE}📁 File QR Code:${NC} access-qr.png (print dan tempel!)"
        echo ""
    fi
    
    echo -e "${BLUE}🔐 Login:${NC}"
    echo "  Username: admin"
    echo "  Password: admin123"
    echo ""
    
    # Status
    echo -e "${BLUE}📊 Status:${NC}"
    if is_running; then
        print_success "Aplikasi berjalan"
    else
        print_warning "Aplikasi tidak berjalan"
        echo "    Start: ./manage.sh start"
    fi
    echo ""
    
    # Network info
    echo -e "${BLUE}🌐 Info Jaringan:${NC}"
    echo "  IP Address: ${IP_ADDRESS}"
    echo "  Hostname:   ${HOSTNAME}"
    echo "  Port:       ${PORT}"
    echo ""
    
    echo -e "${YELLOW}💡 Tips:${NC}"
    echo "  • Pastikan HP dan Raspberry Pi di WiFi yang sama"
    echo "  • Bookmark URL di browser HP untuk akses cepat"
    echo ""
}

cmd_logs() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Logs ${APP_NAME}${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null || systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
        print_info "Menampilkan log dari systemd (tekan Ctrl+C untuk keluar)..."
        echo ""
        sudo journalctl -u "${SERVICE_NAME}" -f --no-pager
    else
        print_warning "Service systemd tidak aktif"
        print_info "Log untuk manual mode tidak tersedia"
    fi
}

cmd_install_deps() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Install Dependencies ${APP_NAME}${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    
    check_python_packages
    print_success "Dependencies installation complete!"
}

# Main
COMMAND="${1:-help}"

case "$COMMAND" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    status)
        cmd_status
        ;;
    info)
        cmd_info
        ;;
    logs)
        cmd_logs
        ;;
    install-deps)
        cmd_install_deps
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Command tidak dikenal: $COMMAND"
        echo ""
        show_help
        exit 1
        ;;
esac
