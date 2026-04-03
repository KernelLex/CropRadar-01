# CropRadar Flutter App — One-shot setup + APK build
# Run this AFTER installing Flutter + Android Studio (see instructions below)
#
# Usage:
#   cd D:\Z-work\CropRadar\CropRadar-01
#   .\cropradar_app\setup_and_build.ps1

$ErrorActionPreference = "Stop"
$ROOT = Split-Path $PSScriptRoot -Parent          # CropRadar-01\
$SRC  = "$ROOT\cropradar_app"                     # our source files
$DEST = "$ROOT\cropradar_app_build"               # new flutter scaffold

Write-Host "`n[1/6] Creating Flutter project scaffold..." -ForegroundColor Cyan
Set-Location $ROOT
flutter create $DEST --org com.cropradar --platforms android --project-name cropradar_app
if (-not $?) { throw "flutter create failed" }

Write-Host "`n[2/6] Copying source files..." -ForegroundColor Cyan
Copy-Item "$SRC\pubspec.yaml"   "$DEST\pubspec.yaml"   -Force
Copy-Item "$SRC\lib"            "$DEST\lib"             -Recurse -Force

Write-Host "`n[3/6] Patching AndroidManifest.xml..." -ForegroundColor Cyan
$manifest = "$DEST\android\app\src\main\AndroidManifest.xml"
$xml = Get-Content $manifest -Raw

$permissions = @"
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
    <uses-permission android:name="android.permission.CAMERA"/>
    <uses-permission android:name="android.permission.READ_MEDIA_IMAGES"/>
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32"/>

"@

# Insert permissions before <application tag
$xml = $xml -replace '(\s*)(<application)', "$permissions`$1`$2"
$xml | Set-Content $manifest -Encoding UTF8
Write-Host "  -> Permissions added." -ForegroundColor Green

Write-Host "`n[4/6] Setting minSdk to 21..." -ForegroundColor Cyan
# Newer Flutter uses Kotlin DSL (.gradle.kts); older uses .gradle
$gradle_kts = "$DEST\android\app\build.gradle.kts"
$gradle     = "$DEST\android\app\build.gradle"
if (Test-Path $gradle_kts) {
    $g = Get-Content $gradle_kts -Raw
    $g = $g -replace 'minSdk\s*=\s*flutter\.minSdkVersion', 'minSdk = 21'
    $g = $g -replace 'minSdk\s*=\s*\d+', 'minSdk = 21'
    $g | Set-Content $gradle_kts -Encoding UTF8
} elseif (Test-Path $gradle) {
    $g = Get-Content $gradle -Raw
    $g = $g -replace 'minSdkVersion\s+\d+', 'minSdkVersion 21'
    $g | Set-Content $gradle -Encoding UTF8
} else {
    Write-Warning "Could not find build.gradle — skipping minSdk patch."
}
Write-Host "  -> minSdk = 21" -ForegroundColor Green

Write-Host "`n[5/6] Installing packages (flutter pub get)..." -ForegroundColor Cyan
Set-Location $DEST
flutter pub get
if (-not $?) { throw "flutter pub get failed" }

Write-Host "`n[6/6] Building debug APK..." -ForegroundColor Cyan
flutter build apk --debug
if (-not $?) { throw "flutter build apk failed" }

$apk = "$DEST\build\app\outputs\flutter-apk\app-debug.apk"
Write-Host "`n========================================" -ForegroundColor Green
Write-Host " APK built successfully!" -ForegroundColor Green
Write-Host " Location: $apk" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Green
Write-Host "Transfer to your phone:" -ForegroundColor Cyan
Write-Host "  Option A: USB cable -> copy APK -> install"
Write-Host "  Option B: Run this to install directly via ADB:"
Write-Host "    adb install `"$apk`""
Write-Host ""
