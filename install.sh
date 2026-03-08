#!/bin/bash

# ==========================================
# One-Click Installer - Aplikasi Bel Sekolah
# Usage: sudo ./install.sh
# ==========================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Bel Sekolah"
SERVICE_NAME="bel-sekolah.service"
DEFAULT_HOSTNAME="bel-sekolah"

# ==========================================
# Helper Functions
# ==========================================
print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║           🔔 APLIKASI BEL SEKOLAH - INSTALLER               ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

get_ip_address() {
    # Get the main IP address
    IP=$(hostname -I | awk '{print $1}')
    if [ -z "$IP" ]; then
        IP="localhost"
    fi
    echo "$IP"
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        OS=$(uname -s)
        VERSION=$(uname -r)
    fi
    echo "$OS"
}

is_raspberry_pi() {
    if [ -f /proc/device-tree/model ]; then
        if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
            return 0
        fi
    fi
    if grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
        return 0
    fi
    return 1
}

# ==========================================
# Pre-flight Checks
# ==========================================
print_banner

echo ""
print_info "Memulai instalasi aplikasi Bel Sekolah..."
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "Installer harus dijalankan dengan sudo"
    echo ""
    echo -e "${YELLOW}Cara pakai:${NC}"
    echo "  sudo ./install.sh"
    echo ""
    exit 1
fi

# Detect OS
OS=$(detect_os)
print_info "Sistem terdeteksi: $OS"

# Check if Raspberry Pi
if is_raspberry_pi; then
    print_info "✓ Raspberry Pi terdeteksi!"
    IS_RPI=true
else
    IS_RPI=false
fi

echo ""

# ==========================================
# Step 0: Configure Hostname (SKIPPED - tidak mengubah hostname)
# ==========================================
print_info "[0/7] Konfigurasi Hostname..."
print_info "Hostname tidak diubah - menggunakan hostname saat ini"

HOSTNAME_TO_SET=$(hostname)

echo ""

# ==========================================
# Step 1: Install System Dependencies
# ==========================================
print_info "[1/7] Menginstall system dependencies..."
echo ""

if command -v apt-get &> /dev/null; then
    # Debian/Ubuntu/Raspberry Pi OS
    print_info "Mengupdate package list..."
    apt-get update -qq
    
    print_info "Menginstall Python dan dependencies..."
    apt-get install -y -qq \
        python3 \
        python3-venv \
        python3-pip \
        python3-dev \
        mpg123 \
        alsa-utils \
        sqlite3 \
        avahi-daemon \
        libnss-mdns \
        qrencode
    
    # Set audio output for Raspberry Pi
    if [ "$IS_RPI" = true ]; then
        print_info "Mengkonfigurasi audio output Raspberry Pi..."
        if command -v raspi-config &> /dev/null; then
            raspi-config nonint do_audio 1 2>/dev/null || true
        fi
        amixer set 'PCM' 80% 2>/dev/null || true
    fi

elif command -v dnf &> /dev/null; then
    # Fedora
    dnf install -y \
        python3 \
        python3-virtualenv \
        python3-pip \
        mpg123 \
        alsa-utils \
        sqlite \
        avahi \
        nss-mdns \
        qrencode

elif command -v pacman &> /dev/null; then
    # Arch Linux
    pacman -Sy --noconfirm \
        python \
        python-virtualenv \
        python-pip \
        mpg123 \
        alsa-utils \
        sqlite \
        avahi \
        nss-mdns \
        qrencode

else
    print_warning "Package manager tidak dikenali, melewati install system dependencies"
    print_warning "Pastikan Python 3.8+ sudah terinstall"
fi

# Enable avahi-daemon for mDNS
if command -v systemctl &> /dev/null; then
    systemctl enable avahi-daemon 2>/dev/null || true
    systemctl start avahi-daemon 2>/dev/null || true
fi

print_success "System dependencies terinstall"
echo ""

# ==========================================
# Step 2: Check Python
# ==========================================
print_info "[2/7] Memeriksa Python..."

if ! command -v python3 &> /dev/null; then
    print_error "Python3 tidak ditemukan!"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_success "Python $PYTHON_VERSION ditemukan"
echo ""

# ==========================================
# Step 3: Create Virtual Environment
# ==========================================
print_info "[3/7] Setup virtual environment..."

if [ -d "venv" ]; then
    print_warning "Virtual environment sudah ada, menggunakan yang ada..."
else
    python3 -m venv venv
    print_success "Virtual environment dibuat"
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip -q
print_success "PIP diupgrade"
echo ""

# ==========================================
# Step 4: Install Python Dependencies
# ==========================================
print_info "[4/7] Menginstall Python packages..."

