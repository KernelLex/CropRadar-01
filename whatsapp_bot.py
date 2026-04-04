"""
CropRadar — WhatsApp Bot (Twilio Sandbox)

Key design:
  - Webhook returns EMPTY TwiML instantly (avoids Twilio's 15s timeout)
  - Heavy work (image download + AI analysis) runs in a background thread
  - Result sent back via Twilio REST API (outbound message)
  - Buttons via numbered quick-reply style (sandbox compatible)
"""

import os
import re
import threading
import requests
import tempfile
import pathlib
from flask import Flask, request, Response
from dotenv import load_dotenv
import database

load_dotenv()

API_URL            = os.getenv("CROPRADAR_API_URL", "http://localhost:8000")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WA_NUMBER   = "whatsapp:+14155238886"   # Twilio sandbox sender

app = Flask(__name__)
sessions: dict[str, dict] = {}

WAITING_LANGUAGE = "WAITING_LANGUAGE"
WAITING_LOCATION = "WAITING_LOCATION"
WAITING_PHOTO    = "WAITING_PHOTO"

# ---------------------------------------------------------------------------
# Bilingual strings
# ---------------------------------------------------------------------------
STRINGS = {
    "en": {
        "welcome":           "🌾 *Welcome to CropRadar!*\n\nI detect crop diseases from photos and alert you to outbreaks nearby.\n\nReply with:\n*1* — English\n*2* — ಕನ್ನಡ",
        "language_set":      "✅ Language set to *English*. Let's get started!",
        "ask_location":      "📍 *Step 1 — Share Your Location*\n\nSo I can check for disease outbreaks in your area.\n\nTap the 📎 attachment button → Location\nOR type coordinates:  12.97, 77.59",
        "location_received": "✅ Location received — *{lat:.4f}°, {lon:.4f}°*\n\n🔍 Checking for disease outbreaks in your area…",
        "outbreak_header":   "⚠️ *Outbreak Risk Alert!*\n\nThe following diseases have been reported near you recently:\n",
        "outbreak_row":      "🦠 *{disease}* — {count} reports within 50 km",
        "outbreak_footer":   "\n\n🛡️ Apply preventive treatment and monitor your crops closely.\n\n📸 *Step 2:* Now send me a photo of your crop leaf and I'll analyse it.",
        "no_outbreak":       "✅ *No active outbreaks detected near you.*\n\n📸 *Step 2:* Send me a photo of your crop leaf and I'll diagnose it!",
        "ask_photo":         "📸 *Send a photo* of your crop leaf for AI diagnosis.",
        "analysing":         "🔬 Analysing your crop image… please wait.",
        "diagnosis":         "🌿 *CropRadar Diagnosis*\n\n🦠 *Disease:* {disease}\n{confidence}\n\n💊 *Remedy:*\n{remedy}\n\n🛡️ *Prevention:*\n{prevention}\n\n📸 Send another photo to analyse more crops.",
        "outbreak_suffix":   "\n\n━━━━━━━━━━━━━━━━\n🚨 {alert}",
        "error":             "❌ Something went wrong. Please try again.",
        "invalid_location":  "❌ Couldn't read that location.\nTap 📎 → Location, or type:  lat, lon",
        "invalid_choice":    "Please reply *1* for English or *2* for ಕನ್ನಡ.",
        "audio_failed":      "❌ Couldn't transcribe audio. Please type or send a photo.",
    },
    "kn": {
        "welcome":           "🌾 *ಕ್ರಾಪ್‌ರಾಡಾರ್‌ಗೆ ಸ್ವಾಗತ!*\n\nನಾನು ಫೋಟೋಗಳಿಂದ ಬೆಳೆ ರೋಗಗಳನ್ನು ಪತ್ತೆ ಮಾಡಿ ಹತ್ತಿರದ ಹರಡುವಿಕೆ ಬಗ್ಗೆ ಎಚ್ಚರಿಸುತ್ತೇನೆ.\n\nಉತ್ತರಿಸಿ:\n*1* — English\n*2* — ಕನ್ನಡ",
        "language_set":      "✅ ಭಾಷೆ *ಕನ್ನಡ*ಕ್ಕೆ ಹೊಂದಿಸಲಾಗಿದೆ. ಪ್ರಾರಂಭಿಸೋಣ!",
        "ask_location":      "📍 *ಹಂತ 1 — ನಿಮ್ಮ ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ*\n\nನಿಮ್ಮ ಬಳಿ ರೋಗ ಹರಡುವಿಕೆ ಇದೆಯೇ ಎಂದು ಪರಿಶೀಲಿಸಲು.\n\n📎 ಅಟ್ಯಾಚ್‌ಮೆಂಟ್ → ಲೊಕೇಶನ್ ಟ್ಯಾಪ್ ಮಾಡಿ\nಅಥವಾ ಟೈಪ್ ಮಾಡಿ:  12.97, 77.59",
        "location_received": "✅ ಸ್ಥಳ ಸ್ವೀಕರಿಸಲಾಗಿದೆ — *{lat:.4f}°, {lon:.4f}°*\n\n🔍 ನಿಮ್ಮ ಪ್ರದೇಶದಲ್ಲಿ ರೋಗ ಹರಡುವಿಕೆ ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ…",
        "outbreak_header":   "⚠️ *ರೋಗ ಹರಡುವಿಕೆ ಎಚ್ಚರಿಕೆ!*\n\nಇತ್ತೀಚೆಗೆ ನಿಮ್ಮ ಬಳಿ ಈ ರೋಗಗಳು ವರದಿಯಾಗಿವೆ:\n",
        "outbreak_row":      "🦠 *{disease}* — 50 ಕಿ.ಮೀ ಒಳಗೆ {count} ವರದಿಗಳು",
        "outbreak_footer":   "\n\n🛡️ ತಡೆಗಟ್ಟುವ ಚಿಕಿತ್ಸೆ ಅನ್ವಯಿಸಿ ಮತ್ತು ನಿಮ್ಮ ಬೆಳೆಗಳನ್ನು ಗಮನಿಸಿ.\n\n📸 *ಹಂತ 2:* ಈಗ ನಿಮ್ಮ ಬೆಳೆ ಎಲೆಯ ಫೋಟೋ ಕಳುಹಿಸಿ.",
        "no_outbreak":       "✅ *ನಿಮ್ಮ ಬಳಿ ಯಾವುದೇ ರೋಗ ಹರಡುವಿಕೆ ಕಂಡುಬಂದಿಲ್ಲ.*\n\n📸 *ಹಂತ 2:* ರೋಗ ಪತ್ತೆಗಾಗಿ ನಿಮ್ಮ ಬೆಳೆ ಎಲೆಯ ಫೋಟೋ ಕಳುಹಿಸಿ!",
        "ask_photo":         "📸 ರೋಗ ನಿರ್ಣಯಕ್ಕಾಗಿ ಬೆಳೆ ಎಲೆಯ *ಫೋಟೋ ಕಳುಹಿಸಿ*.",
        "analysing":         "🔬 ಬೆಳೆ ಚಿತ್ರ ವಿಶ್ಲೇಷಿಸಲಾಗುತ್ತಿದೆ… ದಯವಿಟ್ಟು ನಿರೀಕ್ಷಿಸಿ.",
        "diagnosis":         "🌿 *ಕ್ರಾಪ್‌ರಾಡಾರ್ ರೋಗ ನಿರ್ಣಯ*\n\n🦠 *ರೋಗ:* {disease}\n{confidence}\n\n💊 *ಪರಿಹಾರ:*\n{remedy}\n\n🛡️ *ತಡೆಗಟ್ಟುವಿಕೆ:*\n{prevention}\n\n📸 ಮತ್ತೊಂದು ಫೋಟೋ ಕಳುಹಿಸಬಹುದು.",
        "outbreak_suffix":   "\n\n━━━━━━━━━━━━━━━━\n🚨 {alert}",
        "error":             "❌ ತಪ್ಪಾಗಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        "invalid_location":  "❌ ಸ್ಥಳ ಓದಲಾಗಲಿಲ್ಲ.\n📎 → ಲೊಕೇಶನ್ ಟ್ಯಾಪ್ ಮಾಡಿ, ಅಥವಾ ಟೈಪ್ ಮಾಡಿ:  lat, lon",
        "invalid_choice":    "*1* (English) ಅಥವಾ *2* (ಕನ್ನಡ) ಉತ್ತರಿಸಿ.",
        "audio_failed":      "❌ ಆಡಿಯೋ ಅನುವಾದ ವಿಫಲ. ದಯವಿಟ್ಟು ಟೈಪ್ ಮಾಡಿ ಅಥವಾ ಫೋಟೋ ಕಳುಹಿಸಿ.",
    },
}

