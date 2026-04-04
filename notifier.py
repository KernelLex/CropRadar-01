"""
notifier.py — Multi-channel outbreak broadcast for CropRadar

Channels:
  1. Telegram  — via Bot API       (bot_users table)
  2. WhatsApp  — via Twilio REST   (whatsapp_users table)
  3. App push  — via Firebase FCM  (app_devices table)

Called from api.py → _maybe_broadcast_outbreak() in a background thread.
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WA_NUMBER   = "whatsapp:+14155238886"   # Twilio sandbox sender

# Firebase: set FCM_SERVER_KEY in .env (Firebase Console → Project Settings
# → Cloud Messaging → Server key).  Skipped gracefully if not set.
FCM_SERVER_KEY = os.environ.get("FCM_SERVER_KEY", "")

# ---------------------------------------------------------------------------
# Bilingual alert templates
# ---------------------------------------------------------------------------

ALERT_EN = (
    "⚠️ *CropRadar Outbreak Alert*\n\n"
    "Possible outbreak of *{disease}* detected near your area.\n"
    "{count} reports within 50 km in the last 48 hours.\n\n"
    "🛡️ Inspect nearby crops, isolate affected plants, "
    "and begin preventive treatment early."
)

ALERT_KN = (
    "⚠️ *ಕ್ರಾಪ್‌ರಾಡಾರ್ ರೋಗ ಹರಡುವಿಕೆ ಎಚ್ಚರಿಕೆ*\n\n"
    "ನಿಮ್ಮ ಪ್ರದೇಶದ ಬಳಿ *{disease}* ರೋಗ ಹರಡುವಿಕೆ ಪತ್ತೆಯಾಗಿದೆ.\n"
    "ಕಳೆದ 48 ಗಂಟೆಗಳಲ್ಲಿ 50 ಕಿ.ಮೀ ಒಳಗೆ {count} ವರದಿಗಳು.\n\n"
    "🛡️ ಬೆಳೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿ, ಬಾಧಿತ ಸಸ್ಯಗಳನ್ನು ಪ್ರತ್ಯೇಕಿಸಿ "
    "ಮತ್ತು ತಡೆಗಟ್ಟುವ ಚಿಕಿತ್ಸೆ ಪ್ರಾರಂಭಿಸಿ."
)

TEMPLATES = {"en": ALERT_EN, "kn": ALERT_KN}


def _fmt(disease: str, count: int, lang: str) -> str:
    tmpl = TEMPLATES.get(lang, ALERT_EN)
    return tmpl.format(disease=disease, count=count)


# ---------------------------------------------------------------------------
# Master broadcast — calls all three channels
# ---------------------------------------------------------------------------

def broadcast_outbreak_alert(
    disease: str,
    count: int,
    telegram_users: list[dict],
    whatsapp_users: list[dict],
    app_devices: list[dict],
) -> dict:
    """
    Send outbreak alert across Telegram, WhatsApp and FCM push.
    Returns dict with sent counts per channel.
    """
    tg  = _broadcast_telegram(disease, count, telegram_users)
    wa  = _broadcast_whatsapp(disease, count, whatsapp_users)
    fcm = _broadcast_fcm(disease, count, app_devices)

    logger.info(
        "Outbreak broadcast — disease=%s  telegram=%d  whatsapp=%d  fcm=%d",
        disease, tg, wa, fcm,
    )
    return {"telegram": tg, "whatsapp": wa, "fcm": fcm}


# ---------------------------------------------------------------------------
# Channel 1 — Telegram
# ---------------------------------------------------------------------------

def _broadcast_telegram(disease: str, count: int, users: list[dict]) -> int:
    if not TELEGRAM_TOKEN or not users:
        return 0

    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    sent = 0
    for user in users:
        lang = user.get("language", "en")
        try:
            resp = requests.post(
                url,
                json={
                    "chat_id":    user["chat_id"],
                    "text":       _fmt(disease, count, lang),
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            if resp.ok:
                sent += 1
            else:
                logger.warning("Telegram send failed chat_id=%s: %s",
                               user["chat_id"], resp.text)
        except Exception as exc:
            logger.warning("Telegram send error chat_id=%s: %s",
                           user["chat_id"], exc)
    return sent


# ---------------------------------------------------------------------------
# Channel 2 — WhatsApp (Twilio)
# ---------------------------------------------------------------------------

def _broadcast_whatsapp(disease: str, count: int, users: list[dict]) -> int:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not users:
        return 0

    url  = (f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{TWILIO_ACCOUNT_SID}/Messages.json")
    sent = 0
    for user in users:
        lang = user.get("language", "en")
        text = _fmt(disease, count, lang).replace("*", "")  # strip Markdown
        try:
            resp = requests.post(
                url,
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                data={
                    "From": TWILIO_WA_NUMBER,
                    "To":   user["wa_number"],
                    "Body": text,
                },
                timeout=15,
            )
            if resp.ok:
                sent += 1
            else:
                logger.warning("WhatsApp send failed to=%s: %s",
                               user["wa_number"], resp.text)
        except Exception as exc:
            logger.warning("WhatsApp send error to=%s: %s",
                           user["wa_number"], exc)
    return sent


# ---------------------------------------------------------------------------
# Channel 3 — FCM push (Firebase Cloud Messaging)
# ---------------------------------------------------------------------------

def _broadcast_fcm(disease: str, count: int, devices: list[dict]) -> int:
    """
    Send push via FCM legacy HTTP API (batches of 1000 tokens).
    Skipped gracefully if FCM_SERVER_KEY is not configured.
    """
    if not FCM_SERVER_KEY or not devices:
        return 0

    tokens = [d["fcm_token"] for d in devices if d.get("fcm_token")]
    if not tokens:
        return 0

    BATCH = 1000
    sent  = 0

    for i in range(0, len(tokens), BATCH):
        batch = tokens[i : i + BATCH]
        payload = {
            "registration_ids": batch,
            "notification": {
                "title": "⚠️ CropRadar Outbreak Alert",
                "body":  (f"{disease} detected near you — "
                          f"{count} reports within 50 km."),
                "sound": "default",
            },
            "data": {
                "disease": disease,
                "count":   str(count),
                "type":    "outbreak_alert",
            },
            "priority": "high",
        }
        try:
            resp = requests.post(
                "https://fcm.googleapis.com/fcm/send",
                json=payload,
                headers={
                    "Authorization": f"key={FCM_SERVER_KEY}",
                    "Content-Type":  "application/json",
                },
                timeout=15,
            )
            if resp.ok:
                result = resp.json()
                sent  += result.get("success", 0)
                failed = result.get("failure", 0)
                if failed:
                    logger.warning("FCM batch: %d failed of %d", failed, len(batch))
            else:
                logger.warning("FCM batch failed: %s", resp.text)
        except Exception as exc:
            logger.warning("FCM batch error: %s", exc)

    return sent
