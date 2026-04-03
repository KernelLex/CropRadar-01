# CropRadar WhatsApp Bot — Setup Guide

This guide walks you through registering your SIM number with Meta's WhatsApp Business Cloud API
and connecting it to `whatsapp_bot.py`.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| A prepaid SIM with a WhatsApp-capable number | Dedicated number — **not already linked to a personal WhatsApp account** |
| Meta (Facebook) Developer account | Free — https://developers.facebook.com |
| Meta Business account | Free — https://business.facebook.com |
| Python ≥ 3.11 + pip | Already in use for Telegram bot |
| `flask>=3.0.0` installed | `pip install flask` or `pip install -r requirements.txt` |
| **ngrok** (for local testing) | https://ngrok.com/download — free tier is fine |

---

## Step 1 — Register Your Number with Meta

1. Go to https://developers.facebook.com and log in.
2. Click **My Apps → Create App → Business** type.
3. In the app dashboard, click **Add Product → WhatsApp → Set up**.
4. Under **WhatsApp → API Setup**:
   - You'll see a test number and your **Phone Number ID** — copy it.
   - Generate a **temporary access token** (valid 24h) — copy it.
5. To add your own prepaid SIM number:
   - Go to **WhatsApp → Phone Numbers → Add phone number**.
   - Enter your number, verify via OTP SMS.
   - Once verified, **copy the new Phone Number ID** (different from the test one).
6. For a **permanent access token** (needed in production):
   - Create a **System User** in Meta Business Manager → Settings → Users → System Users.
   - Assign the WhatsApp app and generate a permanent token.

---

## Step 2 — Configure `.env`

Copy `.env.example` to `.env` and fill in:

```env
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxx...        # from API Setup or System User
WHATSAPP_PHONE_NUMBER_ID=1234567890123     # your number's ID
WHATSAPP_VERIFY_TOKEN=cropradar_verify_secret   # any secret string you choose
WA_BOT_PORT=5000
CROPRADAR_API_URL=http://localhost:8000    # your FastAPI backend
```

---

## Step 3 — Run the Bot Locally

### 3a. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3b. Start the FastAPI backend (in a separate terminal)

```powershell
uvicorn api:app --reload
```

### 3c. Start the WhatsApp bot

```powershell
python whatsapp_bot.py
```

You should see:
```
INFO  🌾 CropRadar WhatsApp bot starting on port 5000…
```

### 3d. Expose with ngrok

```powershell
ngrok http 5000
```

Copy the HTTPS forwarding URL, e.g.:
`https://abc123.ngrok-free.app`

---

## Step 4 — Register the Webhook in Meta

1. In Meta App Dashboard → **WhatsApp → Configuration → Webhook**.
2. Click **Edit**:
   - **Callback URL**: `https://abc123.ngrok-free.app/whatsapp`
   - **Verify token**: same value as `WHATSAPP_VERIFY_TOKEN` in `.env`
3. Click **Verify and Save**.
   - Meta sends a GET to `/whatsapp` — the bot echoes the challenge → ✅ verified.
4. Under **Webhook Fields**, subscribe to **`messages`**.

---

## Step 5 — Test

Send a WhatsApp message from any phone to your registered number:

| You send | Bot replies |
|---|---|
| `hi` | Welcome + language prompt |
| `1` | English confirmed + location prompt |
| Share location (📎 → Location) | Outbreak check + photo prompt |
| `12.9716, 77.5946` | Same — typed coordinate fallback |
| Send a crop leaf photo | Diagnosis result |
| `restart` | Resets the session |
| `cancel` | Ends the session |

---

## Step 6 — Production Deployment

When you deploy to a server (e.g., a VPS, Railway, Render):

1. Set all env vars in the platform's secrets manager.
2. Run: `python whatsapp_bot.py` (or use `gunicorn whatsapp_bot:app -b 0.0.0.0:5000`).
3. Update the Meta webhook URL to your production domain.
4. Replace the temporary access token with the permanent **System User token**.

> **Note:** ngrok is only needed during local development. In production, your server's domain is the webhook URL directly.

---

## Conversation Flow

```
User sends "hi"
  ├─ Bot: Welcome message + "Reply 1 for English / 2 for ಕನ್ನಡ"
  │         [State: WAITING_LANGUAGE]
  │
  └─ User sends 1 or 2
       ├─ Bot: Language confirmed + location instructions
       │         [State: WAITING_LOCATION]
       │
       └─ User shares location (native) OR types "12.97, 77.59"
            ├─ Bot: Nearby outbreak check result
            │         [State: WAITING_PHOTO]
            │
            └─ User sends crop photo
                 └─ Bot: Diagnosis (disease, confidence, remedy, prevention)
                          → loops back (user can send more photos)
                          → or type "restart" to reset
```

---

## Files Added / Modified

| File | Change |
|---|---|
| `whatsapp_bot.py` | **New** — WhatsApp webhook server (Flask + Meta Cloud API) |
| `.env.example` | Added `WHATSAPP_*` variables |
| `requirements.txt` | Added `flask>=3.0.0` |
| `WHATSAPP_SETUP.md` | **New** — this guide |

---

## Future: Voice Messages

When you're ready to add audio communication:
- WhatsApp audio messages arrive as `.ogg` (Opus codec) via a media ID.
- The pipeline will be: download OGG → convert to WAV (pydub + ffmpeg) → Google Cloud STT → map to bot command.
- This requires a GCP project with the Speech-to-Text API enabled.
