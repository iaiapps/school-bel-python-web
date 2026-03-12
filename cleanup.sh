#!/bin/bash

# ==========================================
# Cleanup & Uninstall Script
# Usage: sudo ./cleanup.sh
# ==========================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SERVICE_NAME="bel-sekolah.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_banner() {
    echo -e "${CYAN}"
    echo "+==========================================================+"
    echo "|         CLEANUP & UNINSTALL - APLIKASI BEL SEKOLAH       |"
    echo "+==========================================================+"
    echo -e "${NC}"
}

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        print_error "Script harus dijalankan dengan sudo"
        echo ""
        echo -e "${YELLOW}Cara pakai:${NC}"
        echo "  sudo ./cleanup.sh"
        echo ""
        exit 1
    fi
}

# Show menu
show_menu() {
    echo ""
    echo -e "${BLUE}Pilih tindakan:${NC}"
    echo ""
    echo "  1) Reset"
    echo "     → Hapus venv saja"
    echo "     → Database, sounds, settings TIDAK dihapus"
    echo "     → Cocok untuk reinstall dependency saja"
    echo ""
    echo "  2) Uninstall (Hapus semua)"
    echo "     → Hapus service, venv, database, sounds, settings, logs"
    echo "     → File project & templates TIDAK dihapus"
    echo "     → Cocok untuk uninstall permanen"
    echo ""
    echo "  0) Batal"
    echo ""
}

# Stop service
stop_service() {
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        echo "→ Stopping service..."
        systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
    fi
}

# Disable service
disable_service() {
    if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
        echo "→ Disabling service..."
        systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
    fi
}

# Remove service file
remove_service() {
    if [ -f "/etc/systemd/system/${SERVICE_NAME}" ]; then
        echo "→ Removing service file..."
        rm -f "/etc/systemd/system/${SERVICE_NAME}"
        systemctl daemon-reload 2>/dev/null || true
    fi
}

# Option 1: Reset (hanya hapus venv)
do_reset() {
    echo ""
    print_warning "⚠️  RESET - Reinstall Dependency"
    echo ""
    echo -e "${YELLOW}Yang akan dihapus:${NC}"
    echo "  • Virtual environment (venv/)"
    echo ""
    echo -e "${GREEN}Yang TIDAK dihapus:${NC}"
    echo "  • Database (database.db)"
    echo "  • Sounds (sounds/)"
    echo "  • Settings & QR code files"
    echo "  • Logs"
    echo "  • Service systemd"
    echo "  • Templates & Source code"
    echo ""
    
    read -p "Lanjutkan reset? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "Dibatalkan."
        exit 0
    fi
    
    echo ""
    print_info "🔄 Memulai reset..."
    echo ""
    
    cd "$SCRIPT_DIR"
    
    # Remove venv
    if [ -d "venv" ]; then
        echo "→ Removing virtual environment..."
        rm -rf venv
    fi
    
    # Stop service (karena venv hilang)
    stop_service
    
    echo ""
    print_success "✅ Reset selesai!"
    echo ""
    print_info "Selanjutnya jalankan install ulang:"
    echo "  sudo ./install.sh"
    echo ""
}

# Option 2: Uninstall (hapus semua)
do_uninstall() {
    echo ""
    print_warning "⚠️  UNINSTALL - Hapus Aplikasi"
    echo ""
    echo -e "${RED}PERINGATAN: Semua data aplikasi akan dihapus!${NC}"
    echo ""
    echo -e "${YELLOW}Yang akan dihapus:${NC}"
    echo "  • Service systemd (bel-sekolah.service)"
    echo "  • Virtual environment (venv/)"
    echo "  • Database (database.db)"
    echo "  • Sounds (sounds/)"
    echo "  • Settings & QR code files"
    echo "  • Logs"
    echo ""
    echo -e "${GREEN}Yang TIDAK dihapus:${NC}"
    echo "  • templates/ - HTML templates"
    echo "  • *.py, *.sh - Source code"
    echo ""
    echo -e "${RED}Ini akan menghapus aplikasi dari sistem!${NC}"
    echo ""
    
    read -p "Apakah Anda yakin ingin uninstall? (y/N): " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "Dibatalkan."
        exit 0
    fi
    
    echo ""
    print_info "🗑️  Memulai uninstall..."
    echo ""
    
    cd "$SCRIPT_DIR"
    
    # Stop service
    stop_service
    disable_service
    remove_service
    
    # Remove venv
    if [ -d "venv" ]; then
        echo "→ Removing virtual environment..."
        rm -rf venv
    fi
    
    # Remove Python cache
    if [ -d "__pycache__" ]; then
        echo "→ Removing Python cache..."
        rm -rf __pycache__
    fi
    
    # Remove database
    if [ -f "database.db" ]; then
        echo "→ Removing database..."
        rm -f database.db
    fi
    
    # Remove WAL/SHM files
    rm -f database.db-shm database.db-wal
    
    # Remove sounds folder
    if [ -d "sounds" ]; then
        echo "→ Removing sounds..."
        rm -rf sounds
    fi
    
    # Remove settings files
    rm -f app_settings.json
    
    # Remove access files
    rm -f access-qr.png access-info.txt qr-terminal.txt
    
    # Remove logs
    if [ -d "logs" ]; then
        echo "→ Removing logs..."
        rm -rf logs
    fi
    
    echo ""
    print_success "✅ Uninstall selesai!"
    echo ""
    print_info "File yang tersisa (tidak dihapus):"
    echo "  • templates/ - File HTML"
    echo "  • *.py, *.sh - Source code"
    echo ""
    print_info "Untuk install ulang:"
    echo "  sudo ./install.sh"
    echo ""
}

# Main
print_banner
check_root
show_menu

read -p "Pilih opsi (0-2): " choice

case "$choice" in
    1)
        do_reset
        ;;
    2)
        do_uninstall
        ;;
    0|"")
        echo "Dibatalkan."
        exit 0
        ;;
    *)
        print_error "Opsi tidak valid"
        exit 1
        ;;
esac
