# build_apk.ps1 -- local Android build helper (ASCII only, PowerShell 5.1 safe)
#
# Builds the single-file web app, stages it into the Android assets, generates
# launcher icons, then builds a debug APK with the Gradle wrapper.
#
# Requirements on this machine:
#   - JDK 17+            (java -version)
#   - Android SDK        (set ANDROID_HOME, or install Android Studio)
#   - Python 3 + Pillow  (pip install pillow)
#
# Output: android\app\build\outputs\apk\debug\app-debug.apk

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here        # ...\lua-audit

Write-Host '=== 1/4 build single-file web app ==='
Push-Location (Join-Path $root 'web')
python -X utf8 build_web.py
Pop-Location

Write-Host '=== 2/4 stage into Android assets ==='
$assets = Join-Path $here 'app\src\main\assets'
New-Item -ItemType Directory -Force -Path $assets | Out-Null
Copy-Item (Join-Path $root 'web\SskidScanner.html') $assets -Force

Write-Host '=== 3/4 generate launcher icons ==='
Push-Location $here
python -X utf8 make_icons.py
Pop-Location

Write-Host '=== 4/4 gradle assembleDebug ==='
if (-not $env:ANDROID_HOME -and -not $env:ANDROID_SDK_ROOT) {
    $guess = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
    if (Test-Path $guess) {
        $env:ANDROID_HOME = $guess
        Write-Host "ANDROID_HOME set to $guess"
    } else {
        Write-Warning 'ANDROID_HOME not set and no SDK found. Install the Android SDK first.'
    }
}
Push-Location $here
& (Join-Path $here 'gradlew.bat') --no-daemon assembleDebug
Pop-Location

$apk = Join-Path $here 'app\build\outputs\apk\debug\app-debug.apk'
if (Test-Path $apk) {
    $mb = [math]::Round((Get-Item $apk).Length / 1MB, 2)
    Write-Host ""
    Write-Host "OK  $apk  ($mb MB)"
} else {
    Write-Warning 'APK not found -- the build failed.'
    exit 1
}