# Cek apakah ada folder libs/ (untuk offline install)
if [ -d "libs" ] && [ "$(ls -A libs/*.whl 2>/dev/null)" ]; then
    print_info "Menginstall dari folder lokal (libs/)..."
    pip install --no-index --find-links=./libs -r requirements.txt -q
else
    print_info "Menginstall dari PyPI (online)..."
    pip install -r requirements.txt -q
fi

print_success "Python packages terinstall"
echo ""

# ==========================================
# Step 5: Initialize Database
# ==========================================
print_info "[5/7] Setup database..."

python3 -c "
from database import init_db
from config import Config
print(f'  → Database: {Config.DB_PATH}')
init_db()
print('  ✓ Database siap')
"

print_success "Database initialized"
echo ""

# ==========================================
# Step 6: Setup Systemd Service
# ==========================================
print_info "[6/7] Setup auto-start service..."

# Get actual user (not root)
ACTUAL_USER=${SUDO_USER:-$USER}
if [ "$ACTUAL_USER" = "root" ] || [ -z "$ACTUAL_USER" ]; then
    ACTUAL_USER=$(logname 2>/dev/null || echo "pi")
fi

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Aplikasi Bel Sekolah - SDIT Harapan Umat Jember
After=network.target sound.target
Wants=network.target sound.target

[Service]
Type=simple
User=${ACTUAL_USER}
WorkingDirectory=${SCRIPT_DIR}
Environment="PATH=${SCRIPT_DIR}/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=${SCRIPT_DIR}/venv/bin/python ${SCRIPT_DIR}/run.py
Restart=always
RestartSec=10
StartLimitInterval=60s
StartLimitBurst=3

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=bel-sekolah

[Install]
WantedBy=multi-user.target
EOF

print_success "Service file dibuat"

# Reload systemd
systemctl daemon-reload
print_success "Systemd daemon reloaded"

# Enable service
systemctl enable "${SERVICE_NAME}"
print_success "Auto-start enabled"

# Start service
systemctl start "${SERVICE_NAME}"
sleep 2

# Check status
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    print_success "Service berjalan!"
else
    print_error "Service gagal start"
    echo ""
    print_info "Log error:"
    journalctl -u "${SERVICE_NAME}" -n 10 --no-pager
    exit 1
fi

echo ""

# ==========================================
# Step 7: Generate QR Code & Access Info
# ==========================================
print_info "[7/7] Membuat QR Code dan info akses..."
echo ""

IP_ADDRESS=$(get_ip_address)
PORT=$(python3 -c "from config import Config; print(Config.PORT)" 2>/dev/null || echo "5000")
HOSTNAME_URL="http://${HOSTNAME_TO_SET}.local:${PORT}"
IP_URL="http://${IP_ADDRESS}:${PORT}"

# Generate QR code PNG
if command -v qrencode &> /dev/null; then
    qrencode -o "access-qr.png" -s 10 -l H "${HOSTNAME_URL}"
    print_success "QR Code dibuat: access-qr.png"
    
    # Also generate terminal QR
    qrencode -t ANSIUTF8 -m 2 "${HOSTNAME_URL}" > qr-terminal.txt
fi

# Save access info
 cat > "access-info.txt" << EOF
========================================
AKSES APLIKASI BEL SEKOLAH
========================================

📱 URL Akses (dari HP):
   ${HOSTNAME_URL}

🔢 Alternatif (IP Address):
   ${IP_URL}

🔐 Login Credentials:
   Username: admin
   Password: admin123

📋 Command Management:
   Status:  sudo systemctl status ${SERVICE_NAME}
   Restart: sudo systemctl restart ${SERVICE_NAME}
   Stop:    sudo systemctl stop ${SERVICE_NAME}
   Logs:    sudo journalctl -u ${SERVICE_NAME} -f

📁 Lokasi File:
   Aplikasi: ${SCRIPT_DIR}
   Database: ${SCRIPT_DIR}/database.db
   Sounds:   ${SCRIPT_DIR}/sounds/

🖨️  QR Code:
   File: ${SCRIPT_DIR}/access-qr.png
   Print dan tempel di tempat strategis

========================================
Tanggal Install: $(date)
Hostname: ${HOSTNAME_TO_SET}
IP Address: ${IP_ADDRESS}
========================================
EOF

print_success "Info akses disimpan: access-info.txt"
echo ""

# ==========================================
# Installation Complete
# ==========================================
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                  ✅ INSTALLASI SELESAI!                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

