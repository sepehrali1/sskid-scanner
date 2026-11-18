@echo off
rem SskidScriptScanner.bat — اجرای برنامه بدون باز شدن پنجرهٔ کنسول
rem اگر dist\SskidScriptScanner.exe ساخته شده باشد همان را اجرا می‌کند، وگرنه نسخهٔ پایتونی.
setlocal
cd /d "%~dp0"

if exist "dist\SskidScriptScanner.exe" (
    start "" "dist\SskidScriptScanner.exe"
    exit /b 0
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "sskid_scanner.py"
) else (
    python "sskid_scanner.py"
)
