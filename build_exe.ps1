Write-Host "Building TGA Analysis Tool..."
$ErrorActionPreference = "Stop"
python -m PyInstaller .\tga_tool.spec --noconfirm --clean
Write-Host "Build complete. Output in .\dist\TGA_Analysis_Tool"