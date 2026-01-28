Write-Host "Building TGA Analysis Tool..."
pyinstaller .\tga_tool.spec --noconfirm --clean
Write-Host "Build complete. Output in .\dist\TGA_Analysis_Tool"