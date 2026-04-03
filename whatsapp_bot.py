"""
whatsapp_bot.py - CropRadar WhatsApp Bot (Meta Cloud API)

Conversation flow (mirrors Telegram bot exactly):
  User sends "hi" / "start" / any first message
    └─► Language choice (reply 1 = English / 2 = ಕನ್ನಡ)  [WAITING_LANGUAGE]
         └─► Ask for location                               [WAITING_LOCATION]
              └─► Check nearby outbreaks
                   └─► Ask for crop photo                   [WAITING_PHOTO]
                        └─► Diagnose → reply → loop back for next photo

Location input (two paths):
  • Native WhatsApp location share  (📎 → Location)
  • Typed coordinates fallback       e.g. "12.9716, 77.5946"

Run with:
  python whatsapp_bot.py

Expose via ngrok (until deployed):
  ngrok http 5000
  → set https://<id>.ngrok.io/whatsapp as the webhook in Meta App Dashboard
"""

from dotenv import load_dotenv
load_dotenv()

import logging
import os
import re
import tempfile
from pathlib import Path

import requests
from flask import Flask, request, jsonify

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WA_TOKEN        = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WA_PHONE_ID     = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WA_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "cropradar_verify_secret")
API_BASE_URL    = os.environ.get("CROPRADAR_API_URL", "http://localhost:8000")

GRAPH_VERSION   = "v19.0"
GRAPH_API_URL   = f"https://graph.facebook.com/{GRAPH_VERSION}/{WA_PHONE_ID}/messages"
GRAPH_MEDIA_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Session state  (in-memory dict, keyed by WhatsApp "from" number)
# ---------------------------------------------------------------------------

WAITING_LANGUAGE = 0
WAITING_LOCATION = 1
WAITING_PHOTO    = 2

# { "919876543210": {"state": int, "lang": str, "lat": float|None, "lon": float|None} }
sessions: dict[str, dict] = {}


def get_session(phone: str) -> dict:
    if phone not in sessions:
        sessions[phone] = {
            "state": WAITING_LANGUAGE,
            "lang":  "en",
            "lat":   None,
            "lon":   None,
        }
    return sessions[phone]


# ---------------------------------------------------------------------------
# Bilingual string table  (same strings as bot.py / Telegram bot)
# ---------------------------------------------------------------------------

