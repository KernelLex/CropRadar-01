# 🌾 CropRadar

> **Messaging-first crop intelligence for farmers — powered by AI Vision, predictive risk analysis, and real-time outbreak mapping.**

CropRadar is a prototype where farmers send crop or pesticide photos through a Telegram bot to receive disease diagnosis, treatment guidance, outbreak alerts, and preventive recommendations. The system also provides **predictive crop disease risk reports** based on live weather data, vegetation health signals, and regional disease history — warning farmers *before* visible symptoms appear. Reports are logged to generate a regional outbreak map that helps nearby farmers take early action.

---

## 🚨 Problem

Farmers often detect crop diseases too late — by the time visible symptoms appear, significant yield loss has already occurred. Most smallholder farmers lack quick access to agronomists or plant pathologists, and traditional advisory systems are too slow and inaccessible for rural communities. A single outbreak can devastate an entire village's crops if neighboring farmers aren't warned in time.

---

## 💡 Solution

CropRadar puts disease intelligence directly in a farmer's hands through a messaging interface they already use — Telegram. A farmer simply:

1. Opens the bot and selects their language (English or ಕನ್ನಡ)
2. Shares their GPS location
3. **Receives a predictive Crop Risk Report** before even sending a photo
4. Sends a photo of an affected crop leaf for AI-powered diagnosis

The bot instantly returns an AI-powered diagnosis with a remedy and prevention tips — all in the farmer's chosen language. Every report is stored and geo-tagged, contributing to a regional outbreak intelligence network. If 3 or more reports of the same disease appear within 50 km, nearby farmers are proactively warned.

---

## ✅ Features

### Core Features
- 📸 **Crop image diagnosis** using Google Gemini Vision API
- 💊 **Remedy & prevention recommendations** tailored to the detected disease
- ⚠️ **Outbreak detection & alerts** — triggered when ≥ 3 nearby reports match the same disease, proactively broadcasting a bilingual warning to nearby farmers via Telegram
- 🗺️ **Regional outbreak map** — interactive Streamlit + Folium dashboard with clustered markers
- 🌐 **Bilingual interface** — full English and Kannada (ಕನ್ನಡ) support, including AI responses in Kannada
- 📍 **GPS-linked reports** — every diagnosis is geo-tagged via native Telegram location sharing
- 💬 **Messaging-based interface** — no app install, no literacy barrier

