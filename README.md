# 🌾 CropRadar

> **Proactive crop intelligence for farmers — powered by AI Vision, predictive risk analysis, automated alerts, and real-time outbreak mapping.**

CropRadar is an agricultural intelligence platform where farmers interact through **Telegram**, **WhatsApp**, or a **mobile app** to receive crop disease diagnosis, treatment guidance, outbreak alerts, and proactive daily risk advisories. The system runs a **background scheduler** that automatically monitors weather, vegetation health, and disease patterns — sending farmers personalized alerts *before* problems become visible. Every diagnosis is geo-tagged to power a regional outbreak intelligence network.

---

## 🚨 Problem

Farmers often detect crop diseases too late — by the time visible symptoms appear, significant yield loss has already occurred. Most smallholder farmers lack quick access to agronomists or plant pathologists, and traditional advisory systems are too slow and inaccessible for rural communities. A single outbreak can devastate an entire village's crops if neighboring farmers aren't warned in time.

---

## 💡 Solution

CropRadar puts disease intelligence directly in a farmer's hands through messaging interfaces they already use — **Telegram** and **WhatsApp**. A farmer simply:

1. Opens the bot and selects their language (English or ಕನ್ನಡ)
2. Shares their GPS location
3. **Selects their crop type** (Rice, Wheat, Tomato, Potato, Maize, Cotton, Sorghum, Sugarcane, Chili, Mango)
4. **Receives a predictive Crop Risk Report** before even sending a photo
5. Sends a photo of an affected crop leaf for AI-powered diagnosis

After onboarding, the system works **proactively** — sending:
- ⚡ **Daily risk alerts** (7 AM) when weather conditions create disease risk
- 🌱 **Weekly crop stage advisories** (Mondays) with growth-stage-specific guidance
- 🚨 **Outbreak broadcasts** when disease clusters are detected nearby

All alerts are bilingual, deduplicated, and delivered across **Telegram, WhatsApp, and Android push notifications**.

---

## ✅ Features

### Core Features
- 📸 **Crop image diagnosis** using Google Gemini Vision API
- 💊 **Remedy & prevention recommendations** tailored to the detected disease
- ⚠️ **Outbreak detection & alerts** — triggered when ≥ 3 nearby reports match the same disease, proactively broadcasting a bilingual warning to all nearby farmers
- 🗺️ **Regional outbreak map** — interactive Streamlit + Folium dashboard with clustered markers
- 🌐 **Bilingual interface** — full English and Kannada (ಕನ್ನಡ) support, including AI responses in Kannada
- 📍 **GPS-linked reports** — every diagnosis is geo-tagged via native location sharing
- 💬 **Multi-channel interface** — Telegram, WhatsApp (Twilio), and Android app (Flutter + FCM)