CONF_EMOJI = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
LOC_RE     = re.compile(r'(-?\d{1,3}(?:\.\d+)?)[,\s]+(-?\d{1,3}(?:\.\d+)?)')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def s(lang: str, key: str, **kwargs) -> str:
    text = STRINGS.get(lang, STRINGS["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


def empty_twiml() -> Response:
    """Return an empty TwiML response immediately — prevents Twilio timeout."""
    xml = "<?xml version='1.0' encoding='UTF-8'?><Response></Response>"
    return Response(xml, mimetype="text/xml")


def twiml(text: str) -> Response:
    """Return a TwiML response with a message (for fast replies only)."""
    safe = (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
    xml = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{safe}</Message></Response>"
    return Response(xml, mimetype="text/xml")


def send_message(to: str, text: str) -> None:
    """Send an outbound WhatsApp message via Twilio REST API."""
    try:
        requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={"From": TWILIO_WA_NUMBER, "To": to, "Body": text},
            timeout=15,
        )
    except Exception as e:
        print(f"[send_message error] {e}")


def download_media(url: str) -> bytes:
    resp = requests.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=30)
    resp.raise_for_status()
    return resp.content


# ---------------------------------------------------------------------------
# Background worker — runs after webhook returns
# ---------------------------------------------------------------------------
def _analyse_and_reply(sender: str, session: dict, media_url: str) -> None:
    lang = session["lang"]
    lat  = session.get("lat")
    lon  = session.get("lon")
    tmp  = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        pathlib.Path(tmp).write_bytes(download_media(media_url))

        data: dict = {"language": lang}
        if lat is not None:
            data["latitude"]  = str(lat)
            data["longitude"] = str(lon)

        with open(tmp, "rb") as f:
            resp = requests.post(
                f"{API_URL}/analyze-image",
                files={"file": ("crop.jpg", f, "image/jpeg")},
                data=data,
                timeout=60,
            )

        if not resp.ok:
            send_message(sender, s(lang, "error"))
            return

        result   = resp.json()
        conf     = result.get("confidence", "?")
        conf_str = f"{CONF_EMOJI.get(conf, '⚪')} {conf}"

        msg = s(lang, "diagnosis",
                disease=result.get("disease_name", "Unknown"),
                confidence=conf_str,
                remedy=result.get("remedy", ""),
                prevention=result.get("prevention", ""))

        if result.get("outbreak_alert"):
            msg += s(lang, "outbreak_suffix", alert=result["outbreak_alert"])

        send_message(sender, msg)

    except Exception as e:
        print(f"[_analyse_and_reply error] {e}")
        send_message(sender, s(lang, "error"))
    finally:
        if tmp:
            pathlib.Path(tmp).unlink(missing_ok=True)


def _transcribe_and_reply(sender: str, session: dict, media_url: str) -> None:
    lang = session.get("lang", "en")
    tmp  = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".ogg")
        os.close(fd)
        pathlib.Path(tmp).write_bytes(download_media(media_url))

        with open(tmp, "rb") as f:
            resp = requests.post(
                f"{API_URL}/transcribe-audio",
                files={"file": ("voice.ogg", f, "audio/ogg")},
                data={"language": lang},
                timeout=30,
            )

        text = resp.json().get("text", "").strip() if resp.ok else ""
        if not text:
            send_message(sender, s(lang, "audio_failed"))
            return

        # Process transcribed text as a normal message
        _handle_text(sender, session, text)

    except Exception as e:
        print(f"[_transcribe_and_reply error] {e}")
        send_message(sender, s(lang, "audio_failed"))
    finally:
        if tmp:
            pathlib.Path(tmp).unlink(missing_ok=True)