STRINGS = {
    "en": {
        "welcome": (
            "🌾 *Welcome to CropRadar!*\n\n"
            "I detect crop diseases from photos and alert you to outbreaks nearby.\n\n"
            "Please choose your language:\n"
            "1️⃣  English\n"
            "2️⃣  ಕನ್ನಡ\n\n"
            "_Reply with *1* or *2*_"
        ),
        "lang_set": "✅ Language set to *English*. Let's get started!\n\n",
        "ask_location": (
            "📍 *Step 1 — Share Your Location*\n\n"
            "Please share your location so I can check for disease outbreaks "
            "in your area before we analyse your crop.\n\n"
            "📌 *Option A:* Tap the 📎 clip → *Location* to share live GPS\n"
            "📌 *Option B:* Type your coordinates, e.g.:\n"
            "`12.9716, 77.5946`"
        ),
        "location_received": (
            "✅ Location received — *{lat:.4f}°, {lon:.4f}°*\n\n"
            "🔍 Checking for disease outbreaks in your area…"
        ),
        "outbreak_header": (
            "⚠️ *Outbreak Risk Alert!*\n\n"
            "The following diseases have been reported near you recently:\n"
        ),
        "outbreak_row":    "🦠 *{disease}* — {count} reports within 50 km",
        "outbreak_footer": (
            "\n\n🛡️ Apply preventive treatment and monitor your crops closely.\n\n"
            "📸 *Step 2:* Now send me a photo of your crop leaf and I'll analyse it."
        ),
        "no_outbreak": (
            "✅ *No active outbreaks detected near you.*\n\n"
            "📸 *Step 2:* Send me a photo of your crop leaf and I'll diagnose it!"
        ),
        "analysing":        "🔍 Analysing your crop image, please wait…",
        "diagnosis_header": "🌿 *CropRadar Diagnosis*",
        "disease_label":    "🦠 *Disease:*",
        "confidence_label": "*Confidence:*",
        "remedy_label":     "💊 *Remedy:*",
        "prevention_label": "🛡️ *Prevention:*",
        "report_stored":    "📋 _Report #{id} stored{loc}_",
        "next_photo": (
            "\n📸 Send another photo to analyse more crops, "
            "or type *restart* to reset."
        ),
        "conn_error": (
            "❌ Could not connect to the CropRadar backend.\n"
            "Make sure the API is running at: {url}"
        ),
        "analysis_error":   "❌ Analysis failed: {err}",
        "nudge_location": (
            "⚠️ I need your *location* first.\n\n"
            "Tap 📎 → *Location* to share, or type coordinates:\n"
            "e.g. `12.9716, 77.5946`"
        ),
        "nudge_photo":    "📸 Please send a *photo* of a crop leaf to get a diagnosis.",
        "nudge_language": "Please reply with *1* for English or *2* for ಕನ್ನಡ:",
        "session_ended":  "Session ended. Send *hi* or *start* to begin again.",
        "transcribing":   "🎙️ Transcribing audio...",
        "audio_retry":    "Sorry, I couldn't understand the audio. Let's try again.",
        "audio_fallback": "Sorry, I am having trouble understanding the audio. Please use text-based messages for now.",
    },
    "kn": {
        "welcome": (
            "🌾 *ಕ್ರಾಪ್‌ರಾಡಾರ್‌ಗೆ ಸ್ವಾಗತ!*\n\n"
            "ನಾನು ಫೋಟೋಗಳಿಂದ ಬೆಳೆ ರೋಗಗಳನ್ನು ಪತ್ತೆ ಮಾಡುತ್ತೇನೆ ಮತ್ತು ನಿಮ್ಮ ಸುತ್ತಲಿನ "
            "ರೋಗ ಹರಡುವಿಕೆ ಬಗ್ಗೆ ಎಚ್ಚರಿಸುತ್ತೇನೆ.\n\n"
            "ಭಾಷೆ ಆರಿಸಿ:\n"
            "1️⃣  English\n"
            "2️⃣  ಕನ್ನಡ\n\n"
            "_*1* ಅಥವಾ *2* ಎಂದು ಉತ್ತರಿಸಿ_"
        ),
        "lang_set": "✅ ಭಾಷೆಯನ್ನು *ಕನ್ನಡ*ಕ್ಕೆ ಹೊಂದಿಸಲಾಗಿದೆ. ಪ್ರಾರಂಭಿಸೋಣ!\n\n",
        "ask_location": (
            "📍 *ಹಂತ 1 — ನಿಮ್ಮ ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ*\n\n"
            "ನಿಮ್ಮ ಬಳಿ ರೋಗ ಹರಡುವಿಕೆ ಇದೆಯೇ ಎಂದು ಪರಿಶೀಲಿಸಲು ದಯವಿಟ್ಟು "
            "ನಿಮ್ಮ ಸ್ಥಳವನ್ನು ಹಂಚಿಕೊಳ್ಳಿ.\n\n"
            "📌 *ಆಯ್ಕೆ A:* 📎 → *Location* ಟ್ಯಾಪ್ ಮಾಡಿ\n"
            "📌 *ಆಯ್ಕೆ B:* ನಿರ್ದೇಶಾಂಕ ಟೈಪ್ ಮಾಡಿ, ಉದಾ.:\n"
            "`12.9716, 77.5946`"
        ),
        "location_received": (
            "✅ ಸ್ಥಳ ಸ್ವೀಕರಿಸಲಾಗಿದೆ — *{lat:.4f}°, {lon:.4f}°*\n\n"
            "🔍 ನಿಮ್ಮ ಪ್ರದೇಶದಲ್ಲಿ ರೋಗ ಹರಡುವಿಕೆ ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ…"
        ),
        "outbreak_header": (
            "⚠️ *ರೋಗ ಹರಡುವಿಕೆ ಎಚ್ಚರಿಕೆ!*\n\n"
            "ಇತ್ತೀಚೆಗೆ ನಿಮ್ಮ ಬಳಿ ಈ ರೋಗಗಳು ವರದಿಯಾಗಿವೆ:\n"
        ),
        "outbreak_row":    "🦠 *{disease}* — 50 ಕಿ.ಮೀ ಒಳಗೆ {count} ವರದಿಗಳು",
        "outbreak_footer": (
            "\n\n🛡️ ತಡೆಗಟ್ಟುವ ಚಿಕಿತ್ಸೆ ಅನ್ವಯಿಸಿ ಮತ್ತು ನಿಮ್ಮ ಬೆಳೆಗಳನ್ನು ಗಮನಿಸಿ.\n\n"
            "📸 *ಹಂತ 2:* ಈಗ ನಿಮ್ಮ ಬೆಳೆ ಎಲೆಯ ಫೋಟೋ ಕಳುಹಿಸಿ."
        ),
        "no_outbreak": (
            "✅ *ನಿಮ್ಮ ಬಳಿ ಯಾವುದೇ ರೋಗ ಹರಡುವಿಕೆ ಕಂಡುಬಂದಿಲ್ಲ.*\n\n"
            "📸 *ಹಂತ 2:* ರೋಗ ಪತ್ತೆಗಾಗಿ ನಿಮ್ಮ ಬೆಳೆ ಎಲೆಯ ಫೋಟೋ ಕಳುಹಿಸಿ!"
        ),
        "analysing":        "🔍 ನಿಮ್ಮ ಬೆಳೆಯ ಚಿತ್ರ ವಿಶ್ಲೇಷಿಸಲಾಗುತ್ತಿದೆ, ದಯವಿಟ್ಟು ನಿರೀಕ್ಷಿಸಿ…",
        "diagnosis_header": "🌿 *ಕ್ರಾಪ್‌ರಾಡಾರ್ ರೋಗ ನಿರ್ಣಯ*",
        "disease_label":    "🦠 *ರೋಗ:*",
        "confidence_label": "*ವಿಶ್ವಾಸ:*",
        "remedy_label":     "💊 *ಪರಿಹಾರ:*",
        "prevention_label": "🛡️ *ತಡೆಗಟ್ಟುವಿಕೆ:*",
        "report_stored":    "📋 _ವರದಿ #{id} ಸಂಗ್ರಹಿಸಲಾಗಿದೆ{loc}_",
        "next_photo": (
            "\n📸 ಇನ್ನೊಂದು ಫೋಟೋ ಕಳುಹಿಸಿ ಅಥವಾ *restart* ಎಂದು ಟೈಪ್ ಮಾಡಿ."
        ),
        "conn_error": (
            "❌ CropRadar ಬ್ಯಾಕೆಂಡ್‌ಗೆ ಸಂಪರ್ಕಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ.\n"
            "{url} ನಲ್ಲಿ API ಚಾಲನೆಯಲ್ಲಿದೆಯೇ ಎಂದು ಖಚಿತಪಡಿಸಿ."
        ),
        "analysis_error":   "❌ ವಿಶ್ಲೇಷಣೆ ವಿಫಲವಾಗಿದೆ: {err}",
        "nudge_location": (
            "⚠️ ಮೊದಲು ನಿಮ್ಮ *ಸ್ಥಳ* ಬೇಕು.\n\n"
            "📎 → *Location* ಟ್ಯಾಪ್ ಮಾಡಿ, ಅಥವಾ ನಿರ್ದೇಶಾಂಕ ಟೈಪ್ ಮಾಡಿ:\n"
            "ಉದಾ. `12.9716, 77.5946`"
        ),
        "nudge_photo":    "📸 ರೋಗ ನಿರ್ಣಯ ಪಡೆಯಲು ಬೆಳೆ ಎಲೆಯ *ಫೋಟೋ* ಕಳುಹಿಸಿ.",
        "nudge_language": "*1* ಇಂಗ್ಲಿಷ್‌ಗಾಗಿ ಅಥವಾ *2* ಕನ್ನಡಕ್ಕಾಗಿ ಉತ್ತರಿಸಿ:",
        "session_ended":  "ಸೆಷನ್ ಮುಕ್ತಾಯವಾಗಿದೆ. ಮತ್ತೆ ಪ್ರಾರಂಭಿಸಲು *hi* ಕಳುಹಿಸಿ.",
        "transcribing":   "🎙️ ಆಡಿಯೊವನ್ನು ಅರ್ಥೈಸಲಾಗುತ್ತಿದೆ...",
        "audio_retry":    "ಕ್ಷಮಿಸಿ, ಆಡಿಯೊ ಅರ್ಥವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        "audio_fallback": "ಕ್ಷಮಿಸಿ, ಆಡಿಯೊವನ್ನು ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಈಗ ಪಠ್ಯ ಸಂದೇಶಗಳನ್ನು ಬಳಸಿ.",
    },
}