### 🔮 Predictive Risk Analysis
- 🌦️ **Live weather integration** — real-time weather data via [Open-Meteo](https://open-meteo.com/) (free, no API key required), including temperature, humidity, precipitation, wind speed, and 7-day history
- 🌱 **Vegetation health signals** — NDVI-based vegetation stress estimation using seasonal and weather-derived models
- 📊 **Area-level risk scoring** — rule-based engine combining weather favorability, vegetation stress, and nearby disease history into a 0–100 risk score
- 🔮 **Crop Risk Reports** — bilingual preventive warning messages sent to farmers *before* visible symptoms, clearly distinct from outbreak alerts
- 🦠 **Disease-weather correlation** — built-in knowledge of which diseases thrive under which weather conditions (Late Blight ← cool+wet, Powdery Mildew ← warm+dry, etc.)
- ⚡ **Smart caching** — weather and NDVI results cached per ~1km grid cell to avoid redundant API calls

### 🤖 Proactive Intelligence (NEW)
- ⏰ **Automated scheduler** — APScheduler runs inside the FastAPI backend with 3 jobs:
  - **Daily risk alerts** (7:00 AM IST) — weather + NDVI risk analysis for all registered users
  - **Weekly crop stage** (Monday 8:00 AM IST) — growth-stage-specific advisories
  - **Outbreak cluster scan** (every minute) — detects disease clusters and broadcasts alerts
- 🌱 **Crop growth stage tracking** — 10 crop calendars (Rice, Wheat, Tomato, Potato, Maize, Cotton, Sorghum, Sugarcane, Chili, Mango) with stage-specific risk advisories
- 🔔 **Multi-channel push** — proactive alerts sent via Telegram, WhatsApp (Twilio), and Android (Firebase FCM)
- 🔕 **Alert deduplication** — daily/weekly dedup prevents notification spam
- 📬 **Admin monitoring** — dedicated dashboard page for tracking all proactive alerts

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend API | Python · FastAPI · Uvicorn |
| Bot Interfaces | Telegram Bot API · WhatsApp (Twilio) · Android (Flutter + FCM) |
| AI Vision | Google Gemini Vision (gemini-2.5-flash) |
| Weather Data | Open-Meteo API (free, no key required) |
| Risk Scoring | Rule-based weighted engine (weather + NDVI + disease context) |
| Crop Stage | Calendar-based growth stage estimator (10 crops) |
| Scheduler | APScheduler (in-process background jobs) |
| Database | SQLite (8 tables including alert log) |
| Push Notifications | Firebase Cloud Messaging V1 API |
| Outbreak Map | Streamlit · Folium · streamlit-folium |
| Geo-detection | Haversine distance formula |

---

## 🚀 How to Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your API keys
Copy `.env.example` to `.env` and fill in:
```
GEMINI_API_KEY=your_gemini_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
CROPRADAR_API_URL=http://localhost:8000
```

> Get Gemini key free at [aistudio.google.com](https://aistudio.google.com) · Get bot token from [@BotFather](https://t.me/BotFather)
>
> **No weather API key needed** — Open-Meteo is free and keyless.

### 3. Quick start (Windows — all services at once)
```powershell
.\start_all.ps1
```

### 3b. Manual start (separate terminals)

**Terminal 1 — FastAPI backend + Scheduler**
```bash
python -m uvicorn api:app --reload --port 8000
```
> The proactive scheduler starts automatically with the backend.

**Terminal 2 — Telegram bot**
```bash
python bot.py
```

**Terminal 3 — WhatsApp bot**
```bash
python whatsapp_bot.py
```

**Terminal 4 — Admin dashboard**
```bash
python -m streamlit run admin_dashboard.py --server.port 8501
```

- API docs → http://localhost:8000/docs
- Admin dashboard → http://localhost:8501
- Scheduler status → http://localhost:8000/scheduler/status

---

## 🤖 Proactive Alert System

### How It Works

The scheduler runs 3 background jobs inside the FastAPI process:

| Job | Schedule | What It Does |
|-----|----------|--------------|
| Daily Risk | 7:00 AM IST | Fetches weather + NDVI → scores risk → alerts users if ≥ Medium |
| Weekly Stage | Monday 8:00 AM IST | Estimates crop growth stage → sends stage-specific advisory |
| Outbreak Scan | Every minute | Scans reports for clusters (3+ same disease in 50 km) → broadcasts |

### Crop Growth Stages

The system tracks 10 crops through their full lifecycle:

| Crop | Stages |
|------|--------|
| Rice | Seedling → Tillering → Booting → Flowering → Grain Filling → Maturity |
| Wheat | Seedling → Tillering → Jointing → Heading → Grain Filling → Maturity |
| Tomato | Seedling → Vegetative → Flowering → Fruiting → Maturity |
| Maize | Emergence → Vegetative → Tasseling → Silking → Grain Fill → Maturity |
| Cotton | Seedling → Vegetative → Square Formation → Flowering → Boll Dev → Maturity |
| ... | + Potato, Sorghum, Sugarcane, Chili, Mango |

Each stage has bilingual risk advisories (English + Kannada) specific to that growth phase.

### Admin Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/scheduler/status` | GET | Check scheduler health, jobs, last run times |
| `/scheduler/trigger-daily` | POST | Manually trigger daily risk job |
| `/scheduler/trigger-weekly` | POST | Manually trigger weekly stage job |
| `/scheduler/trigger-outbreak-scan` | POST | Manually trigger outbreak scan |
| `/crop-stage` | GET | Get crop growth stage info |
| `/supported-crops` | GET | List supported crop types |
| `/alerts-log` | GET | View proactive alert history |

---

## 🔮 How Predictive Risk Analysis Works

When a user shares their location, the bot runs a 3-signal risk pipeline **before** the existing outbreak check:

### Signal Sources

| Signal | Source | Weight |
|--------|--------|--------|
| Weather | Open-Meteo API (current + 7-day history) | 0–35 pts |
| Vegetation health | Seasonal NDVI estimation + weather modulation | 0–25 pts |
| Disease context | Nearby disease reports from the database | 0–40 pts |

### Risk Levels

| Score | Level | Bot Response |
|-------|-------|-------------|
| 0–30 | 🟢 Low | Basic monitoring advice |
| 31–60 | 🟡 Medium | Preparation and increased vigilance |
| 61–100 | 🔴 High | Immediate preventive action recommended |

### Bot Message Flow

```
1. User sends /start
2. 🌐 Language selection (English / ಕನ್ನಡ)
3. 📍 Location sharing
4. 📊 Predictive Crop Risk Report (weather-based early warning)
5. ⚠️ Outbreak Alert (if confirmed nearby outbreaks exist)
   OR ✅ "No active outbreaks detected"
6. 🌱 Crop type selection (Rice, Wheat, Tomato, etc.)
7. 📸 Photo diagnosis (send crop leaf photo)

After onboarding, automated alerts arrive daily/weekly.
```

---

## 🔭 Future Improvements

- 🤖 **Local LLM / multimodal model** — Replace external vision APIs with a locally hosted model (e.g., LLaVA, MedSAM) trained on agricultural datasets to eliminate API costs and latency, and enable fully offline operation in rural areas.
- 🌱 **Specialized plant disease model** — Train a dedicated plant disease detection model on [PlantVillage](https://plantvillage.psu.edu/) and similar datasets for higher accuracy on common Indian crops.
- 🔊 **Multilingual voice responses** — Add audio output in regional languages (Kannada, Hindi, Telugu, Tamil) for farmers with low literacy, using text-to-speech synthesis.
- 🛰️ **Real satellite NDVI** — Integrate NASA AppEEARS or Sentinel Hub for actual satellite-derived vegetation indices instead of the current seasonal estimator.
- 🔍 **Pesticide authenticity detection** — Use OCR and packaging image analysis to verify pesticide labels and warn farmers about counterfeit or expired products.
- 🗺️ **Scalable geospatial intelligence** — Build a production-grade outbreak intelligence system with PostGIS, clustering algorithms, and dashboards for agricultural agencies and government bodies.

---

## 📁 Project Structure

```
CropRadar-01/
├── api.py                  FastAPI backend (diagnosis, alerts, risk, scheduler endpoints)
├── bot.py                  Telegram bot (bilingual, crop profiling)
├── whatsapp_bot.py         WhatsApp bot (Twilio sandbox, crop profiling)
├── database.py             SQLite layer (8 tables, geo helpers, alert dedup)
├── notifier.py             Multi-channel alert broadcaster (TG, WA, FCM)
├── vision_diagnosis.py     Gemini Vision integration with language-aware prompts
├── audio_transcription.py  Voice message transcription
├── admin_dashboard.py      Streamlit admin panel (8 pages incl. proactive alerts)
│
├── weather_service.py      Open-Meteo weather data integration
├── satellite_service.py    NDVI / vegetation health estimation
├── risk_features.py        Feature engineering (weather + NDVI + disease)
├── risk_model.py           Rule-based risk scoring engine
├── risk_report.py          Bilingual risk report formatter
│
├── crop_stage.py           🆕 Crop growth stage estimator (10 crops)
├── scheduler.py            🆕 APScheduler (daily/weekly/outbreak jobs)
│
├── cropradar_app/          Flutter Android app
│   ├── lib/main.dart
│   ├── lib/screens/        Home, diagnosis, history, map screens
│   ├── lib/services/       API and location services
│   └── pubspec.yaml
│
├── start_all.ps1           Windows quick-start script (all services)
├── requirements.txt        Python dependencies
├── .env.example            API key template
└── firebase-adminsdk-*.json  FCM service account (not committed)
```

---

*Built as a hackathon MVP — designed to be extended into a production-grade agricultural intelligence platform.*
