# CropRadar Flutter App — Setup Guide

Backup frontend that talks directly to the existing FastAPI backend —
no WhatsApp / Meta account required.

---

## Step 1 — Install Flutter (Windows)

```powershell
# Download Flutter SDK from https://docs.flutter.dev/get-started/install/windows
# Unzip to C:\flutter, then add to PATH:
$env:PATH += ";C:\flutter\bin"

# Verify
flutter --version
flutter doctor   # check for any missing dependencies
```

Install Android Studio → Tools → SDK Manager → install:
- Android SDK Platform 33+
- Android SDK Build-Tools
- Android Emulator

---

## Step 2 — Create the Flutter project scaffold

```powershell
cd D:\Z-work\CropRadar\CropRadar-01

# Create the Android/iOS scaffold (one-time)
flutter create cropradar_app --org com.cropradar --platforms android

cd cropradar_app
```

The `lib/` files in this folder (already written) replace the default ones.
Copy them into the newly created project:

```powershell
# From CropRadar-01 root — if you cloned from this branch they're already there
# Otherwise copy cropradar_app/lib/ → the new project's lib/
# And copy pubspec.yaml as well
```

---

## Step 3 — Add Android permissions

Open `android/app/src/main/AndroidManifest.xml` and add these lines
**inside the `<manifest>` tag, before `<application>`**:

```xml
<!-- Internet access for FastAPI backend -->
<uses-permission android:name="android.permission.INTERNET"/>

<!-- GPS location -->
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>

<!-- Camera -->
<uses-permission android:name="android.permission.CAMERA"/>

<!-- Photo gallery (Android 13+) -->
<uses-permission android:name="android.permission.READ_MEDIA_IMAGES"/>
<!-- Photo gallery (Android 12 and below) -->
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"
    android:maxSdkVersion="32"/>
```

---

## Step 4 — Set minimum SDK version

Open `android/app/build.gradle` and set:

```gradle
android {
    defaultConfig {
        minSdkVersion 21    // ← change from 16 to 21 (required by geolocator)
        targetSdkVersion 34
    }
}
```

---

## Step 5 — Install packages and run

```powershell
flutter pub get

# Run on a connected Android device or emulator:
flutter run
```

---

## Step 6 — Connect to FastAPI backend

The app defaults to `http://10.0.2.2:8000` (Android emulator → host machine).

| Scenario | URL to use |
|---|---|
| Android Emulator | `http://10.0.2.2:8000` (default) |
| Physical phone, same WiFi | `http://192.168.x.x:8000` (your machine's local IP) |
| Deployed server | `https://your-domain.com` |

**Change it at runtime:** tap the ⚙️ settings icon in the app → paste your URL → Save.

Make sure FastAPI is running first:
```powershell
cd D:\Z-work\CropRadar\CropRadar-01
python -m uvicorn api:app --host 0.0.0.0 --reload --port 8000
```

---

## App Structure

```
cropradar_app/
├── pubspec.yaml                  # dependencies
└── lib/
    ├── main.dart                 # entry point, Material 3 green theme, lang state
    ├── screens/
    │   ├── home_screen.dart      # camera/gallery buttons, location, outbreak banners
    │   ├── diagnosis_screen.dart # AI result display + outbreak alert
    │   └── history_screen.dart   # past reports from /reports endpoint
    ├── services/
    │   ├── api_service.dart      # HTTP client (analyze-image, nearby-alerts, reports)
    │   └── location_service.dart # GPS permission + position
    └── widgets/
        ├── diagnosis_card.dart   # reusable diagnosis result card
        └── outbreak_banner.dart  # red alert banner
```

---

## Same pipeline as backend

```
Flutter app
  📸 image_picker → File
  📍 geolocator   → lat/lon
           │
           ▼
  POST /analyze-image  (same FastAPI endpoint as Telegram/WhatsApp bots)
           │
           ▼
  Gemini Vision → SQLite → outbreak check
           │
           ▼
  DiagnosisScreen (disease, confidence, remedy, prevention, outbreak alert)
```

The **entire Python backend is unchanged** — Flutter is just a new frontend.
