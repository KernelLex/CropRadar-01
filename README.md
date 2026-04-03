# 🌾 CropRadar

> **Messaging-first crop intelligence for farmers — powered by AI Vision, FastAPI, and real-time outbreak mapping.**

CropRadar is a prototype where farmers send crop or pesticide photos through a Telegram bot to receive disease diagnosis, treatment guidance, outbreak alerts, and preventive recommendations. Reports are logged to generate a regional outbreak map that helps nearby farmers take early action against crop diseases.

---

## 🚨 Problem

Farmers often detect crop diseases too late — by the time visible symptoms appear, significant yield loss has already occurred. Most smallholder farmers lack quick access to agronomists or plant pathologists, and traditional advisory systems are too slow and inaccessible for rural communities. A single outbreak can devastate an entire village's crops if neighboring farmers aren't warned in time.

---

## 💡 Solution

CropRadar puts disease intelligence directly in a farmer's hands through a messaging interface they already use — Telegram. A farmer simply:

1. Opens the bot and selects their language (English or ಕನ್ನಡ)
2. Shares their GPS location
3. Sends a photo of an affected crop leaf

The bot instantly returns an AI-powered diagnosis with a remedy and prevention tips — all in the farmer's chosen language. Every report is stored and geo-tagged, contributing to a regional outbreak intelligence network. If 3 or more reports of the same disease appear within 50 km, nearby farmers are proactively warned *before* they even ask.

---

## ✅ Prototype Features

- 📸 **Crop image diagnosis** using Google Gemini Vision API
- 💊 **Remedy & prevention recommendations** tailored to the detected disease
- ⚠️ **Outbreak detection & Alerts** — triggered when ≥ 3 nearby reports match the same disease, proactively broadcasting a bilingual warning to nearby farmers via Telegram.
- 🗺️ **Regional outbreak map** — interactive Streamlit + Folium dashboard with clustered markers
- 🌐 **Bilingual interface** — full English and Kannada (ಕನ್ನಡ) support, including AI responses in Kannada
- 📍 **GPS-linked reports** — every diagnosis is geo-tagged via native Telegram location sharing
- 💬 **Messaging-based interface** — no app install, no literacy barrier

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python · FastAPI · Uvicorn |
| Bot Interface | Telegram Bot API · python-telegram-bot |
| AI Vision | Google Gemini Vision (gemini-2.5-flash) |
| Database | SQLite |
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

### 3. Run all three services (separate terminals)

**Terminal 1 — FastAPI backend**
```bash
# Windows
$env:GEMINI_API_KEY="your_key"; $env:TELEGRAM_BOT_TOKEN="your_token"
python -m uvicorn api:app --reload --port 8000
```

**Terminal 2 — Telegram bot**
```bash
$env:GEMINI_API_KEY="your_key"; $env:TELEGRAM_BOT_TOKEN="your_token"
python bot.py
```

**Terminal 3 — Outbreak map dashboard**
```bash
python -m streamlit run map_dashboard.py
```

- API docs → http://localhost:8000/docs
- Dashboard → http://localhost:8501

---

## 🔭 Future Improvements

- 🤖 **Local LLM / multimodal model** — Replace external vision APIs with a locally hosted model (e.g., LLaVA, MedSAM) trained on agricultural datasets to eliminate API costs and latency, and enable fully offline operation in rural areas.
- 🌱 **Specialized plant disease model** — Train a dedicated plant disease detection model on [PlantVillage](https://plantvillage.psu.edu/) and similar datasets for higher accuracy on common Indian crops.
- 🔊 **Multilingual voice responses** — Add audio output in regional languages (Kannada, Hindi, Telugu, Tamil) for farmers with low literacy, using text-to-speech synthesis.
- 📱 **WhatsApp-native interface** — Deploy via WhatsApp Business API for real-world adoption, since WhatsApp has near-universal penetration in rural India.
- 🌦️ **Weather & satellite integration** — Incorporate weather API data and satellite imagery (NDVI) to build predictive models for disease spread before symptoms appear.
- 🔍 **Pesticide authenticity detection** — Use OCR and packaging image analysis to verify pesticide labels and warn farmers about counterfeit or expired products.
- 🗺️ **Scalable geospatial intelligence** — Build a production-grade outbreak intelligence system with PostGIS, clustering algorithms, and dashboards for agricultural agencies and government bodies.

---

## 📁 Project Structure

```
cropradar/
├── api.py               FastAPI backend (analyze-image, alerts, reports)
├── bot.py               Telegram bot (bilingual ConversationHandler)
├── database.py          SQLite + Haversine geo-outbreak detection
├── notifier.py          Proactive bilingual Telegram alert broadcaster
├── vision_diagnosis.py  Gemini Vision integration with language-aware prompts
├── map_dashboard.py     Streamlit + Folium outbreak map dashboard
├── requirements.txt     Python dependencies
└── .env.example         API key template
```

---

*Built as a hackathon MVP — designed to be extended into a production-grade agricultural intelligence platform.*