def s(session: dict, key: str) -> str:
    """Return a string for the session's chosen language (defaults to English)."""
    return STRINGS[session.get("lang", "en")][key]


# ---------------------------------------------------------------------------
# Meta Graph API helpers
# ---------------------------------------------------------------------------

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type":  "application/json",
    }


def send_text(to: str, body: str) -> None:
    """Send a plain text WhatsApp message."""
    payload = {
        "messaging_product": "whatsapp",
        "to":   to,
        "type": "text",
        "text": {"body": body, "preview_url": False},
    }
    r = requests.post(GRAPH_API_URL, json=payload, headers=_headers(), timeout=15)
    if not r.ok:
        logger.error("send_text failed [%s]: %s", r.status_code, r.text[:300])


def download_media(media_id: str) -> bytes:
    """
    Fetch a media file via the WhatsApp Cloud API.
    Step 1: GET /<media_id>  →  get the temporary URL
    Step 2: GET <url>        →  download the bytes
    """
    info_resp = requests.get(
        f"{GRAPH_MEDIA_URL}/{media_id}",
        headers=_headers(),
        timeout=15,
    )
    info_resp.raise_for_status()
    url = info_resp.json().get("url")
    if not url:
        raise ValueError(f"No URL in media response for id={media_id}: {info_resp.text}")

    dl_resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {WA_TOKEN}"},
        timeout=45,
    )
    dl_resp.raise_for_status()
    return dl_resp.content