def _handle_text(sender: str, session: dict, body: str) -> None:
    """Process a text body — called directly or after audio transcription."""
    state = session["state"]
    lang  = session["lang"]

    if state == WAITING_LOCATION:
        m = LOC_RE.search(body)
        if m:
            _do_location(sender, session, float(m.group(1)), float(m.group(2)))
        else:
            send_message(sender, s(lang, "invalid_location"))

    elif state == WAITING_PHOTO:
        send_message(sender, s(lang, "ask_photo"))


def _do_location(sender: str, session: dict, lat: float, lon: float) -> None:
    lang = session["lang"]
    session.update(lat=lat, lon=lon, state=WAITING_PHOTO)

    # Persist location so this user receives future outbreak broadcasts
    database.upsert_whatsapp_user(sender, lang, latitude=lat, longitude=lon)

    # Step 1 — immediate confirmation
    send_message(sender, s(lang, "location_received", lat=lat, lon=lon))

    # Step 2 — predictive risk report (weather + NDVI + disease history)
    try:
        risk_resp = requests.get(
            f"{API_URL}/risk-report",
            params={"lat": lat, "lon": lon, "language": lang},
            timeout=15,
        )
        if risk_resp.ok:
            report_text = risk_resp.json().get("report_text", "")
            if report_text:
                send_message(sender, report_text)
    except Exception as exc:
        print(f"[_do_location risk-report error] {exc}")

    # Step 3 — query outbreak API (confirmed recent cases)
    try:
        resp = requests.get(
            f"{API_URL}/nearby-alerts",
            params={"lat": lat, "lon": lon, "radius_km": 50},
            timeout=10,
        )
        outbreaks = resp.json().get("outbreaks", []) if resp.ok else []
    except Exception:
        outbreaks = []

    # Step 4 — send structured outbreak result
    if outbreaks:
        lines = [s(lang, "outbreak_header")]
        for ob in outbreaks:
            lines.append(s(lang, "outbreak_row",
                           disease=ob["disease_type"], count=ob["count"]))
        lines.append(s(lang, "outbreak_footer"))
        send_message(sender, "\n".join(lines))
    else:
        send_message(sender, s(lang, "no_outbreak"))


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender     = request.form.get("From", "")
    body       = request.form.get("Body", "").strip()
    num_media  = int(request.form.get("NumMedia", 0))
    media_url  = request.form.get("MediaUrl0", "")
    media_type = request.form.get("MediaContentType0", "")
    lat_str    = request.form.get("Latitude")
    lon_str    = request.form.get("Longitude")

    session = sessions.setdefault(sender, {"state": WAITING_LANGUAGE, "lang": "en"})

    # ── Reset ──────────────────────────────────────────────────────────────
    if body.lower() in ("hi", "hello", "start", "restart", "/start"):
        sessions[sender] = {"state": WAITING_LANGUAGE, "lang": "en"}
        return twiml(s("en", "welcome"))   # fast — return directly

    # ── Language selection (fast) ──────────────────────────────────────────
    if session["state"] == WAITING_LANGUAGE:
        if body in ("1", "1️⃣"):
            session.update(lang="en", state=WAITING_LOCATION)
            database.upsert_whatsapp_user(sender, "en")
            return twiml(s("en", "language_set") + "\n\n" + s("en", "ask_location"))
        if body in ("2", "2️⃣"):
            session.update(lang="kn", state=WAITING_LOCATION)
            database.upsert_whatsapp_user(sender, "kn")
            return twiml(s("kn", "language_set") + "\n\n" + s("kn", "ask_location"))
        return twiml(s("en", "invalid_choice"))

    lang  = session["lang"]
    state = session["state"]

    # ── Native location share (fast) ──────────────────────────────────────
    if lat_str and lon_str:
        threading.Thread(
            target=_do_location,
            args=(sender, session, float(lat_str), float(lon_str)),
            daemon=True,
        ).start()
        return empty_twiml()

    # ── Audio — background transcribe ─────────────────────────────────────
    if num_media > 0 and media_type.startswith("audio/"):
        send_message(sender, s(lang, "analysing"))
        threading.Thread(
            target=_transcribe_and_reply,
            args=(sender, session, media_url),
            daemon=True,
        ).start()
        return empty_twiml()

    # ── Image — background analyse ────────────────────────────────────────
    if num_media > 0 and media_type.startswith("image/"):
        if state == WAITING_PHOTO:
            # Acknowledge immediately so user knows it's processing
            send_message(sender, s(lang, "analysing"))
            threading.Thread(
                target=_analyse_and_reply,
                args=(sender, session, media_url),
                daemon=True,
            ).start()
            return empty_twiml()
        return twiml(s(lang, "ask_photo"))

    # ── Text in location state ────────────────────────────────────────────
    if state == WAITING_LOCATION:
        m = LOC_RE.search(body)
        if m:
            threading.Thread(
                target=_do_location,
                args=(sender, session, float(m.group(1)), float(m.group(2))),
                daemon=True,
            ).start()
            return empty_twiml()
        return twiml(s(lang, "invalid_location"))

    return twiml(s(lang, "ask_photo"))


@app.route("/health")
def health():
    return {"status": "ok", "service": "CropRadar WhatsApp Bot (Twilio)"}


if __name__ == "__main__":
    port = int(os.getenv("WHATSAPP_PORT", 5001))
    print(f"\n🌱 CropRadar — Twilio WhatsApp Bot")
    print(f"   Port    : {port}")
    print(f"   Webhook : http://<tunnel-url>/whatsapp\n")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
