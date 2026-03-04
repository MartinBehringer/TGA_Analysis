#!/bin/bash
set -e

echo "Building TGA Analysis Tool (.app)..."
pyinstaller ./tga_tool.spec --noconfirm --clean --windowed
echo "Build complete. Output in ./dist/TGA_Analysis_Tool/TGA_Analysis_Tool.app"