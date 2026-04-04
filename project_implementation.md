# CropRadar — Complete Project Implementation Guide

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Flutter Mobile App](#4-flutter-mobile-app)
5. [FastAPI Backend](#5-fastapi-backend)
6. [AI Vision Pipeline](#6-ai-vision-pipeline)
7. [Telegram Bot](#7-telegram-bot)
8. [WhatsApp Bot (Twilio)](#8-whatsapp-bot-twilio)
9. [Multi-Channel Notifications (FCM + Telegram + WhatsApp)](#9-multi-channel-notifications)
10. [Predictive Risk Pipeline](#10-predictive-risk-pipeline)
11. [Proactive Scheduler](#11-proactive-scheduler)
12. [Crop Stage Intelligence](#12-crop-stage-intelligence)
13. [Database Layer](#13-database-layer)
14. [Admin Dashboard](#14-admin-dashboard)
15. [Starting the System](#15-starting-the-system)
16. [End-to-End User Flows](#16-end-to-end-user-flows)
17. [Q&A — Everything About the System](#17-qa--everything-about-the-system)

---

## 1. Project Overview

**CropRadar** is an AI-powered crop disease detection and outbreak alerting platform for farmers, built for the TFT Hackathon.

**Core problem:** Farmers cannot detect crop disease early enough to prevent spread across a region.

**Solution:** A farmer scans a crop leaf photo → Gemini Vision AI diagnoses the disease → the result is stored geographically → when 3+ farmers near each other report the same disease within 48 hours, ALL registered farmers in that area are automatically warned across WhatsApp, Telegram, and mobile push notifications.

**Key differentiators:**
- Works on WhatsApp (no app install needed for farmers)
- Bilingual: English + Kannada
- Proactive risk reports using weather + NDVI + disease history
- Crop stage-aware weekly advisories
- Zero recurring infra cost (SQLite, Open-Meteo free API)

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FARMER INTERFACES                        │
│                                                                 │
│  Flutter App (Android)   Telegram Bot      WhatsApp (Twilio)   │
│  firebase_messaging      python-telegram-  Flask webhook        │
│  flutter_map             bot v21+          Twilio REST API      │
└──────────┬───────────────────┬─────────────────────┬───────────┘
           │                   │                     │
           │  HTTP / REST       │  long-poll          │  cloudflared
           ▼                   ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (port 8000)                  │
│                    uvicorn + Python 3.11                        │
│                                                                 │
│  /analyze-image   /risk-report    /register-device             │
│  /nearby-alerts   /risk-nearby    /transcribe-audio            │
│  /reports         /crop-stage     /scheduler/*                 │
└──────────┬───────────────────────────────────────┬─────────────┘
           │                                       │
     ┌─────▼──────┐                    ┌───────────▼──────────┐
     │  SQLite DB  │                   │     AI Services      │
     │  cropradar  │                   │                      │
     │  .db        │                   │  Gemini Vision API   │
     │             │                   │  Google Open-Meteo   │
     │  9 tables   │                   │  Synthetic NDVI      │
     └─────────────┘                   └──────────────────────┘
           │
     ┌─────▼──────────────────────────────────────────────┐
     │                  notifier.py                       │
     │                                                    │
     │  Telegram Bot API  →  all nearby bot_users         │
     │  Twilio REST API   →  all nearby whatsapp_users    │
     │  Firebase FCM V1   →  all nearby app_devices       │
     └────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Mobile App | Flutter 3 + Dart | Cross-platform, fast UI |
| Push Notifications | Firebase FCM V1 | Free, reliable Android push |
| Backend | FastAPI + uvicorn | Async Python, auto-docs |
| AI Vision | Google Gemini Vision | Best accuracy for plant disease |
| Database | SQLite | Zero-setup, persistent, portable |
| Telegram Bot | python-telegram-bot v21 | Official, async |
| WhatsApp Bot | Flask + Twilio Sandbox | No WhatsApp Business approval needed |
| Weather Data | Open-Meteo API | Completely free, no API key |
| NDVI | Synthetic seasonal model | MVP — swap in real satellite later |
| Scheduler | APScheduler | In-process cron, no Redis needed |
| Admin UI | Streamlit | Fast to build, good data tables |
| Tunnel | cloudflared | Free HTTPS tunnel for webhooks |
| Deployment | PowerShell launcher | One-command start of all services |

---

## 4. Flutter Mobile App

### Location: `cropradar_app/` and `cropradar_app_build/`

The app has three tabs: **Map**, **Scan**, **Stats**.

### 4.1 Entry Point — `main.dart`

```
App Launch
  │
  ├── Firebase.initializeApp()      ← initialise Firebase
  ├── _setupFCM()
  │     ├── request notification permission
  │     ├── create Android notification channel
  │     ├── get FCM token
  │     ├── POST /register-device   ← tell backend our push address
  │     └── listen for foreground messages → show local notification
  │
  └── CropRadarApp (MaterialApp)
        └── MainShell (NavigationBar)
              ├── Tab 0: MapScreen
              ├── Tab 1: HomeScreen (Scan)
              └── Tab 2: HistoryScreen (Stats)
```

**Language toggle** — EN / ಕನ್ನಡ switch in AppBar; state held at root and passed as `lang` prop to all children.

### 4.2 Scan Flow — `home_screen.dart`

```
HomeScreen
  │
  ├── GPS location fetched via geolocator
  │     (with 15-second timeout, falls back gracefully)
  │
  ├── User taps "Camera Scan" or "Gallery Pick"
  │     └── image_picker returns File
  │
  └── ApiService.analyzeImage(image, lat, lon, lang)
        │   POST /analyze-image (multipart)
        │
        ├── On success → push DiagnosisScreen(result)
        └── On error   → show red error banner
```

**API Settings (gear icon):** Runtime URL dialog — user can change `baseUrl` without rebuilding the APK. Useful when switching between WiFi/hotspot/tunnel.

### 4.3 Diagnosis Screen — `diagnosis_screen.dart`

Displays:
- **Red outbreak banner** — if `outbreak_alert` is non-null in the response
- `DiagnosisCard` widget — disease name, confidence badge (High/Medium/Low), remedy, prevention
- "Scan Another" button

### 4.4 Map Screen — `map_screen.dart`

- **OpenStreetMap tiles** via `flutter_map`
- Dots for every disease report (coloured by disease type)
- **Outbreak zones**: when ≥3 same-disease reports exist within 50 km, draws:
  - Red 50 km circle (alert zone)
  - Orange 15 km circle (hotspot core)
- User location blue dot
- Outbreak alert banner in AppBar when active
- Disease colour legend at bottom

### 4.5 Stats Screen — `history_screen.dart`

- Loads all reports via `GET /reports`
- **Summary pills**: total reports | diseases with 3+ reports | unique disease types
- **Filter chips** — tap any disease to filter the list
- **Report cards**: photo thumbnail (from `/photos/{id}.jpg`), disease name, confidence badge, IST timestamp, GPS coordinates

### 4.6 Firebase FCM Integration

```dart
// Gets FCM token on launch and sends to backend:
ApiService.registerDevice(
  fcmToken: token,
  lang: 'en',
  lat: position.latitude,
  lon: position.longitude,
)
// This stores the token in app_devices table
// When an outbreak is detected near those coordinates,
// the backend sends a push notification to this device
```

**Background handler** (top-level function annotated with `@pragma('vm:entry-point')`) — handles notifications when app is killed.

---

## 5. FastAPI Backend

### Location: `api.py` | Port: 8000

### All Endpoints

| Method | Endpoint | Purpose |
|--------|---------|---------|
| GET | `/` | Health check |
| POST | `/analyze-image` | Upload crop photo → AI diagnosis |
| POST | `/report` | Manually add a disease report |
| GET | `/reports` | List all reports (for map/stats) |
| GET | `/alerts` | Global outbreak diseases |
| GET | `/nearby-alerts` | Outbreaks near a GPS point |
| POST | `/register-device` | Register FCM token |
| POST | `/transcribe-audio` | Speech-to-text for voice messages |
| GET | `/risk-nearby` | Structured risk JSON for a location |
| GET | `/risk-report` | Formatted risk text for bots |
| GET | `/crop-stage` | Growth stage for a crop |
| GET | `/crop-stage-report` | Formatted stage advisory |
| GET | `/supported-crops` | List of supported crop types |
| GET | `/scheduler/status` | Scheduler health |
| POST | `/scheduler/trigger-daily` | Manually fire daily alerts |
| POST | `/scheduler/trigger-weekly` | Manually fire weekly alerts |
| POST | `/scheduler/trigger-outbreak-scan` | Manually fire outbreak scan |
| GET | `/alerts-log` | History of proactive alerts sent |
| GET | `/docs` | Interactive Swagger UI |

### Outbreak Detection Logic

```python
OUTBREAK_THRESHOLD = 3   # reports
OUTBREAK_WINDOW_HRS = 48  # hours

# After every scan:
# 1. Check if same disease has 3+ reports within 50 km in 48 hours
# 2. If yes, check dedup: was a notification sent recently for this?
# 3. If no recent notification:
#    a. Query nearby Telegram users, WhatsApp users, app devices
#    b. Call notifier.broadcast_outbreak_alert() in background thread
#    c. Record the notification (dedup log)
```

### Photo Storage

Every crop scan is saved: `photos/{report_id}.jpg`
Served as static files: `GET /photos/42.jpg`
Used by the Stats screen to show photo thumbnails.

---

## 6. AI Vision Pipeline

### `vision_diagnosis.py` (called by `api.py`)

```
Input: crop leaf image (JPG/PNG)
         │
         ▼
Gemini Vision Pro (gemini-pro-vision)
   Prompt: "Analyse this crop leaf image. Identify:
            1. Disease name
            2. Confidence (High/Medium/Low)
            3. Remedy (step-by-step)
            4. Prevention advice
            Return JSON."
         │
         ▼
Output: { disease_name, confidence, remedy, prevention }
```

**Fallback:** If Gemini fails → tries GPT-4o Vision (if `OPENAI_API_KEY` set).

---

## 7. Telegram Bot

### Location: `bot.py`

### Conversation Flow

```
User sends /start
  │
  └── WAITING_LANGUAGE
        "Reply 1 for English, 2 for Kannada"
              │
              ▼
        WAITING_LOCATION
        "Share your location (GPS pin or coordinates)"
              │
              ├── Saves user to bot_users table
              ├── Fetches predictive risk report (/risk-report)
              ├── Checks nearby outbreaks (/nearby-alerts)
              └── WAITING_CROP
                    Inline keyboard: [Rice] [Wheat] [Tomato] ...
                          │
                          ├── Saves crop type to bot_users
                          └── WAITING_PHOTO
                                "Send a photo of your crop leaf"
                                      │
                                      └── POST /analyze-image
                                            → Sends diagnosis + remedy
                                            → Outbreak alert suffix if applicable
```

### Key Features
- `upsert_bot_user()` — stores chat_id, language, lat/lon, crop_type for proactive alerts
- Language preference persisted across sessions
- Bilingual strings (en/kn) for every message
- Handles `/cancel` to reset

---

## 8. WhatsApp Bot (Twilio)

### Location: `whatsapp_bot.py` | Port: 5001

### How Twilio WhatsApp Works

```
Phone WhatsApp
  │  sends "hi"
  │
  ▼
Twilio servers
  │  HTTP POST to webhook URL
  │
  ▼
cloudflared tunnel (HTTPS)
  │
  ▼
http://localhost:5001/whatsapp
  │
  ▼
Flask webhook handler
  │  returns empty TwiML instantly (< 1 second)
  │  (avoids Twilio's 15-second timeout)
  │
  └── Background thread sends reply via Twilio REST API
```

### Conversation Flow (same 4 states as Telegram)

```
"hi" / "hello" → Welcome + Language selection (1/2)
  │
  ▼
"1" (English) or "2" (Kannada) → ask for location
  │
  ▼
GPS pin OR typed "12.97, 77.59"
  ├── Saves to whatsapp_users table (for future outbreak broadcasts)
  ├── Sends predictive risk report
  ├── Sends nearby outbreak alert if any
  └── Ask crop type (numbered list)
        │
        ▼
      "3" (e.g. Tomato) → ask for photo
        │
        ▼
      Photo sent → downloads from Twilio → POSTs to /analyze-image
        → Sends diagnosis + remedy + outbreak suffix
```

### Why Empty TwiML + REST API?

Twilio has a 15-second timeout for webhook responses. Image analysis takes 20-40 seconds. Solution:
1. Return `<Response></Response>` (empty TwiML) instantly
2. Do the heavy work in a background thread
3. Send reply via Twilio REST API (POST to Messages.json) when done

### Sandbox Limitations
- 50 messages/day per account (upgrade to remove)
- Users must join with "join `<word>`" first
- Webhook URL must be updated in Twilio Console when tunnel URL changes

---

## 9. Multi-Channel Notifications

### Location: `notifier.py`

When outbreak threshold is crossed, ALL registered users near the location receive alerts simultaneously.

### Channel 1 — Telegram

```python
POST https://api.telegram.org/bot{TOKEN}/sendMessage
  { chat_id, text (Markdown), parse_mode: "Markdown" }
```
Uses `TELEGRAM_BOT_TOKEN` from `.env`.

### Channel 2 — WhatsApp (Twilio REST)

```python
POST https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json
  { From: "whatsapp:+14155238886", To: wa_number, Body: text }
Auth: Basic (ACCOUNT_SID, AUTH_TOKEN)
```
Strips Markdown `*` before sending (WhatsApp doesn't render it).

### Channel 3 — FCM V1 (Firebase Push)

FCM Legacy API was deprecated in 2024. CropRadar uses **FCM V1 API** with OAuth2 JWT authentication:

```
Step 1: Read firebase-adminsdk-account.json (service account)

Step 2: Build JWT manually
  Header:  { alg: RS256, typ: JWT }
  Claims:  { iss: client_email,
             scope: firebase.messaging,
             aud: oauth2.googleapis.com/token,
             iat: now, exp: now+3600 }

Step 3: Sign JWT with RS256 (using cryptography package)
  private_key = RSA key from service account JSON
  signature   = PKCS1v15(SHA256(header.payload))

Step 4: Exchange JWT for OAuth2 access token
  POST https://oauth2.googleapis.com/token
  { grant_type: jwt-bearer, assertion: jwt }

Step 5: Send FCM message
  POST https://fcm.googleapis.com/v1/projects/{project_id}/messages:send
  Authorization: Bearer {access_token}
  { message: { token: fcm_token, notification: {...}, android: {...} } }
```

Token is cached in memory for 55 minutes to avoid redundant OAuth2 calls.

### Alert Deduplication

Before broadcasting, checks:
```sql
SELECT 1 FROM outbreak_notifications
WHERE disease_type = ?
AND center_latitude BETWEEN ? AND ?
AND center_longitude BETWEEN ? AND ?
AND triggered_at > datetime('now', '-24 hours')
```
If found → skip (already notified today for this area).

### Bilingual Alert Templates

```python
ALERT_EN = "⚠️ CropRadar Outbreak Alert\n\n{disease} detected near your area.\n{count} reports within 50 km..."
ALERT_KN = "⚠️ ಕ್ರಾಪ್‌ರಾಡಾರ್ ರೋಗ ಹರಡುವಿಕೆ ಎಚ್ಚರಿಕೆ\n\n{disease} ರೋಗ ಪತ್ತೆಯಾಗಿದೆ..."
```
Language is looked up per user from the database.

---

## 10. Predictive Risk Pipeline

### Files: `weather_service.py`, `satellite_service.py`, `risk_features.py`, `risk_model.py`, `risk_report.py`

This pipeline warns farmers about disease risk **before** symptoms appear, using 3 signals:

### Signal 1 — Weather (Open-Meteo API)

```python
GET https://api.open-meteo.com/v1/forecast
  ?latitude=12.97&longitude=77.59
  &hourly=temperature_2m,relative_humidity_2m,...
  &past_days=7
```

Free API, no key needed. Fetches 7-day historical + current data.
Returns: temperature_mean, humidity_mean, precipitation_sum, wind_speed_mean, dew_point, cloud_cover.
Cached in `weather_snapshots` for 6 hours per ~1km grid cell.

### Signal 2 — NDVI (Vegetation Health)

Synthetic seasonal estimator (MVP):
```python
ndvi_base = 0.3 + 0.4 * sin(2π * day_of_year / 365)  # seasonal curve
ndvi_mean = ndvi_base - humidity_penalty - rain_penalty
```
Models crop stress from latitude, season, and weather. Designed to swap in real Sentinel Hub / NASA AppEEARS satellite data later.
Returns: ndvi_mean, ndvi_change_7d, stress_flag.

### Signal 3 — Disease History

```sql
SELECT disease_type, COUNT(*) as reports
FROM disease_reports
WHERE timestamp > datetime('now', '-7 days')
  AND haversine(lat, lon, latitude, longitude) < 50
GROUP BY disease_type
```

### Risk Scoring (0–100 points)

| Component | Max Points | Logic |
|-----------|-----------|-------|
| Humidity | 15 pts | >80% → max points |
| Temperature | 10 pts | 15-30°C optimal for pathogens |
| Precipitation | 10 pts | >10mm → high risk |
| Wind speed | 5 pts | Low wind → disease accumulates |
| NDVI stress | 20 pts | Declining NDVI → stressed crops |
| Low NDVI | 5 pts | NDVI < 0.3 → very weak crops |
| Disease history | 25 pts | Reports in last 7 days |
| Active outbreaks | 15 pts | Outbreak clusters nearby |

**Risk levels:** Low (0-39) | Medium (40-69) | High (70-100)

### Report Format (sent to farmers)

```
🔮 CropRadar Crop Risk Report
📍 Location: 12.97°, 77.59°

⚠️ Risk Level: HIGH (Score: 78/100)

🌱 Crops at Risk: Tomato, Potato, Rice
🦠 Possible Diseases: Late Blight, Leaf Spot

📊 Why this area is at risk:
• High humidity (85%) — optimal for fungal spread
• Temperature (24°C) in pathogen-optimal range
• 11 disease reports nearby in last 7 days

🛡️ Recommended Actions:
• Apply fungicide spray within 48 hours
• Inspect crops every 2 days
• Ensure good drainage
```

---

## 11. Proactive Scheduler

### Location: `scheduler.py` | Uses: APScheduler

The scheduler runs inside the FastAPI process (no separate service needed).

### Three Jobs

| Job | Schedule | What it does |
|-----|---------|-------------|
| Daily Risk Alert | Every day at 07:00 IST | Sends personalised risk report to ALL registered users based on their saved location |
| Weekly Crop Stage | Every Monday 08:00 IST | Sends crop growth stage advisory + disease risks for current stage |
| Outbreak Cluster Scan | Every 1 minute | Scans all recent reports for new outbreak clusters; broadcasts if threshold crossed |

### Daily Risk Alert Flow

```
For each user in (bot_users + whatsapp_users + app_devices):
  1. Check: was_alert_sent_today(user_key, "daily_risk") → skip if yes
  2. Build risk features for user's saved lat/lon
  3. Score risk → get risk_level, reasons, recommendations
  4. Format bilingual report text
  5. Send via appropriate channel (Telegram/WhatsApp/FCM)
  6. record_alert_sent(user_key, "daily_risk")
```

### Weekly Crop Stage Flow

```
For each user with a saved crop_type:
  1. Check: was_alert_sent_this_week(user_key, "weekly_stage") → skip if yes
  2. estimate_growth_stage(crop_type, registered_at)
  3. build_stage_report(language, stage_info)
  4. Send advisory with stage name, risks, actions
  5. record_alert_sent(user_key, "weekly_stage")
```

### Manual Triggers (Admin)

```bash
curl -X POST http://localhost:8000/scheduler/trigger-daily
curl -X POST http://localhost:8000/scheduler/trigger-weekly
curl -X POST http://localhost:8000/scheduler/trigger-outbreak-scan
```

---

## 12. Crop Stage Intelligence

### Location: `crop_stage.py`

Tracks where a crop is in its growth cycle and sends tailored advisories.

### Supported Crops

Rice, Wheat, Tomato, Potato, Maize, Cotton, Sorghum, Sugarcane, Chili, Mango

### Growth Stages Example (Tomato)

```
Day 0-15:    Seedling     → damp-off risk, avoid overwatering
Day 16-40:   Vegetative   → monitor for leaf curl, aphids
Day 41-65:   Flowering    → blossom drop, thrips alert
Day 66-90:   Fruiting     → late blight high risk, spray fungicide
Day 91-110:  Maturation   → harvest window, reduce irrigation
```

### Stage Estimation

```python
days_since_sowing = (today - registered_at).days
# Walk through CROP_STAGES[crop_type] to find current stage
# Returns: stage_name, day_in_stage, progress_pct, next_stage, disease_risks
```

---

## 13. Database Layer

### Location: `database.py` | File: `cropradar.db`

### 9 Tables

| Table | Purpose |
|-------|---------|
| `disease_reports` | Every crop scan result with GPS, photo path, timestamp |
| `bot_users` | Telegram users: chat_id, language, lat/lon, crop_type |
| `whatsapp_users` | WhatsApp users: wa_number, language, lat/lon, crop_type |
| `app_devices` | Flutter app FCM tokens with lat/lon |
| `outbreak_notifications` | Dedup log — prevents repeat alerts within 24h / 20km |
| `weather_snapshots` | Cached Open-Meteo weather per grid cell (6h TTL) |
| `ndvi_snapshots` | Cached NDVI values per grid cell (24h TTL) |
| `risk_scores` | Historical risk scores per grid cell |
| `daily_alerts_log` | Tracks which users got which alerts (dedup for scheduler) |

### Geo-Filtering (Haversine Distance)

```python
def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * asin(sqrt(a))
```

Used to find all users/devices within 50 km of an outbreak.

### Grid Cell System

```python
def lat_lon_to_grid_id(lat, lon, precision=2):
    # Rounds to ~1km cells for weather/NDVI caching
    return f"{round(lat, precision)}_{round(lon, precision)}"
```

### IST Timestamps

All display timestamps are converted to IST (UTC+5:30):
```python
IST = timezone(timedelta(hours=5, minutes=30))
def fmt_ist(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=IST).strftime("%Y-%m-%d %H:%M IST")
```

---

## 14. Admin Dashboard

### Location: `admin_dashboard.py` | Port: 8501

### Login

Default: `admin` / `cropradar123` (set via `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env`)

### 8 Pages

| Page | What you see |
|------|-------------|
| Overview | KPI cards (total reports, active users, outbreaks), time-series charts |
| Disease Reports | Filterable table + photo grid, delete individual records |
| Bot Users | Telegram user list, deactivate/delete |
| Outbreak Alerts | History of outbreak notifications sent, timeline chart |
| Proactive Alerts | Scheduler log — who was notified, when, which channel |
| Weather Cache | Cached weather snapshots, clear cache button |
| NDVI Snapshots | Cached NDVI values, clear cache button |
| Risk Scores | Historical risk scores per grid cell, expandable reasons |

---

## 15. Starting the System

### One Command

```powershell
cd D:\Z-work\CropRadar\CropRadar-01
.\start_all.ps1
```

### What it launches

| Window | Service | Command |
|--------|---------|---------|
| 1 | FastAPI backend | `uvicorn api:app --reload --host 0.0.0.0 --port 8000` |
| 2 | Telegram bot | `python bot.py` |
| 3 | WhatsApp bot | `python whatsapp_bot.py` |
| 4 | Admin dashboard | `streamlit run admin_dashboard.py --port 8501` |

### What the main window does

1. Starts two cloudflared tunnels:
   - `:8000` → HTTPS URL for the Flutter app
   - `:5001` → HTTPS URL for WhatsApp webhook
2. Prints both URLs clearly
3. You copy-paste them:
   - App URL → ⚙️ in the Flutter app
   - WhatsApp URL → Twilio Console → Sandbox Settings → "When a message comes in"

### Environment Variables (`.env`)

```env
GEMINI_API_KEY=your_key
TELEGRAM_BOT_TOKEN=your_token
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=your_token
ADMIN_USERNAME=admin
ADMIN_PASSWORD=cropradar123
CROPRADAR_API_URL=http://localhost:8000
WHATSAPP_PORT=5001
```

---

## 16. End-to-End User Flows

### Flow A — App User Scans a Crop

```
1. Opens app → GPS fetched automatically
2. FCM token registered with backend (POST /register-device)
3. Taps "Camera Scan" or "Gallery Pick"
4. Selects leaf photo
5. App POSTs to POST /analyze-image (multipart: file + lat + lon + lang)
6. Backend:
   a. Saves temp file
   b. Calls Gemini Vision → gets disease_name, confidence, remedy, prevention
   c. Inserts row into disease_reports
   d. Saves photo to photos/{report_id}.jpg
   e. Checks outbreak threshold → sets outbreak_alert string
   f. Starts background thread → _maybe_broadcast_outbreak()
7. App shows DiagnosisScreen:
   - Red banner if outbreak
   - Disease name + confidence badge
   - Remedy + Prevention text
8. Background thread:
   - Finds 3+ same-disease reports nearby in 48h? → YES
   - Dedup check → not notified yet
   - Queries nearby Telegram + WhatsApp + app_devices
   - Sends alerts to all of them
```

### Flow B — Telegram Bot User

```
1. /start → language choice (1/2)
2. Share location (GPS pin)
3. Bot saves user → gets risk report → checks outbreaks → shows crop keyboard
4. User picks crop type (e.g. Tomato)
5. User sends leaf photo
6. Bot downloads → POSTs to /analyze-image → sends diagnosis reply
```

### Flow C — WhatsApp User

```
1. Sends "join <word>" to +1 415 523 8886 to join sandbox
2. Sends "hi" → welcome + language selection
3. Sends "1" (English) → asks for location
4. Sends GPS pin OR "12.97, 77.59"
5. Bot replies with risk report + outbreak status + crop selection
6. Sends "3" for Tomato → asks for photo
7. Sends leaf photo → gets diagnosis in WhatsApp
```

### Flow D — Proactive Outbreak Alert

```
Trigger: 3rd farmer in the same area reports Leaf Blight

1. /analyze-image runs → inserts report #3
2. Background thread: get_nearby_outbreak_risk() → finds 3 Leaf Blight reports
3. was_outbreak_notified_recently() → no
4. get_nearby_users(lat, lon, 50km) → 5 Telegram users
5. get_nearby_whatsapp_users() → 2 WhatsApp users
6. get_nearby_app_devices() → 3 FCM tokens
7. record_outbreak_notification() → saves dedup record
8. broadcast_outbreak_alert():
   - Telegram: POST /bot{TOKEN}/sendMessage × 5
   - WhatsApp: POST Twilio Messages.json × 2
   - FCM: POST fcm.googleapis.com × 3
9. All 10 users get alerted within seconds
```

---

## 17. Q&A — Everything About the System

**Q: How does disease detection work?**
A: The user captures a leaf photo. It's sent to Google Gemini Vision Pro with a structured prompt asking for disease name, confidence level, remedy, and prevention. The response is parsed as JSON and stored in the database.

**Q: How is location used?**
A: GPS coordinates from the phone are attached to every scan. This lets the system cluster nearby reports of the same disease. When 3+ farmers within 50 km report the same disease within 48 hours, it's flagged as an outbreak.

**Q: Why WhatsApp instead of a dedicated app?**
A: Most farmers in rural India already have WhatsApp and don't want to install new apps. The Twilio sandbox lets us serve them immediately without Meta WhatsApp Business API approval.

**Q: How does the push notification work?**
A: When the Flutter app opens, it requests an FCM token from Firebase, then POSTs that token to `/register-device`. The backend stores it in `app_devices`. When an outbreak fires, the backend signs a JWT with the Firebase service account private key, exchanges it for an OAuth2 access token, then calls the FCM V1 API to send a push to each device token.

**Q: Why not use the Firebase Admin SDK?**
A: The `firebase-admin` package is heavy and has dependency conflicts. We implemented JWT RS256 signing manually using Python's `cryptography` package — just `requests` and `cryptography`, no extra SDK needed.

**Q: Why SQLite instead of PostgreSQL?**
A: For a hackathon/MVP, SQLite needs zero setup, runs in-process, and is fast enough for thousands of records. It can be swapped for PostgreSQL with a one-line connection string change in `database.py`.

**Q: What is the risk score based on?**
A: Three signals — weather favorability (humidity, temperature, rain — 35 pts), vegetation stress from NDVI (25 pts), and regional disease history (40 pts). Weather comes from Open-Meteo (free API). NDVI is synthetic for the MVP but designed to accept real Sentinel Hub data.

**Q: What is NDVI?**
A: Normalized Difference Vegetation Index — a 0–1 scale of plant health derived from satellite imagery. NDVI < 0.3 means stressed/dying vegetation. We estimate it synthetically using seasonal curves + weather data for the MVP.

**Q: How does the scheduler work without a separate process?**
A: APScheduler's `BackgroundScheduler` runs as a daemon thread inside the FastAPI/uvicorn process. It starts in the `@app.on_event("startup")` hook and stops in `shutdown`. No Redis, Celery, or separate worker process needed.

**Q: How is Twilio WhatsApp different from the Telegram bot?**
A: Telegram has a persistent long-polling connection; the bot constantly pulls updates. WhatsApp (via Twilio) uses webhooks — Twilio POSTs to our server when a message arrives. This requires a public HTTPS URL (cloudflared tunnel). Telegram needs no tunnel.

**Q: What happens if the tunnel URL changes?**
A: Every time `start_all.ps1` runs, a new cloudflared URL is generated. The script prints both URLs. You must update Twilio's sandbox webhook with the new URL. The Flutter app URL is updated via the ⚙️ Settings dialog — no rebuild needed.

**Q: How is bilingual support implemented?**
A: A `STRINGS` dictionary in each bot file holds English and Kannada versions of every message, keyed by `lang` (`"en"` or `"kn"`). The user's language preference is stored per-user in the database and used for all future messages including proactive alerts.

**Q: How does deduplication prevent spam?**
A: `outbreak_notifications` table records every broadcast (disease, lat, lon, timestamp). Before sending, `was_outbreak_notified_recently()` checks if an alert was sent within the last 24 hours within 20 km of the current outbreak. `daily_alerts_log` similarly prevents the same daily/weekly alert being sent twice.

**Q: Can this scale to production?**
A: The architecture is production-ready with these swaps:
- SQLite → PostgreSQL (change `DB_PATH` to a `postgresql://` connection string)
- cloudflared free tunnel → paid Cloudflare tunnel or ngrok paid plan (fixed URL)
- Twilio sandbox → registered WhatsApp Business number (removes 50/day limit)
- Single server → containerised (the codebase is stateless except the DB)

---

*Last updated: April 2026 | CropRadar v1.0 | TFT Hackathon*