### 🔮 Predictive Risk Analysis (NEW)
- 🌦️ **Live weather integration** — real-time weather data via [Open-Meteo](https://open-meteo.com/) (free, no API key required), including temperature, humidity, precipitation, wind speed, and 7-day history
- 🌱 **Vegetation health signals** — NDVI-based vegetation stress estimation using seasonal and weather-derived models
- 📊 **Area-level risk scoring** — rule-based engine combining weather favorability, vegetation stress, and nearby disease history into a 0–100 risk score
- 🔮 **Crop Risk Reports** — bilingual preventive warning messages sent to farmers *before* visible symptoms, clearly distinct from outbreak alerts
- 🦠 **Disease-weather correlation** — built-in knowledge of which diseases thrive under which weather conditions (Late Blight ← cool+wet, Powdery Mildew ← warm+dry, etc.)
- ⚡ **Smart caching** — weather and NDVI results cached per ~1km grid cell to avoid redundant API calls

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend API | Python · FastAPI · Uvicorn |
| Bot Interface | Telegram Bot API · python-telegram-bot |
| AI Vision | Google Gemini Vision (gemini-2.5-flash) |
| Weather Data | Open-Meteo API (free, no key required) |
| Risk Scoring | Rule-based weighted engine (weather + NDVI + disease context) |
| Database | SQLite (6 tables) |
| Outbreak Map | Streamlit · Folium · streamlit-folium |
| Geo-detection | Haversine distance formula |

---

## 🚀 How to Run the Prototype

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your API keys
Copy `.env.example` to `.env` and fill in:
```
GEMINI_API_KEY=your_gemini_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
CROPRADAR_API_URL=http://localhost:8000
```

> Get Gemini key free at [aistudio.google.com](https://aistudio.google.com) · Get bot token from [@BotFather](https://t.me/BotFather)
>
> **No weather API key needed** — Open-Meteo is free and keyless.

### 3. Run all three services (separate terminals)

**Terminal 1 — FastAPI backend**
```bash
python -m uvicorn api:app --reload --port 8000
```

**Terminal 2 — Telegram bot**
```bash
python bot.py
```

**Terminal 3 — Outbreak map dashboard**
```bash
python -m streamlit run map_dashboard.py
```

- API docs → http://localhost:8000/docs
- Dashboard → http://localhost:8501

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
1. User sends location
2. 📊 "Analysing crop risk for your area…"
3. 🔮 Crop Risk Report (preventive early warning)
4. ⚠️ Outbreak Alert (if confirmed nearby outbreaks exist)
   OR ✅ "No active outbreaks detected"
5. 📸 "Send me a photo of your crop leaf…"
```

The risk report (🔮) and outbreak alert (⚠️) are distinct:
- **Risk report** = predictive early warning based on weather, vegetation, and regional data
- **Outbreak alert** = confirmed nearby outbreak based on report threshold

---

## 🔭 Future Improvements

- 🤖 **Local LLM / multimodal model** — Replace external vision APIs with a locally hosted model (e.g., LLaVA, MedSAM) trained on agricultural datasets to eliminate API costs and latency, and enable fully offline operation in rural areas.
- 🌱 **Specialized plant disease model** — Train a dedicated plant disease detection model on [PlantVillage](https://plantvillage.psu.edu/) and similar datasets for higher accuracy on common Indian crops.
- 🔊 **Multilingual voice responses** — Add audio output in regional languages (Kannada, Hindi, Telugu, Tamil) for farmers with low literacy, using text-to-speech synthesis.
- 📱 **WhatsApp-native interface** — Deploy via WhatsApp Business API for real-world adoption, since WhatsApp has near-universal penetration in rural India.
- 🛰️ **Real satellite NDVI** — Integrate NASA AppEEARS or Sentinel Hub for actual satellite-derived vegetation indices instead of the current seasonal estimator.
- 🔍 **Pesticide authenticity detection** — Use OCR and packaging image analysis to verify pesticide labels and warn farmers about counterfeit or expired products.
- 🗺️ **Scalable geospatial intelligence** — Build a production-grade outbreak intelligence system with PostGIS, clustering algorithms, and dashboards for agricultural agencies and government bodies.

---

## 📁 Project Structure

```
cropradar/
├── api.py                FastAPI backend (diagnosis, alerts, risk endpoints)
├── bot.py                Telegram bot (bilingual ConversationHandler)
├── database.py           SQLite layer (6 tables, geo helpers, risk caching)
├── notifier.py           Proactive bilingual Telegram alert broadcaster
├── vision_diagnosis.py   Gemini Vision integration with language-aware prompts
├── map_dashboard.py      Streamlit + Folium outbreak map dashboard
│
├── weather_service.py    🆕 Open-Meteo weather data integration
├── satellite_service.py  🆕 NDVI / vegetation health estimation
├── risk_features.py      🆕 Feature engineering (weather + NDVI + disease)
├── risk_model.py         🆕 Rule-based risk scoring engine
├── risk_report.py        🆕 Bilingual Telegram risk report formatter
│
├── test_outbreak_broadcast.py   Tests for outbreak broadcast feature
├── test_risk_pipeline.py        🆕 Tests for predictive risk pipeline
├── requirements.txt             Python dependencies
└── .env.example                 API key template
```

---

*Built as a hackathon MVP — designed to be extended into a production-grade agricultural intelligence platform.*
