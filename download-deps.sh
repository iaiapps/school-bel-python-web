#!/bin/bash

# Script untuk download dependencies secara lokal
# Usage: ./download-deps.sh
# Output: folder libs/ berisi semua package

echo "=========================================="
echo "Downloading dependencies to ./libs/"
echo "=========================================="

mkdir -p libs

# Download all packages from requirements.txt
pip download -r requirements.txt -d ./libs

echo ""
echo "=========================================="
echo "Download complete!"
echo "Total files in libs/:"
ls -1 libs/ | wc -l
echo "=========================================="
echo ""
echo "Copy folder 'libs/' bersama project ke Raspberry Pi"
echo "Untuk install offline: pip install --no-index --find-links=./libs -r requirements.txt"
