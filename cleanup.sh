#!/bin/bash

# ==========================================
# Cleanup Script - Bersihkan semua file installasi
# Usage: sudo ./cleanup.sh
# ==========================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVICE_NAME="bel-sekolah.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${YELLOW}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    🧹 CLEANUP SCRIPT                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}✗ Jalankan dengan sudo${NC}"
    echo "  sudo ./cleanup.sh"
    exit 1
fi

echo -e "${YELLOW}⚠️  Peringatan: Semua data berikut akan dihapus:${NC}"
echo ""
echo "  • Service (systemd)"
echo "  • Virtual environment (venv/)"
echo "  • Python cache (__pycache__/)"
echo "  • Database (database.db)"
echo "  • Settings (app_settings.json)"
echo "  • File akses (access-qr.png, access-info.txt)"
echo "  • Logs"
echo ""
echo -e "${RED}File sounds/ dan file project TIDAK dihapus.${NC}"
echo ""

read -p "Lanjutkan cleanup? (y/N): " confirm
if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo "Dibatalkan."
    exit 0
fi

echo ""
echo -e "${BLUE}🧹 Memulai cleanup...${NC}"
echo ""

# Stop service
if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
    echo "→ Stopping service..."
    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
fi

# Disable service
if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
    echo "→ Disabling service..."
    systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
fi

# Remove service file
if [ -f "/etc/systemd/system/${SERVICE_NAME}" ]; then
    echo "→ Removing service file..."
    rm -f "/etc/systemd/system/${SERVICE_NAME}"
    systemctl daemon-reload 2>/dev/null || true
fi

cd "$SCRIPT_DIR"

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
if [ -f "database.db-shm" ]; then
    rm -f database.db-shm
fi
if [ -f "database.db-wal" ]; then
    rm -f database.db-wal
fi

# Remove settings
if [ -f "app_settings.json" ]; then
    echo "→ Removing settings..."
    rm -f app_settings.json
fi

# Remove access files
if [ -f "access-qr.png" ]; then
    echo "→ Removing QR code..."
    rm -f access-qr.png
fi
if [ -f "access-info.txt" ]; then
    rm -f access-info.txt
fi
if [ -f "qr-terminal.txt" ]; then
    rm -f qr-terminal.txt
fi

# Remove logs
if [ -d "logs" ]; then
    echo "→ Removing logs..."
    rm -rf logs
fi

echo ""
echo -e "${GREEN}✅ Cleanup selesai!${NC}"
echo ""
echo -e "${GREEN}Sekarang jalankan ulang install:${NC}"
echo "  sudo ./install.sh"
echo ""