# ---------------------------------------------------------------------------
# Location: typed-coordinate fallback
# ---------------------------------------------------------------------------

# Matches "12.9716, 77.5946"  or  "12.9716 77.5946"  or  "-33.87, 151.21"
_COORD_RE = re.compile(
    r"(-?\d{1,3}(?:\.\d+)?)\s*[,\s]\s*(-?\d{1,3}(?:\.\d+)?)"
)


def parse_typed_location(text: str) -> tuple[float, float] | None:
    """Return (lat, lon) if the text contains a valid coordinate pair, else None."""
    m = _COORD_RE.search(text.strip())
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            return lat, lon
    return None


# ---------------------------------------------------------------------------
# Outbreak check (calls same API endpoint as Telegram bot)
# ---------------------------------------------------------------------------

def _check_nearby_outbreaks(lat: float, lon: float) -> list[dict]:
    try:
        r = requests.get(
            f"{API_BASE_URL}/nearby-alerts",
            params={"lat": lat, "lon": lon, "radius_km": 50},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("outbreaks", [])
    except Exception as exc:
        logger.warning("Could not fetch nearby alerts: %s", exc)
        return []


# ---------------------------------------------------------------------------
# State handlers
# ---------------------------------------------------------------------------

def _handle_start(phone: str, session: dict) -> None:
    """Reset session and send welcome / language-selection message."""
    session.update({"state": WAITING_LANGUAGE, "lang": "en", "lat": None, "lon": None})
    send_text(phone, STRINGS["en"]["welcome"])


# ── State: WAITING_LANGUAGE ─────────────────────────────────────────────────

def _handle_language_state(phone: str, session: dict, raw_text: str) -> None:
    t = raw_text.strip()
    if t == "1" or t.lower() in ("english", "en"):
        session["lang"] = "en"
    elif t == "2" or "kannada" in t.lower() or "ಕನ್ನಡ" in t:
        session["lang"] = "kn"
    else:
        send_text(phone, s(session, "nudge_language"))
        return
    send_text(phone, s(session, "lang_set") + s(session, "ask_location"))
    session["state"] = WAITING_LOCATION


# ── State: WAITING_LOCATION ──────────────────────────────────────────────────

def _process_location(phone: str, session: dict, lat: float, lon: float) -> None:
    """Store location, send confirmation, check outbreaks, advance state."""
    session["lat"] = lat
    session["lon"] = lon
    send_text(phone, s(session, "location_received").format(lat=lat, lon=lon))

    outbreaks = _check_nearby_outbreaks(lat, lon)
    if outbreaks:
        lines = [s(session, "outbreak_header")]
        for ob in outbreaks:
            lines.append(
                s(session, "outbreak_row").format(
                    disease=ob["disease_type"], count=ob["count"]
                )
            )
        lines.append(s(session, "outbreak_footer"))
        send_text(phone, "\n".join(lines))
    else:
        send_text(phone, s(session, "no_outbreak"))

    session["state"] = WAITING_PHOTO


def _handle_location_state(phone: str, session: dict, msg: dict) -> None:
    # Path A: native WhatsApp location share
    if msg.get("type") == "location":
        loc = msg["location"]
        _process_location(phone, session, loc["latitude"], loc["longitude"])
        return
    # Path B: typed coordinates in text
    if msg.get("type") == "text":
        coords = parse_typed_location(msg["text"]["body"])
        if coords:
            _process_location(phone, session, *coords)
            return
    send_text(phone, s(session, "nudge_location"))


# ── State: WAITING_PHOTO ─────────────────────────────────────────────────────

def _handle_photo_state(phone: str, session: dict, msg: dict) -> None:
    lat = session.get("lat")
    lon = session.get("lon")
    msg_type = msg.get("type", "")

    # Allow location refresh mid-session (same as Telegram bot)
    if msg_type == "location":
        loc = msg["location"]
        _process_location(phone, session, loc["latitude"], loc["longitude"])
        return
    if msg_type == "text":
        coords = parse_typed_location(msg["text"].get("body", ""))
        if coords:
            _process_location(phone, session, *coords)
            return

    if msg_type != "image":
        send_text(phone, s(session, "nudge_photo"))
        return

    send_text(phone, s(session, "analysing"))

    # ── Download image from WhatsApp Cloud API ──
    media_id = msg["image"]["id"]
    try:
        img_bytes = download_media(media_id)
    except Exception as exc:
        logger.error("Media download failed: %s", exc)
        send_text(phone, s(session, "analysis_error").format(err=str(exc)))
        return

    # ── Save temp file and POST to /analyze-image ──
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(img_bytes)

        form_data: dict = {"language": session.get("lang", "en")}
        if lat is not None:
            form_data["latitude"]  = lat
            form_data["longitude"] = lon

        with open(tmp_path, "rb") as img_file:
            response = requests.post(
                f"{API_BASE_URL}/analyze-image",
                files={"file": ("crop.jpg", img_file, "image/jpeg")},
                data=form_data,
                timeout=60,
            )
        response.raise_for_status()
        result = response.json()

    except requests.exceptions.ConnectionError:
        send_text(phone, s(session, "conn_error").format(url=API_BASE_URL))
        return
    except Exception as exc:
        logger.error("API error: %s", exc)
        send_text(phone, s(session, "analysis_error").format(err=str(exc)))
        return
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # ── Build and send diagnosis reply ──
    disease    = result.get("disease_name", "Unknown")
    confidence = result.get("confidence", "Unknown")
    remedy     = result.get("remedy", "N/A")
    prevention = result.get("prevention", "N/A")
    alert      = result.get("outbreak_alert")
    report_id  = result.get("report_id")

    conf_emoji = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(confidence, "⚪")

    lines = [
        s(session, "diagnosis_header"), "",
        f"{s(session, 'disease_label')} {disease}",
        f"{conf_emoji} {s(session, 'confidence_label')} {confidence}", "",
        f"{s(session, 'remedy_label')}\n{remedy}", "",
        f"{s(session, 'prevention_label')}\n{prevention}",
    ]
    if report_id:
        loc_note = f" (📍 {lat:.4f}°, {lon:.4f}°)" if lat is not None else ""
        lines += ["", s(session, "report_stored").format(id=report_id, loc=loc_note)]
    if alert:
        lines += ["", "━━━━━━━━━━━━━━━━", alert]
    lines.append(s(session, "next_photo"))

    send_text(phone, "\n".join(lines))
    # State stays WAITING_PHOTO — user can keep sending photos


# ---------------------------------------------------------------------------
# Flask webhook endpoints
# ---------------------------------------------------------------------------

@app.get("/whatsapp")
def verify_webhook():
    """
    Meta sends a GET request to verify the webhook URL.
    We must echo back hub.challenge when hub.verify_token matches.
    """
    hub_mode      = request.args.get("hub.mode")
    hub_token     = request.args.get("hub.verify_token")
    hub_challenge = request.args.get("hub.challenge")

    if hub_mode == "subscribe" and hub_token == WA_VERIFY_TOKEN:
        logger.info("✅ Webhook verified by Meta.")
        return hub_challenge, 200
    logger.warning("❌ Webhook verification failed. Token mismatch.")
    return "Forbidden", 403


@app.post("/whatsapp")
def receive_webhook():
    """
    Meta sends a POST for every incoming WhatsApp message.
    We parse the payload and dispatch to the appropriate state handler.
    """
    body = request.get_json(force=True, silent=True) or {}
    logger.debug("Incoming webhook: %s", body)

    try:
        entry   = body["entry"][0]
        change  = entry["changes"][0]
        value   = change["value"]

        # Ignore status updates (delivered, read, etc.)
        if "messages" not in value:
            return jsonify({"status": "no_message"}), 200

        msg      = value["messages"][0]
        phone    = msg["from"]          # e.g. "919876543210"
        msg_type = msg.get("type", "")

        session = get_session(phone)
        session.setdefault("audio_fails", 0)
        state   = session.get("state", WAITING_LANGUAGE)

        # Resolve the text body safely (only present for type=text)
        text_body  = msg.get("text", {}).get("body", "").strip()

        # ── Audio Handle ──────────────────────────────────────────────────
        if msg_type == "audio":
            try:
                media_id = msg["audio"]["id"]
                audio_bytes = download_media(media_id)
                # Save to temp file
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".ogg")
                try:
                    with os.fdopen(tmp_fd, "wb") as f:
                        f.write(audio_bytes)
                    
                    lang = session.get("lang", "en")
                    send_text(phone, s(session, "transcribing"))

                    with open(tmp_path, "rb") as f:
                        resp = requests.post(
                            f"{API_BASE_URL}/transcribe-audio",
                            files={"file": ("audio.ogg", f, "audio/ogg")},
                            data={"language": lang},
                            timeout=30,
                        )
                    resp.raise_for_status()
                    text_body = resp.json().get("text", "").strip()
                    
                    if not text_body:
                        raise ValueError("Empty transcription")
                    
                    msg_type = "text"   # pretend it's text now
                    msg["text"] = {"body": text_body} # update msg for state machines
                    session["audio_fails"] = 0        # success resets fail counter
                    
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
            except Exception as e:
                logger.error("Audio transcription failed: %s", e)
                session["audio_fails"] += 1
                if session["audio_fails"] >= 3:
                    # rollback to text
                    send_text(phone, s(session, "audio_fallback"))
                    session["audio_fails"] = 0
                else:
                    send_text(phone, s(session, "audio_retry"))
                return jsonify({"status": "ok"}), 200

        text_lower = text_body.lower()

        # ── Global: restart / cancel commands ────────────────────────────
        if text_lower in ("hi", "hello", "start", "restart", "/start", "/restart"):
            _handle_start(phone, session)
            return jsonify({"status": "ok"}), 200

        if text_lower in ("cancel", "/cancel", "stop", "bye"):
            lang = session.get("lang", "en")
            sessions.pop(phone, None)
            send_text(phone, STRINGS[lang]["session_ended"])
            return jsonify({"status": "ok"}), 200

        # ── State machine ─────────────────────────────────────────────────
        if state == WAITING_LANGUAGE:
            _handle_language_state(phone, session, text_body)
        elif state == WAITING_LOCATION:
            _handle_location_state(phone, session, msg)
        elif state == WAITING_PHOTO:
            _handle_photo_state(phone, session, msg)
        else:
            # Unexpected state — restart gracefully
            _handle_start(phone, session)

    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("Malformed webhook payload (%s): %s", type(exc).__name__, exc)

    # Always return 200 so Meta doesn't retry
    return jsonify({"status": "ok"}), 200


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    missing = []
    if not WA_TOKEN:    missing.append("WHATSAPP_ACCESS_TOKEN")
    if not WA_PHONE_ID: missing.append("WHATSAPP_PHONE_NUMBER_ID")
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}\n"
            "Copy .env.example → .env and fill in your values."
        )

    port = int(os.environ.get("WA_BOT_PORT", 5000))
    logger.info("🌾 CropRadar WhatsApp bot starting on port %d…", port)
    app.run(host="0.0.0.0", port=port, debug=False)