echo -e "${CYAN}📱 Akses Aplikasi dari HP:${NC}"
echo ""
echo -e "  ${GREEN}URL Utama:${NC}   ${HOSTNAME_URL}"
echo -e "  ${YELLOW}Alternatif:${NC}  ${IP_URL}"
echo ""

if [ -f "access-qr.png" ]; then
    echo -e "${CYAN}📱 QR Code (scan dengan HP):${NC}"
    echo ""
    cat qr-terminal.txt
    echo ""
    echo -e "${YELLOW}💡 File QR Code: access-qr.png${NC}"
    echo -e "   Print dan tempel di Raspberry Pi/dinding"
    echo ""
fi

echo -e "${BLUE}🔐 Login Credentials:${NC}"
echo -e "  Username: ${YELLOW}admin${NC}"
echo -e "  Password: ${YELLOW}admin123${NC}"
echo ""

if [ "$IS_RPI" = true ]; then
    echo -e "${YELLOW}💡 Tips Raspberry Pi:${NC}"
    echo "  • Aplikasi akan otomatis jalan saat Raspberry Pi dinyalakan"
    echo "  • Jika tidak bisa akses hostname, gunakan IP address"
    echo "  • Colok speaker/earphone ke jack audio 3.5mm"
    echo ""
fi

echo -e "${BLUE}📝 Command Penting:${NC}"
echo "  cat access-info.txt     # Lihat info akses"
echo "  ./info.sh               # Cek status dan IP"
echo "  sudo systemctl status ${SERVICE_NAME}"
echo ""

# ==========================================
# Verification - Ensure Everything Works
# ==========================================
print_info "🔍 Verifikasi sistem..."
echo ""

# Check 1: Service is enabled
if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
    print_success "✓ Service enabled (auto-start ON)"
else
    print_warning "⚠ Service not enabled, enabling..."
    systemctl enable "${SERVICE_NAME}"
fi

# Check 2: Service is running
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    print_success "✓ Service running"
else
    print_error "✗ Service not running!"
    print_info "Mencoba restart service..."
    systemctl restart "${SERVICE_NAME}"
    sleep 3
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        print_success "✓ Service now running"
    else
        print_error "✗ Service masih tidak berjalan!"
        print_info "Check logs: sudo journalctl -u ${SERVICE_NAME} -n 20"
    fi
fi

# Check 3: Web server responding
print_info "Mengetes web server..."
sleep 2
if curl -s "http://localhost:${PORT}" > /dev/null 2>&1; then
    print_success "✓ Web server responding on port ${PORT}"
else
    print_warning "⚠ Web server belum siap (tunggu 10 detik...)"
    sleep 10
    if curl -s "http://localhost:${PORT}" > /dev/null 2>&1; then
        print_success "✓ Web server now responding"
    else
        print_warning "⚠ Web server belum responding (mungkin butuh waktu lebih)"
    fi
fi

# Check 4: Hostname resolution
print_info "Mengetes hostname..."
if ping -c 1 "${HOSTNAME_TO_SET}.local" > /dev/null 2>&1; then
    print_success "✓ Hostname ${HOSTNAME_TO_SET}.local reachable"
else
    print_warning "⚠ Hostname belum aktif (butuh beberapa menit pertama kali)"
fi

# Check 5: Audio system
print_info "🎵 Testing audio system..."
if command -v mpg123 &> /dev/null && command -v aplay &> /dev/null; then
    print_success "  ✓ Audio tools ready (mpg123 + aplay)"
else
    print_warning "  ⚠ mpg123 or aplay not found"
fi

echo ""
print_success "══════════════════════════════════════════════════════════════"
print_success "  VERIFIKASI SELESAI - Sistem siap digunakan!"
print_success "══════════════════════════════════════════════════════════════"
echo ""

# Final status report
echo -e "${CYAN}📊 Status Akhir:${NC}"
echo "  • Service: $(systemctl is-active ${SERVICE_NAME} 2>/dev/null || echo 'unknown')"
echo "  • Auto-start: $(systemctl is-enabled ${SERVICE_NAME} 2>/dev/null || echo 'unknown')"
echo "  • URL: ${HOSTNAME_URL}"
echo "  • IP: ${IP_ADDRESS}"
echo ""

echo -e "${GREEN}🎉 Selamat menggunakan aplikasi Bel Sekolah!${NC}"
echo ""
echo -e "${YELLOW}⚠️  Penting:${NC}"
echo "  1. Ganti password default di menu Pengaturan"
echo "  2. Print QR Code (access-qr.png) dan tempel di tempat strategis"
echo "  3. Raspberry Pi akan otomatis menjalankan aplikasi saat boot"
echo ""
