# build_exe.ps1 - build the single-file Windows app for "Sskid Script Scanner"
# Output: dist\SskidScriptScanner.exe
#
# Run:  powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
#
# Needs: Python 3 with tkinter (default on Windows) and PyInstaller.
# If assets\ is missing it is generated from the default image.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host '[1/4] Checking requirements...' -ForegroundColor Cyan
python -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) { throw 'tkinter not found. Install Python with tkinter support.' }

python -m PyInstaller --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '    PyInstaller missing; installing...' -ForegroundColor Yellow
    python -m pip install --upgrade pyinstaller
}

Write-Host '[2/4] Checking assets...' -ForegroundColor Cyan
if (-not (Test-Path 'assets\splash.png')) {
    Write-Host '    assets missing; building from image...' -ForegroundColor Yellow
    $img = Join-Path $env:USERPROFILE 'Downloads\noFilter.webp'
    if (Test-Path $img) { python -X utf8 make_assets.py $img }
    else { throw 'assets\splash.png missing and no default image found.' }
}

Write-Host '[3/4] Cleaning previous build...' -ForegroundColor Cyan
Get-Process -Name 'SskidScriptScanner','LuaAudit' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 400
foreach ($d in @('build', 'dist')) { if (Test-Path $d) { Remove-Item $d -Recurse -Force } }
if (Test-Path 'SskidScriptScanner.spec') { Remove-Item 'SskidScriptScanner.spec' -Force }
if (Test-Path 'LuaAudit.spec') { Remove-Item 'LuaAudit.spec' -Force }

Write-Host '[4/4] Building exe...' -ForegroundColor Cyan
python -m PyInstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name SskidScriptScanner `
    --icon "assets\icon.ico" `
    --add-data "lua_audit.py;." `
    --add-data "assets;assets" `
    sskid_scanner.py

if (-not (Test-Path 'dist\SskidScriptScanner.exe')) { throw 'Build failed.' }

$size = [Math]::Round((Get-Item 'dist\SskidScriptScanner.exe').Length / 1MB, 1)
Write-Host ''
Write-Host ("Done.  dist\SskidScriptScanner.exe  ({0} MB)" -f $size) -ForegroundColor Green
Write-Host 'No Python needed at runtime - copy the exe anywhere.' -ForegroundColor Green
