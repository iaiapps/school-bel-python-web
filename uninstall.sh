#!/bin/bash

# ==========================================
# Uninstall Script - Hapus aplikasi dan service
# Usage: sudo ./uninstall.sh
# ==========================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVICE_NAME="bel-sekolah.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${RED}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              ⚠️  UNINSTALL APLIKASI BEL SEKOLAH              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}✗ Jalankan dengan sudo${NC}"
    echo "  sudo ./uninstall.sh"
    exit 1
fi

echo -e "${YELLOW}Peringatan: Semua file aplikasi akan dihapus.${NC}"
echo ""

read -p "Lanjutkan uninstall? (y/N): " confirm
if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo "Dibatalkan."
    exit 0
fi

echo ""
echo -e "${BLUE}🗑️  Menghapus aplikasi...${NC}"
echo ""

# Stop service
if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
    echo "→ Stopping service..."
    systemctl stop "${SERVICE_NAME}"
fi

# Disable service
if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
    echo "→ Disabling service..."
    systemctl disable "${SERVICE_NAME}"
fi

# Remove service file
if [ -f "/etc/systemd/system/${SERVICE_NAME}" ]; then
    echo "→ Removing service file..."
    rm "/etc/systemd/system/${SERVICE_NAME}"
    systemctl daemon-reload
fi

cd "$SCRIPT_DIR"

# Remove venv
if [ -d "venv" ]; then
    echo "→ Removing virtual environment..."
    rm -rf venv
fi

# Remove cache
if [ -d "__pycache__" ]; then
    echo "→ Removing Python cache..."
    rm -rf __pycache__
fi

# Remove database
if [ -f "database.db" ]; then
    echo "→ Removing database..."
    rm -f database.db
fi

# Remove all app generated files
rm -f database.db-shm database.db-wal
rm -f app_settings.json
rm -f access-qr.png access-info.txt qr-terminal.txt

echo ""
echo -e "${GREEN}✅ Uninstall selesai!${NC}"
echo ""
echo -e "${YELLOW}File yang tersisa (tidak dihapus):${NC}"
echo "  • sounds/ - File audio bel"
echo "  • templates/ - File HTML"
echo "  • Semua file .py, .sh"
echo ""
echo -e "${BLUE}Untuk install ulang:${NC}"
echo "  sudo ./install.sh"
echo ""
