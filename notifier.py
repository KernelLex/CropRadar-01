"""
notifier.py — Multi-channel outbreak broadcast for CropRadar

Channels:
  1. Telegram  — via Bot API              (bot_users table)
  2. WhatsApp  — via Twilio REST API      (whatsapp_users table)
  3. App push  — via Firebase FCM V1 API  (app_devices table)

Called from api.py → _maybe_broadcast_outbreak() in a background thread.
"""

import json
import logging
import os
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WA_NUMBER   = "whatsapp:+14155238886"

# Firebase service account JSON path (never commit this file)
_SA_PATH = Path(__file__).resolve().parent / "firebase-adminsdk-account.json"

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
    return TEMPLATES.get(lang, ALERT_EN).format(disease=disease, count=count)


# ---------------------------------------------------------------------------
# Master broadcast
# ---------------------------------------------------------------------------

def broadcast_outbreak_alert(
    disease: str,
    count: int,
    telegram_users: list[dict],
    whatsapp_users: list[dict],
    app_devices: list[dict],
) -> dict:
    tg  = _broadcast_telegram(disease, count, telegram_users)
    wa  = _broadcast_whatsapp(disease, count, whatsapp_users)
    fcm = _broadcast_fcm(disease, count, app_devices)
    logger.info("Outbreak broadcast — disease=%s  tg=%d  wa=%d  fcm=%d",
                disease, tg, wa, fcm)
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
        try:
            resp = requests.post(url, json={
                "chat_id":    user["chat_id"],
                "text":       _fmt(disease, count, user.get("language", "en")),
                "parse_mode": "Markdown",
            }, timeout=10)
            if resp.ok:
                sent += 1
            else:
                logger.warning("Telegram fail chat_id=%s: %s", user["chat_id"], resp.text)
        except Exception as exc:
            logger.warning("Telegram error chat_id=%s: %s", user["chat_id"], exc)
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
        text = _fmt(disease, count, user.get("language", "en")).replace("*", "")
        try:
            resp = requests.post(url,
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                data={"From": TWILIO_WA_NUMBER, "To": user["wa_number"], "Body": text},
                timeout=15)
            if resp.ok:
                sent += 1
            else:
                logger.warning("WhatsApp fail to=%s: %s", user["wa_number"], resp.text)
        except Exception as exc:
            logger.warning("WhatsApp error to=%s: %s", user["wa_number"], exc)
    return sent


# ---------------------------------------------------------------------------
# Channel 3 — FCM V1 API (Firebase)
# ---------------------------------------------------------------------------

# Simple in-memory token cache: {token_str: expires_at}
_fcm_token_cache: dict = {}


def _get_fcm_access_token() -> str | None:
    """
    Obtain a short-lived OAuth2 access token from the service account JSON
    using only the `requests` library (no google-auth dependency needed).
    Caches the token until 60s before expiry.
    """
    if not _SA_PATH.exists():
        logger.warning("Firebase service account not found at %s", _SA_PATH)
        return None

    now = time.time()
    cached = _fcm_token_cache.get("token")
    expires = _fcm_token_cache.get("expires", 0)
    if cached and now < expires:
        return cached

    try:
        sa = json.loads(_SA_PATH.read_text())
    except Exception as exc:
        logger.error("Cannot read service account JSON: %s", exc)
        return None

    # Build a signed JWT manually
    import base64
    import json as _json
    import hmac
    import hashlib

    # Header
    header = base64.urlsafe_b64encode(
        _json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    # Claims
    iat = int(now)
    exp = iat + 3600
    claims = {
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/firebase.messaging",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": iat,
        "exp": exp,
    }
    payload = base64.urlsafe_b64encode(
        _json.dumps(claims).encode()
    ).rstrip(b"=").decode()

    signing_input = f"{header}.{payload}".encode()

    # Sign with RS256 using the private key
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        private_key = serialization.load_pem_private_key(
            sa["private_key"].encode(), password=None
        )
        signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    except ImportError:
        logger.warning("cryptography package not installed — FCM push disabled. "
                       "Run: pip install cryptography")
        return None
    except Exception as exc:
        logger.error("JWT signing error: %s", exc)
        return None

    jwt = f"{header}.{payload}.{sig_b64}"

    # Exchange JWT for access token
    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion":  jwt,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        _fcm_token_cache["token"]   = token
        _fcm_token_cache["expires"] = now + data.get("expires_in", 3600) - 60
        return token
    except Exception as exc:
        logger.error("FCM token exchange failed: %s", exc)
        return None


def _broadcast_fcm(disease: str, count: int, devices: list[dict]) -> int:
    """Send push via FCM V1 API (one request per token — V1 doesn't support multicast yet)."""
    if not devices:
        return 0

    access_token = _get_fcm_access_token()
    if not access_token:
        return 0

    # Extract project_id from service account
    try:
        sa = json.loads(_SA_PATH.read_text())
        project_id = sa["project_id"]
    except Exception:
        return 0

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
    }

    sent = 0
    for device in devices:
        token = device.get("fcm_token")
        if not token:
            continue
        payload = {
            "message": {
                "token": token,
                "notification": {
                    "title": "⚠️ CropRadar Outbreak Alert",
                    "body":  (f"{disease} detected near you — "
                              f"{count} reports within 50 km."),
                },
                "data": {
                    "disease": disease,
                    "count":   str(count),
                    "type":    "outbreak_alert",
                },
                "android": {
                    "priority": "high",
                    "notification": {"sound": "default"},
                },
            }
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.ok:
                sent += 1
            else:
                logger.warning("FCM V1 fail token=...%s: %s", token[-8:], resp.text)
                # Token may be expired — could clean up from DB here
        except Exception as exc:
            logger.warning("FCM V1 error: %s", exc)

    return sent
